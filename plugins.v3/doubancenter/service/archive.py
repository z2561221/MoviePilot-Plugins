"""豆瓣中心归档服务。"""

import datetime
from copy import deepcopy
from typing import Any, Callable, Optional

from ..model import archive_match
from ..storage import records as storage
from . import lifecycle

# 保留原服务符号，匹配规则的唯一实现归纯模型模块。
archive_record_key = archive_match.archive_record_key
archive_record_score = archive_match.archive_record_score
same_archive_record = archive_match.same_archive_record

DETAIL_SECTION_LIMIT = 5
DETAIL_OVERFLOW_REASON = "超过详情页显示上限归档"
BLACKLIST_REASON = "黑名拦截"
LEGACY_BLACKLIST_REASON = "黑名单关键词"
BLACKLIST_SOURCE_NAME = "黑名拦截"
OBSERVATION_SOURCE_NAME = "观察日志"
OBSERVATION_COMPLETED_SOURCE = "observation_completed"
OBSERVATION_QUEUE_SOURCE_NAME = "观察队列"
SUBSCRIBE_HISTORY_SOURCE_NAME = "订阅历史"
OBSERVATION_START_REASON = "开始观察"
OBSERVATION_WAIT_REASON = "继续观察"
OBSERVATION_COMPLETED_REASON = "观察完成"
OBSERVATION_DROPPED_REASON = "跌出榜单"
LEGACY_OBSERVATION_COMPLETED_REASON = "观察期完成"
LEGACY_REASON_MAP = {
    LEGACY_BLACKLIST_REASON: BLACKLIST_REASON,
    "观察期首次记录": OBSERVATION_START_REASON,
    "观察期未满": OBSERVATION_WAIT_REASON,
    LEGACY_OBSERVATION_COMPLETED_REASON: OBSERVATION_COMPLETED_REASON,
}


def normalize_reason(reason: str = "") -> str:
    """归一化归档记录中的旧版状态名。"""
    reason = str(reason or "")
    return LEGACY_REASON_MAP.get(reason, reason)


def subscribe_display_status(record: dict) -> str:
    """返回订阅历史归档的展示状态。"""
    status = str((record or {}).get("status") or "")
    if status == "failed":
        return "订阅失败"
    if status == "success":
        return "订阅成功"
    if normalize_reason((record or {}).get("reason") or "") == DETAIL_OVERFLOW_REASON:
        return "订阅成功"
    return normalize_reason((record or {}).get("reason") or "") or "订阅历史"


def observation_display_status(record: dict) -> str:
    """返回观察队列归档的展示状态。"""
    remaining = (record or {}).get("remaining_days")
    if remaining not in (None, ""):
        return f"剩余 {remaining} 天"
    elapsed = (record or {}).get("elapsed_days")
    total = (record or {}).get("observe_days")
    if elapsed not in (None, "") and total not in (None, ""):
        return f"观察 {elapsed} / {total} 天"
    return normalize_reason((record or {}).get("reason") or "") or "观察中"


def normalize_archive_item(archive: dict) -> dict:
    """按来源补齐归档条目的展示字段。"""
    item = dict(archive or {})
    record = dict(item.get("record") or {})
    source = str(item.get("source") or "")
    if "reason" in record:
        record["reason"] = normalize_reason(record.get("reason") or "")
    if record.get("observe_dropped_reason"):
        record["observe_dropped_reason"] = normalize_reason(record.get("observe_dropped_reason") or "")

    archive_reason = str(item.get("archive_reason") or "")
    if not archive_reason and str(item.get("reason") or "") == DETAIL_OVERFLOW_REASON:
        archive_reason = DETAIL_OVERFLOW_REASON
    if not archive_reason and str(record.get("reason") or "") == DETAIL_OVERFLOW_REASON:
        archive_reason = DETAIL_OVERFLOW_REASON
    if archive_reason:
        item["archive_reason"] = archive_reason

    item["record"] = record
    item["title"] = record.get("title") or item.get("title") or ""
    item["time"] = record.get("time") or record.get("first_seen") or item.get("time") or ""
    item["rank_key"] = record.get("rank_key") or item.get("rank_key") or ""
    item["rank_name"] = record.get("rank_name") or item.get("rank_name") or ""
    item["poster"] = record.get("poster") or record.get("cover") or item.get("poster") or ""
    item["detail"] = record.get("detail") or item.get("detail") or ""
    item["link"] = record.get("link") or item.get("link") or ""

    if source == "subscribe_history":
        item["source_name"] = SUBSCRIBE_HISTORY_SOURCE_NAME
        item["display_status"] = subscribe_display_status(record)
        item["reason"] = item.get("reason") or record.get("reason") or ""
    elif source == "observation":
        item["source_name"] = OBSERVATION_QUEUE_SOURCE_NAME
        item["display_status"] = observation_display_status(record)
        item["reason"] = normalize_reason(item.get("reason") or record.get("reason") or "")
    elif source == "anti_cheat_log":
        reason = normalize_reason(record.get("reason") or item.get("reason") or "")
        record["reason"] = reason
        item["reason"] = reason
        if reason == BLACKLIST_REASON:
            item["source_name"] = BLACKLIST_SOURCE_NAME
            item["display_status"] = record.get("detail") or item.get("detail") or BLACKLIST_REASON
        else:
            item["source_name"] = OBSERVATION_SOURCE_NAME
            item["display_status"] = reason or OBSERVATION_SOURCE_NAME
    else:
        item["source_name"] = item.get("source_name") or source
        item["reason"] = normalize_reason(item.get("reason") or record.get("reason") or "")
        item["display_status"] = item.get("display_status") or item.get("reason") or item.get("source_name") or "归档"
    return item


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
    return normalize_archive_item(archive)


