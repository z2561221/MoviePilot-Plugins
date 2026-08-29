"""Bangumi subject 到 TMDB 的统一识别辅助。"""

import re
import unicodedata
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


def _subject_meta(
    meta: Any,
    title: str,
    year: str,
    meta_cls=None,
    *,
    preserve_fallback_year: bool = True,
) -> Any:
    """使用 subject 的标题和年份构造标题识别元信息。"""
    constructor = meta_cls or type(meta)
    subject_meta = constructor(title)
    if year:
        subject_meta.year = str(year)
    elif preserve_fallback_year:
        original_year = getattr(meta, "year", None)
        if original_year:
            subject_meta.year = str(original_year)
    original_type = getattr(meta, "type", None)
    if original_type is not None:
        subject_meta.type = original_type
    return subject_meta


def _seasonal_title_candidates(meta: Any, title: str, meta_cls=None) -> list[tuple[str, int]]:
    """生成带明确季号的 BGM 基础标题候选。"""
    candidates: list[tuple[str, int]] = []
    raw_title = re.sub(r"\s+", " ", str(title or "")).strip()
    if not raw_title:
        return candidates
    candidate_meta = _subject_meta(
        meta,
        raw_title,
        "",
        meta_cls=meta_cls,
        preserve_fallback_year=False,
    )
    parsed_name = re.sub(r"\s+", " ", str(getattr(candidate_meta, "name", None) or "")).strip()
    parsed_season = getattr(candidate_meta, "begin_season", None)
    try:
        parsed_season = int(parsed_season) if parsed_season is not None else None
    except (TypeError, ValueError):
        parsed_season = None
    if parsed_name and parsed_season is not None and parsed_name.casefold() != raw_title.casefold():
        candidates.append((parsed_name, parsed_season))

    ordinal_match = re.search(
        r"(?i)(?:\s+|[-:：~～]+)(?:(\d{1,2})(?:st|nd|rd|th)\s+season|season\s*(\d{1,2})|s(\d{1,2}))\b",
        raw_title,
    )
    if ordinal_match:
        season_text = next((value for value in ordinal_match.groups() if value), "")
        season = int(season_text) if season_text.isdigit() else None
        base_title = raw_title[:ordinal_match.start()].strip(" -:：~～—")
        if base_title and season and season > 0:
            candidates.append((base_title, season))

    roman_match = re.search(
        r"([\u2160-\u216b\u2170-\u217b])(?=\s*(?:[~～:：—-]|$))",
        raw_title,
    )
    if roman_match:
        try:
            roman_season = int(unicodedata.numeric(roman_match.group(1)))
        except (TypeError, ValueError):
            roman_season = None
        if roman_season is not None:
            base_title = re.sub(
                r"\s+",
                " ",
                f"{raw_title[:roman_match.start()]}{raw_title[roman_match.end():]}",
            ).strip()
            if base_title:
                candidates.append((base_title, roman_season))
                short_title = re.split(r"\s*[~～:：—]\s*", base_title, maxsplit=1)[0].strip()
                if short_title and short_title != base_title:
                    candidates.append((short_title, roman_season))

    result: list[tuple[str, int]] = []
    seen = set()
    for candidate_title, season in candidates:
        key = (candidate_title.casefold(), season)
        if not candidate_title or key in seen:
            continue
        seen.add(key)
        result.append((candidate_title, season))
    return result


def _record_tmdb_result(
    result: Dict[str, Any],
    mediainfo: Any,
    *,
    season: Any = None,
    match_title: str = "",
) -> Dict[str, Any]:
    """把命中的 TMDB 媒体及其母剧匹配上下文写入结果。"""
    result["mediainfo"] = mediainfo
    if season not in (None, ""):
        result["season"] = int(season)
    if match_title:
        result["match_title"] = str(match_title)
    tmdb_title = str(getattr(mediainfo, "title", None) or "").strip()
    if tmdb_title:
        result["tmdb_title"] = tmdb_title
    return result


