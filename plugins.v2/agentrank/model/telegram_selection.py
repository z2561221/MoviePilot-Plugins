"""Telegram 榜单选择会话领域对象。"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping


@dataclass
class TelegramSelectionSession:
    """保存一次 Telegram 海报轮播中的待订阅选择。"""

    token: str
    username: str
    telegram_userid: str
    run_id: str
    candidate_ids: List[str]
    selected_ids: List[str] = field(default_factory=list)
    current_index: int = 0
    view: str = "carousel"
    status: str = "open"
    created_at: str = ""
    expires_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TelegramSelectionSession":
        """从持久化字典恢复并校验选择会话。"""
        if not isinstance(value, Mapping):
            raise ValueError("telegram selection session must be a mapping")
        token = str(value.get("token") or "").strip()
        username = str(value.get("username") or "").strip()
        telegram_userid = str(value.get("telegram_userid") or "").strip()
        run_id = str(value.get("run_id") or "").strip()
        candidate_ids = [
            str(item).strip()
            for item in value.get("candidate_ids") or []
            if str(item).strip()
        ]
        if not token or not username or not telegram_userid or not run_id:
            raise ValueError("telegram selection identity is incomplete")
        if not candidate_ids:
            raise ValueError("telegram selection candidates are required")
        selected = [
            str(item).strip()
            for item in value.get("selected_ids") or []
            if str(item).strip() in candidate_ids
        ]
        return cls(
            token=token,
            username=username,
            telegram_userid=telegram_userid,
            run_id=run_id,
            candidate_ids=candidate_ids,
            selected_ids=list(dict.fromkeys(selected)),
            current_index=max(
                0,
                min(int(value.get("current_index") or 0), len(candidate_ids) - 1),
            ),
            view=(
                str(value.get("view") or "carousel")
                if str(value.get("view") or "carousel") in {"carousel", "selected"}
                else "carousel"
            ),
            status=str(value.get("status") or "open"),
            created_at=str(value.get("created_at") or ""),
            expires_at=str(value.get("expires_at") or ""),
        )

    def is_expired(self, now: datetime = None) -> bool:
        """判断会话是否已超过有效期。"""
        if not self.expires_at:
            return True
        try:
            expires = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return True
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current >= expires
