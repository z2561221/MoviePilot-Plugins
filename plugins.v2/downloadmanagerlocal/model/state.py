"""下载中心持久化状态键与轻量读写 helper。"""

from __future__ import annotations

from typing import Any, Iterable


RENAME_RECORDS_KEY = "rename_records"
RENAME_RETRY_STATE_KEY = "rename_retry_state"
SEED_RECHECK_QUEUE_KEY = "seed_recheck_queue"

SPEED_MONITOR_SCHEMA_VERSION = 1
SPEED_MONITOR_SESSIONS_KEY = "speed_monitor_sessions"
SPEED_MONITOR_BASELINES_KEY = "speed_monitor_baselines"
SPEED_MONITOR_ALERTS_KEY = "speed_monitor_alerts"
SPEED_MONITOR_TERMINAL_TTL_SECONDS = 30 * 24 * 60 * 60
SPEED_MONITOR_TERMINAL_MAX_ITEMS = 1000
SPEED_MONITOR_HEALTH_SAMPLE_WINDOW = 20

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
    "speed_monitor_sessions": SPEED_MONITOR_SESSIONS_KEY,
    "speed_monitor_baselines": SPEED_MONITOR_BASELINES_KEY,
    "speed_monitor_alerts": SPEED_MONITOR_ALERTS_KEY,
    "iyuu_history": f"{IYUU_HISTORY_KEY_PREFIX}<source_hash>",
    "iyuu_source": f"{IYUU_SOURCE_KEY_PREFIX}<seed_hash>",
    "iyuu_cache_config": IYUU_CACHE_CONFIG_KEYS,
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
