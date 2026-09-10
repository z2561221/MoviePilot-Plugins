"""
DoubanCenter - 工具函数模块
"""
import datetime
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import pytz

from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.media import MetaInfo
from app.schemas.types import MediaType


LIVE_TV_MEDIA_TYPES = {
    "livetv",
    "livetvchannel",
    "livetvprogram",
    "program",
    "tvchannel",
}


def is_live_tv_media_type(media_type: Any) -> bool:
    """判断媒体服务器事件是否为明确的电视直播类型。"""
    normalized = re.sub(r"[\s_-]", "", str(media_type or "")).casefold()
    return normalized in LIVE_TV_MEDIA_TYPES


def parse_wish_count(description: str) -> int:
    """从描述文本中解析想看人数。"""
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
    """从文本中提取四位年份。"""
    if not string:
        return ""
    match = re.search(r"\b(19|20)\d{2}\b", string)
    if not match:
        return ""
    return match.group(0)


def parse_regions_and_genres(category: str) -> Tuple[List[str], List[str]]:
    """从 RSS 分类文本中解析地区与类型。"""
    if not category:
        return [], []
    parts = [p.strip() for p in category.split("/") if p.strip()]
    region_text = parts[1] if len(parts) > 1 else ""
    genre_text = parts[2] if len(parts) > 2 else ""
    regions = [x.strip() for x in re.split(r"[\s、,，]+", region_text) if x.strip()]
    genres = [x.strip() for x in re.split(r"[\s、,，]+", genre_text) if x.strip()]
    return regions, genres


_REGION_NAMES = (
    "中国大陆", "中国香港", "中国台湾", "美国", "日本", "韩国", "英国", "泰国", "印度",
    "法国", "德国", "西班牙", "加拿大", "澳大利亚", "俄罗斯", "瑞典", "丹麦", "爱尔兰",
    "意大利", "巴西", "新加坡", "马来西亚", "菲律宾", "越南", "墨西哥", "土耳其",
)


def parse_regions_from_description(description: str) -> List[str]:
    """从 RSS 描述中的地区/产地字段补提地区。"""
    text = str(description or "").strip()
    if not text:
        return []
    found: List[str] = []
    labelled = re.findall(r"(?:地区|国家|产地|制片国家/地区)\s*[：:]\s*([^\n|；;]+)", text, flags=re.IGNORECASE)
    candidates = labelled or re.split(r"\s*/\s*", text)
    for candidate in candidates:
        value = str(candidate or "").strip()
        value = re.sub(r"^(?:19|20)\d{2}\s*", "", value).strip()
        for region in _REGION_NAMES:
            if region in value or (not labelled and region in text):
                if region not in found:
                    found.append(region)
    return found


def normalize_region_values(value: Any) -> List[str]:
    """将地区字段统一为去重后的字符串列表。"""
    if isinstance(value, str):
        values = re.split(r"[\s、,，/|；;]+", value)
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = []
    result: List[str] = []
    seen = set()
    for item in values:
        if isinstance(item, dict):
            item = item.get("name") or item.get("origin_country") or item.get("iso_3166_1")
        text = str(item or "").strip()
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            result.append(text)
    return result


def match_any_filter(item_values: List[str], selected_values: List[str]) -> bool:
    """判断条目值是否命中任一已选筛选值。"""
    if not selected_values:
        return True
    return bool(set(item_values) & set(selected_values))


def normalize_rss_domain(raw_domain: str) -> str:
    """规范化 RSSHub 域名配置。"""
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
    """根据分辨率筛选项生成匹配规则。"""
    if not resolution_filters:
        return None
    if len(resolution_filters) == 1:
        return resolution_filters[0]
    return "|".join([f"(?:{item})" for item in resolution_filters if item])


def normalize_season(value: Any) -> int | None:
    """规范化明确季号，保留特别篇的第零季，拒绝小数和布尔值。"""
    if isinstance(value, bool):
        return None
    text = str(value).strip() if value is not None else ""
    return int(text) if re.fullmatch(r"[0-9]+", text) else None


def resolve_media_season(meta, *, season: Any = None, titles=()) -> int | None:
    """保留明确季号，并补齐宿主未提取的英文季标记及原始标题中的季号。"""
    for value in (season, getattr(meta, "begin_season", None)):
        if (number := normalize_season(value)) is not None:
            return number
    original = str(getattr(meta, "org_string", None) or "")
    for title in dict.fromkeys(str(value or "").strip() for value in (original, *titles)):
        if not title:
            continue
        matched = re.search(
            r"(?i)\b(?:season\s*(\d{1,3})|(\d{1,3})(?:st|nd|rd|th)\s+season)\b",
            title,
        )
        if matched:
            return int(next(value for value in matched.groups() if value is not None))
        if title != original:
            parsed = MetaInfo(title)
            if (number := normalize_season(getattr(parsed, "begin_season", None))) is not None:
                return number
    return None


