"""下载中心配置初始化服务。"""

from app.sdk.logging import logger

from ..adapter.moviepilot import create_downloader_helper, list_builtin_sites
from ..model.state import (
    IYUU_CLEAR_CACHE_KEY,
    IYUU_ERROR_CACHES_KEY,
    IYUU_PERMANENT_ERROR_CACHES_KEY,
    IYUU_SUCCESS_CACHES_KEY,
)
from ..utils.config import (
    PLUGIN_CONFIG_DEFAULTS,
    normalize_speed_monitor_config,
    normalize_upload_limit_config,
    safe_int,
)
from ..utils.tracker import parse_tracker_mappings


def initialize_runtime_config(plugin, config: dict = None) -> dict:
    """根据插件配置初始化运行时字段并返回可继续持久化的配置。"""
    config = config or {}
    plugin.downloader_helper = create_downloader_helper()

    default_mappings = (
        "chdbits.xyz -> ptchdbits.co\n"
        "agsvpt.trackers.work -> agsvpt.com\n"
        "tracker.cinefiles.info -> audiences.me"
    )
    plugin._tracker_mappings = parse_tracker_mappings(default_mappings)

    monitor_config = normalize_speed_monitor_config(config)
    for key, value in monitor_config.items():
        setattr(plugin, f"_{key}", value)

    upload_limit_config = normalize_upload_limit_config(config)
    for key, value in upload_limit_config.items():
        setattr(plugin, f"_{key}", value)

    if not config:
        return config

    config.update(monitor_config)
    config.update(upload_limit_config)
    defaults = PLUGIN_CONFIG_DEFAULTS

    plugin._enabled = config.get("enabled", defaults["enabled"])
    plugin._transfer_enabled = config.get("transfer_enabled", defaults["transfer_enabled"])
    plugin._onlyonce = config.get("onlyonce", defaults["onlyonce"])
    plugin._delay_minutes = config.get("delay_minutes", defaults["delay_minutes"])
    plugin._transfer_fallback_enabled = config.get(
        "transfer_fallback_enabled", defaults["transfer_fallback_enabled"]
    )
    try:
        plugin._transfer_fallback_interval_minutes = max(1, int(
            config.get("transfer_fallback_interval_minutes")
            or defaults["transfer_fallback_interval_minutes"]
        ))
    except (TypeError, ValueError):
        plugin._transfer_fallback_interval_minutes = defaults["transfer_fallback_interval_minutes"]
    plugin._notify = config.get("notify", defaults["notify"])
    plugin._nolabels = config.get("nolabels", defaults["nolabels"])
    plugin._includelabels = config.get("includelabels", defaults["includelabels"])
    plugin._includecategory = config.get("includecategory", defaults["includecategory"])
    plugin._frompath = config.get("frompath", defaults["frompath"])
    plugin._topath = config.get("topath", defaults["topath"])
    plugin._fromdownloader = config.get("fromdownloader", defaults["fromdownloader"])
    plugin._todownloader = config.get("todownloader", defaults["todownloader"])
    plugin._deletesource = config.get("deletesource", defaults["deletesource"])
    plugin._deleteduplicate = config.get("deleteduplicate", defaults["deleteduplicate"])
    plugin._fromtorrentpath = config.get("fromtorrentpath", defaults["fromtorrentpath"])
    plugin._nopaths = config.get("nopaths", defaults["nopaths"])
    plugin._transferemptylabel = config.get("transferemptylabel", defaults["transferemptylabel"])
    plugin._add_torrent_tags = config.get("add_torrent_tags") or ""
    plugin._torrent_tags = (
        plugin._add_torrent_tags.strip().split(",")
        if plugin._add_torrent_tags
        else []
    )
    plugin._remainoldcat = config.get("remainoldcat", defaults["remainoldcat"])
    plugin._remainoldtag = config.get("remainoldtag", defaults["remainoldtag"])
    plugin._seed_autostart = config.get("seed_autostart", defaults["seed_autostart"])
    plugin._seed_skipverify = config.get("seed_skipverify", defaults["seed_skipverify"])
    plugin._seed_check_interval = safe_int(config.get("seed_check_interval"), 60, 10, 3600)
    plugin._seed_max_wait_minutes = safe_int(config.get("seed_max_wait_minutes"), 120, 10, 1440)

    plugin._rename_enabled = config.get("rename_enabled", defaults["rename_enabled"])
    plugin._rename_movie_format = config.get(
        "rename_movie_format",
        defaults["rename_movie_format"],
    )
    plugin._rename_tv_format = config.get(
        "rename_tv_format",
        defaults["rename_tv_format"],
    )
    plugin._rename_exclude_dirs = config.get("rename_exclude_dirs", defaults["rename_exclude_dirs"])

    plugin._tag_enabled = config.get("tag_enabled", defaults["tag_enabled"])
    plugin._tag_siteprefix = config.get("tag_siteprefix", defaults["tag_siteprefix"])
    plugin._tag_tracker_mappings_str = config.get("tag_tracker_mappings_str", defaults["tag_tracker_mappings_str"])
    if plugin._tag_tracker_mappings_str:
        plugin._tracker_mappings.update(parse_tracker_mappings(plugin._tag_tracker_mappings_str))

    plugin._iyuu_enabled = config.get("iyuu_enabled", defaults["iyuu_enabled"])
    plugin._iyuu_cron = config.get("iyuu_cron", defaults["iyuu_cron"])
    plugin._iyuu_onlyonce = config.get("iyuu_onlyonce", defaults["iyuu_onlyonce"])
    plugin._iyuu_token = config.get("iyuu_token", defaults["iyuu_token"])
    plugin._iyuu_downloaders = config.get("iyuu_downloaders") or defaults["iyuu_downloaders"]
    plugin._iyuu_auto_downloader = config.get("iyuu_auto_downloader", defaults["iyuu_auto_downloader"])
    plugin._iyuu_sites = config.get("iyuu_sites") or defaults["iyuu_sites"]
    plugin._iyuu_nolabels = config.get("iyuu_nolabels", defaults["iyuu_nolabels"])
    plugin._iyuu_nopaths = config.get("iyuu_nopaths", defaults["iyuu_nopaths"])
    plugin._iyuu_size = float(config.get("iyuu_size", defaults["iyuu_size"])) if config.get("iyuu_size") else 0
    plugin._iyuu_auto_category = config.get("iyuu_auto_category", defaults["iyuu_auto_category"])
    plugin._iyuu_labelsafterseed = config.get("iyuu_labelsafterseed") or defaults["iyuu_labelsafterseed"]
    plugin._iyuu_categoryafterseed = config.get("iyuu_categoryafterseed", defaults["iyuu_categoryafterseed"])
    plugin._iyuu_clearcache = config.get(IYUU_CLEAR_CACHE_KEY, defaults["iyuu_clearcache"])
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
            site.id for site in list_builtin_sites()
        ] + [site.get("id") for site in plugin._custom_sites()]
        plugin._iyuu_sites = [sid for sid in all_site_ids if sid in plugin._iyuu_sites]
        plugin._update_iyuu_config(config)

    return config
