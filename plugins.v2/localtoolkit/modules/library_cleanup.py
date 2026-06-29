from apscheduler.triggers.cron import CronTrigger
from app.log import logger
from app.helper.mediaserver import MediaServerHelper
from .base import BaseToolModule
from pathlib import Path
import importlib.util
import sys
import time

# 全局选项缓存（5分钟过期）
_options_cache = {"data": None, "expire": 0}


class LibraryCleanupModule(BaseToolModule):
    module_key='library_cleanup'; module_name='清理库存'
    last_error = ''

    def get_default_config(self):
        return {'enabled': False, 'cron':'9 0 * * *','notify': True,'days_threshold':30,'selected_library':'','selected_server':'','selected_user':'','filter_played':'played','filter_favorite':'unfav','auto_delete':False,'auto_delete_delay':60,'dry_run':False,'auto_delete_max_count':20}
    def get_service(self):
        cron = self.config.get('cron')
        if not self.config.get('enabled') or not cron: return []
        try:
            trigger = CronTrigger.from_crontab(cron)
        except Exception as e:
            logger.warning(f'本地工具集：清库存 cron 配置无效，已跳过定时服务：{cron}，错误：{e}')
            return []
        return [{'id':'LocalToolkit.LibraryCleanup','name':'本地工具集 - 清库存','trigger':trigger,'func':self.run_once,'kwargs':{}}]
    def _delegate(self):
        self.last_error = ''
        try:
            LibraryCleanup = self._load_library_cleanup_class()
            obj=LibraryCleanup(); obj.init_plugin(self.config); return obj
        except Exception as e:
            self.last_error = str(e)
            logger.error(f'本地工具集：初始化清库存模块失败：{e}')
            return None

    def _load_library_cleanup_class(self):
        try:
            from app.plugins.librarycleanup import LibraryCleanup
            return LibraryCleanup
        except Exception as import_error:
            last_error = import_error

        for source in self._library_cleanup_source_paths():
            try:
                if not source.exists():
                    continue
                module_name = '_localtoolkit_librarycleanup_delegate'
                spec = importlib.util.spec_from_file_location(module_name, source)
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                return getattr(module, 'LibraryCleanup')
            except Exception as e:
                last_error = e
        raise last_error

    def _library_cleanup_source_paths(self):
        return [
            Path('/config/plugins/librarycleanup/__init__.py'),
            Path('/app/app/plugins/librarycleanup/__init__.py'),
            Path('/vol1/1000/docker/moviepilot-v2/config/plugins/librarycleanup/__init__.py'),
        ]

    def get_options(self):
        """返回清库存模块的媒体服务器/媒体库/用户选项，供 Vue 配置页联动。"""
        global _options_cache
        now = time.time()
        if now < _options_cache["expire"] and _options_cache["data"] is not None:
            return _options_cache["data"]

        options = {"servers": [], "libraries": [], "users": []}
        try:
            helper = MediaServerHelper()
            options["servers"] = [
                {"title": cfg.name, "value": cfg.name}
                for cfg in helper.get_configs().values()
                if getattr(cfg, "type", "") in ("emby", "jellyfin")
            ]

            selected_server = self.config.get("selected_server") or ""
            services = helper.get_services(name_filters=[selected_server]) if selected_server else helper.get_services()

            obj = self._delegate()
            for server, service in services.items():
                try:
                    if service.instance.is_inactive():
                        continue
                    if obj and hasattr(obj, "_fetch_libraries_from_service"):
                        options["libraries"].extend(obj._fetch_libraries_from_service(server, service) or [])
                    if obj and hasattr(obj, "_fetch_users_from_service"):
                        options["users"].extend(obj._fetch_users_from_service(server, service) or [])
                except Exception as e:
                    logger.warning(f"本地工具集：获取 {server} 媒体库/用户选项失败：{e}")

            # 去重，避免多个服务或重复刷新产生重复项
            for key in ("servers", "libraries", "users"):
                seen = set()
                deduped = []
                for item in options[key]:
                    value = item.get("value") if isinstance(item, dict) else item
                    if value in seen:
                        continue
                    seen.add(value)
                    deduped.append(item)
                options[key] = deduped
        except Exception as e:
            logger.error(f"本地工具集：获取清库存媒体服务器选项失败：{e}")
            options["error"] = str(e)

        _options_cache["data"] = options
        _options_cache["expire"] = now + 300
        return options

    def invalidate_options_cache(self):
        """手动清除选项缓存（用于媒体服务器配置变更后刷新）。"""
        global _options_cache
        _options_cache = {"data": None, "expire": 0}

    def run_once(self):
        import time
        start=time.time(); obj=self._delegate()
        if not obj:
            message = f'清库存模块初始化失败：{self.last_error}' if self.last_error else '清库存模块初始化失败'
            self.add_history('failed', message, 0); return {'success':False,'message':message}

        auto_delete=self.config.get('auto_delete',False)

        # 第一步：分析，不删除
        obj._auto_delete = False
        if auto_delete:
            obj._notify = False
        result=obj.run_cleanup()
        qualified=getattr(result,"qualified_count",0)

        if qualified==0:
            summary='媒体库很干净，没有需要清理的电影。'
            self.plugin.save_data(key='library_cleanup_result', value=obj.get_data(key='last_cleanup_result'))
            self.add_history('success', summary, time.time()-start)
            if auto_delete and self.config.get('notify', True):
                self.send_notification('清库存检查报告', summary)
            return {'success':True,'summary':summary}

        movies=getattr(result,'qualified_movies',[]) or []

        if auto_delete:
            try:
                auto_delete_max_count = int(self.config.get('auto_delete_max_count') or 0)
            except (TypeError, ValueError):
                auto_delete_max_count = 0
            if auto_delete_max_count > 0 and qualified > auto_delete_max_count:
                summary=f'符合条件 {qualified} 部，超过自动删除上限 {auto_delete_max_count} 部，已中止删除'
                self.plugin.save_data(key='library_cleanup_result', value=obj.get_data(key='last_cleanup_result'))
                self.add_history('failed', summary, time.time()-start)
                if self.config.get('notify', True):
                    self.send_notification('清库存检查报告', summary)
                return {'success':False,'summary':summary}
            if self.config.get('dry_run', False):
                summary=f'演练模式：符合条件 {qualified} 部，未执行删除'
                self.plugin.save_data(key='library_cleanup_result', value=obj.get_data(key='last_cleanup_result'))
                self.add_history('success', summary, time.time()-start)
                if self.config.get('notify', True):
                    self.send_notification('清库存检查报告', summary)
                return {'success':True,'summary':summary}

        # 自动删除模式由工具集发送最终通知；手动模式保留原版清库存通知，避免重复。
        if auto_delete and self.config.get('notify', True):
            from datetime import datetime, timezone
            title='清库存检查报告'
            text=f'符合条件(超{self.config.get("days_threshold",30)}天+已看过+未收藏): {qualified}部\n\n待删除列表:\n'
            now=datetime.now(timezone.utc)
            for i,m in enumerate(movies[:20],1):
                code=m.code or m.movie_id or '未知'
                date_str=m.date_created[:10] if m.date_created else '未知'
                age=(now-m.date_created_obj).days if m.date_created_obj else 0
                text+=f'  {i}. {code} | {age}天 | {date_str}\n'
            if qualified>20:
                text+=f'  ... 还有{qualified-20}部\n'
            text+='\n即将开始自动删除...'
            self.send_notification(title, text)

        # 第三步：执行自动删除
        delay=self.config.get('auto_delete_delay',60)
        success_count=0; fail_count=0

        if auto_delete:
            for index,item in enumerate(list(movies),start=1):
                code=item.code or item.movie_id or '未知'
                logger.info(f'本地工具集：自动删除 [{index}/{len(movies)}]: {code}')
                if obj._emby_delete(item.movie_id):
                    success_count+=1
                else:
                    fail_count+=1
                if index<len(movies) and delay>0:
                    time.sleep(delay)

        summary=f'符合条件 {qualified} 部，删除成功 {success_count} 部，失败 {fail_count} 部'
        self.plugin.save_data(key='library_cleanup_result', value=obj.get_data(key='last_cleanup_result'))
        self.add_history('success', summary, time.time()-start)
        return {'success':True,'summary':summary}
    def get_status(self):
        status = {'enabled': self.config.get('enabled', False), 'auto_delete': self.config.get('auto_delete', False), 'cron': self.config.get('cron','')}
        if self.last_error:
            status['last_error'] = self.last_error
        return status
