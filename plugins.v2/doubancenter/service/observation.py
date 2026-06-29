"""豆瓣中心观察期服务。"""

import datetime
from typing import List

from app.log import logger

from ..model import rank as rank_model
from ..storage import records as storage


def log_anti_cheat(plugin, reason: str, title: str, detail: str = "", link: str = "") -> None:
    """记录订阅过滤与观察期日志。"""
    logs = storage.read_anti_cheat_logs(plugin)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    matched = None
    kept = []
    for log in logs:
        if (
            isinstance(log, dict)
            and log.get("reason") == reason
            and log.get("title") == title
            and log.get("detail") == detail
            and (log.get("link") or "") == (link or "")
        ):
            if matched is None:
                matched = dict(log)
            else:
                try:
                    matched["count"] = int(matched.get("count") or 1) + int(log.get("count") or 1)
                except (TypeError, ValueError):
                    matched["count"] = int(matched.get("count") or 1) + 1
            continue
        kept.append(log)
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
    observe_reasons = {"观察期首次记录", "观察期未满"}
    title = str(title or "")
    unique = str(unique or "")
    kept = []
    changed = False
    for log in logs:
        if not isinstance(log, dict):
            kept.append(log)
            continue
        reason = str(log.get("reason") or "")
        log_title = str(log.get("title") or "")
        if reason in observe_reasons and log_title in {title, unique}:
            changed = True
            continue
        kept.append(log)
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
        first_seen = item.get("first_seen") or item.get("time", "")
        if first_seen:
            try:
                first_seen_at = datetime.datetime.strptime(first_seen, "%Y-%m-%d %H:%M:%S")
                elapsed = (now - first_seen_at).days
                if elapsed < days:
                    item["first_seen"] = first_seen
                    item["observing"] = True
                    logger.info(f"豆瓣中心：条目《{item.get('title')}》观察期未满（{elapsed}/{days} 天），跳过订阅")
                    log_anti_cheat(plugin, "观察期未满", item.get("title", ""), f"已过 {elapsed} 天，需要 {days} 天")
                    return True
                logger.info(f"豆瓣中心：条目《{item.get('title') or title or unique}》观察期已满（{elapsed}/{days} 天），继续订阅")
                log_anti_cheat(plugin, "观察期完成", item.get("title") or title or unique, f"已过 {elapsed} 天，达到 {days} 天")
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
    log_anti_cheat(plugin, "观察期首次记录", title or unique, f"需要观察 {days} 天")
    return True


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
            item["observe_dropped_reason"] = "跌出当前自动订阅候选"
