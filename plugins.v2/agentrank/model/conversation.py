"""CinePilot Agent 对话线程、消息与待确认命令领域模型。"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Dict, Iterable, Mapping, Tuple


CONVERSATION_SCHEMA_VERSION = 1
CONVERSATION_MESSAGE_ROLES = frozenset({"user", "assistant"})
CONVERSATION_MESSAGE_STATUSES = frozenset(
    {
        "draft",
        "queued",
        "processing",
        "completed",
        "failed",
        "retryable_failed",
        "superseded",
    }
)
CONVERSATION_COMMAND_STATUSES = frozenset(
    {"pending_confirmation", "confirmed", "rejected", "failed", "superseded"}
)
CONVERSATION_COMMAND_KINDS = frozenset(
    {"profile_tag", "weight", "ignore", "subscribe", "reset_learning"}
)
CONVERSATION_REMINDER_POLICIES = frozenset(
    {"unselected", "in_1_day", "in_3_days", "in_7_days", "never"}
)
CONVERSATION_THREAD_STATUSES = frozenset({"active", "closed"})


def _text(value: Any, limit: int) -> str:
    """把可选标量规范为有界单行文本。"""
    return " ".join(str(value or "").split()).strip()[: max(1, int(limit))]


def _iso_time(value: Any, field_name: str, *, optional: bool = False) -> str:
    """校验并返回带时区的 ISO 时间文本。"""
    text = _text(value, 64)
    if not text and optional:
        return ""
    if not text:
        raise ValueError(f"{field_name} is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} must be ISO datetime") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include timezone")
    return text


def _unique_texts(
    values: Iterable[Any], *, item_limit: int = 24, text_limit: int = 128
) -> Tuple[str, ...]:
    """返回保持顺序的有界唯一文本元组。"""
    result = []
    for value in values or ():
        text = _text(value, text_limit)
        if text and text not in result:
            result.append(text)
        if len(result) >= max(1, int(item_limit)):
            break
    return tuple(result)


def _command_payload(kind: str, value: Mapping[str, Any]) -> Dict[str, Any]:
    """按命令类型白名单规范化执行参数。"""
    raw = dict(value or {})
    allowed = {
        "profile_tag": {"kind", "action", "tag"},
        "weight": {"weight_name", "value"},
        "ignore": {"candidate_id", "run_id", "analysis_id", "board_revision"},
        "subscribe": {"candidate_id"},
        "reset_learning": set(),
    }[kind]
    if set(raw) - allowed:
        raise ValueError("conversation command payload contains unknown fields")
    if kind == "profile_tag":
        result = {
            "kind": _text(raw.get("kind"), 16),
            "action": _text(raw.get("action"), 16),
            "tag": _text(raw.get("tag"), 20),
        }
        if result["kind"] not in {"positive", "negative"}:
            raise ValueError("conversation profile tag kind is invalid")
        if result["action"] not in {"add", "remove", "restore"}:
            raise ValueError("conversation profile tag action is invalid")
        if not result["tag"]:
            raise ValueError("conversation profile tag is required")
        return result
    if kind == "weight":
        weight_name = _text(raw.get("weight_name"), 32)
        try:
            number = float(raw.get("value"))
        except (TypeError, ValueError) as error:
            raise ValueError("conversation weight value is invalid") from error
        if not weight_name or not 0.0 <= number <= 1.0:
            raise ValueError("conversation weight command is invalid")
        return {"weight_name": weight_name, "value": number}
    if kind == "ignore":
        try:
            revision = int(raw.get("board_revision") or 0)
        except (TypeError, ValueError) as error:
            raise ValueError("conversation ignore revision is invalid") from error
        result = {
            "candidate_id": _text(raw.get("candidate_id"), 128),
            "run_id": _text(raw.get("run_id"), 128),
            "analysis_id": _text(raw.get("analysis_id"), 128),
            "board_revision": revision,
        }
        if not all(result.values()):
            raise ValueError("conversation ignore command is incomplete")
        return result
    if kind == "subscribe":
        candidate_id = _text(raw.get("candidate_id"), 128)
        if not candidate_id:
            raise ValueError("conversation subscribe candidate_id is required")
        return {"candidate_id": candidate_id}
    if raw:
        raise ValueError("conversation reset command cannot contain payload")
    return {}


@dataclass(frozen=True)
class ConversationCommand:
    """表示只能由用户显式确认后执行的受控写命令。"""

    command_id: str
    profile_id: str
    thread_id: str
    source_message_id: str
    kind: str
    title: str
    preview: str
    payload: Mapping[str, Any]
    requested_by_mp_user_id: str
    created_at: str
    status: str = "pending_confirmation"
    requires_superuser: bool = False
    supersedes: str = ""
    reminder_policy: str = "unselected"
    next_remind_at: str = ""
    last_reminded_at: str = ""
    resolved_by_mp_user_id: str = ""
    resolved_at: str = ""
    execution_code: str = ""
    execution_message: str = ""
    schema_version: int = CONVERSATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范化命令并校验待确认与终态审计字段。"""
        for field_name, limit in (
            ("command_id", 128),
            ("profile_id", 128),
            ("thread_id", 128),
            ("source_message_id", 128),
            ("kind", 32),
            ("title", 80),
            ("preview", 240),
            ("requested_by_mp_user_id", 128),
            ("status", 32),
            ("supersedes", 128),
            ("reminder_policy", 32),
            ("next_remind_at", 64),
            ("last_reminded_at", 64),
            ("resolved_by_mp_user_id", 128),
            ("execution_code", 64),
            ("execution_message", 240),
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), limit))
        object.__setattr__(self, "created_at", _iso_time(self.created_at, "created_at"))
        object.__setattr__(
            self,
            "resolved_at",
            _iso_time(self.resolved_at, "resolved_at", optional=True),
        )
        for field_name in ("next_remind_at", "last_reminded_at"):
            object.__setattr__(
                self,
                field_name,
                _iso_time(getattr(self, field_name), field_name, optional=True),
            )
        object.__setattr__(self, "requires_superuser", bool(self.requires_superuser))
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not all(
            (
                self.command_id,
                self.profile_id,
                self.thread_id,
                self.source_message_id,
                self.kind,
                self.title,
                self.preview,
                self.requested_by_mp_user_id,
            )
        ):
            raise ValueError("conversation command identity is incomplete")
        if self.kind not in CONVERSATION_COMMAND_KINDS:
            raise ValueError("conversation command kind is invalid")
        object.__setattr__(self, "payload", _command_payload(self.kind, self.payload))
        if self.status not in CONVERSATION_COMMAND_STATUSES:
            raise ValueError("conversation command status is invalid")
        if self.reminder_policy not in CONVERSATION_REMINDER_POLICIES:
            raise ValueError("conversation command reminder_policy is invalid")
        if self.reminder_policy in {"unselected", "never"} and self.next_remind_at:
            raise ValueError("conversation command reminder policy cannot have next_remind_at")
        if self.status != "pending_confirmation" and self.next_remind_at:
            raise ValueError("resolved conversation command cannot keep next_remind_at")
        resolution = (
            self.resolved_by_mp_user_id,
            self.resolved_at,
            self.execution_code,
            self.execution_message,
        )
        if self.status == "pending_confirmation" and any(resolution):
            raise ValueError("pending conversation command cannot be resolved")
        if self.status != "pending_confirmation" and not all(resolution[:2]):
            raise ValueError("resolved conversation command requires audit fields")
        if self.schema_version != CONVERSATION_SCHEMA_VERSION:
            raise ValueError("conversation command schema_version is unsupported")

    @property
    def terminal(self) -> bool:
        """返回命令是否已经离开待确认状态。"""
        return self.status != "pending_confirmation"

    def resolve(
        self,
        *,
        status: str,
        actor_id: str,
        resolved_at: str,
        code: str,
        message: str,
    ) -> "ConversationCommand":
        """返回带完整审计字段的终态命令副本。"""
        if self.terminal:
            return self
        return replace(
            self,
            status=status,
            reminder_policy="unselected",
            next_remind_at="",
            resolved_by_mp_user_id=actor_id,
            resolved_at=resolved_at,
            execution_code=code,
            execution_message=message,
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回不含凭据、提示词和模型原文的命令字典。"""
        return {
            "record_type": "conversation_command",
            "command_id": self.command_id,
            "profile_id": self.profile_id,
            "thread_id": self.thread_id,
            "source_message_id": self.source_message_id,
            "kind": self.kind,
            "title": self.title,
            "preview": self.preview,
            "payload": dict(self.payload),
            "requested_by_mp_user_id": self.requested_by_mp_user_id,
            "created_at": self.created_at,
            "status": self.status,
            "requires_superuser": self.requires_superuser,
            "supersedes": self.supersedes,
            "reminder_policy": self.reminder_policy,
            "next_remind_at": self.next_remind_at,
            "last_reminded_at": self.last_reminded_at,
            "resolved_by_mp_user_id": self.resolved_by_mp_user_id,
            "resolved_at": self.resolved_at,
            "execution_code": self.execution_code,
            "execution_message": self.execution_message,
            "schema_version": self.schema_version,
        }

    def to_public_dict(self) -> Dict[str, Any]:
        """返回前端确认窗口需要的安全命令字段。"""
        value = self.to_dict()
        value.pop("requested_by_mp_user_id", None)
        value.pop("resolved_by_mp_user_id", None)
        value.pop("reminder_policy", None)
        value.pop("next_remind_at", None)
        value.pop("last_reminded_at", None)
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ConversationCommand":
        """从持久化字典恢复待确认命令。"""
        if not isinstance(value, Mapping):
            raise ValueError("conversation command must be a mapping")
        return cls(
            command_id=value.get("command_id"),
            profile_id=value.get("profile_id"),
            thread_id=value.get("thread_id"),
            source_message_id=value.get("source_message_id"),
            kind=value.get("kind"),
            title=value.get("title"),
            preview=value.get("preview"),
            payload=value.get("payload") or {},
            requested_by_mp_user_id=value.get("requested_by_mp_user_id"),
            created_at=value.get("created_at"),
            status=value.get("status") or "pending_confirmation",
            requires_superuser=value.get("requires_superuser") is True,
            supersedes=value.get("supersedes"),
            reminder_policy=value.get("reminder_policy") or "unselected",
            next_remind_at=value.get("next_remind_at"),
            last_reminded_at=value.get("last_reminded_at"),
            resolved_by_mp_user_id=value.get("resolved_by_mp_user_id"),
            resolved_at=value.get("resolved_at"),
            execution_code=value.get("execution_code"),
            execution_message=value.get("execution_message"),
            schema_version=value.get("schema_version") or 0,
        )


@dataclass(frozen=True)
class ConversationMessage:
    """表示一条可重试且不保存 Agent 原始输出的对话消息。"""

    message_id: str
    profile_id: str
    thread_id: str
    role: str
    content: str
    status: str
    created_at: str
    idempotency_key: str = ""
    reply_to: str = ""
    created_by_mp_user_id: str = ""
    related_candidate_ids: Tuple[str, ...] = ()
    related_analysis_ids: Tuple[str, ...] = ()
    command_ids: Tuple[str, ...] = ()
    error_code: str = ""
    error_message: str = ""
    provider: str = ""
    model: str = ""
    schema_version: int = CONVERSATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范化消息并校验角色、状态和重试字段。"""
        for field_name, limit in (
            ("message_id", 128),
            ("profile_id", 128),
            ("thread_id", 128),
            ("role", 16),
            ("content", 1000),
            ("status", 24),
            ("idempotency_key", 256),
            ("reply_to", 128),
            ("created_by_mp_user_id", 128),
            ("error_code", 64),
            ("error_message", 240),
            ("provider", 80),
            ("model", 120),
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), limit))
        object.__setattr__(self, "created_at", _iso_time(self.created_at, "created_at"))
        object.__setattr__(
            self,
            "related_candidate_ids",
            _unique_texts(self.related_candidate_ids, item_limit=16),
        )
        object.__setattr__(
            self,
            "related_analysis_ids",
            _unique_texts(self.related_analysis_ids, item_limit=16),
        )
        object.__setattr__(
            self,
            "command_ids",
            _unique_texts(self.command_ids, item_limit=8),
        )
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not all((self.message_id, self.profile_id, self.thread_id, self.role, self.content)):
            raise ValueError("conversation message identity is incomplete")
        if self.role not in CONVERSATION_MESSAGE_ROLES:
            raise ValueError("conversation message role is invalid")
        if self.status not in CONVERSATION_MESSAGE_STATUSES:
            raise ValueError("conversation message status is invalid")
        if self.role == "user" and not all(
            (self.idempotency_key, self.created_by_mp_user_id)
        ):
            raise ValueError("user conversation message requires actor and idempotency")
        if self.role == "assistant" and not self.reply_to:
            raise ValueError("assistant conversation message requires reply_to")
        if self.status in {"failed", "retryable_failed"} and not self.error_code:
            raise ValueError("failed conversation message requires error_code")
        if self.status not in {"failed", "retryable_failed"} and (
            self.error_code or self.error_message
        ):
            raise ValueError("non-failed conversation message cannot contain error")
        if self.schema_version != CONVERSATION_SCHEMA_VERSION:
            raise ValueError("conversation message schema_version is unsupported")

    def to_dict(self) -> Dict[str, Any]:
        """返回不含提示词、工具过程和原始模型响应的消息字典。"""
        return {
            "record_type": "conversation_message",
            "message_id": self.message_id,
            "profile_id": self.profile_id,
            "thread_id": self.thread_id,
            "role": self.role,
            "content": self.content,
            "status": self.status,
            "created_at": self.created_at,
            "idempotency_key": self.idempotency_key,
            "reply_to": self.reply_to,
            "created_by_mp_user_id": self.created_by_mp_user_id,
            "related_candidate_ids": list(self.related_candidate_ids),
            "related_analysis_ids": list(self.related_analysis_ids),
            "command_ids": list(self.command_ids),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "provider": self.provider,
            "model": self.model,
            "schema_version": self.schema_version,
        }

    def to_public_dict(self) -> Dict[str, Any]:
        """返回对话窗口可展示且不含操作者与幂等键的字段。"""
        value = self.to_dict()
        value.pop("idempotency_key", None)
        value.pop("created_by_mp_user_id", None)
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ConversationMessage":
        """从持久化字典恢复一条对话消息。"""
        if not isinstance(value, Mapping):
            raise ValueError("conversation message must be a mapping")
        return cls(
            message_id=value.get("message_id"),
            profile_id=value.get("profile_id"),
            thread_id=value.get("thread_id"),
            role=value.get("role"),
            content=value.get("content"),
            status=value.get("status"),
            created_at=value.get("created_at"),
            idempotency_key=value.get("idempotency_key"),
            reply_to=value.get("reply_to"),
            created_by_mp_user_id=value.get("created_by_mp_user_id"),
            related_candidate_ids=tuple(value.get("related_candidate_ids") or ()),
            related_analysis_ids=tuple(value.get("related_analysis_ids") or ()),
            command_ids=tuple(value.get("command_ids") or ()),
            error_code=value.get("error_code"),
            error_message=value.get("error_message"),
            provider=value.get("provider"),
            model=value.get("model"),
            schema_version=value.get("schema_version") or 0,
        )


