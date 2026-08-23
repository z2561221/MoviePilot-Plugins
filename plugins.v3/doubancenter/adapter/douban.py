"""豆瓣公开移动页适配器。"""

from __future__ import annotations

import html
import re
from typing import Any, List

from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.network import RequestUtils


_MOBILE_SUBJECT_URL = "https://m.douban.com/movie/subject/{media_id}/"
_MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 Mobile/15E148",
    "Accept": "text/html,application/xhtml+xml",
}
_ORIGINAL_TITLE_PATTERN = re.compile(
    r'<div\s+class=["\'][^"\']*\bsub-original-title\b[^"\']*["\'][^>]*>(.*?)</div>',
    flags=re.IGNORECASE | re.DOTALL,
)


def parse_mobile_original_titles(document: Any) -> List[str]:
    """从豆瓣移动详情页提取原名，保持页面顺序并去重。"""
    text = str(document or "")
    titles: List[str] = []
    seen = set()
    for match in _ORIGINAL_TITLE_PATTERN.finditer(text):
        value = re.sub(r"<[^>]+>", " ", match.group(1))
        value = re.sub(r"\s+", " ", html.unescape(value)).strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            titles.append(value)
    return titles


def fetch_mobile_original_titles(
    plugin: Any,
    media_id: Any,
    *,
    request_utils_cls=RequestUtils,
    settings_obj=settings,
) -> List[str]:
    """读取豆瓣公开移动详情页中的原名；失败时返回空列表。"""
    normalized_id = str(media_id or "").strip()
    if not normalized_id.isdigit():
        return []
    try:
        request = (
            request_utils_cls(headers=_MOBILE_HEADERS, proxies=settings_obj.PROXY)
            if getattr(plugin, "_proxy", False)
            else request_utils_cls(headers=_MOBILE_HEADERS)
        )
        response = request.get_res(_MOBILE_SUBJECT_URL.format(media_id=normalized_id))
        if not response or getattr(response, "status_code", 200) >= 400:
            return []
        content = getattr(response, "text", "") or ""
        return parse_mobile_original_titles(content)
    except Exception as err:
        logger.warning(f"豆瓣中心：读取豆瓣 {normalized_id} 移动页原名失败：{err}")
        return []
