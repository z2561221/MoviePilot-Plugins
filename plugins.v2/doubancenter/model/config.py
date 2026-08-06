"""Configuration defaults for DoubanCenter."""

from copy import deepcopy
from typing import Any, Dict, List

from .rank import default_observe_rank_keys

DEFAULT_CRON = "0 8 * * *"
DEFAULT_WISH_CRON = "*/30 * * * *"
DEFAULT_RSSHUB_DOMAIN = "https://rsshub.ddsrem.com"

REGION_OPTIONS: List[str] = [
    "中国大陆",
    "中国香港",
    "中国台湾",
    "美国",
    "日本",
    "韩国",
    "英国",
    "泰国",
    "印度",
    "法国",
    "德国",
    "西班牙",
    "加拿大",
    "澳大利亚",
    "俄罗斯",
    "瑞典",
    "丹麦",
    "爱尔兰",
    "意大利",
    "巴西",
]

GENRE_OPTIONS: List[str] = [
    "爱情",
    "喜剧",
    "剧情",
    "悬疑",
    "古装",
    "动作",
    "犯罪",
    "科幻",
    "家庭",
    "奇幻",
    "武侠",
    "历史",
    "动画",
    "惊悚",
    "战争",
    "冒险",
    "恐怖",
    "灾难",
    "传记",
    "音乐",
    "歌舞",
]

RESOLUTION_OPTIONS: List[Dict[str, str]] = [
    {"title": "2160p/4K", "value": "2160p|4k|uhd"},
    {"title": "1080p", "value": "1080p"},
    {"title": "720p", "value": "720p"},
]

DEFAULT_RANK_CONFIGS: Dict[str, Dict[str, Any]] = {
    "coming": {
        "enabled": False,
        "count": 0,
        "wish_count": 5000,
        "air_days": 7,
        "vote": 0,
        "year": 0,
        "regions": [],
    },
    "tv_real_time": {
        "enabled": False,
        "count": 0,
        "wish_count": 0,
        "air_days": 0,
        "vote": 0,
        "year": 0,
        "regions": [],
    },
    "tv_chinese": {
        "enabled": False,
        "count": 0,
        "wish_count": 0,
        "air_days": 0,
        "vote": 0,
        "year": 0,
        "regions": [],
    },
    "tv_global": {
        "enabled": False,
        "count": 0,
        "wish_count": 0,
        "air_days": 0,
        "vote": 0,
        "year": 0,
        "regions": [],
    },
    "movie_weekly": {
        "enabled": False,
        "count": 0,
        "wish_count": 0,
        "air_days": 0,
        "vote": 0,
        "year": 0,
        "regions": [],
    },
    "bangumi": {
        "enabled": False,
        "count": 0,
        "wish_count": 0,
        "air_days": 0,
        "vote": 0,
        "year": 0,
        "regions": [],
    },
}

CUSTOM_RANK_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "count": 0,
    "wish_count": 0,
    "air_days": 0,
    "vote": 0,
    "year": 0,
    "regions": [],
}


def normalize_regions(value: Any) -> List[str]:
    """规范化榜单地区条件，空列表表示不限地区。"""
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = []
    result: List[str] = []
    seen = set()
    for item in values:
        text = str(item or "").strip()
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            result.append(text)
    return result


def normalize_rank_configs(values: Any, ranks: List[dict]) -> Dict[str, Dict[str, Any]]:
    """按有效榜单集合清理并补齐榜单订阅配置。"""
    source = values if isinstance(values, dict) else {}
    result: Dict[str, Dict[str, Any]] = {}
    for rank in ranks or []:
        if not isinstance(rank, dict):
            continue
        key = str(rank.get("key") or "")
        if not key:
            continue
        defaults = DEFAULT_RANK_CONFIGS.get(key, CUSTOM_RANK_CONFIG)
        current = source.get(key)
        normalized = {
            **deepcopy(defaults),
            **(current if isinstance(current, dict) else {}),
        }
        normalized["regions"] = normalize_regions(normalized.get("regions"))
        if rank.get("custom"):
            normalized.pop("media_type", None)
        result[key] = normalized
    return result


def default_config() -> Dict[str, Any]:
    """返回插件表单和配置清理使用的默认配置。"""
    return {
        "enabled": False,
        "cron": DEFAULT_CRON,
        "notify": False,
        "proxy": False,
        "onlyonce": False,
        "rsshub_domain": DEFAULT_RSSHUB_DOMAIN,
        "rank_configs": deepcopy(DEFAULT_RANK_CONFIGS),
        "custom_ranks": [],
        "region_filters": [],
        "genre_filters": [],
        "resolution_filters": [],
        "custom_rss_addrs": "",
        "folio_enabled": True,
        "folio_private": True,
        "folio_first": True,
        "folio_notify": False,
        "folio_exclude_live_tv": True,
        "folio_user": "",
        "folio_exclude": "",
        "folio_cookie": "",
        "wish_enabled": False,
        "wish_cron": DEFAULT_WISH_CRON,
        "wish_user": "",
        "wish_notify": False,
        "wish_onlyonce": False,
        "wish_max_pages": 1,
        "wish_days": 7,
        "dashboard_rank_keys": [],
        "discovery_page_enabled": False,
        "blacklist_keywords": "",
        "observe_days": 0,
        "observe_rank_keys": default_observe_rank_keys(),
    }
