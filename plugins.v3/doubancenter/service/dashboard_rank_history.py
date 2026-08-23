"""豆瓣中心榜单历史仪表盘服务。"""

from typing import Callable, Dict, List


def _has_han_text(value: object) -> bool:
    """判断文本中是否包含汉字。"""
    return any("\u4e00" <= char <= "\u9fff" for char in str(value or ""))


def _normalize_display_item(rank_key: str, item: dict) -> dict:
    """在响应副本中纠正旧榜单记录里颠倒的中文标题。"""
    if not isinstance(item, dict):
        return item
    normalized = dict(item)
    if rank_key == "bangumi":
        return normalized
    title = str(normalized.get("title") or "").strip()
    original_title = str(normalized.get("original_title") or "").strip()
    if original_title and _has_han_text(original_title) and not _has_han_text(title):
        normalized["title"] = original_title
        if title and not normalized.get("tmdb_title"):
            normalized["tmdb_title"] = title
    return normalized


def build_rank_history_response(
    plugin,
    rank_items_reader: Callable[[object, str, int], List[dict]],
    limit: int = 5,
) -> Dict[str, Dict[str, List[dict]]]:
    """按仪表盘配置聚合榜单历史展示数据。"""
    rank_keys = getattr(plugin, "_dashboard_rank_keys", None) or []
    data = {}
    for key in rank_keys:
        if not key:
            continue
        items = rank_items_reader(plugin, key, limit)
        data[key] = [_normalize_display_item(key, item) for item in items]
    return {"data": data}
