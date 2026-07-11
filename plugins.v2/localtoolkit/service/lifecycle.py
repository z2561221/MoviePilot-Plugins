"""工具中心生命周期与旧配置迁移服务。"""

from app.log import logger

from ..model.config import merge_config
from ..security import redact_sensitive_text
from .check_missing import CheckMissingModule
from .library_cleanup import LibraryCleanupModule
from .tmdb_cache import TmdbCacheModule


def initialize_plugin(plugin, config: dict | None = None) -> None:
    """初始化工具中心插件运行状态与模块实例。"""
    plugin._config = merge_config(plugin, config or {})
    plugin._enabled = bool(plugin._config.get("enabled", False))
    plugin.tmdb_cache = TmdbCacheModule(plugin)
    plugin.tmdb_cache.load_config(plugin._config.get("tmdb_cache", {}))
    plugin.check_missing = CheckMissingModule(plugin)
    plugin.check_missing.load_config(plugin._config.get("check_missing", {}))
    plugin.library_cleanup = LibraryCleanupModule(plugin)
    plugin.library_cleanup.load_config(plugin._config.get("library_cleanup", {}))
    if config is None or not config.get("migration_done"):
        migrate_old_configs(plugin)


def migrate_old_configs(plugin) -> None:
    """从旧独立插件配置迁移到工具中心配置。"""
    try:
        from app.core.plugin import PluginManager

        plugin_manager = PluginManager()
        mapping = {
            "ClearTmdbCache": "tmdb_cache",
            "CheckMissing": "check_missing",
            "LibraryCleanup": "library_cleanup",
        }
        changed = False
        for plugin_id, key in mapping.items():
            old_config = plugin_manager.get_plugin_config(plugin_id) or {}
            if old_config:
                plugin._config[key].update(
                    item
                    for item in old_config.items()
                    if item[0] in plugin._config[key]
                )
                changed = True
        plugin._config["migration_done"] = True
        plugin.update_config(plugin._config)
        if changed:
            logger.info("本地工具集：已导入旧插件配置")
    except Exception as err:
        logger.warning(f"本地工具集：旧配置迁移失败：{redact_sensitive_text(err)}")


def build_services(plugin) -> list:
    """返回工具中心需要注册的后台服务。"""
    if not plugin._enabled:
        return []
    return plugin.library_cleanup.get_service()


def stop_plugin_service(plugin) -> None:
    """停止工具中心后台服务。"""
    return None
