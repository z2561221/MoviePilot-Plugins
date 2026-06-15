"""
DoubanCenter v1.0.2 - MoviePilot 本地插件
整合：豆瓣即将播出订阅 + 豆瓣榜单Plus + 豆瓣档案
"""
import datetime
import re
import threading
import time
import xml.dom.minidom
from typing import Any, List, Dict, Tuple, Optional
from urllib.parse import urlparse

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.chain.download import DownloadChain
from app.chain.media import MediaChain
from app.chain.subscribe import SubscribeChain
from app.core.config import settings
from app.core.context import MediaInfo
from app.core.event import eventmanager, Event
from app.core.metainfo import MetaInfo
from app.db.site_oper import SiteOper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import WebhookEventInfo
from app.schemas.types import EventType, MediaType, NotificationType
from app.utils.dom import DomUtils
from app.utils.http import RequestUtils

from .doubanapi import DoubanApi

lock = threading.Lock()


class DoubanCenter(_PluginBase):
    plugin_name = "豆瓣中心"
    plugin_desc = "豆瓣即将播出订阅 + 榜单订阅 + 豆瓣档案，一站式豆瓣集成。"
    plugin_icon = "douban.png"
    plugin_color = "#2E7D32"
    plugin_version = "1.0.3"
    plugin_author = "牧濑红莉栖"
    author_url = "https://raw.githubusercontent.com/z2561221/MoviePilot-Plugins/main/icons/author-avatars/kurisu"
    plugin_config_prefix = "doubancenter_"
    plugin_order = 15
    auth_level = 1

    # ── 通用 ──
    _enabled = False
    _cron = "0 8 * * *"
    _notify = False
    _proxy = False
    _onlyonce_coming = False
    _onlyonce_rank = False

    # ── 即将播出 ──
    _coming_enabled = True
    _coming_min_wish = 5000
    _coming_air_days = 7
    _coming_region_filters: List[str] = []
    _coming_genre_filters: List[str] = []
    _coming_resolution_filters: List[str] = []
    _coming_subscribe_sites: List[int] = []
    _coming_rss_domain = "https://rsshub.ddsrem.com"
    _coming_rss_path = "/douban/tv/coming"

    # ── 榜单 ──
    _rank_enabled = True
    _rank_vote = 0.0
    _rank_release_year = 0
    _rank_ranks: List[str] = []
    _rank_rss_addrs: List[str] = []
    _rank_is_seasons_all = True
    _rank_is_only_movies = False

    # ── 豆瓣档案 ──
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

    # ── 内置榜单地址 ──
    _douban_address = {
        "movie-ustop": "https://rsshub.app/douban/movie/ustop",
        "movie-weekly": "https://rsshub.app/douban/movie/weekly",
        "movie-real-time": "https://rsshub.app/douban/movie/weekly/movie_real_time_hotest",
        "show-domestic": "https://rsshub.app/douban/movie/weekly/show_domestic",
        "movie-hot-gaia": "https://rsshub.app/douban/movie/weekly/movie_hot_gaia",
        "tv-hot": "https://rsshub.app/douban/movie/weekly/tv_hot",
        "movie-top250": "https://rsshub.app/douban/movie/weekly/movie_top250",
        "movie-top250-full": "https://rsshub.app/douban/list/movie_top250",
    }

    _region_options = [
        "中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "英国", "泰国", "印度", "法国",
        "德国", "西班牙", "加拿大", "澳大利亚", "俄罗斯", "瑞典", "丹麦", "爱尔兰", "意大利", "巴西"
    ]
    _genre_options = [
        "爱情", "喜剧", "剧情", "悬疑", "古装", "动作", "犯罪", "科幻", "家庭", "奇幻", "武侠",
        "历史", "动画", "惊悚", "战争", "冒险", "恐怖", "灾难", "传记", "音乐", "歌舞"
    ]
    _resolution_options = [
        {"title": "2160p / 4K", "value": "2160p|4k|uhd"},
        {"title": "1080p", "value": "1080p"},
        {"title": "720p", "value": "720p"},
    ]

    _scheduler = None
    _event = None
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
        self._onlyonce_coming = config.get("onlyonce_coming", False)
        self._onlyonce_rank = config.get("onlyonce_rank", False)

        # 即将播出
        self._coming_enabled = config.get("coming_enabled", True)
        self._coming_min_wish = int(config.get("coming_min_wish", 5000) or 5000)
        self._coming_air_days = int(config.get("coming_air_days", 7) or 7)
        self._coming_region_filters = config.get("coming_region_filters") or []
        self._coming_genre_filters = config.get("coming_genre_filters") or []
        self._coming_resolution_filters = config.get("coming_resolution_filters") or []
        self._coming_subscribe_sites = config.get("coming_subscribe_sites") or []
        self._coming_rss_domain = self.__normalize_rss_domain(
            config.get("coming_rss_domain") or "https://rsshub.ddsrem.com"
        )

        # 榜单
        self._rank_enabled = config.get("rank_enabled", True)
        self._rank_vote = float(str(config.get("rank_vote", 0) or 0))
        self._rank_release_year = int(str(config.get("rank_release_year", 0) or 0))
        self._rank_ranks = config.get("rank_ranks") or []
        rss_addrs = config.get("rank_rss_addrs", "")
        self._rank_rss_addrs = rss_addrs.split("\n") if isinstance(rss_addrs, str) and rss_addrs.strip() else []
        self._rank_is_seasons_all = config.get("rank_is_seasons_all", True)
        self._rank_is_only_movies = config.get("rank_is_only_movies", False)

        # 豆瓣档案
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

        self.stop_service()

        if self._enabled and self._folio_enabled:
            logger.info("豆瓣档案模块已启用")

        # 处理立即运行
        if self._onlyonce_coming or self._onlyonce_rank:
            run_coming = self._onlyonce_coming
            run_rank = self._onlyonce_rank
            self._onlyonce_coming = False
            self._onlyonce_rank = False
            self.__update_config()
            if run_coming:
                logger.info("豆瓣中心 - 即将播出：立即运行一次")
                self.__refresh_coming()
            if run_rank:
                logger.info("豆瓣中心 - 榜单订阅：立即运行一次")
                self.__refresh_ranks()

    # ═══════════════════════════════════════════════════════════════
    # 通用
    # ═══════════════════════════════════════════════════════════════

    def __run_all(self):
        """定时任务入口"""
        run_coming = self._onlyonce_coming or self._coming_enabled
        run_rank = self._onlyonce_rank or self._rank_enabled
        if self._onlyonce_coming:
            self._onlyonce_coming = False
            self.__update_config()
            logger.info("豆瓣中心 - 即将播出：立即运行一次")
        if self._onlyonce_rank:
            self._onlyonce_rank = False
            self.__update_config()
            logger.info("豆瓣中心 - 榜单订阅：立即运行一次")
        if run_coming:
            self.__refresh_coming()
        if run_rank:
            self.__refresh_ranks()

    def __run_once(self, run_coming: bool = False, run_rank: bool = False):
        """立即运行一次"""
        try:
            if run_coming:
                logger.info("豆瓣中心 - 即将播出：立即运行一次")
                self.__refresh_coming()
            if run_rank:
                logger.info("豆瓣中心 - 榜单订阅：立即运行一次")
                self.__refresh_ranks()
        finally:
            # 重置立即运行标志
            self._onlyonce_coming = False
            self._onlyonce_rank = False
            self.__update_config()

    def __update_config(self):
        """保存当前配置"""
        self.update_config({
            "enabled": self._enabled,
            "cron": self._cron,
            "notify": self._notify,
            "proxy": self._proxy,
            "onlyonce_coming": self._onlyonce_coming,
            "onlyonce_rank": self._onlyonce_rank,
            "coming_enabled": self._coming_enabled,
            "coming_min_wish": self._coming_min_wish,
            "coming_air_days": self._coming_air_days,
            "coming_region_filters": self._coming_region_filters,
            "coming_genre_filters": self._coming_genre_filters,
            "coming_resolution_filters": self._coming_resolution_filters,
            "coming_subscribe_sites": self._coming_subscribe_sites,
            "coming_rss_domain": self._coming_rss_domain,
            "rank_enabled": self._rank_enabled,
            "rank_vote": self._rank_vote,
            "rank_release_year": self._rank_release_year,
            "rank_ranks": self._rank_ranks,
            "rank_rss_addrs": "\n".join(self._rank_rss_addrs) if self._rank_rss_addrs else "",
            "rank_is_seasons_all": self._rank_is_seasons_all,
            "rank_is_only_movies": self._rank_is_only_movies,
            "folio_enabled": self._folio_enabled,
            "folio_private": self._folio_private,
            "folio_first": self._folio_first,
            "folio_notify": self._folio_notify,
            "folio_user": self._folio_user,
            "folio_exclude": self._folio_exclude,
            "folio_cookie": self._folio_cookie,
            "folio_pc_month": self._folio_pc_month,
            "folio_pc_num": self._folio_pc_num,
            "folio_mobile_month": self._folio_mobile_month,
            "folio_mobile_num": self._folio_mobile_num,
        })

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/folio_data",
                "endpoint": self.api_folio_data,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取豆瓣档案数据",
            },
            {
                "path": "/config",
                "endpoint": self.api_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取插件配置",
            },
        ]

    def api_folio_data(self):
        """返回豆瓣档案数据"""
        data = self.get_data('folio_data') or {}
        return {"data": data}

    def api_config(self):
        """返回当前插件配置"""
        return {
            "data": {
                "folio_pc_month": self._folio_pc_month,
                "folio_pc_num": self._folio_pc_num,
                "folio_mobile_month": self._folio_mobile_month,
                "folio_mobile_num": self._folio_mobile_num,
            }
        }

    def get_service(self) -> List[Dict[str, Any]]:
        if self._enabled and self._cron:
            return [{
                "id": "DoubanCenter",
                "name": "豆瓣中心定时服务",
                "trigger": CronTrigger.from_crontab(self._cron),
                "func": self.__run_all,
                "kwargs": {},
            }]
        return []

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """返回渲染模式：vue 联邦组件模式"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """Vue 模式下表单由前端组件渲染"""
        return None, {
            "enabled": False, "cron": "0 8 * * *", "notify": False, "proxy": False,
            "onlyonce_coming": False, "onlyonce_rank": False,
            "coming_enabled": True, "coming_min_wish": 5000, "coming_air_days": 7,
            "coming_region_filters": [], "coming_genre_filters": [], "coming_resolution_filters": [],
            "coming_subscribe_sites": [], "coming_rss_domain": "https://rsshub.ddsrem.com",
            "rank_enabled": True, "rank_vote": 0, "rank_release_year": 0, "rank_ranks": [],
            "rank_rss_addrs": "", "rank_is_seasons_all": True, "rank_is_only_movies": False,
            "folio_enabled": True, "folio_private": True, "folio_first": True, "folio_notify": False,
            "folio_user": "", "folio_exclude": "", "folio_cookie": "",
            "folio_pc_month": 3, "folio_pc_num": 50, "folio_mobile_month": 2, "folio_mobile_num": 15,
        }

    def get_page(self) -> Optional[List[dict]]:
        """无详情页"""
        return None

    def get_dashboard(self, key: str, **kwargs) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
        """豆瓣档案时间线仪表盘 - Vue 模式"""
        if not self._folio_enabled:
            return None
        cols = {"cols": 12, "md": 12}
        attrs = {"refresh": 600, "border": True, "title": "豆瓣中心", "subtitle": "追剧观影时间线"}
        return cols, attrs, None

    def _get_timeline_items(self, mobile: bool = False):
        """构建时间线元素"""
        data: Dict = self.get_data('folio_data') or {}
        content = []
        last_month = None
        current_month_item = None
        limit_month = (self._folio_mobile_month if mobile else self._folio_pc_month) - 1
        limit_num = self._folio_mobile_num if mobile else self._folio_pc_num

        sorted_data = sorted(data.items(),
                             key=lambda item: datetime.datetime.strptime(item[1]['timestamp'], "%Y-%m-%d %H:%M:%S"))

        for key, val in sorted_data[::-1]:
            if not isinstance(val, dict):
                continue
            if not val.get('poster_path', ''):
                meta = MetaInfo(val.get("subject_name"))
                meta.type = MediaType("电视剧" if not val.get("type", '') else val.get("type"))
                mediainfo: MediaInfo = MediaChain().recognize_media(meta=meta, mtype=meta.type, cache=True)
                if mediainfo:
                    poster_path = mediainfo.poster_path
                else:
                    continue
            else:
                poster_path = val.get('poster_path')

            time_object = datetime.datetime.strptime(val.get('timestamp'), "%Y-%m-%d %H:%M:%S")

            if time_object.month != last_month or last_month is None:
                if limit_month < 1:
                    break
                if last_month:
                    num_movies = len(current_month_item["content"][0]["content"][1]["content"])
                    current_month_item["content"][0]["content"][0][
                        "html"] += f"<span class='text-sm font-normal'>看过{num_movies}部</span>"
                    current_month_item["content"][0]["content"][1]["content"] = \
                        current_month_item["content"][0]["content"][1]["content"][:limit_num]
                    content.append(current_month_item)
                    limit_month -= 1

                current_month_item = {
                    "component": "VTimelineItem",
                    "props": {"size": "x-small"},
                    "content": [{
                        "component": "VCol",
                        'props': {'style': 'padding: 0rem 0rem 0rem 0rem'},
                        'content': [
                            {
                                'component': 'h1',
                                'props': {
                                    'style': 'padding:0rem 0rem 1rem 0rem;font-weight: bold;',
                                    'class': 'text-base'
                                },
                                'html': f"{time_object.month}月 ",
                            },
                            {
                                'component': 'VRow',
                                'props': {'style': 'padding: 0rem 0rem 0rem 0rem'},
                                'content': []
                            }
                        ]
                    }]
                }
                last_month = time_object.month

            if not poster_path or (poster_path.count('original') < 1):
                continue

            current_month_item["content"][0]["content"][1]["content"].append({
                "component": "a",
                'props': {
                    'href': 'https://www.douban.com/doubanapp/dispatch?uri=/movie/' + val.get(
                        'subject_id') + '?from=mdouban&open=app',
                    'target': '_blank',
                    'style': 'padding: 0.2rem'
                },
                "content": [{
                    "component": "VCard",
                    "props": {"class": "elevation-4"},
                    "content": [{
                        "component": "VImg",
                        "props": {
                            "src": poster_path.replace("/original/", "/w200/"),
                            "style": "width:44px; height: 66px;" if mobile else "width:66px; height: 99px;",
                            "aspect-ratio": "2/3"
                        }
                    }]
                }]
            })

        if current_month_item:
            num_movies = len(current_month_item["content"][0]["content"][1]["content"])
            current_month_item["content"][0]["content"][0][
                "html"] += f"<span class='text-sm font-normal'>看过{num_movies}部</span>"
            current_month_item["content"][0]["content"][1]["content"] = \
                current_month_item["content"][0]["content"][1]["content"][:limit_num]
            content.append(current_month_item)
        return content

    def stop_service(self):
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as err:
            logger.error(str(err))

    # ═══════════════════════════════════════════════════════════════
    # 豆瓣档案（完整移植自 DoubanFolio v1.0.4）
    # ═══════════════════════════════════════════════════════════════

    @eventmanager.register(EventType.WebhookMessage)
    def sync_log(self, event: Event, played: bool = False):
        if not self._enabled or not self._folio_enabled:
            return
        if not hasattr(self, '_sync_lock'):
            self._sync_lock = threading.Lock()
        if not self._sync_lock.acquire(blocking=False):
            import time
            now = time.time()
            if not hasattr(self, '_last_skip_log_time'):
                self._last_skip_log_time = 0
            if now - self._last_skip_log_time > 600:
                self._last_skip_log_time = now
            return
        try:
            import time
            if not hasattr(self, '_last_cookie_check_time'):
                self._last_cookie_check_time = 0
            now = time.time()
            if now - self._last_cookie_check_time > 3600:
                if not hasattr(self, '_last_cookie_invalid_time'):
                    self._last_cookie_invalid_time = 0
                try:
                    douban_helper = DoubanApi(user_cookie=self._folio_cookie)
                    subject_name, subject_id = douban_helper.get_subject_id(title="肖申克的救赎")
                except Exception:
                    subject_id = None
                if subject_id:
                    if not hasattr(self, '_last_cookie_valid_time'):
                        self._last_cookie_valid_time = 0
                    if now - self._last_cookie_valid_time > 600:
                        logger.info("cookie有效性检测通过")
                        self._last_cookie_valid_time = now
                else:
                    if now - self._last_cookie_invalid_time > 600:
                        self._send_folio_notification(False, "豆瓣cookie可能已失效，请及时更换！")
                        self._last_cookie_invalid_time = now
                self._last_cookie_check_time = now

            event_info: WebhookEventInfo = event.event_data
            play_start = {"playback.start", "media.play", "PlaybackStart"}
            path = event_info.item_path
            processed_items: Dict = self.get_data('folio_data') or {}
            self._wait_process: Dict = self.get_data('folio_wait') or {}

            if (event_info.event in play_start and event_info.user_name in self._folio_user.split(',')) or played:
                if played:
                    logger.info(f"标记播放完成 {event_info.item_name}")

                if not self._exclude_keyword(path=path, keywords=self._folio_exclude).get("ret", False):
                    logger.info(self._exclude_keyword(path=path, keywords=self._folio_exclude).get("message", ""))
                    return

                if event_info.item_type == "TV":
                    self._process_tv_show(event_info, processed_items, played=played)
                elif event_info.item_type == "MOV":
                    self._process_movie(event_info, processed_items, played=played)
                else:
                    return
        finally:
            self._sync_lock.release()
            self._skip_log_printed = False

    @eventmanager.register(EventType.WebhookMessage)
    def sync_played(self, event: Event):
        if not self._enabled or not self._folio_enabled:
            return
        event_info: WebhookEventInfo = event.event_data
        played = {'item.markplayed', 'media.scrobble'}
        is_played = event_info.event in played
        if event_info.channel == "jellyfin":
            is_played = event_info.event == 'UserDataSaved' and event_info.save_reason == 'TogglePlayed'

        if is_played and event_info.user_name in self._folio_user.split(','):
            with lock:
                self.sync_log(event=event, played=True)

    def _process_tv_show(self, event_info: WebhookEventInfo, processed_items: Dict, played: bool = False):
        index = event_info.item_name.index(" S")
        title = event_info.item_name[:index]
        season_id, episode_id = map(int, [event_info.season_id, event_info.episode_id])
        tmdb_id = event_info.tmdb_id

        if not played:
            logger.info(f"开始播放 {title} 第{season_id}季 第{episode_id}集")

        if episode_id < 2 and self._folio_first:
            logger.info(f"剧集第1集的活动不同步到豆瓣档案，跳过")
            return

        meta = MetaInfo(title)
        meta.begin_season = season_id
        meta.type = MediaType("电视剧")
        mediainfo = self._recognize_media(meta, tmdb_id)

        if not mediainfo:
            logger.warning(f'标题：{title}，tmdbid：{tmdb_id}，指定tmdbid未识别到媒体信息，尝试仅使用标题识别')
            meta.tmdbid = None
            mediainfo = self._recognize_media(meta, None)
            if not mediainfo:
                logger.error(f'仍然未识别到媒体信息，请检查TMDB网络连接...')
                return

        episodes = mediainfo.seasons.get(season_id, [])

        title = self._format_title(title, season_id)
        status = "collect" if len(episodes) == episode_id else "do"

        if processed_items.get(title) and len(episodes) != episode_id:
            logger.info(f"{title} 已同步到豆瓣在看，不处理")
            if self._folio_notify:
                logger.info(f"{title} 跳过同步，不发送通知")
            return

        sync_ret = self._sync_to_douban(title, status, event_info.item_type, processed_items, mediainfo)
        if sync_ret:
            logger.info(f"尝试同步之前同步失败的条目")
            self._wait_process: Dict = self.get_data('folio_wait') or {}
            for key, value in self._wait_process.items():
                logger.info(f"尝试同步: {key}")
                self._sync_to_douban(key, value["status"], value["type"], processed_items, None)

    def _process_movie(self, event_info: WebhookEventInfo, processed_items: Dict, played: bool = False):
        title = event_info.item_name

        if not played:
            logger.info(f"开始播放 {title}")

        meta = MetaInfo(title)
        meta.type = MediaType("电影")
        mediainfo = self._recognize_media(meta, event_info.tmdb_id)

        if not mediainfo:
            logger.warning(f'标题：{title}，tmdbid：{event_info.tmdb_id}，指定tmdbid未识别到媒体信息，尝试仅使用标题识别')
            meta.tmdbid = None
            mediainfo = self._recognize_media(meta, None)
            if not mediainfo:
                logger.error(f'仍然未识别到媒体信息，请检查TMDB网络连接...')
                return

        if processed_items.get(title):
            logger.info(f"{title} 已同步到豆瓣在看，不处理")
            return

        self._sync_to_douban(title, "collect", event_info.item_type, processed_items, mediainfo)

    def _recognize_media(self, meta: MetaInfo, tmdb_id: Optional[int]) -> Optional[MediaInfo]:
        return MediaChain().recognize_media(meta=meta, mtype=meta.type, tmdbid=tmdb_id, cache=True)

    def _sync_to_douban(self, title: str, status: str, mediaType: str, processed_items: Dict,
                        mediainfo: Optional[MediaInfo] = None) -> bool:
        logger.info(f"开始尝试获取 {title} 豆瓣id")
        douban_helper = DoubanApi(user_cookie=self._folio_cookie)
        
        # 如果有 TMDB 信息，用年份辅助搜索
        search_title = title
        if mediainfo and mediainfo.year:
            search_title = f"{title} {mediainfo.year}"
            logger.info(f"使用带年份的搜索词: {search_title}")
        
        subject_name, subject_id = douban_helper.get_subject_id(title=search_title)
        
        # 如果带年份搜不到，回退到原标题
        if not subject_id and search_title != title:
            logger.info(f"带年份搜索无结果，回退到原标题: {title}")
            subject_name, subject_id = douban_helper.get_subject_id(title=title)

        if subject_id:
            poster_path = mediainfo.poster_path if mediainfo else ""
            logger.info(f"查询：{title} => 匹配豆瓣：{subject_name} https://movie.douban.com/subject/{subject_id}/")
            ret = douban_helper.set_watching_status(subject_id=subject_id, status=status, private=self._folio_private)
            if ret:
                processed_items[title] = {
                    "subject_id": subject_id,
                    "subject_name": subject_name,
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "poster_path": poster_path,
                    "type": "电视剧" if mediaType == "TV" else "电影"
                }

                if title in self._wait_process:
                    del self._wait_process[title]

                self.save_data('folio_data', processed_items)
                self.save_data('folio_wait', self._wait_process)
                logger.info(f"{title} 同步到档案成功")
                self._send_folio_notification(True, f"《{title}》已成功同步到豆瓣档案。")
                return True
            else:
                error_msg = f'{title} 同步到档案失败'
                if 'The resource you requested could not be found.' in error_msg:
                    logger.error('请求的资源未找到（可能是条目不存在或ID错误）')
                else:
                    logger.error(error_msg)
                if title not in self._wait_process:
                    self._wait_process[title] = {
                        "subject_id": subject_id,
                        "subject_name": subject_name,
                        "status": status,
                        "poster_path": poster_path,
                        "type": mediaType
                    }
                    self.save_data('folio_wait', self._wait_process)
                    error_msg = f'{title} 添加到待同步列表'
                    if 'The resource you requested could not be found.' in error_msg:
                        logger.error('请求的资源未找到（可能是条目不存在或ID错误）')
                    else:
                        logger.error(error_msg)
                self._send_folio_notification(False, f"《{title}》同步到豆瓣档案失败，请检查cookie或网络。")
        else:
            logger.warning(f"获取 {title} subject_id 失败，本条目不存在于豆瓣")
        return False

    def _send_folio_notification(self, success: bool, message: str):
        if not self._folio_notify:
            return
        title = f"豆瓣观影档案 {'成功' if success else '失败'}"
        text_content = message.strip()
        text_content += f"\n时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        try:
            self.post_message(mtype=NotificationType.MediaServer, title=title, text=text_content)
            logger.info(f"{self.plugin_name} 发送通知: {title}")
        except Exception as e:
            error_msg = f'{self.plugin_name} 发送通知失败: {e}'
            if 'The resource you requested could not be found.' in error_msg:
                logger.error('请求的资源未找到（可能是条目不存在或ID错误）')
            else:
                logger.error(error_msg)

    # ═══════════════════════════════════════════════════════════════
    # 即将播出
    # ═══════════════════════════════════════════════════════════════

    def __refresh_coming(self):
        rss_url = f"{self._coming_rss_domain.rstrip('/')}{self._coming_rss_path}"
        logger.info(f"开始刷新豆瓣即将播出RSS：{rss_url}")
        rss_infos = self.__get_coming_rss(rss_url)
        if not rss_infos:
            logger.error(f"RSS地址：{rss_url}，未查询到数据")
            return

        history: List[dict] = self.get_data("coming_history") or []
        unique_history = {item.get("unique") for item in history}

        logger.info(f"RSS地址：{rss_url}，获取 {len(rss_infos)} 条数据")
        for rss_info in rss_infos:
            title = rss_info.get("title") or ""
            link = rss_info.get("link") or ""
            wish_count = rss_info.get("wish_count", 0)
            rss_description = rss_info.get("description") or ""
            year = rss_info.get("year") or ""
            regions = rss_info.get("regions") or []
            genres = rss_info.get("genres") or []
            unique_flag = f"doubantvcoming:{link or title}"

            logger.info(f"标题：{title}，想看人数：{wish_count}，地区：{regions}，类型：{genres}")
            if unique_flag in unique_history:
                logger.info(f"{title} 已处理过")
                continue
            if wish_count < self._coming_min_wish:
                logger.info(f"{title} 想看人数 {wish_count} 未达到阈值 {self._coming_min_wish}")
                continue
            if not self.__match_any_filter(regions, self._coming_region_filters):
                logger.info(f"{title} 地区 {regions} 未命中已选筛选 {self._coming_region_filters}")
                continue
            if not self.__match_any_filter(genres, self._coming_genre_filters):
                logger.info(f"{title} 类型 {genres} 未命中已选筛选 {self._coming_genre_filters}")
                continue

            meta = MetaInfo(title)
            if year:
                meta.year = str(year)
            meta.type = MediaType.TV

            mediainfo: MediaInfo = self.chain.recognize_media(meta=meta, mtype=MediaType.TV)
            if not mediainfo:
                logger.warning(f"未识别到媒体信息，标题：{title}，链接：{link}")
                continue

            tmdb_air_date = self.__get_tmdb_air_date(mediainfo.tmdb_id, season=meta.begin_season)
            if not tmdb_air_date:
                logger.info(f"{title} 未获取到TMDB播出日期，跳过")
                continue
            if not self.__is_within_days(tmdb_air_date, self._coming_air_days):
                logger.info(f"{title} TMDB播出日期 {tmdb_air_date} 不在{self._coming_air_days}天内，跳过")
                continue

            downloadchain = DownloadChain()
            subscribechain = SubscribeChain()
            exist_flag, _ = downloadchain.get_no_exists_info(meta=meta, mediainfo=mediainfo)
            if exist_flag:
                logger.info(f"{mediainfo.title_year} 媒体库中已存在")
                continue
            if subscribechain.exists(mediainfo=mediainfo, meta=meta):
                logger.info(f"{mediainfo.title_year} 订阅已存在")
                continue

            sid, msg = subscribechain.add(
                title=mediainfo.title,
                year=mediainfo.year or year or "",
                mtype=MediaType.TV,
                tmdbid=mediainfo.tmdb_id,
                season=meta.begin_season,
                resolution=self.__build_resolution_rule(),
                sites=self._coming_subscribe_sites or None,
                exist_ok=True,
                username="豆瓣中心-即映",
                message=False
            )
            if not sid:
                logger.error(f"{title} 订阅失败：{msg}")
                continue

            if self._notify:
                self.post_message(
                    mtype=NotificationType.Subscribe,
                    title=f"豆瓣中心-即映：{mediainfo.title_year} Season {meta.begin_season if meta.begin_season else '1'} 已添加订阅",
                    text=(
                        f"播出时间：{tmdb_air_date}\n"
                        f"想看人数：{wish_count}\n"
                        f"豆瓣链接：{self.__build_douban_dispatch_link(link)}\n"
                        f"简介：{rss_description or mediainfo.overview or '暂无简介'}\n\n"
                        f"[豆瓣中心-即映]\n"
                    ),
                    image=mediainfo.get_message_image(),
                    link=settings.MP_DOMAIN("#/subscribe/tv?tab=mysub")
                )

            logger.info(f"{title} 想看人数 {wish_count}，已添加订阅")
            history.append({
                "title": title,
                "year": year,
                "wish_count": wish_count,
                "air_date": tmdb_air_date,
                "regions": regions,
                "genres": genres,
                "link": link,
                "tmdbid": mediainfo.tmdb_id,
                "poster": mediainfo.get_poster_image(),
                "overview": mediainfo.overview,
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "unique": unique_flag
            })
            unique_history.add(unique_flag)

        self.save_data("coming_history", history)
        logger.info("豆瓣即将播出RSS刷新完成\n")

    def __get_coming_rss(self, addr: str) -> List[dict]:
        try:
            if self._proxy:
                ret = RequestUtils(proxies=settings.PROXY).get_res(addr)
            else:
                ret = RequestUtils().get_res(addr)
            if not ret:
                return []

            dom_tree = xml.dom.minidom.parseString(ret.text)
            root_node = dom_tree.documentElement
            items = root_node.getElementsByTagName("item")

            ret_array = []
            for item in items:
                title = DomUtils.tag_value(item, "title", default="")
                link = DomUtils.tag_value(item, "link", default="")
                description = DomUtils.tag_value(item, "description", default="")
                category = DomUtils.tag_value(item, "category", default="")

                if not title and not link:
                    continue

                wish_count = self.__parse_wish_count(description)
                year = self.__parse_year(category)
                regions, genres = self.__parse_regions_and_genres(category)
                ret_array.append({
                    "title": title,
                    "link": link,
                    "description": description,
                    "wish_count": wish_count,
                    "year": year,
                    "regions": regions,
                    "genres": genres
                })
            return ret_array
        except Exception as err:
            logger.error(f"获取RSS失败：{err}")
            return []

    # ═══════════════════════════════════════════════════════════════
    # 榜单订阅
    # ═══════════════════════════════════════════════════════════════

    def __refresh_ranks(self):
        urls = []
        for rank_key in self._rank_ranks:
            if rank_key in self._douban_address:
                urls.append(self._douban_address[rank_key])
        urls.extend(self._rank_rss_addrs)

        if not urls:
            logger.info("未配置任何榜单或自定义RSS地址")
            return

        history: List[dict] = self.get_data("rank_history") or []
        unique_history = {item.get("unique") for item in history}

        for url in urls:
            url = url.strip()
            if not url:
                continue
            logger.info(f"开始处理榜单：{url}")
            rss_infos = self.__get_rank_rss(url)
            if not rss_infos:
                logger.warning(f"榜单 {url} 未获取到数据")
                continue

            for rss_info in rss_infos:
                title = rss_info.get("title", "")
                link = rss_info.get("link", "")
                mtype = rss_info.get("mtype", "")
                doubanid = rss_info.get("doubanid")
                year = rss_info.get("year")

                if not title:
                    continue

                unique_flag = f"doubanrank:{link or title}"
                if unique_flag in unique_history:
                    continue

                if self._rank_is_only_movies and mtype != "movie":
                    continue

                meta = MetaInfo(title)
                if year:
                    meta.year = str(year)
                meta.type = MediaType.MOVIE if mtype == "movie" else MediaType.TV

                mediainfo: MediaInfo = self.chain.recognize_media(meta=meta, mtype=meta.type)
                if not mediainfo:
                    logger.warning(f"未识别到媒体信息：{title}")
                    continue

                if self._rank_vote > 0 and mediainfo.vote_average and mediainfo.vote_average < self._rank_vote:
                    logger.info(f"{title} 评分 {mediainfo.vote_average} 低于阈值 {self._rank_vote}")
                    continue

                if self._rank_release_year > 0 and mediainfo.year and int(mediainfo.year) < self._rank_release_year:
                    logger.info(f"{title} 年份 {mediainfo.year} 早于 {self._rank_release_year}")
                    continue

                downloadchain = DownloadChain()
                subscribechain = SubscribeChain()
                exist_flag, _ = downloadchain.get_no_exists_info(meta=meta, mediainfo=mediainfo)
                if exist_flag:
                    logger.info(f"{mediainfo.title_year} 媒体库中已存在")
                    continue
                if subscribechain.exists(mediainfo=mediainfo, meta=meta):
                    logger.info(f"{mediainfo.title_year} 订阅已存在")
                    continue

                if meta.type == MediaType.TV and self._rank_is_seasons_all:
                    sid, msg = subscribechain.add(
                        title=mediainfo.title,
                        year=mediainfo.year or year or "",
                        mtype=MediaType.TV,
                        tmdbid=mediainfo.tmdb_id,
                        season=meta.begin_season,
                        exist_ok=True,
                        username="豆瓣中心-榜单",
                        message=False
                    )
                else:
                    sid, msg = subscribechain.add(
                        title=mediainfo.title,
                        year=mediainfo.year or year or "",
                        mtype=mediainfo.type if mediainfo.type else meta.type,
                        tmdbid=mediainfo.tmdb_id,
                        season=meta.begin_season if meta.type == MediaType.TV else None,
                        exist_ok=True,
                        username="豆瓣中心-榜单",
                        message=False
                    )

                if sid:
                    logger.info(f"{title} 已添加订阅")
                    if self._notify:
                        media_type_name = "电影" if (mediainfo.type == MediaType.MOVIE or meta.type == MediaType.MOVIE) else "电视剧"
                        self.post_message(
                            mtype=NotificationType.Subscribe,
                            title=f"豆瓣中心-榜单：{mediainfo.title_year} 已添加订阅",
                            text=(
                                f"类型：{media_type_name}\n"
                                f"来源榜单：{url}\n"
                                f"豆瓣链接：{self.__build_douban_dispatch_link(link)}\n\n"
                                f"[豆瓣中心-榜单]\n"
                            ),
                            image=mediainfo.get_message_image(),
                            link=settings.MP_DOMAIN("#/subscribe/tv?tab=mysub")
                        )
                    history.append({
                        "title": title,
                        "link": link,
                        "tmdbid": mediainfo.tmdb_id,
                        "poster": mediainfo.get_poster_image(),
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "unique": unique_flag
                    })
                    unique_history.add(unique_flag)
                else:
                    logger.error(f"{title} 订阅失败：{msg}")

                time.sleep(1)

        self.save_data("rank_history", history)
        logger.info("豆瓣榜单刷新完成\n")

    def __get_rank_rss(self, addr: str) -> List[dict]:
        try:
            if self._proxy:
                ret = RequestUtils(proxies=settings.PROXY).get_res(addr)
            else:
                ret = RequestUtils().get_res(addr)
            if not ret:
                return []

            dom_tree = xml.dom.minidom.parseString(ret.text)
            root_node = dom_tree.documentElement
            items = root_node.getElementsByTagName("item")

            ret_array = []
            for item in items:
                title = DomUtils.tag_value(item, "title", default="")
                link = DomUtils.tag_value(item, "link", default="")
                description = DomUtils.tag_value(item, "description", default="")

                if not title:
                    continue

                mtype = "movie"
                if re.search(r"第[一二三四五六七八九十\d]+季|Season\s*\d+", title, re.IGNORECASE):
                    mtype = "tv"

                doubanid = None
                if link:
                    match = re.search(r"/subject/(\d+)/?", link)
                    if match:
                        doubanid = match.group(1)

                year = None
                if description:
                    year_match = re.search(r"\b(19|20)\d{2}\b", description)
                    if year_match:
                        year = year_match.group(0)

                ret_array.append({
                    "title": title,
                    "link": link,
                    "mtype": mtype,
                    "doubanid": doubanid,
                    "year": year,
                })
            return ret_array
        except Exception as err:
            logger.error(f"获取榜单RSS失败：{err}")
            return []

    # ═══════════════════════════════════════════════════════════════
    # 工具方法
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def __parse_wish_count(description: str) -> int:
        if not description:
            return 0
        match = re.search(r"想看人数[：:]\s*([0-9,]+)", description)
        if not match:
            return 0
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return 0

    @staticmethod
    def __parse_year(category: str) -> str:
        if not category:
            return ""
        match = re.search(r"\b(19|20)\d{2}\b", category)
        if not match:
            return ""
        return match.group(0)

    @staticmethod
    def __parse_regions_and_genres(category: str) -> Tuple[List[str], List[str]]:
        if not category:
            return [], []
        parts = [p.strip() for p in category.split("/") if p.strip()]
        region_text = parts[1] if len(parts) > 1 else ""
        genre_text = parts[2] if len(parts) > 2 else ""
        regions = [x.strip() for x in re.split(r"[\s、,，]+", region_text) if x.strip()]
        genres = [x.strip() for x in re.split(r"[\s、,，]+", genre_text) if x.strip()]
        return regions, genres

    @staticmethod
    def __match_any_filter(item_values: List[str], selected_values: List[str]) -> bool:
        if not selected_values:
            return True
        return bool(set(item_values) & set(selected_values))

    @staticmethod
    def __normalize_rss_domain(raw_domain: str) -> str:
        domain = (raw_domain or "").strip()
        if not domain:
            return "https://rsshub.app"
        if "://" not in domain:
            domain = f"https://{domain}"
        parsed = urlparse(domain)
        netloc = parsed.netloc or parsed.path
        scheme = parsed.scheme or "https"
        return f"{scheme}://{netloc}".rstrip("/")

    def __build_resolution_rule(self) -> Optional[str]:
        if not self._coming_resolution_filters:
            return None
        if len(self._coming_resolution_filters) == 1:
            return self._coming_resolution_filters[0]
        return "|".join([f"(?:{item})" for item in self._coming_resolution_filters if item])

    def __get_tmdb_air_date(self, tmdb_id: Optional[int], season: Optional[int] = None) -> Optional[str]:
        if not tmdb_id:
            return None
        try:
            if season:
                season_info = self.chain.tmdb_info(tmdbid=tmdb_id, mtype=MediaType.TV, season=season)
                if season_info:
                    season_air_date = season_info.get("air_date") or season_info.get("first_air_date")
                    if season_air_date:
                        return season_air_date

            tmdb_info = self.chain.tmdb_info(tmdbid=tmdb_id, mtype=MediaType.TV)
            if not tmdb_info:
                return None

            if season:
                for season_item in tmdb_info.get("seasons", []) or []:
                    if season_item.get("season_number") == season and season_item.get("air_date"):
                        return season_item.get("air_date")

            return tmdb_info.get("first_air_date") or tmdb_info.get("release_date")
        except Exception as err:
            logger.error(f"获取TMDB播出日期失败：{err}")
            return None

    @staticmethod
    def __is_within_days(date_str: str, days: int) -> bool:
        try:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            today = datetime.datetime.now(pytz.timezone(settings.TZ)).date()
            diff_days = (target_date - today).days
            return 0 <= diff_days <= days
        except Exception:
            return False

    @staticmethod
    def __build_douban_dispatch_link(link: str) -> str:
        if not link:
            return ""
        match = re.search(r"/subject/(\d+)/?", link)
        if not match:
            return link
        subject_id = match.group(1)
        return f"https://www.douban.com/doubanapp/dispatch?uri=/movie/{subject_id}?from=mdouban&open=app"

    @staticmethod
    def _exclude_keyword(path: str, keywords: str) -> Dict[str, Any]:
        if not keywords:
            return {"ret": True, "message": "空关键词"}
        if not path:
            logger.warning('媒体路径为空,不执行过滤操作')
            return {"ret": True, "message": "媒体路径为空,不执行过滤操作"}
        keywords_list = re.split(r'[，,]', keywords)
        if any(k in path for k in keywords_list):
            return {"ret": False, "message": f"路径 {path} 包含 {keywords}"}
        return {"ret": True, "message": f"路径 {path} 不包含任何关键词 {keywords}"}

    @staticmethod
    def _format_title(title: str, season_id: int) -> str:
        if season_id > 1:
            return f"{title} 第{season_id}季"
        else:
            return title

    @staticmethod
    def is_mobile(user_agent):
        mobile_keywords = [
            'Mobile', 'Android', 'Silk/', 'Kindle', 'BlackBerry', 'Opera Mini', 'Opera Mobi', 'iPhone', 'iPad'
        ]
        for keyword in mobile_keywords:
            if re.search(keyword, user_agent, re.IGNORECASE):
                return True
        return False