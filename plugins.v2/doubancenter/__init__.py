"""
DoubanCenter v1.2.1 - MoviePilot 本地插件
整合：榜单订阅 + 豆瓣时间 + 仪表盘双面板
"""
import datetime
import threading
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import WebhookEventInfo
from app.schemas.types import EventType

from . import dashboard as dash, feed, folio
from . import utils

lock = threading.Lock()


class DoubanCenter(_PluginBase):
    plugin_name = "豆瓣中心"
    plugin_desc = "豆瓣榜单订阅 + 豆瓣时间 + 仪表盘，一站式豆瓣集成。"
    plugin_icon = "douban.png"
    plugin_color = "#2E7D32"
    plugin_version = "1.2.1"
    plugin_author = "牧濑红莉栖"
    author_url = "https://github.com/z2561221"
    plugin_config_prefix = "doubancenter_"
    plugin_order = 14
    auth_level = 1

    _enabled = False
    _cron = "0 8 * * *"
    _notify = False
    _proxy = False
    _onlyonce = False
    _rsshub_domain = "https://rsshub.ddsrem.com"
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
    _anti_cheat_enabled: bool = False
    _anti_cheat_min_vote: float = 5.0

    _region_options = ["中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "英国", "泰国", "印度", "法国", "德国", "西班牙", "加拿大", "澳大利亚", "俄罗斯", "瑞典", "丹麦", "爱尔兰", "意大利", "巴西"]
    _genre_options = ["爱情", "喜剧", "剧情", "悬疑", "古装", "动作", "犯罪", "科幻", "家庭", "奇幻", "武侠", "历史", "动画", "惊悚", "战争", "冒险", "恐怖", "灾难", "传记", "音乐", "歌舞"]
    _resolution_options = [{"title":"2160p/4K","value":"2160p|4k|uhd"},{"title":"1080p","value":"1080p"},{"title":"720p","value":"720p"}]

    _scheduler = None
    _wait_process: Dict = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sync_lock = threading.Lock()

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = config.get("enabled", False)
        self._cron = config.get("cron") or "0 8 * * *"
        self._notify = config.get("notify", False)
        self._proxy = config.get("proxy", False)
        self._onlyonce = config.get("onlyonce", False)
        self._rsshub_domain = utils.normalize_rss_domain(config.get("rsshub_domain") or "https://rsshub.ddsrem.com")
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
        self._anti_cheat_enabled = config.get("anti_cheat_enabled", False)
        self._anti_cheat_min_vote = float(config.get("anti_cheat_min_vote", 5.0) or 5.0)
        self.stop_service()
        if self._onlyonce:
            self._onlyonce = False
            self.__update_config()
            # 立即运行先刷新 RSS 榜单，再按当前配置执行订阅。
            feed.run_once(self)

    def __run_all(self):
        feed.subscribe_to_ranks(self)

    def __update_config(self):
        self.update_config({"enabled":self._enabled,"cron":self._cron,"notify":self._notify,"proxy":self._proxy,"onlyonce":self._onlyonce,"rsshub_domain":self._rsshub_domain,"rank_configs":self._rank_configs,"region_filters":[],"genre_filters":[],"resolution_filters":[],"custom_rss_addrs":"","folio_enabled":self._folio_enabled,"folio_private":self._folio_private,"folio_first":self._folio_first,"folio_notify":self._folio_notify,"folio_user":self._folio_user,"folio_exclude":self._folio_exclude,"folio_cookie":self._folio_cookie,"folio_pc_month":self._folio_pc_month,"folio_pc_num":self._folio_pc_num,"folio_mobile_month":self._folio_mobile_month,"folio_mobile_num":self._folio_mobile_num,"dashboard_rank_keys":self._dashboard_rank_keys,"blacklist_keywords":self._blacklist_keywords,"observe_days":self._observe_days,"anti_cheat_enabled":self._anti_cheat_enabled,"anti_cheat_min_vote":self._anti_cheat_min_vote})

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {"path":"/folio_data","endpoint":self.api_folio_data,"methods":["GET"],"auth":"bear","summary":"获取豆瓣时间数据"},
            {"path":"/overview","endpoint":self.api_overview,"methods":["GET"],"auth":"bear","summary":"获取运行总览"},
            {"path":"/config","endpoint":self.api_config,"methods":["GET"],"auth":"bear","summary":"获取插件配置"},
            {"path":"/rank_history","endpoint":self.api_rank_history,"methods":["GET"],"auth":"bear","summary":"获取榜单历史"},
            {"path":"/resolve_media","endpoint":self.api_resolve_media,"methods":["GET"],"auth":"bear","summary":"识别榜单媒体"},
            {"path":"/subscribe","endpoint":self.api_subscribe,"methods":["GET","POST"],"auth":"bear","summary":"一键订阅"},
            {"path":"/refresh_rss","endpoint":self.api_refresh_rss,"methods":["POST"],"auth":"bear","summary":"刷新 RSS 榜单数据"},
            {"path":"/stats","endpoint":self.api_stats,"methods":["GET"],"auth":"bear","summary":"获取订阅统计"},
            {"path":"/subscribe_history","endpoint":self.api_subscribe_history,"methods":["GET"],"auth":"bear","summary":"获取订阅历史"},
            {"path":"/pending_observations","endpoint":self.api_pending_observations,"methods":["GET"],"auth":"bear","summary":"获取观察期待订阅条目"},
            {"path":"/anti_cheat_logs","endpoint":self.api_anti_cheat_logs,"methods":["GET"],"auth":"bear","summary":"获取防刷榜日志"},
            {"path":"/delete_subscribe_history","endpoint":self.api_delete_subscribe_history,"methods":["POST"],"auth":"bear","summary":"删除订阅历史记录"},
            {"path":"/delete_observation","endpoint":self.api_delete_observation,"methods":["POST"],"auth":"bear","summary":"删除观察队列条目"},
            {"path":"/delete_anti_cheat_log","endpoint":self.api_delete_anti_cheat_log,"methods":["POST"],"auth":"bear","summary":"删除防刷榜日志"},
            {"path":"/archive_records","endpoint":self.api_archive_records,"methods":["GET"],"auth":"bear","summary":"获取归档记录"},
            {"path":"/restore_archive","endpoint":self.api_restore_archive,"methods":["POST"],"auth":"bear","summary":"恢复归档记录"},
            {"path":"/delete_archive","endpoint":self.api_delete_archive,"methods":["POST"],"auth":"bear","summary":"删除归档记录"},
        ]

    def api_folio_data(self):
        return dash.api_folio_data(self)

    def api_overview(self):
        """返回设置页运行总览数据。"""
        try:
            return dash.api_overview(self)
        except Exception as e:
            logger.error(f"豆瓣中心：api_overview 异常：{e}", exc_info=True)
            return {"code": 1, "msg": f"获取运行总览失败：{e}"}

    def api_config(self):
        return dash.api_config(self)

    def api_rank_history(self):
        return dash.api_rank_history(self)

    def api_resolve_media(self, media_type=None, title="", year="", tmdb_id=None, bangumi_id=None):
        """识别榜单条目并返回媒体信息。"""
        try:
            if not title and not tmdb_id and not bangumi_id:
                return {"success": False, "message": "缺少必要参数"}
            return dash.api_resolve_media_from_rank(self, media_type, title, year, tmdb_id=tmdb_id, bangumi_id=bangumi_id)
        except Exception as e:
            logger.error(f"豆瓣中心：api_resolve_media 异常：{e}", exc_info=True)
            return {"success": False, "message": f"识别失败：{e}"}

    def api_subscribe(self, tmdb_id=None, media_type=None, title="", year="", bangumi_id=None):
        """从仪表盘榜单条目发起订阅。"""
        try:
            if not title and not tmdb_id and not bangumi_id:
                return {"success": False, "message": "缺少必要参数"}
            return dash.api_subscribe_from_rank(self, tmdb_id, media_type, title, year, bangumi_id=bangumi_id)
        except Exception as e:
            logger.error(f"豆瓣中心：api_subscribe 异常：{e}", exc_info=True)
            return {"success": False, "message": f"订阅失败：{e}"}

    def api_refresh_rss(self):
        """刷新 RSS 榜单数据但不创建订阅。"""
        try:
            logger.info("豆瓣中心：api_refresh_rss 被调用")
            rank_keys = self._dashboard_rank_keys or None
            logger.info(f"豆瓣中心：refresh_rss rank_keys={rank_keys}")
            result = feed.refresh_rank_data(self, rank_keys=rank_keys)
            return {"success": True, "message": "RSS 刷新完成", "data": result}
        except Exception as e:
            logger.error(f"豆瓣中心：api_refresh_rss 异常：{e}", exc_info=True)
            return {"success": False, "message": f"刷新失败：{e}"}

    def api_stats(self):
        """返回订阅统计。"""
        try:
            return dash.api_stats(self)
        except Exception as e:
            logger.error(f"豆瓣中心：api_stats 异常：{e}", exc_info=True)
            return {"success": False, "message": f"获取统计失败：{e}"}

    def api_subscribe_history(self, page=1, page_size=20):
        """返回分页订阅历史。"""
        try:
            return dash.api_subscribe_history(self, page=int(page), page_size=int(page_size))
        except Exception as e:
            logger.error(f"豆瓣中心：api_subscribe_history 异常：{e}", exc_info=True)
            return {"success": False, "message": f"获取订阅历史失败：{e}"}

    def api_pending_observations(self):
        """返回观察期内等待自动订阅的条目。"""
        try:
            return dash.api_pending_observations(self)
        except Exception as e:
            logger.error(f"豆瓣中心：api_pending_observations 异常：{e}", exc_info=True)
            return {"success": False, "message": f"获取观察期条目失败：{e}"}

    def api_anti_cheat_logs(self):
        """返回防刷榜日志。"""
        try:
            return dash.api_anti_cheat_logs(self)
        except Exception as e:
            logger.error(f"豆瓣中心：api_anti_cheat_logs 异常：{e}", exc_info=True)
            return {"success": False, "message": f"获取防刷榜日志失败：{e}"}

    def api_delete_subscribe_history(self, time="", title="", tmdbid=None):
        """从详情页删除一条订阅历史并归档。"""
        try:
            return dash.api_delete_subscribe_history(self, time=time, title=title, tmdbid=tmdbid)
        except Exception as e:
            logger.error(f"豆瓣中心：api_delete_subscribe_history 异常：{e}", exc_info=True)
            return {"success": False, "message": f"删除订阅历史失败：{e}"}

    def api_delete_observation(self, unique="", rank_key="", title=""):
        """从详情页删除一条观察队列记录并归档。"""
        try:
            return dash.api_delete_observation(self, unique=unique, rank_key=rank_key, title=title)
        except Exception as e:
            logger.error(f"豆瓣中心：api_delete_observation 异常：{e}", exc_info=True)
            return {"success": False, "message": f"删除观察条目失败：{e}"}

    def api_delete_anti_cheat_log(self, time="", title="", reason=""):
        """从详情页删除一条防刷日志并归档。"""
        try:
            return dash.api_delete_anti_cheat_log(self, time=time, title=title, reason=reason)
        except Exception as e:
            logger.error(f"豆瓣中心：api_delete_anti_cheat_log 异常：{e}", exc_info=True)
            return {"success": False, "message": f"删除防刷日志失败：{e}"}

    def api_archive_records(self, page=1, page_size=20):
        """返回分页归档记录。"""
        try:
            return dash.api_archive_records(self, page=int(page), page_size=int(page_size))
        except Exception as e:
            logger.error(f"豆瓣中心：api_archive_records 异常：{e}", exc_info=True)
            return {"success": False, "message": f"获取归档记录失败：{e}"}

    def api_restore_archive(self, archive_id=""):
        """从归档恢复一条详情页记录。"""
        try:
            return dash.api_restore_archive(self, archive_id=archive_id)
        except Exception as e:
            logger.error(f"豆瓣中心：api_restore_archive 异常：{e}", exc_info=True)
            return {"success": False, "message": f"恢复归档记录失败：{e}"}

    def api_delete_archive(self, archive_id=""):
        """永久删除一条归档记录。"""
        try:
            return dash.api_delete_archive(self, archive_id=archive_id)
        except Exception as e:
            logger.error(f"豆瓣中心：api_delete_archive 异常：{e}", exc_info=True)
            return {"success": False, "message": f"删除归档记录失败：{e}"}

    def get_service(self) -> List[Dict[str, Any]]:
        if self._enabled and self._cron:
            return [{"id":"DoubanCenter","name":"豆瓣中心定时服务","trigger":CronTrigger.from_crontab(self._cron),"func":self.__run_all,"kwargs":{}}]
        return []

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        return None, {"enabled":False,"cron":"0 8 * * *","notify":False,"proxy":False,"onlyonce":False,"rsshub_domain":"https://rsshub.ddsrem.com","rank_configs":{"coming":{"enabled":False,"count":0,"wish_count":5000,"air_days":7,"vote":0,"year":0},"tv_real_time":{"enabled":False,"count":0,"wish_count":0,"air_days":0,"vote":0,"year":0},"tv_chinese":{"enabled":False,"count":0,"wish_count":0,"air_days":0,"vote":0,"year":0},"tv_global":{"enabled":False,"count":0,"wish_count":0,"air_days":0,"vote":0,"year":0},"movie_weekly":{"enabled":False,"count":0,"wish_count":0,"air_days":0,"vote":0,"year":0},"bangumi":{"enabled":False,"count":0,"wish_count":0,"air_days":0,"vote":0,"year":0}},"region_filters":[],"genre_filters":[],"resolution_filters":[],"custom_rss_addrs":"","folio_enabled":True,"folio_private":True,"folio_first":True,"folio_notify":False,"folio_user":"","folio_exclude":"","folio_cookie":"","folio_pc_month":3,"folio_pc_num":50,"folio_mobile_month":2,"folio_mobile_num":15,"dashboard_rank_keys":[],"blacklist_keywords":"","observe_days":0,"anti_cheat_enabled":False,"anti_cheat_min_vote":5.0}

    def get_page(self) -> Optional[List[dict]]:
        return None

    def get_dashboard(self, key: str, **kwargs) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
        return dash.get_dashboard(self, key, **kwargs)

    def stop_service(self):
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as err:
            logger.error(str(err))

    @eventmanager.register(EventType.WebhookMessage)
    def sync_log(self, event: Event, played: bool = False):
        if not self._enabled or not self._folio_enabled:
            return
        if not hasattr(self, '_sync_lock'):
            self._sync_lock = threading.Lock()
        if not self._sync_lock.acquire(blocking=False):
            now = datetime.datetime.now().timestamp()
            if not hasattr(self, '_last_skip_log_time'):
                self._last_skip_log_time = 0
            if now - self._last_skip_log_time > 600:
                self._last_skip_log_time = now
            return
        try:
            folio.check_cookie_periodically(self)
            folio.sync_log_handler(self, event.event_data, played=played)
        finally:
            self._sync_lock.release()

    @eventmanager.register(EventType.WebhookMessage)
    def sync_played(self, event: Event):
        if not self._enabled or not self._folio_enabled:
            return
        ei = event.event_data
        played = {'item.markplayed', 'media.scrobble'}
        ip = ei.event in played
        if ei.channel == "jellyfin":
            ip = ei.event == 'UserDataSaved' and ei.save_reason == 'TogglePlayed'
        if ip and ei.user_name in self._folio_user.split(','):
            with lock:
                self.sync_log(event=event, played=True)
