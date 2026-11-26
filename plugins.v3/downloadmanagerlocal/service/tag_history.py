"""按下载器与种子身份核验转种、辅种历史；读取历史不触发任务。"""

from ..model.state import iyuu_history_key, iyuu_source_key


def completion_data_snapshot(plugin) -> dict:
    """一次读取当前插件数据，扫描期间复用。"""
    get_data = getattr(plugin, "get_data", None)
    data = get_data() if callable(get_data) else None
    if isinstance(data, dict):
        return data
    if isinstance(data, (list, tuple)):
        return {str(row.key): row.value for row in data if getattr(row, "key", None) is not None}
    return {}


def has_transfer_history(downloader_name, torrent_hash, source_service, cache, data_snapshot) -> bool:
    """只接受源、目标和 hash 均匹配的已完成转移记录。"""
    if not source_service or not getattr(source_service, "name", ""):
        return False
    key = (source_service.name, downloader_name, torrent_hash.casefold())
    if key not in cache:
        record = data_snapshot.get(f"{source_service.name}-{torrent_hash}")
        cache[key] = bool(isinstance(record, dict) and record.get("transfer_state") == "completed"
                          and str(record.get("to_download") or "") == downloader_name
                          and str(record.get("to_download_id") or "").casefold() == torrent_hash.casefold())
    return cache[key]


def has_iyuu_history(downloader_name, torrent_hash, cache, data_snapshot) -> bool:
    """母种索引和已完成记录必须指向当前下载器上的同一颗种子。"""
    key = (downloader_name, torrent_hash.casefold())
    if key not in cache:
        source_hash = data_snapshot.get(iyuu_source_key(torrent_hash))
        history = data_snapshot.get(iyuu_history_key(str(source_hash))) if source_hash else None
        cache[key] = any(isinstance(item, dict) and str(item.get("downloader") or "") == downloader_name
                         and torrent_hash.casefold() in {str(value or "").casefold() for value in item.get("torrents") or []}
                         for item in history or [])
    return cache[key]
