"""豆瓣时间线仪表盘服务。"""

import datetime
from typing import Callable, Dict, List, Optional
from urllib.parse import urlencode, urlparse

from ..model.folio_record import timeline_records
from ..storage import records as storage

TIMELINE_MONTH_LIMIT = 3
TIMELINE_ITEM_LIMIT = 50


def get_folio_data(plugin, raw: bool = False) -> dict:
    """读取豆瓣时间数据，当前插件无数据时回退到原 DoubanCenter 数据。"""
    data = storage.read_folio_data(plugin)
    if not data:
        data = storage.read_folio_data(plugin, plugin_id="DoubanCenter")
    return {"data": data if raw else timeline_records(data)}


def get_timeline_items(
    plugin,
    mobile: bool = False,
    poster_resolver: Optional[Callable[[dict], Optional[str]]] = None,
) -> List[dict]:
    """按固定单排策略构建豆瓣时间线条目。"""
    data = storage.read_folio_data(plugin)
    return build_timeline_items(
        data,
        mobile=mobile,
        month_limit=TIMELINE_MONTH_LIMIT,
        item_limit=TIMELINE_ITEM_LIMIT,
        poster_resolver=poster_resolver,
    )


def build_timeline_items(
    data: Dict,
    *,
    mobile: bool = False,
    month_limit: int = 0,
    item_limit: int = 0,
    poster_resolver: Optional[Callable[[dict], Optional[str]]] = None,
) -> List[dict]:
    """根据豆瓣时间数据构建 Vuetify 时间线组件。"""
    content = []
    last_month = None
    current = None
    sorted_data = sorted(
        timeline_records(data).items(),
        key=lambda item: str(item[1]["timestamp"]),
    )
    for _, value in sorted_data[::-1]:
        if not isinstance(value, dict):
            continue
        poster = _resolve_poster_path(value, poster_resolver)
        timestamp = datetime.datetime.fromisoformat(str(value["timestamp"]))
        month = (timestamp.year, timestamp.month)
        if month != last_month:
            if current:
                finish_timeline_item(current, item_limit)
                content.append(current)
            if month_limit > 0 and len(content) >= month_limit:
                current = None
                break
            current = _new_timeline_item(timestamp.month, timestamp.year)
            last_month = month
        current["content"][0]["content"][1]["content"].append(_poster_card(value, poster or "", mobile=mobile))
    if current:
        finish_timeline_item(current, item_limit)
        content.append(current)
    return content


def finish_timeline_item(item: dict, limit: int) -> None:
    """补齐月份标题统计并限制该月展示条数。"""
    cards = item["content"][0]["content"][1]["content"]
    cards = cards[:limit] if limit > 0 else cards
    item["content"][0]["content"][0]["html"] += f"<span class='text-sm font-normal'>看过{len(cards)}部</span>"
    item["content"][0]["content"][1]["content"] = cards


def _resolve_poster_path(
    value: dict,
    poster_resolver: Optional[Callable[[dict], Optional[str]]] = None,
) -> Optional[str]:
    """返回条目海报地址，缺失时尝试通过外部解析器补齐。"""
    poster = value.get("poster_path") or ""
    if poster:
        return poster
    if not poster_resolver:
        return None
    return poster_resolver(value)


def _new_timeline_item(month: int, year: int) -> dict:
    """创建月份时间线组件骨架。"""
    return {
        "component": "VTimelineItem",
        "props": {"size": "x-small"},
        "content": [
            {
                "component": "VCol",
                "props": {"style": "padding: 0rem 0rem 0rem 0rem"},
                "content": [
                    {
                        "component": "h1",
                        "props": {
                            "style": "padding:0rem 0rem 1rem 0rem;font-weight:bold;",
                            "class": "text-base",
                        },
                        "html": f"{year}年{month}月 ",
                    },
                    {
                        "component": "VRow",
                        "props": {"style": "padding: 0rem 0rem 0rem 0rem"},
                        "content": [],
                    },
                ],
            }
        ],
    }


def _poster_card(value: dict, poster: str, *, mobile: bool = False) -> dict:
    """创建豆瓣条目海报卡片。"""
    dimensions = "width:44px;height:66px;" if mobile else "width:66px;height:99px;"
    thumbnail = poster.replace("/original/", "/w200/")
    if (urlparse(thumbnail).hostname or "").lower().endswith(".doubanio.com"):
        thumbnail = "/api/v1/system/img/0?" + urlencode({"imgurl": thumbnail, "cache": "true"})
    picture = {
        "component": "VImg",
        "props": {"src": thumbnail, "style": dimensions, "aspect-ratio": "2/3"},
    } if poster else {
        "component": "div", "props": {"style": dimensions + "display:grid;place-items:center;"},
        "content": [{"component": "VIcon", "props": {"icon": "mdi-filmstrip", "size": 18}}],
    }
    return {
        "component": "a",
        "props": {
            "href": (
                "https://www.douban.com/doubanapp/dispatch?"
                f"uri=/movie/{value.get('subject_id')}?from=mdouban&open=app"
            ),
            "target": "_blank",
            "rel": "noopener noreferrer",
            "title": value.get("display_title") or value.get("subject_name") or "",
            "style": "padding: 0.2rem",
        },
        "content": [
            {
                "component": "VCard",
                "props": {"class": "elevation-4", "style": "position:relative;"},
                "content": [picture],
            }
        ],
    }