def _is_tmdb_media(mediainfo: Any) -> bool:
    """判断识别结果是否确实拥有 TMDB 主身份。"""
    source, media_id = identity_from_media(mediainfo)
    if source == MediaSource.TMDB and media_id:
        return True
    # 部分宿主媒体对象只填充 tmdb_id，尚未回填统一 media_source/media_id。
    # 只有没有其它明确来源时才接受这个兼容形态，避免把 Bangumi 身份误判成 TMDB。
    tmdb_id = getattr(mediainfo, "tmdb_id", None)
    raw_source = getattr(mediainfo, "media_source", None)
    raw_source = str(getattr(raw_source, "value", raw_source) or "").strip().lower()
    return (
        source is None
        and raw_source in ("", "tmdb", "themoviedb")
        and tmdb_id not in (None, "", 0, "0")
    )


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


def _recognize_tmdb_match(chain: Any, meta: Any, media_type: Any, value: Any) -> Any:
    """使用 TMDB 匹配结果中的明确身份读取媒体详情。"""
    matched_tmdb_id = _tmdb_id_from_match(value)
    if not matched_tmdb_id:
        return None
    try:
        mediainfo = recognize_media(
            chain,
            meta=meta,
            mtype=media_type,
            tmdb_id=matched_tmdb_id,
            cache=False,
        )
    except Exception:
        return None
    return mediainfo if _is_tmdb_media(mediainfo) else None


def _media_value(media: Any, field: str) -> Any:
    """兼容字典和媒体对象读取字段。"""
    return media.get(field) if isinstance(media, dict) else getattr(media, field, None)


def _select_tmdb_search_media(value: Any, title: str, year: str) -> Any:
    """从 TMDB 限定搜索结果中选取标题或年份吻合的媒体。"""
    candidates = value[1] if isinstance(value, tuple) and len(value) >= 2 else value
    if not isinstance(candidates, (list, tuple)):
        return None
    expected_title = str(title or "").strip().casefold()
    expected_year = str(year or "").strip()
    year_matches = []
    for candidate in candidates:
        if not _is_tmdb_media(candidate) and not _tmdb_id_from_match(candidate):
            continue
        titles = [
            _media_value(candidate, field)
            for field in ("title", "en_title", "original_title", "original_name")
        ]
        names = _media_value(candidate, "names")
        if isinstance(names, (list, tuple, set)):
            titles.extend(names)
        normalized_titles = {
            str(candidate_title).strip().casefold()
            for candidate_title in titles
            if candidate_title
        }
        if expected_title and expected_title in normalized_titles:
            return candidate
        candidate_year = str(_media_value(candidate, "year") or "").strip()
        if expected_year and candidate_year == expected_year:
            year_matches.append(candidate)
    return year_matches[0] if len(year_matches) == 1 else None


def _requested_season(value: Any) -> Optional[int]:
    """把外部季号转换为正整数。"""
    try:
        season = int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
    return season if season and season > 0 else None


def _initial_result(meta: Any, season: Any) -> Dict[str, Any]:
    """创建 Bangumi 识别结果的稳定初始结构。"""
    result: Dict[str, Any] = {
        "mediainfo": None,
        "subject": None,
        "title": str(getattr(meta, "name", None) or getattr(meta, "title", None) or ""),
        "year": str(getattr(meta, "year", None) or ""),
    }
    normalized_season = _requested_season(season)
    if normalized_season:
        result["season"] = normalized_season
    return result


def _load_subject_context(
    plugin: Any,
    bangumi_id: Any,
    result: Dict[str, Any],
    *,
    subject_fetcher: Optional[Callable[[Any, Any], Optional[dict]]],
    subject_title: Optional[Callable[..., Any]],
    subject_year: Optional[Callable[..., Any]],
) -> tuple[Optional[dict], str, str]:
    """读取 Bangumi subject 并更新标题、年份与原始标题。"""
    subject = None
    if bangumi_id not in (None, "") and callable(subject_fetcher):
        try:
            subject = subject_fetcher(plugin, bangumi_id)
        except Exception:
            subject = None
    if not isinstance(subject, dict):
        return None, result["title"], result["year"]

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
    original_title = str(subject.get("name") or "").strip()
    if original_title:
        result["original_title"] = original_title
    return subject, title, year


