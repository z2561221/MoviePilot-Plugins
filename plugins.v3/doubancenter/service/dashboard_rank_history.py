"""豆瓣中心榜单历史仪表盘服务。"""

from typing import Callable, Dict, List


def build_rank_history_response(
    plugin,
    rank_items_reader: Callable[[object, str, int], List[dict]],
    limit: int = 5,
) -> Dict[str, Dict[str, List[dict]]]:
    """按仪表盘配置聚合榜单历史展示数据。"""
    rank_keys = getattr(plugin, "_dashboard_rank_keys", None) or []
    return {
        "data": {
            key: rank_items_reader(plugin, key, limit)
            for key in rank_keys
            if key
        }
    }
