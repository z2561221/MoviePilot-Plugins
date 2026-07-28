"""AgentRank 版本化确定性策略快照模型。"""

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Dict, Iterable, Mapping, Tuple


POLICY_SNAPSHOT_SCHEMA_VERSION = 1
POLICY_WEIGHT_NAMES = (
    "type_weight",
    "theme_weight",
    "actor_weight",
    "director_weight",
    "region_weight",
    "year_weight",
    "rating_weight",
    "heat_weight",
    "freshness_weight",
    "similarity_weight",
)
POLICY_DELTA_LIMIT = 0.25
POLICY_CALIBRATION_NAMES = frozenset(
    {
        "delta_limit",
        "memory_delta_scale",
        "playback_delta_scale",
        "abandonment_delta_scale",
        "minimum_independent_playback",
        "delta_semantics",
        "effective_formula",
    }
)


def _text(value: Any) -> str:
    """把可选标量规范为去除首尾空白的文本。"""
    return str(value or "").strip()


def _weight_mapping(
    value: Mapping[str, Any],
    *,
    field_name: str,
    minimum: float,
    maximum: float,
) -> Dict[str, float]:
    """读取恰好十项且全部有限的策略数值映射。"""
    if not isinstance(value, Mapping) or set(value) != set(POLICY_WEIGHT_NAMES):
        raise ValueError(f"{field_name} must contain the exact ten policy weights")
    result: Dict[str, float] = {}
    for name in POLICY_WEIGHT_NAMES:
        if isinstance(value[name], bool):
            raise ValueError(f"{field_name}.{name} is out of range")
        number = float(value[name])
        if not math.isfinite(number) or not minimum <= number <= maximum:
            raise ValueError(f"{field_name}.{name} is out of range")
        result[name] = round(number, 6)
    return result


def _evidence_mapping(value: Mapping[str, Iterable[Any]]) -> Dict[str, Tuple[str, ...]]:
    """读取十项权重对应的去重证据引用。"""
    if not isinstance(value, Mapping) or set(value) != set(POLICY_WEIGHT_NAMES):
        raise ValueError("evidence_refs must contain the exact ten policy weights")
    result: Dict[str, Tuple[str, ...]] = {}
    for name in POLICY_WEIGHT_NAMES:
        raw_refs = value[name]
        if raw_refs is None:
            raw_refs = ()
        if isinstance(raw_refs, (str, bytes, Mapping)):
            raise ValueError(f"evidence_refs.{name} must be a sequence")
        refs = []
        try:
            iterator = iter(raw_refs)
        except TypeError as error:
            raise ValueError(
                f"evidence_refs.{name} must be a sequence"
            ) from error
        for raw in iterator:
            ref = _text(raw)
            if ref and ref not in refs:
                refs.append(ref)
        result[name] = tuple(refs)
    return result


