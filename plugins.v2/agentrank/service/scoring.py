"""AgentRank 版本化策略学习与后续确定性评分入口。"""

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from ..model.config import WEIGHT_DEFAULTS
from ..model.memory import PreferenceMemory
from ..model.playback import PlaybackSample, PlaybackSnapshot
from ..model.policy import (
    POLICY_DELTA_LIMIT,
    POLICY_WEIGHT_NAMES,
    PolicySnapshot,
)


POLICY_ALGORITHM_VERSION = 1
MIN_INDEPENDENT_PLAYBACK_EVIDENCE = 2
MEMORY_DELTA_SCALE = 0.10
PLAYBACK_DELTA_SCALE = 0.04
ABANDONMENT_DELTA_SCALE = 0.01
_ROUND_DIGITS = 6

_CATEGORY_WEIGHTS = {
    "type": ("type_weight",),
    "media_type": ("type_weight",),
    "genre": ("theme_weight",),
    "theme": ("theme_weight",),
    "actor": ("actor_weight",),
    "character": ("actor_weight",),
    "director": ("director_weight",),
    "creator": ("actor_weight", "director_weight"),
    "region": ("region_weight",),
    "era": ("year_weight",),
    "year": ("year_weight",),
    "rating": ("rating_weight",),
    "quality": ("rating_weight",),
    "heat": ("heat_weight",),
    "popularity": ("heat_weight",),
    "novelty": ("freshness_weight",),
    "freshness": ("freshness_weight",),
    "style": ("similarity_weight",),
    "emotion": ("similarity_weight",),
    "cognition": ("similarity_weight",),
    "narrative": ("similarity_weight",),
    "pacing": ("similarity_weight",),
    "pace": ("similarity_weight",),
    "completion": ("similarity_weight",),
    "similarity": ("similarity_weight",),
}


@dataclass(frozen=True)
class _PolicySignal:
    """表示一个只参与策略聚合的最小可信证据信号。"""

    weight_name: str
    delta: float
    certainty: float
    evidence_refs: Tuple[str, ...]


