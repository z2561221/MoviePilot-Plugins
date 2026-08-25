"""下载中心持久化状态键与轻量读写 helper。"""

from __future__ import annotations

from datetime import date
from threading import RLock
from typing import Any, Iterable


RENAME_RECORDS_KEY = "rename_records"
RENAME_RETRY_STATE_KEY = "rename_retry_state"
SEED_RECHECK_QUEUE_KEY = "seed_recheck_queue"
TRANSFER_STATS_KEY = "transfer_stats"
TRANSFER_STATS_SCHEMA_VERSION = 2
_TRANSFER_STATS_LOCK = RLock()

IYUU_STATS_KEY = "iyuu_stats"
IYUU_STATS_SCHEMA_VERSION = 1
_IYUU_STATS_LOCK = RLock()

SPEED_MONITOR_SCHEMA_VERSION = 1
SPEED_MONITOR_SESSIONS_KEY = "speed_monitor_sessions"
SPEED_MONITOR_BASELINES_KEY = "speed_monitor_baselines"
SPEED_MONITOR_ALERTS_KEY = "speed_monitor_alerts"
SPEED_MONITOR_TERMINAL_TTL_SECONDS = 30 * 24 * 60 * 60
SPEED_MONITOR_TERMINAL_MAX_ITEMS = 1000
SPEED_MONITOR_HEALTH_SAMPLE_WINDOW = 20

UPLOAD_LIMIT_STATE_KEY = "upload_limit_state"

IYUU_HISTORY_KEY_PREFIX = "iyuu_"
IYUU_SOURCE_KEY_PREFIX = "iyuu_source_"
IYUU_PERMANENT_ERROR_CACHES_KEY = "iyuu_permanent_error_caches"
IYUU_ERROR_CACHES_KEY = "iyuu_error_caches"
IYUU_SUCCESS_CACHES_KEY = "iyuu_success_caches"
IYUU_CLEAR_CACHE_KEY = "iyuu_clearcache"
IYUU_CACHE_CONFIG_KEYS = (
    IYUU_PERMANENT_ERROR_CACHES_KEY,
    IYUU_ERROR_CACHES_KEY,
    IYUU_SUCCESS_CACHES_KEY,
)

PERSISTED_STATE_KEYS = {
    "rename_history": RENAME_RECORDS_KEY,
    "rename_retry_state": RENAME_RETRY_STATE_KEY,
    "seed_recheck_queue": SEED_RECHECK_QUEUE_KEY,
    "transfer_stats": TRANSFER_STATS_KEY,
    "speed_monitor_sessions": SPEED_MONITOR_SESSIONS_KEY,
    "speed_monitor_baselines": SPEED_MONITOR_BASELINES_KEY,
    "speed_monitor_alerts": SPEED_MONITOR_ALERTS_KEY,
    "upload_limit_state": UPLOAD_LIMIT_STATE_KEY,
    "iyuu_history": f"{IYUU_HISTORY_KEY_PREFIX}<source_hash>",
    "iyuu_source": f"{IYUU_SOURCE_KEY_PREFIX}<seed_hash>",
    "iyuu_cache_config": IYUU_CACHE_CONFIG_KEYS,
    "iyuu_stats": IYUU_STATS_KEY,
}


def iyuu_history_key(source_hash: str) -> str:
    """返回指定母种 hash 的 IYUU 辅种历史持久化 key。"""
    return f"{IYUU_HISTORY_KEY_PREFIX}{source_hash}"


def iyuu_source_key(seed_hash: str) -> str:
    """返回指定辅种 hash 反查母种 hash 的持久化 key。"""
    return f"{IYUU_SOURCE_KEY_PREFIX}{seed_hash}"


def load_dict_data(plugin: Any, key: str) -> dict:
    """读取 dict 类型持久化数据，非 dict 或空值按旧逻辑回退为空字典。"""
    value = plugin.get_data(key)
    return value if isinstance(value, dict) else {}


def save_dict_data(plugin: Any, key: str, value: dict | None) -> None:
    """保存 dict 类型持久化数据，空值按旧逻辑持久化为空字典。"""
    plugin.save_data(key, value or {})


def _non_negative_int(value: Any) -> int:
    """把不可信计数规范为非负整数。"""
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def today_stamp() -> str:
    """返回本地时区当天日期戳，用于今日计数按天归零。"""
    return date.today().isoformat()


def _normalize_daily_counters(
    payload: dict,
    *,
    total_keys: tuple[str, ...],
    today_keys: tuple[str, ...],
) -> dict[str, Any]:
    """按当天日期戳规范化今日计数，跨天读取时视为归零且不写盘。

    :param payload: 原始持久化字典
    :param total_keys: 累计计数字段名，按父子顺序排列，后者必须是前者的子集
    :param today_keys: 今日计数字段名，与累计字段一一对应
    :return: 规范化后的今日日期戳与今日计数字段
    """
    today = today_stamp()
    if str(payload.get("today_date") or "").strip() != today:
        return {"today_date": today, **{key: 0 for key in today_keys}}
    normalized: dict[str, Any] = {"today_date": today}
    ceiling: int | None = None
    for total_key, today_key in zip(total_keys, today_keys):
        limit = _non_negative_int(payload.get(total_key))
        if ceiling is not None:
            limit = min(limit, ceiling)
        value = min(limit, _non_negative_int(payload.get(today_key)))
        normalized[today_key] = value
        ceiling = value
    return normalized


