"""Agent榜单中心配置模型。"""

from typing import Any, Dict


def default_config() -> Dict[str, Any]:
    """返回插件骨架的默认配置。"""
    return {
        "enabled": False,
        "schedule_enabled": False,
        "cron": "0 8 * * *",
        "users": [],
        "default_user": "",
        "notify": True,
        "action_mode": "notify",
        "auto_subscribe_top_n": 0,
    }


def normalize_config(config: dict = None) -> Dict[str, Any]:
    """合并并清洗插件配置。"""
    normalized = default_config()
    if isinstance(config, dict):
        normalized.update(config)
    normalized["enabled"] = bool(normalized.get("enabled"))
    normalized["schedule_enabled"] = bool(normalized.get("schedule_enabled"))
    normalized["notify"] = bool(normalized.get("notify"))
    normalized["users"] = list(normalized.get("users") or [])
    normalized["default_user"] = str(normalized.get("default_user") or "")
    normalized["cron"] = str(normalized.get("cron") or default_config()["cron"])
    normalized["action_mode"] = str(normalized.get("action_mode") or "notify")
    normalized["auto_subscribe_top_n"] = max(
        0, int(normalized.get("auto_subscribe_top_n") or 0)
    )
    return normalized
