from typing import Any, Dict, List
from app.plugins import _PluginBase
from app.log import logger
from app.schemas.types import NotificationType
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
        return [
            {'path':'/local_toolkit/status','endpoint':self.api_status,'auth':'bear','methods':['GET'],'summary':'本地工具中心状态'},
            {'path':'/local_toolkit/run/{module}','endpoint':self.api_run,'auth':'bear','methods':['POST'],'summary':'运行本地工具模块'},
            {'path':'/local_toolkit/history','endpoint':self.api_history,'auth':'bear','methods':['GET'],'summary':'本地工具中心历史'},
            {'path':'/local_toolkit/options','endpoint':self.api_options,'auth':'bear','methods':['GET'],'summary':'本地工具中心配置选项'},
            {'path':'/local_toolkit/invalidate_cache','endpoint':self.api_invalidate_cache,'auth':'bear','methods':['POST'],'summary':'清除选项缓存'},
        ]
    def __modules(self):
        return {'tmdb_cache':self.tmdb_cache,'check_missing':self.check_missing,'library_cleanup':self.library_cleanup}

    @staticmethod
    def __safe_int(value, default, min_value=None, max_value=None):
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = default
        if min_value is not None and value < min_value:
            value = default
        if max_value is not None and value > max_value:
            value = max_value
        return value

    def __safe_status(self, key, module):
        try:
            status = module.get_status()
            return status if isinstance(status, dict) else {'success': True, 'value': status}
        except Exception as e:
            name = getattr(module, 'module_name', key)
            logger.error(f'本地工具集：获取{name}状态失败：{e}')
            return {'success': False, 'module_name': name, 'error': str(e)}

    def api_status(self):
        return {'enabled':self._enabled,'modules':{key:self.__safe_status(key, module) for key,module in self.__modules().items()}}
    def api_run(self, module: str):
        module = str(module or '').strip()
        m = self.__modules().get(module)
        if not m: return {'success':False,'message':f'未知模块：{module or "empty"}'}
        try:
            result = m.run_once()
            return result if isinstance(result, dict) else {'success': True, 'result': result}
        except Exception as e:
            name = getattr(m, 'module_name', module)
            logger.error(f'本地工具集：运行{name}失败：{e}')
            try:
                if hasattr(m, 'add_history'):
                    m.add_history('failed', f'运行异常：{e}', 0)
            except Exception as history_error:
                logger.warning(f'本地工具集：记录{name}失败历史失败：{history_error}')
            return {'success':False,'message':f'{name}运行失败：{e}'}
    def api_history(self, page: Any = 1, page_size: Any = 15):
        page = self.__safe_int(page, 1, min_value=1)
        page_size = self.__safe_int(page_size, 15, min_value=1, max_value=100)
        all_data = self.get_data(key='tool_history') or []
        if not isinstance(all_data, list):
            logger.warning('本地工具集：历史记录格式异常，已忽略')
            all_data = []
        total = len(all_data)
        total_pages = max(1, -(-total // page_size))
        if page > total_pages:
            page = total_pages
        start = (page - 1) * page_size
        end = start + page_size
        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'items': all_data[start:end]
        }
    def api_options(self):
        return {
            'success': True,
            'library_cleanup': self.library_cleanup.get_options()
        }

    def api_invalidate_cache(self):
        """清除选项缓存"""
        self.library_cleanup.invalidate_options_cache()
        return {'success': True, 'message': '缓存已清除'}

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