def dedupe_archive_records(archives: list) -> tuple:
    """按原首次匹配语义去重，由单次候选索引缩小比较集合。"""
    if not isinstance(archives, list):
        return [], False
    merged = []
    candidates = archive_match.ArchiveMatchIndex()
    changed = False
    for archive in archives:
        if not isinstance(archive, dict):
            changed = True
            continue
        source = str(archive.get("source") or "")
        record = archive.get("record") or {}
        position, feature = candidates.find(source, record)
        if position is None:
            merged.append(archive)
            candidates.add(source, record, feature)
            continue
        changed = True
        existing = merged[position]
        if archive_record_score(record) > archive_record_score(existing.get("record") or {}):
            merged[position] = archive
            candidates.replace(position, record, feature)
    return merged[-500:], changed or len(merged) != len(archives)


def archive_record(plugin, source: str, record: dict, source_name: str = "", dedupe: bool = False) -> Optional[dict]:
    """将详情页删除的记录写入归档。"""
    if not isinstance(record, dict):
        return None
    archives = storage.read_archive_records(plugin)
    item, changed = _append_archive(archives, source, record, source_name, dedupe)
    if changed:
        storage.save_archive_records(plugin, archives)
    return item


def _append_archive(archives: list, source: str, record: dict, source_name: str, dedupe: bool):
    """在本次读取的列表内去重追加，不执行持久化。"""
    if dedupe:
        for index, archive in enumerate(archives):
            if not isinstance(archive, dict) or archive.get("source") != source:
                continue
            if same_archive_record(source, archive.get("record") or {}, record):
                if archive_record_score(record) > archive_record_score(archive.get("record") or {}):
                    archives[index] = update_archive_item_from_record(archive, source, record, source_name)
                    return archives[index], True
                return archive, False
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
    item = normalize_archive_item(item)
    archives.append(item)
    return item, True


def archive_records(plugin, source: str, records: list, source_name: str = "") -> None:
    """批量归档：先保存全部归档成功，调用方才能裁剪原记录。"""
    if not records:
        return
    archives = storage.read_archive_records(plugin)
    changed = False
    for record in records:
        if not isinstance(record, dict):
            continue
        _, added = _append_archive(archives, source, record, source_name, True)
        changed = changed or added
        # 保留原逐条写入时的容量与淘汰顺序。
        archives = archives[-storage.DETAIL_RECORD_LIMIT:]
    if changed:
        storage.save_archive_records(plugin, archives)


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
    overflow = []
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
        overflow.append(archived_record)
        changed = True
    archive_records(plugin, source, overflow, source_name)
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
        if str(log.get("reason") or "") in {BLACKLIST_REASON, LEGACY_BLACKLIST_REASON}:
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
        if record.get("reason") == LEGACY_OBSERVATION_COMPLETED_REASON:
            record["reason"] = OBSERVATION_COMPLETED_REASON
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
    archives = storage.read_archive_records(plugin)
    valid_archives = [normalize_archive_item(item) for item in archives if isinstance(item, dict)]
    deduped_archives, _ = dedupe_archive_records(valid_archives)
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


@lifecycle.rank_locked
def restore_archive_record(
    plugin,
    archive_id: str,
    same_record_checker: Callable[[dict, str, str, str, Any], bool],
) -> dict:
    """先保存恢复目标，再移除归档；清理失败时可幂等重试。"""
    if not archive_id:
        return {"success": False, "message": "缺少归档标识"}
    archives = storage.read_archive_records(plugin)
    archive = next((
        item for item in archives
        if isinstance(item, dict) and item.get("id") == archive_id
    ), None)
    if not archive:
        return {"success": False, "message": "未找到归档记录"}
    source = archive.get("source")
    record = deepcopy(archive.get("record") or {})
    if not isinstance(record, dict):
        return {"success": False, "message": "归档记录格式无效"}
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
        key = anti_cheat_log_key(record)
        if not any(anti_cheat_log_key(item) == key for item in logs):
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
    remove_archive(plugin, archive_id)
    return {"success": True, "message": "已恢复归档记录"}


def delete_archive_record(plugin, archive_id: str) -> dict:
    """永久删除一条归档记录。"""
    if not archive_id:
        return {"success": False, "message": "缺少归档标识"}
    archive = remove_archive(plugin, archive_id)
    if not archive:
        return {"success": False, "message": "未找到归档记录"}
    return {"success": True, "message": "已删除归档记录"}
