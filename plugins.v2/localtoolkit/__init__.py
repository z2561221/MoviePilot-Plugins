from typing import Any, Dict, List
from app.plugins import _PluginBase
from app.schemas.types import NotificationType
from .controller.api import (
    build_api_routes,
    history_response,
    invalidate_cache_response,
    options_response,
    run_module,
    status_response,
)
from .service.lifecycle import build_services, initialize_plugin, stop_plugin_service

class LocalToolkit(_PluginBase):
    """工具中心插件入口，负责声明 MoviePilot 契约并委托服务层执行。"""

    plugin_name = "工具中心"
    plugin_display_name = "工具中心"
    plugin_desc = "整合清理库存、扫描缺集、清理TMDB的本地维护工具中心。"
    plugin_icon = "Ittools_A.png"
    plugin_color = "#26A69A"
    plugin_version = "1.2.10"
    plugin_author = "牧濑红莉栖"
    author_url = "https://github.com/z2561221"
    plugin_config_prefix = "localtoolkit_"
    plugin_order = 52
    auth_level = 1

    _enabled = False
    _config: Dict[str, Any] = {}

    def init_plugin(self, config: dict = None):
        """初始化插件配置与运行状态。"""
        initialize_plugin(self, config)

    def get_state(self):
        """返回工具中心启用状态。"""
        return self._enabled

    def get_render_mode(self):
        """声明工具中心使用 Vue 联邦组件渲染。"""
        return 'vue', 'dist/assets'

    def get_service(self):
        """返回工具中心后台服务列表。"""
        return build_services(self)

    def get_api(self):
        """返回工具中心 API 路由声明。"""
        return build_api_routes(self)

    def api_status(self):
        """返回工具中心状态。"""
        return status_response(self)

    def api_run(self, module: str):
        """运行指定工具模块。"""
        return run_module(self, module)

    def api_history(self, page: Any = 1, page_size: Any = 15):
        """返回工具中心历史记录。"""
        return history_response(self, page, page_size)

    def api_options(self):
        """返回工具中心配置选项。"""
        return options_response(self)

    def api_invalidate_cache(self):
        """清除选项缓存"""
        return invalidate_cache_response(self)

    def get_form(self):
        """返回 Vue 模式下的兜底配置表单。"""
        return [{"component":"VForm","content":[
            {"component":"VAlert","props":{"type":"info","variant":"tonal","text":"本地工具中心整合清库存、查漏集、清 TMDB 缓存。配置页建议使用 Vue 页面，旧表单仅保底。"}},
            {"component":"VSwitch","props":{"model":"enabled","label":"启用本地工具中心"}}
        ]}], self._config

    def get_page(self):
        """返回 Vue 模式下的详情页占位 schema。"""
        return []

    def stop_service(self):
        """停止工具中心后台服务。"""
        stop_plugin_service(self)
