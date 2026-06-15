"""
DownloadManagerLocal v3.0.13 - MoviePilot 本地插件
基于官方自动转移做种 v1.10.3，整合 IYUU 自动辅种，支持转移后自动重命名 + 打站点标签
"""
import os
import re
from datetime import datetime, timedelta
import time
from pathlib import Path
from threading import Event as ThreadEvent
import threading
from typing import Any, List, Dict, Tuple, Optional, Union
from urllib.parse import urljoin

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from bencode import bdecode, bencode
from lxml import etree

from app.core.config import settings
from app.core.event import eventmanager, Event
from app.core.meta.metabase import MetaBase
from app.core.metainfo import MetaInfo
from app.db.site_oper import SiteOper
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.downloader import DownloaderHelper
from app.helper.sites import SitesHelper
from app.helper.torrent import TorrentHelper
from app.log import logger
from app.modules.filemanager.transhandler import TransHandler
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.plugins import _PluginBase
from app.plugins.downloadmanagerlocal.iyuu_helper import IyuuHelper
from app.schemas import NotificationType, ServiceInfo
from app.schemas.types import MediaType, SystemConfigKey, EventType
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class DownloadManagerLocal(_PluginBase):
    # 插件名称
    plugin_name = "下载管理"
    # 插件描述
    plugin_desc = "转移做种 + IYUU辅种 + 种子重命名 + 站点标签，一站式下载管理。"
    # 插件图标
    plugin_icon = "download.png"
    # 插件颜色
    plugin_color = "#4CAF50"
    # 插件版本
    plugin_version = "3.0.17"
    # 插件作者
    plugin_author = "牧濑红莉栖"
    # 作者主页
    author_url = "https://raw.githubusercontent.com/z2561221/MoviePilot-Plugins/main/icons/author-avatars/kurisu"
    # 插件配置项ID前缀
    plugin_config_prefix = "downloadmanagerlocal_"
    # 加载顺序
    plugin_order = 18
    # 可使用的用户级别
    auth_level = 2

    # 私有属性
    _scheduler = None

    # ── 转移做种配置 ──
    _enabled = False
    _transfer_enabled = True
    _delay_minutes = 25
    _transfer_fallback_enabled = True
    _transfer_fallback_interval_minutes = 60
    _onlyonce = False
    _fromdownloader = None
    _todownloader = None
    _frompath = None
    _topath = None
    _notify = False
    _nolabels = None
    _includelabels = None
    _includecategory = None
    _nopaths = None
    _deletesource = False
    _deleteduplicate = False
    _fromtorrentpath = None
    _transferemptylabel = False
    _add_torrent_tags = None
    _remainoldcat = False
    _remainoldtag = False
    _seed_autostart: bool = True
    _seed_skipverify: bool = False
    _seed_check_interval: int = 60
    _seed_max_wait_minutes: int = 120


    # ── 重命名配置 ──
    _rename_enabled: bool = True
    _rename_movie_format: str = "[ {{ title }}{% if year %} ({{ year }}){% endif %} ] - {{original_name}}"
    _rename_tv_format: str = "[ {{ title }}{% if year %} ({{ year }}){% endif %}{% if season_episode %} - {{season_episode}}{% endif %} ] - {{original_name}}"
    _rename_exclude_dirs: str = ""

    # ── 站点标签配置 ──
    _tag_enabled: bool = True
    _tag_siteprefix: str = "🏠"
    _tag_tracker_mappings_str: str = ""

    # ── IYUU 辅种配置 ──
    _iyuu_enabled: bool = False
    _iyuu_cron: str = ""
    _iyuu_onlyonce: bool = False
    _iyuu_token: str = ""
    _iyuu_downloaders: list = []
    _iyuu_auto_downloader: str = ""
    _iyuu_sites: list = []
    _iyuu_nolabels: str = ""
    _iyuu_nopaths: str = ""
    _iyuu_size: float = 0
    _iyuu_auto_category: bool = False
    _iyuu_labelsafterseed: str = "已整理,辅种"
    _iyuu_categoryafterseed: str = ""
    _iyuu_clearcache: bool = False
    # IYUU 辅种缓存
    _iyuu_error_caches: list = []
    _iyuu_success_caches: list = []
    _iyuu_permanent_error_caches: list = []
    _iyuu_seed_cache_max: int = 10000
    # IYUU 辅种计数
    _iyuu_total: int = 0
    _iyuu_realtotal: int = 0
    _iyuu_success: int = 0
    _iyuu_exist: int = 0
    _iyuu_fail: int = 0
    _iyuu_cached: int = 0
    # IYUU 种子链接 xpaths
    _iyuu_torrent_xpaths: list = [
        "//form[contains(@action, 'download.php?id=')]/@action",
        "//a[contains(@href, 'download.php?hash=')]/@href",
        "//a[contains(@href, 'download.php?id=')]/@href",
        "//a[@class='index'][contains(@href, '/dl/')]/@href",
    ]

    # 退出事件
    _event = ThreadEvent()
    # 待检查种子清单：{下载器名: {hash: 来源}}
    _recheck_torrents = {}
    _is_recheck_running = False
    _seed_recheck_running = False
    _seed_recheck_lock = threading.RLock()
    _seed_recheck_queue_key = "seed_recheck_queue"

    # 任务标签
    _torrent_tags = []
    # tracker 映射
    _tracker_mappings: Dict[str, str] = {}

    # 辅助
    downloader_helper = None

    def init_plugin(self, config: dict = None):
        self.downloader_helper = DownloaderHelper()

        # 默认 tracker 映射
        default_mappings = (
            "chdbits.xyz -> ptchdbits.co\n"
            "agsvpt.trackers.work -> agsvpt.com\n"
            "tracker.cinefiles.info -> audiences.me"
        )
        self._tracker_mappings = self._parse_tracker_mappings(default_mappings)

        # 读取配置
        if config:
            self._enabled = config.get("enabled")
            self._transfer_enabled = config.get("transfer_enabled", True)
            self._onlyonce = config.get("onlyonce")
            self._delay_minutes = config.get("delay_minutes", 25)
            self._transfer_fallback_enabled = config.get("transfer_fallback_enabled", True)
            try:
                self._transfer_fallback_interval_minutes = max(1, int(config.get("transfer_fallback_interval_minutes") or 60))
            except (TypeError, ValueError):
                self._transfer_fallback_interval_minutes = 60
            self._notify = config.get("notify")
            self._nolabels = config.get("nolabels")
            self._includelabels = config.get("includelabels")
            self._includecategory = config.get("includecategory")
            self._frompath = config.get("frompath")
            self._topath = config.get("topath")
            self._fromdownloader = config.get("fromdownloader")
            self._todownloader = config.get("todownloader")
            self._deletesource = config.get("deletesource")
            self._deleteduplicate = config.get("deleteduplicate")
            self._fromtorrentpath = config.get("fromtorrentpath")
            self._nopaths = config.get("nopaths")
            self._transferemptylabel = config.get("transferemptylabel")
            self._add_torrent_tags = config.get("add_torrent_tags") or ""
            self._torrent_tags = self._add_torrent_tags.strip().split(",") if self._add_torrent_tags else []
            self._remainoldcat = config.get("remainoldcat")
            self._remainoldtag = config.get("remainoldtag")
            self._seed_autostart = config.get("seed_autostart", True)
            self._seed_skipverify = config.get("seed_skipverify", False)
            self._seed_check_interval = self.__safe_int(config.get("seed_check_interval"), 60, 10, 3600)
            self._seed_max_wait_minutes = self.__safe_int(config.get("seed_max_wait_minutes"), 120, 10, 1440)


            # 重命名配置
            self._rename_enabled = config.get("rename_enabled", True)
            self._rename_movie_format = config.get("rename_movie_format",
                "[ {{ title }}{% if year %} ({{ year }}){% endif %} ] - {{original_name}}")
            self._rename_tv_format = config.get("rename_tv_format",
                "[ {{ title }}{% if year %} ({{ year }}){% endif %}{% if season_episode %} - {{season_episode}}{% endif %} ] - {{original_name}}")
            self._rename_exclude_dirs = config.get("rename_exclude_dirs", "")

            # 站点标签配置
            self._tag_enabled = config.get("tag_enabled", True)
            self._tag_siteprefix = config.get("tag_siteprefix", "🏠")
            self._tag_tracker_mappings_str = config.get("tag_tracker_mappings_str", "")
            if self._tag_tracker_mappings_str:
                self._tracker_mappings.update(self._parse_tracker_mappings(self._tag_tracker_mappings_str))

            # IYUU 辅种配置
            self._iyuu_enabled = config.get("iyuu_enabled", False)
            self._iyuu_cron = config.get("iyuu_cron", "")
            self._iyuu_onlyonce = config.get("iyuu_onlyonce", False)
            self._iyuu_token = config.get("iyuu_token", "")
            self._iyuu_downloaders = config.get("iyuu_downloaders") or []
            self._iyuu_auto_downloader = config.get("iyuu_auto_downloader", "")
            self._iyuu_sites = config.get("iyuu_sites") or []
            self._iyuu_nolabels = config.get("iyuu_nolabels", "")
            self._iyuu_nopaths = config.get("iyuu_nopaths", "")
            self._iyuu_size = float(config.get("iyuu_size")) if config.get("iyuu_size") else 0
            self._iyuu_auto_category = config.get("iyuu_auto_category", False)
            self._iyuu_labelsafterseed = config.get("iyuu_labelsafterseed") or "已整理,辅种"
            self._iyuu_categoryafterseed = config.get("iyuu_categoryafterseed", "")
            self._iyuu_clearcache = config.get("iyuu_clearcache", False)
            self._iyuu_permanent_error_caches = [] if self._iyuu_clearcache else list(config.get("iyuu_permanent_error_caches") or [])
            self._iyuu_error_caches = [] if self._iyuu_clearcache else list(config.get("iyuu_error_caches") or [])
            self._iyuu_success_caches = [] if self._iyuu_clearcache else list(config.get("iyuu_success_caches") or [])
            if self._iyuu_clearcache:
                # 立即持久化清空后的缓存到 config
                config["iyuu_permanent_error_caches"] = []
                config["iyuu_error_caches"] = []
                config["iyuu_success_caches"] = []
                self._iyuu_clearcache = False
                config["iyuu_clearcache"] = False
                self.update_config(config=config)
                logger.info("IYUU辅种：已清除所有辅种缓存")
            self._trim_seed_cache(self._iyuu_permanent_error_caches)
            self._trim_seed_cache(self._iyuu_error_caches)
            self._trim_seed_cache(self._iyuu_success_caches)

            # 过滤掉已删除的站点
            if self._iyuu_sites:
                all_site_ids = [site.id for site in SiteOper().list_order_by_pri()] + [site.get("id") for site in self._custom_sites()]
                self._iyuu_sites = [sid for sid in all_site_ids if sid in self._iyuu_sites]
                self._update_iyuu_config(config)

        # 停止现有任务
        self.stop_service()

        # 启动转移做种服务（事件驱动）
        if self._transfer_active or self._onlyonce:
            if not self.__validate_config():
                self._enabled = False
                self._onlyonce = False
                config["enabled"] = self._enabled
                config["onlyonce"] = self._onlyonce
                self.update_config(config=config)
                return

            self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            if self._onlyonce:
                logger.info(f"转移做种服务启动，立即运行一次")
                self._scheduler.add_job(self.transfer, 'date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3))
                self._onlyonce = False
                config["onlyonce"] = self._onlyonce
                self.update_config(config=config)

            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                if not self._scheduler.running:
                    self._scheduler.start()

        # 启动 IYUU 辅种服务（cron 定时）
        if self._iyuu_enabled and self._iyuu_token and self._iyuu_downloaders:
            self.iyuu_helper = IyuuHelper(token=self._iyuu_token)
            if not self._scheduler:
                self._scheduler = BackgroundScheduler(timezone=settings.TZ)

            if self._iyuu_onlyonce:
                logger.info(f"IYUU辅种服务启动，立即运行一次")
                self._scheduler.add_job(self.iyuu_auto_seed, 'date',
                                        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=5))
                self._iyuu_onlyonce = False
                config["iyuu_onlyonce"] = self._iyuu_onlyonce
                self.update_config(config=config)

            if self._scheduler.get_jobs() and not self._scheduler.running:
                self._scheduler.start()


    @staticmethod
    def __safe_int(value, default, min_value, max_value):
        try:
            ivalue = int(float(value))
        except Exception:
            ivalue = default
        return max(min_value, min(max_value, ivalue))

    @staticmethod
    def _parse_tracker_mappings(mapping_str: str) -> dict:
        result = {}
        if not mapping_str:
            return result
        for line in mapping_str.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            for sep in ('->', '\u2192', ':', '\uff1a'):
                if sep in line:
                    parts = line.split(sep, 1)
                    if len(parts) == 2:
                        k, v = parts[0].strip(), parts[1].strip()
                        if k and v:
                            result[k] = v
                    break
        return result

    @staticmethod
    def service_info(name: str) -> Optional[ServiceInfo]:
        """
        服务信息
        """
        if not name:
            logger.warning("尚未配置下载器，请检查配置")
            return None

        service = DownloaderHelper().get_service(name)
        if not service or not service.instance:
            logger.warning(f"获取下载器 {name} 实例失败，请检查配置")
            return None

        if service.instance.is_inactive():
            logger.warning(f"下载器 {name} 未连接，请检查配置")
            return None

        return service

    def get_state(self):
        return True if self._enabled \
                       and self._fromdownloader \
                       and self._todownloader \
                       and self._fromtorrentpath else False

    @property
    def _transfer_active(self) -> bool:
        """转移做种功能是否激活（总开关 + 转移开关 + 配置完整）"""
        return self._enabled and self._transfer_enabled \
               and self._fromdownloader and self._todownloader and self._fromtorrentpath

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/downloaders",
                "endpoint": self.api_downloaders,
                "auth": "bear",
                "methods": ["GET"],
                "summary": "获取下载器列表",
            },
            {
                "path": "/rename_history",
                "endpoint": self.api_rename_history,
                "auth": "bear",
                "methods": ["GET"],
                "summary": "获取重命名历史",
            },
            {
                "path": "/delete_rename_history",
                "endpoint": self.api_delete_rename_history,
                "auth": "bear",
                "methods": ["POST"],
                "summary": "删除重命名历史记录",
            },
            {
                "path": "/recovery_torrent",
                "endpoint": self.api_recovery_torrent,
                "auth": "bear",
                "methods": ["POST"],
                "summary": "恢复种子原始名称",
            },
            {
                "path": "/sites",
                "endpoint": self.api_sites,
                "auth": "bear",
                "methods": ["GET"],
                "summary": "获取站点列表（用于辅种站点选择）",
            },
        ]

    def api_downloaders(self):
        """返回可用下载器列表"""
        try:
            services = self.downloader_helper.get_services()
            result = []
            if services:
                for name, info in services.items():
                    result.append({
                        "title": name,
                        "value": name,
                    })
            return {"data": result}
        except Exception as e:
            logger.error(f"获取下载器列表失败: {e}")
            return {"data": []}

    def api_sites(self):
        """返回可用站点列表（内置站点 + 自定义站点）"""
        try:
            custom_sites = self._custom_sites()
            result = [{"title": site.name, "value": site.id}
                      for site in SiteOper().list_order_by_pri()]
            result += [{"title": site.get("name"), "value": site.get("id")}
                       for site in custom_sites]
            return {"data": result}
        except Exception as e:
            logger.error(f"获取站点列表失败: {e}")
            return {"data": []}

    def api_rename_history(self):
        """返回重命名历史记录"""
        records = self.get_data("rename_records") or {}
        result = sorted(records.values(), key=lambda x: x.get("time", ""), reverse=True)
        return {"data": result}

    def api_delete_rename_history(self, hash: str = ""):
        """删除指定 hash 的重命名记录"""
        records = self.get_data("rename_records") or {}
        if hash in records:
            del records[hash]
            self.save_data("rename_records", records)
            return {"code": 0, "msg": "已删除"}
        return {"code": 1, "msg": "记录不存在"}

    def api_recovery_torrent(self, hash: str = ""):
        """恢复种子原始名称"""
        if not hash:
            return {"code": 1, "msg": "缺少 hash 参数"}
        records = self.get_data("rename_records") or {}
        record = records.get(hash)
        if not record or not record.get("success"):
            return {"code": 1, "msg": "未找到成功的重命名记录"}
        original_name = record.get("original_name")
        if not original_name:
            return {"code": 1, "msg": "原始名称为空"}

        # 在目标下载器中查找并恢复
        try:
            dl_helper = DownloaderHelper()
            to_config = dl_helper.get_config(self._todownloader)
            if not to_config:
                return {"code": 1, "msg": f"下载器 {self._todownloader} 不存在"}
            dl = to_config.instance
            dl_type = to_config.type

            if dl_type == "qbittorrent":
                dl.qbc.torrents_rename(torrent_hash=hash, new_torrent_name=original_name)
            else:
                dl.rename_torrent(hash, original_name)

            # 更新记录
            record["after_name"] = original_name
            record["success"] = True
            record["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            records[hash] = record
            self.save_data("rename_records", records)
            logger.info(f"种子恢复成功: {hash} → {original_name}")
            return {"code": 0, "msg": f"已恢复为: {original_name}"}
        except Exception as e:
            logger.error(f"种子恢复失败: {e}")
            return {"code": 1, "msg": str(e)}

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        """
        services = []
        # 做种校验：改为按需触发，不再注册固定周期服务
        # 转移做种兜底服务：事件漏触发时，按自定义间隔低频扫描 QB1 已完成任务
        if self._transfer_active and self._transfer_fallback_enabled:
            services.append({
                "id": "TorrentTransferFallback",
                "name": "转移做种兜底服务",
                "trigger": "interval",
                "func": self._fallback_transfer,
                "kwargs": {"minutes": self._transfer_fallback_interval_minutes}
            })
        # IYUU 辅种服务
        if self._iyuu_enabled and self._iyuu_cron and self._iyuu_token and self._iyuu_downloaders:
            services.append({
                "id": "IYUUAutoSeed",
                "name": "IYUU自动辅种服务",
                "trigger": CronTrigger.from_crontab(self._iyuu_cron),
                "func": self.iyuu_auto_seed,
                "kwargs": {}
            })
        return services

    def _fallback_transfer(self):
        """转移做种兜底扫描包装函数，避免把业务参数混入调度器 interval 参数。"""
        self.transfer(trigger_source="兜底扫描")


    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """返回渲染模式：vue 联邦组件模式"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """Vue 模式下表单由前端组件渲染"""
        return None, {
            "enabled": False, "transfer_enabled": True, "notify": False, "onlyonce": False, "delay_minutes": 25,
            "transfer_fallback_enabled": True, "transfer_fallback_interval_minutes": 60,
            "nolabels": "", "includelabels": "", "includecategory": "",
            "frompath": "", "topath": "", "fromdownloader": "", "todownloader": "",
            "deletesource": False, "deleteduplicate": False, "fromtorrentpath": "",
            "nopaths": "",
            "transferemptylabel": False, "add_torrent_tags": "⏩转种",
            "remainoldcat": False, "remainoldtag": False,
            "rename_enabled": True,
            "rename_movie_format": "[ {{ title }}{% if year %} ({{ year }}){% endif %} ] - {{original_name}}",
            "rename_tv_format": "[ {{ title }}{% if year %} ({{ year }}){% endif %}{% if season_episode %} - {{season_episode}}{% endif %} ] - {{original_name}}",
            "rename_exclude_dirs": "",
            "tag_enabled": True, "tag_siteprefix": "🏠", "tag_tracker_mappings_str": "",
            # IYUU 辅种
            "iyuu_enabled": False, "iyuu_cron": "", "iyuu_onlyonce": False,
            "iyuu_token": "", "iyuu_downloaders": [], "iyuu_auto_downloader": "",
            "iyuu_sites": [], "iyuu_nolabels": "", "iyuu_nopaths": "",
            "iyuu_size": 0, "iyuu_auto_category": False,
            "iyuu_labelsafterseed": "已整理,辅种", "iyuu_categoryafterseed": "",
            "seed_autostart": True, "seed_skipverify": False,
            "seed_check_interval": 60, "seed_max_wait_minutes": 120,
            "iyuu_clearcache": False,
        }

    def get_page(self) -> Optional[List[dict]]:
        """Vue 模式下无详情页"""
        return None

    def __validate_config(self) -> bool:
        """
        校验配置
        """
        # 检查配置
        if self._fromtorrentpath and not Path(self._fromtorrentpath).exists():
            logger.error(f"源下载器种子文件保存路径不存在：{self._fromtorrentpath}")
            self.systemmessage.put(f"源下载器种子文件保存路径不存在：{self._fromtorrentpath}", title="自动转移做种")
            return False
        if self._fromdownloader == self._todownloader:
            logger.error(f"源下载器和目的下载器不能相同")
            self.systemmessage.put(f"源下载器和目的下载器不能相同", title="自动转移做种")
            return False
        return True

    def __download(self, service: ServiceInfo, content: bytes,
                   save_path: str, torrent) -> Optional[str]:
        """
        添加下载任务
        """
        if not service or not service.instance:
            return
        downloader = service.instance
        from_service = self.service_info(self._fromdownloader)
        downloader_helper = DownloaderHelper()
        if downloader_helper.is_downloader("qbittorrent", service=service):
            # 生成随机Tag
            tag = StringUtils.generate_random_str(10)
            if self._remainoldtag:
                # 获取种子标签
                torrent_labels = self.__get_label(torrent, from_service.type)
                new_tag = list(set(torrent_labels + self._torrent_tags + [tag]))
            else:
                new_tag = self._torrent_tags + [tag]
            if self._remainoldcat:
                # 获取种子分类
                torrent_category = self.__get_category(torrent, from_service.type)
            else:
                torrent_category = None
            state = downloader.add_torrent(content=content,
                                           download_dir=save_path,
                                           is_paused=True,
                                           tag=new_tag,
                                           category=torrent_category,
                                           is_skip_checking=self._seed_skipverify)
            if not state:
                return None
            else:
                # 获取种子Hash
                torrent_hash = downloader.get_torrent_id_by_tag(tags=tag)
                if not torrent_hash:
                    logger.error(f"{downloader} 下载任务添加成功，但获取任务信息失败！")
                    return None
            return torrent_hash
        elif downloader_helper.is_downloader("transmission", service=service):
            # 添加任务
            if self._remainoldtag:
                # 获取种子标签
                torrent_labels = self.__get_label(torrent, from_service.type)
                new_tag = list(set(torrent_labels + self._torrent_tags))
            else:
                new_tag = self._torrent_tags
            torrent = downloader.add_torrent(content=content,
                                             download_dir=save_path,
                                             is_paused=True,
                                             labels=new_tag)
            if not torrent:
                return None
            else:
                return torrent.hashString

        logger.error(f"不支持的下载器类型")
        return None

    def transfer(self, trigger_source: str = "手动/定时"):
        """
        开始转移做种
        """
        logger.info(f"开始转移做种任务，触发来源：{trigger_source} ...")

        if not self.__validate_config():
            return

        from_service = self.service_info(self._fromdownloader)
        from_downloader: Optional[Union[Qbittorrent, Transmission]] = from_service.instance if from_service else None
        to_service = self.service_info(self._todownloader)
        to_downloader: Optional[Union[Qbittorrent, Transmission]] = to_service.instance if to_service else None

        if not from_downloader or not to_downloader:
            return

        torrents = from_downloader.get_completed_torrents()
        if torrents:
            logger.info(f"下载器 {from_service.name} 已做种的种子数：{len(torrents)}")
        else:
            logger.info(f"下载器 {from_service.name} 没有已做种的种子")
            return

        # 过滤种子，记录保存目录
        trans_torrents = []
        for torrent in torrents:
            if self._event.is_set():
                logger.info(f"转移服务停止")
                return

            # 获取种子hash
            hash_str = self.__get_hash(torrent, from_service.type)
            # 获取保存路径
            save_path = self.__get_save_path(torrent, from_service.type)

            if self._nopaths and save_path:
                # 过滤不需要转移的路径
                nopath_skip = False
                for nopath in self._nopaths.split('\n'):
                    if os.path.normpath(save_path).startswith(os.path.normpath(nopath)):
                        logger.info(f"种子 {hash_str} 保存路径 {save_path} 不需要转移，跳过 ...")
                        nopath_skip = True
                        break
                if nopath_skip:
                    continue

            # 获取种子标签
            torrent_labels = self.__get_label(torrent, from_service.type)
            # 获取种子分类
            torrent_category = self.__get_category(torrent, from_service.type)
            # 种子为无标签,则进行规范化
            is_torrent_labels_empty = torrent_labels == [''] or torrent_labels == [] or torrent_labels is None
            if is_torrent_labels_empty:
                torrent_labels = []

            # 如果分类项存在数值，则进行判断
            if self._includecategory:
                # 排除未标记的分类
                if torrent_category not in self._includecategory.split(','):
                    logger.info(f"种子 {hash_str} 不含有转移分类 {self._includecategory}，跳过 ...")
                    continue
            # 根据设置决定是否转移无标签的种子
            if is_torrent_labels_empty:
                if not self._transferemptylabel:
                    continue
            else:
                # 排除含有不转移的标签
                if self._nolabels:
                    is_skip = False
                    for label in self._nolabels.split(','):
                        if label in torrent_labels:
                            logger.info(f"种子 {hash_str} 含有不转移标签 {label}，跳过 ...")
                            is_skip = True
                            break
                    if is_skip:
                        continue
                # 排除不含有转移标签的种子
                if self._includelabels:
                    is_skip = False
                    for label in self._includelabels.split(','):
                        if label not in torrent_labels:
                            logger.info(f"种子 {hash_str} 不含有转移标签 {label}，跳过 ...")
                            is_skip = True
                            break
                    if is_skip:
                        continue

            # 添加转移数据
            trans_torrents.append({
                "hash": hash_str,
                "save_path": save_path,
                "torrent": torrent
            })

        # 开始转移任务
        if trans_torrents:
            logger.info(f"需要转移的种子数：{len(trans_torrents)}")
            # 记数
            total = len(trans_torrents)
            # 总成功数
            success = 0
            # 总失败数
            fail = 0
            # 跳过数
            skip = 0
            # 删除重复数
            del_dup = 0

            downloader_helper = DownloaderHelper()
            for torrent_item in trans_torrents:
                # 检查种子文件是否存在
                torrent_file = Path(self._fromtorrentpath) / f"{torrent_item.get('hash')}.torrent"
                if not torrent_file.exists():
                    logger.error(f"种子文件不存在：{torrent_file}")
                    # 失败计数
                    fail += 1
                    continue

                # 查询hash值是否已经在目的下载器中
                torrent_info, _ = to_downloader.get_torrents(ids=[torrent_item.get('hash')])
                if torrent_info:
                    # 删除重复的源种子，不能删除文件！
                    if self._deleteduplicate:
                        logger.info(f"删除重复的源下载器任务（不含文件）：{torrent_item.get('hash')} ...")
                        from_downloader.delete_torrents(delete_file=False, ids=[torrent_item.get('hash')])
                        del_dup += 1
                    else:
                        logger.info(f"{torrent_item.get('hash')} 已在目的下载器中，跳过 ...")
                        # 跳过计数
                        skip += 1
                    continue

                # 转换保存路径
                download_dir = self.__convert_save_path(torrent_item.get('save_path'),
                                                        self._frompath,
                                                        self._topath)
                if not download_dir:
                    logger.error(f"转换保存路径失败：{torrent_item.get('save_path')}")
                    # 失败计数
                    fail += 1
                    continue

                # 如果源下载器是QB检查是否有Tracker，没有的话额外获取
                if downloader_helper.is_downloader("qbittorrent", service=from_service):
                    # 读取种子内容、解析种子文件
                    content = torrent_file.read_bytes()
                    if not content:
                        logger.warning(f"读取种子文件失败：{torrent_file}")
                        fail += 1
                        continue
                    # 读取trackers
                    try:
                        torrent_main = bdecode(content)
                        main_announce = torrent_main.get('announce')
                    except Exception as err:
                        logger.warning(f"解析种子文件 {torrent_file} 失败：{str(err)}")
                        fail += 1
                        continue

                    if not main_announce:
                        logger.info(f"{torrent_item.get('hash')} 未发现tracker信息，尝试补充tracker信息...")
                        # 读取fastresume文件
                        fastresume_file = Path(self._fromtorrentpath) / f"{torrent_item.get('hash')}.fastresume"
                        if not fastresume_file.exists():
                            logger.warning(f"fastresume文件不存在：{fastresume_file}")
                            fail += 1
                            continue
                        # 尝试补充trackers
                        try:
                            # 解析fastresume文件
                            fastresume = fastresume_file.read_bytes()
                            torrent_fastresume = bdecode(fastresume)
                            # 读取trackers
                            fastresume_trackers = torrent_fastresume.get('trackers')
                            if isinstance(fastresume_trackers, list) \
                                    and len(fastresume_trackers) > 0 \
                                    and fastresume_trackers[0]:
                                # 重新赋值
                                torrent_main['announce'] = fastresume_trackers[0][0]
                                # 保留其他tracker，避免单一tracker无法连接
                                if len(fastresume_trackers) > 1 or len(fastresume_trackers[0]) > 1:
                                    torrent_main['announce-list'] = fastresume_trackers
                                # 替换种子文件路径
                                torrent_file = settings.TEMP_PATH / f"{torrent_item.get('hash')}.torrent"
                                # 编码并保存到临时文件
                                torrent_file.write_bytes(bencode(torrent_main))
                        except Exception as err:
                            logger.error(f"解析fastresume文件 {fastresume_file} 出错：{str(err)}")
                            fail += 1
                            continue

                # 发送到另一个下载器中下载：默认暂停、传输下载路径、关闭自动管理模式
                logger.info(f"添加转移做种任务到下载器 {to_service.name}：{torrent_file}")
                download_id = self.__download(service=to_service,
                                              content=torrent_file.read_bytes(),
                                              save_path=download_dir,
                                              torrent=torrent_item.get('torrent'))
                if not download_id:
                    # 下载失败
                    fail += 1
                    logger.error(f"添加下载任务失败：{torrent_file}")
                    continue
                else:
                    # 下载成功
                    logger.info(f"成功添加转移做种任务，种子文件：{torrent_file}")

                    # ── v2.0.0: 转移后立即重命名 + 打站点标签 ──
                    self._post_transfer_process(to_service, download_id)

                    # TR会自动校验，QB需要手动校验
                    if downloader_helper.is_downloader("qbittorrent", service=to_service):
                        if self._seed_skipverify:
                            if self._seed_autostart:
                                logger.info(f"{download_id} 跳过校验，开启自动开始，注意观察种子的完整性")
                                self._register_seed_recheck(to_service.name, [download_id], "transfer")
                            else:
                                logger.info(f"{download_id} 跳过校验，请自行检查手动开始任务...")
                        else:
                            logger.info(f"qbittorrent 开始校验 {download_id} ...")
                            to_downloader.recheck_torrents(ids=[download_id])
                            self._register_seed_recheck(to_service.name, [download_id], "transfer")
                    else:
                        self._register_seed_recheck(to_service.name, [download_id], "transfer")

                    # 删除源种子，不能删除文件！
                    if self._deletesource:
                        logger.info(f"删除源下载器任务（不含文件）：{torrent_item.get('hash')} ...")
                        from_downloader.delete_torrents(delete_file=False, ids=[torrent_item.get('hash')])

                    # 成功计数
                    success += 1
                    # 插入转种记录
                    history_key = f"{from_service.name}-{torrent_item.get('hash')}"
                    self.save_data(key=history_key,
                                   value={
                                       "to_download": to_service.name,
                                       "to_download_id": download_id,
                                       "delete_source": self._deletesource,
                                       "delete_duplicate": self._deleteduplicate,
                                   })
            # 触发校验任务（已由 _register_seed_recheck 按需处理）

            # 发送通知
            if self._notify:
                self.post_message(
                    mtype=NotificationType.SiteMessage,
                    title="【转移做种任务执行完成】",
                    text=f"总数：{total}，成功：{success}，失败：{fail}，跳过：{skip}，删除重复：{del_dup}"
                )
        else:
            logger.info(f"没有需要转移的种子")

        # ── v2.0.0: 补刀之前重命名失败的种子（无论是否有新转移）──
        self._retry_failed_renames(to_service)

        logger.info("转移做种任务执行完成")

    def __add_recheck_torrents(self, service: ServiceInfo, download_id: str, source: str = "未知来源"):
        """追加做种校验任务，记录来源用于日志区分。"""
        if not service or not download_id:
            return
        logger.info(f"做种校验服务：添加校验任务 [{source}] {service.name} / {download_id} ...")
        if not isinstance(self._recheck_torrents.get(service.name), dict):
            self._recheck_torrents[service.name] = {}
        self._recheck_torrents[service.name][download_id] = source or "未知来源"

    def check_recheck(self):
        """
        定时检查下载器中种子是否校验完成，校验完成且完整的自动开始辅种。
        同时执行队列外兜底扫描，处理插件重载后丢失队列的历史暂停任务。
        """
        if self._is_recheck_running:
            return

        self._is_recheck_running = True
        try:
            # 收集所有需要检查的下载器
            check_services = []
            seen_services = set()

            def add_check_service(svc: Optional[ServiceInfo]):
                if not svc or not svc.instance or svc.name in seen_services:
                    return
                check_services.append(svc)
                seen_services.add(svc.name)

            # 转移做种目标下载器
            if self._todownloader:
                add_check_service(self.service_info(self._todownloader))

            # IYUU 辅种下载器
            if self._iyuu_enabled and self._iyuu_downloaders:
                dl_helper = DownloaderHelper()
                for name in self._iyuu_downloaders:
                    svc = dl_helper.get_service(name)
                    if svc and not svc.instance.is_inactive():
                        add_check_service(svc)

            if not check_services:
                return

            # 队列内检查：只在存在待校验任务时执行
            if self._recheck_torrents:
                for svc in check_services:
                    recheck_items = self._recheck_torrents.get(svc.name, {})
                    if isinstance(recheck_items, list):
                        # 兼容旧版本运行期队列
                        recheck_items = {hash_id: "历史队列" for hash_id in recheck_items}
                        self._recheck_torrents[svc.name] = recheck_items
                    if not recheck_items:
                        continue

                    recheck_torrents = list(recheck_items.keys())
                    logger.info(f"做种校验服务：开始检查下载器 {svc.name} 的校验任务，共 {len(recheck_torrents)} 个 ...")
                    to_downloader = svc.instance
                    torrents, _ = to_downloader.get_torrents(ids=recheck_torrents)
                    if torrents:
                        can_seeding_torrents = []
                        source_counts = {}
                        for torrent in torrents:
                            hash_str = self.__get_hash(torrent, svc.type)
                            if self.__can_seeding(torrent, svc.type):
                                can_seeding_torrents.append(hash_str)
                                source = recheck_items.get(hash_str, "未知来源")
                                source_counts[source] = source_counts.get(source, 0) + 1

                        if can_seeding_torrents:
                            source_text = "，".join([f"{source} {count} 个" for source, count in source_counts.items()]) or f"{len(can_seeding_torrents)} 个"
                            logger.info(f"做种校验服务：下载器 {svc.name} 中 {source_text} 任务校验完成，开始做种")
                            to_downloader.start_torrents(ids=can_seeding_torrents)
                            for hash_id in can_seeding_torrents:
                                recheck_items.pop(hash_id, None)
                            self._recheck_torrents[svc.name] = recheck_items
                        else:
                            logger.info("做种校验服务：没有新的任务校验完成，将在下次周期继续检查 ...")
                    elif torrents is None:
                        logger.info(f"做种校验服务：下载器 {svc.name} 查询校验任务失败，将在下次继续查询 ...")
                    else:
                        logger.info(f"做种校验服务：下载器 {svc.name} 中没有需要检查的校验任务，清空待处理列表")
                        self._recheck_torrents[svc.name] = {}

            # 队列之外的兜底：即使队列为空也执行
            self._sweep_paused_seed_tasks(check_services)
        except Exception as e:
            logger.error(f"做种校验服务执行失败: {e}")
        finally:
            self._is_recheck_running = False

    def _sweep_paused_seed_tasks(self, check_services: List[ServiceInfo]):
        """兜底扫描已完成但暂停的转移/铺种任务，并自动开始做种。"""
        for svc in check_services:
            try:
                downloader = svc.instance
                torrents, _ = downloader.get_torrents()
                if not torrents:
                    continue
                can_start = []
                source_counts = {}
                for torrent in torrents:
                    if not self.__can_seeding(torrent, svc.type):
                        continue
                    labels = self.__get_label(torrent, svc.type) or []
                    source = None
                    if self._iyuu_labelsafterseed:
                        iyuu_labels = [label.strip() for label in self._iyuu_labelsafterseed.split(',') if label.strip()]
                        if any(label in labels for label in iyuu_labels):
                            source = "IYUU铺种"
                    if not source and self._torrent_tags:
                        if any(label in labels for label in self._torrent_tags):
                            source = "转移做种"
                    if not source:
                        continue
                    hash_str = self.__get_hash(torrent, svc.type)
                    if hash_str:
                        can_start.append(hash_str)
                        source_counts[source] = source_counts.get(source, 0) + 1
                if can_start:
                    source_text = "，".join([f"{source} {count} 个" for source, count in source_counts.items()])
                    logger.info(f"做种校验服务：兜底发现下载器 {svc.name} 中 {source_text} 已校验但未开始，开始做种")
                    downloader.start_torrents(ids=can_start)
            except Exception as e:
                logger.error(f"做种校验服务：兜底扫描下载器 {svc.name} 失败: {e}")

    @staticmethod
    def __get_hash(torrent: Any, dl_type: str):
        """
        获取种子hash
        """
        try:
            return torrent.get("hash") if dl_type == "qbittorrent" else torrent.hashString
        except Exception as e:
            logger.error(f"获取种子hash失败: {e}")
            return ""

    @staticmethod
    def __get_label(torrent: Any, dl_type: str):
        """
        获取种子标签
        """
        try:
            return [str(tag).strip() for tag in torrent.get("tags").split(',')] \
                if dl_type == "qbittorrent" else torrent.labels or []
        except Exception as e:
            logger.error(f"获取种子标签失败: {e}")
            return []

    @staticmethod
    def __get_category(torrent: Any, dl_type: str):
        """
        获取种子分类
        """
        try:
            return torrent.get("category").strip() \
                if dl_type == "qbittorrent" else ""
        except Exception as e:
            logger.error(f"获取种子分类失败: {e}")
            return ""

    @staticmethod
    def __get_save_path(torrent: Any, dl_type: str):
        """
        获取种子保存路径
        """
        try:
            return torrent.get("save_path") if dl_type == "qbittorrent" else torrent.download_dir
        except Exception as e:
            logger.error(f"获取种子保存路径失败: {e}")
            return ""

    @staticmethod
    def __can_seeding(torrent: Any, dl_type: str):
        """
        判断种子是否可以做种并处于暂停状态
        """
        try:
            return (torrent.get("state") in ["pausedUP", "stoppedUP"]) if dl_type == "qbittorrent" \
                else (torrent.status.stopped and torrent.percent_done == 1)
        except Exception as e:
            logger.error(f"判断种子做种状态失败: {e}")
            return False

    @staticmethod
    def __convert_save_path(save_path: str, from_root: str, to_root: str):
        """
        转换保存路径
        """
        try:
            # 没有保存目录，以目的根目录为准
            if not save_path:
                return to_root
            # 没有设置根目录时返回save_path
            if not to_root or not from_root:
                return save_path
            # 统一目录格式
            save_path = os.path.normpath(save_path).replace("\\", "/")
            from_root = os.path.normpath(from_root).replace("\\", "/")
            to_root = os.path.normpath(to_root).replace("\\", "/")
            # 替换根目录
            if save_path.startswith(from_root):
                return save_path.replace(from_root, to_root, 1)
        except Exception as e:
            logger.error(f"转换保存路径失败: {e}")
        return None

    # ════════════════════════════════════════════════════════════
    # v2.0.0: 转移后自动重命名 + 站点标签
    # ════════════════════════════════════════════════════════════

    def _post_transfer_process(self, to_service: ServiceInfo, torrent_hash: str):
        """
        种子转移到目标下载器后，立即执行重命名 + 打站点标签
        """
        if not torrent_hash or not to_service or not to_service.instance:
            return

        dl = to_service.instance
        dl_type = to_service.type

        # 获取种子信息
        try:
            if dl_type == "qbittorrent":
                torrents, _ = dl.get_torrents(ids=[torrent_hash])
                if not torrents:
                    logger.warning(f"转移后处理：无法获取种子信息 hash={torrent_hash}")
                    return
                torrent = torrents[0]
                torrent_name = torrent.get("name", "")
                torrent_tags = [str(t).strip() for t in torrent.get("tags", "").split(",") if t.strip()] if torrent.get("tags") else []
                trackers = [t.get("url") for t in (torrent.trackers or []) if t.get("tier", -1) >= 0 and t.get("url")]
                save_path = torrent.get("save_path", "")
            else:
                torrents, _ = dl.get_torrents(ids=[torrent_hash])
                if not torrents:
                    return
                torrent = torrents[0]
                torrent_name = torrent.name
                torrent_tags = torrent.labels or []
                trackers = [t.announce for t in (torrent.trackers or []) if t.tier >= 0 and t.announce]
                save_path = torrent.download_dir
        except Exception as e:
            logger.error(f"转移后处理：获取种子信息失败 hash={torrent_hash}: {e}")
            return

        if not torrent_name:
            return

        # ── 1. 重命名 ──
        if self._rename_enabled:
            self._rename_torrent(dl, dl_type, torrent_hash, torrent_name, save_path)

        # ── 2. 站点标签 ──
        if self._tag_enabled:
            self._tag_torrent(dl, dl_type, torrent_hash, torrent_tags, trackers)

    def _rename_torrent(self, dl, dl_type: str, torrent_hash: str, torrent_name: str, save_path: str):
        """重命名单个种子，并记录结果到持久化存储"""
        try:
            # 排除目录检查
            if self._rename_exclude_dirs:
                for d in self._rename_exclude_dirs.split("\n"):
                    if d and d in str(save_path):
                        logger.info(f"转移后重命名：命中排除目录 {d}，跳过 hash={torrent_hash}")
                        self._save_rename_record(torrent_hash, torrent_name, torrent_name, False, "命中排除目录")
                        return

            # 优先从下载历史获取识别信息（含完整季集号）
            from app.db.downloadhistory_oper import DownloadHistoryOper
            downloadhis = DownloadHistoryOper().get_by_hash(torrent_hash)
            if downloadhis:
                logger.info(f"转移后重命名：找到下载历史记录，使用历史名称识别: {downloadhis.torrent_name}")
                meta = MetaInfo(title=downloadhis.torrent_name, subtitle=downloadhis.torrent_description)
                media_info = self.chain.recognize_media(
                    meta=meta, mtype=MediaType(downloadhis.type), tmdbid=downloadhis.tmdbid
                )
                if media_info:
                    template = self._rename_movie_format if media_info.type == MediaType.MOVIE else self._rename_tv_format
                    new_name = self._format_torrent_name(template, meta, media_info)
                    if new_name and str(new_name) != torrent_name:
                        if dl_type == "qbittorrent":
                            dl.qbc.torrents_rename(torrent_hash=torrent_hash, new_torrent_name=str(new_name))
                        else:
                            dl.rename_torrent(torrent_hash, str(new_name))
                        logger.info(f"转移后重命名成功(历史): {torrent_name} → {new_name}")
                        self._save_rename_record(torrent_hash, torrent_name, str(new_name), True, "")
                        return
                    else:
                        logger.info(f"转移后重命名(历史): 名称未变化或格式化失败，回退到种子名解析")

            # 回退：解析种子名称
            meta = MetaInfo(torrent_name)
            if not meta or not meta.title:
                logger.warning(f"转移后重命名：元数据获取失败 hash={torrent_hash} name={torrent_name}")
                self._save_rename_record(torrent_hash, torrent_name, torrent_name, False, "元数据获取失败")
                return

            # TMDB 识别
            media_info = self.chain.recognize_media(meta=meta)
            if not media_info:
                logger.warning(f"转移后重命名：媒体识别失败 hash={torrent_hash} name={torrent_name}")
                self._save_rename_record(torrent_hash, torrent_name, torrent_name, False, "媒体识别失败")
                return

            # 选择模板
            template = self._rename_movie_format if media_info.type == MediaType.MOVIE else self._rename_tv_format
            new_name = self._format_torrent_name(template, meta, media_info)
            if not new_name:
                logger.warning(f"转移后重命名：格式化结果为空 hash={torrent_hash}")
                self._save_rename_record(torrent_hash, torrent_name, torrent_name, False, "格式化结果为空")
                return
            if str(new_name) == torrent_name:
                logger.info(f"转移后重命名：名称未变化 hash={torrent_hash}")
                self._save_rename_record(torrent_hash, torrent_name, str(new_name), True, "名称未变化")
                return

            # 执行重命名
            if dl_type == "qbittorrent":
                dl.qbc.torrents_rename(torrent_hash=torrent_hash, new_torrent_name=str(new_name))
            else:
                dl.rename_torrent(torrent_hash, str(new_name))
            logger.info(f"转移后重命名成功: {torrent_name} → {new_name}")
            self._save_rename_record(torrent_hash, torrent_name, str(new_name), True, "")
        except Exception as e:
            logger.error(f"转移后重命名失败 hash={torrent_hash}: {e}")
            self._save_rename_record(torrent_hash, torrent_name, torrent_name, False, str(e))

    def _tag_torrent(self, dl, dl_type: str, torrent_hash: str, torrent_tags: list, trackers: list):
        """给种子打站点标签（通过 SystemConfigOper 读取站点配置，无需用户认证）"""
        try:
            # 通过 tracker 解析站点
            site_name = None
            for tracker in trackers:
                domain = None
                for key, mapped in self._tracker_mappings.items():
                    if key in tracker:
                        domain = mapped
                        break
                if not domain:
                    domain = StringUtils.get_url_domain(tracker)
                if not domain:
                    continue
                # 从系统配置中查找匹配的站点
                site_name = self._find_site_by_domain(domain)
                if site_name:
                    break

            if not site_name:
                logger.info(f"转移后标签：无法识别站点 hash={torrent_hash}")
                return

            # 构造标签
            site_tag = (self._tag_siteprefix + site_name) if self._tag_siteprefix else site_name
            if site_tag in torrent_tags:
                logger.info(f"转移后标签：标签已存在 hash={torrent_hash}")
                return

            # 设置标签
            if dl_type == "qbittorrent":
                dl.set_torrents_tag(ids=torrent_hash, tags=[site_tag])
            else:
                dl.set_torrent_tag(ids=torrent_hash, tags=[site_tag])
            logger.info(f"转移后标签成功: hash={torrent_hash} tag={site_tag}")
        except Exception as e:
            logger.error(f"转移后标签失败 hash={torrent_hash}: {e}")

    @staticmethod
    def _find_site_by_domain(domain: str) -> Optional[str]:
        """通过域名从系统站点配置中查找站点名称（优先 SystemConfigOper，fallback SitesHelper）"""
        # 方式1：SystemConfigOper（无需认证，调度器环境可用）
        try:
            sites = SystemConfigOper().get(SystemConfigKey.UserSite) or {}
            if sites:
                for site_info in sites.values():
                    if not isinstance(site_info, dict):
                        continue
                    site_domain = site_info.get("domain", "")
                    if not site_domain:
                        continue
                    site_domain_clean = StringUtils.get_url_domain(site_domain)
                    if site_domain_clean and site_domain_clean in domain:
                        return site_info.get("name")
                    if domain in site_domain:
                        return site_info.get("name")
        except Exception:
            pass

        # 方式2：SitesHelper（需要用户认证，作为 fallback）
        try:
            sh = SitesHelper()
            site_info = sh.get_indexer(domain)
            if site_info:
                return site_info.get("name")
        except Exception:
            pass

        return None

    @staticmethod
    def _format_torrent_name(template_string: str, meta: MetaBase, mediainfo) -> Optional[str]:
        """根据 Jinja2 模板格式化种子名称"""
        if meta and meta.title:
            processed = re.sub(r'\[.*?\][\s.]*', '', meta.title)
            processed = re.sub(r'\.torrent$', '', processed).strip(' .')
            meta.title = processed
        handler = TransHandler()
        rename_dict = handler.get_naming_dict(meta=meta, mediainfo=mediainfo)
        path = handler.get_rename_path(template_string, rename_dict)
        return path.as_posix() if path else None

    # ════════════════════════════════════════════════════════════
    # 重命名记录持久化
    # ════════════════════════════════════════════════════════════

    def _save_rename_record(self, torrent_hash: str, original_name: str, after_name: str,
                            success: bool, reason: str = ""):
        """保存重命名记录"""
        records = self.get_data("rename_records") or {}
        records[torrent_hash] = {
            "hash": torrent_hash,
            "original_name": original_name,
            "after_name": after_name,
            "success": success,
            "reason": reason,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.save_data("rename_records", records)

    def _get_failed_rename_hashes(self) -> set:
        """获取所有重命名失败的种子 hash"""
        records = self.get_data("rename_records") or {}
        return {h for h, r in records.items() if not r.get("success")}

    def _retry_failed_renames(self, to_service: ServiceInfo):
        """对目标下载器中之前重命名失败的种子进行补刀（重命名+站点标签）"""
        if not self._rename_enabled and not self._tag_enabled:
            return
        failed_hashes = self._get_failed_rename_hashes()
        if not failed_hashes:
            return

        dl = to_service.instance
        dl_type = to_service.type
        try:
            torrents, _ = dl.get_torrents(ids=list(failed_hashes))
            if not torrents:
                return
            retry_count = 0
            for torrent in torrents:
                th = torrent.get("hash") if dl_type == "qbittorrent" else torrent.hashString
                if th not in failed_hashes:
                    continue
                tn = torrent.get("name", "") if dl_type == "qbittorrent" else torrent.name
                sp = torrent.get("save_path", "") if dl_type == "qbittorrent" else torrent.download_dir
                tags = [str(t).strip() for t in torrent.get("tags", "").split(",") if t.strip()] if dl_type == "qbittorrent" and torrent.get("tags") else (torrent.labels or [])
                trackers = [t.get("url") for t in (torrent.trackers or []) if t.get("tier", -1) >= 0 and t.get("url")] if dl_type == "qbittorrent" else [t.announce for t in (torrent.trackers or []) if t.tier >= 0 and t.announce]
                logger.info(f"补刀处理: hash={th} name={tn}")
                if self._rename_enabled:
                    self._rename_torrent(dl, dl_type, th, tn, sp)
                if self._tag_enabled:
                    self._tag_torrent(dl, dl_type, th, tags, trackers)
                retry_count += 1
            if retry_count > 0:
                logger.info(f"补刀完成，处理 {retry_count} 个种子")
        except Exception as e:
            logger.error(f"补刀失败: {e}")

    # ════════════════════════════════════════════════════════════
    # v2.3.0: 事件驱动转移
    # ════════════════════════════════════════════════════════════

    @eventmanager.register(EventType.TransferComplete)
    def on_transfer_complete(self, event: Event):
        """
        监听 TransferComplete 事件，延迟 N 分钟后自动转移做种
        """
        if not self._transfer_active:
            return

        event_data = event.event_data or {}
        # 检查事件来源下载器是否匹配
        downloader_name = event_data.get("downloader") or event_data.get("downloader_name", "")
        if downloader_name and downloader_name != self._fromdownloader:
            return

        delay = max(1, int(self._delay_minutes or 25))
        logger.info(f"收到 TransferComplete 事件（来源: {downloader_name}），将在 {delay} 分钟后执行转移做种")

        # 使用 scheduler 延迟执行
        if not self._scheduler:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            self._scheduler.start()

        run_time = datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(minutes=delay)
        self._scheduler.add_job(
            self._delayed_transfer,
            'date',
            run_date=run_time,
            id=f"delayed_transfer_{datetime.now().strftime('%H%M%S%f')}"
        )

    def _delayed_transfer(self):
        """延迟执行的转移任务（由事件触发）"""
        logger.info("延迟时间到，开始执行事件驱动的转移做种")
        self.transfer(trigger_source="事件驱动")

    # ════════════════════════════════════════════════════════════
    # v3.0.0: IYUU 自动辅种
    # ════════════════════════════════════════════════════════════

    @property
    def _iyuu_service_infos(self) -> Optional[Dict[str, ServiceInfo]]:
        """IYUU 辅种下载器服务信息"""
        if not self._iyuu_downloaders:
            logger.warning("IYUU辅种：尚未配置下载器")
            return None
        services = DownloaderHelper().get_services(name_filters=self._iyuu_downloaders)
        if not services:
            logger.warning("IYUU辅种：获取下载器实例失败")
            return None
        active = {}
        for name, info in services.items():
            if info.instance.is_inactive():
                logger.warning(f"IYUU辅种：下载器 {name} 未连接")
            else:
                active[name] = info
        return active if active else None

    @property
    def _iyuu_auto_service_info(self) -> Optional[ServiceInfo]:
        """IYUU 主辅分离下载器"""
        if not self._iyuu_auto_downloader:
            return None
        service = DownloaderHelper().get_service(name=self._iyuu_auto_downloader)
        if not service or service.instance.is_inactive():
            logger.warning(f"IYUU辅种：主辅分离下载器 {self._iyuu_auto_downloader} 不可用")
            return None
        return service

    def iyuu_auto_seed(self):
        """IYUU 自动辅种主逻辑"""
        if not self.iyuu_helper or not self._iyuu_service_infos:
            return
        logger.info("开始 IYUU 辅种任务 ...")

        self._iyuu_total = 0
        self._iyuu_realtotal = 0
        self._iyuu_success = 0
        self._iyuu_exist = 0
        self._iyuu_fail = 0
        self._iyuu_cached = 0

        for service in self._iyuu_service_infos.values():
            downloader = service.name
            downloader_obj = service.instance
            logger.info(f"IYUU辅种：扫描下载器 {downloader} ...")
            torrents = downloader_obj.get_completed_torrents()
            if not torrents:
                logger.info(f"IYUU辅种：下载器 {downloader} 没有已完成种子")
                continue
            logger.info(f"IYUU辅种：下载器 {downloader} 已完成种子数：{len(torrents)}")

            hash_strs = []
            for torrent in torrents:
                if self._event.is_set():
                    logger.info("IYUU辅种服务停止")
                    return
                hash_str = self.__get_hash(torrent, service.type)
                if hash_str in self._iyuu_error_caches or hash_str in self._iyuu_permanent_error_caches:
                    continue
                save_path = self.__get_save_path(torrent, service.type)
                if self._iyuu_nopaths and save_path:
                    skip = False
                    for nopath in self._iyuu_nopaths.split('\n'):
                        if os.path.normpath(save_path).startswith(os.path.normpath(nopath)):
                            skip = True
                            break
                    if skip:
                        continue
                torrent_labels = self.__get_label(torrent, service.type)
                if torrent_labels and self._iyuu_nolabels:
                    skip = False
                    for label in self._iyuu_nolabels.split(','):
                        if label in torrent_labels:
                            skip = True
                            break
                    if skip:
                        continue
                torrent_size = self.__get_torrent_size(torrent, service.type) / 1024 / 1024 / 1024
                if self._iyuu_size and torrent_size < self._iyuu_size:
                    continue
                category = self.__get_category(torrent, service.type) if self._iyuu_auto_category else None
                hash_strs.append({
                    "hash": hash_str,
                    "save_path": save_path,
                    "category": category or self._iyuu_categoryafterseed
                })

            if hash_strs:
                logger.info(f"IYUU辅种：需要辅种的种子数：{len(hash_strs)}")
                chunk_size = 200
                for i in range(0, len(hash_strs), chunk_size):
                    chunk = hash_strs[i:i + chunk_size]
                    self._iyuu_seed_torrents(hash_strs=chunk, service=service)
                # 做种校验已由 _register_seed_recheck 按需处理
            else:
                logger.info(f"IYUU辅种：下载器 {downloader} 没有需要辅种的种子")

        self._update_iyuu_config()
        if self._notify and (self._iyuu_success or self._iyuu_fail):
            self.post_message(
                mtype=NotificationType.SiteMessage,
                title="【IYUU自动辅种任务完成】",
                text=f"服务器返回可辅种总数：{self._iyuu_total}\n"
                     f"实际可辅种数：{self._iyuu_realtotal}\n"
                     f"已存在：{self._iyuu_exist}\n"
                     f"成功：{self._iyuu_success}\n"
                     f"失败：{self._iyuu_fail}\n"
                     f"缓存跳过：{self._iyuu_cached}"
            )
        logger.info("IYUU 辅种任务执行完成")

    def _iyuu_seed_torrents(self, hash_strs: list, service: ServiceInfo):
        """执行一批种子的 IYUU 辅种"""
        if not hash_strs:
            return
        logger.info(f"IYUU辅种：下载器 {service.name} 查询辅种，数量：{len(hash_strs)}")
        hashs = [item.get("hash") for item in hash_strs]
        save_paths = {item.get("hash"): item.get("save_path") for item in hash_strs}
        save_category = {item.get("hash"): item.get("category") for item in hash_strs}
        sites_helper = SitesHelper()
        unmanaged_sites = {}
        skipped_sites = {}

        def __count(counter: dict, key: str):
            if not key:
                key = "未知站点"
            counter[key] = counter.get(key, 0) + 1

        def __log_counter(title: str, counter: dict, limit: int = 20):
            if not counter:
                return
            total = sum(counter.values())
            top_items = sorted(counter.items(), key=lambda item: item[1], reverse=True)[:limit]
            detail = ", ".join([f"{name}({count})" for name, count in top_items])
            logger.info(f"IYUU辅种：{title} {len(counter)} 个站点，共 {total} 条：{detail}")

        seed_list, msg = self.iyuu_helper.get_seed_info(hashs)
        if not isinstance(seed_list, dict):
            if self._iyuu_token and msg == '请求缺少token':
                logger.warning(f'IYUU辅种失败，疑似站点未绑定：{msg}')
            else:
                logger.warning(f"IYUU辅种：当前种子列表没有可辅种的站点：{msg}")
            return
        logger.info(f"IYUU辅种：返回可辅种数：{len(seed_list)}")

        for current_hash, seed_info in seed_list.items():
            if not seed_info:
                continue
            seed_torrents = seed_info.get("torrent")
            if not isinstance(seed_torrents, list):
                seed_torrents = [seed_torrents]

            success_torrents = []
            for seed in seed_torrents:
                if not seed or not isinstance(seed, dict):
                    continue
                if not seed.get("sid") or not seed.get("info_hash"):
                    continue
                if seed.get("info_hash") in hashs:
                    continue
                if seed.get("info_hash") in self._iyuu_success_caches:
                    continue
                if seed.get("info_hash") in self._iyuu_error_caches or seed.get("info_hash") in self._iyuu_permanent_error_caches:
                    continue

                # 先做站点映射过滤，避免未维护站点逐条进入下载逻辑刷屏。
                site_url, _ = self.iyuu_helper.get_torrent_url(seed.get("sid"))
                site_domain = StringUtils.get_url_domain(site_url) if site_url else None
                site_info = sites_helper.get_indexer(site_domain) if site_domain else None
                if not site_info or not site_info.get('url'):
                    __count(unmanaged_sites, site_url or str(seed.get("sid")))
                    continue
                if self._iyuu_sites and site_info.get('id') not in self._iyuu_sites:
                    __count(skipped_sites, site_info.get('name') or site_url or str(seed.get("sid")))
                    continue

                target_service = self._iyuu_auto_service_info or service
                success = self._iyuu_download_torrent(seed=seed, service=target_service,
                                                      save_path=save_paths.get(current_hash),
                                                      save_category=save_category.get(current_hash),
                                                      source_hash=current_hash,
                                                      site_info=site_info)
                if success:
                    success_torrents.append(seed.get("info_hash"))

            if success_torrents:
                self._iyuu_save_history(current_hash=current_hash, downloader=service.name,
                                        success_torrents=success_torrents)

        __log_counter("跳过未维护站点", unmanaged_sites)
        __log_counter("跳过未选择站点", skipped_sites)
        logger.info(f"IYUU辅种：下载器 {service.name} 辅种完成")

    def _iyuu_download_torrent(self, seed: dict, service: ServiceInfo, save_path: str, save_category: str,
                               source_hash: str = None, site_info: dict = None):
        """从站点下载种子并添加到下载器，辅种后打站点标签"""
        def __is_special_site(url):
            if "hdsky.me" in url:
                return False
            return True

        self._iyuu_total += 1
        site_url, download_page = self.iyuu_helper.get_torrent_url(seed.get("sid"))
        if not site_url or not download_page:
            self._append_iyuu_cache(self._iyuu_error_caches, seed.get("info_hash"))
            self._iyuu_fail += 1
            self._iyuu_cached += 1
            return False

        site_domain = StringUtils.get_url_domain(site_url)
        sites_helper = SitesHelper()
        if not site_info:
            site_info = sites_helper.get_indexer(site_domain)
        if not site_info or not site_info.get('url'):
            return False
        if self._iyuu_sites and site_info.get('id') not in self._iyuu_sites:
            return False

        self._iyuu_realtotal += 1
        downloader_obj = service.instance
        torrent_info, _ = downloader_obj.get_torrents(ids=[seed.get("info_hash")])
        if torrent_info:
            self._iyuu_exist += 1
            return False

        check, checkmsg = sites_helper.check(site_domain)
        if check:
            logger.warning(checkmsg)
            self._iyuu_fail += 1
            return False

        torrent_url = self._iyuu_get_download_url(seed=seed, site=site_info, base_url=download_page)
        if not torrent_url:
            self._append_iyuu_cache(self._iyuu_error_caches, seed.get("info_hash"))
            self._iyuu_fail += 1
            self._iyuu_cached += 1
            return False

        def __with_https_param(url: str) -> str:
            if not url or not __is_special_site(url) or "https=1" in url:
                return url
            return url + ("&https=1" if "?" in url else "?https=1")

        torrent_url = __with_https_param(torrent_url)

        _, content, _, _, error_msg = TorrentHelper().download_torrent(
            url=torrent_url, cookie=site_info.get("cookie"),
            ua=site_info.get("ua") or settings.USER_AGENT, proxy=site_info.get("proxy"))

        # 普通模板直链下载失败时，回退到详情页重新抓取真实下载链接。
        if not content:
            logger.warning(
                f"IYUU辅种：下载种子文件失败，准备回退详情页获取：站点={site_info.get('name')}，"
                f"info_hash={seed.get('info_hash')}，url={torrent_url}，原因={error_msg or '未知'}"
            )
            fallback_url = self._iyuu_get_download_url(seed=seed, site=site_info, base_url=download_page,
                                                       force_page=True)
            fallback_url = __with_https_param(fallback_url)
            if fallback_url and fallback_url != torrent_url:
                logger.info(f"IYUU辅种：使用详情页下载链接重试：{fallback_url}")
                _, content, _, _, fallback_error = TorrentHelper().download_torrent(
                    url=fallback_url, cookie=site_info.get("cookie"),
                    ua=site_info.get("ua") or settings.USER_AGENT, proxy=site_info.get("proxy"))
                if content:
                    torrent_url = fallback_url
                    error_msg = ""
                else:
                    error_msg = fallback_error or error_msg

        if not content:
            self._iyuu_fail += 1
            transient_keywords = ('无法打开链接', '触发站点流控', '403', '401', '429', 'Cloudflare',
                                  'cloudflare', 'timeout', 'Timeout', 'Connection', '连接', '登录', 'Cookie')
            if error_msg and any(keyword in error_msg for keyword in transient_keywords):
                self._append_iyuu_cache(self._iyuu_error_caches, seed.get("info_hash"))
            else:
                self._append_iyuu_cache(self._iyuu_permanent_error_caches, seed.get("info_hash"))
            logger.error(
                f"IYUU辅种：下载种子文件失败：站点={site_info.get('name')}，"
                f"info_hash={seed.get('info_hash')}，url={torrent_url}，原因={error_msg or '未知'}"
            )
            return False

        logger.info(f"IYUU辅种：准备添加下载任务：{torrent_url}")
        download_id = self._iyuu_download(service=service, content=content,
                                          save_path=save_path, save_category=save_category,
                                          site_name=site_info.get("name"),
                                          expected_hash=seed.get("info_hash"),
                                          torrent_url=torrent_url)
        if not download_id:
            self._iyuu_fail += 1
            self._append_iyuu_cache(self._iyuu_error_caches, seed.get("info_hash"))
            self._iyuu_cached += 1
            return False

        self._iyuu_success += 1
        # ── 辅种后：校验 + 自动开始 + 重命名 + 打站点标签 ──
        dl = service.instance
        dl_type = service.type

        # 1. 触发校验（QB需要手动校验，TR自动）
        downloader_helper = DownloaderHelper()
        if downloader_helper.is_downloader("qbittorrent", service=service):
            if self._seed_skipverify:
                if self._seed_autostart:
                    logger.info(f"IYUU辅种：{download_id} 跳过校验，自动开始")
                    self._register_seed_recheck(service.name, [download_id], "iyuu")
                else:
                    logger.info(f"IYUU辅种：{download_id} 跳过校验，等待手动开始")
            else:
                logger.info(f"IYUU辅种：qbittorrent 开始校验 {download_id}")
                dl.recheck_torrents(ids=[download_id])
                self._register_seed_recheck(service.name, [download_id], "iyuu")
        else:
            self._register_seed_recheck(service.name, [download_id], "iyuu")

        # 2. 重命名：优先复用母种重命名记录前缀，失败再回退 TMDB 识别
        if self._rename_enabled:
            try:
                torrents, _ = dl.get_torrents(ids=[download_id])
                if torrents:
                    t = torrents[0]
                    torrent_name = t.get("name", "") if dl_type == "qbittorrent" else t.name
                    save_path_t = t.get("save_path", "") if dl_type == "qbittorrent" else t.download_dir
                    if torrent_name:
                        reused = self._rename_iyuu_torrent_by_source_record(
                            dl=dl,
                            dl_type=dl_type,
                            torrent_hash=download_id,
                            torrent_name=torrent_name,
                            source_hash=source_hash
                        )
                        if not reused:
                            self._rename_torrent(dl, dl_type, download_id, torrent_name, save_path_t)
            except Exception as e:
                logger.error(f"IYUU辅种后重命名失败: {e}")

        # 3. 打站点标签
        if self._tag_enabled:
            try:
                torrents, _ = dl.get_torrents(ids=[download_id])
                if torrents:
                    t = torrents[0]
                    tags = [str(x).strip() for x in t.get("tags", "").split(",") if x.strip()] if dl_type == "qbittorrent" and t.get("tags") else (t.labels or [])
                    trackers = [tr.get("url") for tr in (t.trackers or []) if tr.get("tier", -1) >= 0 and tr.get("url")] if dl_type == "qbittorrent" else [tr.announce for tr in (t.trackers or []) if tr.tier >= 0 and tr.announce]
                    self._tag_torrent(dl, dl_type, download_id, tags, trackers)
            except Exception as e:
                logger.error(f"IYUU辅种后打标签失败: {e}")

        return True

    def _rename_iyuu_torrent_by_source_record(self, dl, dl_type: str, torrent_hash: str,
                                             torrent_name: str, source_hash: str = None) -> bool:
        """IYUU铺种重命名：复用母种已重命名记录的媒体前缀。"""
        if not source_hash:
            return False
        try:
            records = self.get_data("rename_records") or {}
            source_record = records.get(source_hash)
            if not source_record or not source_record.get("success"):
                return False
            source_name = source_record.get("after_name") or ""
            if "] - " not in source_name:
                return False
            prefix = source_name.split("] - ", 1)[0] + "] - "
            new_name = prefix + torrent_name
            if new_name == torrent_name:
                return True
            if dl_type == "qbittorrent":
                dl.qbc.torrents_rename(torrent_hash=torrent_hash, new_torrent_name=new_name)
            else:
                dl.rename_torrent(torrent_hash, new_name)
            logger.info(f"IYUU辅种重命名成功(复用母种): {torrent_name} → {new_name}")
            self._save_rename_record(torrent_hash, torrent_name, new_name, True, f"复用母种 {source_hash} 命名前缀")
            return True
        except Exception as e:
            logger.error(f"IYUU辅种复用母种重命名失败 hash={torrent_hash}, source={source_hash}: {e}")
            return False

    def _iyuu_download(self, service: ServiceInfo, content: bytes,
                       save_path: str, save_category: str, site_name: str,
                       expected_hash: str = None, torrent_url: str = None) -> Optional[str]:
        """添加 IYUU 辅种下载任务，并用 expected_hash + 临时标签多次确认任务入库。"""
        torrent_tags = self._iyuu_labelsafterseed.split(',')
        if self._iyuu_addhosttotag:
            torrent_tags.append(site_name)

        if service.type == "qbittorrent":
            tag = StringUtils.generate_random_str(10)
            torrent_tags.append(tag)

            def __find_torrent_hash():
                if expected_hash:
                    try:
                        torrents, _ = service.instance.get_torrents(ids=[expected_hash])
                        if torrents:
                            return expected_hash
                    except Exception as err:
                        logger.warning(f"IYUU辅种：按 expected_hash 查询任务失败：{expected_hash}，{err}")
                try:
                    torrent_hash = service.instance.get_torrent_id_by_tag(tags=tag)
                    if torrent_hash:
                        return torrent_hash
                except Exception as err:
                    logger.warning(f"IYUU辅种：按临时标签查询任务失败：tag={tag}，{err}")
                return None

            state = service.instance.add_torrent(content=content, download_dir=save_path,
                                                 is_paused=True, tag=torrent_tags,
                                                 category=save_category,
                                                 is_skip_checking=self._seed_skipverify)
            if not state:
                logger.error(
                    f"IYUU辅种：{service.name} 下载任务添加失败：expected_hash={expected_hash}，"
                    f"url={torrent_url}，save_path={save_path}，category={save_category}"
                )
                return None

            # qB 接收种子后可能延迟入库或延迟写入标签，轮询确认。
            for index in range(6):
                torrent_hash = __find_torrent_hash()
                if torrent_hash:
                    logger.info(
                        f"IYUU辅种：成功添加下载任务：hash={torrent_hash}，站点={site_name}，"
                        f"确认方式={'expected_hash' if expected_hash and torrent_hash == expected_hash else 'tag'}"
                    )
                    return torrent_hash
                time.sleep(2)

            logger.error(
                f"IYUU辅种：{service.name} 下载器返回已接收，但未能确认任务入库："
                f"expected_hash={expected_hash}，tag={tag}，url={torrent_url}，"
                f"save_path={save_path}，category={save_category}"
            )
            return None
        elif service.type == "transmission":
            torrent = service.instance.add_torrent(content=content, download_dir=save_path,
                                                   is_paused=True, labels=torrent_tags)
            return torrent.hashString if torrent else None

        logger.error(f"IYUU辅种：不支持的下载器类型：{service.type}")
        return None

    def _iyuu_get_download_url(self, seed: dict, site: dict, base_url: str, force_page: bool = False) -> Optional[str]:
        """获取站点种子下载链接（移植自原版 IYUU 插件，含特殊站点处理）"""

        def __is_mteam(url: str):
            return "m-team." in url

        def __is_monika(url: str):
            return "monikadesign." in url

        def __is_gpw(url: str):
            return "greatposterwall." in url

        def __is_special_site(url: str):
            spec_params = ["hash=", "authkey="]
            if any(field in base_url for field in spec_params):
                return True
            special_domains = ["hdchina.org", "hdsky.me", "hdcity.in", "totheglory.im"]
            return any(d in url for d in special_domains)

        def __get_mteam_enclosure(tid: str, apikey: str):
            if not apikey:
                logger.warning("IYUU辅种：m-team 站点的 apikey 未配置")
                return None
            api_url = re.sub(r'//[^/]+\.m-team', '//api.m-team', site.get('url'))
            ua = site.get("ua") or settings.USER_AGENT
            res = RequestUtils(
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'User-Agent': ua,
                    'Accept': 'application/json, text/plain, */*',
                    'x-api-key': apikey
                }
            ).post_res(f"{api_url}api/torrent/genDlToken", params={'id': tid})
            if not res:
                logger.warning(f"IYUU辅种：m-team 获取种子下载链接失败：{tid}")
                return None
            return res.json().get("data")

        def __get_monika_torrent(tid: str, rssurl: str):
            if not rssurl:
                logger.warning("IYUU辅种：Monika 站点的 rss 链接未配置")
                return None
            rss_match = re.search(r'/rss/\d+\.(\w+)', rssurl)
            if not rss_match:
                logger.warning("IYUU辅种：Monika 站点 rss 链接格式不匹配")
                return None
            rsskey = rss_match.group(1)
            return f"{site.get('url')}torrents/download/{tid}.{rsskey}"

        def __get_torrent_url_from_page(seed: dict, site: dict):
            if not site.get('url'):
                logger.warning(f"IYUU辅种：站点 {site.get('name')} 未获取站点地址")
                return None
            try:
                page_url = f"{site.get('url')}details.php?id={seed.get('torrent_id')}&hit=1"
                logger.info(f"IYUU辅种：正在从详情页获取种子下载链接：{page_url}")
                res = RequestUtils(
                    cookies=site.get("cookie"),
                    ua=site.get("ua") or settings.USER_AGENT,
                    proxies=settings.PROXY if site.get("proxy") else None
                ).get_res(url=page_url)
                if res is not None and res.status_code in (200, 500):
                    if "charset=utf-8" in res.text or "charset=UTF-8" in res.text:
                        res.encoding = "UTF-8"
                    else:
                        res.encoding = res.apparent_encoding
                    if not res.text:
                        logger.warning(f"IYUU辅种：详情页内容为空：{page_url}")
                        return None
                    html = etree.HTML(res.text)
                    for xpath in self._iyuu_torrent_xpaths:
                        download_url = html.xpath(xpath)
                        if download_url:
                            download_url = download_url[0]
                            if not download_url.startswith("http"):
                                download_url = urljoin(site.get('url'), download_url)
                            logger.info(f"IYUU辅种：从详情页获取下载链接成功：{download_url}")
                            return download_url
                    logger.warning(f"IYUU辅种：详情页 xpath 未匹配到下载链接：{page_url}，站点：{site.get('name')}")
                else:
                    logger.warning(f"IYUU辅种：详情页请求失败（HTTP {res.status_code if res else '无响应'}）：{page_url}")
            except Exception as e:
                logger.error(f"IYUU辅种：从详情页获取下载链接异常：{e}")
            return None

        try:
            site_url = site.get('url', '')

            # 强制回退：普通模板直链失败后，尝试从详情页抓真实下载链接。
            if force_page:
                return __get_torrent_url_from_page(seed=seed, site=site)

            # m-team 特殊处理
            if __is_mteam(site_url):
                return __get_mteam_enclosure(tid=seed.get("torrent_id"), apikey=site.get("apikey"))

            # Monika 特殊处理
            if __is_monika(site_url):
                return __get_monika_torrent(tid=seed.get("torrent_id"), rssurl=site.get("rss"))

            # GPW / 特殊站点：从详情页获取
            if __is_gpw(site_url) or __is_special_site(site_url):
                return __get_torrent_url_from_page(seed=seed, site=site)

            # 普通站点：模板替换
            download_url = base_url.replace(
                "id={}", "id={id}"
            ).replace(
                "/{}", "/{id}"
            ).replace(
                "/{torrent_key}", ""
            ).format(
                **{
                    "id": seed.get("torrent_id"),
                    "passkey": site.get("passkey") or '',
                    "uid": site.get("uid") or '',
                }
            )
            if download_url.count("{"):
                logger.warning(f"IYUU辅种：当前不支持该站点的辅助任务，Url转换失败：{seed}")
                return None
            download_url = re.sub(r"[&?]passkey=", "",
                                  re.sub(r"[&?]uid=", "",
                                         download_url,
                                         flags=re.IGNORECASE),
                                  flags=re.IGNORECASE)
            return f"{site_url}{download_url}"
        except Exception as e:
            logger.warning(f"IYUU辅种：{site.get('name')} Url转换失败：{e}，回退到详情页获取")
            return __get_torrent_url_from_page(seed=seed, site=site)

    def _iyuu_save_history(self, current_hash: str, downloader: str, success_torrents: list):
        """保存 IYUU 辅种历史"""
        try:
            seed_history = self.get_data(key=f"iyuu_{current_hash}") or []
            new_history = True
            for history in seed_history:
                if history and isinstance(history, dict) and str(history.get("downloader")) == downloader:
                    history["torrents"] = list(set((history.get("torrents") or []) + success_torrents))
                    new_history = False
                    break
            if new_history:
                seed_history.append({"downloader": downloader, "torrents": list(set(success_torrents))})
            self.save_data(key=f"iyuu_{current_hash}", value=seed_history)
        except Exception as e:
            logger.error(f"IYUU辅种：保存历史失败：{e}")

    @staticmethod
    def _append_iyuu_cache(cache_list: list, info_hash: str):
        """追加 IYUU 辅种缓存"""
        if info_hash not in cache_list:
            cache_list.append(info_hash)

    @staticmethod
    def _trim_seed_cache(cache_list: list):
        """裁剪辅种缓存"""
        max_items = 10000
        if len(cache_list) > max_items:
            del cache_list[:len(cache_list) - max_items]

    @staticmethod
    def _custom_sites() -> list:
        """获取自定义站点"""
        try:
            return [site for site in SystemConfigOper().get(SystemConfigKey.UserSite) or {} if isinstance(site, dict)]
        except Exception:
            return []

    def _update_iyuu_config(self, config: dict = None):
        """更新 IYUU 辅种缓存到持久化存储（合并模式，不覆盖其他配置）"""
        if config is None:
            config = SystemConfigOper().get(f"plugin.{self.__class__.__name__}") or {}
        config["iyuu_permanent_error_caches"] = self._iyuu_permanent_error_caches
        config["iyuu_error_caches"] = self._iyuu_error_caches
        config["iyuu_success_caches"] = self._iyuu_success_caches
        self.update_config(config=config)

    @staticmethod
    def __get_torrent_size(torrent: Any, dl_type: str) -> float:
        """获取种子大小"""
        try:
            return torrent.get("size", 0) if dl_type == "qbittorrent" else (torrent.total_size or 0)
        except Exception:
            return 0


    # ════════════════════════════════════════════════════════════
    # v3.0.14: 按需做种校验
    # ════════════════════════════════════════════════════════════

    def _load_seed_recheck_queue(self):
        return self.get_data(self._seed_recheck_queue_key) or {}

    def _save_seed_recheck_queue(self, queue):
        self.save_data(self._seed_recheck_queue_key, queue)

    def _register_seed_recheck(self, downloader, hashes, source):
        if not hashes:
            return
        queue = self._load_seed_recheck_queue()
        for h in hashes:
            existing = queue.get(h, {})
            queue[h] = {
                "hash": h,
                "downloader": downloader,
                "source": source,
                "created_at": existing.get("created_at") or time.time(),
                "updated_at": time.time(),
                "attempts": existing.get("attempts", 0),
                "last_check": existing.get("last_check", 0),
                "max_wait_minutes": self._seed_max_wait_minutes,
            }
        self._save_seed_recheck_queue(queue)
        logger.info(f"做种校验：注册 {len(hashes)} 个待校验任务，来源={source}，下载器={downloader}")
        self._ensure_seed_recheck_worker()

    def _ensure_seed_recheck_worker(self):
        with self._seed_recheck_lock:
            if self._seed_recheck_running:
                return
            self._seed_recheck_running = True
        thread = threading.Thread(
            target=self._seed_recheck_loop,
            name="DownloadManagerSeedRecheck",
            daemon=True
        )
        thread.start()
        logger.info("做种校验：按需 worker 已启动")

    def _seed_recheck_loop(self):
        try:
            while self._enabled:
                queue = self._load_seed_recheck_queue()
                if not queue:
                    logger.info("做种校验：队列已清空，worker 退出")
                    break
                changed = self._process_seed_recheck_once(queue)
                if changed:
                    self._save_seed_recheck_queue(queue)
                time.sleep(self._seed_check_interval)
        finally:
            with self._seed_recheck_lock:
                self._seed_recheck_running = False

    def _process_seed_recheck_once(self, queue):
        changed = False
        grouped = {}
        for h, item in queue.items():
            dl = item.get("downloader", "")
            grouped.setdefault(dl, []).append(item)
        for downloader_name, items in grouped.items():
            svc = self.service_info(downloader_name)
            if not svc:
                continue
            dl = svc.instance
            dl_type = svc.type
            hashes = [it["hash"] for it in items]
            try:
                torrents, _ = dl.get_torrents(ids=hashes)
            except Exception as e:
                logger.error(f"做种校验：查询下载器 {downloader_name} 失败: {e}")
                continue
            if not torrents:
                continue
            task_map = {}
            for t in torrents:
                h = self.__get_hash(t, dl_type)
                if h:
                    task_map[h] = t
            for item in items:
                h = item["hash"]
                task = task_map.get(h)
                if not task:
                    if self._seed_should_remove_missing(item):
                        queue.pop(h, None)
                        changed = True
                        logger.info(f"做种校验：{h} 在下载器中未找到，已移出队列")
                    continue
                state = task.get("state") if dl_type == "qbittorrent" else task.status
                if self._seed_is_checking(state, dl_type):
                    continue
                if self._seed_is_ready(state, dl_type):
                    try:
                        dl.start_torrents(ids=[h])
                        logger.info(f"做种校验：{h} 校验完成，已自动开始做种，来源={item.get('source')}")
                        queue.pop(h, None)
                        changed = True
                    except Exception as e:
                        logger.error(f"做种校验：{h} 开始做种失败: {e}")
                    continue
                if self._seed_is_error(state, dl_type):
                    item["attempts"] = item.get("attempts", 0) + 1
                    if item["attempts"] >= 5:
                        queue.pop(h, None)
                        changed = True
                        logger.info(f"做种校验：{h} 多次错误，已移出队列")
                    continue
                if self._seed_is_timeout(item):
                    queue.pop(h, None)
                    changed = True
                    logger.info(f"做种校验：{h} 等待超时（{self._seed_max_wait_minutes}分钟），已移出队列")
                    continue
                item["last_check"] = time.time()
        return changed

    @staticmethod
    def _seed_should_remove_missing(item):
        elapsed = (time.time() - item.get("created_at", 0)) / 60
        return elapsed > max(item.get("max_wait_minutes", 120), 30)

    @staticmethod
    def _seed_is_checking(state, dl_type):
        if dl_type == "qbittorrent":
            return state in ["checkingUP", "checkingDL", "checkingResumeData", "checking", "queuedUP", "queuedDL", "moving"]
        return hasattr(state, 'checking') and state.checking

    @staticmethod
    def _seed_is_ready(state, dl_type):
        if dl_type == "qbittorrent":
            return state in ["pausedUP", "stoppedUP", "completed"]
        return hasattr(state, 'stopped') and state.stopped and getattr(state, 'percent_done', 0) == 1

    @staticmethod
    def _seed_is_error(state, dl_type):
        if dl_type == "qbittorrent":
            return state in ["missingFiles", "error", "unknown"]
        return False

    def _seed_is_timeout(self, item):
        elapsed = (time.time() - item.get("created_at", 0)) / 60
        return elapsed > item.get("max_wait_minutes", self._seed_max_wait_minutes)


    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._event.set()
                    self._scheduler.shutdown()
                    self._event.clear()
                self._scheduler = None
        except Exception as e:
            logger.error(f"停止服务失败: {e}")
