"""Agent榜单中心生命周期服务。"""

from typing import Any

from ..model.config import normalize_config


def initialize_plugin(plugin: Any, config: dict = None) -> None:
    """初始化插件状态并保存规范化配置快照。"""
    plugin.stop_service()
    plugin._config = normalize_config(config)
    plugin._enabled = bool(plugin._config.get("enabled"))
