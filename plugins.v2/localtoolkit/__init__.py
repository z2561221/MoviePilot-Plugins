from typing import Any, Dict, List
from app.plugins import _PluginBase
from app.log import logger
from app.schemas.types import NotificationType
from .modules import TmdbCacheModule, CheckMissingModule, LibraryCleanupModule

class LocalToolkit(_PluginBase):
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
        self._config = self.__merge_default(config or {})
        self._enabled = bool(self._config.get('enabled', False))
        self.tmdb_cache = TmdbCacheModule(self); self.tmdb_cache.load_config(self._config.get('tmdb_cache', {}))
        self.check_missing = CheckMissingModule(self); self.check_missing.load_config(self._config.get('check_missing', {}))
        self.library_cleanup = LibraryCleanupModule(self); self.library_cleanup.load_config(self._config.get('library_cleanup', {}))
        if config is None or not config.get('migration_done'):
            self.__migrate_old_configs()

    def __merge_default(self, config):
        d = self.__default_config()
        for k,v in (config or {}).items():
            if isinstance(v, dict) and isinstance(d.get(k), dict): d[k].update(v)
            else: d[k]=v
        return d

    def __default_config(self):
        return {
            'enabled': False, 'migration_done': False,
            'tmdb_cache': TmdbCacheModule(self).get_default_config(),
            'check_missing': CheckMissingModule(self).get_default_config(),
            'library_cleanup': LibraryCleanupModule(self).get_default_config(),
        }

    def __migrate_old_configs(self):
        try:
            from app.core.plugin import PluginManager
            pm=PluginManager()
            mapping={'ClearTmdbCache':'tmdb_cache','CheckMissing':'check_missing','LibraryCleanup':'library_cleanup'}
            changed=False
            for pid,key in mapping.items():
                old=pm.get_plugin_config(pid) or {}
                if old:
                    self._config[key].update({k:v for k,v in old.items() if k in self._config[key]})
                    changed=True
            self._config['migration_done']=True
            self.update_config(self._config)
            if changed:
                logger.info('本地工具集：已导入旧插件配置')
        except Exception as e:
            logger.warning(f'本地工具集：旧配置迁移失败：{e}')

    def get_state(self): return self._enabled
    def get_render_mode(self): return 'vue', 'dist/assets'
    def get_service(self):
        # 只有清库存允许周期运行；查漏集和清 TMDB 缓存始终按需单次运行。
        if not self._enabled:
            return []
        return self.library_cleanup.get_service()
    def get_api(self):
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
        return [{"component":"VForm","content":[
            {"component":"VAlert","props":{"type":"info","variant":"tonal","text":"本地工具中心整合清库存、查漏集、清 TMDB 缓存。配置页建议使用 Vue 页面，旧表单仅保底。"}},
            {"component":"VSwitch","props":{"model":"enabled","label":"启用本地工具中心"}}
        ]}], self._config

    def get_page(self):
        return []

    def stop_service(self):
        pass
