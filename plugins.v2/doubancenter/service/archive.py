"""豆瓣中心归档服务。"""

import datetime
from typing import Any, Callable, Optional

from ..storage import records as storage

DETAIL_SECTION_LIMIT = 5
DETAIL_OVERFLOW_REASON = "超过详情页显示上限归档"
BLACKLIST_REASON = "黑名单关键词"
BLACKLIST_SOURCE_NAME = "黑名拦截"
OBSERVATION_SOURCE_NAME = "观察日志"
OBSERVATION_COMPLETED_SOURCE = "observation_completed"
OBSERVATION_COMPLETED_REASON = "观察期完成"


def archive_record_key(source: str, record: dict) -> tuple:
    """生成归档记录去重键。"""
    if not isinstance(record, dict):
        return (source, "")
    return (
        source,
        str(record.get("unique") or ""),
        str(record.get("tmdbid") or record.get("tmdb_id") or ""),
        str(record.get("title") or ""),
        str(record.get("reason") or ""),
        str(record.get("detail") or ""),
        str(record.get("time") or ""),
        str(record.get("link") or ""),
    )


def archive_record_score(record: dict) -> int:
    """计算归档原始记录的信息完整度。"""
    if not isinstance(record, dict):
        return 0
    score = sum(1 for value in record.values() if value not in (None, "", [], {}))
    for field in ("unique", "poster", "tmdbid", "rank_key", "rank_name", "first_seen", "subscribed_at"):
        if record.get(field):
            score += 5
    return score


def same_archive_record(source: str, left: dict, right: dict) -> bool:
    """按来源判断两条归档原始记录是否重复。"""
    if archive_record_key(source, left) == archive_record_key(source, right):
        return True
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    if str(left.get("title") or "") != str(right.get("title") or ""):
        return False
    if not str(left.get("title") or ""):
        return False
    for field in ("unique", "tmdbid", "tmdb_id", "reason", "detail", "link"):
        left_value = str(left.get(field) or "")
        right_value = str(right.get(field) or "")
        if left_value and right_value and left_value != right_value:
            return False
    return True


def update_archive_item_from_record(archive: dict, source: str, record: dict, source_name: str = "") -> dict:
    """用更完整的原始记录刷新归档展示字段。"""
    copied = dict(record)
    archive.update({
        "source": source,
        "source_name": source_name or archive.get("source_name") or source,
        "title": copied.get("title") or archive.get("title") or "",
        "time": copied.get("time") or copied.get("first_seen") or archive.get("time") or "",
        "rank_key": copied.get("rank_key") or archive.get("rank_key") or "",
        "rank_name": copied.get("rank_name") or archive.get("rank_name") or "",
        "reason": copied.get("reason") or archive.get("reason") or "",
        "record": copied,
    })
    return archive


def dedupe_archive_records(archives: list) -> tuple:
    """压缩重复归档记录，保留信息更完整的一条。"""
    if not isinstance(archives, list):
        return [], False
    merged = []
    changed = False
    for archive in archives:
        if not isinstance(archive, dict):
            changed = True
            continue
        source = str(archive.get("source") or "")
        record = archive.get("record") or {}
        duplicate_index = None
        for index, existing in enumerate(merged):
            if str(existing.get("source") or "") != source:
                continue
            if same_archive_record(source, existing.get("record") or {}, record):
                duplicate_index = index
                break
        if duplicate_index is None:
            merged.append(archive)
            continue
        changed = True
        existing = merged[duplicate_index]
        if archive_record_score(record) > archive_record_score(existing.get("record") or {}):
            merged[duplicate_index] = archive
    return merged[-500:], changed or len(merged) != len(archives)


