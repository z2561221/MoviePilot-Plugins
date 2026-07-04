"""工具中心配置默认值与合并逻辑。"""

from typing import Any, Dict

from ..modules import CheckMissingModule, LibraryCleanupModule, TmdbCacheModule


def build_default_config(plugin) -> Dict[str, Any]:
    """构建工具中心完整默认配置。"""
    return {
        "enabled": False,
        "migration_done": False,
        "tmdb_cache": TmdbCacheModule(plugin).get_default_config(),
        "check_missing": CheckMissingModule(plugin).get_default_config(),
        "library_cleanup": LibraryCleanupModule(plugin).get_default_config(),
    }


def merge_config(plugin, config: Dict[str, Any] | None) -> Dict[str, Any]:
    """将用户配置合并到默认配置。"""
    merged = build_default_config(plugin)
    for key, value in (config or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged

