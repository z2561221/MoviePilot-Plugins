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
    }
