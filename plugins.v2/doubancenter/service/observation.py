"""豆瓣中心观察期服务。"""

import datetime
from typing import Callable, List, Optional, Set

from app.log import logger

from . import archive as archive_service
from ..model import rank as rank_model
from ..storage import records as storage

DETAIL_SECTION_LIMIT = 5
DETAIL_OVERFLOW_REASON = "超过详情页显示上限归档"
OBSERVATION_SOURCE = "observation"
OBSERVATION_SOURCE_NAME = "观察队列"
BLACKLIST_REASON = "黑名拦截"
OBSERVE_START_REASON = "开始观察"
OBSERVE_WAIT_REASON = "继续观察"
OBSERVE_DONE_REASON = "观察完成"
OBSERVE_DROPPED_REASON = "跌出榜单"
OBSERVE_DROPPED_DETAIL = "跌出当前自动订阅候选"
LEGACY_REASON_MAP = {
    "黑名单关键词": BLACKLIST_REASON,
    "观察期首次记录": OBSERVE_START_REASON,
    "观察期未满": OBSERVE_WAIT_REASON,
    "观察期完成": OBSERVE_DONE_REASON,
}


def normalize_log_reason(reason: str = "") -> str:
    """将旧版观察日志状态归一为四字状态。"""
    reason = str(reason or "")
    return LEGACY_REASON_MAP.get(reason, reason)


def normalize_log_record(record: dict) -> dict:
    """复制并归一化观察日志记录的状态字段。"""
    copied = dict(record or {})
    copied["reason"] = normalize_log_reason(copied.get("reason") or "")
    if str(copied.get("observe_dropped_reason") or "") == OBSERVE_DROPPED_DETAIL:
        copied["observe_dropped_reason"] = OBSERVE_DROPPED_REASON
    return copied


def log_anti_cheat(plugin, reason: str, title: str, detail: str = "", link: str = "") -> None:
    """记录订阅过滤与观察期日志。"""
    reason = normalize_log_reason(reason)
    logs = storage.read_anti_cheat_logs(plugin)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    matched = None
    kept = []
    for log in logs:
        if not isinstance(log, dict):
            kept.append(log)
            continue
        copied = normalize_log_record(log)
        if (
            copied.get("reason") == reason
            and copied.get("title") == title
            and copied.get("detail") == detail
            and (copied.get("link") or "") == (link or "")
        ):
            if matched is None:
                matched = copied
            else:
                try:
                    matched["count"] = int(matched.get("count") or 1) + int(copied.get("count") or 1)
                except (TypeError, ValueError):
                    matched["count"] = int(matched.get("count") or 1) + 1
            continue
        kept.append(copied)
    if matched is not None:
        try:
            matched["count"] = int(matched.get("count") or 1) + 1
        except (TypeError, ValueError):
            matched["count"] = 2
        matched["time"] = now
        kept.append(matched)
        logs = kept
    else:
        logs = kept
        logs.append({
            "time": now,
            "reason": reason,
            "title": title,
            "detail": detail,
            "link": link or "",
        })
    storage.save_anti_cheat_logs(plugin, logs)


def cleanup_observe_logs(plugin, title: str = "", unique: str = "") -> None:
    """订阅成功后清理对应条目的观察期日志。"""
    logs = storage.read_anti_cheat_logs(plugin)
    if not isinstance(logs, list):
        return
    observe_reasons = {OBSERVE_START_REASON, OBSERVE_WAIT_REASON}
    title = str(title or "")
    unique = str(unique or "")
    kept = []
    changed = False
    for log in logs:
        if not isinstance(log, dict):
            kept.append(log)
            continue
        copied = normalize_log_record(log)
        reason = copied.get("reason") or ""
        log_title = str(log.get("title") or "")
        if reason in observe_reasons and log_title in {title, unique}:
            changed = True
            continue
        if copied != log:
            changed = True
        kept.append(copied)
    if changed:
        storage.save_anti_cheat_logs(plugin, kept)


