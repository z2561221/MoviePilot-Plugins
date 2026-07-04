"""重命名补刀失败归档服务实现。"""

from __future__ import annotations

from datetime import datetime

from app.log import logger

from ..model.state import RENAME_RETRY_STATE_KEY

RETRY_STATE_KEY = RENAME_RETRY_STATE_KEY
DEFAULT_ARCHIVE_THRESHOLD = 3

FAILURE_CATEGORY_LABELS = {
    "NO_TRUSTED_SOURCE": "原始发布名无可信候选",
    "LOW_CONFIDENCE_SOURCE": "原始名候选置信度过低",
    "META_PARSE_FAILED": "元数据解析失败",
    "MEDIA_RECOGNIZE_FAILED": "媒体识别失败",
    "FORMAT_EMPTY": "命名模板结果为空",
    "DOWNLOADER_UNAVAILABLE": "目标下载器不可用",
    "TASK_NOT_FOUND": "下载器任务不存在",
    "HASH_MISSING": "种子 hash 缺失",
    "RENAME_API_FAILED": "下载器重命名失败",
    "TAG_FAILED": "站点标签处理失败",
    "EXCLUDED_BY_RULE": "命中排除规则",
    "UNKNOWN_ERROR": "未归类异常",
}


def now_text() -> str:
    """返回统一的状态时间字符串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_rename_failure_state(item: dict, reason_text: str) -> None:
    """输出补刀失败分类日志，测试隔离执行时自动跳过。"""
    log = globals().get("logger")
    if not log:
        return
    log.warning(
        "补刀失败归类：hash=%s category=%s label=%s count=%s archived=%s reason=%s",
        item.get("hash", ""),
        item.get("category", ""),
        item.get("category_label", ""),
        item.get("fail_count", 0),
        bool(item.get("archived")),
        reason_text,
    )


def classify_rename_failure(reason: str = "") -> str:
    """根据失败原因文本归类补刀失败。"""
    text = str(reason or "")
    if "原始发布名污染" in text or "无法可靠补刀" in text or "无可信候选" in text:
        return "NO_TRUSTED_SOURCE"
    if "置信度" in text:
        return "LOW_CONFIDENCE_SOURCE"
    if "元数据" in text:
        return "META_PARSE_FAILED"
    if "媒体识别" in text:
        return "MEDIA_RECOGNIZE_FAILED"
    if "格式化" in text or "为空" in text:
        return "FORMAT_EMPTY"
    if "下载器不可用" in text:
        return "DOWNLOADER_UNAVAILABLE"
    if "未在目标下载器找到" in text or "任务不存在" in text:
        return "TASK_NOT_FOUND"
    if "无 hash" in text or "hash 缺失" in text:
        return "HASH_MISSING"
    if "站点标签" in text:
        return "TAG_FAILED"
    if "排除" in text:
        return "EXCLUDED_BY_RULE"
    if "重命名" in text or "API" in text:
        return "RENAME_API_FAILED"
    return "UNKNOWN_ERROR"


def get_rename_retry_state(plugin) -> dict:
    """读取补刀失败状态。"""
    state = plugin.get_data(RETRY_STATE_KEY) or {}
    return state if isinstance(state, dict) else {}


def save_rename_retry_state(plugin, state: dict) -> None:
    """保存补刀失败状态。"""
    plugin.save_data(RETRY_STATE_KEY, state or {})


def is_rename_archived(plugin, torrent_hash: str) -> bool:
    """判断种子是否已归档，不再参与自动补刀。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return False
    item = get_rename_retry_state(plugin).get(hash_text) or {}
    return bool(item.get("archived"))


