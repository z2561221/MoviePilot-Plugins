"""豆瓣中心榜单媒体识别服务。"""

from typing import Any, Callable, Dict, Optional


def _default_media_chain_cls():
    """按调用时环境读取 MoviePilot 媒体链类。"""
    from app.chain.media import MediaChain

    return MediaChain


def _default_meta_cls():
    """按调用时环境读取 MoviePilot 媒体元信息类。"""
    from app.core.metainfo import MetaInfo

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


def _build_meta(title: str, year: Any, media_type_value, meta_cls):
    """构造 MoviePilot 媒体识别入参。"""
    meta = meta_cls(title)
    if year:
        meta.year = str(year)
    meta.type = media_type_value
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
    season: Any = None,
) -> Dict[str, Any]:
    """构造识别失败但存在外部 ID 时的兜底媒体对象。"""
    mediaid_prefix = "tmdb" if tmdb_id else "bangumi"
    media_id = tmdb_id or bangumi_id
    return {
        "title": title or "",
        "name": title or "",
        "year": year or "",
        "type": media_type_name,
        "tmdb_id": tmdb_id,
        "tmdbid": tmdb_id,
        "douban_id": None,
        "doubanid": None,
        "bangumi_id": bangumi_id,
        "bangumiid": bangumi_id,
        "mediaid_prefix": mediaid_prefix,
        "media_id": media_id,
        "poster_path": "",
        "overview": "",
        "season": season,
        "source": "themoviedb" if tmdb_id else "bangumi",
    }


def _mediainfo_media_data(
    mediainfo,
    *,
    media_type_name: str,
    title: str,
    year: Any,
    bangumi_id: Any = None,
    season: Any = None,
) -> Dict[str, Any]:
    """将 MoviePilot 媒体识别结果转换为前端媒体对象。"""
    resolved_tmdb_id = getattr(mediainfo, "tmdb_id", None)
    resolved_bangumi_id = getattr(mediainfo, "bangumi_id", None) or bangumi_id
    return {
        "title": getattr(mediainfo, "title", "") or title,
        "name": getattr(mediainfo, "title", "") or title,
        "year": getattr(mediainfo, "year", "") or year or "",
        "type": media_type_name,
        "tmdb_id": resolved_tmdb_id,
        "tmdbid": resolved_tmdb_id,
        "douban_id": getattr(mediainfo, "douban_id", None),
        "doubanid": getattr(mediainfo, "douban_id", None),
        "bangumi_id": resolved_bangumi_id,
        "bangumiid": resolved_bangumi_id,
        "mediaid_prefix": "tmdb" if resolved_tmdb_id else ("bangumi" if resolved_bangumi_id else None),
        "media_id": resolved_tmdb_id or resolved_bangumi_id,
        "poster_path": _poster_path(mediainfo),
        "overview": getattr(mediainfo, "overview", "") or "",
        "season": season,
        "source": "themoviedb" if resolved_tmdb_id else ("bangumi" if resolved_bangumi_id else "themoviedb"),
    }


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


def resolve_media_from_rank(
    plugin,
    media_type: str,
    title: str,
    year: Any,
    tmdb_id: Any = None,
    bangumi_id: Any = None,
    *,
    media_chain_cls=None,
    meta_cls=None,
    media_type_cls=None,
    bangumi_subject_fetcher: Optional[Callable[[object, Any], Optional[dict]]] = None,
    bangumi_subject_converter: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """识别榜单条目并返回前端可展示的媒体信息。"""
    media_chain_cls = media_chain_cls or _default_media_chain_cls()
    meta_cls = meta_cls or _default_meta_cls()
    media_type_cls = media_type_cls or _default_media_type_cls()
    media_type_value = _rank_media_type(media_type, media_type_cls=media_type_cls)
    media_type_name = _media_type_name(media_type_value, media_type_cls=media_type_cls)
    meta = _build_meta(title, year, media_type_value, meta_cls=meta_cls)

    chain = media_chain_cls()
    mediainfo = chain.recognize_media(meta=meta, mtype=media_type_value)
    if not mediainfo and bangumi_id:
        try:
            mediainfo = chain.recognize_media(meta=meta, mtype=media_type_value, bangumiid=bangumi_id)
        except TypeError:
            mediainfo = None

    if not mediainfo:
        subject_response = _subject_media_response(
            plugin,
            media_type_name=media_type_name,
            title=title,
            bangumi_id=bangumi_id,
            bangumi_subject_fetcher=bangumi_subject_fetcher,
            bangumi_subject_converter=bangumi_subject_converter,
        )
        if subject_response:
            return subject_response
        if not tmdb_id and not bangumi_id:
            return {"success": False, "message": "无法识别媒体信息"}
        return {
            "success": True,
            "data": _fallback_media_data(
                media_type_name=media_type_name,
                title=title,
                year=year,
                tmdb_id=tmdb_id,
                bangumi_id=bangumi_id,
                season=getattr(meta, "begin_season", None) if media_type_value == media_type_cls.TV else None,
            ),
        }

    return {
        "success": True,
        "data": _mediainfo_media_data(
            mediainfo,
            media_type_name=media_type_name,
            title=title,
            year=year,
            bangumi_id=bangumi_id,
            season=getattr(meta, "begin_season", None) if media_type_value == media_type_cls.TV else None,
        ),
    }
