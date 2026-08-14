"""推荐运行历史领域对象。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping


ADAPTIVE_FINGERPRINT_SCHEMA_VERSION = 1
LEARNING_HEALTH_SCHEMA_VERSION = 1


@dataclass
class RecommendationRun:
    """表示一次按稳定 Emby 画像身份隔离的榜单生成运行。"""

    profile_id: str
    run_id: str
    username: str = ""
    status: str = "idle"
    started_at: str = ""
    finished_at: str = ""
    message: str = ""
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = 2

    def __post_init__(self) -> None:
        """规范化运行归属并拒绝空 profile_id。"""
        self.profile_id = str(self.profile_id or "").strip()
        self.username = str(self.username or "").strip()
        if not self.profile_id:
            raise ValueError("run profile_id is required")

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RecommendationRun":
        """从持久化字典恢复运行记录。"""
        if not isinstance(value, Mapping):
            raise ValueError("run must be a mapping")
        profile_id = str(value.get("profile_id") or "").strip()
        run_id = str(value.get("run_id") or "").strip()
        if not profile_id or not run_id:
            raise ValueError("run profile_id and run_id are required")
        return cls(
            profile_id=profile_id,
            run_id=run_id,
            username=str(value.get("username") or "").strip(),
            status=str(value.get("status") or "idle"),
            started_at=str(value.get("started_at") or ""),
            finished_at=str(value.get("finished_at") or ""),
            message=str(value.get("message") or ""),
            errors=[str(item) for item in value.get("errors") or []],
            metrics=dict(value.get("metrics") or {}),
            schema_version=int(value.get("schema_version") or 2),
        )


@dataclass(frozen=True)
class AdaptiveFingerprints:
    """保存来源、偏好和榜单消费三类生成门控指纹。"""

    profile_id: str
    source_fingerprint: str = ""
    preference_fingerprint: str = ""
    consumption_fingerprint: str = ""
    generated_at: str = ""
    schema_version: int = ADAPTIVE_FINGERPRINT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范指纹文本并保留 legacy 缺失状态。"""
        object.__setattr__(self, "profile_id", str(self.profile_id or "").strip())
        for field_name in (
            "source_fingerprint",
            "preference_fingerprint",
            "consumption_fingerprint",
            "generated_at",
        ):
            object.__setattr__(self, field_name, str(getattr(self, field_name) or "").strip()[:128])
        object.__setattr__(self, "schema_version", int(self.schema_version or 0))
        if not self.profile_id:
            raise ValueError("adaptive fingerprints profile_id is required")
        if self.schema_version != ADAPTIVE_FINGERPRINT_SCHEMA_VERSION:
            raise ValueError("adaptive fingerprints schema is unsupported")

    @property
    def complete(self) -> bool:
        """返回三类输入是否都已有可比较指纹。"""
        return all((self.source_fingerprint, self.preference_fingerprint, self.consumption_fingerprint))

    def to_dict(self) -> Dict[str, Any]:
        """返回持久化字典，并提供计划中的短字段别名。"""
        return {
            "profile_id": self.profile_id,
            "source_fingerprint": self.source_fingerprint,
            "preference_fingerprint": self.preference_fingerprint,
            "consumption_fingerprint": self.consumption_fingerprint,
            "source": self.source_fingerprint,
            "preference": self.preference_fingerprint,
            "consumption": self.consumption_fingerprint,
            "generated_at": self.generated_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AdaptiveFingerprints":
        """从新旧键名恢复生成门控指纹。"""
        if not isinstance(value, Mapping):
            raise ValueError("adaptive fingerprints must be a mapping")
        return cls(
            profile_id=value.get("profile_id"),
            source_fingerprint=value.get("source_fingerprint") or value.get("source") or "",
            preference_fingerprint=value.get("preference_fingerprint") or value.get("preference") or "",
            consumption_fingerprint=value.get("consumption_fingerprint") or value.get("consumption") or "",
            generated_at=value.get("generated_at") or "",
            schema_version=value.get("schema_version") or ADAPTIVE_FINGERPRINT_SCHEMA_VERSION,
        )


@dataclass(frozen=True)
class LearningHealth:
    """向页面投影近期学习量、确认量和归因覆盖，不把数量少判成故障。"""

    profile_id: str
    short_term_signal_count: int = 0
    confirmed_memory_count: int = 0
    pending_count: int = 0
    processed_count: int = 0
    exposure_count: int = 0
    effective_feedback_count: int = 0
    last_effective_feedback_at: str = ""
    attribution_stage_counts: Dict[str, int] = field(default_factory=dict)
    attribution_coverage: str = "none"
    attention_required: bool = False
    attention_reason: str = ""
    legacy_baseline: bool = False
    schema_version: int = LEARNING_HEALTH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范健康度计数和归因阶段。"""
        object.__setattr__(self, "profile_id", str(self.profile_id or "").strip())
        for field_name in (
            "short_term_signal_count",
            "confirmed_memory_count",
            "pending_count",
            "processed_count",
            "exposure_count",
            "effective_feedback_count",
        ):
            object.__setattr__(self, field_name, max(0, int(getattr(self, field_name) or 0)))
        object.__setattr__(self, "last_effective_feedback_at", str(self.last_effective_feedback_at or "").strip())
        object.__setattr__(
            self,
            "attribution_stage_counts",
            {
                str(key): max(0, int(value or 0))
                for key, value in dict(self.attribution_stage_counts or {}).items()
                if str(key).strip()
            },
        )
        object.__setattr__(self, "attribution_coverage", str(self.attribution_coverage or "none").strip()[:32])
        object.__setattr__(self, "attention_required", bool(self.attention_required))
        object.__setattr__(self, "attention_reason", str(self.attention_reason or "").strip()[:160])
        object.__setattr__(self, "legacy_baseline", bool(self.legacy_baseline))
        object.__setattr__(self, "schema_version", int(self.schema_version or 0))
        if not self.profile_id:
            raise ValueError("learning health profile_id is required")
        if self.schema_version != LEARNING_HEALTH_SCHEMA_VERSION:
            raise ValueError("learning health schema is unsupported")

    def to_dict(self) -> Dict[str, Any]:
        """返回前端可读且不包含原始内容的学习健康摘要。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LearningHealth":
        """从持久化摘要恢复学习健康度。"""
        if not isinstance(value, Mapping):
            raise ValueError("learning health must be a mapping")
        return cls(
            profile_id=value.get("profile_id"),
            short_term_signal_count=value.get("short_term_signal_count") or 0,
            confirmed_memory_count=value.get("confirmed_memory_count") or 0,
            pending_count=value.get("pending_count") or 0,
            processed_count=value.get("processed_count") or 0,
            exposure_count=value.get("exposure_count") or 0,
            effective_feedback_count=value.get("effective_feedback_count") or 0,
            last_effective_feedback_at=value.get("last_effective_feedback_at") or "",
            attribution_stage_counts=value.get("attribution_stage_counts") or {},
            attribution_coverage=value.get("attribution_coverage") or "none",
            attention_required=bool(value.get("attention_required", False)),
            attention_reason=value.get("attention_reason") or "",
            legacy_baseline=bool(value.get("legacy_baseline", False)),
            schema_version=value.get("schema_version") or LEARNING_HEALTH_SCHEMA_VERSION,
        )
