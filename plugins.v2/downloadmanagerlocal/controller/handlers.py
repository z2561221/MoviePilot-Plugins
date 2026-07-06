"""下载管理插件 - API 路由实现"""

from datetime import datetime

from app.log import logger

from ..adapter.moviepilot import get_downloader_config, list_builtin_sites
from ..model.state import RENAME_RECORDS_KEY, RENAME_RETRY_STATE_KEY


def api_retry_renames(plugin):
    """手动触发失败历史和脏名称种子的批量补刮。"""
    try:
        return plugin._retry_pending_renames()
    except Exception as e:
        logger.error(f"一键补刀失败: {e}")
        return {"code": 1, "msg": f"补刀失败: {e}", "history": 0, "dirty": 0, "total": 0}


def api_retry_rename(plugin, hash: str = ""):
    """对指定种子 hash 手动重试重命名和站点标签。"""
    try:
        return plugin._retry_rename(hash)
    except Exception as e:
        logger.error(f"单条补刀失败: {e}")
        return {"code": 1, "msg": f"补刀失败: {e}", "hash": hash or ""}


def api_diagnostics(plugin):
    """返回详情页使用的只读诊断摘要。"""
    try:
        return plugin._diagnostics()
    except Exception as e:
        logger.error(f"诊断信息生成失败: {e}")
        return {"code": 1, "msg": f"诊断失败: {e}"}


def api_overview(plugin):
    """返回详情页总览数据。"""
    try:
        diagnostics = plugin._diagnostics()
        archive = plugin.rename_archive_stats()
        rename_history = diagnostics.get("rename_history", {}) if isinstance(diagnostics, dict) else {}
        return {
            "code": 0,
            "plugin": diagnostics.get("plugin", {}) if isinstance(diagnostics, dict) else {},
            "config": diagnostics.get("config", {}) if isinstance(diagnostics, dict) else {},
            "downloaders": diagnostics.get("downloaders", {}) if isinstance(diagnostics, dict) else {},
            "rename_history": rename_history,
            "archive": archive,
            "cards": {
                "transfer": {
                    "enabled": bool(getattr(plugin, "_transfer_enabled", False)),
                    "active": bool(getattr(plugin, "_transfer_active", False)),
                    "fallback_enabled": bool(getattr(plugin, "_transfer_fallback_enabled", False)),
                },
                "iyuu": {
                    "enabled": bool(getattr(plugin, "_iyuu_enabled", False)),
                    "success": int(getattr(plugin, "_iyuu_success", 0) or 0),
                    "fail": int(getattr(plugin, "_iyuu_fail", 0) or 0),
                    "cached": int(getattr(plugin, "_iyuu_cached", 0) or 0),
                },
                "rename": {
                    "enabled": bool(getattr(plugin, "_rename_enabled", False)),
                    "failed": int(rename_history.get("failed", 0) or 0),
                    "dirty": int(rename_history.get("dirty", 0) or 0),
                    "archived": int(archive.get("archived", 0) or 0),
                },
                "seed": {
                    "autostart": bool(getattr(plugin, "_seed_autostart", False)),
                    "skipverify": bool(getattr(plugin, "_seed_skipverify", False)),
                },
            },
        }
    except Exception as e:
        logger.error(f"总览信息生成失败: {e}")
        return {"code": 1, "msg": f"总览失败: {e}"}


def api_downloaders(plugin):
    """返回可用下载器列表"""
    try:
        services = plugin.downloader_helper.get_services()
        result = []
        if services:
            for name, info in services.items():
                result.append({
                    "title": name,
                    "value": name,
                    "type": info.type,
                })
        return {"data": result}
    except Exception as e:
        logger.error(f"获取下载器列表失败: {e}")
        return {"data": []}


def api_sites(plugin):
    """返回可用站点列表（内置站点 + 自定义站点）"""
    try:
        custom_sites = plugin._custom_sites()
        result = [{"title": site.name, "value": site.id}
                  for site in list_builtin_sites()]
        result += [{"title": site.get("name"), "value": site.get("id")}
                   for site in custom_sites]
        return {"data": result}
    except Exception as e:
        logger.error(f"获取站点列表失败: {e}")
        return {"data": []}


def api_rename_history(plugin, page: int = 1, page_size: int = 15):
    """返回重命名历史记录（支持分页）"""
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    retry_state = plugin.get_data(RENAME_RETRY_STATE_KEY) or {}
    archived_hashes = {
        record_hash
        for record_hash, state in retry_state.items()
        if isinstance(state, dict) and state.get("archived")
    } if isinstance(retry_state, dict) else set()
    items = []
    for record_hash, record in records.items():
        if not isinstance(record, dict):
            continue
        if record_hash in archived_hashes:
            continue
        item = dict(record)
        item["hash"] = item.get("hash") or record_hash
        items.append(item)
    all_items = sorted(items, key=lambda x: x.get("time", ""), reverse=True)
    total = len(all_items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "items": all_items[start:end]
    }


def api_delete_rename_history(plugin, hash: str = ""):
    """删除指定 hash 的重命名记录"""
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    if hash in records:
        del records[hash]
        plugin.save_data(RENAME_RECORDS_KEY, records)
        return {"code": 0, "msg": "已删除"}
    return {"code": 1, "msg": "记录不存在"}


def api_rename_archive(plugin, page: int = 1, page_size: int = 15):
    """返回补刀归档记录（支持分页）。"""
    return plugin.list_rename_archive(page, page_size)


def api_restore_rename_archive(plugin, hash: str = ""):
    """恢复归档记录，使其继续参与补刀。"""
    return plugin.restore_rename_archive(hash)


def api_delete_rename_archive(plugin, hash: str = ""):
    """删除归档状态记录。"""
    return plugin.delete_rename_archive(hash)


def api_recovery_torrent(plugin, hash: str = ""):
    """恢复种子原始名称"""
    if not hash:
        return {"code": 1, "msg": "缺少 hash 参数"}
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    record = records.get(hash)
    if not record or not record.get("success"):
        return {"code": 1, "msg": "未找到成功的重命名记录"}
    original_name = record.get("original_name")
    if not original_name:
        return {"code": 1, "msg": "原始名称为空"}

    # 在目标下载器中查找并恢复
    try:
        to_config = get_downloader_config(plugin._todownloader)
        if not to_config:
            return {"code": 1, "msg": f"下载器 {plugin._todownloader} 不存在"}
        dl = to_config.instance
        dl_type = to_config.type

        if dl_type == "qbittorrent":
            dl.qbc.torrents_rename(torrent_hash=hash, new_torrent_name=original_name)
        else:
            dl.rename_torrent(hash, original_name)

        # 更新记录
        record["after_name"] = original_name
        record["success"] = True
        record["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        records[hash] = record
        plugin.save_data(RENAME_RECORDS_KEY, records)
        logger.info(f"种子恢复成功: {hash} → {original_name}")
        return {"code": 0, "msg": f"已恢复为: {original_name}"}
    except Exception as e:
        logger.error(f"种子恢复失败: {e}")
        return {"code": 1, "msg": str(e)}
