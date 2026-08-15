"""豆瓣时间线仪表盘服务。"""

import datetime
from typing import Callable, Dict, List, Optional

from ..storage import records as storage

TIMELINE_MONTH_LIMIT = 3
TIMELINE_ITEM_LIMIT = 50


def get_folio_data(plugin) -> dict:
    """读取豆瓣时间数据，当前插件无数据时回退到原 DoubanCenter 数据。"""
    data = storage.read_folio_data(plugin)
    if not data:
        data = storage.read_folio_data(plugin, plugin_id="DoubanCenter")
    return {"data": data}


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
    remaining_months = int(month_limit or 0) - 1
    sorted_data = sorted(
        (data or {}).items(),
        key=lambda item: datetime.datetime.strptime(item[1]["timestamp"], "%Y-%m-%d %H:%M:%S"),
    )
    for _, value in sorted_data[::-1]:
        if not isinstance(value, dict):
            continue
        poster = _resolve_poster_path(value, poster_resolver)
        if not poster:
            continue
        timestamp = datetime.datetime.strptime(value["timestamp"], "%Y-%m-%d %H:%M:%S")
        if timestamp.month != last_month or last_month is None:
            if remaining_months < 1:
                break
            if last_month:
                finish_timeline_item(current, item_limit)
                content.append(current)
                remaining_months -= 1
            current = _new_timeline_item(timestamp.month)
            last_month = timestamp.month
        if "original" not in poster:
            continue
        current["content"][0]["content"][1]["content"].append(_poster_card(value, poster, mobile=mobile))
    if current:
        finish_timeline_item(current, item_limit)
        content.append(current)
    return content


def finish_timeline_item(item: dict, limit: int) -> None:
    """补齐月份标题统计并限制该月展示条数。"""
    cards = item["content"][0]["content"][1]["content"]
    item["content"][0]["content"][0]["html"] += f"<span class='text-sm font-normal'>看过{len(cards)}部</span>"
    item["content"][0]["content"][1]["content"] = cards[:limit]


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


def _new_timeline_item(month: int) -> dict:
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
                        "html": f"{month}月 ",
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
    return {
        "component": "a",
        "props": {
            "href": (
                "https://www.douban.com/doubanapp/dispatch?"
                f"uri=/movie/{value.get('subject_id')}?from=mdouban&open=app"
            ),
            "target": "_blank",
            "style": "padding: 0.2rem",
        },
        "content": [
            {
                "component": "VCard",
                "props": {"class": "elevation-4"},
                "content": [
                    {
                        "component": "VImg",
                        "props": {
                            "src": poster.replace("/original/", "/w200/"),
                            "style": "width:44px;height:66px;" if mobile else "width:66px;height:99px;",
                            "aspect-ratio": "2/3",
                        },
                    }
                ],
            }
        ],
    }
