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
    """Return a list trimmed to the latest records."""
    if not isinstance(records, list):
        return []
    if not limit or limit <= 0 or len(records) <= limit:
        return records
    return records[-limit:]


def read_list(plugin, key: str) -> List[dict]:
    """Read a list value from plugin storage."""
    records = plugin.get_data(key) or []
    return records if isinstance(records, list) else []


def write_list(plugin, key: str, records: List[dict], limit: Optional[int] = None) -> List[dict]:
    """Write a list value to plugin storage and return the stored list."""
    records = trim_records(records, limit)
    plugin.save_data(key, records)
    return records


def read_dict(plugin, key: str, plugin_id: str = "") -> Dict[str, Any]:
    """Read a dict value from plugin storage."""
    if plugin_id:
        try:
            data = plugin.get_data(key, plugin_id=plugin_id) or {}
        except TypeError:
            data = plugin.get_data(key) or {}
    else:
        data = plugin.get_data(key) or {}
    return data if isinstance(data, dict) else {}


def write_dict(plugin, key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Write a dict value to plugin storage and return the stored dict."""
    data = data if isinstance(data, dict) else {}
    plugin.save_data(key, data)
    return data


def read_folio_data(plugin, plugin_id: str = "") -> Dict[str, Any]:
    return read_dict(plugin, FOLIO_DATA_KEY, plugin_id=plugin_id)


def save_folio_data(plugin, data: Dict[str, Any]) -> Dict[str, Any]:
    return write_dict(plugin, FOLIO_DATA_KEY, data)


def read_folio_wait(plugin) -> Dict[str, Any]:
    return read_dict(plugin, FOLIO_WAIT_KEY)


def save_folio_wait(plugin, data: Dict[str, Any]) -> Dict[str, Any]:
    return write_dict(plugin, FOLIO_WAIT_KEY, data)


def read_subscribe_records(plugin) -> List[dict]:
    return read_list(plugin, SUBSCRIBE_RECORDS_KEY)


def save_subscribe_records(plugin, records: List[dict]) -> List[dict]:
    return write_list(plugin, SUBSCRIBE_RECORDS_KEY, records, DETAIL_RECORD_LIMIT)


def read_anti_cheat_logs(plugin) -> List[dict]:
    return read_list(plugin, ANTI_CHEAT_LOGS_KEY)


def save_anti_cheat_logs(plugin, records: List[dict]) -> List[dict]:
    return write_list(plugin, ANTI_CHEAT_LOGS_KEY, records, ANTI_CHEAT_LOG_LIMIT)


def read_archive_records(plugin) -> List[dict]:
    return read_list(plugin, ARCHIVE_RECORDS_KEY)


def save_archive_records(plugin, records: List[dict]) -> List[dict]:
    return write_list(plugin, ARCHIVE_RECORDS_KEY, records, DETAIL_RECORD_LIMIT)


def rank_history_key(rank_key: str) -> str:
    """Return the stable storage key for a built-in rank history."""
    return "coming_history" if rank_key == "coming" else f"rank_history_{rank_key}"


def custom_rank_history_key(source: str) -> str:
    """Return the stable storage key for a custom RSS rank history."""
    digest = hashlib.sha1((source or "").encode("utf-8")).hexdigest()[:16]
    return f"rank_history_custom_{digest}"


def read_rank_history(plugin, rank_key: str) -> List[dict]:
    return read_list(plugin, rank_history_key(rank_key))


def save_rank_history(plugin, rank_key: str, history: List[dict]) -> List[dict]:
    return write_list(plugin, rank_history_key(rank_key), history, RANK_HISTORY_LIMIT)


def read_custom_rank_history(plugin, source: str) -> List[dict]:
    return read_list(plugin, custom_rank_history_key(source))


def save_custom_rank_history(plugin, source: str, history: List[dict]) -> List[dict]:
    return write_list(plugin, custom_rank_history_key(source), history, RANK_HISTORY_LIMIT)
