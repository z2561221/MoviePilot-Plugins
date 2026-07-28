"""Telegram 待确认交互会话模型。"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping


@dataclass
class TelegramPendingSession:
    """保存一次不可猜令牌约束的 Telegram 待确认交互。"""

    token: str
    profile_id: str
    username: str
    telegram_userid: str
    item_type: str
    item_id: str
    actor_id: str
    title: str
    summary: str
    option_ids: List[str] = field(default_factory=list)
    requires_superuser: bool = False
    detail_link: str = ""
    status: str = "open"
    created_at: str = ""
    expires_at: str = ""

    def __post_init__(self) -> None:
        """规范化会话身份和有限选项。"""
        for field_name, limit in (
            ("token", 64),
            ("profile_id", 240),
            ("username", 128),
            ("telegram_userid", 128),
            ("item_type", 24),
            ("item_id", 160),
            ("actor_id", 128),
            ("title", 80),
            ("summary", 240),
            ("detail_link", 500),
            ("status", 32),
            ("created_at", 64),
            ("expires_at", 64),
        ):
            value = " ".join(str(getattr(self, field_name) or "").split()).strip()
            setattr(self, field_name, value[:limit])
        self.option_ids = list(
            dict.fromkeys(
                str(item or "").strip()[:64]
                for item in self.option_ids or []
                if str(item or "").strip()
            )
        )[:3]
        self.requires_superuser = bool(self.requires_superuser)
        if self.item_type not in {"proposal", "question", "command"}:
            raise ValueError("telegram pending item_type is invalid")
        if not all(
            (
                self.token,
                self.profile_id,
                self.username,
                self.telegram_userid,
                self.item_id,
                self.title,
                self.summary,
                self.created_at,
                self.expires_at,
            )
        ):
            raise ValueError("telegram pending identity is incomplete")

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化会话字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TelegramPendingSession":
        """从持久化字典恢复待确认会话。"""
        if not isinstance(value, Mapping):
            raise ValueError("telegram pending session must be a mapping")
        return cls(
            token=value.get("token"),
            profile_id=value.get("profile_id"),
            username=value.get("username"),
            telegram_userid=value.get("telegram_userid"),
            item_type=value.get("item_type"),
            item_id=value.get("item_id"),
            actor_id=value.get("actor_id"),
            title=value.get("title"),
            summary=value.get("summary"),
            option_ids=list(value.get("option_ids") or ()),
            requires_superuser=value.get("requires_superuser") is True,
            detail_link=value.get("detail_link"),
            status=value.get("status") or "open",
            created_at=value.get("created_at"),
            expires_at=value.get("expires_at"),
        )

    def is_expired(self, now: datetime = None) -> bool:
        """判断会话是否已经超过有效期。"""
        try:
            expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return True
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current >= expires
