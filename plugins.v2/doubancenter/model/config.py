"""Configuration defaults for DoubanCenter."""

from copy import deepcopy
from typing import Any, Dict, List

from .rank import default_observe_rank_keys

DEFAULT_CRON = "0 8 * * *"
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
    },
    "tv_real_time": {
        "enabled": False,
        "count": 0,
        "wish_count": 0,
        "air_days": 0,
        "vote": 0,
        "year": 0,
    },
    "tv_chinese": {
        "enabled": False,
        "count": 0,
        "wish_count": 0,
        "air_days": 0,
        "vote": 0,
        "year": 0,
    },
    "tv_global": {
        "enabled": False,
        "count": 0,
        "wish_count": 0,
        "air_days": 0,
        "vote": 0,
        "year": 0,
    },
    "movie_weekly": {
        "enabled": False,
        "count": 0,
        "wish_count": 0,
        "air_days": 0,
        "vote": 0,
        "year": 0,
    },
    "bangumi": {
        "enabled": False,
        "count": 0,
        "wish_count": 0,
        "air_days": 0,
        "vote": 0,
        "year": 0,
    },
}


def default_config() -> Dict[str, Any]:
    """Return a fresh default config dict for plugin form and cleanup."""
    return {
        "enabled": False,
        "cron": DEFAULT_CRON,
        "notify": False,
        "proxy": False,
        "onlyonce": False,
        "rsshub_domain": DEFAULT_RSSHUB_DOMAIN,
        "rank_configs": deepcopy(DEFAULT_RANK_CONFIGS),
        "region_filters": [],
        "genre_filters": [],
        "resolution_filters": [],
        "custom_rss_addrs": "",
        "folio_enabled": True,
        "folio_private": True,
        "folio_first": True,
        "folio_notify": False,
        "folio_user": "",
        "folio_exclude": "",
        "folio_cookie": "",
        "folio_pc_month": 3,
        "folio_pc_num": 50,
        "folio_mobile_month": 2,
        "folio_mobile_num": 15,
        "dashboard_rank_keys": [],
        "blacklist_keywords": "",
        "observe_days": 0,
        "observe_rank_keys": default_observe_rank_keys(),
    }