def clear_rename_retry_state(plugin, torrent_hash: str) -> None:
    """清理指定种子的补刀失败状态。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return
    state = get_rename_retry_state(plugin)
    if hash_text in state:
        del state[hash_text]
        save_rename_retry_state(plugin, state)


def record_rename_failure(
    plugin,
    torrent_hash: str,
    torrent_name: str,
    category: str = "",
    reason: str = "",
    threshold: int = DEFAULT_ARCHIVE_THRESHOLD,
) -> dict:
    """记录一次补刀失败，达到阈值后自动归档。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return {}
    reason_text = str(reason or "未知原因")
    category_text = str(category or "").strip() or classify_rename_failure(reason_text)
    threshold = max(1, int(threshold or DEFAULT_ARCHIVE_THRESHOLD))
    state = get_rename_retry_state(plugin)
    item = dict(state.get(hash_text) or {})
    fail_count = int(item.get("fail_count") or 0) + 1
    archived = bool(item.get("archived")) or fail_count >= threshold
    item.update({
        "hash": hash_text,
        "name": str(torrent_name or item.get("name") or ""),
        "category": category_text,
        "category_label": FAILURE_CATEGORY_LABELS.get(category_text, "未归类异常"),
        "reason": reason_text,
        "fail_count": fail_count,
        "last_failed_at": now_text(),
        "archived": archived,
    })
    if archived:
        item["archived_at"] = item.get("archived_at") or now_text()
        item["archive_reason"] = f"连续补刀失败 {fail_count} 次：{reason_text}"
    state[hash_text] = item
    save_rename_retry_state(plugin, state)
    log_rename_failure_state(item, reason_text)
    return item


def restore_rename_archive(plugin, torrent_hash: str) -> dict:
    """从归档中恢复指定种子，使其重新参与补刀。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return {"code": 1, "msg": "缺少 hash 参数", "hash": ""}
    state = get_rename_retry_state(plugin)
    item = dict(state.get(hash_text) or {})
    if not item:
        return {"code": 1, "msg": "归档记录不存在", "hash": hash_text}
    item.update({
        "archived": False,
        "fail_count": 0,
        "restored_at": now_text(),
    })
    item.pop("archived_at", None)
    state[hash_text] = item
    save_rename_retry_state(plugin, state)
    return {"code": 0, "msg": "已恢复，后续将重新参与补刀", "hash": hash_text}


def delete_rename_archive(plugin, torrent_hash: str) -> dict:
    """删除指定归档状态记录。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return {"code": 1, "msg": "缺少 hash 参数", "hash": ""}
    state = get_rename_retry_state(plugin)
    if hash_text not in state:
        return {"code": 1, "msg": "归档记录不存在", "hash": hash_text}
    del state[hash_text]
    save_rename_retry_state(plugin, state)
    return {"code": 0, "msg": "已删除归档记录", "hash": hash_text}


def list_rename_archive(plugin, page: int = 1, page_size: int = 15) -> dict:
    """返回补刀归档记录分页。"""
    state = get_rename_retry_state(plugin)
    archived_items = [
        dict(item, hash=hash_text)
        for hash_text, item in state.items()
        if isinstance(item, dict) and item.get("archived")
    ]
    all_items = sorted(
        archived_items,
        key=lambda item: item.get("archived_at") or item.get("last_failed_at") or "",
        reverse=True,
    )
    page = max(1, int(page or 1))
    page_size = max(1, int(page_size or 15))
    total = len(all_items)
    start = (page - 1) * page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "items": all_items[start:start + page_size],
    }


def rename_archive_stats(plugin) -> dict:
    """统计补刀失败状态，用于总览和诊断。"""
    state = get_rename_retry_state(plugin)
    items = [item for item in state.values() if isinstance(item, dict)]
    archived = [item for item in items if item.get("archived")]
    active_failed = [item for item in items if not item.get("archived") and int(item.get("fail_count") or 0) > 0]
    category_counts = {}
    for item in archived:
        category = item.get("category") or "UNKNOWN_ERROR"
        category_counts[category] = category_counts.get(category, 0) + 1
    return {
        "total": len(items),
        "archived": len(archived),
        "active_failed": len(active_failed),
        "near_archive": sum(1 for item in active_failed if int(item.get("fail_count") or 0) >= DEFAULT_ARCHIVE_THRESHOLD - 1),
        "threshold": DEFAULT_ARCHIVE_THRESHOLD,
        "category_counts": category_counts,
        "recent_archived": sorted(
            archived,
            key=lambda item: item.get("archived_at") or item.get("last_failed_at") or "",
            reverse=True,
        )[:5],
    }


__all__ = (
    "clear_rename_retry_state",
    "delete_rename_archive",
    "is_rename_archived",
    "list_rename_archive",
    "record_rename_failure",
    "rename_archive_stats",
    "restore_rename_archive",
)
