"""Record storage helpers for DoubanCenter."""

import hashlib
from typing import Any, Dict, List, Optional

RANK_HISTORY_LIMIT = 500
DETAIL_RECORD_LIMIT = 500
ANTI_CHEAT_LOG_LIMIT = 100

SUBSCRIBE_RECORDS_KEY = "subscribe_records"
ANTI_CHEAT_LOGS_KEY = "anti_cheat_logs"
ARCHIVE_RECORDS_KEY = "archive_records"
FOLIO_DATA_KEY = "folio_data"
FOLIO_WAIT_KEY = "folio_wait"


def trim_records(records: List[dict], limit: Optional[int] = None) -> List[dict]:
    """按上限保留最新记录列表。"""
    if not isinstance(records, list):
        return []
    if not limit or limit <= 0 or len(records) <= limit:
        return records
    return records[-limit:]


def read_list(plugin, key: str) -> List[dict]:
    """从插件存储读取列表数据。"""
    records = plugin.get_data(key) or []
    return records if isinstance(records, list) else []


def write_list(plugin, key: str, records: List[dict], limit: Optional[int] = None) -> List[dict]:
    """写入列表数据并返回实际保存的记录。"""
    records = trim_records(records, limit)
    plugin.save_data(key, records)
    return records


def read_dict(plugin, key: str, plugin_id: str = "") -> Dict[str, Any]:
    """从插件存储读取字典数据。"""
    if plugin_id:
        try:
            data = plugin.get_data(key, plugin_id=plugin_id) or {}
        except TypeError:
            data = plugin.get_data(key) or {}
    else:
        data = plugin.get_data(key) or {}
    return data if isinstance(data, dict) else {}


def write_dict(plugin, key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """写入字典数据并返回实际保存的对象。"""
    data = data if isinstance(data, dict) else {}
    plugin.save_data(key, data)
    return data


def read_folio_data(plugin, plugin_id: str = "") -> Dict[str, Any]:
    """读取豆瓣时间持久化数据。"""
    return read_dict(plugin, FOLIO_DATA_KEY, plugin_id=plugin_id)


def save_folio_data(plugin, data: Dict[str, Any]) -> Dict[str, Any]:
    """保存豆瓣时间持久化数据。"""
    return write_dict(plugin, FOLIO_DATA_KEY, data)


def read_folio_wait(plugin) -> Dict[str, Any]:
    """读取等待处理的豆瓣时间数据。"""
    return read_dict(plugin, FOLIO_WAIT_KEY)


def save_folio_wait(plugin, data: Dict[str, Any]) -> Dict[str, Any]:
    """保存等待处理的豆瓣时间数据。"""
    return write_dict(plugin, FOLIO_WAIT_KEY, data)


def read_subscribe_records(plugin) -> List[dict]:
    """读取订阅历史记录。"""
    return read_list(plugin, SUBSCRIBE_RECORDS_KEY)


def save_subscribe_records(plugin, records: List[dict]) -> List[dict]:
    """保存订阅历史记录。"""
    return write_list(plugin, SUBSCRIBE_RECORDS_KEY, records, DETAIL_RECORD_LIMIT)


def read_anti_cheat_logs(plugin) -> List[dict]:
    """读取观察日志记录。"""
    return read_list(plugin, ANTI_CHEAT_LOGS_KEY)


def save_anti_cheat_logs(plugin, records: List[dict]) -> List[dict]:
    """保存观察日志记录。"""
    return write_list(plugin, ANTI_CHEAT_LOGS_KEY, records, ANTI_CHEAT_LOG_LIMIT)


def read_archive_records(plugin) -> List[dict]:
    """读取归档记录。"""
    return read_list(plugin, ARCHIVE_RECORDS_KEY)


def save_archive_records(plugin, records: List[dict]) -> List[dict]:
    """保存归档记录。"""
    return write_list(plugin, ARCHIVE_RECORDS_KEY, records, DETAIL_RECORD_LIMIT)


def rank_history_key(rank_key: str) -> str:
    """返回内置榜单历史的稳定存储 key。"""
    return "coming_history" if rank_key == "coming" else f"rank_history_{rank_key}"


def custom_rank_history_key(source: str) -> str:
    """返回自定义 RSS 榜单历史的稳定存储 key。"""
    digest = hashlib.sha1((source or "").encode("utf-8")).hexdigest()[:16]
    return f"rank_history_custom_{digest}"


def read_rank_history(plugin, rank_key: str) -> List[dict]:
    """读取内置榜单历史。"""
    return read_list(plugin, rank_history_key(rank_key))


def save_rank_history(plugin, rank_key: str, history: List[dict]) -> List[dict]:
    """保存内置榜单历史。"""
    return write_list(plugin, rank_history_key(rank_key), history, RANK_HISTORY_LIMIT)


def read_custom_rank_history(plugin, source: str) -> List[dict]:
    """读取自定义 RSS 榜单历史。"""
    return read_list(plugin, custom_rank_history_key(source))


def save_custom_rank_history(plugin, source: str, history: List[dict]) -> List[dict]:
    """保存自定义 RSS 榜单历史。"""
    return write_list(plugin, custom_rank_history_key(source), history, RANK_HISTORY_LIMIT)
