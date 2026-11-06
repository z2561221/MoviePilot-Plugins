"""旧删除入口的兼容转发；只有精确媒体范围可以进入同步删除队列。"""

from types import SimpleNamespace

from ..adapter.sync_delete import SyncDeleteAdapter
from ..model.sync_delete import config_for, mappings, text, within
from .sync_delete import receive_webhook


def handle_webhook_message_event(plugin, event):
    """Emby 删除统一交给带配置门禁、文件范围与持久队列的执行器。"""
    return receive_webhook(plugin, event)


def _empty_result(trigger=""):
    """返回无精确媒体范围时的保留回执，不执行 hash 级删除。"""
    return {"trigger": trigger, "source_hash": "", "transfer_deleted": 0,
            "iyuu_deleted": 0, "skipped": True}


def cleanup_by_hash(plugin, source_hash, downloader="", trigger=""):
    """旧 hash 调用不具备文件范围，不再执行整包删除。"""
    return dict(_empty_result(trigger), source_hash=text(source_hash), reason="需要具体媒体路径")


def cleanup_by_path(plugin, item_path, trigger=""):
    """媒体路径仍须通过映射和媒体库文件消失核验。"""
    return receive_webhook(plugin, SimpleNamespace(event_data={
        "event": "deep.delete", "channel": "emby", "item_path": item_path,
    }))


def handle_sync_delete_by_hash_event(plugin, event, trigger=""):
    """源文件事件只反查精确整理目标，不把移除种子扩大成整包删除。"""
    if not getattr(plugin, "_sync_delete_enabled", False) or not getattr(plugin, "_enabled", False):
        return _empty_result(trigger)
    data = getattr(event, "event_data", None) or {}
    src = data.get("src") if isinstance(data, dict) else getattr(data, "src", "")
    if not src:
        return _empty_result(trigger)
    config = config_for(plugin)
    adapter = SyncDeleteAdapter(plugin, config)
    results = []
    for record in adapter.histories(source=src):
        dest = text(record.get("dest"))
        for mapping in mappings(config):
            if text(record.get("dest_storage") or "local") == mapping["storage"] and within(dest, mapping["target"], strict=True):
                suffix = dest[len(mapping["target"]):]
                emby_path = mapping["emby"] + suffix
                if mapping["cloud"]:
                    emby_path = emby_path.rsplit(".", 1)[0] + ".strm"
                results.append(cleanup_by_path(plugin, emby_path, trigger))
                break
    return {"items": results}


def handle_plugin_action_event(plugin, event):
    """网盘动作具有明确媒体路径时才进入统一执行器。"""
    data = getattr(event, "event_data", None) or {}
    if not isinstance(data, dict) or data.get("action") != "networkdisk_del":
        return _empty_result("PluginAction")
    path = data.get("item_path") or data.get("path")
    return cleanup_by_path(plugin, path) if path else _empty_result("PluginAction")
