"""豆瓣中心订阅服务。"""

import datetime
import threading
from typing import Any, Dict, List, Optional

from app.chain.subscribe import SubscribeChain
from app.sdk.logging import logger
from app.schemas.types import MediaType

from .. import utils
from ..model.identity import identity_from_media, identity_payload, legacy_identity
from ..storage import records as storage
from . import observation


_SUBSCRIBE_LOCK = threading.Lock()


def _default_subscribe_oper_cls():
    """按调用时环境读取 MoviePilot 订阅数据库操作类。"""
    from app.db.oper.subscribe import SubscribeOper

    return SubscribeOper


def _default_media_server_oper_cls():
    """按调用时环境读取 MoviePilot 媒体库数据库操作类。"""
    from app.db.mediaserver_oper import MediaServerOper

    return MediaServerOper


def history_item_subscribed(item: dict) -> bool:
    """判断历史条目是否已经产生过订阅。"""
    if not isinstance(item, dict):
        return False
    return bool(item.get("subscribed") or item.get("subscribed_at"))


def history_item_existing(item: dict) -> bool:
    """判断历史条目是否已确认存在订阅。"""
    if not isinstance(item, dict):
        return False
    return bool((item.get("existing") or item.get("existing_at")) and item.get("existing_reason") == "subscribe")


def history_index_by_unique(history: List[dict]) -> Dict[str, dict]:
    """按唯一标识构建榜单历史索引。"""
    return {
        item.get("unique"): item
        for item in history
        if isinstance(item, dict) and item.get("unique")
    }


def is_existing_identity(
    media_source: Any,
    media_id: Any,
    *,
    season: Any = None,
    episode_group: Any = None,
    subscribe_oper_cls=None,
) -> Optional[bool]:
    """检查活动与完成订阅；查询失败返回 None，不能当成不存在。"""
    source, resolved_id = legacy_identity(
        media_source=media_source,
        media_id=media_id,
    )
    if not source or not resolved_id:
        return False
    try:
        subscribe_oper_cls = subscribe_oper_cls or _default_subscribe_oper_cls()
        oper = subscribe_oper_cls()
    except Exception as err:
        logger.warning(f"豆瓣中心：初始化订阅状态检查失败：{type(err).__name__}")
        return None
    params = {
        "media_source": source,
        "media_id": resolved_id,
        "season": season,
        "episode_group": episode_group,
    }
    lookup_failed = False
    try:
        exists = getattr(oper, "exists", None)
        if callable(exists) and exists(**params):
            return True
    except Exception as err:
        lookup_failed = True
        logger.warning(f"豆瓣中心：检查活动订阅状态失败：{type(err).__name__}")
    try:
        exist_history = getattr(oper, "exist_history", None)
        if callable(exist_history) and exist_history(**params):
            return True
    except Exception as err:
        lookup_failed = True
        logger.warning(f"豆瓣中心：检查已完成订阅状态失败：{type(err).__name__}")
    return None if lookup_failed else False


def is_existing_library_media(
    mediainfo,
    meta=None,
    *,
    media_server_oper_cls=None,
) -> Optional[bool]:
    """判断媒体是否已经同步到媒体库；查询失败返回 None。"""
    try:
        media_server_oper_cls = media_server_oper_cls or _default_media_server_oper_cls()
        oper = media_server_oper_cls()
    except Exception as err:
        logger.warning(f"豆瓣中心：初始化媒体库状态检查失败：{type(err).__name__}")
        return None

    media_type = getattr(mediainfo, "type", None) or getattr(meta, "type", None)
    media_type = getattr(media_type, "value", media_type)
    season = getattr(meta, "begin_season", None) if meta else None
    media_source, media_id = identity_from_media(mediainfo)
    try:
        if media_source and media_id and oper.exists(
            media_source=media_source,
            media_id=media_id,
            mtype=media_type,
            season=season,
        ):
            return True
        title = str(getattr(mediainfo, "title", "") or "").strip()
        if title and oper.exists(
            title=title,
            mtype=media_type,
            year=getattr(mediainfo, "year", "") or "",
            season=season,
        ):
            return True
    except Exception as err:
        logger.warning(f"豆瓣中心：检查媒体库存在状态失败：{type(err).__name__}")
        return None
    return False


