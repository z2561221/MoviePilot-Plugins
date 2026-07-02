"""下载中心配置初始化服务。"""

from app.db.site_oper import SiteOper
from app.helper.downloader import DownloaderHelper
from app.log import logger

from ..model.state import (
    IYUU_CLEAR_CACHE_KEY,
    IYUU_ERROR_CACHES_KEY,
    IYUU_PERMANENT_ERROR_CACHES_KEY,
    IYUU_SUCCESS_CACHES_KEY,
)
from ..utils.config import safe_int


def initialize_runtime_config(plugin, config: dict = None) -> dict:
    """根据插件配置初始化运行时字段并返回可继续持久化的配置。"""
    config = config or {}
    plugin.downloader_helper = DownloaderHelper()

    default_mappings = (
        "chdbits.xyz -> ptchdbits.co\n"
        "agsvpt.trackers.work -> agsvpt.com\n"
        "tracker.cinefiles.info -> audiences.me"
    )
    plugin._tracker_mappings = plugin._parse_tracker_mappings(default_mappings)

    if not config:
        return config

    plugin._enabled = config.get("enabled")
    plugin._transfer_enabled = config.get("transfer_enabled", True)
    plugin._onlyonce = config.get("onlyonce")
    plugin._delay_minutes = config.get("delay_minutes", 25)
    plugin._transfer_fallback_enabled = config.get("transfer_fallback_enabled", True)
    try:
        plugin._transfer_fallback_interval_minutes = max(
            1, int(config.get("transfer_fallback_interval_minutes") or 60)
        )
    except (TypeError, ValueError):
        plugin._transfer_fallback_interval_minutes = 60
    plugin._notify = config.get("notify")
    plugin._nolabels = config.get("nolabels")
    plugin._includelabels = config.get("includelabels")
    plugin._includecategory = config.get("includecategory")
    plugin._frompath = config.get("frompath")
    plugin._topath = config.get("topath")
    plugin._fromdownloader = config.get("fromdownloader")
    plugin._todownloader = config.get("todownloader")
    plugin._deletesource = config.get("deletesource")
    plugin._deleteduplicate = config.get("deleteduplicate")
    plugin._fromtorrentpath = config.get("fromtorrentpath")
    plugin._nopaths = config.get("nopaths")
    plugin._transferemptylabel = config.get("transferemptylabel")
    plugin._add_torrent_tags = config.get("add_torrent_tags") or ""
    plugin._torrent_tags = (
        plugin._add_torrent_tags.strip().split(",")
        if plugin._add_torrent_tags
        else []
    )
    plugin._remainoldcat = config.get("remainoldcat")
    plugin._remainoldtag = config.get("remainoldtag")
    plugin._seed_autostart = config.get("seed_autostart", True)
    plugin._seed_skipverify = config.get("seed_skipverify", False)
    plugin._seed_check_interval = safe_int(config.get("seed_check_interval"), 60, 10, 3600)
    plugin._seed_max_wait_minutes = safe_int(config.get("seed_max_wait_minutes"), 120, 10, 1440)

    plugin._rename_enabled = config.get("rename_enabled", True)
    plugin._rename_movie_format = config.get(
        "rename_movie_format",
        "[ {{ title }}{% if year %} ({{ year }}){% endif %} ] - {{original_name}}",
    )
    plugin._rename_tv_format = config.get(
        "rename_tv_format",
        "[ {{ title }}{% if year %} ({{ year }}){% endif %}{% if season_episode %} - {{season_episode}}{% endif %} ] - {{original_name}}",
    )
    plugin._rename_exclude_dirs = config.get("rename_exclude_dirs", "")

    plugin._tag_enabled = config.get("tag_enabled", True)
    plugin._tag_siteprefix = config.get("tag_siteprefix", "🏠")
    plugin._tag_tracker_mappings_str = config.get("tag_tracker_mappings_str", "")
    if plugin._tag_tracker_mappings_str:
        plugin._tracker_mappings.update(plugin._parse_tracker_mappings(plugin._tag_tracker_mappings_str))

    plugin._iyuu_enabled = config.get("iyuu_enabled", False)
    plugin._iyuu_cron = config.get("iyuu_cron", "")
    plugin._iyuu_onlyonce = config.get("iyuu_onlyonce", False)
    plugin._iyuu_token = config.get("iyuu_token", "")
    plugin._iyuu_downloaders = config.get("iyuu_downloaders") or []
    plugin._iyuu_auto_downloader = config.get("iyuu_auto_downloader", "")
    plugin._iyuu_sites = config.get("iyuu_sites") or []
    plugin._iyuu_nolabels = config.get("iyuu_nolabels", "")
    plugin._iyuu_nopaths = config.get("iyuu_nopaths", "")
    plugin._iyuu_size = float(config.get("iyuu_size")) if config.get("iyuu_size") else 0
    plugin._iyuu_auto_category = config.get("iyuu_auto_category", False)
    plugin._iyuu_labelsafterseed = config.get("iyuu_labelsafterseed") or "已整理,辅种"
    plugin._iyuu_categoryafterseed = config.get("iyuu_categoryafterseed", "")
    plugin._iyuu_clearcache = config.get(IYUU_CLEAR_CACHE_KEY, False)
    plugin._iyuu_permanent_error_caches = (
        [] if plugin._iyuu_clearcache else list(config.get(IYUU_PERMANENT_ERROR_CACHES_KEY) or [])
    )
    plugin._iyuu_error_caches = (
        [] if plugin._iyuu_clearcache else list(config.get(IYUU_ERROR_CACHES_KEY) or [])
    )
    plugin._iyuu_success_caches = (
        [] if plugin._iyuu_clearcache else list(config.get(IYUU_SUCCESS_CACHES_KEY) or [])
    )
    if plugin._iyuu_clearcache:
        config[IYUU_PERMANENT_ERROR_CACHES_KEY] = []
        config[IYUU_ERROR_CACHES_KEY] = []
        config[IYUU_SUCCESS_CACHES_KEY] = []
        plugin._iyuu_clearcache = False
        config[IYUU_CLEAR_CACHE_KEY] = False
        plugin.update_config(config=config)
        logger.info("IYUU辅种：已清除所有辅种缓存")
    plugin._trim_seed_cache(plugin._iyuu_permanent_error_caches)
    plugin._trim_seed_cache(plugin._iyuu_error_caches)
    plugin._trim_seed_cache(plugin._iyuu_success_caches)

    if plugin._iyuu_sites:
        all_site_ids = [
            site.id for site in SiteOper().list_order_by_pri()
        ] + [site.get("id") for site in plugin._custom_sites()]
        plugin._iyuu_sites = [sid for sid in all_site_ids if sid in plugin._iyuu_sites]
        plugin._update_iyuu_config(config)

    return config
