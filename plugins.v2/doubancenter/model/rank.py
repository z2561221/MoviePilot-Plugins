"""豆瓣中心榜单定义与自定义榜单规范化。"""

from copy import deepcopy
import re
from typing import Any, Dict, List
from urllib.parse import urlsplit

DEFAULT_OBSERVE_RANK_KEYS = ["coming", "tv_real_time"]
CUSTOM_RANK_KEY_RE = re.compile(r"^custom_[^\s/?#]+$")
BUILTIN_RANKS: List[Dict[str, Any]] = [
    {
        "key": "coming",
        "name": "即将上映",
        "route": "/douban/tv/coming",
        "coming": True,
        "filters": ["vote", "wish_count"],
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
    """返回内置榜单定义副本。"""
    return deepcopy(BUILTIN_RANKS)


def normalize_custom_rank(value: Any) -> Dict[str, Any] | None:
    """规范化单个自定义榜单，非法条目返回 None。"""
    if not isinstance(value, dict):
        return None
    key = str(value.get("key") or "").strip()
    name = str(value.get("name") or "").strip()
    route = str(value.get("route") or "").strip()
    builtin_keys = {str(rank.get("key") or "") for rank in BUILTIN_RANKS}
    if not key or key in builtin_keys or not CUSTOM_RANK_KEY_RE.fullmatch(key):
        return None
    parsed_route = urlsplit(route)
    if (
        not name
        or not route
        or not route.startswith("/")
        or "#" in route
        or parsed_route.scheme
        or parsed_route.netloc
        or parsed_route.fragment
        or not parsed_route.path
    ):
        return None
    return {
        "key": key,
        "name": name,
        "route": route,
    }


def normalize_custom_ranks(values: Any) -> List[Dict[str, Any]]:
    """规范化自定义榜单列表并按 key 去重。"""
    if not isinstance(values, list):
        return []
    result: List[Dict[str, Any]] = []
    seen = set()
    for value in values:
        rank = normalize_custom_rank(value)
        if not rank or rank["key"] in seen:
            continue
        seen.add(rank["key"])
        result.append(rank)
    return result


def effective_ranks(custom_ranks: Any = None) -> List[Dict[str, Any]]:
    """返回内置榜单与合法自定义榜单组成的运行时集合。"""
    ranks = builtin_ranks()
    for custom in normalize_custom_ranks(custom_ranks):
        ranks.append(
            {
                **custom,
                "custom": True,
                "coming": False,
                "filters": ["vote", "year"],
            }
        )
    return ranks


def default_observe_rank_keys() -> List[str]:
    """返回默认启用观察期的高波动榜单 key。"""
    return list(DEFAULT_OBSERVE_RANK_KEYS)


def infer_media_type(rank: dict, item: dict) -> str:
    """根据条目字段和已知路由推断媒体类型，未知时返回 unknown。"""
    raw_type = str((item or {}).get("mtype") or (item or {}).get("media_type") or "").strip().lower()
    if raw_type in ("movie", "电影"):
        return "movie"
    if raw_type in ("tv", "电视剧", "series", "show"):
        return "tv"
    key = str((rank or {}).get("key") or "").lower()
    route = str((rank or {}).get("route") or "").lower()
    if "movie" in key or "/movie" in route:
        return "movie"
    if key in {"coming", "tv_real_time", "tv_chinese", "tv_global", "bangumi"} or "/tv/" in route or "/tv_" in route or "bangumi" in route:
        return "tv"
    return "unknown"


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
