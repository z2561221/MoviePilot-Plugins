"""AgentRank Telegram 交互目标适配器。"""

from typing import Any, Callable, Mapping, Optional


class TelegramTargetAdapter:
    """按 MoviePilot 用户设置解析 Telegram 交互目标。"""

    def __init__(
        self,
        user_oper_factory: Optional[Callable[[], Any]] = None,
        superuser: str = "",
    ):
        """绑定宿主用户设置读取器，并允许测试注入替身。"""
        if user_oper_factory is None:
            from app.core.config import settings
            from app.db.user_oper import UserOper

            user_oper_factory = UserOper
            superuser = superuser or settings.SUPERUSER
        self._user_oper_factory = user_oper_factory
        self._superuser = str(superuser or "").strip()

    @staticmethod
    def _telegram_userid(targets: Any) -> Optional[str]:
        """从 MoviePilot 用户通知设置中提取 Telegram 用户 ID。"""
        if not isinstance(targets, Mapping):
            return None
        userid = str(targets.get("telegram_userid") or "").strip()
        return userid or None

    def resolve_userid(self, username: str) -> Optional[str]:
        """解析目标用户；用户不存在时按宿主规则回退超级管理员。"""
        target_name = str(username or "").strip()
        user_oper = self._user_oper_factory()
        targets = user_oper.get_settings(target_name) if target_name else None
        if targets is not None:
            return self._telegram_userid(targets)
        if not self._superuser or self._superuser == target_name:
            return None
        return self._telegram_userid(user_oper.get_settings(self._superuser))
