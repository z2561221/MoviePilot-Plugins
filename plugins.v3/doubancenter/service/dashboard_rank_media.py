"""豆瓣中心榜单媒体识别服务。"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from app.schemas.types import MediaSource
from app.sdk.logging import logger

from ..adapter import douban as douban_adapter
from . import bangumi_tmdb as bangumi_tmdb_service
from ..model.identity import (
    convert_identity,
    identity_from_media,
    identity_payload,
    legacy_identity,
    recognize_media,
)


def _default_media_chain_cls():
    """按调用时环境读取 MoviePilot 媒体链类。"""
    from app.chain.media import MediaChain

    return MediaChain


def _default_meta_cls():
    """按调用时环境读取 MoviePilot 媒体元信息类。"""
    from app.sdk.media import MetaInfo

    return MetaInfo


def _default_media_type_cls():
    """按调用时环境读取 MoviePilot 媒体类型枚举。"""
    from app.schemas.types import MediaType

    return MediaType


def _rank_media_type(media_type: str, media_type_cls):
    """将前端媒体类型参数转换为 MoviePilot 媒体类型。"""
    return media_type_cls.MOVIE if media_type == "movie" else media_type_cls.TV


def _media_type_name(media_type_value, media_type_cls) -> str:
    """返回前端展示使用的中文媒体类型。"""
    return "电影" if media_type_value == media_type_cls.MOVIE else "电视剧"


def _build_meta(title: str, year: Any, media_type_value, meta_cls, season: Any = None):
    """构造 MoviePilot 媒体识别入参。"""
    meta = meta_cls(title)
    if year:
        meta.year = str(year)
    meta.type = media_type_value
    if season not in (None, ""):
        try:
            meta.begin_season = int(season)
        except (TypeError, ValueError):
            pass
    return meta


def _poster_path(mediainfo) -> str:
    """从识别结果中提取海报地址。"""
    poster_path = ""
    if hasattr(mediainfo, "poster_path"):
        poster_path = getattr(mediainfo, "poster_path") or ""
    if not poster_path and hasattr(mediainfo, "get_poster_image"):
        poster_path = mediainfo.get_poster_image() or ""
    return poster_path


def _fallback_media_data(
    *,
    media_type_name: str,
    title: str,
    year: Any,
    tmdb_id: Any = None,
    bangumi_id: Any = None,
    media_source: Any = None,
    media_id: Any = None,
    season: Any = None,
) -> Dict[str, Any]:
    """构造识别失败但存在外部 ID 时的兜底媒体对象。"""
    source, resolved_id = legacy_identity(
        media_source=media_source,
        media_id=media_id,
        tmdb_id=tmdb_id,
        bangumi_id=bangumi_id,
    )
    source_value = getattr(source, "value", source) if source else None
    resolved_id = str(resolved_id) if resolved_id else None
    if source == MediaSource.TMDB and not tmdb_id:
        tmdb_id = resolved_id
    if source == MediaSource.Bangumi and not bangumi_id:
        bangumi_id = resolved_id
    douban_id = resolved_id if source == MediaSource.Douban else None
    mediaid_prefix = source_value or ("tmdb" if tmdb_id else "bangumi")
    return {
        "title": title or "",
        "name": title or "",
        "year": year or "",
        "type": media_type_name,
        "tmdb_id": tmdb_id,
        "tmdbid": tmdb_id,
        "douban_id": douban_id,
        "doubanid": douban_id,
        "bangumi_id": bangumi_id,
        "bangumiid": bangumi_id,
        "mediaid_prefix": mediaid_prefix,
        "media_id": resolved_id,
        "media_source": source_value,
        "poster_path": "",
        "overview": "",
        "season": season,
        "source": source_value or ("themoviedb" if tmdb_id else "bangumi"),
    }


def _mediainfo_media_data(
    mediainfo,
    *,
    media_type_name: str,
    title: str,
    year: Any,
    bangumi_id: Any = None,
    media_source: Any = None,
    media_id: Any = None,
    douban_id: Any = None,
    season: Any = None,
) -> Dict[str, Any]:
    """将 MoviePilot 媒体识别结果转换为前端媒体对象。"""
    primary_source, primary_id = legacy_identity(media_source=media_source, media_id=media_id)
    resolved_tmdb_id = (
        getattr(mediainfo, "tmdb_id", None)
        or (primary_id if primary_source == MediaSource.TMDB else None)
    )
    resolved_bangumi_id = (
        getattr(mediainfo, "bangumi_id", None)
        or (primary_id if primary_source == MediaSource.Bangumi else None)
        or bangumi_id
    )
    resolved_douban_id = getattr(mediainfo, "douban_id", None) or douban_id
    payload = {
        "title": getattr(mediainfo, "title", "") or title,
        "name": getattr(mediainfo, "title", "") or title,
        "year": getattr(mediainfo, "year", "") or year or "",
        "type": media_type_name,
        "tmdb_id": resolved_tmdb_id,
        "tmdbid": resolved_tmdb_id,
        "douban_id": resolved_douban_id,
        "doubanid": resolved_douban_id,
        "bangumi_id": resolved_bangumi_id,
        "bangumiid": resolved_bangumi_id,
        "mediaid_prefix": "tmdb" if resolved_tmdb_id else ("bangumi" if resolved_bangumi_id else None),
        "media_id": resolved_tmdb_id or resolved_bangumi_id,
        "poster_path": _poster_path(mediainfo),
        "overview": getattr(mediainfo, "overview", "") or "",
        "season": season,
        "source": "themoviedb" if resolved_tmdb_id else ("bangumi" if resolved_bangumi_id else "themoviedb"),
    }
    payload.update(identity_payload(
        mediainfo,
        media_source=media_source,
        media_id=media_id,
        tmdb_id=resolved_tmdb_id,
        bangumi_id=resolved_bangumi_id,
    ))
    if payload.get("media_source"):
        payload["mediaid_prefix"] = payload["media_source"]
        payload["source"] = payload["media_source"]
        payload["media_id"] = str(payload.get("media_id") or "")
    return payload


def _subject_media_response(
    plugin,
    *,
    media_type_name: str,
    title: str,
    bangumi_id: Any,
    bangumi_subject_fetcher: Optional[Callable[[object, Any], Optional[dict]]] = None,
    bangumi_subject_converter: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """尝试用 Bangumi subject 详情生成媒体响应。"""
    if not bangumi_id or not bangumi_subject_fetcher or not bangumi_subject_converter:
        return None
    subject = bangumi_subject_fetcher(plugin, bangumi_id)
    if not subject:
        return None
    return {
        "success": True,
        "data": bangumi_subject_converter(
            subject,
            media_type_name,
            fallback_title=title,
            bangumiid=bangumi_id,
        ),
    }


@dataclass
class _RankMediaResolution:
    """保存榜单条目识别过程中的稳定输入和可变结果。"""

    plugin: Any
    title: str
    year: Any
    tmdb_id: Any
    bangumi_id: Any
    media_source: Any
    media_id: Any
    media_type_value: Any
    media_type_name: str
    media_type_cls: Any
    meta: Any
    chain: Any
    meta_cls: Any
    bangumi_subject_fetcher: Optional[Callable[[object, Any], Optional[dict]]]
    bangumi_subject_converter: Optional[Callable[..., Dict[str, Any]]]
    douban_original_title_fetcher: Optional[Callable[..., Any]]
    source: Any = None
    source_id: Any = None
    tmdb_source: Any = None
    normalized_tmdb_id: Any = None
    bangumi_identity_id: Any = None
    mediainfo: Any = None
    recognized_source: Any = None
    recognized_id: Any = None
    recognition: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_stable_identity(self) -> bool:
        """判断请求是否携带可用于稳定回退的外部身份。"""
        return bool(
            (self.source and self.source_id)
            or (self.tmdb_source and self.normalized_tmdb_id)
            or self.bangumi_identity_id
        )


def _prepare_resolution(
    plugin,
    *,
    media_type: str,
    title: str,
    year: Any,
    tmdb_id: Any,
    bangumi_id: Any,
    media_source: Any,
    media_id: Any,
    season: Any,
    media_chain_cls,
    meta_cls,
    media_type_cls,
    douban_original_title_fetcher,
    bangumi_subject_fetcher,
    bangumi_subject_converter,
) -> _RankMediaResolution:
    """规范化榜单请求并创建识别上下文。"""
    uses_default_media_chain = media_chain_cls is None
    media_chain_cls = media_chain_cls or _default_media_chain_cls()
    meta_cls = meta_cls or _default_meta_cls()
    media_type_cls = media_type_cls or _default_media_type_cls()
    media_type_value = _rank_media_type(media_type, media_type_cls=media_type_cls)
    source, source_id = legacy_identity(media_source=media_source, media_id=media_id)
    tmdb_source, normalized_tmdb_id = legacy_identity(tmdb_id=tmdb_id)
    _, normalized_bangumi_id = legacy_identity(bangumi_id=bangumi_id)
    if douban_original_title_fetcher is None and uses_default_media_chain:
        douban_original_title_fetcher = douban_adapter.fetch_mobile_original_titles
    return _RankMediaResolution(
        plugin=plugin,
        title=title,
        year=year,
        tmdb_id=tmdb_id,
        bangumi_id=bangumi_id,
        media_source=media_source,
        media_id=media_id,
        media_type_value=media_type_value,
        media_type_name=_media_type_name(media_type_value, media_type_cls=media_type_cls),
        media_type_cls=media_type_cls,
        meta=_build_meta(title, year, media_type_value, meta_cls=meta_cls, season=season),
        chain=media_chain_cls(),
        meta_cls=meta_cls,
        bangumi_subject_fetcher=bangumi_subject_fetcher,
        bangumi_subject_converter=bangumi_subject_converter,
        douban_original_title_fetcher=douban_original_title_fetcher,
        source=source,
        source_id=source_id,
        tmdb_source=tmdb_source,
        normalized_tmdb_id=normalized_tmdb_id,
        bangumi_identity_id=normalized_bangumi_id or (source_id if source == MediaSource.Bangumi else None),
    )


def _recognize_douban_mapping(state: _RankMediaResolution) -> None:
    """优先把豆瓣身份转换为 TMDB 并读取媒体详情。"""
    if state.source != MediaSource.Douban or not state.source_id:
        return
    try:
        state.recognized_source, state.recognized_id = convert_identity(
            state.chain,
            target_source=MediaSource.TMDB,
            media_source=state.source,
            media_id=state.source_id,
            mtype=state.media_type_value,
            season=getattr(state.meta, "begin_season", None),
            fallback_title_loader=(
                lambda: state.douban_original_title_fetcher(state.plugin, state.source_id)
                if callable(state.douban_original_title_fetcher)
                else []
            ),
        )
    except Exception as err:
        logger.warning(f"豆瓣中心：手动识别《{state.title}》豆瓣 ID {state.source_id} 转换 TMDB 失败：{err}")
        state.recognized_source, state.recognized_id = None, None
    if not state.recognized_source or not state.recognized_id:
        logger.info(f"豆瓣中心：手动识别《{state.title}》豆瓣 ID {state.source_id} 暂无 TMDB 映射，保留豆瓣身份")
        return
    try:
        state.mediainfo = recognize_media(
            state.chain,
            meta=state.meta,
            mtype=state.media_type_value,
            media_source=state.recognized_source,
            media_id=state.recognized_id,
        )
    except Exception as err:
        logger.warning(f"豆瓣中心：手动识别《{state.title}》TMDB ID {state.recognized_id} 失败：{err}")
        state.mediainfo = None


def _recognize_bangumi_context(state: _RankMediaResolution) -> None:
    """使用 Bangumi subject 恢复母剧标题、季号和 TMDB 身份。"""
    if state.mediainfo or not state.bangumi_identity_id:
        return
    direct_tmdb_id = state.tmdb_id or (
        state.source_id if state.source == MediaSource.TMDB else None
    )
    state.recognition = bangumi_tmdb_service.recognize_bangumi_tmdb(
        state.plugin,
        state.chain,
        state.meta,
        bangumi_id=state.bangumi_identity_id,
        tmdb_id=direct_tmdb_id,
        season=getattr(state.meta, "begin_season", None),
        media_type=state.media_type_value,
        subject_fetcher=state.bangumi_subject_fetcher,
        meta_cls=state.meta_cls,
    )
    state.mediainfo = state.recognition.get("mediainfo")
    if state.recognition.get("season") not in (None, ""):
        state.meta.begin_season = int(state.recognition["season"])
    if state.mediainfo:
        state.recognized_source, state.recognized_id = identity_from_media(state.mediainfo)


def _recognize_identity(state: _RankMediaResolution, source: Any, media_id: Any) -> bool:
    """按明确来源识别媒体，并记录实际命中的身份。"""
    if state.mediainfo or not source or not media_id:
        return False
    try:
        state.mediainfo = recognize_media(
            state.chain,
            meta=state.meta,
            mtype=state.media_type_value,
            media_source=source,
            media_id=media_id,
        )
    except (Exception, TypeError):
        state.mediainfo = None
    if not state.mediainfo:
        return False
    state.recognized_source, state.recognized_id = source, media_id
    return True


def _recognize_known_identities(state: _RankMediaResolution) -> None:
    """依次尝试请求主身份、TMDB 兼容字段和 Bangumi 身份。"""
    if state.source != MediaSource.Bangumi:
        _recognize_identity(state, state.source, state.source_id)
    _recognize_identity(state, state.tmdb_source, state.normalized_tmdb_id)
    _recognize_identity(state, MediaSource.Bangumi, state.bangumi_identity_id)


def _recognize_without_identity(state: _RankMediaResolution) -> None:
    """仅在请求没有稳定外部身份时执行标题识别。"""
    if state.mediainfo or state.has_stable_identity:
        return
    try:
        state.mediainfo = recognize_media(
            state.chain,
            meta=state.meta,
            mtype=state.media_type_value,
        )
    except Exception:
        state.mediainfo = None


def _apply_bangumi_display(data: Dict[str, Any], state: _RankMediaResolution) -> None:
    """把 Bangumi 母剧标题与匹配上下文写入前端对象。"""
    if not state.bangumi_identity_id:
        return
    display_title = str(state.recognition.get("title") or data.get("title") or state.title or "").strip()
    original_title = str(state.recognition.get("original_title") or data.get("original_title") or "").strip()
    if display_title:
        data["title"] = display_title
        data["name"] = display_title
    if original_title and original_title != display_title:
        data["original_title"] = original_title
    else:
        data.pop("original_title", None)
    resolved_source, _ = identity_from_media(state.mediainfo) if state.mediainfo is not None else (None, None)
    if resolved_source == MediaSource.TMDB:
        data["tmdb_title"] = state.recognition.get("tmdb_title") or getattr(state.mediainfo, "title", None) or ""
    if state.recognition.get("match_title"):
        data["match_title"] = state.recognition["match_title"]


def _unrecognized_response(state: _RankMediaResolution) -> Dict[str, Any]:
    """生成 subject 回退、稳定身份回退或识别失败响应。"""
    subject_response = _subject_media_response(
        state.plugin,
        media_type_name=state.media_type_name,
        title=state.title,
        bangumi_id=state.bangumi_identity_id or state.bangumi_id,
        bangumi_subject_fetcher=state.bangumi_subject_fetcher,
        bangumi_subject_converter=state.bangumi_subject_converter,
    )
    if subject_response:
        subject_data = subject_response.get("data") if isinstance(subject_response, dict) else None
        if isinstance(subject_data, dict):
            _apply_bangumi_display(subject_data, state)
            subject_data["season"] = getattr(state.meta, "begin_season", None)
        return subject_response
    if not state.has_stable_identity:
        return {"success": False, "message": "无法识别媒体信息"}
    return {
        "success": True,
        "data": _fallback_media_data(
            media_type_name=state.media_type_name,
            title=state.title,
            year=state.year,
            tmdb_id=state.tmdb_id,
            bangumi_id=state.bangumi_identity_id or state.bangumi_id,
            media_source=state.media_source,
            media_id=state.media_id,
            season=(
                getattr(state.meta, "begin_season", None)
                if state.media_type_value == state.media_type_cls.TV
                else None
            ),
        ),
    }


def _recognized_response(state: _RankMediaResolution) -> Dict[str, Any]:
    """把最终媒体识别结果转换为前端响应。"""
    data = _mediainfo_media_data(
        state.mediainfo,
        media_type_name=state.media_type_name,
        title=state.title,
        year=state.year,
        bangumi_id=state.bangumi_identity_id,
        media_source=state.recognized_source,
        media_id=state.recognized_id,
        douban_id=state.source_id if state.source == MediaSource.Douban else None,
        season=(
            getattr(state.meta, "begin_season", None)
            if state.media_type_value == state.media_type_cls.TV
            else None
        ),
    )
    _apply_bangumi_display(data, state)
    return {"success": True, "data": data}


def resolve_media_from_rank(
    plugin,
    media_type: str,
    title: str,
    year: Any,
    tmdb_id: Any = None,
    bangumi_id: Any = None,
    media_source: Any = None,
    media_id: Any = None,
    season: Any = None,
    *,
    media_chain_cls=None,
    meta_cls=None,
    media_type_cls=None,
    douban_original_title_fetcher=None,
    bangumi_subject_fetcher: Optional[Callable[[object, Any], Optional[dict]]] = None,
    bangumi_subject_converter: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """识别榜单条目并返回前端可展示的媒体信息。"""
    state = _prepare_resolution(
        plugin,
        media_type=media_type,
        title=title,
        year=year,
        tmdb_id=tmdb_id,
        bangumi_id=bangumi_id,
        media_source=media_source,
        media_id=media_id,
        season=season,
        media_chain_cls=media_chain_cls,
        meta_cls=meta_cls,
        media_type_cls=media_type_cls,
        douban_original_title_fetcher=douban_original_title_fetcher,
        bangumi_subject_fetcher=bangumi_subject_fetcher,
        bangumi_subject_converter=bangumi_subject_converter,
    )
    _recognize_douban_mapping(state)
    _recognize_bangumi_context(state)
    _recognize_known_identities(state)
    _recognize_without_identity(state)
    return _recognized_response(state) if state.mediainfo else _unrecognized_response(state)
