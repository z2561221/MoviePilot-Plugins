"""Bangumi subject 到 TMDB 的统一识别辅助。"""

from typing import Any, Callable, Dict, Optional

from app.schemas.types import MediaSource

from ..adapter import bangumi as bangumi_adapter
from ..model.identity import identity_from_media, legacy_identity, recognize_media


def _subject_value(
    subject: dict,
    callback: Optional[Callable[..., Any]],
    *,
    fallback: Any,
    field: str,
) -> str:
    """从注入的适配器或默认 Bangumi 适配器读取 subject 字段。"""
    if callable(callback):
        try:
            value = callback(subject, fallback=fallback)
        except TypeError:
            value = callback(subject, fallback)
    else:
        if field == "title":
            value = bangumi_adapter.subject_title(subject, fallback=fallback)
        else:
            value = bangumi_adapter.subject_year(subject, fallback=fallback)
    return str(value or fallback or "")


def _subject_meta(meta: Any, title: str, year: str, meta_cls=None) -> Any:
    """使用 subject 的标题和年份构造标题识别元信息。"""
    constructor = meta_cls or type(meta)
    subject_meta = constructor(title)
    if year:
        subject_meta.year = str(year)
    else:
        original_year = getattr(meta, "year", None)
        if original_year:
            subject_meta.year = str(original_year)
    original_type = getattr(meta, "type", None)
    if original_type is not None:
        subject_meta.type = original_type
    return subject_meta


def _is_tmdb_media(mediainfo: Any) -> bool:
    """判断识别结果是否确实拥有 TMDB 主身份。"""
    source, media_id = identity_from_media(mediainfo)
    if source == MediaSource.TMDB and media_id:
        return True
    # 部分宿主媒体对象只填充 tmdb_id，尚未回填统一 media_source/media_id。
    # 只有没有其它明确来源时才接受这个兼容形态，避免把 Bangumi 身份误判成 TMDB。
    tmdb_id = getattr(mediainfo, "tmdb_id", None)
    return source is None and tmdb_id not in (None, "", 0, "0")


def _tmdb_id_from_match(value: Any) -> Optional[str]:
    """从宿主 TMDB 匹配结果提取有效的 TMDB ID。"""
    candidates = []
    if isinstance(value, dict):
        candidates.extend(
            value.get(field)
            for field in ("tmdb_id", "tmdbid", "id")
        )
        nested = value.get("tmdb_info")
        if isinstance(nested, dict):
            candidates.extend(
                nested.get(field)
                for field in ("tmdb_id", "tmdbid", "id")
            )
    else:
        candidates.extend(
            getattr(value, field, None)
            for field in ("tmdb_id", "tmdbid", "id")
        )
    for candidate in candidates:
        source, media_id = legacy_identity(tmdb_id=candidate)
        if source == MediaSource.TMDB and media_id:
            return media_id
    return None


def recognize_bangumi_tmdb(
    plugin: Any,
    chain: Any,
    meta: Any,
    *,
    bangumi_id: Any = None,
    tmdb_id: Any = None,
    media_type: Any = None,
    subject_fetcher: Optional[Callable[[Any, Any], Optional[dict]]] = None,
    subject_title: Optional[Callable[..., Any]] = None,
    subject_year: Optional[Callable[..., Any]] = None,
    meta_cls=None,
) -> Dict[str, Any]:
    """按既有 TMDB、Bangumi subject 标题+年份顺序识别媒体。"""
    result: Dict[str, Any] = {
        "mediainfo": None,
        "subject": None,
        "title": str(getattr(meta, "title", None) or ""),
        "year": str(getattr(meta, "year", None) or ""),
    }

    if tmdb_id not in (None, ""):
        try:
            mediainfo = recognize_media(
                chain,
                meta=meta,
                mtype=media_type,
                tmdb_id=tmdb_id,
            )
        except Exception:
            mediainfo = None
        if _is_tmdb_media(mediainfo):
            result["mediainfo"] = mediainfo
            return result

    if bangumi_id in (None, "") or not callable(subject_fetcher):
        return result
    try:
        subject = subject_fetcher(plugin, bangumi_id)
    except Exception:
        subject = None
    if not isinstance(subject, dict):
        return result

    title = _subject_value(
        subject,
        subject_title,
        fallback=result["title"],
        field="title",
    )
    year = _subject_value(
        subject,
        subject_year,
        fallback=result["year"],
        field="year",
    )
    result.update(subject=subject, title=title, year=year)
    if not title:
        return result

    subject_meta = _subject_meta(meta, title, year, meta_cls=meta_cls)
    matcher = getattr(chain, "match_tmdbinfo", None)
    if callable(matcher):
        try:
            tmdb_match = matcher(
                name=title,
                mtype=media_type,
                year=year or None,
                season=getattr(subject_meta, "begin_season", None),
            )
        except (Exception, TypeError):
            tmdb_match = None
        matched_tmdb_id = _tmdb_id_from_match(tmdb_match)
        if matched_tmdb_id:
            try:
                mediainfo = recognize_media(
                    chain,
                    meta=subject_meta,
                    mtype=media_type,
                    tmdb_id=matched_tmdb_id,
                    cache=False,
                )
            except Exception:
                mediainfo = None
            if _is_tmdb_media(mediainfo):
                result["mediainfo"] = mediainfo
                return result
    try:
        mediainfo = recognize_media(
            chain,
            meta=subject_meta,
            mtype=media_type,
            cache=False,
        )
    except Exception:
        mediainfo = None
    if _is_tmdb_media(mediainfo):
        result["mediainfo"] = mediainfo
    return result
