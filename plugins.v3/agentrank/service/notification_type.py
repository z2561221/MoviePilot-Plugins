"""MoviePilot 通知类型解析与配置选项。"""

from typing import Any, Dict, List, Mapping


FALLBACK_OPTIONS = (
    ("Download", "资源下载"),
    ("Organize", "整理入库"),
    ("Subscribe", "订阅"),
    ("SiteMessage", "站点"),
    ("MediaServer", "媒体服务器"),
    ("Manual", "手动处理"),
    ("Plugin", "插件"),
    ("Agent", "智能体"),
    ("Other", "其它"),
)


def resolve_notification_type(
    config: Mapping[str, Any] = None, notification_type_enum: Any = None
) -> Any:
    """从配置解析通知类型，无效或宿主缺项时安全回退插件类型。"""
    if notification_type_enum is None:
        from app.schemas.types import MessageType as notification_type_enum

    name = str((config or {}).get("notification_type") or "Plugin").strip()
    fallback = getattr(
        notification_type_enum, "Plugin", notification_type_enum.Subscribe
    )
    return getattr(notification_type_enum, name, fallback)


def notification_type_options(notification_type_enum: Any = None) -> List[Dict[str, str]]:
    """动态返回当前 MoviePilot 宿主提供的全部通知类型选项。"""
    try:
        if notification_type_enum is None:
            from app.schemas.types import MessageType as notification_type_enum

        values = tuple(
            (str(item.name), str(item.value)) for item in notification_type_enum
        )
    except (ImportError, TypeError):
        values = FALLBACK_OPTIONS
    return [{"title": title, "value": name} for name, title in values]
