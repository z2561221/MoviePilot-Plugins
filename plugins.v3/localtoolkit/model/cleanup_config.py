"""清理库存独立周期的默认配置与旧配置迁移。"""


def default_cleanup_config() -> dict:
    """返回扫描、清理各自的调度及通知设置。"""
    return {
        "scan_enabled": False,
        "scan_cron": "9 0 * * *",
        "scan_notify": True,
        "cleanup_enabled": False,
        "cleanup_cron": "0 * * * *",
        "cleanup_notify": True,
        "days_threshold": 20,
        "selected_library": "",
        "selected_server": "",
        "selected_user": "",
        "filter_played": "played",
        "filter_favorite": "unfav",
        "filter_played_2": "unplayed",
        "filter_favorite_2": "unfav",
        "days_threshold_2": 40,
        "auto_delete": False,
        "auto_delete_delay": 60,
        "dry_run": False,
        "auto_delete_max_count": 10,
        "cycle_cooldown_minutes": 60,
    }


def normalize_cleanup_config(config: dict | None) -> dict:
    """仅在新字段缺失时继承旧值，不自动提高已有清理频率。"""
    raw = dict(config or {})
    for prefix in ("scan", "cleanup"):
        for suffix, legacy in (("enabled", "enabled"), ("cron", "cron"), ("notify", "notify")):
            field = f"{prefix}_{suffix}"
            if field not in raw and legacy in raw:
                raw[field] = raw[legacy]
    for legacy in ("enabled", "cron", "notify"):
        raw.pop(legacy, None)
    return {**default_cleanup_config(), **raw}
