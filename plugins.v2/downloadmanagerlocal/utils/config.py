"""配置清洗工具"""


SPEED_MONITOR_CONFIG_DEFAULTS = {
    "speed_monitor_enabled": False,
    "speed_monitor_downloaders": [],
    "speed_monitor_mode": "auto",
    "speed_monitor_tolerance": 1.5,
    "speed_monitor_min_samples": 5,
    "speed_monitor_interval_seconds": 30,
    "speed_monitor_grace_minutes": 10,
    "speed_monitor_consecutive_abnormal_samples": 2,
    "speed_monitor_manual_speed_bps": {},
    "speed_monitor_floor_speed_bps": {},
    "speed_monitor_notification_type": "Plugin",
}

SPEED_MONITOR_DELETE_FILE = True
SPEED_MONITOR_DELETE_WARNING = "删除种子及全部数据后不可恢复。"
SPEED_MONITOR_EXTERNAL_LINK_WARNING = "换种需要订阅助手增强版监听 MoviePilot 删除事件。"


def safe_int(value, default, min_value=None, max_value=None):
    """安全整数转换，带范围限制"""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    if min_value is not None and v < min_value:
        return min_value
    if max_value is not None and v > max_value:
        return max_value
    return v


def safe_float(value, default, min_exclusive=None):
    """安全转换浮点数，并在不满足下界时回退默认值。"""
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return default
    if min_exclusive is not None and converted <= min_exclusive:
        return default
    return converted


def _positive_speed_mapping(value) -> dict[str, float]:
    """清洗按下载器保存的正数速度映射。"""
    if not isinstance(value, dict):
        return {}
    result = {}
    for downloader, speed in value.items():
        if not isinstance(downloader, str) or not downloader.strip():
            continue
        try:
            normalized_speed = float(speed)
        except (TypeError, ValueError):
            continue
        if normalized_speed > 0:
            result[downloader.strip()] = normalized_speed
    return result


def normalize_speed_monitor_config(config: dict | None) -> dict:
    """按速度监控契约清洗配置并补齐默认值。"""
    source = config if isinstance(config, dict) else {}
    downloaders = []
    for downloader in source.get("speed_monitor_downloaders") or []:
        if (
            isinstance(downloader, str)
            and downloader.strip()
            and downloader.strip() not in downloaders
        ):
            downloaders.append(downloader.strip())

    mode = source.get("speed_monitor_mode")
    if mode not in {"auto", "manual"}:
        mode = SPEED_MONITOR_CONFIG_DEFAULTS["speed_monitor_mode"]

    notification_type = source.get("speed_monitor_notification_type")
    if not isinstance(notification_type, str) or not notification_type.strip():
        notification_type = SPEED_MONITOR_CONFIG_DEFAULTS["speed_monitor_notification_type"]

    return {
        "speed_monitor_enabled": bool(source.get("speed_monitor_enabled", False)),
        "speed_monitor_downloaders": downloaders,
        "speed_monitor_mode": mode,
        "speed_monitor_tolerance": safe_float(
            source.get("speed_monitor_tolerance"), 1.5, min_exclusive=1.0
        ),
        "speed_monitor_min_samples": safe_int(
            source.get("speed_monitor_min_samples"), 5, 1, 100
        ),
        "speed_monitor_interval_seconds": safe_int(
            source.get("speed_monitor_interval_seconds"), 30, 10, 300
        ),
        "speed_monitor_grace_minutes": safe_int(
            source.get("speed_monitor_grace_minutes"), 10, 0, 1440
        ),
        "speed_monitor_consecutive_abnormal_samples": safe_int(
            source.get("speed_monitor_consecutive_abnormal_samples"), 2, 1, 10
        ),
        "speed_monitor_manual_speed_bps": _positive_speed_mapping(
            source.get("speed_monitor_manual_speed_bps")
        ),
        "speed_monitor_floor_speed_bps": _positive_speed_mapping(
            source.get("speed_monitor_floor_speed_bps")
        ),
        "speed_monitor_notification_type": notification_type.strip(),
    }


def is_transfer_active(plugin) -> bool:
    """判断转移做种能力是否处于可运行状态。"""
    return bool(
        getattr(plugin, "_enabled", False)
        and getattr(plugin, "_transfer_enabled", False)
        and getattr(plugin, "_fromdownloader", "")
        and getattr(plugin, "_todownloader", "")
        and getattr(plugin, "_fromtorrentpath", "")
    )


def is_iyuu_active(plugin) -> bool:
    """判断 IYUU 辅种能力是否处于可运行状态。"""
    return bool(
        getattr(plugin, "_enabled", False)
        and getattr(plugin, "_iyuu_enabled", False)
        and getattr(plugin, "_iyuu_token", "")
        and getattr(plugin, "_iyuu_downloaders", [])
    )


def is_speed_monitor_active(plugin) -> bool:
    """判断下载速度异常监控是否具备稳定运行门禁。"""
    selected = getattr(plugin, "_speed_monitor_downloaders", [])
    selected_names = [
        name.strip()
        for name in selected
        if isinstance(name, str) and name.strip()
    ] if isinstance(selected, (list, tuple, set)) else []
    if getattr(plugin, "_speed_monitor_mode", "auto") == "manual":
        manual_speeds = getattr(plugin, "_speed_monitor_manual_speed_bps", {})
        if not isinstance(manual_speeds, dict) or any(
            safe_float(manual_speeds.get(name), 0.0, min_exclusive=0.0) <= 0
            for name in selected_names
        ):
            return False
    return bool(
        getattr(plugin, "_enabled", False)
        and getattr(plugin, "_speed_monitor_enabled", False)
        and selected_names
    )


def is_plugin_active(plugin) -> bool:
    """判断插件是否至少有一个主要能力处于可运行状态。"""
    return (
        is_transfer_active(plugin)
        or is_iyuu_active(plugin)
        or is_speed_monitor_active(plugin)
    )