def is_existing_media(
    mediainfo,
    meta=None,
    subscribe_chain_cls=SubscribeChain,
    subscribe_oper_cls=None,
    media_server_oper_cls=None,
) -> Optional[bool]:
    """判断媒体是否存在订阅或已同步到媒体库。"""
    try:
        if subscribe_chain_cls().exists(mediainfo=mediainfo, meta=meta):
            return True
    except Exception as err:
        logger.warning(f"豆瓣中心：检查订阅存在状态失败：{err}")
    media_source, media_id = identity_from_media(mediainfo)
    subscription_state = is_existing_identity(
        media_source,
        media_id,
        season=getattr(meta, "begin_season", None) if meta else None,
        episode_group=getattr(mediainfo, "episode_group", None),
        subscribe_oper_cls=subscribe_oper_cls,
    )
    library_state = is_existing_library_media(
        mediainfo,
        meta,
        media_server_oper_cls=media_server_oper_cls,
    )
    if subscription_state or library_state:
        return True
    if subscription_state is None or library_state is None:
        return None
    return False


def record_existing_history(
    history: List[dict],
    unique: str,
    title: str = "",
    year: Any = "",
    link: str = "",
    mediainfo=None,
    rank_key: str = "",
    rank_name: str = "",
    media_type: str = "",
    season: Any = None,
    prefer_title: bool = False,
) -> None:
    """记录已存在订阅，避免后续再次进入观察队列。"""
    existing_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "title": (title if prefer_title else None) or getattr(mediainfo, "title", None) or title or unique,
        "year": getattr(mediainfo, "year", None) or year or "",
        "link": link,
        "tmdbid": getattr(mediainfo, "tmdb_id", ""),
        "time": existing_at,
        "unique": unique,
        "existing": True,
        "existing_at": existing_at,
        "existing_reason": "subscribe",
    }
    entry.update(identity_payload(mediainfo))
    try:
        entry["poster"] = mediainfo.get_poster_image() if mediainfo else ""
    except Exception:
        entry["poster"] = ""
    if rank_key:
        entry["rank_key"] = rank_key
    if rank_name:
        entry["rank_name"] = rank_name
    if media_type:
        entry["media_type"] = media_type
    if season not in (None, ""):
        entry["season"] = int(season)
    for index, item in enumerate(history):
        if isinstance(item, dict) and item.get("unique") == unique:
            merged = dict(item)
            merged.update(entry)
            history[index] = merged
            return
    history.append(entry)


def write_subscribe_record(
    plugin,
    mediainfo=None,
    rank_key: str = "",
    rank_name: str = "",
    status: str = "success",
    reason: str = "",
    source_link: str = "",
    *,
    title: str = "",
    year: Any = "",
    media_type=None,
    tmdb_id: Any = None,
    poster: str = "",
    bangumi_id: Any = None,
    media_source: Any = None,
    media_id: Any = None,
    season: Any = None,
    prefer_title: bool = False,
) -> None:
    """写入自动或榜单手动订阅历史记录。"""
    resolved_title = (title if prefer_title else None) or getattr(mediainfo, "title", None) or title
    resolved_year = getattr(mediainfo, "year", None) or year or ""
    resolved_tmdb_id = getattr(mediainfo, "tmdb_id", None) if mediainfo else tmdb_id
    resolved_type = getattr(mediainfo, "type", None) if mediainfo else media_type
    if not poster and mediainfo:
        try:
            poster = mediainfo.get_poster_image() or ""
        except Exception:
            poster = ""
    media_label = "电影" if resolved_type == MediaType.MOVIE or str(resolved_type).lower() == "movie" else "电视剧"
    subs = storage.read_subscribe_records(plugin)
    record = {
        "title": resolved_title,
        "year": resolved_year,
        "tmdbid": resolved_tmdb_id,
        "poster": poster or "",
        "media_type": media_label,
        "rank_key": rank_key,
        "rank_name": rank_name,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "reason": reason,
        "link": source_link or "",
    }
    if season not in (None, ""):
        record["season"] = int(season)
    resolved_source, resolved_id = identity_from_media(mediainfo) if mediainfo else legacy_identity(
        media_source=media_source,
        media_id=media_id,
        tmdb_id=tmdb_id,
        bangumi_id=bangumi_id,
    )
    if resolved_source and resolved_id:
        record["media_source"] = resolved_source.value
        record["media_id"] = resolved_id
    if bangumi_id not in (None, ""):
        record["bangumiid"] = bangumi_id
    record_key = (
        str(status or ""),
        str(record.get("media_source") or ""),
        str(record.get("media_id") or ""),
        str(resolved_title or ""),
        str(resolved_year or ""),
        str(rank_key or ""),
        str(record.get("season") or ""),
    )
    kept = []
    for item in subs:
        if not isinstance(item, dict):
            kept.append(item)
            continue
        item_key = (
            str(item.get("status") or "success"),
            str(item.get("media_source") or ""),
            str(item.get("media_id") or ""),
            str(item.get("title") or ""),
            str(item.get("year") or ""),
            str(item.get("rank_key") or ""),
            str(item.get("season") or ""),
        )
        if item_key == record_key:
            continue
        kept.append(item)
    kept.append(record)
    storage.save_subscribe_records(plugin, kept)


