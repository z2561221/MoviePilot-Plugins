"""豆瓣中心榜单手动订阅服务。"""

from typing import Any, Callable, Optional


def _default_media_chain_cls():
    """按调用时环境读取 MoviePilot 媒体链类。"""
    from app.chain.media import MediaChain

    return MediaChain


def _default_subscribe_chain_cls():
    """按调用时环境读取 MoviePilot 订阅链类。"""
    from app.chain.subscribe import SubscribeChain

    return SubscribeChain


def _default_meta_cls():
    """按调用时环境读取 MoviePilot 媒体元信息类。"""
    from app.core.metainfo import MetaInfo

    return MetaInfo


def _default_media_type_cls():
    """按调用时环境读取 MoviePilot 媒体类型枚举。"""
    from app.schemas.types import MediaType

    return MediaType


def rank_media_type(media_type: str, media_type_cls):
    """将前端媒体类型参数转换为手动订阅使用的媒体类型。"""
    return media_type_cls.TV if media_type == "tv" else media_type_cls.MOVIE


def build_meta(title: str, year: Any, media_type_value, meta_cls):
    """构造 MoviePilot 媒体识别元信息。"""
    meta = meta_cls(title)
    if year:
        meta.year = str(year)
    meta.type = media_type_value
    return meta


def recognize_rank_media(media_chain, meta, media_type_value, tmdb_id: Any = None, bangumi_id: Any = None):
    """按 TMDB、标题、Bangumi 顺序识别榜单媒体。"""
    mediainfo = None
    if tmdb_id:
        try:
            mediainfo = media_chain.recognize_media(meta=meta, mtype=media_type_value, tmdbid=tmdb_id)
        except TypeError:
            mediainfo = None
    if not mediainfo:
        mediainfo = media_chain.recognize_media(meta=meta, mtype=media_type_value)
    if not mediainfo and bangumi_id:
        try:
            mediainfo = media_chain.recognize_media(meta=meta, mtype=media_type_value, bangumiid=bangumi_id)
        except TypeError:
            mediainfo = None
    return mediainfo


def add_silent_subscription(subscribe_chain, title: str, year: Any, media_type_value, tmdb_id: Any = None, bangumi_id: Any = None):
    """按 MoviePilot 默认订阅参数静默添加订阅。"""
    kwargs = {
        "title": title,
        "year": year or "",
        "mtype": media_type_value,
        "tmdbid": tmdb_id,
        "season": None,
        "resolution": None,
        "sites": None,
        "exist_ok": True,
        "username": "豆瓣中心",
    }
    if bangumi_id:
        try:
            return subscribe_chain.add(**kwargs, bangumiid=bangumi_id)
        except TypeError:
            return subscribe_chain.add(**kwargs)
    return subscribe_chain.add(**kwargs)


def subscribe_from_bangumi_subject(
    plugin,
    subscribe_chain,
    media_type_value,
    title: str,
    year: Any,
    bangumi_id: Any,
    *,
    bangumi_subject_fetcher: Optional[Callable[[object, Any], Optional[dict]]] = None,
    bangumi_subject_title: Optional[Callable[..., str]] = None,
    bangumi_subject_year: Optional[Callable[..., str]] = None,
):
    """在媒体链识别失败时使用 Bangumi subject 信息添加订阅。"""
    if not bangumi_id or not bangumi_subject_fetcher or not bangumi_subject_title or not bangumi_subject_year:
        return {"success": False, "message": "无法识别媒体信息"}
    subject = bangumi_subject_fetcher(plugin, bangumi_id)
    if not subject:
        return {"success": False, "message": "无法识别媒体信息"}
    sub_title = bangumi_subject_title(subject, fallback=title)
    sub_year = bangumi_subject_year(subject, fallback=year)
    sid, msg = add_silent_subscription(
        subscribe_chain,
        sub_title,
        sub_year,
        media_type_value,
        tmdb_id=None,
        bangumi_id=bangumi_id,
    )
    if not sid:
        return {"success": False, "message": msg}
    return {"success": True, "message": "已添加订阅"}


def subscribe_from_rank(
    plugin,
    tmdb_id: Any,
    media_type: str,
    title: str,
    year: Any,
    bangumi_id: Any = None,
    *,
    media_chain_cls=None,
    subscribe_chain_cls=None,
    meta_cls=None,
    media_type_cls=None,
    bangumi_subject_fetcher: Optional[Callable[[object, Any], Optional[dict]]] = None,
    bangumi_subject_title: Optional[Callable[..., str]] = None,
    bangumi_subject_year: Optional[Callable[..., str]] = None,
):
    """根据榜单条目执行一次手动订阅。"""
    media_chain_cls = media_chain_cls or _default_media_chain_cls()
    subscribe_chain_cls = subscribe_chain_cls or _default_subscribe_chain_cls()
    meta_cls = meta_cls or _default_meta_cls()
    media_type_cls = media_type_cls or _default_media_type_cls()

    media_type_value = rank_media_type(media_type, media_type_cls)
    meta = build_meta(title, year, media_type_value, meta_cls)
    mediainfo = recognize_rank_media(
        media_chain_cls(),
        meta,
        media_type_value,
        tmdb_id=tmdb_id,
        bangumi_id=bangumi_id,
    )
    subscribe_chain = subscribe_chain_cls()
    if not mediainfo:
        return subscribe_from_bangumi_subject(
            plugin,
            subscribe_chain,
            media_type_value,
            title,
            year,
            bangumi_id,
            bangumi_subject_fetcher=bangumi_subject_fetcher,
            bangumi_subject_title=bangumi_subject_title,
            bangumi_subject_year=bangumi_subject_year,
        )

    if subscribe_chain.exists(mediainfo=mediainfo, meta=meta):
        return {"success": False, "message": "已订阅"}
    sid, msg = add_silent_subscription(
        subscribe_chain,
        getattr(mediainfo, "title", None) or title,
        getattr(mediainfo, "year", None) or year or "",
        media_type_value,
        tmdb_id=tmdb_id or getattr(mediainfo, "tmdb_id", None),
        bangumi_id=bangumi_id or getattr(mediainfo, "bangumi_id", None),
    )
    if not sid:
        return {"success": False, "message": msg}
    return {"success": True, "message": "已添加订阅"}
