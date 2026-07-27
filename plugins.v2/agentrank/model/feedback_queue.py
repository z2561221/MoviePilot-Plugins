"""反馈理解异步队列的持久任务模型。"""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from .feedback import FeedbackEvent


FEEDBACK_QUEUE_SCHEMA_VERSION = 1
FEEDBACK_QUEUE_STATUSES = frozenset(
    {"queued", "running", "retry_wait", "completed", "needs_attention"}
)
FEEDBACK_QUEUE_TERMINAL_STATUSES = frozenset({"completed", "needs_attention"})


def _text(value: Any) -> str:
    """把可选标量规范为去除首尾空白的文本。"""
    return str(value or "").strip()


def _utc_now() -> datetime:
    """返回带时区的当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _iso(value: Optional[datetime] = None) -> str:
    """把时间规范为 UTC ISO 文本。"""
    current = value or _utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str) -> Optional[datetime]:
    """容错解析 ISO 时间，缺失时返回空值。"""
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class FeedbackQueueJob:
    """引用一条反馈事实并记录可恢复的后台处理状态。"""

    job_id: str
    profile_id: str
    event_id: str
    event_sequence: int
    status: str = "queued"
    attempts: int = 0
    max_attempts: int = 3
    created_at: str = ""
    updated_at: str = ""
    next_attempt_at: str = ""
    lease_id: str = ""
    last_error: str = ""
    schema_version: int = FEEDBACK_QUEUE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范字段并拒绝不可恢复或跨契约的任务状态。"""
        for field_name in (
            "job_id",
            "profile_id",
            "event_id",
            "status",
            "created_at",
            "updated_at",
            "next_attempt_at",
            "lease_id",
            "last_error",
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name)))
        object.__setattr__(self, "event_sequence", int(self.event_sequence))
        object.__setattr__(self, "attempts", int(self.attempts))
        object.__setattr__(self, "max_attempts", int(self.max_attempts))
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not self.job_id or not self.profile_id or not self.event_id:
            raise ValueError("feedback queue job identity is incomplete")
        if self.event_sequence <= 0:
            raise ValueError("feedback queue event_sequence must be positive")
        if self.status not in FEEDBACK_QUEUE_STATUSES:
            raise ValueError("feedback queue status is unsupported")
        if self.attempts < 0 or self.max_attempts <= 0:
            raise ValueError("feedback queue attempt counters are invalid")
        if self.attempts > self.max_attempts:
            raise ValueError("feedback queue attempts exceed max_attempts")
        if not self.created_at or not self.updated_at:
            raise ValueError("feedback queue timestamps are required")
        if _parse_iso(self.created_at) is None or _parse_iso(self.updated_at) is None:
            raise ValueError("feedback queue timestamps are invalid")
        if self.status == "running" and not self.lease_id:
            raise ValueError("running feedback queue job requires a lease")
        if self.status != "running" and self.lease_id:
            raise ValueError("non-running feedback queue job cannot retain a lease")
        if self.status == "retry_wait" and _parse_iso(self.next_attempt_at) is None:
            raise ValueError("retrying feedback queue job requires next_attempt_at")
        if self.schema_version != FEEDBACK_QUEUE_SCHEMA_VERSION:
            raise ValueError("feedback queue schema_version is unsupported")

    @property
    def terminal(self) -> bool:
        """返回任务是否已经进入终态。"""
        return self.status in FEEDBACK_QUEUE_TERMINAL_STATUSES

    def ready(self, now: Optional[datetime] = None) -> bool:
        """返回排队或退避任务在指定时刻是否可以认领。"""
        if self.status == "queued":
            return True
        if self.status != "retry_wait":
            return False
        target = _parse_iso(self.next_attempt_at)
        current = now or _utc_now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return bool(target and target <= current.astimezone(timezone.utc))

    @classmethod
    def from_event(
        cls, event: FeedbackEvent, *, max_attempts: int = 3
    ) -> "FeedbackQueueJob":
        """从已持久化反馈事实创建确定性且可幂等入队的任务。"""
        if not isinstance(event, FeedbackEvent) or not event.is_persisted:
            raise ValueError("feedback queue requires a persisted feedback event")
        now = _iso()
        return cls(
            job_id=f"feedback:{event.event_id}",
            profile_id=event.profile_id,
            event_id=event.event_id,
            event_sequence=event.sequence,
            max_attempts=max(1, min(int(max_attempts), 20)),
            created_at=now,
            updated_at=now,
        )

    def claim(self, lease_id: str, now: Optional[datetime] = None) -> "FeedbackQueueJob":
        """认领一个就绪任务并递增本次处理尝试次数。"""
        lease = _text(lease_id)
        if not lease or not self.ready(now):
            raise ValueError("feedback queue job is not claimable")
        return replace(
            self,
            status="running",
            attempts=self.attempts + 1,
            updated_at=_iso(now),
            next_attempt_at="",
            lease_id=lease,
            last_error="",
        )

    def recover(self, now: Optional[datetime] = None) -> "FeedbackQueueJob":
        """把进程中断遗留的运行任务恢复为可重新认领状态。"""
        if self.status != "running":
            return self
        return replace(
            self,
            status="queued",
            updated_at=_iso(now),
            next_attempt_at="",
            lease_id="",
        )

    def complete(self, now: Optional[datetime] = None) -> "FeedbackQueueJob":
        """把当前租约持有的任务标记为完成。"""
        if self.status != "running" or not self.lease_id:
            raise ValueError("only a running feedback queue job can complete")
        return replace(
            self,
            status="completed",
            updated_at=_iso(now),
            next_attempt_at="",
            lease_id="",
            last_error="",
        )

    def retry(
        self,
        *,
        next_attempt_at: datetime,
        error: str,
        now: Optional[datetime] = None,
    ) -> "FeedbackQueueJob":
        """在尝试上限内把失败任务转入有界退避。"""
        if self.status != "running" or not self.lease_id:
            raise ValueError("only a running feedback queue job can retry")
        if self.attempts >= self.max_attempts:
            return self.needs_attention(error=error, now=now)
        return replace(
            self,
            status="retry_wait",
            updated_at=_iso(now),
            next_attempt_at=_iso(next_attempt_at),
            lease_id="",
            last_error=_text(error)[:240],
        )

    def needs_attention(
        self, *, error: str, now: Optional[datetime] = None
    ) -> "FeedbackQueueJob":
        """把达到尝试上限的任务转为可见人工关注状态。"""
        if self.status != "running" or not self.lease_id:
            raise ValueError("only a running feedback queue job can need attention")
        return replace(
            self,
            status="needs_attention",
            updated_at=_iso(now),
            next_attempt_at="",
            lease_id="",
            last_error=_text(error)[:240],
        )

    def to_public_dict(self) -> Dict[str, Any]:
        """返回前端可见且不含事件载荷的队列状态。"""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "next_attempt_at": self.next_attempt_at,
            "updated_at": self.updated_at,
        }

    def to_dict(self) -> Dict[str, Any]:
        """返回完整持久化字典。"""
        return {
            "job_id": self.job_id,
            "profile_id": self.profile_id,
            "event_id": self.event_id,
            "event_sequence": self.event_sequence,
            "status": self.status,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "next_attempt_at": self.next_attempt_at,
            "lease_id": self.lease_id,
            "last_error": self.last_error,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FeedbackQueueJob":
        """从持久化字典恢复并校验队列任务。"""
        if not isinstance(value, Mapping):
            raise ValueError("feedback queue job must be a mapping")
        return cls(
            job_id=value.get("job_id"),
            profile_id=value.get("profile_id"),
            event_id=value.get("event_id"),
            event_sequence=value.get("event_sequence") or 0,
            status=value.get("status") or "queued",
            attempts=value.get("attempts") or 0,
            max_attempts=value.get("max_attempts") or 3,
            created_at=value.get("created_at"),
            updated_at=value.get("updated_at"),
            next_attempt_at=value.get("next_attempt_at"),
            lease_id=value.get("lease_id"),
            last_error=value.get("last_error"),
            schema_version=value.get("schema_version") or 0,
        )
