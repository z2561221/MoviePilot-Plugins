"""豆瓣中心仪表盘总览服务。"""

from typing import Any, Callable, Dict, List

from . import archive as archive_service
from . import dashboard_stats as dashboard_stats_service
from . import dashboard_subscribe_history as subscribe_history_service
from . import observation as observation_service
from ..storage import records as storage


def overview_flows() -> List[Dict[str, List[str]]]:
    """返回总览页流程说明。"""
    return [
        {"label": "榜单订阅", "steps": ["榜单刷新", "订阅观察", "观察入池", "自动订阅", "记录写入"]},
        {"label": "归档治理", "steps": ["条目删除", "归档入库", "手动恢复", "记录清理"]},
        {"label": "同步想看", "steps": ["周期触发", "读取想看", "新增入队", "媒体识别", "创建订阅"]},
        {"label": "同步观影", "steps": ["媒体事件", "条目识别", "豆瓣同步", "写入时间"]},
    ]


def overview_rank_summary(
    builtin_ranks: List[dict],
    rank_histories: Dict[str, List[dict]],
    existing_subscription_checker: Callable[[dict], bool],
) -> Dict[str, Any]:
    """统计总览页榜单刷新和观察状态。"""
    rank_items = 0
    last_refresh = ""
    pending_observations = 0
    ignored_observations = 0

    for rank in builtin_ranks:
        rank_key = rank.get("key") if isinstance(rank, dict) else ""
        history = rank_histories.get(rank_key, [])
        if not isinstance(history, list):
            continue
        rank_items += len(history)
        for item in history:
            if not isinstance(item, dict):
                continue
            refreshed_at = item.get("rank_refreshed_at") or ""
            if refreshed_at > last_refresh:
                last_refresh = refreshed_at
            if item.get("observe_deleted"):
                ignored_observations += 1
            if (
                item.get("observing")
                and not item.get("observe_deleted")
                and not item.get("subscribed")
                and not item.get("existing")
                and not existing_subscription_checker(item)
            ):
                pending_observations += 1

    return {
        "rank_items": rank_items,
        "last_refresh": last_refresh,
        "pending_observations": pending_observations,
        "ignored_observations": ignored_observations,
    }


def build_overview(
    *,
    builtin_ranks: List[dict],
    rank_histories: Dict[str, List[dict]],
    subscribe_records: List[dict],
    anti_cheat_logs: List[dict],
    archive_records: List[dict],
    folio_data: Dict[str, dict],
    stats: Dict[str, Any],
    rank_configs: Dict[str, dict],
    enabled: bool,
    observe_days: int,
    observe_rank_keys: List[str],
    folio_enabled: bool,
    folio_user: str,
    existing_subscription_checker: Callable[[dict], bool],
    wish_enabled: bool = False,
    wish_state: Dict[str, Any] = None,
    wish_queue: List[dict] = None,
    wish_failed: List[dict] = None,
) -> Dict[str, Any]:
    """组装设置页运行总览数据。"""
    rank_summary = overview_rank_summary(builtin_ranks, rank_histories, existing_subscription_checker)
    pending_observations = rank_summary["pending_observations"]
    ignored_observations = rank_summary["ignored_observations"]
    month_new = int((stats or {}).get("month_new") or 0)
    enabled_ranks = sum(
        1
        for cfg in (rank_configs or {}).values()
        if isinstance(cfg, dict) and cfg.get("enabled")
    )
    blacklist_hits = sum(
        1
        for item in anti_cheat_logs
        if (
            isinstance(item, dict)
            and observation_service.normalize_log_reason(item.get("reason") or "") == observation_service.BLACKLIST_REASON
        )
    )
    wish_status = _wish_overview_status(
        enabled=wish_enabled,
        state=wish_state,
        queue=wish_queue,
        failed=wish_failed,
    )

    return {
        "code": 0,
        "cards": {
            "rss": {
                "enabled": enabled_ranks,
                "total": len(builtin_ranks),
                "items": rank_summary["rank_items"],
                "last_refresh": rank_summary["last_refresh"],
            },
            "subscribe": {
                "enabled": bool(enabled),
                "total": len(subscribe_records),
                "month_new": month_new,
            },
            "archive": {
                "enabled": True,
                "total": len(archive_records),
                "pending": pending_observations,
                "ignored": ignored_observations,
            },
            "observe": {
                "enabled": bool(int(observe_days or 0) > 0 and observe_rank_keys),
                "days": int(observe_days or 0),
                "pending": pending_observations,
                "ignored": ignored_observations,
            },
            "folio": {
                "enabled": bool(folio_enabled),
                "items": len(folio_data),
                "user": folio_user or "",
                "wish": wish_status,
            },
        },
        "attention": {
            "pending_observations": pending_observations,
            "subscribe_records": len(subscribe_records),
            "month_new": month_new,
            "anti_cheat_logs": len(anti_cheat_logs),
            "blacklist_hits": blacklist_hits,
            "wish_queue": wish_status["queue"],
            "wish_failed": wish_status["failed"],
        },
        "governance": {
            "archive_records": len(archive_records),
            "ignored_observations": ignored_observations,
            "anti_cheat_logs": len(anti_cheat_logs),
            "subscribe_records": len(subscribe_records),
        },
        "stats": stats or {},
        "flows": overview_flows(),
    }


