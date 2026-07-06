"""下载中心持久化状态键与轻量读写 helper。"""

from __future__ import annotations

from typing import Any


RENAME_RECORDS_KEY = "rename_records"
RENAME_RETRY_STATE_KEY = "rename_retry_state"
SEED_RECHECK_QUEUE_KEY = "seed_recheck_queue"

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