def _collect_seasonal_candidates(
    meta: Any,
    subject: Optional[dict],
    title: str,
    subject_meta: Any,
    requested_season: Optional[int],
    *,
    meta_cls=None,
) -> list[tuple[str, int]]:
    """从 subject 与请求标题收集去重后的母剧标题和季号。"""
    candidate_sources = []
    if isinstance(subject, dict):
        candidate_sources.extend((subject.get("name"), subject.get("name_cn")))
    candidate_sources.extend((title, getattr(meta, "title", None), getattr(meta, "name", None)))
    candidates: list[tuple[str, int]] = []
    seen = set()
    for candidate_source in candidate_sources:
        for candidate in _seasonal_title_candidates(meta, str(candidate_source or ""), meta_cls=meta_cls):
            key = (candidate[0].casefold(), candidate[1])
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    if not candidates and requested_season:
        base_title = str(getattr(subject_meta, "name", None) or title or "").strip()
        if base_title:
            candidates.append((base_title, requested_season))
    return candidates


def _recognize_direct_tmdb(
    chain: Any,
    subject_meta: Any,
    media_type: Any,
    tmdb_id: Any,
    result: Dict[str, Any],
) -> Any:
    """使用请求中的明确 TMDB ID 识别媒体。"""
    if tmdb_id in (None, ""):
        return None
    if result.get("season") not in (None, ""):
        subject_meta.begin_season = int(result["season"])
    try:
        mediainfo = recognize_media(
            chain,
            meta=subject_meta,
            mtype=media_type,
            tmdb_id=tmdb_id,
        )
    except Exception:
        return None
    return mediainfo if _is_tmdb_media(mediainfo) else None


def _recognize_with_matcher(
    chain: Any,
    meta: Any,
    subject_meta: Any,
    title: str,
    year: str,
    media_type: Any,
    seasonal_candidates: list[tuple[str, int]],
    *,
    meta_cls=None,
) -> tuple[Any, Any, str]:
    """使用宿主 match_tmdbinfo 查找明确的 TMDB 匹配。"""
    matcher = getattr(chain, "match_tmdbinfo", None)
    if not callable(matcher):
        return None, None, ""
    for candidate_title, season in seasonal_candidates:
        try:
            tmdb_match = matcher(
                name=candidate_title,
                mtype=media_type,
                year=None,
                season=season,
            )
        except Exception:
            tmdb_match = None
        season_meta = _subject_meta(
            meta,
            candidate_title,
            "",
            meta_cls=meta_cls,
            preserve_fallback_year=False,
        )
        season_meta.begin_season = season
        mediainfo = _recognize_tmdb_match(chain, season_meta, media_type, tmdb_match)
        if mediainfo:
            return mediainfo, season, candidate_title
    if seasonal_candidates:
        return None, None, ""
    try:
        tmdb_match = matcher(
            name=title,
            mtype=media_type,
            year=year or None,
            season=getattr(subject_meta, "begin_season", None),
        )
    except Exception:
        tmdb_match = None
    return _recognize_tmdb_match(chain, subject_meta, media_type, tmdb_match), None, title


def _recognize_with_search(
    chain: Any,
    title: str,
    year: str,
    seasonal_candidates: list[tuple[str, int]],
) -> tuple[Any, Any, str]:
    """使用 TMDB 限定搜索查找标题或年份唯一命中的媒体。"""
    searcher = getattr(chain, "search", None)
    if not callable(searcher):
        return None, None, ""
    search_candidates = [
        (candidate_title, "", season)
        for candidate_title, season in seasonal_candidates
    ] or [(title, year, None)]
    for candidate_title, candidate_year, season in search_candidates:
        query = " ".join(part for part in (candidate_title, candidate_year) if part).strip()
        try:
            search_result = searcher(query, media_source=MediaSource.TMDB)
        except TypeError:
            try:
                search_result = searcher(query)
            except Exception:
                search_result = None
        except Exception:
            search_result = None
        mediainfo = _select_tmdb_search_media(search_result, candidate_title, candidate_year)
        if mediainfo:
            return mediainfo, season, candidate_title
    return None, None, ""


