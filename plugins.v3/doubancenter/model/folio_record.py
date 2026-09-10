"""观影档案的播放身份、同步状态与时间线投影。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from app.sdk.media import build_media_key, resolve_media_identity


def media_kind(value: Any) -> str:
    """统一播放器、宿主和历史记录的影视类型。"""
    value = str(getattr(value, "value", value) or "").strip().lower()
    if value in {"tv", "series", "电视剧", "剧集"}:
        return "tv"
    return "movie" if value in {"movie", "mov", "电影"} else value or "unknown"


def origin_key(origin: dict) -> str:
    """按来源、媒体、分季方式及播放季生成稳定身份。"""
    source, media_id = resolve_media_identity(
        media_source=origin.get("media_source"), media_id=origin.get("media_id"),
    )
    if not source or not media_id:
        return ""
    season = origin.get("season")
    try:
        season = int(season) if season is not None else None
    except (TypeError, ValueError):
        return ""
    values = [
        media_kind(origin.get("type")), build_media_key(source, media_id),
        season, str(origin.get("episode_group") or ""),
    ]
    return "folio:" + json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def find_record(data: dict, origin: dict, title: str) -> tuple[str, dict]:
    """复用同一播放身份；未迁移的标题记录不能冒充已核验身份。"""
    identity = origin_key(origin)
    matches = [
        (key, value) for key, value in data.items()
        if isinstance(value, dict)
        and identity
        and origin_key(value.get("origin") or {}) == identity
    ]
    if matches:
        return max(matches, key=lambda item: str(item[1].get("timestamp") or ""))
    legacy = data.get(title)
    if not identity and isinstance(legacy, dict) and not legacy.get("origin"):
        return title, legacy
    return identity or title, {}


def already_synced(record: dict, status: str) -> bool:
    """重复事件不重写；已经看过的同一季不退回在看。"""
    previous = record.get("watch_status")
    if previous == "collect" or previous == status:
        return True
    return bool(record) and not previous and status == "do"


def fingerprint(data: dict) -> str:
    """为原始记录生成用于乐观并发校验的摘要。"""
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _timeline_identity(key: str, record: dict) -> str:
    """合并已知媒体身份；待核实或缺失身份的记录保持独立。"""
    if record.get("identity_status") == "unresolved":
        return "unresolved:" + key
    source, media_id = record.get("media_source"), record.get("media_id")
    if source is None and media_id is None and record.get("subject_id"):
        source, media_id = "douban", record["subject_id"]
    source, media_id = resolve_media_identity(media_source=source, media_id=media_id)
    if source and media_id:
        return json.dumps([media_kind(record.get("type")), build_media_key(source, media_id)], ensure_ascii=False)
    return "legacy:" + key


def timeline_records(data: dict) -> dict:
    """只读构建时间线：同条目取最新观看时间，保留分季及未决记录。"""
    selected = {}
    for key, record in (data or {}).items():
        if not isinstance(record, dict) or not record.get("timestamp"):
            continue
        try:
            timestamp = datetime.fromisoformat(str(record["timestamp"]))
        except (ValueError, TypeError):
            continue
        identity = _timeline_identity(str(key), record)
        order = (timestamp.isoformat(), str(key))
        if identity not in selected or order > selected[identity][0]:
            selected[identity] = (order, {
                **record,
                "display_title": record.get("display_title") or record.get("subject_name") or key,
            })
    return {key: value[1] for key, value in selected.items()}
