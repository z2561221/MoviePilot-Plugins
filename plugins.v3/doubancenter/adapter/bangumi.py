"""豆瓣中心 BangumiTV 数据适配器。"""

import re
import time
from typing import Any, Optional

from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.network import RequestUtils


_SUBJECT_RETRY_ATTEMPTS = 3
_SUBJECT_RETRY_BASE_DELAY = 1.0
_SUBJECT_RETRY_MAX_DELAY = 8.0


def fetch_subject(plugin, bangumiid: Any, request_utils_cls=None, settings_obj=None) -> Optional[dict]:
    """通过 Bangumi subject id 获取官方条目详情。"""
    if not bangumiid:
        return None
    request_cls = request_utils_cls or RequestUtils
    config = settings_obj or settings
    url = f"https://api.bgm.tv/v0/subjects/{bangumiid}"
    headers = {"User-Agent": "MoviePilot-DoubanCenter/3.0.0"}
    for attempt in range(_SUBJECT_RETRY_ATTEMPTS):
        response = None
        try:
            request = (
                request_cls(headers=headers, proxies=config.PROXY)
                if getattr(plugin, "_proxy", False)
                else request_cls(headers=headers)
            )
            response = request.get_res(url)
            status_code = int(getattr(response, "status_code", 200) or 200) if response else 0
            if response and 200 <= status_code < 300:
                data = response.json()
                return data if isinstance(data, dict) else None

            retryable = not response or status_code == 429 or status_code >= 500
            if not retryable or attempt >= _SUBJECT_RETRY_ATTEMPTS - 1:
                logger.warning(
                    f"豆瓣中心：BangumiTV subject {bangumiid} 详情获取失败，HTTP {status_code or '无响应'}"
                )
                return None
            delay = _subject_retry_delay(response, attempt)
            logger.warning(
                f"豆瓣中心：BangumiTV subject {bangumiid} 返回 HTTP {status_code or '无响应'}，"
                f"{delay:g}s 后重试（{attempt + 1}/{_SUBJECT_RETRY_ATTEMPTS - 1}）"
            )
            time.sleep(delay)
        except Exception as err:
            if attempt >= _SUBJECT_RETRY_ATTEMPTS - 1:
                logger.warning(f"豆瓣中心：BangumiTV subject {bangumiid} 详情获取失败：{err}")
                return None
            delay = min(_SUBJECT_RETRY_BASE_DELAY * (2**attempt), _SUBJECT_RETRY_MAX_DELAY)
            logger.warning(
                f"豆瓣中心：BangumiTV subject {bangumiid} 详情获取异常，"
                f"{delay:g}s 后重试（{attempt + 1}/{_SUBJECT_RETRY_ATTEMPTS - 1}）：{err}"
            )
            time.sleep(delay)
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
    return None


def _subject_retry_delay(response: Any, attempt: int) -> float:
    """计算 Bangumi subject 重试等待时间并尊重 Retry-After。"""
    headers = getattr(response, "headers", None)
    retry_after = headers.get("Retry-After") if headers and hasattr(headers, "get") else None
    try:
        delay = float(retry_after)
    except (TypeError, ValueError):
        delay = _SUBJECT_RETRY_BASE_DELAY * (2**attempt)
    return min(max(delay, _SUBJECT_RETRY_BASE_DELAY), _SUBJECT_RETRY_MAX_DELAY)


def subject_title(subject: dict, fallback: str = "") -> str:
    """从 Bangumi subject 详情提取优先中文标题。"""
    return str((subject or {}).get("name_cn") or (subject or {}).get("name") or fallback or "")


def subject_year(subject: dict, fallback: Any = "") -> str:
    """从 Bangumi subject 详情提取年份。"""
    date_text = str((subject or {}).get("date") or "")
    match = re.search(r"\b(19|20)\d{2}\b", date_text)
    return match.group(0) if match else str(fallback or "")


def subject_poster(subject: dict) -> str:
    """从 Bangumi subject 详情提取海报地址。"""
    subject = subject or {}
    images = subject.get("images") if isinstance(subject.get("images"), dict) else {}
    return str(images.get("large") or images.get("common") or images.get("medium") or "")


def apply_subject(subject: dict, entry: dict, title: str = "", bangumiid: Any = None) -> None:
    """用 Bangumi subject 详情补全榜单条目。"""
    subject = subject or {}
    cn_title = subject_title(subject, fallback=title)
    original_title = str(subject.get("name") or title or "").strip()
    if original_title and original_title != cn_title:
        entry["original_title"] = original_title
    else:
        entry.pop("original_title", None)
    entry["title"] = cn_title or title
    entry["bangumi_title_source"] = "name_cn" if str(subject.get("name_cn") or "").strip() else "name"
    entry["year"] = subject_year(subject, fallback=entry.get("year"))
    subject_id = bangumiid or subject.get("id")
    entry["bangumi_id"] = int(subject_id) if str(subject_id or "").isdigit() else subject_id
    entry["bangumiid"] = entry["bangumi_id"]
    entry["media_source"] = "bangumi"
    entry["media_id"] = str(entry["bangumi_id"]) if entry["bangumi_id"] not in (None, "") else None
    entry["poster"] = subject_poster(subject) or entry.get("poster")


def subject_to_media_data(subject: dict, media_type_name: str, fallback_title: str = "", bangumiid: Any = None) -> dict:
    """将 Bangumi subject 详情转换为前端可展示的媒体对象。"""
    subject = subject or {}
    subject_id = bangumiid or subject.get("id")
    title = subject_title(subject, fallback=fallback_title)
    original_title = str(subject.get("name") or fallback_title or "").strip()
    result = {
        "title": title,
        "name": title,
        "year": subject_year(subject),
        "type": media_type_name,
        "tmdb_id": None,
        "tmdbid": None,
        "douban_id": None,
        "doubanid": None,
        "bangumi_id": subject_id,
        "bangumiid": subject_id,
        "mediaid_prefix": "bangumi",
        "media_id": subject_id,
        "media_source": "bangumi",
        "poster_path": subject_poster(subject),
        "overview": str(subject.get("summary") or ""),
        "season": None,
        "source": "bangumi",
        "bangumi_title_source": "name_cn" if str(subject.get("name_cn") or "").strip() else "name",
    }
    if original_title and original_title != title:
        result["original_title"] = original_title
    return result


def extract_subject_id(item: dict) -> Optional[str]:
    """从 BangumiTV 榜单条目中提取 Bangumi subject id。"""
    if not isinstance(item, dict):
        return None
    for key in ("bangumi_id", "bangumiid"):
        value = item.get(key)
        if value:
            return str(value)
    link = str(item.get("link") or "")
    match = re.search(r"(?:bgm\.tv|bangumi\.tv)/subject/(\d+)", link)
    if match:
        return match.group(1)
    if item.get("rank_key") == "bangumi" and item.get("douban_id"):
        return str(item.get("douban_id"))
    return None


def has_cjk_text(value: Any) -> bool:
    """判断文本中是否包含中日韩统一表意文字。"""
    return any("\u4e00" <= ch <= "\u9fff" for ch in str(value or ""))
