"""下载管理插件诊断模块"""

from datetime import datetime
from pathlib import Path

from app.log import logger

from ..utils.name_cleaner import is_dirty_renamed_torrent_name


def _bool_text(value) -> str:
    return "已开启" if bool(value) else "未开启"


def _service_status(plugin, name: str) -> dict:
    result = {
        "name": name or "",
        "configured": bool(name),
        "available": False,
        "type": "",
        "message": "未配置",
    }
    if not name:
        return result
    try:
        service = plugin.service_info(name)
        if not service or not service.instance:
            result["message"] = "不可用"
            return result
        result.update({
            "available": True,
            "type": service.type or "",
            "message": "连接正常",
        })
        return result
    except Exception as e:
        logger.warning(f"诊断：检查下载器 {name} 失败: {e}")
        result["message"] = str(e)
        return result


def _rename_history_stats(plugin) -> dict:
    records = plugin.get_data("rename_records") or {}
    items = list(records.values())
    success_count = sum(1 for item in items if item.get("success"))
    failed_items = [item for item in items if not item.get("success")]
    dirty_count = sum(
        1
        for item in items
        if is_dirty_renamed_torrent_name(item.get("original_name"))
        or is_dirty_renamed_torrent_name(item.get("after_name"))
    )
    recent_failures = sorted(
        failed_items,
        key=lambda item: item.get("time", ""),
        reverse=True,
    )[:5]
    return {
        "total": len(items),
        "success": success_count,
        "failed": len(failed_items),
        "dirty": dirty_count,
        "recent_failures": [
            {
                "time": item.get("time", ""),
                "hash": item.get("hash", ""),
                "reason": item.get("reason", "") or "未知原因",
                "name": item.get("original_name", "") or item.get("after_name", ""),
            }
            for item in recent_failures
        ],
    }


def _path_exists(path_text: str) -> bool:
    if not path_text:
        return False
    try:
        return Path(path_text).exists()
    except Exception:
        return False


def _check(label: str, status: str, detail: str) -> dict:
    return {"label": label, "status": status, "detail": detail}


def build_diagnostics(plugin):
    """构建只读诊断摘要，供详情页展示。"""
    from_service = _service_status(plugin, plugin._fromdownloader)
    to_service = _service_status(plugin, plugin._todownloader)
    source_path_exists = _path_exists(plugin._fromtorrentpath)
    transfer_ready = bool(
        plugin._transfer_active and from_service["available"] and to_service["available"]
    )
    rename_history = _rename_history_stats(plugin)

    checks = [
        _check(
            "源下载器",
            "ok" if from_service["available"] else "warn",
            from_service["message"],
        ),
        _check(
            "目标下载器",
            "ok" if to_service["available"] else "warn",
            to_service["message"],
        ),
        _check(
            "种子文件目录",
            "ok" if source_path_exists else "warn",
            "路径可访问" if source_path_exists else "未配置或路径不可访问",
        ),
        _check(
            "转移做种",
            "ok" if transfer_ready else ("off" if not plugin._transfer_enabled else "warn"),
            "配置完整" if transfer_ready else "未启用或配置不完整",
        ),
        _check("重命名", "ok" if plugin._rename_enabled else "off", _bool_text(plugin._rename_enabled)),
        _check("站点标签", "ok" if plugin._tag_enabled else "off", _bool_text(plugin._tag_enabled)),
        _check("IYUU辅种", "ok" if plugin._iyuu_enabled else "off", _bool_text(plugin._iyuu_enabled)),
    ]

    return {
        "code": 0,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "plugin": {
            "name": plugin.plugin_name,
            "version": plugin.plugin_version,
            "state": bool(plugin.get_state()),
        },
        "downloaders": {
            "from": from_service,
            "to": to_service,
        },
        "config": {
            "enabled": bool(plugin._enabled),
            "transfer_enabled": bool(plugin._transfer_enabled),
            "transfer_active": bool(plugin._transfer_active),
            "transfer_fallback_enabled": bool(plugin._transfer_fallback_enabled),
            "rename_enabled": bool(plugin._rename_enabled),
            "tag_enabled": bool(plugin._tag_enabled),
            "iyuu_enabled": bool(plugin._iyuu_enabled),
            "seed_autostart": bool(plugin._seed_autostart),
            "seed_skipverify": bool(plugin._seed_skipverify),
        },
        "paths": {
            "frompath": plugin._frompath or "",
            "topath": plugin._topath or "",
            "fromtorrentpath": plugin._fromtorrentpath or "",
            "fromtorrentpath_exists": source_path_exists,
        },
        "rename_history": rename_history,
        "checks": checks,
    }
