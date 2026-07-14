"""Agent榜单中心插件入口。"""

from typing import Any, Dict, List, Optional, Tuple, Type

from app.plugins import _PluginBase

from .controller.api import build_api_routes, config_response, status_response
from .model.config import default_config
from .service.lifecycle import build_services, initialize_plugin, stop_plugin


class AgentRank(_PluginBase):
    """根据用户订阅与发现候选生成 Agent 个性化榜单。"""

    plugin_name = "Agent榜单中心"
    plugin_desc = "调用内置Agent，从MoviePilot发现候选中生成个性化Top10榜单。"
    plugin_icon = "agentresourceofficer.png"
    plugin_color = "#7C4DFF"
    plugin_version = "1.0.0"
    plugin_label = "智能推荐"
    plugin_author = "牧濑红莉栖"
    author_url = "https://github.com/z2561221"
    plugin_config_prefix = "agentrank_"
    plugin_order = 30
    auth_level = 1

    _enabled = False
    _config: Dict[str, Any] = {}
    _runtime: Any = None
    _repository: Any = None

    def init_plugin(self, config: dict = None) -> None:
        """初始化插件配置与运行状态。"""
        initialize_plugin(self, config)

    def get_state(self) -> bool:
        """返回插件启用状态。"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """返回插件命令列表。"""
        return []

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明插件使用 Vue 联邦组件渲染。"""
        return "vue", "dist/assets"

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        """返回主界面发现分区的全页入口。"""
        if not self.get_state() or not self._config.get("discovery_page_enabled", True):
            return []
        return [
            {
                "nav_key": "main",
                "title": "Agent榜单中心",
                "icon": "mdi-brain",
                "section": "discovery",
                "permission": "discovery",
                "order": 30,
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        """返回插件 API 路由。"""
        return build_api_routes(self)

    def api_status(self) -> Dict[str, Any]:
        """返回插件骨架运行状态。"""
        return status_response(self)

    def api_config(self) -> Dict[str, Any]:
        """返回插件当前配置与默认配置。"""
        return config_response(self)

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """返回 Vue 配置组件使用的初始模型。"""
        return [], dict(self._config or default_config())

    def get_page(self) -> List[dict]:
        """返回 Vue 详情组件占位页面。"""
        return []

    def get_dashboard_meta(self) -> Optional[List[Dict[str, str]]]:
        """返回插件仪表板元信息。"""
        return [{"key": "main", "name": "推荐榜单"}]

    def get_dashboard(
        self, key: str = "main", **kwargs: Any
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], None]]:
        """返回 Vue 仪表板布局声明。"""
        return (
            {"cols": 12, "md": 6},
            {
                "title": "Agent榜单中心",
                "subtitle": "个性化推荐 Top 5",
                "refresh": 0,
                "border": False,
            },
            None,
        )

    def get_service(self) -> List[Dict[str, Any]]:
        """返回后台服务列表。"""
        return build_services(self)

    @staticmethod
    def get_agent_tools() -> List[Type]:
        """返回插件提供的 Agent 工具列表。"""
        from .agent_tools.registry import AGENT_TOOL_CLASSES

        return list(AGENT_TOOL_CLASSES)

    def stop_service(self) -> None:
        """停止插件后台服务。"""
        stop_plugin(self)