@dataclass(frozen=True)
class PolicySnapshot:
    """保存可重放的十项基准、学习增量和最终有效权重。"""

    profile_id: str
    policy_version: str
    memory_revision: int
    playback_fingerprint: str
    base_weights: Mapping[str, float]
    learned_deltas: Mapping[str, float]
    evidence_certainty: Mapping[str, float]
    effective_weights: Mapping[str, float]
    evidence_refs: Mapping[str, Tuple[str, ...]]
    calibration: Mapping[str, Any]
    generated_at: str
    algorithm_version: int = 1
    schema_version: int = POLICY_SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范化快照并验证有效权重可由保存字段精确重算。"""
        object.__setattr__(self, "profile_id", _text(self.profile_id))
        object.__setattr__(self, "policy_version", _text(self.policy_version))
        object.__setattr__(
            self, "playback_fingerprint", _text(self.playback_fingerprint)
        )
        object.__setattr__(self, "generated_at", _text(self.generated_at))
        object.__setattr__(self, "memory_revision", int(self.memory_revision))
        object.__setattr__(self, "algorithm_version", int(self.algorithm_version))
        object.__setattr__(self, "schema_version", int(self.schema_version))
        object.__setattr__(
            self,
            "base_weights",
            _weight_mapping(
                self.base_weights,
                field_name="base_weights",
                minimum=0.0,
                maximum=1.0,
            ),
        )
        object.__setattr__(
            self,
            "learned_deltas",
            _weight_mapping(
                self.learned_deltas,
                field_name="learned_deltas",
                minimum=-POLICY_DELTA_LIMIT,
                maximum=POLICY_DELTA_LIMIT,
            ),
        )
        object.__setattr__(
            self,
            "evidence_certainty",
            _weight_mapping(
                self.evidence_certainty,
                field_name="evidence_certainty",
                minimum=0.0,
                maximum=1.0,
            ),
        )
        object.__setattr__(
            self,
            "effective_weights",
            _weight_mapping(
                self.effective_weights,
                field_name="effective_weights",
                minimum=0.0,
                maximum=1.0,
            ),
        )
        object.__setattr__(self, "evidence_refs", _evidence_mapping(self.evidence_refs))
        calibration = dict(self.calibration or {})
        if set(calibration) != POLICY_CALIBRATION_NAMES or any(
            not isinstance(value, (str, int, float)) or isinstance(value, bool)
            for value in calibration.values()
        ):
            raise ValueError("policy snapshot calibration is invalid")
        if any(
            isinstance(value, (int, float)) and not math.isfinite(float(value))
            for value in calibration.values()
        ):
            raise ValueError("policy snapshot calibration is invalid")
        object.__setattr__(self, "calibration", MappingProxyType(calibration))
        for field_name in (
            "base_weights",
            "learned_deltas",
            "evidence_certainty",
            "effective_weights",
            "evidence_refs",
        ):
            object.__setattr__(
                self, field_name, MappingProxyType(dict(getattr(self, field_name)))
            )
        if not self.profile_id or not self.policy_version:
            raise ValueError("policy snapshot identity is incomplete")
        if self.memory_revision < 0 or self.algorithm_version <= 0:
            raise ValueError("policy snapshot revision is invalid")
        if not self.playback_fingerprint or not self.generated_at:
            raise ValueError("policy snapshot provenance is incomplete")
        try:
            datetime.fromisoformat(self.generated_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("policy snapshot generated_at is invalid") from error
        if self.schema_version != POLICY_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("policy snapshot schema_version is unsupported")
        for name in POLICY_WEIGHT_NAMES:
            expected = round(
                min(
                    1.0,
                    max(
                        0.0,
                        self.base_weights[name]
                        + self.learned_deltas[name]
                        * self.evidence_certainty[name],
                    ),
                ),
                6,
            )
            if abs(expected - self.effective_weights[name]) > 0.000001:
                raise ValueError(f"effective_weights.{name} is not reproducible")
        expected_version = self.compute_policy_version(
            profile_id=self.profile_id,
            memory_revision=self.memory_revision,
            playback_fingerprint=self.playback_fingerprint,
            base_weights=self.base_weights,
            learned_deltas=self.learned_deltas,
            evidence_certainty=self.evidence_certainty,
            effective_weights=self.effective_weights,
            evidence_refs=self.evidence_refs,
            calibration=self.calibration,
            algorithm_version=self.algorithm_version,
        )
        if self.policy_version != expected_version:
            raise ValueError("policy snapshot version does not match its content")

    @classmethod
    def compute_policy_version(
        cls,
        *,
        profile_id: str,
        memory_revision: int,
        playback_fingerprint: str,
        base_weights: Mapping[str, float],
        learned_deltas: Mapping[str, float],
        evidence_certainty: Mapping[str, float],
        effective_weights: Mapping[str, float],
        evidence_refs: Mapping[str, Iterable[str]],
        calibration: Mapping[str, Any],
        algorithm_version: int,
    ) -> str:
        """根据不含生成时间的规范内容计算不可伪造的策略版本。"""
        payload = {
            "profile_id": _text(profile_id),
            "memory_revision": int(memory_revision),
            "playback_fingerprint": _text(playback_fingerprint),
            "base_weights": dict(base_weights),
            "learned_deltas": dict(learned_deltas),
            "evidence_certainty": dict(evidence_certainty),
            "effective_weights": dict(effective_weights),
            "evidence_refs": {
                name: list(evidence_refs[name]) for name in POLICY_WEIGHT_NAMES
            },
            "calibration": dict(calibration),
            "algorithm_version": int(algorithm_version),
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"policy-v{int(algorithm_version)}-{hashlib.sha256(encoded).hexdigest()[:20]}"

    @property
    def evidence_count(self) -> int:
        """返回十项策略引用的唯一可信证据数量。"""
        return len(
            {
                ref
                for refs in self.evidence_refs.values()
                for ref in refs
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化且不含原始反馈文本的策略快照。"""
        return {
            "profile_id": self.profile_id,
            "policy_version": self.policy_version,
            "memory_revision": self.memory_revision,
            "playback_fingerprint": self.playback_fingerprint,
            "base_weights": dict(self.base_weights),
            "learned_deltas": dict(self.learned_deltas),
            "evidence_certainty": dict(self.evidence_certainty),
            "effective_weights": dict(self.effective_weights),
            "evidence_refs": {
                name: list(self.evidence_refs[name]) for name in POLICY_WEIGHT_NAMES
            },
            "calibration": dict(self.calibration),
            "generated_at": self.generated_at,
            "algorithm_version": self.algorithm_version,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PolicySnapshot":
        """从持久化字典恢复并严格校验策略快照。"""
        if not isinstance(value, Mapping):
            raise ValueError("policy snapshot must be a mapping")
        return cls(
            profile_id=value.get("profile_id"),
            policy_version=value.get("policy_version"),
            memory_revision=value.get("memory_revision") or 0,
            playback_fingerprint=value.get("playback_fingerprint"),
            base_weights=value.get("base_weights") or {},
            learned_deltas=value.get("learned_deltas") or {},
            evidence_certainty=value.get("evidence_certainty") or {},
            effective_weights=value.get("effective_weights") or {},
            evidence_refs=value.get("evidence_refs") or {},
            calibration=value.get("calibration") or {},
            generated_at=value.get("generated_at"),
            algorithm_version=value.get("algorithm_version") or 0,
            schema_version=value.get("schema_version") or 0,
        )