def default_observe_rank_keys() -> List[str]:
    """返回默认启用观察期的波动榜单。"""
    return rank_model.default_observe_rank_keys()


def rank_observe_enabled(plugin, rank_key: str = "") -> bool:
    """判断指定榜单是否启用观察期。"""
    if int(getattr(plugin, "_observe_days", 0) or 0) <= 0:
        return False
    selected = getattr(plugin, "_observe_rank_keys", None)
    if selected is None:
        selected = default_observe_rank_keys()
    if not isinstance(selected, (list, tuple, set)):
        return False
    selected_keys = {str(item) for item in selected if str(item)}
    if not rank_key:
        return bool(selected_keys)
    return str(rank_key) in selected_keys


def observed_item_subscription_exists(
    item: dict,
    rank_key: str = "",
    *,
    media_chain_factory=None,
    subscribe_chain_factory=None,
    media_type_enum=None,
    meta_factory=None,
) -> bool:
    """检查观察队列条目是否已经存在订阅。"""
    title = str((item or {}).get("title") or "")
    if not title:
        return False
    try:
        if media_type_enum is None:
            from app.schemas.types import MediaType as media_type_enum
        if meta_factory is None:
            from app.core.metainfo import MetaInfo as meta_factory
        if media_chain_factory is None:
            from app.chain.media import MediaChain
            media_chain_factory = MediaChain
        if subscribe_chain_factory is None:
            from app.chain.subscribe import SubscribeChain
            subscribe_chain_factory = SubscribeChain

        raw_type = str((item or {}).get("mtype") or (item or {}).get("media_type") or "").lower()
        if raw_type in ("movie", "电影") or rank_key == "movie_weekly":
            media_type = media_type_enum.MOVIE
        else:
            media_type = media_type_enum.TV
        meta = meta_factory(title)
        year = (item or {}).get("year") or ""
        if year:
            meta.year = str(year)
        meta.type = media_type
        mediainfo = media_chain_factory().recognize_media(meta=meta, mtype=media_type)
        if not mediainfo:
            return False
        return bool(subscribe_chain_factory().exists(mediainfo=mediainfo, meta=meta))
    except Exception:
        return False


def check_observe(plugin, unique: str, history: List[dict], title: str = "", rank_key: str = "") -> bool:
    """条目仍处于观察期内时返回 True。"""
    if rank_key and not rank_observe_enabled(plugin, rank_key):
        return False
    days = int(plugin._observe_days or 0)
    if days <= 0:
        return False
    now = datetime.datetime.now()
    for item in history:
        if item.get("unique") != unique:
            continue
        if item.get("observe_deleted"):
            logger.info(f"豆瓣中心：条目《{item.get('title') or title or unique}》已从观察队列删除，跳过订阅")
            return True
        if item.get("observe_dropped_at") or item.get("observe_dropped_reason") == OBSERVE_DROPPED_REASON:
            observed_at = now.strftime("%Y-%m-%d %H:%M:%S")
            item["time"] = observed_at
            item["first_seen"] = observed_at
            item["observing"] = True
            item.pop("observe_dropped_at", None)
            item.pop("observe_dropped_reason", None)
            item.pop("observe_dropped_detail", None)
            logger.info(f"豆瓣中心：条目《{item.get('title') or title or unique}》重新进入观察期（0/{days} 天），跳过订阅")
            log_anti_cheat(plugin, OBSERVE_START_REASON, item.get("title") or title or unique, f"需要观察 {days} 天")
            return True
        first_seen = item.get("first_seen") or item.get("time", "")
        if first_seen:
            try:
                first_seen_at = datetime.datetime.strptime(first_seen, "%Y-%m-%d %H:%M:%S")
                elapsed = (now - first_seen_at).days
                if elapsed < days:
                    item["first_seen"] = first_seen
                    item["observing"] = True
                    logger.info(f"豆瓣中心：条目《{item.get('title')}》观察期未满（{elapsed}/{days} 天），跳过订阅")
                    log_anti_cheat(plugin, OBSERVE_WAIT_REASON, item.get("title", ""), f"已过 {elapsed} 天，需要 {days} 天")
                    return True
                logger.info(f"豆瓣中心：条目《{item.get('title') or title or unique}》观察期已满（{elapsed}/{days} 天），继续订阅")
                log_anti_cheat(plugin, OBSERVE_DONE_REASON, item.get("title") or title or unique, f"已过 {elapsed} 天，达到 {days} 天")
                return False
            except Exception:
                pass
        item["time"] = now.strftime("%Y-%m-%d %H:%M:%S")
        item["first_seen"] = item["time"]
        item["observing"] = True
        return True
    observed_at = now.strftime("%Y-%m-%d %H:%M:%S")
    history.append({
        "title": title or unique,
        "time": observed_at,
        "first_seen": observed_at,
        "unique": unique,
        "observing": True,
    })
    logger.info(f"豆瓣中心：条目《{title or unique}》首次进入观察期（0/{days} 天），跳过订阅")
    log_anti_cheat(plugin, OBSERVE_START_REASON, title or unique, f"需要观察 {days} 天")
    return True


