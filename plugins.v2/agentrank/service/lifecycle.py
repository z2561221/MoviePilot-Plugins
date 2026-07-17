"""Agent榜单中心插件生命周期服务。"""

from typing import Any, Callable, Dict, List

from ..model.config import normalize_config
from .runtime import AgentRankRuntime


def stop_plugin(plugin: Any) -> None:
    """幂等停止并移除当前运行时。"""
    runtime = getattr(plugin, "_runtime", None)
    if runtime is not None and hasattr(runtime, "stop"):
        runtime.stop()
    plugin._runtime = None


def initialize_plugin(
    plugin: Any,
    config: dict = None,
    runtime_factory: Callable[[Any, Dict[str, Any]], Any] = AgentRankRuntime,
) -> None:
    """停止旧运行时、规范化配置并组装新运行时。"""
    plugin.stop_service()
    normalized = normalize_config(config)
    runtime_config = dict(normalized)
    plugin._config = dict(normalized)
    plugin._enabled = bool(plugin._config.get("enabled"))
    plugin._runtime = runtime_factory(plugin, runtime_config)
    if plugin._config.get("onlyonce"):
        plugin._config["onlyonce"] = False
        persisted = {
            key: value
            for key, value in plugin._config.items()
            if key != "_validation_errors"
        }
        plugin.update_config(config=persisted)


def build_services(plugin: Any) -> List[Dict[str, Any]]:
    """返回当前运行时声明的宿主周期服务。"""
    runtime = getattr(plugin, "_runtime", None)
    if runtime is None:
        return []
    return runtime.get_services()
