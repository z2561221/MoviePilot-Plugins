"""豆瓣中心榜单拉取与刷新展示服务。"""

import time
from typing import Any, Callable, Dict, List, Optional

from app.sdk.logging import logger

from .. import utils
from ..adapter import rss as rss_adapter


def dashboard_rank_sort_key(item: dict) -> tuple:
    """生成仪表盘榜单排序键。"""
    try:
        rank_index = int((item or {}).get("rank_index"))
    except (TypeError, ValueError):
        rank_index = 10 ** 9
    return rank_index, str((item or {}).get("title") or "")


def dashboard_rank_items(history: List[dict], limit: int = 5) -> List[dict]:
    """从榜单历史中返回仪表盘展示条目。"""
    records = [item for item in history if isinstance(item, dict)]
    if not records:
        return []

    latest_batch = max((str(item.get("rank_refreshed_at") or "") for item in records), default="")
    if latest_batch:
        current_items = [item for item in records if str(item.get("rank_refreshed_at") or "") == latest_batch]
        current_items.sort(key=dashboard_rank_sort_key)
        return current_items[:limit]

    return list(reversed(records[-limit:]))


def _fetch_limit(limit_by_rank: Optional[Dict[str, int]], rank_key: str) -> int:
    """返回仪表盘或运行周期需要拉取的候选数量。"""
    if not isinstance(limit_by_rank, dict) or rank_key not in limit_by_rank:
        return 5
    try:
        return max(5, int(limit_by_rank.get(rank_key) or 0))
    except (TypeError, ValueError):
        return 5


def refresh_rank_data(
    plugin: Any,
    *,
    ranks: List[dict],
    rank_enabled: Callable[[Any, str], bool],
    fetch_coming: Callable[[Any, str], List[dict]],
    fetch_general: Callable[[Any, str], List[dict]],
    merge_items: Callable[..., Any],
    dashboard_items: Callable[[Any, str, int], List[dict]],
    rank_keys=None,
    limit_by_rank: Optional[Dict[str, int]] = None,
    with_snapshots: bool = False,
) -> Any:
    """拉取目标 RSS 榜单、合并快照并返回仪表盘数据。"""
    result: Dict[str, List[dict]] = {}
    snapshots: Dict[str, dict] = {}
    try:
        rsshub = utils.normalize_rss_domain(plugin._rsshub_domain)
        targets = [
            rank
            for rank in ranks
            if (rank_keys is None and rank_enabled(plugin, rank["key"]))
            or (rank_keys and rank["key"] in rank_keys)
        ]
        for rank in targets:
            key = rank["key"]
            limit = _fetch_limit(limit_by_rank, key)
            url = rss_adapter.build_rsshub_url(rsshub, rank["route"], limit)
            logger.info(f"豆瓣中心：刷新 RSS [{rank['name']}] {url}")
            fetcher = fetch_coming if rank.get("coming") else fetch_general
            items = fetcher(plugin, url)
            if items:
                if with_snapshots:
                    _, rank_snapshots = merge_items(plugin, key, items, rank, return_snapshot=True)
                    snapshots[key] = {"rank": rank, "items": rank_snapshots}
                else:
                    merge_items(plugin, key, items, rank)
                result[key] = dashboard_items(plugin, key, limit=5)
            time.sleep(1)
        logger.info("豆瓣中心：RSS 刷新完成")
    except Exception as err:
        logger.error(f"豆瓣中心：刷新 RSS 失败：{err}", exc_info=True)
    return (result, snapshots) if with_snapshots else result