def _fallback_meta(
    meta: Any,
    subject_meta: Any,
    seasonal_candidates: list[tuple[str, int]],
    *,
    meta_cls=None,
) -> Any:
    """生成标题识别阶段使用的最终元信息。"""
    if not seasonal_candidates:
        return subject_meta
    fallback_title, fallback_season = seasonal_candidates[0]
    fallback = _subject_meta(
        meta,
        fallback_title,
        "",
        meta_cls=meta_cls,
        preserve_fallback_year=False,
    )
    fallback.begin_season = fallback_season
    return fallback


def _recognize_fallback(chain: Any, fallback_meta: Any, media_type: Any) -> Any:
    """依次使用 recognize_by_meta 与统一识别链完成最后回退。"""
    by_meta = getattr(chain, "recognize_by_meta", None)
    if callable(by_meta):
        try:
            mediainfo = by_meta(fallback_meta, mtype=media_type)
        except TypeError:
            mediainfo = by_meta(fallback_meta)
        except Exception:
            mediainfo = None
        if _is_tmdb_media(mediainfo):
            return mediainfo
    try:
        mediainfo = recognize_media(chain, meta=fallback_meta, mtype=media_type)
    except Exception:
        return None
    return mediainfo if _is_tmdb_media(mediainfo) else None


def recognize_bangumi_tmdb(
    plugin: Any,
    chain: Any,
    meta: Any,
    *,
    bangumi_id: Any = None,
    tmdb_id: Any = None,
    season: Any = None,
    media_type: Any = None,
    subject_fetcher: Optional[Callable[[Any, Any], Optional[dict]]] = None,
    subject_title: Optional[Callable[..., Any]] = None,
    subject_year: Optional[Callable[..., Any]] = None,
    meta_cls=None,
) -> Dict[str, Any]:
    """按既有 TMDB、Bangumi 母剧标题和独立季号顺序识别媒体。"""
    result = _initial_result(meta, season)
    requested_season = _requested_season(season)
    subject, title, year = _load_subject_context(
        plugin,
        bangumi_id,
        result,
        subject_fetcher=subject_fetcher,
        subject_title=subject_title,
        subject_year=subject_year,
    )
    if not title:
        return result

    subject_meta = _subject_meta(meta, title, year, meta_cls=meta_cls)
    seasonal_candidates = _collect_seasonal_candidates(
        meta,
        subject,
        title,
        subject_meta,
        requested_season,
        meta_cls=meta_cls,
    )
    if seasonal_candidates:
        result["match_title"] = seasonal_candidates[0][0]
        result["season"] = seasonal_candidates[0][1]

    mediainfo = _recognize_direct_tmdb(chain, subject_meta, media_type, tmdb_id, result)
    if mediainfo:
        return _record_tmdb_result(
            result,
            mediainfo,
            season=result.get("season"),
            match_title=str(result.get("match_title") or ""),
        )

    mediainfo, matched_season, matched_title = _recognize_with_matcher(
        chain,
        meta,
        subject_meta,
        title,
        year,
        media_type,
        seasonal_candidates,
        meta_cls=meta_cls,
    )
    if mediainfo:
        return _record_tmdb_result(result, mediainfo, season=matched_season, match_title=matched_title)

    mediainfo, matched_season, matched_title = _recognize_with_search(
        chain,
        title,
        year,
        seasonal_candidates,
    )
    if mediainfo:
        return _record_tmdb_result(result, mediainfo, season=matched_season, match_title=matched_title)

    fallback_meta = _fallback_meta(meta, subject_meta, seasonal_candidates, meta_cls=meta_cls)
    mediainfo = _recognize_fallback(chain, fallback_meta, media_type)
    if mediainfo:
        _record_tmdb_result(
            result,
            mediainfo,
            season=result.get("season"),
            match_title=str(result.get("match_title") or title),
        )
    return result
