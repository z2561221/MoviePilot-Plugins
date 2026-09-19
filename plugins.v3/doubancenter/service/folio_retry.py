"""待核实观影身份的逐条退避，不改变分季匹配条件。"""

import time

from ..model import folio_record


BASE_DELAY_SECONDS = 30 * 60
MAX_DELAY_SECONDS = 6 * 60 * 60


def context_key(origin: dict, status: str) -> str:
    """播放身份、观影状态或实际库内季信息变化时允许立即复核。"""
    library = origin.get("library_season") or {}
    return folio_record.fingerprint({
        "identity": folio_record.origin_key(origin),
        "status": status,
        "library": {key: library.get(key) for key in (
            "season", "air_date", "episode_count", "episode_numbers", "episodes",
        )},
    })


def is_due(record: dict, origin: dict, status: str) -> bool:
    """旧队列和已核实身份照常处理，未决身份按保存的时间重试。"""
    if record.get("identity_status") != "unresolved":
        return True
    if record.get("retry_context") != context_key(origin, status):
        return True
    try:
        return time.time() >= float(record.get("next_retry_at") or 0)
    except (TypeError, ValueError):
        return True


def failure_changed(previous: dict, origin: dict, status: str, reason: str) -> bool:
    """只在新条目、输入或失败原因变化时重新报告警告。"""
    return (
        previous.get("identity_status") != "unresolved"
        or previous.get("identity_reason") != reason
        or previous.get("retry_context") != context_key(origin, status)
    )


def defer(record: dict, previous: dict) -> None:
    """持久化递增等待时间；损坏的旧重试计数按首次失败处理。"""
    origin = record.get("origin") or {}
    status = record.get("status") or "do"
    unchanged = not failure_changed(previous, origin, status, record.get("identity_reason") or "")
    try:
        attempts = max(0, int(previous.get("retry_count") or 0)) if unchanged else 0
    except (TypeError, ValueError):
        attempts = 0
    attempts = min(attempts + 1, 5)
    delay = min(BASE_DELAY_SECONDS * 2 ** (attempts - 1), MAX_DELAY_SECONDS)
    record.update(
        retry_count=attempts,
        retry_context=context_key(origin, status),
        next_retry_at=time.time() + delay,
    )