@dataclass(frozen=True)
class ConversationThread:
    """表示按 profile 隔离的有界 CinePilot Agent 对话线程。"""

    thread_id: str
    profile_id: str
    created_by_mp_user_id: str
    created_at: str
    updated_at: str
    revision: int = 0
    status: str = "active"
    summary: str = ""
    last_message_id: str = ""
    related_event_refs: Tuple[str, ...] = ()
    related_analysis_ids: Tuple[str, ...] = ()
    pending_command_ids: Tuple[str, ...] = ()
    schema_version: int = CONVERSATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """校验线程作用域、版本和全部有界引用。"""
        for field_name, limit in (
            ("thread_id", 128),
            ("profile_id", 128),
            ("created_by_mp_user_id", 128),
            ("status", 16),
            ("summary", 400),
            ("last_message_id", 128),
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), limit))
        object.__setattr__(self, "created_at", _iso_time(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", _iso_time(self.updated_at, "updated_at"))
        object.__setattr__(self, "revision", int(self.revision))
        object.__setattr__(
            self,
            "related_event_refs",
            _unique_texts(self.related_event_refs, item_limit=24),
        )
        object.__setattr__(
            self,
            "related_analysis_ids",
            _unique_texts(self.related_analysis_ids, item_limit=24),
        )
        object.__setattr__(
            self,
            "pending_command_ids",
            _unique_texts(self.pending_command_ids, item_limit=64),
        )
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not all((self.thread_id, self.profile_id, self.created_by_mp_user_id)):
            raise ValueError("conversation thread identity is incomplete")
        if self.revision < 0 or self.status not in CONVERSATION_THREAD_STATUSES:
            raise ValueError("conversation thread state is invalid")
        if self.schema_version != CONVERSATION_SCHEMA_VERSION:
            raise ValueError("conversation thread schema_version is unsupported")

    def to_dict(self) -> Dict[str, Any]:
        """返回线程持久化字典。"""
        return {
            "record_type": "conversation_thread",
            "thread_id": self.thread_id,
            "profile_id": self.profile_id,
            "created_by_mp_user_id": self.created_by_mp_user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revision": self.revision,
            "status": self.status,
            "summary": self.summary,
            "last_message_id": self.last_message_id,
            "related_event_refs": list(self.related_event_refs),
            "related_analysis_ids": list(self.related_analysis_ids),
            "pending_command_ids": list(self.pending_command_ids),
            "schema_version": self.schema_version,
        }

    def to_public_dict(self) -> Dict[str, Any]:
        """返回不含线程创建操作者的公开字段。"""
        value = self.to_dict()
        value.pop("created_by_mp_user_id", None)
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ConversationThread":
        """从持久化字典恢复一个对话线程。"""
        if not isinstance(value, Mapping):
            raise ValueError("conversation thread must be a mapping")
        return cls(
            thread_id=value.get("thread_id"),
            profile_id=value.get("profile_id"),
            created_by_mp_user_id=value.get("created_by_mp_user_id"),
            created_at=value.get("created_at"),
            updated_at=value.get("updated_at"),
            revision=value.get("revision") or 0,
            status=value.get("status") or "active",
            summary=value.get("summary"),
            last_message_id=value.get("last_message_id"),
            related_event_refs=tuple(value.get("related_event_refs") or ()),
            related_analysis_ids=tuple(value.get("related_analysis_ids") or ()),
            pending_command_ids=tuple(value.get("pending_command_ids") or ()),
            schema_version=value.get("schema_version") or 0,
        )
