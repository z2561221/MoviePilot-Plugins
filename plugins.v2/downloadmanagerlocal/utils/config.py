"""配置清洗工具"""


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


def is_plugin_active(plugin) -> bool:
    """判断插件是否至少有一个主要能力处于可运行状态。"""
    return is_transfer_active(plugin) or is_iyuu_active(plugin)
