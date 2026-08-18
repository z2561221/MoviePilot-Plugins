"""豆瓣中心 BangumiTV 数据适配器。"""

import html
import re
import time
import xml.dom.minidom
from typing import Any, Optional

from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.network import RequestUtils


_SUBJECT_RETRY_ATTEMPTS = 3
_SUBJECT_RETRY_BASE_DELAY = 1.0
_SUBJECT_RETRY_MAX_DELAY = 8.0
_SUBJECT_REQUEST_TIMEOUT = 10


def fetch_subject(plugin, bangumiid: Any, request_utils_cls=None, settings_obj=None) -> Optional[dict]:
    """通过 Bangumi subject id 获取官方条目详情。"""
    if not bangumiid:
        return None
    request_cls = request_utils_cls or RequestUtils
    config = settings_obj or settings
    rsshub_domain = str(getattr(plugin, "_rsshub_domain", "") or "").strip().rstrip("/")
    if rsshub_domain:
        subject = _fetch_rsshub_subject(
            plugin,
            bangumiid,
            rsshub_domain=rsshub_domain,
            request_cls=request_cls,
            config=config,
        )
        if subject:
            return subject

    return _fetch_api_subject(plugin, bangumiid, request_cls=request_cls, config=config)


def _fetch_rsshub_subject(plugin, bangumiid: Any, *, rsshub_domain: str, request_cls, config) -> Optional[dict]:
    """通过已配置的 RSSHub Bangumi subject 路由读取中文名和封面。"""
    url = f"{rsshub_domain}/bangumi.tv/subject/{bangumiid}"
    headers = {"User-Agent": "MoviePilot-DoubanCenter/3.0.0"}
    response = None
    try:
        response = _request_subject(plugin, request_cls, config, headers, url)
        status_code = _response_status(response)
        if not response or not 200 <= status_code < 300:
            logger.warning(
                f"豆瓣中心：RSSHub Bangumi subject {bangumiid} 详情获取失败，"
                f"HTTP {status_code or '无响应'}，回退 BGM API"
            )
            return None
        return _parse_rsshub_subject(response, bangumiid)
    except Exception as err:
        logger.warning(f"豆瓣中心：RSSHub Bangumi subject {bangumiid} 解析失败，回退 BGM API：{err}")
        return None
    finally:
        _close_response(response)


def _fetch_api_subject(plugin, bangumiid: Any, *, request_cls, config) -> Optional[dict]:
    """从 BGM API 读取完整 subject，并对临时错误有限重试。"""
    url = f"https://api.bgm.tv/v0/subjects/{bangumiid}"
    headers = {"User-Agent": "MoviePilot-DoubanCenter/3.0.0"}
    for attempt in range(_SUBJECT_RETRY_ATTEMPTS):
        response = None
        try:
            response = _request_subject(plugin, request_cls, config, headers, url)
            status_code = _response_status(response)
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
            _close_response(response)
    return None


def _request_subject(plugin, request_cls, config, headers: dict, url: str):
    """创建带短超时的 subject 请求，避免榜单刷新被单个来源长期阻塞。"""
    kwargs = {"headers": headers, "timeout": _SUBJECT_REQUEST_TIMEOUT}
    if getattr(plugin, "_proxy", False):
        kwargs["proxies"] = config.PROXY
    return request_cls(**kwargs).get_res(url)


def _response_status(response: Any) -> int:
    """读取 HTTP 状态码，空响应统一视为 0。"""
    return int(getattr(response, "status_code", 200) or 200) if response else 0


def _close_response(response: Any) -> None:
    """释放 subject HTTP 响应。"""
    close = getattr(response, "close", None)
    if callable(close):
        close()


def _parse_rsshub_subject(response: Any, bangumiid: Any) -> Optional[dict]:
    """把 RSSHub subject RSS 转为 BGM subject 兼容字段。"""
    content = getattr(response, "text", "") or getattr(response, "content", b"")
    dom = xml.dom.minidom.parseString(content)
    channels = dom.documentElement.getElementsByTagName("channel")
    if not channels:
        return None
    channel = channels[0]
    name_cn = _direct_tag_text(channel, "title")
    if not name_cn:
        return None
    summary = _direct_tag_text(channel, "description")
    poster = ""
    items = channel.getElementsByTagName("item")
    if items:
        poster = _description_image(_direct_tag_text(items[0], "description"))
    return {
        "id": int(bangumiid) if str(bangumiid).isdigit() else bangumiid,
        "name_cn": name_cn,
        "summary": summary,
        "images": {"large": poster} if poster else {},
    }


def _direct_tag_text(parent: Any, tag_name: str) -> str:
    """读取 XML 直接子节点文本，避免误取 item 内同名标签。"""
    for node in getattr(parent, "childNodes", []):
        if getattr(node, "tagName", "") != tag_name:
            continue
        return "".join(
            str(getattr(child, "data", ""))
            for child in getattr(node, "childNodes", [])
        ).strip()
    return ""


def _description_image(description: str) -> str:
    """从 RSS 描述中的 img 标签提取并规范化封面 URL。"""
    decoded = html.unescape(str(description or ""))
    match = re.search(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", decoded, flags=re.IGNORECASE)
    if not match:
        return ""
    image_url = match.group(1).strip()
    if image_url.startswith("//"):
        return f"https:{image_url}"
    if image_url.startswith("http://lain.bgm.tv/"):
        return f"https://{image_url[len('http://'):]}"
    return image_url


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
