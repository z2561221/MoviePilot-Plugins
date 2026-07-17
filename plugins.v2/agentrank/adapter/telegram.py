"""MoviePilot Telegram 用户目标解析适配器。"""

from typing import Optional


class TelegramTargetAdapter:
    """从 MoviePilot 用户设置解析 Telegram 用户 ID。"""

    @staticmethod
    def resolve_userid(username: str) -> Optional[str]:
        """返回指定 MoviePilot 用户绑定的 Telegram 用户 ID。"""
        from app.db.user_oper import UserOper

        settings = UserOper().get_settings(str(username or "").strip())
        if not isinstance(settings, dict):
            return None
        userid = str(settings.get("telegram_userid") or "").strip()
        return userid or None
