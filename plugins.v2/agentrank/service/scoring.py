"""AgentRank 版本化策略学习与后续确定性评分入口。"""

import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ..model.board import RecommendationItem
from ..model.config import WEIGHT_DEFAULTS
from ..model.memory import PreferenceMemory
from ..model.playback import PlaybackSample, PlaybackSnapshot
from ..model.profile_preferences import ProfilePreferences
from ..model.policy import (
    POLICY_DELTA_LIMIT,
    POLICY_WEIGHT_NAMES,
    PolicySnapshot,
)
from ..model.support import (
    SUPPORT_UNIT_SCALE,
    SupportContribution,
    SupportScore,
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

_DIMENSION_ALIASES = {
    name: name for name in POLICY_WEIGHT_NAMES
}
_DIMENSION_ALIASES.update(
    {name.removesuffix("_weight"): name for name in POLICY_WEIGHT_NAMES}
)
_TYPE_ALIASES = {
    "movie": "movie",
    "电影": "movie",
    "tv": "tv",
    "电视剧": "tv",
    "剧集": "tv",
    "电视": "tv",
    "anime": "anime",
    "动画": "anime",
    "动漫": "anime",
    "番剧": "anime",
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
    def playback_fingerprint(cls, playback: PlaybackSnapshot) -> str:
        """公开返回策略快照使用的规范化播放事实指纹。"""
        return cls._playback_fingerprint(playback)

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


@dataclass(frozen=True)
class _TrustedPreferenceSignal:
    """表示可由确认记忆、人工设置或独立播放重建的偏好信号。"""

    dimension: str
    value: str
    polarity: str
    certainty: float
    refs: Tuple[str, ...]


@dataclass(frozen=True)
class _CandidateFact:
    """表示候选结构化字段中的一项受信作品事实。"""

    dimension: str
    value: str
    ref: str


@dataclass(frozen=True)
class SupportScoringResult:
    """返回确定性支持度及未被受信数据支撑的声明位置。"""

    score: SupportScore
    verified_positive_count: int
    verified_counter_count: int
    unsupported_claims: Tuple[str, ...]


class DeterministicSupportScorer:
    """用受信候选、确认偏好与独立播放证据重算支持度。"""

    @staticmethod
    def _normalize(value: Any) -> str:
        """移除文本分隔符并统一大小写，供证据等值比较。"""
        return re.sub(r"[\W_]+", "", str(value or "").casefold(), flags=re.UNICODE)

    @classmethod
    def _normalized_type(cls, value: Any) -> str:
        """把电影、剧集和动画常用别名收敛为稳定类型。"""
        normalized = cls._normalize(value)
        return _TYPE_ALIASES.get(normalized, normalized)

    @classmethod
    def _value_matches(cls, expected: Any, actual: Any) -> bool:
        """判断声明值能否回溯到受信原值。"""
        left = cls._normalize(expected)
        right = cls._normalize(actual)
        return bool(left and right and (left in right or right in left))

    @classmethod
    def _values_compatible(
        cls,
        dimension: str,
        user_value: Any,
        candidate_value: Any,
    ) -> bool:
        """按维度判断用户证据与候选事实是否表达同一可核对特征。"""
        if dimension == "type_weight":
            return cls._normalized_type(user_value) == cls._normalized_type(
                candidate_value
            )
        if dimension == "year_weight":
            user_text = str(user_value or "")
            candidate_years = [
                int(item)
                for item in re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", str(candidate_value or ""))
            ]
            explicit_years = [
                int(item)
                for item in re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", user_text)
            ]
            if explicit_years and candidate_years:
                return bool(set(explicit_years) & set(candidate_years))
            decade = re.search(r"(?<!\d)((?:19|20)?\d0)年代", user_text)
            if decade and candidate_years:
                raw = int(decade.group(1))
                start = raw if raw >= 1900 else 2000 + raw if raw < 30 else 1900 + raw
                return any(start <= year <= start + 9 for year in candidate_years)
        if dimension == "rating_weight":
            numbers = re.findall(r"\d+(?:\.\d+)?", str(candidate_value or ""))
            if numbers and any(term in str(user_value or "") for term in ("高分", "高质量", "评分")):
                return float(numbers[0]) >= 7.0
        return cls._value_matches(user_value, candidate_value)

    @staticmethod
    def _fact_ref(candidate_id: str, field_name: str, index: int) -> str:
        """生成不包含作品文案的稳定候选事实引用。"""
        return f"candidate:{candidate_id}:{field_name}:{int(index)}"

    @classmethod
    def _candidate_facts(cls, candidate: Any) -> Tuple[_CandidateFact, ...]:
        """把候选允许参与评分的结构化字段投影为稳定事实。"""
        candidate_id = str(getattr(candidate, "candidate_id", "") or "").strip()
        if not candidate_id:
            raise ValueError("candidate_id is required for deterministic support")
        facts: List[_CandidateFact] = []

        def add(dimension: str, field_name: str, values: Iterable[Any]) -> None:
            """向候选事实集合加入去空值后的稳定字段。"""
            for index, raw in enumerate(values or ()):
                value = str(raw or "").strip()
                if value:
                    facts.append(
                        _CandidateFact(
                            dimension,
                            value,
                            cls._fact_ref(candidate_id, field_name, index),
                        )
                    )

        add("type_weight", "media_type", [getattr(candidate, "media_type", "")])
        add("theme_weight", "genres", getattr(candidate, "genres", ()) or ())
        add("actor_weight", "actors", getattr(candidate, "actors", ()) or ())
        add(
            "director_weight",
            "directors",
            getattr(candidate, "directors", ()) or (),
        )
        add("region_weight", "regions", getattr(candidate, "regions", ()) or ())
        year = getattr(candidate, "year", None)
        if year not in (None, ""):
            add("year_weight", "year", [year])
            add("freshness_weight", "year", [year])
        rating = getattr(candidate, "rating", None)
        if rating not in (None, "") and math.isfinite(float(rating)):
            add("rating_weight", "rating", [f"{float(rating):g}"])
        popularity = getattr(candidate, "popularity", None)
        if popularity not in (None, "") and math.isfinite(float(popularity)):
            add("heat_weight", "popularity", [f"{float(popularity):g}"])
        release_date = str(getattr(candidate, "release_date", "") or "").strip()
        if release_date:
            add("freshness_weight", "release_date", [release_date])
        add(
            "similarity_weight",
            "similarity",
            [
                *(getattr(candidate, "genres", ()) or ()),
                getattr(candidate, "overview", ""),
            ],
        )
        return tuple(
            sorted(
                {fact.ref: fact for fact in facts}.values(),
                key=lambda fact: (fact.dimension, fact.ref, fact.value.casefold()),
            )
        )

    @staticmethod
    def _manual_ref(polarity: str, value: str) -> str:
        """为人工偏好生成不暴露原文的内容寻址引用。"""
        digest = hashlib.sha256(
            f"{polarity}:{str(value or '').strip().casefold()}".encode("utf-8")
        ).hexdigest()[:20]
        return f"profile_preference:{polarity}:{digest}"

    @classmethod
    def _memory_signals(
        cls,
        memory: PreferenceMemory,
    ) -> List[_TrustedPreferenceSignal]:
        """把当前确认记忆转换为带方向、强度与谱系引用的可信信号。"""
        signals: List[_TrustedPreferenceSignal] = []
        for item in memory.active_items():
            for dimension in PolicyLearningService._memory_weight_names(item.category):
                certainty = PolicyLearningService._clamp(
                    item.strength * item.certainty,
                    0.0,
                    1.0,
                )
                if certainty <= 0:
                    continue
                signals.append(
                    _TrustedPreferenceSignal(
                        dimension=dimension,
                        value=item.value,
                        polarity=item.polarity,
                        certainty=certainty,
                        refs=(f"memory:{item.item_id}",),
                    )
                )
        return signals

    @classmethod
    def _manual_signals(
        cls,
        preferences: ProfilePreferences,
    ) -> List[_TrustedPreferenceSignal]:
        """把未归档的人工正负标签转换为跨维度候选信号。"""
        signals: List[_TrustedPreferenceSignal] = []
        for polarity, values in (
            ("positive", preferences.custom_tags),
            ("negative", preferences.custom_negative_tags),
        ):
            for value in values:
                signals.append(
                    _TrustedPreferenceSignal(
                        dimension="",
                        value=value,
                        polarity=polarity,
                        certainty=1.0,
                        refs=(cls._manual_ref(polarity, value),),
                    )
                )
        return signals

    @classmethod
    def _playback_signals(
        cls,
        playback: PlaybackSnapshot,
    ) -> List[_TrustedPreferenceSignal]:
        """只从至少两部独立作品构造类型和题材播放信号。"""
        groups: Dict[Tuple[str, str, str], set] = defaultdict(set)
        for sample in PolicyLearningService._canonical_playback_samples(
            playback.samples
        ):
            if not sample["observed"] and not sample["abandoned"]:
                continue
            polarity = "negative" if sample["abandoned"] else "positive"
            for media_type in sample["media_types"]:
                groups[("type_weight", media_type, polarity)].add(
                    sample["stable_id"]
                )
            for genre in sample["genres"]:
                groups[("theme_weight", genre, polarity)].add(sample["stable_id"])
        signals: List[_TrustedPreferenceSignal] = []
        for (dimension, value, polarity), stable_ids in sorted(groups.items()):
            count = len(stable_ids)
            if count < MIN_INDEPENDENT_PLAYBACK_EVIDENCE:
                continue
            certainty = (
                min(0.35, 0.20 + 0.05 * (count - 2))
                if polarity == "negative"
                else min(1.0, 0.60 + 0.10 * (count - 2))
            )
            prefix = "abandoned" if polarity == "negative" else "observed"
            signals.append(
                _TrustedPreferenceSignal(
                    dimension=dimension,
                    value=value,
                    polarity=polarity,
                    certainty=certainty,
                    refs=tuple(
                        f"playback:{prefix}:{stable_id}"
                        for stable_id in sorted(stable_ids)
                    ),
                )
            )
        return signals

    @classmethod
    def trusted_signal_catalog(
        cls,
        memory: PreferenceMemory,
        preferences: ProfilePreferences,
        playback: PlaybackSnapshot,
    ) -> List[Dict[str, Any]]:
        """返回与确定性校验器同源的最小证据目录。"""
        signals = [
            *cls._memory_signals(memory),
            *cls._manual_signals(preferences),
            *cls._playback_signals(playback),
        ]
        catalog: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for signal in signals:
            dimension = signal.dimension.removesuffix("_weight") or "any"
            key = (dimension, signal.value.casefold(), signal.polarity)
            current = catalog.get(key)
            item = {
                "dimension": dimension,
                "value": signal.value,
                "polarity": signal.polarity,
                "certainty": signal.certainty,
                "evidence_count": len(signal.refs),
            }
            if current is None or (
                item["certainty"],
                item["evidence_count"],
                item["value"].casefold(),
            ) > (
                current["certainty"],
                current["evidence_count"],
                current["value"].casefold(),
            ):
                catalog[key] = item
        return [catalog[key] for key in sorted(catalog)]

    @staticmethod
    def _claim_field(claim: Any, field_name: str) -> str:
        """从冻结对象或映射读取结构化证据声明字段。"""
        raw = (
            claim.get(field_name)
            if isinstance(claim, Mapping)
            else getattr(claim, field_name, "")
        )
        return str(raw or "").strip()

    @classmethod
    def _claim_dimension(cls, claim: Any) -> str:
        """把公开维度名收敛为十项策略权重名。"""
        return _DIMENSION_ALIASES.get(
            cls._claim_field(claim, "dimension").casefold(),
            "",
        )

    @staticmethod
    def _units(value: float) -> int:
        """把零到一数值转换为可重放整数单位。"""
        return max(
            0,
            min(
                SUPPORT_UNIT_SCALE,
                int(float(value) * SUPPORT_UNIT_SCALE + 0.5),
            ),
        )

    @classmethod
    def _contribution(
        cls,
        policy: PolicySnapshot,
        direction: str,
        dimension: str,
        signal: _TrustedPreferenceSignal,
        fact: _CandidateFact,
    ) -> Optional[SupportContribution]:
        """根据已验证信号和候选事实生成整数贡献。"""
        weight_units = cls._units(policy.effective_weights[dimension])
        certainty_units = cls._units(signal.certainty)
        contribution_units = (
            weight_units * certainty_units + SUPPORT_UNIT_SCALE // 2
        ) // SUPPORT_UNIT_SCALE
        if contribution_units <= 0:
            return None
        return SupportContribution(
            dimension=dimension,
            direction=direction,
            user_value=signal.value,
            candidate_value=fact.value,
            user_refs=signal.refs,
            candidate_ref=fact.ref,
            weight_units=weight_units,
            certainty_units=certainty_units,
            contribution_units=contribution_units,
        )

    @classmethod
    def _resolve_claim(
        cls,
        claim: Any,
        direction: str,
        signals: Sequence[_TrustedPreferenceSignal],
        facts: Sequence[_CandidateFact],
        policy: PolicySnapshot,
    ) -> Optional[SupportContribution]:
        """把一项 Agent 声明约束到真实用户信号与候选事实。"""
        dimension = cls._claim_dimension(claim)
        user_value = cls._claim_field(claim, "user_value")
        candidate_value = cls._claim_field(claim, "candidate_value")
        if not dimension or not user_value or not candidate_value:
            return None
        expected_polarity = "positive" if direction == "positive" else "negative"
        matched_signals = [
            signal
            for signal in signals
            if signal.polarity == expected_polarity
            and signal.dimension in {"", dimension}
            and cls._value_matches(user_value, signal.value)
        ]
        matched_facts = [
            fact
            for fact in facts
            if fact.dimension == dimension
            and cls._value_matches(candidate_value, fact.value)
        ]
        pairs = [
            (signal, fact)
            for signal in matched_signals
            for fact in matched_facts
            if cls._values_compatible(dimension, signal.value, fact.value)
        ]
        if not pairs:
            return None
        signal, fact = sorted(
            pairs,
            key=lambda pair: (
                -pair[0].certainty,
                pair[0].refs,
                pair[1].ref,
                pair[0].value.casefold(),
            ),
        )[0]
        return cls._contribution(policy, direction, dimension, signal, fact)

    @classmethod
    def _automatic_contributions(
        cls,
        signals: Sequence[_TrustedPreferenceSignal],
        facts: Sequence[_CandidateFact],
        policy: PolicySnapshot,
        *,
        polarity: str,
        direction: str,
    ) -> List[SupportContribution]:
        """按用户信号和候选事实自动生成每个维度的可验证贡献。"""
        result = []
        for signal in signals:
            if signal.polarity != polarity:
                continue
            dimensions = sorted(
                {
                    fact.dimension
                    for fact in facts
                    if not signal.dimension or signal.dimension == fact.dimension
                }
            )
            for dimension in dimensions:
                matched_facts = [
                    fact
                    for fact in facts
                    if fact.dimension == dimension
                    and cls._values_compatible(
                        dimension,
                        signal.value,
                        fact.value,
                    )
                ]
                if not matched_facts:
                    continue
                fact = sorted(
                    matched_facts,
                    key=lambda item: (item.ref, item.value.casefold()),
                )[0]
                contribution = cls._contribution(
                    policy,
                    direction,
                    dimension,
                    signal,
                    fact,
                )
                if contribution is not None:
                    result.append(contribution)
        return result

    @staticmethod
    def _strongest_per_dimension(
        contributions: Iterable[SupportContribution],
    ) -> List[SupportContribution]:
        """每个方向和权重维度只保留最强且确定性破局的贡献。"""
        selected: Dict[Tuple[str, str], SupportContribution] = {}
        for item in contributions or ():
            key = (item.direction, item.dimension)
            current = selected.get(key)
            if current is None or (
                item.contribution_units,
                item.certainty_units,
                tuple(item.user_refs),
                item.candidate_ref,
                item.user_value.casefold(),
                item.candidate_value.casefold(),
            ) > (
                current.contribution_units,
                current.certainty_units,
                tuple(current.user_refs),
                current.candidate_ref,
                current.user_value.casefold(),
                current.candidate_value.casefold(),
            ):
                selected[key] = item
        return [selected[key] for key in sorted(selected)]

    def score_candidate(
        self,
        candidate: Any,
        policy: PolicySnapshot,
        positive_claims: Sequence[Any],
        counter_claims: Sequence[Any],
        memory: PreferenceMemory,
        preferences: ProfilePreferences,
        playback: PlaybackSnapshot,
    ) -> SupportScoringResult:
        """验证 Agent 证据声明并返回零误差可重算的候选支持度。"""
        if not isinstance(policy, PolicySnapshot):
            raise TypeError("policy must be PolicySnapshot")
        if not isinstance(memory, PreferenceMemory):
            raise TypeError("memory must be PreferenceMemory")
        if not isinstance(preferences, ProfilePreferences):
            raise TypeError("preferences must be ProfilePreferences")
        if not isinstance(playback, PlaybackSnapshot):
            raise TypeError("playback must be PlaybackSnapshot")
        profile_ids = {
            policy.profile_id,
            memory.profile_id,
            preferences.profile_id,
            playback.profile_id,
        }
        if len(profile_ids) != 1 or policy.memory_revision != memory.memory_revision:
            raise RuntimeError("support inputs do not share one current policy revision")
        facts = self._candidate_facts(candidate)
        signals = [
            *self._memory_signals(memory),
            *self._manual_signals(preferences),
            *self._playback_signals(playback),
        ]
        claimed_contributions: Dict[str, List[SupportContribution]] = {
            "positive": [],
            "counter": [],
        }
        unsupported: List[str] = []
        for direction, claims in (
            ("positive", positive_claims),
            ("counter", counter_claims),
        ):
            for index, claim in enumerate(claims or ()):
                contribution = self._resolve_claim(
                    claim,
                    direction,
                    signals,
                    facts,
                    policy,
                )
                if contribution is None:
                    unsupported.append(
                        f"{direction}:{index}:{self._claim_dimension(claim) or 'invalid'}"
                    )
                    continue
                claimed_contributions[direction].append(contribution)
        contributions = [
            *claimed_contributions["positive"],
            *claimed_contributions["counter"],
            *self._automatic_contributions(
                signals,
                facts,
                policy,
                polarity="positive",
                direction="positive",
            ),
            *self._automatic_contributions(
                signals,
                facts,
                policy,
                polarity="negative",
                direction="counter",
            ),
        ]
        contributions = self._strongest_per_dimension(contributions)
        verified_positive_claims = {
            item.identity for item in claimed_contributions["positive"]
        }
        score = SupportScore.from_contributions(
            policy.policy_version,
            contributions,
        )
        return SupportScoringResult(
            score=score,
            verified_positive_count=len(verified_positive_claims),
            verified_counter_count=sum(
                item.direction == "counter" for item in score.contributions
            ),
            unsupported_claims=tuple(unsupported),
        )


class StableRecommendationRanker:
    """按确定性净分和固定破同分规则生成最终榜单顺序。"""

    @staticmethod
    def rank(
        items: Sequence[RecommendationItem],
        candidates: Sequence[Any],
        agent_order: Mapping[str, int] = None,
    ) -> List[RecommendationItem]:
        """依次使用净分、Agent 顺序、冻结顺序和身份稳定排序。"""
        values = list(items or ())
        if not values:
            return []
        if any(item.support is None for item in values):
            raise RuntimeError("deterministic ranking requires support for every item")
        policy_versions = {item.support.policy_version for item in values}
        if len(policy_versions) != 1:
            raise RuntimeError("deterministic ranking requires one policy version")
        candidate_order = {
            str(getattr(candidate, "candidate_id", "") or ""): index
            for index, candidate in enumerate(candidates or ())
        }
        trusted_agent_order = {
            str(candidate_id): int(index)
            for candidate_id, index in dict(agent_order or {}).items()
        }
        missing_agent_order = len(trusted_agent_order) + len(values) + 1
        missing_candidate_order = len(candidate_order) + len(values) + 1
        ranked = sorted(
            values,
            key=lambda item: (
                -item.support.net_units,
                trusted_agent_order.get(item.candidate_id, missing_agent_order),
                candidate_order.get(item.candidate_id, missing_candidate_order),
                item.candidate_id,
            ),
        )
        for index, item in enumerate(ranked, start=1):
            item.rank = index
        return ranked