def archive_record(plugin, source: str, record: dict, source_name: str = "", dedupe: bool = False) -> Optional[dict]:
    """将详情页删除的记录写入归档。"""
    if not isinstance(record, dict):
        return None
    archives = storage.read_archive_records(plugin)
    if dedupe:
        for index, archive in enumerate(archives):
            if not isinstance(archive, dict) or archive.get("source") != source:
                continue
            if same_archive_record(source, archive.get("record") or {}, record):
                if archive_record_score(record) > archive_record_score(archive.get("record") or {}):
                    archives[index] = update_archive_item_from_record(archive, source, record, source_name)
                    storage.save_archive_records(plugin, archives)
                    return archives[index]
                return archive
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    archive_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
    copied = dict(record)
    item = {
        "id": archive_id,
        "source": source,
        "source_name": source_name or source,
        "title": copied.get("title") or "",
        "time": copied.get("time") or copied.get("first_seen") or "",
        "rank_key": copied.get("rank_key") or "",
        "rank_name": copied.get("rank_name") or "",
        "reason": copied.get("reason") or "",
        "archived_at": now,
        "record": copied,
    }
    archives.append(item)
    storage.save_archive_records(plugin, archives)
    return item


def remove_archive(plugin, archive_id: str) -> Optional[dict]:
    """从归档列表取出并删除一条归档记录。"""
    archives = storage.read_archive_records(plugin)
    if not isinstance(archives, list):
        return None
    removed = None
    kept = []
    for item in archives:
        if isinstance(item, dict) and item.get("id") == archive_id and removed is None:
            removed = item
            continue
        kept.append(item)
    if removed:
        storage.save_archive_records(plugin, kept)
    return removed


def detail_record_time(record: dict) -> str:
    """返回详情页记录用于新旧排序的时间字段。"""
    if not isinstance(record, dict):
        return ""
    return str(record.get("time") or record.get("first_seen") or record.get("archived_at") or "")


def latest_detail_indexes(records: list, limit: int = DETAIL_SECTION_LIMIT) -> set:
    """按时间选出详情页应保留的最新记录下标。"""
    indexed = [(index, record) for index, record in enumerate(records) if isinstance(record, dict)]
    ordered = sorted(indexed, key=lambda pair: (detail_record_time(pair[1]), pair[0]), reverse=True)
    return {index for index, _ in ordered[:limit]}


def archive_detail_overflow(
    plugin,
    records: list,
    source: str,
    source_name: str,
    limit: int = DETAIL_SECTION_LIMIT,
) -> tuple:
    """保留最新详情记录，并将超出上限的条目写入归档。"""
    if not isinstance(records, list):
        return [], False
    if len(records) <= limit:
        return records, False
    keep_indexes = latest_detail_indexes(records, limit)
    kept = []
    changed = False
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            changed = True
            continue
        if index in keep_indexes:
            kept.append(record)
            continue
        archived_record = dict(record)
        archived_record.setdefault("reason", record.get("reason") or DETAIL_OVERFLOW_REASON)
        archive_record(plugin, source, archived_record, source_name, dedupe=True)
        changed = True
    return kept, changed


def archive_anti_cheat_overflow(plugin, logs: list, limit: int = DETAIL_SECTION_LIMIT) -> tuple:
    """分别限制黑名拦截与观察日志的详情页展示数量。"""
    if not isinstance(logs, list):
        return [], False
    blacklist_indexes = []
    observe_indexes = []
    for index, log in enumerate(logs):
        if not isinstance(log, dict):
            continue
        if str(log.get("reason") or "") == BLACKLIST_REASON:
            blacklist_indexes.append(index)
        else:
            observe_indexes.append(index)

    keep_indexes = set()
    changed = False
    for indexes, source_name in (
        (blacklist_indexes, BLACKLIST_SOURCE_NAME),
        (observe_indexes, OBSERVATION_SOURCE_NAME),
    ):
        if len(indexes) <= limit:
            keep_indexes.update(indexes)
            continue
        ordered = sorted(indexes, key=lambda item_index: (detail_record_time(logs[item_index]), item_index), reverse=True)
        keep_indexes.update(ordered[:limit])
        for item_index in ordered[limit:]:
            archive_record(plugin, "anti_cheat_log", logs[item_index], source_name, dedupe=True)
            changed = True
    kept = [log for index, log in enumerate(logs) if index in keep_indexes]
    return kept, changed


def anti_cheat_log_key(record: dict) -> tuple:
    """生成观察日志记录的去重键。"""
    if not isinstance(record, dict):
        return ("", "", "", "", "")
    return (
        str(record.get("title") or ""),
        str(record.get("reason") or ""),
        str(record.get("detail") or ""),
        str(record.get("time") or ""),
        str(record.get("link") or ""),
    )


