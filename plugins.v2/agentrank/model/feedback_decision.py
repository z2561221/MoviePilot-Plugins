"""反馈理解后的待确认记忆提案与歧义问询模型。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, Mapping, Tuple


FEEDBACK_DECISION_SCHEMA_VERSION = 1
MEMORY_PROPOSAL_STATUSES = frozenset(
    {"pending_confirmation", "confirmed", "rejected", "expired", "superseded"}
)
MEMORY_CHANGE_OPERATIONS = frozenset(
    {"add", "reinforce", "weaken", "restore", "archive"}
)
PENDING_QUESTION_STATUSES = frozenset(
    {"pending", "answered", "dismissed", "expired", "superseded"}
)
QUESTION_REMINDER_POLICIES = frozenset(
    {"unselected", "in_1_day", "in_3_days", "in_7_days", "never"}
)


def _text(value: Any, limit: int = 240) -> str:
    """把可选标量规范为有界文本。"""
    return str(value or "").strip()[: max(1, int(limit))]


def _unique_texts(
    values: Iterable[Any], *, item_limit: int = 16, text_limit: int = 160
) -> Tuple[str, ...]:
    """返回保持顺序的唯一有界文本元组。"""
    result = []
    for value in values or ():
        text = _text(value, text_limit)
        if text and text not in result:
            result.append(text)
        if len(result) >= max(1, int(item_limit)):
            break
    return tuple(result)


def _iso_time(value: Any, field_name: str) -> str:
    """校验并返回带时区的 ISO 时间文本。"""
    text = _text(value, 64)
    if not text:
        raise ValueError(f"{field_name} is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} must be ISO datetime") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include timezone")
    return text


@dataclass(frozen=True)
class MemoryProposalChange:
    """描述一项尚未确认的长期记忆变化预览。"""

    change_id: str
    operation: str
    category: str
    value: str
    polarity: str
    certainty: float
    evidence_refs: Tuple[str, ...]
    preview: str
    target_memory_item_ids: Tuple[str, ...] = ()
    schema_version: int = FEEDBACK_DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范化变化字段并限制操作、极性和证据范围。"""
        object.__setattr__(self, "change_id", _text(self.change_id, 160))
        object.__setattr__(self, "operation", _text(self.operation, 24).casefold())
        object.__setattr__(self, "category", _text(self.category, 64).casefold())
        object.__setattr__(self, "value", _text(self.value, 120))
        object.__setattr__(self, "polarity", _text(self.polarity, 16).casefold())
        object.__setattr__(
            self, "certainty", max(0.0, min(float(self.certainty), 1.0))
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _unique_texts(self.evidence_refs, item_limit=16, text_limit=160),
        )
        object.__setattr__(self, "preview", _text(self.preview, 240))
        object.__setattr__(
            self,
            "target_memory_item_ids",
            _unique_texts(
                self.target_memory_item_ids, item_limit=8, text_limit=128
            ),
        )
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not self.change_id or not self.category or not self.value:
            raise ValueError("memory proposal change identity is incomplete")
        if self.operation not in MEMORY_CHANGE_OPERATIONS:
            raise ValueError("memory proposal change operation is invalid")
        if self.polarity not in {"positive", "negative"}:
            raise ValueError("memory proposal change polarity is invalid")
        if not self.evidence_refs or not self.preview:
            raise ValueError("memory proposal change requires evidence and preview")
        if self.operation in {"reinforce", "weaken", "restore", "archive"} and not (
            self.target_memory_item_ids
        ):
            raise ValueError("memory proposal change requires a target memory item")
        if self.schema_version != FEEDBACK_DECISION_SCHEMA_VERSION:
            raise ValueError("memory proposal change schema_version is unsupported")

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化的变化预览字典。"""
        return {
            "change_id": self.change_id,
            "operation": self.operation,
            "category": self.category,
            "value": self.value,
            "polarity": self.polarity,
            "certainty": self.certainty,
            "evidence_refs": list(self.evidence_refs),
            "preview": self.preview,
            "target_memory_item_ids": list(self.target_memory_item_ids),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MemoryProposalChange":
        """从持久化字典恢复一项变化预览。"""
        if not isinstance(value, Mapping):
            raise ValueError("memory proposal change must be a mapping")
        return cls(
            change_id=value.get("change_id"),
            operation=value.get("operation"),
            category=value.get("category"),
            value=value.get("value"),
            polarity=value.get("polarity"),
            certainty=value.get("certainty") or 0.0,
            evidence_refs=tuple(value.get("evidence_refs") or ()),
            preview=value.get("preview"),
            target_memory_item_ids=tuple(
                value.get("target_memory_item_ids") or ()
            ),
            schema_version=value.get("schema_version") or 0,
        )


@dataclass(frozen=True)
class MemoryProposal:
    """保存明确反馈形成的待确认记忆变化，不执行投影。"""

    proposal_id: str
    profile_id: str
    event_id: str
    event_sequence: int
    candidate_id: str
    understanding_record_id: str
    restatement: str
    changes: Tuple[MemoryProposalChange, ...]
    evidence_refs: Tuple[str, ...]
    impact_preview: Tuple[str, ...]
    expected_memory_revision: int
    created_at: str
    expires_at: str
    status: str = "pending_confirmation"
    supersedes: str = ""
    reminder_policy: str = "unselected"
    next_remind_at: str = ""
    last_reminded_at: str = ""
    resolved_at: str = ""
    schema_version: int = FEEDBACK_DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """校验提案身份、来源序号、预览和过期时间。"""
        for field_name, limit in (
            ("proposal_id", 160),
            ("profile_id", 240),
            ("event_id", 160),
            ("candidate_id", 160),
            ("understanding_record_id", 200),
            ("restatement", 240),
            ("status", 32),
            ("supersedes", 160),
            ("reminder_policy", 32),
            ("next_remind_at", 64),
            ("last_reminded_at", 64),
            ("resolved_at", 64),
        ):
            object.__setattr__(
                self, field_name, _text(getattr(self, field_name), limit)
            )
        object.__setattr__(self, "event_sequence", int(self.event_sequence))
        object.__setattr__(self, "changes", tuple(self.changes or ()))
        object.__setattr__(
            self,
            "evidence_refs",
            _unique_texts(self.evidence_refs, item_limit=32, text_limit=160),
        )
        object.__setattr__(
            self,
            "impact_preview",
            _unique_texts(self.impact_preview, item_limit=8, text_limit=240),
        )
        object.__setattr__(
            self, "expected_memory_revision", max(0, int(self.expected_memory_revision))
        )
        object.__setattr__(self, "created_at", _iso_time(self.created_at, "created_at"))
        object.__setattr__(self, "expires_at", _iso_time(self.expires_at, "expires_at"))
        for field_name in ("next_remind_at", "last_reminded_at", "resolved_at"):
            value = getattr(self, field_name)
            if value:
                object.__setattr__(self, field_name, _iso_time(value, field_name))
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not all(
            (
                self.proposal_id,
                self.profile_id,
                self.event_id,
                self.candidate_id,
                self.understanding_record_id,
                self.restatement,
            )
        ):
            raise ValueError("memory proposal identity is incomplete")
        if self.event_sequence <= 0:
            raise ValueError("memory proposal event_sequence must be positive")
        if not 1 <= len(self.changes) <= 8 or any(
            not isinstance(item, MemoryProposalChange) for item in self.changes
        ):
            raise ValueError("memory proposal changes are invalid")
        if not self.evidence_refs or not self.impact_preview:
            raise ValueError("memory proposal requires evidence and impact preview")
        if self.status not in MEMORY_PROPOSAL_STATUSES:
            raise ValueError("memory proposal status is invalid")
        if self.reminder_policy not in QUESTION_REMINDER_POLICIES:
            raise ValueError("memory proposal reminder_policy is invalid")
        if self.reminder_policy in {"unselected", "never"} and self.next_remind_at:
            raise ValueError("memory proposal reminder policy cannot have next_remind_at")
        if self.status == "pending_confirmation" and self.resolved_at:
            raise ValueError("pending memory proposal cannot be resolved")
        if self.status != "pending_confirmation" and not self.resolved_at:
            raise ValueError("resolved memory proposal requires resolved_at")
        if datetime.fromisoformat(self.expires_at.replace("Z", "+00:00")) <= datetime.fromisoformat(
            self.created_at.replace("Z", "+00:00")
        ):
            raise ValueError("memory proposal expires_at must be later than created_at")
        if self.schema_version != FEEDBACK_DECISION_SCHEMA_VERSION:
            raise ValueError("memory proposal schema_version is unsupported")

    def to_dict(self) -> Dict[str, Any]:
        """返回不含提示词和思维链的提案字典。"""
        return {
            "record_type": "memory_proposal",
            "proposal_id": self.proposal_id,
            "profile_id": self.profile_id,
            "event_id": self.event_id,
            "event_sequence": self.event_sequence,
            "candidate_id": self.candidate_id,
            "understanding_record_id": self.understanding_record_id,
            "restatement": self.restatement,
            "changes": [item.to_dict() for item in self.changes],
            "evidence_refs": list(self.evidence_refs),
            "impact_preview": list(self.impact_preview),
            "expected_memory_revision": self.expected_memory_revision,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "status": self.status,
            "supersedes": self.supersedes,
            "reminder_policy": self.reminder_policy,
            "next_remind_at": self.next_remind_at,
            "last_reminded_at": self.last_reminded_at,
            "resolved_at": self.resolved_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MemoryProposal":
        """从持久化字典恢复待确认记忆提案。"""
        if not isinstance(value, Mapping):
            raise ValueError("memory proposal must be a mapping")
        return cls(
            proposal_id=value.get("proposal_id"),
            profile_id=value.get("profile_id"),
            event_id=value.get("event_id"),
            event_sequence=value.get("event_sequence") or 0,
            candidate_id=value.get("candidate_id"),
            understanding_record_id=value.get("understanding_record_id"),
            restatement=value.get("restatement"),
            changes=tuple(
                MemoryProposalChange.from_dict(item)
                for item in value.get("changes") or ()
            ),
            evidence_refs=tuple(value.get("evidence_refs") or ()),
            impact_preview=tuple(value.get("impact_preview") or ()),
            expected_memory_revision=value.get("expected_memory_revision") or 0,
            created_at=value.get("created_at"),
            expires_at=value.get("expires_at"),
            status=value.get("status") or "pending_confirmation",
            supersedes=value.get("supersedes"),
            reminder_policy=value.get("reminder_policy") or "unselected",
            next_remind_at=value.get("next_remind_at"),
            last_reminded_at=value.get("last_reminded_at"),
            resolved_at=value.get("resolved_at"),
            schema_version=value.get("schema_version") or 0,
        )


@dataclass(frozen=True)
class PendingQuestionOption:
    """表示歧义问询中的一个稳定可选答案。"""

    option_id: str
    label: str
    schema_version: int = FEEDBACK_DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范化选项身份与显示文本。"""
        object.__setattr__(self, "option_id", _text(self.option_id, 64))
        object.__setattr__(self, "label", _text(self.label, 120))
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not self.option_id or not self.label:
            raise ValueError("pending question option is incomplete")
        if self.schema_version != FEEDBACK_DECISION_SCHEMA_VERSION:
            raise ValueError("pending question option schema_version is unsupported")

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化问询选项。"""
        return {
            "option_id": self.option_id,
            "label": self.label,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PendingQuestionOption":
        """从字典恢复一个问询选项。"""
        if not isinstance(value, Mapping):
            raise ValueError("pending question option must be a mapping")
        return cls(
            option_id=value.get("option_id"),
            label=value.get("label"),
            schema_version=value.get("schema_version") or 0,
        )


@dataclass(frozen=True)
class PendingQuestion:
    """保存歧义反馈的待回答问题，未回答时不改变长期记忆。"""

    question_id: str
    profile_id: str
    event_id: str
    event_sequence: int
    candidate_id: str
    understanding_record_id: str
    question: str
    options: Tuple[PendingQuestionOption, ...]
    allow_custom_answer: bool
    uncertainties: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    expected_memory_revision: int
    created_at: str
    expires_at: str
    status: str = "pending"
    reminder_policy: str = "unselected"
    next_remind_at: str = ""
    supersedes: str = ""
    selected_option_id: str = ""
    answer_text: str = ""
    answer_event_id: str = ""
    answered_by_mp_user_id: str = ""
    last_reminded_at: str = ""
    resolved_at: str = ""
    schema_version: int = FEEDBACK_DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """校验问题、选项、提醒占位与未确认边界。"""
        for field_name, limit in (
            ("question_id", 160),
            ("profile_id", 240),
            ("event_id", 160),
            ("candidate_id", 160),
            ("understanding_record_id", 200),
            ("question", 240),
            ("status", 32),
            ("reminder_policy", 32),
            ("next_remind_at", 64),
            ("supersedes", 160),
            ("selected_option_id", 64),
            ("answer_text", 1000),
            ("answer_event_id", 160),
            ("answered_by_mp_user_id", 128),
            ("last_reminded_at", 64),
            ("resolved_at", 64),
        ):
            object.__setattr__(
                self, field_name, _text(getattr(self, field_name), limit)
            )
        object.__setattr__(self, "event_sequence", int(self.event_sequence))
        object.__setattr__(self, "options", tuple(self.options or ()))
        object.__setattr__(self, "allow_custom_answer", bool(self.allow_custom_answer))
        object.__setattr__(
            self,
            "uncertainties",
            _unique_texts(self.uncertainties, item_limit=8, text_limit=160),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _unique_texts(self.evidence_refs, item_limit=16, text_limit=160),
        )
        object.__setattr__(
            self, "expected_memory_revision", max(0, int(self.expected_memory_revision))
        )
        object.__setattr__(self, "created_at", _iso_time(self.created_at, "created_at"))
        object.__setattr__(self, "expires_at", _iso_time(self.expires_at, "expires_at"))
        if self.next_remind_at:
            object.__setattr__(
                self,
                "next_remind_at",
                _iso_time(self.next_remind_at, "next_remind_at"),
            )
        for field_name in ("last_reminded_at", "resolved_at"):
            value = getattr(self, field_name)
            if value:
                object.__setattr__(self, field_name, _iso_time(value, field_name))
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not all(
            (
                self.question_id,
                self.profile_id,
                self.event_id,
                self.candidate_id,
                self.understanding_record_id,
                self.question,
            )
        ):
            raise ValueError("pending question identity is incomplete")
        if self.event_sequence <= 0:
            raise ValueError("pending question event_sequence must be positive")
        if not 2 <= len(self.options) <= 3 or any(
            not isinstance(item, PendingQuestionOption) for item in self.options
        ):
            raise ValueError("pending question must contain two or three options")
        if len({item.option_id for item in self.options}) != len(self.options):
            raise ValueError("pending question option ids must be unique")
        if not self.allow_custom_answer or not self.evidence_refs:
            raise ValueError("pending question requires custom answer and evidence")
        if self.status not in PENDING_QUESTION_STATUSES:
            raise ValueError("pending question status is invalid")
        if self.reminder_policy not in QUESTION_REMINDER_POLICIES:
            raise ValueError("pending question reminder_policy is invalid")
        if self.reminder_policy == "unselected" and self.next_remind_at:
            raise ValueError("unselected reminder cannot have next_remind_at")
        if self.reminder_policy == "never" and self.next_remind_at:
            raise ValueError("never reminder cannot have next_remind_at")
        option_ids = {item.option_id for item in self.options}
        if self.selected_option_id and self.selected_option_id not in option_ids:
            raise ValueError("pending question selected option is invalid")
        answer_audit = (
            self.selected_option_id,
            self.answer_text,
            self.answer_event_id,
            self.answered_by_mp_user_id,
        )
        if self.status == "pending":
            if any(answer_audit) or self.resolved_at:
                raise ValueError("pending question cannot contain a resolved answer")
        elif not self.resolved_at:
            raise ValueError("resolved pending question requires resolved_at")
        if self.status == "answered" and not all(
            (self.answer_event_id, self.answer_text, self.answered_by_mp_user_id)
        ):
            raise ValueError("answered question requires complete answer audit")
        if self.status != "answered" and any(answer_audit):
            raise ValueError("unanswered question cannot contain answer audit")
        if datetime.fromisoformat(self.expires_at.replace("Z", "+00:00")) <= datetime.fromisoformat(
            self.created_at.replace("Z", "+00:00")
        ):
            raise ValueError("pending question expires_at must be later than created_at")
        if self.schema_version != FEEDBACK_DECISION_SCHEMA_VERSION:
            raise ValueError("pending question schema_version is unsupported")

    def to_dict(self) -> Dict[str, Any]:
        """返回不含提示词、模型原文和思维链的问询字典。"""
        return {
            "record_type": "pending_question",
            "question_id": self.question_id,
            "profile_id": self.profile_id,
            "event_id": self.event_id,
            "event_sequence": self.event_sequence,
            "candidate_id": self.candidate_id,
            "understanding_record_id": self.understanding_record_id,
            "question": self.question,
            "options": [item.to_dict() for item in self.options],
            "allow_custom_answer": self.allow_custom_answer,
            "uncertainties": list(self.uncertainties),
            "evidence_refs": list(self.evidence_refs),
            "expected_memory_revision": self.expected_memory_revision,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "status": self.status,
            "reminder_policy": self.reminder_policy,
            "next_remind_at": self.next_remind_at,
            "supersedes": self.supersedes,
            "selected_option_id": self.selected_option_id,
            "answer_text": self.answer_text,
            "answer_event_id": self.answer_event_id,
            "answered_by_mp_user_id": self.answered_by_mp_user_id,
            "last_reminded_at": self.last_reminded_at,
            "resolved_at": self.resolved_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PendingQuestion":
        """从持久化字典恢复待回答问题。"""
        if not isinstance(value, Mapping):
            raise ValueError("pending question must be a mapping")
        return cls(
            question_id=value.get("question_id"),
            profile_id=value.get("profile_id"),
            event_id=value.get("event_id"),
            event_sequence=value.get("event_sequence") or 0,
            candidate_id=value.get("candidate_id"),
            understanding_record_id=value.get("understanding_record_id"),
            question=value.get("question"),
            options=tuple(
                PendingQuestionOption.from_dict(item)
                for item in value.get("options") or ()
            ),
            allow_custom_answer=value.get("allow_custom_answer") is True,
            uncertainties=tuple(value.get("uncertainties") or ()),
            evidence_refs=tuple(value.get("evidence_refs") or ()),
            expected_memory_revision=value.get("expected_memory_revision") or 0,
            created_at=value.get("created_at"),
            expires_at=value.get("expires_at"),
            status=value.get("status") or "pending",
            reminder_policy=value.get("reminder_policy") or "unselected",
            next_remind_at=value.get("next_remind_at"),
            supersedes=value.get("supersedes"),
            selected_option_id=value.get("selected_option_id"),
            answer_text=value.get("answer_text"),
            answer_event_id=value.get("answer_event_id"),
            answered_by_mp_user_id=value.get("answered_by_mp_user_id"),
            last_reminded_at=value.get("last_reminded_at"),
            resolved_at=value.get("resolved_at"),
            schema_version=value.get("schema_version") or 0,
        )
