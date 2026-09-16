"""Telegram 榜单运行重试会话。"""

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class TelegramRetrySession:
    """绑定异常通知的画像、接收人和一次性重试状态。"""

    token: str
    profile_id: str
    username: str
    telegram_userid: str
    run_id: str
    message: str
    created_at: str
    expires_at: str
    status: str = "open"
    message_id: str = ""
    chat_id: str = ""
    source: str = ""
    attempt: int = 0

    def __post_init__(self) -> None:
        """拒绝缺失身份、非法令牌和未知状态。"""
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,32}", self.token):
            raise ValueError("invalid telegram retry token")
        if not all((self.profile_id, self.username, self.telegram_userid)):
            raise ValueError("telegram retry identity is incomplete")
        if self.status not in {"open", "submitted", "completed", "expired", "stale"}:
            raise ValueError("invalid telegram retry status")
        if self.attempt < 0:
            raise ValueError("invalid telegram retry attempt")

    def to_dict(self) -> dict[str, Any]:
        """返回插件数据接口可保存的会话。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TelegramRetrySession":
        """从持久化数据恢复并校验会话。"""
        if not isinstance(value, Mapping):
            raise TypeError("telegram retry session must be a mapping")
        return cls(
            **{
                name: str(value.get(name) or "").strip()
                for name in (
                    "token",
                    "profile_id",
                    "username",
                    "telegram_userid",
                    "run_id",
                    "message",
                    "created_at",
                    "expires_at",
                    "message_id",
                    "chat_id",
                    "source",
                )
            },
            status=str(value.get("status") or "open"),
            attempt=int(value.get("attempt") or 0),
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        """将缺失或损坏的有效期视为过期。"""
        try:
            expires = datetime.fromisoformat(self.expires_at)
        except (TypeError, ValueError):
            return True
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current >= expires
