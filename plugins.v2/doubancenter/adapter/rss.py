"""RSS adapter for DoubanCenter rank sources."""

import re
import xml.dom.minidom
from typing import List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.config import settings
from app.log import logger
from app.utils.dom import DomUtils
from app.utils.http import RequestUtils

from .. import utils


def default_media_type(addr: str) -> str:
    """根据 RSS 地址推断默认媒体类型。"""
    text = str(addr or "").lower()
    if "movie_" in text or "/movie" in text:
        return "movie"
    return "tv"


def build_rsshub_url(domain: str, route: str, limit: int = 5) -> str:
    """构造公共 RSSHub 请求地址并安全合并 limit 参数。"""
    raw_route = str(route or "").strip()
    parsed_route = urlsplit(raw_route)
    if (
        not raw_route.startswith("/")
        or "#" in raw_route
        or parsed_route.scheme
        or parsed_route.netloc
        or parsed_route.fragment
        or not parsed_route.path
    ):
        raise ValueError("RSSHub 路由必须是以 / 开头的不带主机和 fragment 的相对路径")
    try:
        normalized_limit = max(1, int(limit or 0))
    except (TypeError, ValueError):
        normalized_limit = 5
    query = [(key, value) for key, value in parse_qsl(parsed_route.query, keep_blank_values=True) if key != "limit"]
    query.append(("limit", str(normalized_limit)))
    route_url = urlunsplit(("", "", parsed_route.path, urlencode(query, doseq=True), ""))
    return f"{utils.normalize_rss_domain(domain)}{route_url}"


def _get_response(plugin, addr: str):
    return (
        RequestUtils(proxies=settings.PROXY).get_res(addr)
        if getattr(plugin, "_proxy", False)
        else RequestUtils().get_res(addr)
    )


def fetch_coming(plugin, addr: str) -> List[dict]:
    """拉取并解析豆瓣即将上映 RSS 条目。"""
    try:
        ret = _get_response(plugin, addr)
        if not ret:
            return []
        dom = xml.dom.minidom.parseString(ret.text)
        root = dom.documentElement
        result = []
        for item in root.getElementsByTagName("item"):
            title = DomUtils.tag_value(item, "title", default="")
            link = DomUtils.tag_value(item, "link", default="")
            desc = DomUtils.tag_value(item, "description", default="")
            cat = DomUtils.tag_value(item, "category", default="")
            if not title and not link:
                continue
            regions, genres = utils.parse_regions_and_genres(cat)
            result.append(
                {
                    "title": title,
                    "link": link,
                    "description": desc,
                    "category": cat,
                    "wish_count": utils.parse_wish_count(desc),
                    "year": utils.parse_year(cat),
                    "regions": regions,
                    "genres": genres,
                }
            )
        return result
    except Exception as err:
        logger.error(f"获取即将上映 RSS 失败：{err}")
        return []


def fetch_rank(plugin, addr: str) -> List[dict]:
    """拉取并解析通用榜单 RSS 条目。"""
    try:
        ret = _get_response(plugin, addr)
        if not ret:
            return []
        dom = xml.dom.minidom.parseString(ret.text)
        root = dom.documentElement
        result = []
        default_mtype = default_media_type(addr)
        for item in root.getElementsByTagName("item"):
            title = DomUtils.tag_value(item, "title", default="")
            link = DomUtils.tag_value(item, "link", default="")
            desc = DomUtils.tag_value(item, "description", default="")
            cat = DomUtils.tag_value(item, "category", default="")
            if not title:
                continue
            mtype = default_mtype
            if re.search(r"第[一二三四五六七八九十\d]+季|Season\s*\d+", title, re.IGNORECASE):
                mtype = "tv"
            doubanid = None
            if link:
                match = re.search(r"/subject/(\d+)/?", link)
                if match:
                    doubanid = match.group(1)
            year = None
            if desc:
                match = re.search(r"\b(19|20)\d{2}\b", desc)
                if match:
                    year = match.group(0)
            regions, genres = utils.parse_regions_and_genres(cat)
            result.append(
                {
                    "title": title,
                    "link": link,
                    "description": desc,
                    "category": cat,
                    "mtype": mtype,
                    "doubanid": doubanid,
                    "year": year,
                    "regions": regions,
                    "genres": genres,
                }
            )
        return result
    except Exception as err:
        logger.error(f"获取 RSS 失败：{err}")
        return []
