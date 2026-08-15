"""DoubanCenter V3 媒体身份规范化与通用链调用适配。"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Tuple

# MoviePilot V3 e28de9cf 的 app.sdk.media 尚未导出媒体身份规范化函数。
from app.domain.media import normalize_media_source, resolve_media_identity
from app.schemas.types import MediaSource


LEGACY_ID_FIELDS = {
    MediaSource.TMDB: ("tmdb_id", "tmdbid"),
    MediaSource.Douban: ("douban_id", "doubanid"),
    MediaSource.Bangumi: ("bangumi_id", "bangumiid"),
}

CONVERSION_ID_FIELDS = {
    MediaSource.TMDB: ("tmdb_id", "tmdbid", "id"),
    MediaSource.Douban: ("douban_id", "doubanid", "id"),
    MediaSource.Bangumi: ("bangumi_id", "bangumiid", "id"),
}

CONVERSION_INFO_FIELDS = {
    MediaSource.TMDB: "tmdb_info",
    MediaSource.Douban: "douban_info",
    MediaSource.Bangumi: "bangumi_info",
}


def _source_value(source: Any) -> str:
    """返回来源的稳定传输值。"""
    return str(getattr(source, "value", source) or "").strip()


def legacy_identity(
    *,
    media_source: Any = None,
    media_id: Any = None,
    tmdb_id: Any = None,
    douban_id: Any = None,
    bangumi_id: Any = None,
) -> Tuple[Optional[MediaSource], Optional[str]]:
    """把统一身份或旧来源字段规范化为 V3 身份对。"""
    if media_source is not None or media_id is not None:
        return resolve_media_identity(media_source=media_source, media_id=media_id)

    for source, value in (
        (MediaSource.TMDB, tmdb_id),
        (MediaSource.Douban, douban_id),
        (MediaSource.Bangumi, bangumi_id),
    ):
        if value not in (None, ""):
            normalized_source = normalize_media_source(source)
            normalized_id = str(value).strip()
            if normalized_source and normalized_id and normalized_id != "0":
                return normalized_source, normalized_id
    return None, None


def _target_identity(target_source: Any, media_id: Any) -> Tuple[Optional[MediaSource], Optional[str]]:
    """校验转换结果中的目标来源 ID，并拒绝非正数 TMDB ID。"""
    target_source = normalize_media_source(target_source)
    source, resolved_id = resolve_media_identity(
        media_source=target_source,
        media_id=media_id,
    )
    if not source or not resolved_id:
        return None, None
    if source == MediaSource.TMDB:
        try:
            tmdb_id = int(resolved_id)
        except (TypeError, ValueError):
            return None, None
        if tmdb_id <= 0:
            return None, None
        resolved_id = str(tmdb_id)
    return source, resolved_id


def _conversion_identity(
    value: Any,
    target_source: Any,
) -> Tuple[Optional[MediaSource], Optional[str]]:
    """从字典、媒体对象或裸 ID 中提取转换后的目标身份。"""
    target_source = normalize_media_source(target_source)
    if not target_source or value is None:
        return None, None
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        return _target_identity(target_source, value)

    source, media_id = resolve_media_identity(media=value)
    if source == target_source and media_id:
        return _target_identity(target_source, media_id)

    for field in CONVERSION_ID_FIELDS.get(target_source, ("media_id", "id")):
        raw_id = value.get(field) if isinstance(value, Mapping) else getattr(value, field, None)
        source, media_id = _target_identity(target_source, raw_id)
        if source and media_id:
            return source, media_id

    nested_field = CONVERSION_INFO_FIELDS.get(target_source)
    if nested_field:
        nested = value.get(nested_field) if isinstance(value, Mapping) else getattr(value, nested_field, None)
        if nested is not None and nested is not value:
            return _conversion_identity(nested, target_source)
    return None, None


def _contains_cjk(value: Any) -> bool:
    """判断标题是否包含中日韩统一表意文字。"""
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", str(value or "")))


def _mapping_year(value: Mapping[str, Any]) -> str:
    """从来源详情或 TMDB 匹配结果中提取可比较年份。"""
    for field in ("year", "first_air_date", "release_date"):
        raw_value = str(value.get(field) or "").strip()
        match = re.search(r"(?:19|20)\d{2}", raw_value)
        if match:
            return match.group(0)
    return ""


def _douban_tmdb_original_title_fallback(
    chain: Any,
    *,
    media_id: str,
    mtype: Any = None,
    season: Any = None,
) -> Tuple[Optional[MediaSource], Optional[str]]:
    """用豆瓣非中文原名做一次不带年份的 TMDB 精确匹配。"""
    douban_info = getattr(chain, "douban_info", None)
    match_tmdbinfo = getattr(chain, "match_tmdbinfo", None)
    if not callable(douban_info) or not callable(match_tmdbinfo):
        return None, None

    detail_kwargs = {"doubanid": media_id}
    if mtype is not None:
        detail_kwargs["mtype"] = mtype
    source_info = douban_info(**detail_kwargs)
    if not isinstance(source_info, Mapping):
        return None, None

    source_year = _mapping_year(source_info)
    seen = set()
    for field in ("original_title", "en_title", "title"):
        title = re.sub(r"\s+", " ", str(source_info.get(field) or "")).strip()
        title_key = title.casefold()
        if (
            not title
            or title_key in seen
            or _contains_cjk(title)
            or not re.search(r"[A-Za-z]", title)
        ):
            continue
        seen.add(title_key)
        target_info = match_tmdbinfo(
            name=title,
            mtype=mtype,
            year=None,
            season=season,
        )
        if not isinstance(target_info, Mapping):
            continue
        target_year = _mapping_year(target_info)
        if source_year and target_year and source_year != target_year:
            continue
        source, target_id = _conversion_identity(target_info, MediaSource.TMDB)
        if source and target_id:
            return source, target_id
    return None, None


def convert_identity(
    chain: Any,
    *,
    target_source: Any,
    media_source: Any,
    media_id: Any,
    mtype: Any = None,
    season: Any = None,
) -> Tuple[Optional[MediaSource], Optional[str]]:
    """调用 V3 跨源转换链，并为未定档条目补受限原名匹配。"""
    target_source = normalize_media_source(target_source)
    source, resolved_id = resolve_media_identity(
        media_source=media_source,
        media_id=media_id,
    )
    if not target_source or not source or not resolved_id:
        return None, None
    if source == target_source:
        return _target_identity(target_source, resolved_id)

    converter = getattr(chain, "convert_media_identity", None)
    if not callable(converter):
        return None, None
    kwargs = {
        "target_source": target_source,
        "media_source": source,
        "media_id": resolved_id,
    }
    if mtype is not None:
        kwargs["mtype"] = mtype
    if season is not None:
        kwargs["season"] = season
    converted_identity = _conversion_identity(converter(**kwargs), target_source)
    if all(converted_identity):
        return converted_identity
    if target_source == MediaSource.TMDB and source == MediaSource.Douban:
        return _douban_tmdb_original_title_fallback(
            chain,
            media_id=resolved_id,
            mtype=mtype,
            season=season,
        )
    return None, None


def identity_from_media(media: Any) -> Tuple[Optional[MediaSource], Optional[str]]:
    """从媒体对象或记录读取主身份，并兼容旧来源字段。"""
    source, media_id = resolve_media_identity(media=media)
    if source and media_id:
        return source, media_id

    if isinstance(media, Mapping):
        return legacy_identity(
            media_source=media.get("media_source"),
            media_id=media.get("media_id"),
            tmdb_id=media.get("tmdb_id", media.get("tmdbid")),
            douban_id=media.get("douban_id", media.get("doubanid")),
            bangumi_id=media.get("bangumi_id", media.get("bangumiid")),
        )
    return legacy_identity(
        media_source=getattr(media, "media_source", None),
        media_id=getattr(media, "media_id", None),
        tmdb_id=getattr(media, "tmdb_id", None),
        douban_id=getattr(media, "douban_id", None),
        bangumi_id=getattr(media, "bangumi_id", None),
    )


def identity_payload(
    value: Any,
    *,
    media_source: Any = None,
    media_id: Any = None,
    tmdb_id: Any = None,
    douban_id: Any = None,
    bangumi_id: Any = None,
) -> dict:
    """返回包含规范化身份对的记录副本。"""
    if isinstance(value, Mapping):
        payload = dict(value)
    else:
        payload = {}
    source, resolved_id = legacy_identity(media_source=media_source, media_id=media_id)
    if not source or not resolved_id:
        source, resolved_id = identity_from_media(value)
    if not source or not resolved_id:
        source, resolved_id = legacy_identity(
            tmdb_id=tmdb_id,
            douban_id=douban_id,
            bangumi_id=bangumi_id,
        )
    if source and resolved_id:
        payload["media_source"] = _source_value(source)
        payload["media_id"] = str(resolved_id)
    return payload


def normalize_record(record: Mapping[str, Any]) -> tuple[dict, bool, bool]:
    """迁移单条历史记录，返回记录、副本是否变化及是否无法回填。"""
    original = dict(record)
    migrated = identity_payload(original)
    source, media_id = resolve_media_identity(
        media_source=migrated.get("media_source"),
        media_id=migrated.get("media_id"),
    )
    if source and media_id:
        for field in LEGACY_ID_FIELDS.get(source, ()):
            if str(migrated.get(field) or "").strip() == str(media_id):
                migrated.pop(field, None)
    changed = migrated != original
    unresolved = not (source and media_id)
    return migrated, changed, unresolved


def recognize_media(
    chain: Any,
    *,
    meta: Any = None,
    mtype: Any = None,
    media_source: Any = None,
    media_id: Any = None,
    tmdb_id: Any = None,
    douban_id: Any = None,
    bangumi_id: Any = None,
    cache: bool = True,
) -> Any:
    """通过 V3 通用媒体链执行规范化身份识别。"""
    source, resolved_id = legacy_identity(
        media_source=media_source,
        media_id=media_id,
        tmdb_id=tmdb_id,
        douban_id=douban_id,
        bangumi_id=bangumi_id,
    )
    kwargs = {"meta": meta, "cache": cache}
    if mtype is not None:
        kwargs["mtype"] = mtype
    if source and resolved_id:
        kwargs["media_source"] = source
        kwargs["media_id"] = resolved_id
    return chain.recognize_media(**kwargs)


def media_chain_kwargs(media: Any) -> dict:
    """构造 V3 订阅链所需的身份参数。"""
    source, media_id = identity_from_media(media)
    if not source or not media_id:
        return {}
    return {"media_source": source, "media_id": media_id}
