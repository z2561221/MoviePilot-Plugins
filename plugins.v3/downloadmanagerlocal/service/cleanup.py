"""下载中心同步删除服务。"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

from app.log import logger

from ..adapter.moviepilot import get_download_hash_by_fullpath
from ..model.state import iyuu_history_key


RECENT_CLEANUP_WINDOW_SECONDS = 30


def handle_sync_delete_by_hash_event(plugin, event, trigger: str = "") -> Dict[str, Any]:
    """处理携带下载 hash 的同步删除事件。"""
    event_data = _event_data(event)
    source_hash = _clean_text(_data_get(event_data, "hash") or _data_get(event_data, "download_hash"))
    downloader = _clean_text(_data_get(event_data, "downloader") or _data_get(event_data, "downloader_name"))
    return cleanup_by_hash(plugin, source_hash, downloader=downloader, trigger=trigger)


def handle_webhook_message_event(plugin, event) -> Dict[str, Any]:
    """处理媒体服务器 Webhook 删除事件。"""
    event_data = _event_data(event)
    webhook_event = _clean_text(_data_get(event_data, "event")).lower()
    channel = _clean_text(_data_get(event_data, "channel")).lower()
    if webhook_event != "library.deleted" or (channel and channel != "emby"):
        return _empty_result(trigger="WebhookMessage")
    item_path = _clean_text(_data_get(event_data, "item_path") or _data_get(event_data, "path"))
    return cleanup_by_path(plugin, item_path, trigger="WebhookMessage")


def handle_plugin_action_event(plugin, event) -> Dict[str, Any]:
    """处理网盘同步删除插件动作。"""
    event_data = _event_data(event)
    action = _clean_text(_data_get(event_data, "action"))
    if action != "networkdisk_del":
        return _empty_result(trigger="PluginAction")
    source_hash = _clean_text(_data_get(event_data, "hash") or _data_get(event_data, "download_hash"))
    downloader = _clean_text(_data_get(event_data, "downloader") or _data_get(event_data, "downloader_name"))
    if source_hash:
        return cleanup_by_hash(plugin, source_hash, downloader=downloader, trigger="PluginAction")
    item_path = _clean_text(_data_get(event_data, "item_path") or _data_get(event_data, "path"))
    return cleanup_by_path(plugin, item_path, trigger="PluginAction")


def cleanup_by_path(plugin, item_path: str, trigger: str = "") -> Dict[str, Any]:
    """按媒体文件路径反查源 hash 后执行同步删除。"""
    path_text = _clean_text(item_path)
    if not path_text:
        return _empty_result(trigger=trigger)
    try:
        source_hash = _clean_text(get_download_hash_by_fullpath(path_text))
    except Exception as err:
        logger.error(f"同步删除：按路径反查下载 hash 失败 path={path_text}: {err}")
        return _empty_result(trigger=trigger)
    return cleanup_by_hash(plugin, source_hash, trigger=trigger)


def cleanup_by_hash(plugin, source_hash: str, downloader: str = "", trigger: str = "") -> Dict[str, Any]:
    """按源下载 hash 清理转种任务和 IYUU 辅种任务。"""
    source_hash = _clean_text(source_hash)
    result = _empty_result(trigger=trigger)
    result["source_hash"] = source_hash
    if not source_hash:
        return result
    if _skip_recent_duplicate(plugin, source_hash):
        result["skipped"] = True
        return result

    source_downloader = _clean_text(downloader or getattr(plugin, "_fromdownloader", ""))
    transfer_deleted = _cleanup_transfer_target(plugin, source_hash, source_downloader)
    iyuu_deleted = _cleanup_iyuu_targets(plugin, source_hash)
    result["transfer_deleted"] = transfer_deleted
    result["iyuu_deleted"] = iyuu_deleted
    if transfer_deleted or iyuu_deleted:
        logger.info(
            f"同步删除：{trigger or '事件'} 已按源 hash={source_hash} 删除转种 {transfer_deleted} 个、辅种 {iyuu_deleted} 个（含文件）"
        )
    return result


def _cleanup_transfer_target(plugin, source_hash: str, source_downloader: str) -> int:
    """删除源 hash 对应的转种目标任务。"""
    if not source_downloader:
        return 0
    record = plugin.get_data(f"{source_downloader}-{source_hash}") or {}
    if not isinstance(record, dict):
        return 0
    target_downloader = _clean_text(record.get("to_download"))
    target_hash = _clean_text(record.get("to_download_id"))
    return _delete_downloader_hashes(plugin, target_downloader, [target_hash])


def _cleanup_iyuu_targets(plugin, source_hash: str) -> int:
    """删除源 hash 对应的 IYUU 辅种任务。"""
    history = plugin.get_data(iyuu_history_key(source_hash)) or []
    if not isinstance(history, list):
        return 0
    deleted = 0
    for item in history:
        if not isinstance(item, dict):
            continue
        downloader = _clean_text(item.get("downloader"))
        deleted += _delete_downloader_hashes(plugin, downloader, item.get("torrents") or [])
    return deleted


def _delete_downloader_hashes(plugin, downloader: str, hashes: Iterable[str]) -> int:
    """调用下载器删除任务和文件，并返回请求删除的 hash 数量。"""
    downloader = _clean_text(downloader)
    hash_list = _unique_hashes(hashes)
    if not downloader or not hash_list:
        return 0
    try:
        service = plugin.service_info(downloader)
        instance = getattr(service, "instance", None) if service else None
        if not instance:
            logger.warning(f"同步删除：下载器不可用，跳过 {downloader} / {hash_list}")
            return 0
        state = instance.delete_torrents(delete_file=True, ids=hash_list)
        if state is False:
            logger.warning(f"同步删除：下载器删除返回失败 {downloader} / {hash_list}")
            return 0
        return len(hash_list)
    except Exception as err:
        logger.error(f"同步删除：删除下载器任务失败 {downloader} / {hash_list}: {err}")
        return 0


def _skip_recent_duplicate(plugin, source_hash: str) -> bool:
    """短时间内跳过同一源 hash 的重复广播。"""
    now = time.time()
    recent = getattr(plugin, "_sync_delete_recent", None)
    if not isinstance(recent, dict):
        recent = {}
        setattr(plugin, "_sync_delete_recent", recent)
    last = float(recent.get(source_hash) or 0)
    recent[source_hash] = now
    for key, value in list(recent.items()):
        if now - float(value or 0) > RECENT_CLEANUP_WINDOW_SECONDS:
            recent.pop(key, None)
    return bool(last and now - last <= RECENT_CLEANUP_WINDOW_SECONDS)


def _event_data(event) -> Any:
    """从 Event 或测试替身中读取事件数据。"""
    return getattr(event, "event_data", None) or {}


def _data_get(data, key: str) -> Any:
    """兼容 dict、Pydantic 模型和普通对象的字段读取。"""
    if isinstance(data, dict):
        return data.get(key)
    return getattr(data, key, None)


def _clean_text(value) -> str:
    """把可选值收敛为去空白字符串。"""
    return str(value or "").strip()


def _unique_hashes(values: Iterable[str]) -> List[str]:
    """保序去重并过滤空 hash。"""
    result = []
    for value in values or []:
        text = _clean_text(value)
        if text and text not in result:
            result.append(text)
    return result


def _empty_result(trigger: str = "") -> Dict[str, Any]:
    """返回同步删除空结果。"""
    return {
        "trigger": trigger,
        "source_hash": "",
        "transfer_deleted": 0,
        "iyuu_deleted": 0,
        "skipped": False,
    }


__all__ = (
    "cleanup_by_hash",
    "cleanup_by_path",
    "handle_plugin_action_event",
    "handle_sync_delete_by_hash_event",
    "handle_webhook_message_event",
)
