"""Frozen reference from 17ff14fd: matching and greedy archive deduplication."""

from app.plugins.doubancenter.model.identity import identity_from_media


def archive_record_key(source: str, record: dict) -> tuple:
    """生成归档记录去重键。"""
    if not isinstance(record, dict):
        return (source, "")
    media_source, media_id = identity_from_media(record)
    return (
        source,
        str(record.get("unique") or ""),
        str(getattr(media_source, "value", media_source) or ""),
        str(media_id or ""),
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
    left_source, left_id = identity_from_media(left)
    right_source, right_id = identity_from_media(right)
    if left_source and left_id and right_source and right_id:
        if left_source != right_source or str(left_id) != str(right_id):
            return False
    for field in ("unique", "tmdbid", "tmdb_id", "reason", "detail", "link"):
        left_value = str(left.get(field) or "")
        right_value = str(right.get(field) or "")
        if left_value and right_value and left_value != right_value:
            return False
    return True



def dedupe_archive_records(archives: list) -> tuple:
    """压缩重复归档记录，保留信息更完整的一条。"""
    if not isinstance(archives, list):
        return [], False
    merged = []
    buckets = {}
    changed = False
    for archive in archives:
        if not isinstance(archive, dict):
            changed = True
            continue
        source = str(archive.get("source") or "")
        record = archive.get("record") or {}
        duplicate_index = None
        bucket = (source, str(record.get("title") or "") if isinstance(record, dict) else "")
        for index in buckets.get(bucket, []):
            existing = merged[index]
            if same_archive_record(source, existing.get("record") or {}, record):
                duplicate_index = index
                break
        if duplicate_index is None:
            buckets.setdefault(bucket, []).append(len(merged))
            merged.append(archive)
            continue
        changed = True
        existing = merged[duplicate_index]
        if archive_record_score(record) > archive_record_score(existing.get("record") or {}):
            merged[duplicate_index] = archive
    return merged[-500:], changed or len(merged) != len(archives)
