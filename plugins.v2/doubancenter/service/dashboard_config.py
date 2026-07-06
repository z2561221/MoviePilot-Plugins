"""豆瓣中心仪表盘配置服务。"""

from typing import Any, Callable, Dict, List


def build_config(
    *,
    builtin_ranks: List[dict],
    rank_enabled_checker: Callable[[str], bool],
    folio_pc_month: Any,
    folio_pc_num: Any,
    folio_mobile_month: Any,
    folio_mobile_num: Any,
    dashboard_rank_keys: Any,
    blacklist_keywords: Any,
    observe_days: Any,
    observe_rank_keys: Any,
    wish_enabled: Any = False,
    wish_cron: Any = "",
    wish_user: Any = "",
    wish_notify: Any = False,
    wish_onlyonce: Any = False,
    wish_max_pages: Any = 1,
    wish_days: Any = 7,
    wish_state: Dict[str, Any] = None,
    wish_queue: List[dict] = None,
    wish_processed: List[dict] = None,
    wish_failed: List[dict] = None,
) -> Dict[str, Any]:
    """组装配置页运行时补充数据。"""
    rank_options = []
    for rank in builtin_ranks:
        if not isinstance(rank, dict):
            continue
        key = rank.get("key")
        if not key or not rank_enabled_checker(str(key)):
            continue
        rank_options.append({"title": rank.get("name") or key, "value": key})

    return {
        "folio_pc_month": folio_pc_month,
        "folio_pc_num": folio_pc_num,
        "folio_mobile_month": folio_mobile_month,
        "folio_mobile_num": folio_mobile_num,
        "dashboard_rank_keys": dashboard_rank_keys if isinstance(dashboard_rank_keys, list) else [],
        "rank_options": rank_options,
        "blacklist_keywords": blacklist_keywords or "",
        "observe_days": int(observe_days or 0),
        "observe_rank_keys": observe_rank_keys if isinstance(observe_rank_keys, list) else [],
        "wish_status": _build_wish_status(
            enabled=wish_enabled,
            cron=wish_cron,
            user=wish_user,
            notify=wish_notify,
            onlyonce=wish_onlyonce,
            max_pages=wish_max_pages,
            days=wish_days,
            state=wish_state,
            queue=wish_queue,
            processed=wish_processed,
            failed=wish_failed,
        ),
    }


def _build_wish_status(
    *,
    enabled: Any = False,
    cron: Any = "",
    user: Any = "",
    notify: Any = False,
    onlyonce: Any = False,
    max_pages: Any = 1,
    days: Any = 7,
    state: Dict[str, Any] = None,
    queue: List[dict] = None,
    processed: List[dict] = None,
    failed: List[dict] = None,
) -> Dict[str, Any]:
    """组装同步想看配置页需要的运行状态。"""
    state = state if isinstance(state, dict) else {}
    queue = queue if isinstance(queue, list) else []
    processed = processed if isinstance(processed, list) else []
    failed = failed if isinstance(failed, list) else []
    try:
        normalized_pages = max(1, int(max_pages or 1))
    except (TypeError, ValueError):
        normalized_pages = 1
    try:
        normalized_days = max(0, int(days or 0))
    except (TypeError, ValueError):
        normalized_days = 7
    return {
        "enabled": bool(enabled),
        "cron": str(cron or "*/30 * * * *"),
        "user": str(user or ""),
        "notify": bool(notify),
        "onlyonce": bool(onlyonce),
        "max_pages": normalized_pages,
        "days": normalized_days,
        "initialized": bool(state.get("initialized")),
        "last_error": state.get("last_error") or "",
        "last_run": state.get("last_run") or "",
        "queue": len(queue),
        "processed": len(processed),
        "failed": len(failed),
    }
