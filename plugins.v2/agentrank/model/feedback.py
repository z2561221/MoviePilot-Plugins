"""用户反馈事件与分段账本领域模型。"""

from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, Mapping, Tuple


FEEDBACK_EVENT_SCHEMA_VERSION = 1
FEEDBACK_LEDGER_SCHEMA_VERSION = 1


def _text(value: Any) -> str:
    """把可选标量规范为去除首尾空白的文本。"""
    return str(value or "").strip()


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
        if self.schema_version != FEEDBACK_LEDGER_SCHEMA_VERSION:
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
    segments: Tuple[FeedbackSegmentReference, ...] = ()
    idempotency: Mapping[str, FeedbackEventPointer] = None
    schema_version: int = FEEDBACK_LEDGER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """校验索引中的分段连续性、下一序号和幂等指针。"""
        object.__setattr__(self, "profile_id", _text(self.profile_id))
        object.__setattr__(self, "next_sequence", int(self.next_sequence))
        object.__setattr__(self, "segments", tuple(self.segments or ()))
        object.__setattr__(self, "idempotency", dict(self.idempotency or {}))
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not self.profile_id or self.next_sequence <= 0:
            raise ValueError("feedback ledger index scope is invalid")
        if self.schema_version != FEEDBACK_LEDGER_SCHEMA_VERSION:
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
        if previous_end and self.next_sequence != previous_end + 1:
            raise ValueError("feedback ledger next_sequence is inconsistent")
        if not previous_end and self.next_sequence != 1:
            raise ValueError("empty feedback ledger must start at sequence one")
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
            segments=tuple(references),
            idempotency=idempotency,
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化索引。"""
        return {
            "profile_id": self.profile_id,
            "next_sequence": self.next_sequence,
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
        return cls(
            profile_id=value.get("profile_id"),
            next_sequence=value.get("next_sequence") or 0,
            segments=tuple(
                FeedbackSegmentReference.from_dict(item)
                for item in value.get("segments") or []
            ),
            idempotency={
                _text(key): FeedbackEventPointer.from_dict(pointer)
                for key, pointer in raw_idempotency.items()
            },
            schema_version=value.get("schema_version") or 0,
        )

    def referenced_segment_ids(self) -> Iterable[int]:
        """按顺序返回索引引用的段号。"""
        return (reference.segment_id for reference in self.segments)
