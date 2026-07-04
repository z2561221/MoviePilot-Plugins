"""
DownloadManagerLocal v3.2.3 - MoviePilot 本地插件
基于官方自动转移做种 v1.10.3，整合 IYUU 自动辅种，支持转移后自动重命名 + 打站点标签
"""
from datetime import datetime, timedelta
from threading import Event as ThreadEvent
import threading
from typing import Any, List, Dict, Tuple, Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.event import eventmanager, Event
from app.core.meta.metabase import MetaBase
from app.log import logger
from app.plugins import _PluginBase
from app.plugins.downloadmanagerlocal.iyuu_helper import IyuuHelper
from app.schemas import ServiceInfo
from app.schemas.types import EventType

from .adapter.moviepilot import get_downloader_service
from .model.state import SEED_RECHECK_QUEUE_KEY
from .utils.config import safe_int, is_plugin_active, is_transfer_active
from .utils.tracker import parse_tracker_mappings
from .utils.path import convert_save_path
from .utils.torrent_adapter import get_hash, get_label, get_category, get_save_path, get_torrent_size
from .api import api_downloaders as _api_downloaders, api_sites as _api_sites, api_rename_history as _api_rename_history, api_delete_rename_history as _api_delete_rename_history, api_recovery_torrent as _api_recovery_torrent, api_retry_renames as _api_retry_renames, api_retry_rename as _api_retry_rename, api_diagnostics as _api_diagnostics, api_overview as _api_overview, api_rename_archive as _api_rename_archive, api_restore_rename_archive as _api_restore_rename_archive, api_delete_rename_archive as _api_delete_rename_archive
from .service.rename import rename_torrent as _rename_torrent_impl, format_torrent_name as _format_torrent_name_impl, save_rename_record as _save_rename_record_impl, get_failed_rename_hashes as _get_failed_rename_hashes_impl, retry_failed_renames as _retry_failed_renames_impl, retry_rename_by_hash as _retry_rename_by_hash_impl, rename_iyuu_torrent_by_source_record as _rename_iyuu_torrent_by_source_record_impl
from .service.archive import record_rename_failure as _record_rename_failure_impl, clear_rename_retry_state as _clear_rename_retry_state_impl, is_rename_archived as _is_rename_archived_impl, list_rename_archive as _list_rename_archive_impl, restore_rename_archive as _restore_rename_archive_impl, delete_rename_archive as _delete_rename_archive_impl, rename_archive_stats as _rename_archive_stats_impl
from .service.diagnostics import build_diagnostics as _build_diagnostics_impl
from .service.site_tag import tag_torrent as _tag_torrent_impl, find_site_by_domain as _find_site_by_domain_impl
from .service.recheck import load_seed_recheck_queue as _load_seed_recheck_queue_impl, save_seed_recheck_queue as _save_seed_recheck_queue_impl, register_seed_recheck as _register_seed_recheck_impl, ensure_seed_recheck_worker as _ensure_seed_recheck_worker_impl, seed_recheck_loop as _seed_recheck_loop_impl, process_seed_recheck_once as _process_seed_recheck_once_impl, seed_should_remove_missing as _seed_should_remove_missing_impl, seed_is_checking as _seed_is_checking_impl, seed_is_ready as _seed_is_ready_impl, seed_is_error as _seed_is_error_impl, seed_is_timeout as _seed_is_timeout_impl, run_recheck_cycle as _check_recheck_impl, sweep_paused_seed_tasks as _sweep_paused_seed_tasks_impl, can_seed_paused_torrent as _can_seeding_impl
from .service.transfer import validate_config as _validate_config_impl, download_torrent as _download_impl, post_transfer_process as _post_transfer_process_impl, transfer as _transfer_impl, fallback_transfer as _fallback_transfer_impl, delayed_transfer as _delayed_transfer_impl, retry_pending_renames as _retry_pending_renames_impl
from .service.iyuu import iyuu_service_infos as _iyuu_service_infos_impl, iyuu_auto_service_info as _iyuu_auto_service_info_impl, iyuu_auto_seed as _iyuu_auto_seed_impl, iyuu_seed_torrents as _iyuu_seed_torrents_impl, iyuu_download_torrent as _iyuu_download_torrent_impl, iyuu_download as _iyuu_download_impl, iyuu_get_download_url as _iyuu_get_download_url_impl, iyuu_save_history as _iyuu_save_history_impl, append_iyuu_cache as _append_iyuu_cache_impl, trim_seed_cache as _trim_seed_cache_impl, custom_sites as _custom_sites_impl, update_iyuu_config as _update_iyuu_config_impl
from .controller.api import build_api_routes as _build_api_routes_impl
from .service.events import handle_transfer_complete_event as _handle_transfer_complete_event_impl
from .service.config import initialize_runtime_config as _initialize_runtime_config_impl
from .service.scheduler import build_plugin_services as _build_plugin_services_impl

