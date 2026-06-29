"""豆瓣中心归档服务。"""

import datetime
from typing import Optional

from ..storage import records as storage


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
