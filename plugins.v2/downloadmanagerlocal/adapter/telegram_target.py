"""MoviePilot 管理员 Telegram 通知目标适配器。"""

from __future__ import annotations

from typing import Any, Callable


def resolve_admin_telegram_userid(
    user_oper_factory: Callable[[], Any] | None = None,
    username: str = "",
) -> str:
    """从 MoviePilot 用户通知设置读取管理员 Telegram 用户 ID。"""
    if user_oper_factory is None:
        from app.core.config import settings
        from app.db.user_oper import UserOper

        user_oper_factory = UserOper
        username = username or settings.SUPERUSER
    try:
        targets = user_oper_factory().get_settings(str(username or "").strip())
    except Exception:
        return ""
    if not isinstance(targets, dict):
        return ""
    return str(targets.get("telegram_userid") or "").strip()


__all__ = ("resolve_admin_telegram_userid",)