class PolicyLearningService:
    """从已确认记忆与独立播放事实生成可重放策略快照。"""

    def __init__(
        self,
        repository: Any,
        now_factory: Callable[[], datetime] = None,
        max_revision_retries: int = 3,
    ) -> None:
        """注入存储、时钟和记忆并发重试上限。"""
        self.repository = repository
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self._max_revision_retries = max(1, min(int(max_revision_retries), 10))

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        """将数值限制到闭区间并做稳定小数归一化。"""
        return round(min(maximum, max(minimum, float(value))), _ROUND_DIGITS)

    @classmethod
    def _base_weights(cls, raw: Mapping[str, Any]) -> Dict[str, float]:
        """复制十项用户配置作为不可覆盖的策略基准。"""
        source = raw if isinstance(raw, Mapping) else {}
        result: Dict[str, float] = {}
        for name in POLICY_WEIGHT_NAMES:
            try:
                value = float(source.get(name, WEIGHT_DEFAULTS[name]))
            except (TypeError, ValueError):
                value = WEIGHT_DEFAULTS[name]
            if not math.isfinite(value):
                value = WEIGHT_DEFAULTS[name]
            result[name] = cls._clamp(value, 0.0, 1.0)
        return result

    @staticmethod
    def _memory_weight_names(category: str) -> Tuple[str, ...]:
        """把已确认偏好类别映射到受影响的十项策略维度。"""
        normalized = str(category or "").strip().casefold()
        if normalized in POLICY_WEIGHT_NAMES:
            return (normalized,)
        return _CATEGORY_WEIGHTS.get(normalized, ())

    @staticmethod
    def _canonical_playback_samples(
        samples: Iterable[PlaybackSample],
    ) -> Tuple[Dict[str, Any], ...]:
        """按作品身份合并重复播放，防止同一作品冒充独立证据。"""
        grouped: Dict[str, Dict[str, Any]] = {}
        for sample in samples or ():
            stable_id = str(getattr(sample, "stable_id", "") or "").strip()
            if not stable_id:
                continue
            current = grouped.setdefault(
                stable_id,
                {
                    "stable_id": stable_id,
                    "media_types": set(),
                    "genres": set(),
                    "completed": False,
                    "abandoned": False,
                    "observed": False,
                },
            )
            media_type = str(getattr(sample, "media_type", "") or "").strip().casefold()
            if media_type:
                current["media_types"].add(media_type)
            current["genres"].update(
                str(item or "").strip().casefold()
                for item in getattr(sample, "genres", ()) or ()
                if str(item or "").strip()
            )
            current["abandoned"] = current["abandoned"] or bool(
                getattr(sample, "abandoned", False)
            )
            current["completed"] = current["completed"] or bool(
                getattr(sample, "completed", False)
            )
            current["observed"] = current["observed"] or bool(
                getattr(sample, "completed", False)
                or int(getattr(sample, "play_count", 0) or 0) > 0
                or int(getattr(sample, "watch_minutes", 0) or 0) > 0
            )
        return tuple(
            {
                "stable_id": stable_id,
                "media_types": tuple(sorted(value["media_types"])),
                "genres": tuple(sorted(value["genres"])),
                "abandoned": value["abandoned"] and not value["completed"],
                "observed": value["observed"],
            }
            for stable_id, value in sorted(grouped.items())
        )

    @classmethod
    def _playback_fingerprint(cls, playback: PlaybackSnapshot) -> str:
        """按策略实际使用的去重播放事实计算顺序无关指纹。"""
        payload = {
            "profile_id": playback.profile_id,
            "source": playback.source,
            "samples": cls._canonical_playback_samples(playback.samples),
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _memory_signals(cls, memory: PreferenceMemory) -> List[_PolicySignal]:
        """把当前确认态偏好转换为维度重要性信号，不读取旧谱系。"""
        signals: List[_PolicySignal] = []
        for item in sorted(
            memory.active_items(),
            key=lambda value: (value.source_event_sequence, value.item_id),
        ):
            weight_names = cls._memory_weight_names(item.category)
            if not weight_names:
                continue
            # 正向和负向偏好都说明该维度重要；偏好方向由后续评分证据决定。
            delta = MEMORY_DELTA_SCALE * item.strength / len(weight_names)
            for weight_name in weight_names:
                signals.append(
                    _PolicySignal(
                        weight_name=weight_name,
                        delta=delta,
                        certainty=item.certainty,
                        evidence_refs=(f"memory:{item.item_id}",),
                    )
                )
        return signals

    @classmethod
    def _playback_signals(
        cls, playback: PlaybackSnapshot
    ) -> List[_PolicySignal]:
        """只让至少两部不同作品形成稳定播放信号，弃看保持弱负向。"""
        groups: Dict[Tuple[str, str, str], set] = defaultdict(set)
        for sample in cls._canonical_playback_samples(playback.samples):
            if not sample["observed"] and not sample["abandoned"]:
                continue
            polarity = "negative" if sample["abandoned"] else "positive"
            for media_type in sample["media_types"]:
                groups[("type_weight", media_type, polarity)].add(sample["stable_id"])
            for genre in sample["genres"]:
                groups[("theme_weight", genre, polarity)].add(sample["stable_id"])

        signals: List[_PolicySignal] = []
        for (weight_name, _value, polarity), stable_ids in sorted(groups.items()):
            count = len(stable_ids)
            if count < MIN_INDEPENDENT_PLAYBACK_EVIDENCE:
                continue
            if polarity == "negative":
                delta = -min(
                    ABANDONMENT_DELTA_SCALE * 2,
                    ABANDONMENT_DELTA_SCALE + 0.0025 * (count - 2),
                )
                certainty = min(0.35, 0.20 + 0.05 * (count - 2))
                ref_prefix = "playback:abandoned"
            else:
                delta = min(
                    PLAYBACK_DELTA_SCALE * 2,
                    PLAYBACK_DELTA_SCALE + 0.01 * (count - 2),
                )
                certainty = min(1.0, 0.60 + 0.10 * (count - 2))
                ref_prefix = "playback:observed"
            signals.append(
                _PolicySignal(
                    weight_name=weight_name,
                    delta=delta,
                    certainty=certainty,
                    evidence_refs=tuple(
                        f"{ref_prefix}:{stable_id}" for stable_id in sorted(stable_ids)
                    ),
                )
            )
        return signals

    @classmethod
    def _aggregate_signals(
        cls, signals: Iterable[_PolicySignal]
    ) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, Tuple[str, ...]]]:
        """按权重聚合有界增量、加权确定性和稳定证据引用。"""
        by_weight: Dict[str, List[_PolicySignal]] = defaultdict(list)
        for signal in signals:
            if signal.weight_name in POLICY_WEIGHT_NAMES:
                by_weight[signal.weight_name].append(signal)
        deltas: Dict[str, float] = {}
        certainties: Dict[str, float] = {}
        evidence: Dict[str, Tuple[str, ...]] = {}
        for name in POLICY_WEIGHT_NAMES:
            values = by_weight.get(name, [])
            total_delta = sum(item.delta for item in values)
            deltas[name] = cls._clamp(
                total_delta, -POLICY_DELTA_LIMIT, POLICY_DELTA_LIMIT
            )
            magnitude = sum(abs(item.delta) for item in values)
            certainties[name] = (
                cls._clamp(
                    sum(abs(item.delta) * item.certainty for item in values)
                    / magnitude,
                    0.0,
                    1.0,
                )
                if magnitude
                else 0.0
            )
            evidence[name] = tuple(
                sorted(
                    {
                        ref
                        for item in values
                        for ref in item.evidence_refs
                        if str(ref or "").strip()
                    }
                )
            )
        return deltas, certainties, evidence

    @staticmethod
    def _calibration() -> Dict[str, Any]:
        """返回随算法版本固定的学习边界与公式说明。"""
        return {
            "delta_limit": POLICY_DELTA_LIMIT,
            "memory_delta_scale": MEMORY_DELTA_SCALE,
            "playback_delta_scale": PLAYBACK_DELTA_SCALE,
            "abandonment_delta_scale": ABANDONMENT_DELTA_SCALE,
            "minimum_independent_playback": MIN_INDEPENDENT_PLAYBACK_EVIDENCE,
            "delta_semantics": "dimension_salience",
            "effective_formula": "clamp(base + delta * certainty, 0, 1)",
        }

    def build_snapshot(
        self,
        profile_id: str,
        base_weights: Mapping[str, Any],
        memory: PreferenceMemory,
        playback: PlaybackSnapshot,
    ) -> PolicySnapshot:
        """纯函数式生成一次确定性策略快照，不执行持久化。"""
        target = str(profile_id or "").strip()
        if not target or memory.profile_id != target or playback.profile_id != target:
            raise ValueError("policy inputs must belong to the same profile")
        base = self._base_weights(base_weights)
        signals = [
            *self._memory_signals(memory),
            *self._playback_signals(playback),
        ]
        deltas, certainties, evidence = self._aggregate_signals(signals)
        playback_fingerprint = self._playback_fingerprint(playback)
        effective = {
            name: self._clamp(
                base[name] + deltas[name] * certainties[name], 0.0, 1.0
            )
            for name in POLICY_WEIGHT_NAMES
        }
        calibration = self._calibration()
        return PolicySnapshot(
            profile_id=target,
            policy_version=PolicySnapshot.compute_policy_version(
                profile_id=target,
                memory_revision=memory.memory_revision,
                playback_fingerprint=playback_fingerprint,
                base_weights=base,
                learned_deltas=deltas,
                evidence_certainty=certainties,
                effective_weights=effective,
                evidence_refs=evidence,
                calibration=calibration,
                algorithm_version=POLICY_ALGORITHM_VERSION,
            ),
            memory_revision=memory.memory_revision,
            playback_fingerprint=playback_fingerprint,
            base_weights=base,
            learned_deltas=deltas,
            evidence_certainty=certainties,
            effective_weights=effective,
            evidence_refs=evidence,
            calibration=calibration,
            generated_at=self._now_factory().astimezone(timezone.utc).isoformat(),
            algorithm_version=POLICY_ALGORITHM_VERSION,
        )

    def refresh(
        self,
        profile_id: str,
        base_weights: Mapping[str, Any],
        playback: PlaybackSnapshot,
    ) -> PolicySnapshot:
        """在记忆 revision 竞争下重算并原子保存最新策略快照。"""
        target = str(profile_id or "").strip()
        for _attempt in range(self._max_revision_retries):
            memory = self.repository.load_preference_memory(target)
            snapshot = self.build_snapshot(target, base_weights, memory, playback)
            stored = self.repository.save_policy_snapshot(
                snapshot, expected_memory_revision=memory.memory_revision
            )
            if stored is not None:
                return stored
        raise RuntimeError("preference memory changed during policy refresh")