def remove_legacy_observation_completed_archives(plugin) -> bool:
    """将旧版观察完成归档迁回观察日志并从归档页移除。"""
    archives = storage.read_archive_records(plugin)
    if not isinstance(archives, list):
        return False
    logs = storage.read_anti_cheat_logs(plugin)
    existing_log_keys = {anti_cheat_log_key(log) for log in logs if isinstance(log, dict)}
    kept_archives = []
    changed = False
    for archive in archives:
        if not isinstance(archive, dict):
            changed = True
            continue
        if archive.get("source") != OBSERVATION_COMPLETED_SOURCE:
            kept_archives.append(archive)
            continue
        record = dict(archive.get("record") or {})
        record["title"] = record.get("title") or archive.get("title") or ""
        record["time"] = record.get("time") or archive.get("time") or ""
        record["reason"] = record.get("reason") or OBSERVATION_COMPLETED_REASON
        key = anti_cheat_log_key(record)
        if key not in existing_log_keys:
            logs.append(record)
            existing_log_keys.add(key)
        changed = True
    if changed:
        storage.save_archive_records(plugin, kept_archives)
        storage.save_anti_cheat_logs(plugin, logs)
    return changed


def paginate_archive_records(plugin, page: int = 1, page_size: int = 20) -> dict:
    """返回已去重并按归档时间倒序排列的归档分页。"""
    remove_legacy_observation_completed_archives(plugin)
    archives = storage.read_archive_records(plugin)
    valid_archives = [item for item in archives if isinstance(item, dict)]
    deduped_archives, changed = dedupe_archive_records(valid_archives)
    if changed or len(valid_archives) != len(archives):
        storage.save_archive_records(plugin, deduped_archives)
    ordered_archives = sorted(deduped_archives, key=lambda item: item.get("archived_at", ""), reverse=True)
    safe_page = max(int(page), 1)
    safe_page_size = max(int(page_size), 1)
    total = len(ordered_archives)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return {
        "items": ordered_archives[start:end],
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "total_pages": (total + safe_page_size - 1) // safe_page_size,
    }


def restore_archive_record(
    plugin,
    archive_id: str,
    same_record_checker: Callable[[dict, str, str, str, Any], bool],
) -> dict:
    """将归档记录恢复回原数据列表。"""
    if not archive_id:
        return {"success": False, "message": "缺少归档标识"}
    archive = remove_archive(plugin, archive_id)
    if not archive:
        return {"success": False, "message": "未找到归档记录"}
    source = archive.get("source")
    record = archive.get("record") or {}
    if source == "subscribe_history":
        records = storage.read_subscribe_records(plugin)
        exists = any(same_record_checker(
            item,
            record.get("unique", ""),
            record.get("time", ""),
            record.get("title", ""),
            record.get("tmdbid"),
        ) for item in records)
        if not exists:
            records.append(record)
        storage.save_subscribe_records(plugin, records)
    elif source == "anti_cheat_log":
        logs = storage.read_anti_cheat_logs(plugin)
        logs.append(record)
        storage.save_anti_cheat_logs(plugin, logs)
    elif source == "observation":
        rank_key = record.get("rank_key") or archive.get("rank_key") or ""
        if not rank_key:
            return {"success": False, "message": "归档缺少榜单标识"}
        history = storage.read_rank_history(plugin, rank_key)
        restored = False
        for item in history:
            if isinstance(item, dict) and item.get("unique") == record.get("unique"):
                item.update(record)
                item["observing"] = True
                item["observe_deleted"] = False
                restored = True
                break
        if not restored:
            record["observing"] = True
            record["observe_deleted"] = False
            history.append(record)
        storage.save_rank_history(plugin, rank_key, history)
    else:
        return {"success": False, "message": "未知归档类型"}
    return {"success": True, "message": "已恢复归档记录"}


def delete_archive_record(plugin, archive_id: str) -> dict:
    """永久删除一条归档记录。"""
    if not archive_id:
        return {"success": False, "message": "缺少归档标识"}
    archive = remove_archive(plugin, archive_id)
    if not archive:
        return {"success": False, "message": "未找到归档记录"}
    return {"success": True, "message": "已删除归档记录"}