def _tmdb_date_info(chain, tmdb_id: int, season: int | None = None) -> dict | None:
    """隔离日期查询失败，使季详情不可用时仍可查询整剧的季列表。"""
    try:
        info = chain.tmdb_info(tmdbid=tmdb_id, mtype=MediaType.TV, season=season)
    except Exception as err:
        target = f"第{season}季" if season is not None else "剧集"
        logger.error(f"获取TMDB{target}播出日期失败：{err}")
        return None
    return info if isinstance(info, dict) else None


def get_tmdb_air_date(
    chain, tmdb_id: int | None, season: int | None = None, *, mediainfo: Any = None,
) -> str | None:
    """优先复用已识别的目标季日期，再查询 TMDB，续季不回退到整剧首播。"""
    target_season = normalize_season(season)
    if season is not None and target_season is None:
        return None
    if date := get_media_release_date(mediainfo, season=target_season):
        return date
    if not tmdb_id:
        return None
    if target_season is not None:
        season_info = _tmdb_date_info(chain, tmdb_id, target_season)
        if season_info:
            returned_season = normalize_season(season_info.get("season_number"))
            if returned_season in (None, target_season):
                if date := _normalize_iso_date(season_info.get("air_date")):
                    return date
    tmdb_info = _tmdb_date_info(chain, tmdb_id)
    if not tmdb_info:
        return None
    if target_season is not None:
        if date := _season_air_date(tmdb_info.get("seasons"), target_season):
            return date
        if target_season != 1:
            return None
    return _normalize_iso_date(tmdb_info.get("first_air_date") or tmdb_info.get("release_date"))


def _normalize_iso_date(value: Any) -> str | None:
    """从日期或日期时间值中提取有效的 ISO 日期。"""
    match = re.search(r"\d{4}-\d{2}-\d{2}", str(value or "").strip())
    if not match:
        return None
    try:
        return datetime.date.fromisoformat(match.group(0)).isoformat()
    except ValueError:
        return None


def _season_air_date(seasons: Any, season: int) -> str | None:
    """仅提取目标季的有效首播日期，忽略缺失或损坏的季条目。"""
    if not isinstance(seasons, (list, tuple)):
        return None
    for season_info in seasons or []:
        if not isinstance(season_info, dict):
            continue
        if normalize_season(season_info.get("season_number")) != season:
            continue
        if date := _normalize_iso_date(season_info.get("air_date")):
            return date
    return None


def get_media_release_date(mediainfo: Any, season: int | None = None) -> str | None:
    """读取指定季首播日期；整剧首播日期仅能补充首季或未指定季的媒体。"""
    target_season = normalize_season(season)
    if season is not None and target_season is None:
        return None
    if target_season is not None:
        if date := _season_air_date(getattr(mediainfo, "season_info", None), target_season):
            return date
        if target_season != 1:
            return None
    for value in (
        getattr(mediainfo, "release_date", None),
        getattr(mediainfo, "first_air_date", None),
    ):
        if release_date := _normalize_iso_date(value):
            return release_date
    return None


def is_within_days(date_str: str, days: int) -> bool:
    """判断日期是否位于未来指定天数内。"""
    try:
        target = datetime.datetime.strptime(_normalize_iso_date(date_str) or "", "%Y-%m-%d").date()
        today = datetime.datetime.now(pytz.timezone(settings.TZ)).date()
        return 0 <= (target - today).days <= days
    except Exception:
        return False


def is_within_recent_days(date_str: str, days: int) -> bool:
    """判断日期是否位于最近指定天数内。"""
    try:
        target = datetime.datetime.strptime(_normalize_iso_date(date_str) or "", "%Y-%m-%d").date()
        today = datetime.datetime.now(pytz.timezone(settings.TZ)).date()
        return 0 <= (today - target).days <= days
    except Exception:
        return False


def build_douban_dispatch_link(link: str) -> str:
    """将豆瓣网页链接转换为豆瓣 App dispatch 链接。"""
    if not link:
        return ""
    match = re.search(r"/subject/(\d+)/?", link)
    if not match:
        return link
    return f"https://www.douban.com/doubanapp/dispatch?uri=/movie/{match.group(1)}?from=mdouban&open=app"


def exclude_keyword(path: str, keywords: str) -> Dict[str, Any]:
    """按路径排除关键词判断媒体是否允许同步。"""
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
    """按季号格式化剧集标题。"""
    return f"{title} 第{season_id}季" if season_id > 1 else title


def is_mobile(user_agent):
    """根据 User-Agent 判断是否为移动端访问。"""
    for kw in ['Mobile', 'Android', 'Silk/', 'Kindle', 'BlackBerry', 'Opera Mini', 'Opera Mobi', 'iPhone', 'iPad']:
        if re.search(kw, user_agent, re.IGNORECASE):
            return True
    return False
