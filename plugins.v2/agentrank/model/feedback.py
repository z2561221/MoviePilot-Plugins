"""用户反馈事件与分段账本领域模型。"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from math import exp, log
from typing import Any, Dict, Iterable, Mapping, Tuple


FEEDBACK_EVENT_SCHEMA_VERSION = 1
FEEDBACK_LEDGER_SCHEMA_VERSION = 2
BOARD_CONSUMPTION_SCHEMA_VERSION = 1
SHORT_TERM_SIGNAL_SCHEMA_VERSION = 1

BOARD_CONSUMPTION_INTERACTIONS = frozenset(
    {
        "like",
        "dislike",
        "ignore",
        "subscribe",
        "playback_start",
        "playback_completed",
        "playback_abandoned",
        "detail_opened",
    }
)
SHORT_TERM_SIGNAL_KINDS = frozenset(
    {
        "like",
        "dislike",
        "subscribe",
        "playback_start",
        "playback_completed",
        "playback_abandoned",
        "detail_opened",
        "rotation",
    }
)


def _text(value: Any) -> str:
    """把可选标量规范为去除首尾空白的文本。"""
    return str(value or "").strip()


def _unique_texts(values: Iterable[Any]) -> Tuple[str, ...]:
    """返回保持顺序的唯一非空文本。"""
    result = []
    for value in values or ():
        text = _text(value)
        if text and text not in result:
            result.append(text)
    return tuple(result)


def _time(value: Any, field_name: str, *, optional: bool = False) -> str:
    """规范可选 ISO 时间，避免不同来源的时间格式破坏指纹。"""
    text = _text(value)
    if not text and optional:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be an ISO datetime") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class BoardConsumption:
    """记录一个榜单 revision 的真实曝光、详情打开和交互状态。"""

    profile_id: str
    run_id: str
    board_revision: int
    exposed_at: str = ""
    exposed_candidate_ids: Tuple[str, ...] = ()
    detail_opened_candidate_ids: Tuple[str, ...] = ()
    interaction_kinds: Tuple[str, ...] = ()
    last_interaction_at: str = ""
    exposure_count: int = 0
    detail_open_count: int = 0
    schema_version: int = BOARD_CONSUMPTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范榜单身份并限制交互枚举。"""
        object.__setattr__(self, "profile_id", _text(self.profile_id))
        object.__setattr__(self, "run_id", _text(self.run_id))
        object.__setattr__(self, "board_revision", max(1, int(self.board_revision or 1)))
        object.__setattr__(self, "exposed_at", _time(self.exposed_at, "exposed_at", optional=True))
        object.__setattr__(self, "last_interaction_at", _time(self.last_interaction_at, "last_interaction_at", optional=True))
        object.__setattr__(self, "exposed_candidate_ids", _unique_texts(self.exposed_candidate_ids))
        object.__setattr__(self, "detail_opened_candidate_ids", _unique_texts(self.detail_opened_candidate_ids))
        interactions = _unique_texts(self.interaction_kinds)
        if any(item not in BOARD_CONSUMPTION_INTERACTIONS for item in interactions):
            raise ValueError("board consumption interaction is invalid")
        object.__setattr__(self, "interaction_kinds", interactions)
        object.__setattr__(self, "exposure_count", max(0, int(self.exposure_count or 0)))
        object.__setattr__(self, "detail_open_count", max(0, int(self.detail_open_count or 0)))
        object.__setattr__(self, "schema_version", int(self.schema_version or 0))
        if not self.profile_id or not self.run_id:
            raise ValueError("board consumption identity is incomplete")
        if self.schema_version != BOARD_CONSUMPTION_SCHEMA_VERSION:
            raise ValueError("board consumption schema is unsupported")

    @property
    def exposed(self) -> bool:
        """返回榜单是否被页面实际记录为可见。"""
        return bool(self.exposed_at)

    @property
    def interacted(self) -> bool:
        """返回是否存在明确交互或结果事实。"""
        return bool(self.interaction_kinds)

    def with_exposure(self, candidate_ids: Iterable[Any], observed_at: str) -> "BoardConsumption":
        """幂等合并一次页面曝光；重复调用不会增加曝光次数。"""
        ids = _unique_texts(candidate_ids)
        if self.exposed:
            return replace(
                self,
                exposed_candidate_ids=_unique_texts((*self.exposed_candidate_ids, *ids)),
            )
        return replace(
            self,
            exposed_at=_time(observed_at, "exposed_at"),
            exposed_candidate_ids=_unique_texts((*self.exposed_candidate_ids, *ids)),
            exposure_count=self.exposure_count + 1,
        )

    def with_detail_opened(self, candidate_id: Any, observed_at: str) -> "BoardConsumption":
        """幂等记录一条推荐详情打开。"""
        candidate = _text(candidate_id)
        if not candidate:
            raise ValueError("detail opened candidate_id is required")
        if candidate in self.detail_opened_candidate_ids:
            return self
        return replace(
            self,
            detail_opened_candidate_ids=(*self.detail_opened_candidate_ids, candidate),
            detail_open_count=self.detail_open_count + 1,
            last_interaction_at=_time(observed_at, "last_interaction_at"),
            interaction_kinds=_unique_texts((*self.interaction_kinds, "detail_opened")),
        )

    def with_interaction(self, kind: Any, observed_at: str) -> "BoardConsumption":
        """记录交互种类，但不把无操作转换为负向偏好。"""
        action = _text(kind).casefold()
        if action not in BOARD_CONSUMPTION_INTERACTIONS:
            raise ValueError("board consumption interaction is invalid")
        return replace(
            self,
            last_interaction_at=_time(observed_at, "last_interaction_at"),
            interaction_kinds=_unique_texts((*self.interaction_kinds, action)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回稳定的页面消费记录。"""
        return {
            "profile_id": self.profile_id,
            "run_id": self.run_id,
            "board_revision": self.board_revision,
            "exposed_at": self.exposed_at,
            "exposed": self.exposed,
            "exposed_candidate_ids": list(self.exposed_candidate_ids),
            "detail_opened_candidate_ids": list(self.detail_opened_candidate_ids),
            "interaction_kinds": list(self.interaction_kinds),
            "last_interaction_at": self.last_interaction_at,
            "exposure_count": self.exposure_count,
            "detail_open_count": self.detail_open_count,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BoardConsumption":
        """从持久化数据恢复榜单消费记录。"""
        if not isinstance(value, Mapping):
            raise ValueError("board consumption must be a mapping")
        return cls(
            profile_id=value.get("profile_id"),
            run_id=value.get("run_id"),
            board_revision=value.get("board_revision") or value.get("revision") or 1,
            exposed_at=value.get("exposed_at") or "",
            exposed_candidate_ids=tuple(value.get("exposed_candidate_ids") or ()),
            detail_opened_candidate_ids=tuple(value.get("detail_opened_candidate_ids") or ()),
            interaction_kinds=tuple(value.get("interaction_kinds") or ()),
            last_interaction_at=value.get("last_interaction_at") or "",
            exposure_count=value.get("exposure_count") or 0,
            detail_open_count=value.get("detail_open_count") or 0,
            schema_version=value.get("schema_version") or BOARD_CONSUMPTION_SCHEMA_VERSION,
        )


@dataclass(frozen=True)
class ShortTermSignal:
    """保存按时间衰减的近期反馈；它永远不会直接升级为长期记忆。"""

    profile_id: str
    kind: str
    idempotency_key: str
    candidate_id: str = ""
    run_id: str = ""
    board_revision: int = 0
    strength: float = 0.0
    decay_days: int = 30
    observed_at: str = ""
    source: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = SHORT_TERM_SIGNAL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范信号身份、强度和半衰期。"""
        for field_name in ("profile_id", "kind", "idempotency_key", "candidate_id", "run_id", "source"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name)))
        kind = self.kind.casefold()
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "board_revision", max(0, int(self.board_revision or 0)))
        object.__setattr__(self, "strength", max(-1.0, min(1.0, float(self.strength or 0.0))))
        object.__setattr__(self, "decay_days", max(1, min(3650, int(self.decay_days or 30))))
        object.__setattr__(self, "observed_at", _time(self.observed_at, "observed_at"))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))
        object.__setattr__(self, "schema_version", int(self.schema_version or 0))
        if not self.profile_id or not self.kind or not self.idempotency_key:
            raise ValueError("short-term signal identity is incomplete")
        if self.kind not in SHORT_TERM_SIGNAL_KINDS:
            raise ValueError("short-term signal kind is invalid")
        if self.kind != "rotation" and not self.candidate_id:
            raise ValueError("short-term signal candidate_id is required")
        if self.schema_version != SHORT_TERM_SIGNAL_SCHEMA_VERSION:
            raise ValueError("short-term signal schema is unsupported")

    @property
    def polarity(self) -> str:
        """返回排序可用的信号方向；轮换信号不参与负向口味。"""
        if self.kind in {"dislike", "playback_abandoned"}:
            return "negative"
        if self.kind == "rotation":
            return "rotation"
        return "positive"

    def decayed_strength(self, at: Any = None) -> float:
        """按半衰期计算当前强度，避免近期行为永久占据排序。"""
        try:
            current = datetime.now(timezone.utc) if at is None else datetime.fromisoformat(str(at).replace("Z", "+00:00"))
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            observed = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (current - observed).total_seconds() / 86400.0)
        except (TypeError, ValueError):
            age_days = 0.0
        return self.strength * exp(-log(2.0) * age_days / self.decay_days)

    def to_dict(self) -> Dict[str, Any]:
        """返回不含提示词和敏感凭据的短期信号。"""
        return {
            "profile_id": self.profile_id,
            "kind": self.kind,
            "idempotency_key": self.idempotency_key,
            "candidate_id": self.candidate_id,
            "run_id": self.run_id,
            "board_revision": self.board_revision,
            "strength": self.strength,
            "decay_days": self.decay_days,
            "observed_at": self.observed_at,
            "source": self.source,
            "metadata": dict(self.metadata),
            "polarity": self.polarity,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ShortTermSignal":
        """从持久化数据恢复短期信号。"""
        if not isinstance(value, Mapping):
            raise ValueError("short-term signal must be a mapping")
        return cls(
            profile_id=value.get("profile_id"),
            kind=value.get("kind"),
            idempotency_key=value.get("idempotency_key"),
            candidate_id=value.get("candidate_id") or "",
            run_id=value.get("run_id") or "",
            board_revision=value.get("board_revision") or 0,
            strength=value.get("strength") or 0.0,
            decay_days=value.get("decay_days") or 30,
            observed_at=value.get("observed_at"),
            source=value.get("source") or "",
            metadata=value.get("metadata") or {},
            schema_version=value.get("schema_version") or SHORT_TERM_SIGNAL_SCHEMA_VERSION,
        )


@dataclass(frozen=True)
class FeedbackEvent:
    """表示一条按 profile 隔离且写入后不可变的用户反馈事实。"""

    profile_id: str
    kind: str
    idempotency_key: str
    event_id: str = ""
    sequence: int = 0
    candidate_id: str = ""
    run_id: str = ""
    analysis_id: str = ""
    comment: str = ""
    created_by_mp_user_id: str = ""
    created_at: str = ""
    supersedes: str = ""
    status: str = "recorded"
    schema_version: int = FEEDBACK_EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范化字段并区分待写入事件与已持久化事件。"""
        for field_name in (
            "profile_id",
            "kind",
            "idempotency_key",
            "event_id",
            "candidate_id",
            "run_id",
            "analysis_id",
            "comment",
            "created_by_mp_user_id",
            "created_at",
            "supersedes",
            "status",
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name)))
        object.__setattr__(self, "sequence", int(self.sequence))
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not self.profile_id:
            raise ValueError("feedback event profile_id is required")
        if not self.kind:
            raise ValueError("feedback event kind is required")
        if not self.idempotency_key:
            raise ValueError("feedback event idempotency_key is required")
        if len(self.idempotency_key) > 256:
            raise ValueError("feedback event idempotency_key is too long")
        if not self.status:
            raise ValueError("feedback event status is required")
        if self.schema_version != FEEDBACK_EVENT_SCHEMA_VERSION:
            raise ValueError("feedback event schema_version is unsupported")
        if self.sequence < 0:
            raise ValueError("feedback event sequence cannot be negative")
        persisted_fields = bool(self.event_id or self.created_at)
        if self.sequence == 0 and persisted_fields:
            raise ValueError("draft feedback event cannot have persistence fields")
        if self.sequence > 0 and (not self.event_id or not self.created_at):
            raise ValueError("persisted feedback event is incomplete")

    @property
    def is_persisted(self) -> bool:
        """返回事件是否已由仓库分配身份与序号。"""
        return self.sequence > 0

    def assign_persistence(
        self, *, event_id: str, sequence: int, created_at: str
    ) -> "FeedbackEvent":
        """由仓库为待写入事件分配不可变持久化字段。"""
        if self.is_persisted:
            raise ValueError("feedback event is already persisted")
        return replace(
            self,
            event_id=event_id,
            sequence=sequence,
            created_at=created_at,
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回稳定的可持久化事件字典。"""
        return {
            "event_id": self.event_id,
            "profile_id": self.profile_id,
            "sequence": self.sequence,
            "kind": self.kind,
            "candidate_id": self.candidate_id,
            "run_id": self.run_id,
            "analysis_id": self.analysis_id,
            "comment": self.comment,
            "created_by_mp_user_id": self.created_by_mp_user_id,
            "created_at": self.created_at,
            "idempotency_key": self.idempotency_key,
            "supersedes": self.supersedes,
            "status": self.status,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FeedbackEvent":
        """从持久化字典恢复并校验一条已写入事件。"""
        if not isinstance(value, Mapping):
            raise ValueError("feedback event must be a mapping")
        event = cls(
            event_id=value.get("event_id"),
            profile_id=value.get("profile_id"),
            sequence=value.get("sequence") or 0,
            kind=value.get("kind"),
            candidate_id=value.get("candidate_id"),
            run_id=value.get("run_id"),
            analysis_id=value.get("analysis_id"),
            comment=value.get("comment"),
            created_by_mp_user_id=value.get("created_by_mp_user_id"),
            created_at=value.get("created_at"),
            idempotency_key=value.get("idempotency_key"),
            supersedes=value.get("supersedes"),
            status=value.get("status") or "recorded",
            schema_version=value.get("schema_version") or 0,
        )
        if not event.is_persisted:
            raise ValueError("stored feedback event must have a positive sequence")
        return event


@dataclass(frozen=True)
class FeedbackAppendResult:
    """返回幂等追加结果，供调用方只为首次事件触发后续学习。"""

    event: FeedbackEvent
    created: bool

    def __post_init__(self) -> None:
        """确保结果始终携带一条已持久化事件。"""
        if not isinstance(self.event, FeedbackEvent) or not self.event.is_persisted:
            raise ValueError("feedback append result requires a persisted event")
        object.__setattr__(self, "created", bool(self.created))


@dataclass(frozen=True)
class FeedbackEventPointer:
    """定位幂等键对应事件所在的段和序号。"""

    segment_id: int
    sequence: int

    def __post_init__(self) -> None:
        """拒绝无效的段号或事件序号。"""
        object.__setattr__(self, "segment_id", int(self.segment_id))
        object.__setattr__(self, "sequence", int(self.sequence))
        if self.segment_id <= 0 or self.sequence <= 0:
            raise ValueError("feedback event pointer is invalid")

    def to_dict(self) -> Dict[str, int]:
        """返回可持久化指针。"""
        return {"segment_id": self.segment_id, "sequence": self.sequence}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FeedbackEventPointer":
        """从持久化字典恢复事件指针。"""
        if not isinstance(value, Mapping):
            raise ValueError("feedback event pointer must be a mapping")
        return cls(
            segment_id=value.get("segment_id") or 0,
            sequence=value.get("sequence") or 0,
        )


@dataclass(frozen=True)
class FeedbackSegmentReference:
    """描述一个反馈事件段在账本中的连续序号范围。"""

    segment_id: int
    start_sequence: int
    end_sequence: int
    event_count: int

    def __post_init__(self) -> None:
        """校验段引用的序号范围与事件数量一致。"""
        for field_name in (
            "segment_id",
            "start_sequence",
            "end_sequence",
            "event_count",
        ):
            object.__setattr__(self, field_name, int(getattr(self, field_name)))
        if self.segment_id <= 0 or self.start_sequence <= 0:
            raise ValueError("feedback segment reference is invalid")
        if self.end_sequence < self.start_sequence:
            raise ValueError("feedback segment sequence range is invalid")
        if self.event_count != self.end_sequence - self.start_sequence + 1:
            raise ValueError("feedback segment event_count is inconsistent")

    def to_dict(self) -> Dict[str, int]:
        """返回可持久化段引用。"""
        return {
            "segment_id": self.segment_id,
            "start_sequence": self.start_sequence,
            "end_sequence": self.end_sequence,
            "event_count": self.event_count,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FeedbackSegmentReference":
        """从持久化字典恢复段引用。"""
        if not isinstance(value, Mapping):
            raise ValueError("feedback segment reference must be a mapping")
        return cls(
            segment_id=value.get("segment_id") or 0,
            start_sequence=value.get("start_sequence") or 0,
            end_sequence=value.get("end_sequence") or 0,
            event_count=value.get("event_count") or 0,
        )


@dataclass(frozen=True)
class FeedbackEventSegment:
    """保存同一 profile 的一段连续反馈事件。"""

    profile_id: str
    segment_id: int
    events: Tuple[FeedbackEvent, ...] = ()
    schema_version: int = FEEDBACK_LEDGER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """校验段归属以及段内严格递增的连续序号。"""
        object.__setattr__(self, "profile_id", _text(self.profile_id))
        object.__setattr__(self, "segment_id", int(self.segment_id))
        object.__setattr__(self, "events", tuple(self.events or ()))
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not self.profile_id or self.segment_id <= 0:
            raise ValueError("feedback event segment scope is invalid")
        if self.schema_version not in {1, FEEDBACK_LEDGER_SCHEMA_VERSION}:
            raise ValueError("feedback event segment schema_version is unsupported")
        previous = 0
        for event in self.events:
            if not isinstance(event, FeedbackEvent) or not event.is_persisted:
                raise ValueError("feedback event segment contains an invalid event")
            if event.profile_id != self.profile_id:
                raise ValueError("feedback event segment contains cross-profile data")
            if previous and event.sequence != previous + 1:
                raise ValueError("feedback event segment sequence is not contiguous")
            previous = event.sequence

    def append(self, event: FeedbackEvent) -> "FeedbackEventSegment":
        """返回追加一条连续事件后的新段。"""
        if event.profile_id != self.profile_id:
            raise ValueError("feedback event profile_id mismatch")
        if not event.is_persisted:
            raise ValueError("feedback event must be persisted before append")
        if self.events and event.sequence != self.events[-1].sequence + 1:
            raise ValueError("feedback event sequence is not contiguous")
        return replace(self, events=(*self.events, event))

    def to_reference(self) -> FeedbackSegmentReference:
        """根据当前非空段生成索引引用。"""
        if not self.events:
            raise ValueError("empty feedback event segment cannot be indexed")
        return FeedbackSegmentReference(
            segment_id=self.segment_id,
            start_sequence=self.events[0].sequence,
            end_sequence=self.events[-1].sequence,
            event_count=len(self.events),
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化事件段。"""
        return {
            "profile_id": self.profile_id,
            "segment_id": self.segment_id,
            "events": [event.to_dict() for event in self.events],
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FeedbackEventSegment":
        """从持久化字典恢复事件段。"""
        if not isinstance(value, Mapping):
            raise ValueError("feedback event segment must be a mapping")
        return cls(
            profile_id=value.get("profile_id"),
            segment_id=value.get("segment_id") or 0,
            events=tuple(
                FeedbackEvent.from_dict(item) for item in value.get("events") or []
            ),
            schema_version=value.get("schema_version") or 0,
        )


@dataclass(frozen=True)
class FeedbackLedgerIndex:
    """维护一个 profile 的下一序号、分段范围与幂等定位。"""

    profile_id: str
    next_sequence: int = 1
    retained_from_sequence: int = 1
    segments: Tuple[FeedbackSegmentReference, ...] = ()
    idempotency: Mapping[str, FeedbackEventPointer] = None
    schema_version: int = FEEDBACK_LEDGER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """校验索引中的分段连续性、下一序号和幂等指针。"""
        object.__setattr__(self, "profile_id", _text(self.profile_id))
        object.__setattr__(self, "next_sequence", int(self.next_sequence))
        object.__setattr__(
            self, "retained_from_sequence", int(self.retained_from_sequence)
        )
        object.__setattr__(self, "segments", tuple(self.segments or ()))
        object.__setattr__(self, "idempotency", dict(self.idempotency or {}))
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if (
            not self.profile_id
            or self.next_sequence <= 0
            or self.retained_from_sequence <= 0
            or self.retained_from_sequence > self.next_sequence
        ):
            raise ValueError("feedback ledger index scope is invalid")
        if self.schema_version not in {1, FEEDBACK_LEDGER_SCHEMA_VERSION}:
            raise ValueError("feedback ledger index schema_version is unsupported")
        previous_segment_id = 0
        previous_end = 0
        segment_ids = set()
        for reference in self.segments:
            if not isinstance(reference, FeedbackSegmentReference):
                raise ValueError("feedback ledger contains an invalid segment reference")
            if reference.segment_id <= previous_segment_id:
                raise ValueError("feedback ledger segment ids are not increasing")
            if previous_end and reference.start_sequence != previous_end + 1:
                raise ValueError("feedback ledger segment ranges are not contiguous")
            previous_segment_id = reference.segment_id
            previous_end = reference.end_sequence
            segment_ids.add(reference.segment_id)
        if self.segments and self.segments[0].start_sequence != self.retained_from_sequence:
            raise ValueError("feedback ledger retained range is inconsistent")
        if previous_end and self.next_sequence != previous_end + 1:
            raise ValueError("feedback ledger next_sequence is inconsistent")
        if not previous_end and self.retained_from_sequence != self.next_sequence:
            raise ValueError("empty feedback ledger retained range is inconsistent")
        for key, pointer in self.idempotency.items():
            if not _text(key) or not isinstance(pointer, FeedbackEventPointer):
                raise ValueError("feedback ledger idempotency entry is invalid")
            if pointer.segment_id not in segment_ids or pointer.sequence >= self.next_sequence:
                raise ValueError("feedback ledger idempotency pointer is out of range")

    @classmethod
    def empty(cls, profile_id: str) -> "FeedbackLedgerIndex":
        """创建一个尚未包含事件的账本索引。"""
        return cls(profile_id=profile_id)

    def with_event(
        self, segment: FeedbackEventSegment, event: FeedbackEvent
    ) -> "FeedbackLedgerIndex":
        """返回登记新事件和最新段引用后的索引。"""
        if event.sequence != self.next_sequence:
            raise ValueError("feedback event does not match next_sequence")
        reference = segment.to_reference()
        references = list(self.segments)
        if references and references[-1].segment_id == reference.segment_id:
            references[-1] = reference
        else:
            references.append(reference)
        idempotency = dict(self.idempotency)
        idempotency[event.idempotency_key] = FeedbackEventPointer(
            segment_id=segment.segment_id,
            sequence=event.sequence,
        )
        return FeedbackLedgerIndex(
            profile_id=self.profile_id,
            next_sequence=event.sequence + 1,
            retained_from_sequence=self.retained_from_sequence,
            segments=tuple(references),
            idempotency=idempotency,
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化索引。"""
        return {
            "profile_id": self.profile_id,
            "next_sequence": self.next_sequence,
            "retained_from_sequence": self.retained_from_sequence,
            "segments": [reference.to_dict() for reference in self.segments],
            "idempotency": {
                key: pointer.to_dict() for key, pointer in self.idempotency.items()
            },
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FeedbackLedgerIndex":
        """从持久化字典恢复账本索引。"""
        if not isinstance(value, Mapping):
            raise ValueError("feedback ledger index must be a mapping")
        raw_idempotency = value.get("idempotency") or {}
        if not isinstance(raw_idempotency, Mapping):
            raise ValueError("feedback ledger idempotency must be a mapping")
        schema_version = int(value.get("schema_version") or 0)
        return cls(
            profile_id=value.get("profile_id"),
            next_sequence=value.get("next_sequence") or 0,
            retained_from_sequence=(
                value.get("retained_from_sequence")
                or (
                    (value.get("segments") or [{}])[0].get("start_sequence")
                    if value.get("segments")
                    else value.get("next_sequence")
                )
                or 1
            ),
            segments=tuple(
                FeedbackSegmentReference.from_dict(item)
                for item in value.get("segments") or []
            ),
            idempotency={
                _text(key): FeedbackEventPointer.from_dict(pointer)
                for key, pointer in raw_idempotency.items()
            },
            schema_version=schema_version,
        )

    def referenced_segment_ids(self) -> Iterable[int]:
        """按顺序返回索引引用的段号。"""
        return (reference.segment_id for reference in self.segments)
