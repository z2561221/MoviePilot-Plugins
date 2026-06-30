"""Rank definitions for DoubanCenter."""

from copy import deepcopy
from typing import Any, Dict, List

DEFAULT_OBSERVE_RANK_KEYS = ["coming", "tv_real_time"]

BUILTIN_RANKS: List[Dict[str, Any]] = [
    {
        "key": "coming",
        "name": "即将上映",
        "route": "/douban/tv/coming",
        "coming": True,
        "filters": ["wish_count", "air_days"],
    },
    {
        "key": "tv_real_time",
        "name": "实时热门",
        "route": "/douban/list/tv_real_time_hotest",
        "coming": False,
        "filters": ["vote", "year"],
    },
    {
        "key": "tv_chinese",
        "name": "华语口碑",
        "route": "/douban/list/tv_chinese_best_weekly",
        "coming": False,
        "filters": ["vote", "year"],
    },
    {
        "key": "tv_global",
        "name": "全球口碑",
        "route": "/douban/list/tv_global_best_weekly",
        "coming": False,
        "filters": ["vote", "year"],
    },
    {
        "key": "movie_weekly",
        "name": "电影口碑",
        "route": "/douban/list/movie_weekly_best",
        "coming": False,
        "filters": ["vote", "year"],
    },
    {
        "key": "bangumi",
        "name": "BangumiTV",
        "route": "/bangumi.tv/anime/followrank",
        "coming": False,
        "filters": ["vote", "year"],
    },
]


def builtin_ranks() -> List[Dict[str, Any]]:
    """Return rank definitions as a fresh list."""
    return deepcopy(BUILTIN_RANKS)


def default_observe_rank_keys() -> List[str]:
    """Return default observe-enabled volatile rank keys."""
    return list(DEFAULT_OBSERVE_RANK_KEYS)


def infer_media_type(rank: dict, item: dict) -> str:
    """根据榜单定义和条目字段推断媒体类型。"""
    raw_type = str((item or {}).get("mtype") or "").lower()
    if raw_type in ("movie", "tv"):
        return raw_type
    key = str((rank or {}).get("key") or "").lower()
    route = str((rank or {}).get("route") or "").lower()
    if "movie" in key or "/movie" in route:
        return "movie"
    return "tv"


def record_history_item(history: List[dict], entry: dict) -> None:
    """更新或插入榜单历史条目，并移除观察占位标记。"""
    stored = dict(entry or {})
    stored.pop("observing", None)
    unique = stored.get("unique")
    if unique:
        for index, item in enumerate(history):
            if item.get("unique") == unique:
                merged = dict(item or {})
                merged.update(stored)
                merged.pop("observing", None)
                history[index] = merged
                return
    history.append(stored)


def positive_number(value: Any) -> bool:
    """判断值是否能解析为正数。"""
    try:
        return float(value or 0) > 0
    except (TypeError, ValueError):
        return False


def year_below_min(value: Any, min_year: int) -> bool:
    """判断年份是否低于最低年份筛选条件。"""
    if min_year <= 0 or value in (None, ""):
        return False
    try:
        return int(str(value)[:4]) < min_year
    except (TypeError, ValueError):
        return False