def load_transfer_stats(plugin: Any) -> dict[str, Any]:
    """读取并规范化累计与今日转种成功统计。"""
    raw_value = plugin.get_data(TRANSFER_STATS_KEY)
    payload = raw_value if isinstance(raw_value, dict) else {}
    success_total = _non_negative_int(payload.get("success_total"))
    fallback_success = min(
        success_total,
        _non_negative_int(payload.get("fallback_success")),
    )
    daily = _normalize_daily_counters(
        payload,
        total_keys=("success_total", "fallback_success"),
        today_keys=("today_success", "today_fallback"),
    )
    return {
        "schema_version": TRANSFER_STATS_SCHEMA_VERSION,
        "success_total": success_total,
        "fallback_success": fallback_success,
        **daily,
    }


def record_transfer_success(plugin: Any, count: int, *, fallback: bool) -> dict[str, Any]:
    """累计一次转种成功批次，并返回最新持久化统计。"""
    increment = _non_negative_int(count)
    with _TRANSFER_STATS_LOCK:
        stats = load_transfer_stats(plugin)
        if increment:
            stats["success_total"] += increment
            stats["today_success"] += increment
            if fallback:
                stats["fallback_success"] += increment
                stats["today_fallback"] += increment
            plugin.save_data(TRANSFER_STATS_KEY, stats)
        return stats


def load_iyuu_stats(plugin: Any) -> dict[str, Any]:
    """读取并规范化累计与今日 IYUU 辅种统计。"""
    raw_value = plugin.get_data(IYUU_STATS_KEY)
    payload = raw_value if isinstance(raw_value, dict) else {}
    daily = _normalize_daily_counters(
        payload,
        total_keys=("success_total", "fail_total"),
        today_keys=("today_success", "today_fail"),
    )
    return {
        "schema_version": IYUU_STATS_SCHEMA_VERSION,
        "success_total": _non_negative_int(payload.get("success_total")),
        "fail_total": _non_negative_int(payload.get("fail_total")),
        "today_date": daily["today_date"],
        "today_success": daily["today_success"],
        "today_fail": daily["today_fail"],
    }


def record_iyuu_results(plugin: Any, *, success: int, fail: int) -> dict[str, Any]:
    """累计一轮 IYUU 辅种的成功与失败数，并返回最新持久化统计。"""
    success_increment = _non_negative_int(success)
    fail_increment = _non_negative_int(fail)
    with _IYUU_STATS_LOCK:
        stats = load_iyuu_stats(plugin)
        if success_increment or fail_increment:
            stats["success_total"] += success_increment
            stats["today_success"] += success_increment
            stats["fail_total"] += fail_increment
            stats["today_fail"] += fail_increment
            plugin.save_data(IYUU_STATS_KEY, stats)
        return stats



class SpeedMonitorStateMigrationError(ValueError):
    """速度监控持久化状态无法安全迁移。"""


def migrate_speed_monitor_payload(value: Any, state_name: str) -> dict:
    """把缺失版本或旧版速度监控状态显式迁移到当前 schema。"""
    if value in (None, {}):
        return {"schema_version": SPEED_MONITOR_SCHEMA_VERSION, "items": {}}
    if not isinstance(value, dict):
        raise SpeedMonitorStateMigrationError(f"{state_name} state must be a dict")
    version = value.get("schema_version")
    if version is None:
        items = value.get("items") if "items" in value else value
    elif version in {0, SPEED_MONITOR_SCHEMA_VERSION}:
        items = value.get("items", {})
    else:
        raise SpeedMonitorStateMigrationError(
            f"unsupported {state_name} schema version: {version}"
        )
    if not isinstance(items, dict):
        raise SpeedMonitorStateMigrationError(f"{state_name} items must be a dict")
    return {
        "schema_version": SPEED_MONITOR_SCHEMA_VERSION,
        "items": dict(items),
    }


def load_speed_monitor_items(plugin: Any, key: str, state_name: str) -> dict:
    """读取并按需迁移速度监控状态，迁移成功后回写当前 schema。"""
    raw_value = plugin.get_data(key)
    payload = migrate_speed_monitor_payload(raw_value, state_name)
    if raw_value != payload:
        plugin.save_data(key, payload)
    return dict(payload["items"])


def save_speed_monitor_items(plugin: Any, key: str, items: dict) -> None:
    """以当前 schema 保存速度监控状态项。"""
    plugin.save_data(key, {
        "schema_version": SPEED_MONITOR_SCHEMA_VERSION,
        "items": dict(items),
    })


def trim_terminal_records(
    records: dict,
    *,
    now: float,
    active_statuses: Iterable[str] = ("active", "pending"),
    timestamp_field: str = "terminal_at",
    ttl_seconds: int = SPEED_MONITOR_TERMINAL_TTL_SECONDS,
    max_items: int = SPEED_MONITOR_TERMINAL_MAX_ITEMS,
) -> dict:
    """按 TTL 和数量裁剪终态记录，同时无条件保留活跃记录。"""
    active_statuses = set(active_statuses)
    active = {}
    terminal = []
    for key, value in (records or {}).items():
        item = value if isinstance(value, dict) else {}
        if str(item.get("status") or "") in active_statuses:
            active[key] = value
            continue
        try:
            timestamp = float(item.get(timestamp_field) or 0)
        except (TypeError, ValueError):
            timestamp = 0.0
        if timestamp > 0 and float(now) - timestamp <= ttl_seconds:
            terminal.append((timestamp, key, value))
    terminal.sort(key=lambda item: item[0], reverse=True)
    result = dict(active)
    result.update({key: value for _, key, value in terminal[:max_items]})
    return result


def trim_health_samples(samples: Any) -> list:
    """仅保留最近 20 条下载器健康完成样本。"""
    values = list(samples) if isinstance(samples, (list, tuple)) else []
    return values[-SPEED_MONITOR_HEALTH_SAMPLE_WINDOW:]
