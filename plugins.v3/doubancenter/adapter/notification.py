"""读取宿主通知路由与管理员个人 Telegram 绑定，不连接通知客户端。"""

import re
from urllib.parse import quote


def destinations(message_type) -> list[dict]:
    """显式尊重渠道启用及分类开关，再按来源发送以免 Telegram 双发。"""
    from app.sdk.services import ServiceConfigHelper

    configs = ServiceConfigHelper.get_notification_configs() or []
    return list({
        config.name: {"id": str(getattr(config, "id", "") or ""), "name": config.name, "type": config.type.lower()}
        for config in configs
        if config.enabled and config.name and config.type and message_type.value in (config.switchs or [])
    }.values())


def telegram_userid() -> str:
    """使用公开 UserOper 合同读取管理员绑定，群聊 ID 不能充当操作人。"""
    from app.db.oper.user import UserOper
    from app.sdk.config import settings

    user = UserOper().get_by_name(settings.SUPERUSER)
    if not user or not user.is_active or not user.is_superuser:
        return ""
    targets = user.settings
    value = str((targets if isinstance(targets, dict) else {}).get("telegram_userid") or "").strip()
    return value if re.fullmatch(r"[1-9][0-9]{0,19}", value) else ""


def detail_link(plugin) -> str:
    """复用宿主的登录态插件页面，不把 API 凭据放进通知链接。"""
    from app.sdk.config import settings

    plugin_id = quote(plugin.__class__.__name__, safe="")
    return settings.MP_DOMAIN(f"#/plugins?tab=installed&id={plugin_id}") or ""
