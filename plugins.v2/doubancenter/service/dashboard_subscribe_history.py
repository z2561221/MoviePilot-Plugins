"""豆瓣中心仪表盘订阅历史数据服务。"""

from typing import Any, Callable, Optional

from . import archive as archive_service
from ..storage import records as storage

DETAIL_SECTION_LIMIT = 5


def same_record(item: dict, unique: str = "", time: str = "", title: str = "", tmdbid: Any = None) -> bool:
    """按稳定字段判断是否为同一条详情页记录。"""
    if not isinstance(item, dict):
        return False
    if unique and item.get("unique") == unique:
        return True
    if tmdbid not in (None, "") and str(item.get("tmdbid") or "") == str(tmdbid):
        if not title or item.get("title") == title:
            return True
    if time and item.get("time") == time:
        if not title or item.get("title") == title:
            return True
    return False


def delete_subscribe_history(
    plugin,
    *,
    time: str = "",
    title: str = "",
    tmdbid: Any = None,
    archive_record_callback: Callable[..., Optional[dict]],
) -> dict:
    """删除一条豆瓣中心订阅历史记录并写入归档。"""
    records = storage.read_subscribe_records(plugin)
    removed = [item for item in records if same_record(item, time=time, title=title, tmdbid=tmdbid)]
    kept = [item for item in records if item not in removed]
    if len(kept) == len(records):
        return {"success": False, "message": "未找到订阅历史记录"}
    archive = None
    for item in removed:
        archive = archive_record_callback(plugin, "subscribe_history", item, "订阅历史") or archive
    storage.save_subscribe_records(plugin, kept)
    return {"success": True, "message": "已归档订阅历史记录", "archive_id": archive.get("id") if archive else ""}


def paginate_subscribe_history(
    plugin,
    page: int = 1,
    page_size: int = 20,
    limit: int = DETAIL_SECTION_LIMIT,
) -> dict:
    """返回已去重、倒序并治理溢出的订阅历史分页。"""
    records = storage.read_subscribe_records(plugin)
    records, changed = dedupe_records(records)
    records.sort(key=lambda item: item.get("time", ""), reverse=True)
    records, overflow_changed = archive_service.archive_detail_overflow(
        plugin,
        records,
        "subscribe_history",
        "订阅历史",
        limit,
    )
    if changed or overflow_changed:
        storage.save_subscribe_records(plugin, records)
    safe_page = max(int(page), 1)
    safe_page_size = max(int(page_size), 1)
    total = len(records)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return {
        "items": records[start:end],
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "total_pages": (total + safe_page_size - 1) // safe_page_size,
    }


def dedupe_records(records: list) -> tuple:
    """按状态、TMDB、标题、年份和榜单合并订阅历史。"""
    if not isinstance(records, list):
        return [], False
    merged = []
    index = {}
    changed = False
    for record in records:
        if not isinstance(record, dict):
            continue
        key = (
            str(record.get("status") or "success"),
            str(record.get("tmdbid") or ""),
            str(record.get("title") or ""),
            str(record.get("year") or ""),
            str(record.get("rank_key") or ""),
        )
        if key in index:
            target = merged[index[key]]
            if (record.get("time") or "") >= (target.get("time") or ""):
                target.update(record)
            changed = True
            continue
        index[key] = len(merged)
        merged.append(dict(record))
    if len(merged) != len(records):
        changed = True
    return merged[-500:], changed
