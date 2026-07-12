"""Agent榜单中心 API 控制器。"""

from typing import Any, Dict, List

from ..model.config import default_config


def build_api_routes(plugin: Any) -> List[Dict[str, Any]]:
    """构建前端使用的 bearer API 路由。"""
    return [
        {
            "path": "/status",
            "endpoint": plugin.api_status,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "获取Agent榜单中心状态",
        },
        {
            "path": "/config",
            "endpoint": plugin.api_config,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "获取Agent榜单中心配置",
        },
    ]


def status_response(plugin: Any) -> Dict[str, Any]:
    """返回骨架阶段的运行状态响应。"""
    return {
        "success": True,
        "data": {
            "enabled": bool(plugin.get_state()),
            "state": "idle",
            "plugin_version": plugin.plugin_version,
            "message": "Agent榜单中心骨架已就绪",
        },
    }


def config_response(plugin: Any) -> Dict[str, Any]:
    """返回当前配置与默认配置响应。"""
    return {
        "success": True,
        "data": {
            "config": dict(plugin._config or default_config()),
            "defaults": default_config(),
        },
    }
