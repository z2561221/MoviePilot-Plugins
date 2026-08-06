"""豆瓣中心订阅服务。"""

import datetime
from typing import Any, Dict, List

from app.chain.subscribe import SubscribeChain
from app.log import logger
from app.schemas.types import MediaType

from ..storage import records as storage
from . import observation


def _default_subscribe_oper_cls():
    """按调用时环境读取 MoviePilot 订阅数据库操作类。"""
    from app.db.subscribe_oper import SubscribeOper

    return SubscribeOper


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


def is_existing_media(mediainfo, meta=None, subscribe_chain_cls=SubscribeChain, subscribe_oper_cls=None) -> bool:
    """判断媒体是否存在活动订阅或已完成订阅历史。"""
    try:
        if subscribe_chain_cls().exists(mediainfo=mediainfo, meta=meta):
            return True
    except Exception as err:
        logger.warning(f"豆瓣中心：检查订阅存在状态失败：{err}")
    try:
        subscribe_oper_cls = subscribe_oper_cls or _default_subscribe_oper_cls()
        if subscribe_oper_cls().exist_history(
            tmdbid=getattr(mediainfo, "tmdb_id", None),
            doubanid=getattr(mediainfo, "douban_id", None),
            season=getattr(meta, "begin_season", None) if meta else None,
        ):
            return True
    except Exception as err:
        logger.warning(f"豆瓣中心：检查已完成订阅状态失败：{err}")
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
) -> None:
    """记录已存在订阅，避免后续再次进入观察队列。"""
    existing_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "title": getattr(mediainfo, "title", None) or title or unique,
        "year": getattr(mediainfo, "year", None) or year or "",
        "link": link,
        "tmdbid": getattr(mediainfo, "tmdb_id", ""),
        "time": existing_at,
        "unique": unique,
        "existing": True,
        "existing_at": existing_at,
        "existing_reason": "subscribe",
    }
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
) -> None:
    """写入自动或榜单手动订阅历史记录。"""
    resolved_title = getattr(mediainfo, "title", None) or title
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
    if bangumi_id not in (None, ""):
        record["bangumiid"] = bangumi_id
    record_key = (
        str(status or ""),
        str(resolved_tmdb_id or ""),
        str(resolved_title or ""),
        str(resolved_year or ""),
        str(rank_key or ""),
    )
    kept = []
    for item in subs:
        if not isinstance(item, dict):
            kept.append(item)
            continue
        item_key = (
            str(item.get("status") or "success"),
            str(item.get("tmdbid") or ""),
            str(item.get("title") or ""),
            str(item.get("year") or ""),
            str(item.get("rank_key") or ""),
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
    subscribe_chain_cls=SubscribeChain,
    subscribe_oper_cls=None,
) -> bool:
    """按 MP 默认 TMDB 语义执行自动订阅。"""
    if is_existing_media(
        mediainfo,
        meta,
        subscribe_chain_cls=subscribe_chain_cls,
        subscribe_oper_cls=subscribe_oper_cls,
    ):
        observation.cleanup_observe_logs(plugin, title=getattr(mediainfo, "title", ""))
        return False
    subscribe_chain = subscribe_chain_cls()
    sid, msg = subscribe_chain.add(
        title=mediainfo.title,
        year=mediainfo.year or "",
        mtype=mediainfo.type if mediainfo.type else MediaType.TV,
        tmdbid=mediainfo.tmdb_id,
        season=None,
        resolution=None,
        sites=None,
        exist_ok=True,
        username="豆瓣中心",
    )
    if not sid:
        write_subscribe_record(plugin, mediainfo, rank_key=rank_key, rank_name=rank_name, status="failed", reason=msg or "订阅失败", source_link=source_link)
        return False
    observation.cleanup_observe_logs(plugin, title=mediainfo.title)
    write_subscribe_record(plugin, mediainfo, rank_key=rank_key, rank_name=rank_name, status="success", source_link=source_link)
    return True
