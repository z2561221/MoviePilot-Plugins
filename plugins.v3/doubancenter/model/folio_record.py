"""观影档案的播放身份、同步状态与时间线投影。"""

from __future__ import annotations

import hashlib
import json
import re
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
    if identity := library_key(origin):
        return identity
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


def library_key(origin: dict) -> str:
    """媒体库的真实季条目决定一条档案，不随外部 Part 或剧集组变化。"""
    reference = origin.get("mediaserver") or {}
    if not isinstance(reference, dict):
        return ""
    values = [str(reference.get(key) or "").strip() for key in ("server", "series_id", "season_id")]
    if not all(values) or media_kind(origin.get("type")) != "tv":
        return ""
    return "folio:library:" + json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def same_native_season(left: dict, right: dict) -> bool:
    """仅为唯一旧档案接续季身份；已知的不同媒体库季条目不能互相覆盖。"""
    left_id = resolve_media_identity(media_source=left.get("media_source"), media_id=left.get("media_id"))
    right_id = resolve_media_identity(media_source=right.get("media_source"), media_id=right.get("media_id"))
    if not all(left_id) or left_id != right_id:
        return False
    if library_key(left) and library_key(right) and library_key(left) != library_key(right):
        return False
    return (media_kind(left.get("type")) == media_kind(right.get("type")) == "tv"
            and left.get("season") is not None and str(left["season"]) == str(right.get("season")))


def library_title(title: str) -> str:
    """保留正式作品名称，媒体库整季展示不追加分播 Part 标签。"""
    return re.sub(r"\s+Part\s*[.\-]?\s*\d+\s*$", "", str(title or ""), flags=re.IGNORECASE).strip()


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
        select = min if library_key(origin) else max
        return select(matches, key=lambda item: str(item[1].get("timestamp") or ""))
    # 修复后的库内季可接住旧队列；尚未迁移的唯一记录须重新核验后才复用状态。
    migrated = [(key, value) for key, value in data.items()
                if isinstance(value, dict)
                and (library_key(origin) or library_key(value.get("origin") or {}))
                and same_native_season(origin, value.get("origin") or {})]
    if len(migrated) == 1:
        return migrated[0]
    legacy = data.get(title)
    if not identity and isinstance(legacy, dict) and not legacy.get("origin"):
        return title, legacy
    return identity or title, {}


def already_synced(record: dict, status: str) -> bool:
    """重复事件不重写；已经看过的同一季不退回在看。"""
    previous = record.get("watch_status")
    if previous == "collect" or previous == status:
        return True
    return bool(record) and not previous and status == "do" and record.get("identity_scope") != "library_season"


def fingerprint(data: dict) -> str:
    """为原始记录生成用于乐观并发校验的摘要。"""
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _timeline_identity(key: str, record: dict) -> str:
    """合并已知媒体身份；待核实或缺失身份的记录保持独立。"""
    if record.get("identity_status") == "unresolved":
        return "unresolved:" + key
    if identity := library_key(record.get("origin") or {}):
        return identity
    source, media_id = record.get("media_source"), record.get("media_id")
    if source is None and media_id is None and record.get("subject_id"):
        source, media_id = "douban", record["subject_id"]
    source, media_id = resolve_media_identity(media_source=source, media_id=media_id)
    if source and media_id:
        return json.dumps([media_kind(record.get("type")), build_media_key(source, media_id)], ensure_ascii=False)
    return "legacy:" + key


def timeline_records(data: dict) -> dict:
    """只读构建时间线：库内一季一条保留最早日期，旧条目继续按媒体去重。"""
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
        prefer = (identity not in selected or
                  (order < selected[identity][0] if identity.startswith("folio:library:")
                   else order > selected[identity][0]))
        if prefer:
            title = record.get("display_title") or record.get("subject_name") or key
            selected[identity] = (order, {
                **record,
                "display_title": library_title(title) if library_key(record.get("origin") or {}) else title,
            })
    return {key: value[1] for key, value in selected.items()}