class DownloadManagerLocal(_PluginBase):
    # 插件名称
    plugin_name = "下载中心"
    # 插件描述
    plugin_desc = "转移做种 + IYUU辅种 + 种子重命名 + 站点标签，一站式下载管理。"
    # 插件图标
    plugin_icon = "download.png"
    # 插件颜色
    plugin_color = "#4CAF50"
    # 插件版本
    plugin_version = "3.2.4"
    # 插件作者
    plugin_author = "牧濑红莉栖"
    # 作者主页
    author_url = "https://github.com/z2561221"
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
    _seed_recheck_queue_key = SEED_RECHECK_QUEUE_KEY

    # 任务标签
    _torrent_tags = []
    # tracker 映射
    _tracker_mappings: Dict[str, str] = {}

    # 辅助
    downloader_helper = None

    def init_plugin(self, config: dict = None):
        config = _initialize_runtime_config_impl(self, config)

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
        return safe_int(value, default, min_value, max_value)

    @staticmethod
    def _parse_tracker_mappings(mapping_str: str) -> dict:
        return parse_tracker_mappings(mapping_str)

    @staticmethod
    def get_hash(torrent, dl_type: str):
        return get_hash(torrent, dl_type)

    @staticmethod
    def __get_hash(torrent, dl_type: str):
        return DownloadManagerLocal.get_hash(torrent, dl_type)

    @staticmethod
    def get_label(torrent, dl_type: str):
        return get_label(torrent, dl_type)

    @staticmethod
    def __get_label(torrent, dl_type: str):
        return DownloadManagerLocal.get_label(torrent, dl_type)

    @staticmethod
    def get_category(torrent, dl_type: str):
        return get_category(torrent, dl_type)

    @staticmethod
    def __get_category(torrent, dl_type: str):
        return DownloadManagerLocal.get_category(torrent, dl_type)

    @staticmethod
    def get_save_path(torrent, dl_type: str):
        return get_save_path(torrent, dl_type)

    @staticmethod
    def __get_save_path(torrent, dl_type: str):
        return DownloadManagerLocal.get_save_path(torrent, dl_type)

    @staticmethod
    def get_torrent_size(torrent, dl_type: str):
        return get_torrent_size(torrent, dl_type)

    @staticmethod
    def __get_torrent_size(torrent, dl_type: str):
        return DownloadManagerLocal.get_torrent_size(torrent, dl_type)

    @staticmethod
    def convert_save_path(save_path: str, from_root: str, to_root: str):
        return convert_save_path(save_path, from_root, to_root)

    @staticmethod
    def __convert_save_path(save_path: str, from_root: str, to_root: str):
        return DownloadManagerLocal.convert_save_path(save_path, from_root, to_root)

    @staticmethod
    def service_info(name: str) -> Optional[ServiceInfo]:
        """
        服务信息
        """
        if not name:
            logger.warning("尚未配置下载器，请检查配置")
            return None

        service = get_downloader_service(name)
        if not service or not service.instance:
            logger.warning(f"获取下载器 {name} 实例失败，请检查配置")
            return None

        if service.instance.is_inactive():
            logger.warning(f"下载器 {name} 未连接，请检查配置")
            return None

        return service

    def get_state(self):
        return is_plugin_active(self)

    @property
    def _transfer_active(self) -> bool:
        """转移做种功能是否激活（总开关 + 转移开关 + 配置完整）"""
        return is_transfer_active(self)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return _build_api_routes_impl(self)

    def api_downloaders(self):
        return _api_downloaders(self)

    def api_sites(self):
        return _api_sites(self)

    def api_rename_history(self, page: int = 1, page_size: int = 15):
        return _api_rename_history(self, page, page_size)

    def api_overview(self):
        return _api_overview(self)

    def api_delete_rename_history(self, hash: str = ""):
        return _api_delete_rename_history(self, hash)

    def api_rename_archive(self, page: int = 1, page_size: int = 15):
        return _api_rename_archive(self, page, page_size)

    def api_restore_rename_archive(self, hash: str = ""):
        return _api_restore_rename_archive(self, hash)

    def api_delete_rename_archive(self, hash: str = ""):
        return _api_delete_rename_archive(self, hash)

    def api_recovery_torrent(self, hash: str = ""):
        return _api_recovery_torrent(self, hash)

    def api_retry_renames(self):
        return _api_retry_renames(self)

    def api_retry_rename(self, hash: str = ""):
        return _api_retry_rename(self, hash)

    def api_diagnostics(self):
        return _api_diagnostics(self)

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        """
        return _build_plugin_services_impl(self)

    def _fallback_transfer(self):
        return _fallback_transfer_impl(self)


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
        return _validate_config_impl(self)

    def __download(self, service: ServiceInfo, content: bytes,
                   save_path: str, torrent) -> Optional[str]:
        return _download_impl(self, service, content, save_path, torrent)
        return None

    def transfer(self, trigger_source: str = "手动/定时"):
        return _transfer_impl(self, trigger_source)

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
        return _check_recheck_impl(self)

    def _sweep_paused_seed_tasks(self, check_services: List[ServiceInfo]):
        """兜底扫描已完成但暂停的转移/铺种任务，并自动开始做种。"""
        return _sweep_paused_seed_tasks_impl(self, check_services)

    @staticmethod
    def __can_seeding(torrent: Any, dl_type: str):
        """
        判断种子是否可以做种并处于暂停状态
        """
        return _can_seeding_impl(torrent, dl_type)

    # ════════════════════════════════════════════════════════════
    # v2.0.0: 转移后自动重命名 + 站点标签
    # ════════════════════════════════════════════════════════════

    def _post_transfer_process(self, to_service: ServiceInfo, torrent_hash: str):
        return _post_transfer_process_impl(self, to_service, torrent_hash)

    def _rename_torrent(self, dl, dl_type: str, torrent_hash: str, torrent_name: str, save_path: str):
        return _rename_torrent_impl(self, dl, dl_type, torrent_hash, torrent_name, save_path)

    def _tag_torrent(self, dl, dl_type: str, torrent_hash: str, torrent_tags: list, trackers: list):
        return _tag_torrent_impl(self, dl, dl_type, torrent_hash, torrent_tags, trackers)

    @staticmethod
    def _find_site_by_domain(domain: str) -> Optional[str]:
        return _find_site_by_domain_impl(domain)

    @staticmethod
    def _format_torrent_name(template_string: str, meta: MetaBase, mediainfo) -> Optional[str]:
        return _format_torrent_name_impl(template_string, meta, mediainfo)

    # ════════════════════════════════════════════════════════════
    # 重命名记录持久化
    # ════════════════════════════════════════════════════════════

    def _save_rename_record(self, torrent_hash: str, original_name: str, after_name: str,
                            success: bool, reason: str = ""):
        return _save_rename_record_impl(self, torrent_hash, original_name, after_name, success, reason)

    def _get_failed_rename_hashes(self) -> set:
        return _get_failed_rename_hashes_impl(self)

    def _retry_failed_renames(self, to_service: ServiceInfo):
        return _retry_failed_renames_impl(self, to_service)

    def _retry_pending_renames(self):
        return _retry_pending_renames_impl(self)

    def _retry_rename(self, hash: str = ""):
        to_service = self.service_info(self._todownloader)
        return _retry_rename_by_hash_impl(self, to_service, hash)

    def _diagnostics(self):
        return _build_diagnostics_impl(self)

    def record_rename_failure(self, torrent_hash: str, torrent_name: str,
                              category: str = "", reason: str = ""):
        return _record_rename_failure_impl(self, torrent_hash, torrent_name, category, reason)

    def clear_rename_retry_state(self, torrent_hash: str):
        return _clear_rename_retry_state_impl(self, torrent_hash)

    def is_rename_archived(self, torrent_hash: str):
        return _is_rename_archived_impl(self, torrent_hash)

    def list_rename_archive(self, page: int = 1, page_size: int = 15):
        return _list_rename_archive_impl(self, page, page_size)

    def restore_rename_archive(self, torrent_hash: str):
        return _restore_rename_archive_impl(self, torrent_hash)

    def delete_rename_archive(self, torrent_hash: str):
        return _delete_rename_archive_impl(self, torrent_hash)

    def rename_archive_stats(self):
        return _rename_archive_stats_impl(self)

    # ════════════════════════════════════════════════════════════
    # v2.3.0: 事件驱动转移
    # ════════════════════════════════════════════════════════════

    @eventmanager.register(EventType.TransferComplete)
    def on_transfer_complete(self, event: Event):
        """
        监听 TransferComplete 事件，延迟 N 分钟后自动转移做种
        """
        return _handle_transfer_complete_event_impl(self, event)

    def _delayed_transfer(self):
        return _delayed_transfer_impl(self)

    # ════════════════════════════════════════════════════════════
    # v3.0.0: IYUU 自动辅种
    # ════════════════════════════════════════════════════════════

    @property
    def _iyuu_service_infos(self):
        return _iyuu_service_infos_impl(self)

    @property
    def _iyuu_auto_service_info(self):
        return _iyuu_auto_service_info_impl(self)

    def iyuu_auto_seed(self):
        return _iyuu_auto_seed_impl(self)

    def _iyuu_seed_torrents(self, hash_strs: list, service: ServiceInfo):
        return _iyuu_seed_torrents_impl(self, hash_strs, service)

    def _iyuu_download_torrent(self, seed: dict, service: ServiceInfo, save_path: str, save_category: str,
                               source_hash: str = None, site_info: dict = None):
        return _iyuu_download_torrent_impl(self, seed, service, save_path, save_category, source_hash, site_info)

    def _rename_iyuu_torrent_by_source_record(self, dl, dl_type: str, torrent_hash: str,
                                             torrent_name: str, source_hash: str = None) -> bool:
        return _rename_iyuu_torrent_by_source_record_impl(self, dl, dl_type, torrent_hash, torrent_name, source_hash) is not None

    def _iyuu_download(self, service: ServiceInfo, content: bytes,
                       save_path: str, save_category: str, site_name: str,
                       expected_hash: str = None, torrent_url: str = None) -> Optional[str]:
        return _iyuu_download_impl(self, service, content, save_path, save_category, site_name, expected_hash, torrent_url)

    def _iyuu_get_download_url(self, seed: dict, site: dict, base_url: str, force_page: bool = False) -> Optional[str]:
        return _iyuu_get_download_url_impl(self, seed, site, base_url, force_page)

    def _iyuu_save_history(self, current_hash: str, downloader: str, success_torrents: list):
        return _iyuu_save_history_impl(self, current_hash, downloader, success_torrents)

    @staticmethod
    def _append_iyuu_cache(cache_list: list, info_hash: str):
        return _append_iyuu_cache_impl(cache_list, info_hash)

    @staticmethod
    def _trim_seed_cache(cache_list: list):
        return _trim_seed_cache_impl(cache_list)

    @staticmethod
    def _custom_sites() -> list:
        return _custom_sites_impl()

    def _update_iyuu_config(self, config: dict = None):
        return _update_iyuu_config_impl(self, config)

    # ════════════════════════════════════════════════════════════
    # v3.0.14: 按需做种校验
    # ════════════════════════════════════════════════════════════

    def _load_seed_recheck_queue(self):
        return _load_seed_recheck_queue_impl(self)

    def _save_seed_recheck_queue(self, queue):
        return _save_seed_recheck_queue_impl(self, queue)

    def _register_seed_recheck(self, downloader, hashes, source):
        return _register_seed_recheck_impl(self, downloader, hashes, source)

    def _ensure_seed_recheck_worker(self):
        return _ensure_seed_recheck_worker_impl(self)

    def _seed_recheck_loop(self):
        return _seed_recheck_loop_impl(self)

    def _process_seed_recheck_once(self, queue):
        return _process_seed_recheck_once_impl(self, queue)

    @staticmethod
    def _seed_should_remove_missing(item):
        return _seed_should_remove_missing_impl(item)

    @staticmethod
    def _seed_is_checking(state, dl_type):
        return _seed_is_checking_impl(state, dl_type)

    @staticmethod
    def _seed_is_ready(state, dl_type):
        return _seed_is_ready_impl(state, dl_type)

    @staticmethod
    def _seed_is_error(state, dl_type):
        return _seed_is_error_impl(state, dl_type)

    def _seed_is_timeout(self, item):
        return _seed_is_timeout_impl(item, self._seed_max_wait_minutes)


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
