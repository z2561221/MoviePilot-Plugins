"""
DoubanCenter v1.2.11 - MoviePilot 本地插件
整合：榜单订阅 + 豆瓣时间 + 仪表盘双面板
"""
import threading
from typing import Any, Dict, List, Optional, Tuple

from app.core.event import eventmanager, Event
from app.plugins import _PluginBase
from app.schemas.types import EventType

from . import dashboard as dash, feed, migration
from . import utils
from .controller import api as api_controller
from .model.config import (
    DEFAULT_CRON,
    DEFAULT_RSSHUB_DOMAIN,
    GENRE_OPTIONS,
    REGION_OPTIONS,
    RESOLUTION_OPTIONS,
    default_config,
)
from .service import scheduler as scheduler_service
from .service import webhook as webhook_service


class DoubanCenter(_PluginBase):
    """整合豆瓣榜单订阅、豆瓣时间和仪表盘的 MoviePilot 插件入口。"""

    plugin_name = "豆瓣中心"
    plugin_desc = "豆瓣榜单订阅 + 豆瓣时间 + 仪表盘，一站式豆瓣集成。"
    plugin_icon = "douban.png"
    plugin_color = "#2E7D32"
    plugin_version = "1.2.11"
    plugin_author = "牧濑红莉栖"
    author_url = "https://github.com/z2561221"
    plugin_config_prefix = "doubancenter_"
    plugin_order = 14
    auth_level = 1

    _enabled = False
    _cron = DEFAULT_CRON
    _notify = False
    _proxy = False
    _onlyonce = False
    _rsshub_domain = DEFAULT_RSSHUB_DOMAIN
    _rank_configs: Dict[str, Any] = {}
    _region_filters: List[str] = []
    _genre_filters: List[str] = []
    _resolution_filters: List[str] = []
    _custom_rss_addrs: List[str] = []
    _folio_enabled = True
    _folio_private = True
    _folio_first = True
    _folio_notify = False
    _folio_user = ""
    _folio_exclude = ""
    _folio_cookie = ""
    _folio_pc_month = 3
    _folio_pc_num = 50
    _folio_mobile_month = 2
    _folio_mobile_num = 15
    _dashboard_rank_keys: List[str] = []
    _blacklist_keywords: str = ""
    _observe_days: int = 0
    _observe_rank_keys: List[str] = []

    _region_options = REGION_OPTIONS
    _genre_options = GENRE_OPTIONS
    _resolution_options = RESOLUTION_OPTIONS

    _scheduler = None
    _wait_process: Dict = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sync_lock = threading.Lock()

    def init_plugin(self, config: dict = None):
        """根据插件配置初始化运行状态并触发一次性任务。"""
        config = config or {}
        self._enabled = config.get("enabled", False)
        self._cron = config.get("cron") or DEFAULT_CRON
        self._notify = config.get("notify", False)
        self._proxy = config.get("proxy", False)
        self._onlyonce = config.get("onlyonce", False)
        self._rsshub_domain = utils.normalize_rss_domain(config.get("rsshub_domain") or DEFAULT_RSSHUB_DOMAIN)
        self._rank_configs = config.get("rank_configs") or {}
        self._region_filters = []
        self._genre_filters = []
        self._resolution_filters = []
        self._custom_rss_addrs = []
        self._folio_enabled = config.get("folio_enabled", True)
        self._folio_private = config.get("folio_private", True)
        self._folio_first = config.get("folio_first", True)
        self._folio_notify = config.get("folio_notify", False)
        self._folio_user = config.get("folio_user", "")
        self._folio_exclude = config.get("folio_exclude", "")
        self._folio_cookie = config.get("folio_cookie", "")
        self._folio_pc_month = int(config.get("folio_pc_month", 3) or 3)
        self._folio_pc_num = int(config.get("folio_pc_num", 50) or 50)
        self._folio_mobile_month = int(config.get("folio_mobile_month", 2) or 2)
        self._folio_mobile_num = int(config.get("folio_mobile_num", 15) or 15)
        self._dashboard_rank_keys = config.get("dashboard_rank_keys") or []
        self._blacklist_keywords = config.get("blacklist_keywords") or ""
        self._observe_days = int(config.get("observe_days", 0) or 0)
        self._observe_rank_keys = config.get("observe_rank_keys") if "observe_rank_keys" in config else feed.default_observe_rank_keys()
        if not isinstance(self._observe_rank_keys, list):
            self._observe_rank_keys = []
        if set(config) - set(self.__current_config()):
            self.__update_config()
        migration.normalize_legacy_subscribe_usernames()
        self.stop_service()
        if self._onlyonce:
            self._onlyonce = False
            self.__update_config()
            # 立即运行先刷新 RSS 榜单，再按当前配置执行订阅。
            feed.run_once(self)

    def __run_all(self):
        feed.run_scheduled(self)

    def __current_config(self):
        """返回当前有效配置快照，用于清理旧字段。"""
        return {"enabled":self._enabled,"cron":self._cron,"notify":self._notify,"proxy":self._proxy,"onlyonce":self._onlyonce,"rsshub_domain":self._rsshub_domain,"rank_configs":self._rank_configs,"region_filters":[],"genre_filters":[],"resolution_filters":[],"custom_rss_addrs":"","folio_enabled":self._folio_enabled,"folio_private":self._folio_private,"folio_first":self._folio_first,"folio_notify":self._folio_notify,"folio_user":self._folio_user,"folio_exclude":self._folio_exclude,"folio_cookie":self._folio_cookie,"folio_pc_month":self._folio_pc_month,"folio_pc_num":self._folio_pc_num,"folio_mobile_month":self._folio_mobile_month,"folio_mobile_num":self._folio_mobile_num,"dashboard_rank_keys":self._dashboard_rank_keys,"blacklist_keywords":self._blacklist_keywords,"observe_days":self._observe_days,"observe_rank_keys":self._observe_rank_keys}

    def __update_config(self):
        self.update_config(self.__current_config())

    def get_state(self) -> bool:
        """返回插件当前启用状态。"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """返回插件命令列表。"""
        return []

    @staticmethod
    def get_agent_tools() -> List[type]:
        """返回插件提供的 Agent 工具列表。"""
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """返回插件对外开放的 API 路由定义。"""
        return api_controller.get_api(self)

    def api_folio_data(self):
        """返回豆瓣时间数据。"""
        return api_controller.api_folio_data(self)

    def api_overview(self):
        """返回插件总览数据。"""
        return api_controller.api_overview(self)

    def api_config(self):
        """返回前端配置选项和当前配置。"""
        return api_controller.api_config(self)

    def api_rank_history(self):
        """返回榜单历史快照。"""
        return api_controller.api_rank_history(self)

    def api_resolve_media(self, media_type=None, title="", year="", tmdb_id=None, bangumi_id=None):
        """根据标题、年份和外部 ID 解析媒体信息。"""
        return api_controller.api_resolve_media(self, media_type, title, year, tmdb_id=tmdb_id, bangumi_id=bangumi_id)

    def api_subscribe(self, tmdb_id=None, media_type=None, title="", year="", bangumi_id=None):
        """根据前端请求创建媒体订阅。"""
        return api_controller.api_subscribe(self, tmdb_id, media_type, title, year, bangumi_id=bangumi_id)

    def api_refresh_rss(self):
        """立即刷新 RSS 榜单并执行订阅检查。"""
        return api_controller.api_refresh_rss(self)

    def api_stats(self):
        """返回插件统计数据。"""
        return api_controller.api_stats(self)

    def api_subscribe_history(self, page=1, page_size=20):
        """分页返回订阅历史记录。"""
        return api_controller.api_subscribe_history(self, page=page, page_size=page_size)

    def api_pending_observations(self):
        """返回待观察的媒体记录。"""
        return api_controller.api_pending_observations(self)

    def api_anti_cheat_logs(self):
        """返回反作弊拦截日志。"""
        return api_controller.api_anti_cheat_logs(self)

    def api_delete_subscribe_history(self, time="", title="", tmdbid=None):
        """删除指定订阅历史记录。"""
        return api_controller.api_delete_subscribe_history(self, time=time, title=title, tmdbid=tmdbid)

    def api_delete_observation(self, unique="", rank_key="", title=""):
        """删除指定观察记录。"""
        return api_controller.api_delete_observation(self, unique=unique, rank_key=rank_key, title=title)

    def api_delete_anti_cheat_log(self, time="", title="", reason=""):
        """删除指定反作弊日志。"""
        return api_controller.api_delete_anti_cheat_log(self, time=time, title=title, reason=reason)

    def api_archive_records(self, page=1, page_size=20):
        """分页返回订阅归档记录。"""
        return api_controller.api_archive_records(self, page=page, page_size=page_size)

    def api_restore_archive(self, archive_id=""):
        """恢复指定订阅归档记录。"""
        return api_controller.api_restore_archive(self, archive_id=archive_id)

    def api_delete_archive(self, archive_id=""):
        """删除指定订阅归档记录。"""
        return api_controller.api_delete_archive(self, archive_id=archive_id)

    def get_service(self) -> List[Dict[str, Any]]:
        """返回插件定时服务定义。"""
        return scheduler_service.get_services(self, self.__run_all)

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明插件使用 Vue 联邦组件渲染。"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """返回 Vue 模式下的默认配置模型。"""
        return None, default_config()

    def get_page(self) -> Optional[List[dict]]:
        """返回插件详情页结构，Vue 模式下由前端远程组件渲染。"""
        return None

    def get_dashboard(self, key: str, **kwargs) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
        """返回指定仪表盘组件数据。"""
        return dash.get_dashboard(self, key, **kwargs)

    def stop_service(self):
        """停止插件后台定时服务。"""
        scheduler_service.stop_scheduler(self)

    @eventmanager.register(EventType.WebhookMessage)
    def sync_log(self, event: Event, played: bool = False):
        """处理媒体库同步完成的 Webhook 日志。"""
        webhook_service.handle_sync_log(self, event=event, played=played)

    @eventmanager.register(EventType.WebhookMessage)
    def sync_played(self, event: Event):
        """处理媒体库已播放同步 Webhook。"""
        webhook_service.handle_sync_played(self, event=event, sync_log=self.sync_log)