def pending_observations(
    plugin,
    *,
    ranks: list,
    rank_history_reader: Callable[[object, str], list],
    item_existing_subscription_checker: Callable[[dict], bool],
    observed_subscription_exists_checker: Callable[..., bool],
    archive_record_callback: Callable[..., Optional[dict]],
    now: Optional[datetime.datetime] = None,
    limit: int = DETAIL_SECTION_LIMIT,
) -> dict:
    """获取观察期内等待自动订阅的榜单条目。"""
    observe_days = int(getattr(plugin, "_observe_days", 0) or 0)
    if observe_days <= 0:
        return {"data": []}
    now = now or datetime.datetime.now()
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    items = []
    histories = {}
    changed_rank_keys = set()
    for rank in ranks or []:
        if not isinstance(rank, dict):
            continue
        rank_key = str(rank.get("key") or "")
        if not rank_key:
            continue
        history = rank_history_reader(plugin, rank_key)
        histories[rank_key] = history
        changed = False
        for item in history:
            if not isinstance(item, dict) or not item.get("observing"):
                continue
            if (
                item.get("observe_deleted")
                or item.get("subscribed")
                or item.get("subscribed_at")
                or item_existing_subscription_checker(item)
            ):
                continue
            if observed_subscription_exists_checker(item, rank_key=rank_key):
                item["observing"] = False
                item["existing"] = True
                item["existing_at"] = now_text
                item["existing_reason"] = "subscribe"
                changed = True
                continue
            first_seen = item.get("first_seen") or item.get("time") or ""
            elapsed_days = 0
            if first_seen:
                try:
                    first_seen_at = datetime.datetime.strptime(first_seen, "%Y-%m-%d %H:%M:%S")
                    elapsed_days = max((now - first_seen_at).days, 0)
                except Exception:
                    elapsed_days = 0
            pending = dict(item)
            pending.update({
                "rank_key": rank_key,
                "rank_name": rank.get("name") or rank_key,
                "observe_days": observe_days,
                "elapsed_days": elapsed_days,
                "remaining_days": max(observe_days - elapsed_days, 0),
            })
            items.append(pending)
        if changed:
            changed_rank_keys.add(rank_key)
    items.sort(key=lambda item: item.get("first_seen") or item.get("time") or "", reverse=True)
    if limit and len(items) > limit:
        overflow = items[limit:]
        items = items[:limit]
        for pending in overflow:
            if not isinstance(pending, dict):
                continue
            rank_key = pending.get("rank_key") or ""
            history = histories.get(rank_key, [])
            target_unique = pending.get("unique")
            target_title = pending.get("title")
            for item in history:
                if not isinstance(item, dict):
                    continue
                same_unique = target_unique and item.get("unique") == target_unique
                same_title = not target_unique and target_title and item.get("title") == target_title
                if not (same_unique or same_title):
                    continue
                item["observing"] = False
                item["observe_deleted"] = True
                item["observe_deleted_at"] = now_text
                item["observe_deleted_reason"] = DETAIL_OVERFLOW_REASON
                changed_rank_keys.add(rank_key)
                break
            record = dict(pending)
            record["reason"] = DETAIL_OVERFLOW_REASON
            archive_record_callback(plugin, OBSERVATION_SOURCE, record, OBSERVATION_SOURCE_NAME, dedupe=True)
    for rank_key in changed_rank_keys:
        if rank_key:
            storage.save_rank_history(plugin, rank_key, histories.get(rank_key, []))
    return {"data": items}


