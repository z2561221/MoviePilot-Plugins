"""为观察日志保留、补齐可核验的媒体展示信息。"""

from ..model.identity import identity_from_media, identity_payload

MEDIA_FIELDS = (
    "poster", "rank_key", "rank_name", "link", "unique", "year", "media_type", "season",
    "media_source", "media_id", "douban_id", "bangumi_id", "original_title",
)


def media_snapshot(record: dict) -> dict:
    """只提取展示和身份字段，日志时间、状态与计数由日志自身维护。"""
    normalized = identity_payload(record)
    normalized["poster"] = (
        normalized.get("poster") or normalized.get("poster_path") or normalized.get("cover")
    )
    return {key: normalized[key] for key in MEDIA_FIELDS if normalized.get(key) not in (None, "")}


def _candidate_key(record: dict) -> tuple:
    source, media_id = identity_from_media(record)
    if source and media_id:
        return str(source), str(media_id), str(record.get("season") or "")
    for field in ("link", "unique"):
        if record.get(field):
            return field, str(record[field])
    return ()


def _matching_candidates(log: dict, candidates: list[dict]) -> list[dict]:
    source, media_id = identity_from_media(log)
    if source and media_id:
        matches = [item for item in candidates if identity_from_media(item) == (source, media_id)]
    elif log.get("media_source") or log.get("media_id"):
        return []
    elif log.get("unique"):
        matches = [item for item in candidates if item.get("unique") == log["unique"]]
    elif log.get("link"):
        matches = [item for item in candidates if item.get("link") == log["link"]]
    elif log.get("title"):
        matches = [item for item in candidates if item.get("title") == log["title"]]
    else:
        return []
    return [
        item for item in matches
        if all(
            log.get(field) in (None, "") or item.get(field) in (None, "")
            or str(log[field]) == str(item[field])
            for field in ("year", "media_type", "season", "rank_key")
        )
    ]


def enrich_log_metadata(logs: list, candidates: list[dict]) -> tuple[list, bool]:
    """仅在候选身份唯一时补缺字段，不改日志事实或猜测同名作品。"""
    candidates = [item for item in candidates if isinstance(item, dict) and _candidate_key(item)]
    result, changed = [], False
    for log in logs or []:
        if not isinstance(log, dict):
            result.append(log)
            continue
        copied = dict(log)
        matches = _matching_candidates(log, candidates)
        if len({_candidate_key(item) for item in matches}) == 1:
            for item in matches:
                for field, value in media_snapshot(item).items():
                    if copied.get(field) in (None, ""):
                        copied[field] = value
        changed = changed or copied != log
        result.append(copied)
    return result, changed
