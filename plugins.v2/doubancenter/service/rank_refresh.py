"""豆瓣中心榜单刷新展示服务。"""

from typing import List


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
