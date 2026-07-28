"""推荐结果归因的单调状态与安全证据模型。"""

from dataclasses import MISSING, asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Any, Dict, Mapping


OUTCOME_STATES = (
    "native_drawer_opened",
    "subscription_observed",
    "library_observed",
    "playback_observed",
)
OUTCOME_STATE_RANK = {state: index for index, state in enumerate(OUTCOME_STATES)}
VERIFICATION_STATUSES = frozenset({"verified", "verification_pending"})
_STATE_TIME_FIELDS = {
    "native_drawer_opened": "native_drawer_opened_at",
    "subscription_observed": "subscription_observed_at",
    "library_observed": "library_observed_at",
    "playback_observed": "playback_observed_at",
}
_STATE_SOURCE_FIELDS = {
    "native_drawer_opened": "native_drawer_source",
    "subscription_observed": "subscription_source",
    "library_observed": "library_source",
    "playback_observed": "playback_source",
}


def _text(value: Any, limit: int) -> str:
    """把任意标量规范为有界单行文本。"""
    return " ".join(str(value or "").split()).strip()[: max(1, int(limit))]


def _iso(value: Any, field_name: str, *, optional: bool = False) -> str:
    """规范 ISO 时间并统一为带时区格式。"""
    text = _text(value, 64)
    if not text and optional:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ValueError(f"outcome attribution {field_name} is invalid") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class OutcomeAttribution:
    """保存一条推荐从交互到播放的可信单调归因。"""

    attribution_id: str
    profile_id: str
    run_id: str
    candidate_id: str
    title: str
    media_type: str
    tmdb_id: str
    mp_media_type: str
    state: str
    created_at: str
    updated_at: str
    native_drawer_opened_at: str = ""
    subscription_observed_at: str = ""
    library_observed_at: str = ""
    playback_observed_at: str = ""
    native_drawer_source: str = ""
    subscription_source: str = ""
    library_source: str = ""
    playback_source: str = ""
    verification_status: str = "verified"
    verification_code: str = "direct_evidence"
    last_checked_at: str = ""
    revision: int = 1
    schema_version: int = 1

    def __post_init__(self) -> None:
        """规范身份、状态、证据时间和复查结果。"""
        for field_name, limit in (
            ("attribution_id", 192),
            ("profile_id", 240),
            ("run_id", 160),
            ("candidate_id", 160),
            ("title", 160),
            ("media_type", 24),
            ("tmdb_id", 32),
            ("mp_media_type", 24),
            ("state", 32),
            ("native_drawer_source", 48),
            ("subscription_source", 48),
            ("library_source", 48),
            ("playback_source", 48),
            ("verification_status", 32),
            ("verification_code", 64),
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), limit))
        for field_name in (
            "created_at",
            "updated_at",
            "native_drawer_opened_at",
            "subscription_observed_at",
            "library_observed_at",
            "playback_observed_at",
            "last_checked_at",
        ):
            object.__setattr__(
                self,
                field_name,
                _iso(
                    getattr(self, field_name),
                    field_name,
                    optional=field_name not in {"created_at", "updated_at"},
                ),
            )
        object.__setattr__(self, "revision", max(1, int(self.revision or 1)))
        object.__setattr__(self, "schema_version", int(self.schema_version or 1))
        if not all(
            (
                self.attribution_id,
                self.profile_id,
                self.run_id,
                self.candidate_id,
                self.title,
                self.media_type,
                self.tmdb_id,
            )
        ):
            raise ValueError("outcome attribution identity is incomplete")
        if self.state not in OUTCOME_STATE_RANK:
            raise ValueError("outcome attribution state is invalid")
        if self.verification_status not in VERIFICATION_STATUSES:
            raise ValueError("outcome attribution verification_status is invalid")
        evidence_states = []
        for evidence_state in OUTCOME_STATES:
            evidence_time = getattr(self, _STATE_TIME_FIELDS[evidence_state])
            evidence_source = getattr(self, _STATE_SOURCE_FIELDS[evidence_state])
            if bool(evidence_time) != bool(evidence_source):
                raise ValueError(
                    "outcome attribution evidence time and source must be paired"
                )
            if evidence_time:
                evidence_states.append(evidence_state)
        if not evidence_states or evidence_states[-1] != self.state:
            raise ValueError("outcome attribution state must match highest evidence")
        if self.schema_version != 1:
            raise ValueError("outcome attribution schema_version is unsupported")

    @property
    def terminal(self) -> bool:
        """返回归因是否已经到达播放终态。"""
        return self.state == "playback_observed"

    def advance(self, state: str, observed_at: str, source: str) -> "OutcomeAttribution":
        """记录一项可信证据，并仅在更高层级时推进当前状态。"""
        target = _text(state, 32)
        if target not in OUTCOME_STATE_RANK:
            raise ValueError("outcome attribution target state is invalid")
        evidence_time = _iso(observed_at, _STATE_TIME_FIELDS[target])
        evidence_source = _text(source, 48)
        if not evidence_source:
            raise ValueError("outcome attribution evidence source is required")
        if getattr(self, _STATE_TIME_FIELDS[target]):
            return self
        changes = {
            _STATE_TIME_FIELDS[target]: evidence_time,
            _STATE_SOURCE_FIELDS[target]: evidence_source,
            "updated_at": evidence_time,
            "verification_status": "verified",
            "verification_code": "evidence_observed",
            "revision": self.revision + 1,
        }
        if OUTCOME_STATE_RANK[target] > OUTCOME_STATE_RANK[self.state]:
            changes["state"] = target
        return replace(self, **changes)

    def mark_verification(
        self,
        *,
        checked_at: str,
        pending: bool,
        code: str,
    ) -> "OutcomeAttribution":
        """保存本轮复查结论，不改变最后可信业务状态。"""
        current = _iso(checked_at, "last_checked_at")
        return replace(
            self,
            verification_status=(
                "verification_pending" if pending else "verified"
            ),
            verification_code=_text(code, 64) or "verification_complete",
            last_checked_at=current,
            updated_at=current,
            revision=self.revision + 1,
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化且不含宿主凭据的归因字典。"""
        return asdict(self)

    def to_public_dict(self) -> Dict[str, Any]:
        """返回前端和脱敏导出可安全展示的归因事实。"""
        return self.to_dict()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OutcomeAttribution":
        """从持久化字典恢复并校验归因记录。"""
        if not isinstance(value, Mapping):
            raise ValueError("outcome attribution must be a mapping")
        fields = cls.__dataclass_fields__
        return cls(
            **{
                name: (
                    value.get(name)
                    if field.default is MISSING
                    else value.get(name, field.default)
                )
                for name, field in fields.items()
            }
        )
