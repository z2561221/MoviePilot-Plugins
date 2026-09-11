"""将实际播放、已看标记和豆瓣同步时间分别记录。"""

import datetime

from ..model import folio_record
from ..storage import records as storage

TIMES_KEY = "folio_playback_times"


def event_time(event_info) -> str:
    """优先使用播放事件自身的日期，无有效日期时记录接收时刻。"""
    payload = getattr(event_info, "json_object", None)
    value = payload.get("Date") if isinstance(payload, dict) else None
    now = datetime.datetime.now().astimezone()
    try:
        timestamp = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        timestamp = timestamp.astimezone() if timestamp.tzinfo else timestamp.replace(tzinfo=now.tzinfo)
        if timestamp > now + datetime.timedelta(minutes=5):
            timestamp = now
    except (TypeError, ValueError):
        timestamp = now
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def observe(plugin, origin: dict, event_info, processed: dict, *, played: bool = False) -> None:
    """第 1 集也保留播放日期，跳过豆瓣同步和批量已看标记都不丢失首播记录。"""
    identity = folio_record.origin_key(origin)
    if not identity:
        return
    data = storage.read_dict(plugin, TIMES_KEY) if callable(getattr(plugin, "get_data", None)) else {}
    previous = data.get(identity) or {}
    timestamp = event_time(event_info)
    observed = dict(previous)
    if played:
        observed["last_marked_at"] = max(timestamp, previous.get("last_marked_at") or timestamp)
    else:
        observed["first_played_at"] = min(timestamp, previous.get("first_played_at") or timestamp)
        observed["last_played_at"] = max(timestamp, previous.get("last_played_at") or timestamp)
    if observed != previous:
        data[identity] = observed
        storage.write_dict(plugin, TIMES_KEY, data)
    key, record = folio_record.find_record(processed, origin, "")
    if record and folio_record.origin_key(record.get("origin") or {}) == identity:
        update = {**record, **{name: value for name, value in observed.items() if name != "first_played_at"}}
        if not played and record.get("first_played_at"):
            update["first_played_at"] = min(record["first_played_at"], observed["first_played_at"])
            update["timestamp"] = update["first_played_at"]
        if update != record:
            processed[key] = update
            storage.save_folio_data(plugin, processed)


def sync_fields(plugin, origin: dict, previous: dict) -> dict:
    """同步成功只更新同步时刻，不把旧档案或首次播放日期改成今天。"""
    getter = getattr(plugin, "get_data", None)
    data = getter(TIMES_KEY) if getter else {}
    observed = (data.get(folio_record.origin_key(origin)) or {}) if isinstance(data, dict) else {}
    now = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    result = {**observed, "last_synced_at": now}
    first = previous.get("first_played_at") or observed.get("first_played_at")
    if previous.get("first_played_at") and observed.get("first_played_at"):
        first = min(previous["first_played_at"], observed["first_played_at"])
    if previous.get("timestamp") and not previous.get("first_played_at"):
        # 无来源的旧时间不能被一次新播放冒充为首次观看；历史修复显式恢复。
        result["timestamp"] = previous["timestamp"]
        result["timestamp_source"] = previous.get("timestamp_source") or "legacy_sync"
        result.pop("first_played_at", None)
    elif first:
        result.update(timestamp=first, first_played_at=first,
                      timestamp_source=previous.get("timestamp_source") or "playback")
    else:
        result.update(timestamp=observed.get("last_marked_at") or now, timestamp_source="marked_or_synced")
    return result


def restore_first_playback(record: dict, value, evidence: str) -> dict:
    """使用已核对的历史证据恢复日期，同时保存被替换的同步时间。"""
    if not value:
        return record
    if not evidence:
        raise ValueError("恢复播放日期必须提供已核验的时间来源")
    first = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    first = first.astimezone().replace(tzinfo=None) if first.tzinfo else first
    old = datetime.datetime.fromisoformat(str(record["timestamp"]))
    if first > old or first > datetime.datetime.now().astimezone().replace(tzinfo=None):
        raise ValueError("首次播放时间不能晚于原档案时间或当前时间")
    timestamp = first.strftime("%Y-%m-%d %H:%M:%S")
    return {**record, "timestamp": timestamp, "first_played_at": timestamp,
            "timestamp_source": "verified_playback_evidence", "time_evidence": evidence,
            "last_synced_at": record.get("last_synced_at") or record["timestamp"]}