def _wish_overview_status(
    *,
    enabled: bool = False,
    state: Dict[str, Any] = None,
    queue: List[dict] = None,
    failed: List[dict] = None,
) -> Dict[str, Any]:
    """组装运行总览中的豆瓣想看同步状态。"""
    state = state if isinstance(state, dict) else {}
    queue = queue if isinstance(queue, list) else []
    failed = failed if isinstance(failed, list) else []
    return {
        "enabled": bool(enabled),
        "initialized": bool(state.get("initialized")),
        "queue": len(queue),
        "failed": len(failed),
        "last_run": state.get("last_run") or "",
        "last_error": state.get("last_error") or "",
    }


def build_overview_response(
    plugin,
    *,
    builtin_ranks: List[dict],
    rank_history_reader: Callable[[object, str], List[dict]],
    existing_subscription_checker: Callable[[dict], bool],
) -> Dict[str, Any]:
    """读取并治理运行总览所需数据，然后组装总览响应。"""
    archive_service.remove_legacy_observation_completed_archives(plugin)

    subscribe_records = storage.read_subscribe_records(plugin)
    subscribe_records, changed_subscribe_records = subscribe_history_service.dedupe_records(subscribe_records)
    if changed_subscribe_records:
        storage.save_subscribe_records(plugin, subscribe_records)

    rank_histories = {}
    ranks = []
    for rank in builtin_ranks or []:
        if not isinstance(rank, dict):
            continue
        rank_key = rank.get("key") or ""
        if not rank_key:
            continue
        history = rank_history_reader(plugin, rank_key)
        rank_histories[rank_key] = history
        ranks.append({**rank, "history": history})

    anti_cheat_logs = storage.read_anti_cheat_logs(plugin)
    anti_cheat_logs, changed_anti_cheat_logs = observation_service.reconcile_anti_cheat_logs(
        anti_cheat_logs,
        subscribe_records=subscribe_records,
        ranks=ranks,
        archived_completion_titles=observation_service.archived_completion_titles(plugin),
        existing_subscription_checker=existing_subscription_checker,
    )
    if changed_anti_cheat_logs:
        storage.save_anti_cheat_logs(plugin, anti_cheat_logs)

    archive_records = storage.read_archive_records(plugin)
    archive_records, changed_archive_records = archive_service.dedupe_archive_records(archive_records)
    if changed_archive_records:
        storage.save_archive_records(plugin, archive_records)

    folio_data = storage.read_folio_data(plugin)
    wish_state = storage.read_folio_wish_state(plugin)
    wish_queue = storage.read_folio_wish_queue(plugin)
    wish_failed = storage.read_folio_wish_failed(plugin)
    stats = dashboard_stats_service.build_stats(subscribe_records, builtin_ranks)
    return build_overview(
        builtin_ranks=builtin_ranks,
        rank_histories=rank_histories,
        subscribe_records=subscribe_records,
        anti_cheat_logs=anti_cheat_logs,
        archive_records=archive_records,
        folio_data=folio_data,
        stats=stats,
        rank_configs=getattr(plugin, "_rank_configs", {}) or {},
        enabled=bool(getattr(plugin, "_enabled", False)),
        observe_days=int(getattr(plugin, "_observe_days", 0) or 0),
        observe_rank_keys=getattr(plugin, "_observe_rank_keys", []),
        folio_enabled=bool(getattr(plugin, "_folio_enabled", False)),
        folio_user=getattr(plugin, "_folio_user", "") or "",
        existing_subscription_checker=existing_subscription_checker,
        wish_enabled=bool(getattr(plugin, "_wish_enabled", False)),
        wish_state=wish_state,
        wish_queue=wish_queue,
        wish_failed=wish_failed,
    )
