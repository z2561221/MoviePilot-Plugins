"""
DoubanCenter - 工具函数模块
"""
import datetime
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import pytz

from app.core.config import settings
from app.core.metainfo import MetaInfo
from app.log import logger
from app.schemas.types import MediaType


def parse_wish_count(description: str) -> int:
    if not description:
        return 0
    match = re.search(r"想看人数[：:]\s*([0-9,]+)", description)
    if not match:
        return 0
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return 0


def parse_year(string: str) -> str:
    if not string:
        return ""
    match = re.search(r"\b(19|20)\d{2}\b", string)
    if not match:
        return ""
    return match.group(0)


def parse_regions_and_genres(category: str) -> Tuple[List[str], List[str]]:
    if not category:
        return [], []
    parts = [p.strip() for p in category.split("/") if p.strip()]
    region_text = parts[1] if len(parts) > 1 else ""
    genre_text = parts[2] if len(parts) > 2 else ""
    regions = [x.strip() for x in re.split(r"[\s、,，]+", region_text) if x.strip()]
    genres = [x.strip() for x in re.split(r"[\s、,，]+", genre_text) if x.strip()]
    return regions, genres


def match_any_filter(item_values: List[str], selected_values: List[str]) -> bool:
    if not selected_values:
        return True
    return bool(set(item_values) & set(selected_values))


def normalize_rss_domain(raw_domain: str) -> str:
    domain = (raw_domain or "").strip()
    if not domain:
        return "https://rsshub.app"
    if "://" not in domain:
        domain = f"https://{domain}"
    parsed = urlparse(domain)
    netloc = parsed.netloc or parsed.path
    scheme = parsed.scheme or "https"
    return f"{scheme}://{netloc}".rstrip("/")


def build_resolution_rule(resolution_filters: List[str]) -> Optional[str]:
    if not resolution_filters:
        return None
    if len(resolution_filters) == 1:
        return resolution_filters[0]
    return "|".join([f"(?:{item})" for item in resolution_filters if item])


def get_tmdb_air_date(chain, tmdb_id: Optional[int], season: Optional[int] = None) -> Optional[str]:
    if not tmdb_id:
        return None
    try:
        if season:
            season_info = chain.tmdb_info(tmdbid=tmdb_id, mtype=MediaType.TV, season=season)
            if season_info:
                date = season_info.get("air_date") or season_info.get("first_air_date")
                if date:
                    return date
        tmdb_info = chain.tmdb_info(tmdbid=tmdb_id, mtype=MediaType.TV)
        if not tmdb_info:
            return None
        if season:
            for s in (tmdb_info.get("seasons") or []):
                if s.get("season_number") == season and s.get("air_date"):
                    return s.get("air_date")
        return tmdb_info.get("first_air_date") or tmdb_info.get("release_date")
    except Exception as err:
        logger.error(f"获取TMDB播出日期失败：{err}")
        return None


def is_within_days(date_str: str, days: int) -> bool:
    try:
        target = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.datetime.now(pytz.timezone(settings.TZ)).date()
        return 0 <= (target - today).days <= days
    except Exception:
        return False


def build_douban_dispatch_link(link: str) -> str:
    if not link:
        return ""
    match = re.search(r"/subject/(\d+)/?", link)
    if not match:
        return link
    return f"https://www.douban.com/doubanapp/dispatch?uri=/movie/{match.group(1)}?from=mdouban&open=app"


def exclude_keyword(path: str, keywords: str) -> Dict[str, Any]:
    if not keywords:
        return {"ret": True, "message": "空关键词"}
    if not path:
        logger.warning('媒体路径为空,不执行过滤操作')
        return {"ret": True, "message": "媒体路径为空,不执行过滤操作"}
    for k in re.split(r'[，,]', keywords):
        if k in path:
            return {"ret": False, "message": f"路径 {path} 包含 {keywords}"}
    return {"ret": True, "message": f"路径 {path} 不包含 {keywords}"}


def format_title(title: str, season_id: int) -> str:
    return f"{title} 第{season_id}季" if season_id > 1 else title


def is_mobile(user_agent):
    for kw in ['Mobile', 'Android', 'Silk/', 'Kindle', 'BlackBerry', 'Opera Mini', 'Opera Mobi', 'iPhone', 'iPad']:
        if re.search(kw, user_agent, re.IGNORECASE):
            return True
    return False