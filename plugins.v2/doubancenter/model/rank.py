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