def add_subscription(
    plugin,
    mediainfo,
    meta=None,
    rank_key: str = "",
    rank_name: str = "",
    source_link: str = "",
    record_title: str = "",
    subscribe_chain_cls=SubscribeChain,
    subscribe_oper_cls=None,
    media_server_oper_cls=None,
) -> bool:
    """按 MoviePilot V3 通用媒体身份执行自动订阅。"""
    if meta is not None:
        meta.begin_season = utils.resolve_media_season(meta, titles=(record_title,))
    # 订阅链本身是先查后建，锁住整个区段以防并发榜单任务重复创建同一媒体。
    with _SUBSCRIBE_LOCK:
        existing_state = is_existing_media(
            mediainfo,
            meta,
            subscribe_chain_cls=subscribe_chain_cls,
            subscribe_oper_cls=subscribe_oper_cls,
            media_server_oper_cls=media_server_oper_cls,
        )
        if existing_state is None:
            write_subscribe_record(
                plugin, mediainfo, rank_key=rank_key, rank_name=rank_name,
                status="failed", reason="订阅状态检查失败，未提交订阅",
                source_link=source_link, title=record_title,
                season=getattr(meta, "begin_season", None) if meta else None,
                prefer_title=bool(record_title),
            )
            return False
        if existing_state:
            observation.cleanup_observe_logs(plugin, title=getattr(mediainfo, "title", ""))
            return False
        subscribe_chain = subscribe_chain_cls()
        season = getattr(meta, "begin_season", None) if meta else None
        media_source, media_id = identity_from_media(mediainfo)
        if not media_source or not media_id:
            write_subscribe_record(
                plugin,
                mediainfo,
                rank_key=rank_key,
                rank_name=rank_name,
                status="failed",
                reason="缺少有效媒体身份",
                source_link=source_link,
                title=record_title,
                season=season,
                prefer_title=bool(record_title),
            )
            return False
        sid, msg = subscribe_chain.add(
            title=mediainfo.title,
            year=mediainfo.year or "",
            mtype=mediainfo.type if mediainfo.type else MediaType.TV,
            media_source=media_source,
            media_id=media_id,
            season=season,
            resolution=None,
            sites=None,
            exist_ok=True,
            username="豆瓣中心",
        )
        if not sid:
            write_subscribe_record(
                plugin,
                mediainfo,
                rank_key=rank_key,
                rank_name=rank_name,
                status="failed",
                reason=msg or "订阅失败",
                source_link=source_link,
                title=record_title,
                season=season,
                prefer_title=bool(record_title),
            )
            return False
        observation.cleanup_observe_logs(plugin, title=mediainfo.title)
        write_subscribe_record(
            plugin,
            mediainfo,
            rank_key=rank_key,
            rank_name=rank_name,
            status="success",
            source_link=source_link,
            title=record_title,
            season=season,
            prefer_title=bool(record_title),
        )
        return True
