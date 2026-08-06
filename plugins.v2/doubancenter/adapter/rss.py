"""RSS adapter for DoubanCenter rank sources."""

import json
import re
from collections import Counter
import xml.dom.minidom
from typing import Any, List
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

from app.core.config import settings
from app.log import logger
from app.utils.dom import DomUtils
from app.utils.http import RequestUtils

from .. import utils


_DOUBAN_REXXAR_MAX_ITEMS = 50
_DOUBAN_REXXAR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
    "Accept": "application/json, text/plain, */*",
}


def _channel_link(root) -> str:
    """读取 RSS channel 的来源链接，供榜单条目回到原站。"""
    channels = root.getElementsByTagName("channel")
    if not channels:
        return ""
    for node in channels[0].childNodes:
        if getattr(node, "tagName", "").lower() != "link":
            continue
        value = "".join(getattr(child, "data", "") for child in node.childNodes).strip()
        if value:
            return value
    return ""


def default_media_type(addr: str) -> str:
    """根据 RSS 地址推断默认媒体类型。"""
    text = str(addr or "").lower()
    if "movie_" in text or "/movie" in text:
        return "movie"
    if "/douban/tv" in text or "/tv_" in text or "/tv/" in text or "bangumi" in text:
        return "tv"
    return "unknown"


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


def _douban_collection_from_addr(addr: str) -> str:
    """从 RSSHub 地址提取可安全用于 rexxar 的豆瓣榜单集合 slug。"""
    path = urlsplit(str(addr or "")).path
    match = re.fullmatch(r"/douban/list/([^/?#]+)", path, flags=re.IGNORECASE)
    return unquote(match.group(1)) if match else ""


def _douban_rexxar_url(collection: str, count: int) -> str:
    """构造单次、有限数量的豆瓣 rexxar 榜单请求。"""
    return (
        "https://m.douban.com/rexxar/api/v2/subject_collection/"
        f"{quote(collection, safe='')}/items?playable=0&start=0&count={count}"
    )


def _rexxar_items(plugin, collection: str, count: int) -> List[dict]:
    """读取 rexxar 条目；网络或响应异常时返回空列表。"""
    headers = {
        **_DOUBAN_REXXAR_HEADERS,
        "Referer": f"https://m.douban.com/subject_collection/{quote(collection, safe='')}/",
    }
    try:
        request = (
            RequestUtils(headers=headers, proxies=settings.PROXY)
            if getattr(plugin, "_proxy", False)
            else RequestUtils(headers=headers)
        )
        response = request.get_res(_douban_rexxar_url(collection, count))
        if not response or getattr(response, "status_code", 200) >= 400:
            return []
        try:
            payload = response.json()
        except (AttributeError, TypeError, ValueError):
            payload = json.loads(getattr(response, "text", "") or "{}")
        if not isinstance(payload, dict):
            return []
        items = payload.get("subject_collection_items") or payload.get("items")
        return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    except Exception as err:
        warn = getattr(logger, "warning", None) or getattr(logger, "error", None)
        if warn:
            warn(f"豆瓣中心：rexxar 榜单补 ID 失败：{err}")
        return []


def _rexxar_item_title(item: Any) -> str:
    """读取 rexxar 条目标题，不用简介或集合标题猜测。"""
    if not isinstance(item, dict):
        return ""
    return str(item.get("title") or item.get("name") or "").strip()


def _rexxar_item_id(item: Any) -> str:
    """从 rexxar 的 id/uri/url 提取数字 subject id。"""
    if not isinstance(item, dict):
        return ""
    raw_id = str(item.get("id") or "").strip()
    if re.fullmatch(r"\d+", raw_id):
        return raw_id
    for key in ("uri", "url", "sharing_url"):
        value = str(item.get(key) or "")
        match = re.search(r"/(?:movie|tv|subject)/(\d+)(?:[/?#]|$)", value, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _strict_title(value: Any) -> str:
    """仅折叠空白后比较标题，保留标点以避免错绑。"""
    return re.sub(r"\s+", "", str(value or "")).casefold()


def _enrich_douban_ids(plugin, addr: str, items: List[dict]) -> None:
    """按 RSS 顺序和唯一标题严格补回豆瓣 subject id。"""
    collection = _douban_collection_from_addr(addr)
    pending = [item for item in items if isinstance(item, dict) and not item.get("doubanid")]
    if not collection or not pending:
        return
    count = min(max(len(items), 1), _DOUBAN_REXXAR_MAX_ITEMS)
    remote_items = _rexxar_items(plugin, collection, count)
    if not remote_items:
        return

    rss_counts = Counter(_strict_title(item.get("title")) for item in items if item.get("title"))
    remote_counts = Counter(_strict_title(_rexxar_item_title(item)) for item in remote_items)
    used_ids = {
        str(item.get("doubanid"))
        for item in items
        if isinstance(item, dict) and item.get("doubanid")
    }
    for index, item in enumerate(items[:count]):
        if not isinstance(item, dict) or item.get("doubanid") or index >= len(remote_items):
            continue
        rss_title = _strict_title(item.get("title"))
        remote_item = remote_items[index]
        remote_title = _strict_title(_rexxar_item_title(remote_item))
        if (
            not rss_title
            or rss_title != remote_title
            or rss_counts[rss_title] != 1
            or remote_counts[remote_title] != 1
        ):
            continue
        subject_id = _rexxar_item_id(remote_item)
        if subject_id and subject_id not in used_ids:
            item["doubanid"] = subject_id
            used_ids.add(subject_id)


def fetch_coming(plugin, addr: str) -> List[dict]:
    """拉取并解析豆瓣即将上映 RSS 条目。"""
    try:
        ret = _get_response(plugin, addr)
        if not ret:
            return []
        dom = xml.dom.minidom.parseString(ret.text)
        root = dom.documentElement
        source_link = _channel_link(root)
        result = []
        for item in root.getElementsByTagName("item"):
            title = DomUtils.tag_value(item, "title", default="")
            link = DomUtils.tag_value(item, "link", default="")
            desc = DomUtils.tag_value(item, "description", default="")
            cat = DomUtils.tag_value(item, "category", default="")
            if not title and not link:
                continue
            regions, genres = utils.parse_regions_and_genres(cat)
            region_source = "category" if regions else ""
            if not regions:
                parser = getattr(utils, "parse_regions_from_description", None)
                regions = parser(desc) if callable(parser) else []
                region_source = "description" if regions else ""
            result.append(
                {
                    "title": title,
                    "link": link,
                    "source_link": source_link,
                    "description": desc,
                    "category": cat,
                    "wish_count": utils.parse_wish_count(desc),
                    "year": utils.parse_year(cat),
                    "regions": regions,
                    "region_source": region_source,
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
        source_link = _channel_link(root)
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
            region_source = "category" if regions else ""
            if not regions:
                parser = getattr(utils, "parse_regions_from_description", None)
                regions = parser(desc) if callable(parser) else []
                region_source = "description" if regions else ""
            result.append(
                {
                    "title": title,
                    "link": link,
                    "source_link": source_link,
                    "description": desc,
                    "category": cat,
                    "mtype": mtype,
                    "doubanid": doubanid,
                    "year": year,
                    "regions": regions,
                    "region_source": region_source,
                    "genres": genres,
                }
            )
        _enrich_douban_ids(plugin, addr, result)
        return result
    except Exception as err:
        logger.error(f"获取 RSS 失败：{err}")
        return []