def delete_observation(
    plugin,
    *,
    unique: str = "",
    rank_key: str = "",
    title: str = "",
    ranks: list,
    rank_history_reader: Callable[[object, str], list],
    archive_record_callback: Callable[..., Optional[dict]],
    now: Optional[datetime.datetime] = None,
) -> dict:
    """从观察队列删除条目，并标记为已忽略以避免再次自动进入队列。"""
    if not unique:
        return {"success": False, "message": "缺少观察条目标识"}
    rank_keys = [rank_key] if rank_key else [rank.get("key") for rank in ranks if isinstance(rank, dict)]
    now_text = (now or datetime.datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    for key in rank_keys:
        key = str(key or "")
        if not key:
            continue
        history = rank_history_reader(plugin, key)
        record = None
        for item in history:
            if not isinstance(item, dict) or item.get("unique") != unique:
                continue
            item["observing"] = False
            item["observe_deleted"] = True
            item["observe_deleted_at"] = now_text
            if title:
                item["title"] = item.get("title") or title
            record = dict(item)
            record["rank_key"] = key
            break
        if record is None:
            continue
        archive = archive_record_callback(plugin, OBSERVATION_SOURCE, record, OBSERVATION_SOURCE_NAME)
        storage.save_rank_history(plugin, key, history)
        return {"success": True, "message": "已归档观察条目", "archive_id": archive.get("id") if archive else ""}
    return {"success": False, "message": "未找到观察条目"}


def delete_anti_cheat_log(
    plugin,
    *,
    time: str = "",
    title: str = "",
    reason: str = "",
    archive_record_callback: Callable[..., Optional[dict]],
) -> dict:
    """删除一条观察日志记录并写入归档。"""
    if not (time or title or reason):
        return {"success": False, "message": "缺少观察日志标识"}
    logs = storage.read_anti_cheat_logs(plugin)
    normalized_reason = normalize_log_reason(reason)
    removed = []
    kept = []
    for item in logs:
        if not isinstance(item, dict):
            kept.append(item)
            continue
        copied = normalize_log_record(item)
        matched = (
            (not time or copied.get("time") == time)
            and (not title or copied.get("title") == title)
            and (not normalized_reason or copied.get("reason") == normalized_reason)
        )
        if matched:
            removed.append(copied)
        else:
            kept.append(copied)
    if not removed:
        return {"success": False, "message": "未找到观察日志"}
    archive = None
    for item in removed:
        archive = archive_record_callback(plugin, "anti_cheat_log", item, "观察日志") or archive
    storage.save_anti_cheat_logs(plugin, kept)
    return {"success": True, "message": "已归档观察日志", "archive_id": archive.get("id") if archive else ""}


def archived_completion_titles(plugin) -> Set[str]:
    """收集已经归档的观察完成日志标题。"""
    titles = set()
    archives = storage.read_archive_records(plugin)
    if not isinstance(archives, list):
        return titles
    for archive in archives:
        if not isinstance(archive, dict):
            continue
        record = archive.get("record") or {}
        if archive.get("source") == "anti_cheat_log" and normalize_log_reason(record.get("reason") or "") == OBSERVE_DONE_REASON:
            titles.add(str(record.get("title") or archive.get("title") or ""))
    return titles


def list_anti_cheat_logs(
    plugin,
    *,
    ranks: list,
    existing_subscription_checker: Callable[[dict], bool],
    limit: int = DETAIL_SECTION_LIMIT,
) -> dict:
    """返回已修正、去重并治理溢出的观察日志列表。"""
    archive_service.remove_legacy_observation_completed_archives(plugin)
    logs = storage.read_anti_cheat_logs(plugin)
    logs, changed = reconcile_anti_cheat_logs(
        logs,
        subscribe_records=storage.read_subscribe_records(plugin),
        ranks=ranks,
        archived_completion_titles=archived_completion_titles(plugin),
        existing_subscription_checker=existing_subscription_checker,
    )
    logs, overflow_changed = archive_service.archive_anti_cheat_overflow(plugin, logs, limit)
    if changed or overflow_changed:
        storage.save_anti_cheat_logs(plugin, logs)
    return {"data": logs}


def dedupe_anti_cheat_logs(logs: list) -> tuple:
    """按原因、标题和详情合并观察日志。"""
    if not isinstance(logs, list):
        return [], False
    merged = []
    index = {}
    changed = False
    for log in logs:
        if not isinstance(log, dict):
            continue
        normalized_reason = normalize_log_reason(log.get("reason") or "")
        key = (normalized_reason, log.get("title") or "", log.get("detail") or "")
        if key in index:
            target = merged[index[key]]
            try:
                target["count"] = int(target.get("count") or 1) + int(log.get("count") or 1)
            except (TypeError, ValueError):
                target["count"] = int(target.get("count") or 1) + 1
            if (log.get("time") or "") >= (target.get("time") or ""):
                target["time"] = log.get("time")
            changed = True
            continue
        copied = normalize_log_record(log)
        if copied != log:
            changed = True
        if int(copied.get("count") or 1) > 1:
            copied["count"] = int(copied.get("count") or 1)
        index[key] = len(merged)
        merged.append(copied)
    if len(merged) != len(logs):
        changed = True
    return merged[-100:], changed


def finished_observation_titles(
    *,
    subscribe_records: list,
    ranks: list,
    existing_subscription_checker: Callable[[dict], bool],
) -> Set[str]:
    """收集已经结束观察的条目标题，用于清理观察日志。"""
    titles = set()
    if isinstance(subscribe_records, list):
        for record in subscribe_records:
            if not isinstance(record, dict):
                continue
            status = str(record.get("status") or "success")
            title = str(record.get("title") or "")
            if title and status != "failed":
                titles.add(title)
    if not isinstance(ranks, list):
        return titles
    for rank in ranks:
        history = rank.get("history") if isinstance(rank, dict) else []
        if not isinstance(history, list):
            continue
        for item in history:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            if not title:
                continue
            finished = (
                item.get("subscribed")
                or item.get("subscribed_at")
                or existing_subscription_checker(item)
                or (item.get("observing") is False and (item.get("observe_dropped_at") or item.get("observe_deleted_at")))
            )
            if finished:
                titles.add(title)
    return titles


def observation_completion_log(item: dict, rank: dict) -> Optional[dict]:
    """从榜单历史构造观察完成日志。"""
    if not isinstance(item, dict) or not isinstance(rank, dict):
        return None
    title = str(item.get("title") or "")
    first_seen = str(item.get("first_seen") or "")
    subscribed_at = str(item.get("subscribed_at") or "")
    if not title or not first_seen or not (item.get("subscribed") or subscribed_at):
        return None
    record = dict(item)
    record.update({
        "time": subscribed_at or str(item.get("time") or first_seen),
        "reason": OBSERVE_DONE_REASON,
        "title": title,
        "detail": f"{rank.get('name') or rank.get('key') or ''}：{first_seen} -> {subscribed_at or '已订阅'}",
        "link": item.get("link") or "",
        "rank_key": rank.get("key") or item.get("rank_key") or "",
        "rank_name": rank.get("name") or item.get("rank_name") or "",
        "first_seen": first_seen,
        "subscribed_at": subscribed_at,
    })
    return normalize_log_record(record)


def observation_dropped_log(item: dict, rank: dict) -> Optional[dict]:
    """从榜单历史构造跌出榜单日志。"""
    if not isinstance(item, dict) or not isinstance(rank, dict):
        return None
    title = str(item.get("title") or "")
    first_seen = str(item.get("first_seen") or "")
    dropped_at = str(item.get("observe_dropped_at") or "")
    if not title or not first_seen or not dropped_at:
        return None
    detail_reason = str(item.get("observe_dropped_detail") or OBSERVE_DROPPED_DETAIL)
    record = dict(item)
    record.update({
        "time": dropped_at,
        "reason": OBSERVE_DROPPED_REASON,
        "title": title,
        "detail": f"{rank.get('name') or rank.get('key') or ''}：{first_seen} -> {dropped_at}，{detail_reason}",
        "link": item.get("link") or "",
        "rank_key": rank.get("key") or item.get("rank_key") or "",
        "rank_name": rank.get("name") or item.get("rank_name") or "",
        "first_seen": first_seen,
        "observe_dropped_at": dropped_at,
        "observe_dropped_reason": OBSERVE_DROPPED_REASON,
    })
    return normalize_log_record(record)


def append_observation_completion_logs(
    logs: list,
    *,
    ranks: list,
    archived_completion_titles: Set[str],
) -> tuple:
    """补齐已订阅观察条目的观察完成日志。"""
    if not isinstance(logs, list):
        logs = []
    changed = False
    existing_keys = {
        (str(log.get("title") or ""), normalize_log_reason(log.get("reason") or ""))
        for log in logs
        if isinstance(log, dict)
    }
    existing_keys.update((str(title), OBSERVE_DONE_REASON) for title in (archived_completion_titles or set()))
    if not isinstance(ranks, list):
        return logs, changed
    for rank in ranks:
        if not isinstance(rank, dict):
            continue
        history = rank.get("history") or []
        if not isinstance(history, list):
            continue
        for item in history:
            for record in (observation_completion_log(item, rank), observation_dropped_log(item, rank)):
                key = (str((record or {}).get("title") or ""), normalize_log_reason((record or {}).get("reason") or ""))
                if not record or key in existing_keys:
                    continue
                logs.append(record)
                existing_keys.add(key)
                changed = True
    if len(logs) > 100:
        logs = logs[-100:]
        changed = True
    return logs, changed


def reconcile_anti_cheat_logs(
    logs: list,
    *,
    subscribe_records: list,
    ranks: list,
    archived_completion_titles: Set[str],
    existing_subscription_checker: Callable[[dict], bool],
) -> tuple:
    """合并并清理已经结束观察项的观察日志。"""
    logs, changed = dedupe_anti_cheat_logs(logs)
    finished_titles = finished_observation_titles(
        subscribe_records=subscribe_records,
        ranks=ranks,
        existing_subscription_checker=existing_subscription_checker,
    )
    if finished_titles:
        observe_reasons = {OBSERVE_START_REASON, OBSERVE_WAIT_REASON}
        kept = []
        for log in logs:
            if (
                isinstance(log, dict)
                and normalize_log_reason(log.get("reason") or "") in observe_reasons
                and str(log.get("title") or "") in finished_titles
            ):
                changed = True
                continue
            kept.append(log)
        logs = kept
    logs, completion_logs_changed = append_observation_completion_logs(
        logs,
        ranks=ranks,
        archived_completion_titles=archived_completion_titles,
    )
    changed = changed or completion_logs_changed
    return logs, changed


def drop_stale_observations(history: List[dict], current_candidates: set) -> None:
    """将已跌出当前候选窗口的观察条目标记为结束。"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in history:
        if not isinstance(item, dict):
            continue
        if not item.get("observing") or item.get("subscribed") or item.get("existing") or item.get("observe_deleted"):
            continue
        unique = item.get("unique")
        if unique and unique not in current_candidates:
            item["observing"] = False
            item["observe_dropped_at"] = now
            item["observe_dropped_reason"] = OBSERVE_DROPPED_REASON
            item["observe_dropped_detail"] = OBSERVE_DROPPED_DETAIL
