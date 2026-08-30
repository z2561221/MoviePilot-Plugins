"""豆瓣中心榜单快照合并服务。"""

import datetime
from typing import Any, Callable, Dict, List, Optional

from app.sdk.logging import logger

from ..storage import records as storage


def _history_index(history: List[dict]) -> Dict[str, int]:
    """按唯一键构建历史记录位置索引。"""
    return {
        item.get("unique"): index
        for index, item in enumerate(history)
        if isinstance(item, dict) and item.get("unique")
    }


def _snapshot_entry(
    rank_key: str,
    rank: dict,
    item: dict,
    rank_index: int,
    refresh_time: str,
    *,
    infer_media_type: Callable[[dict, dict], str],
) -> dict:
    """把 RSS 条目转换为稳定的榜单快照结构。"""
    title = item.get("title", "")
    link = item.get("link", "")
    media_type = "tv" if rank_key == "coming" else infer_media_type(rank, item)
    entry = {
        "title": title,
        "year": item.get("year", "") or "",
        "media_type": media_type,
        "link": link,
        "rank_route": rank.get("route", ""),
        "tmdbid": item.get("tmdbid"),
        "poster": item.get("poster"),
        "time": refresh_time,
        "unique": f"dc2_coming:{link or title}" if rank_key == "coming" else f"dc2_rank:{link or title}",
        "douban_id": item.get("doubanid"),
        "regions": list(item.get("regions") or []),
        "region_source": item.get("region_source") or "",
        "rank_index": rank_index,
        "rank_order": rank_index + 1,
        "rank_key": rank_key,
        "rank_name": rank.get("name", ""),
        "rank_refreshed_at": refresh_time,
    }
    source_link = item.get("source_link") or ""
    if source_link:
        entry["source_link"] = source_link
    if rank_key == "coming":
        entry.update(year=item.get("year", ""), wish_count=item.get("wish_count", 0))
    return entry


def _merge_existing(existing: dict, entry: dict, rank_key: str) -> dict:
    """合并已有历史，并保留观察期相关状态。"""
    merged = dict(existing)
    merged.update(entry)
    if rank_key != "bangumi":
        merged.pop("original_title", None)
    if existing.get("observing"):
        merged["observing"] = True
        merged["first_seen"] = existing.get("first_seen") or existing.get("time")
    if existing.get("observe_deleted"):
        merged["observe_deleted"] = True
        if existing.get("observe_deleted_at"):
            merged["observe_deleted_at"] = existing.get("observe_deleted_at")
    return merged


def merge_rank_items(
    plugin: Any,
    rank_key: str,
    items: List[dict],
    rank: dict,
    *,
    infer_media_type: Callable[[dict, dict], str],
    recognize_item: Callable[[Any, str, dict, dict, dict, dict], Any],
    preserve_existing_identity: Callable[[dict, dict], None],
    return_snapshot: bool = False,
    now: Optional[Callable[[], datetime.datetime]] = None,
):
    """合并本轮 RSS 条目并返回可选的已识别快照。"""
    history: List[dict] = storage.read_rank_history(plugin, rank_key)
    history_index = _history_index(history)
    snapshots = []
    new_count = 0
    clock = now or datetime.datetime.now
    refresh_time = clock().strftime("%Y-%m-%d %H:%M:%S")
    for rank_index, raw_item in enumerate(items or []):
        item = raw_item if isinstance(raw_item, dict) else {}
        try:
            if not item.get("title"):
                continue
            entry = _snapshot_entry(
                rank_key,
                rank,
                item,
                rank_index,
                refresh_time,
                infer_media_type=infer_media_type,
            )
            existing_index = history_index.get(entry["unique"])
            existing = (
                history[existing_index]
                if existing_index is not None and isinstance(history[existing_index], dict)
                else {}
            )
            mediainfo = recognize_item(plugin, rank_key, item, entry, rank, existing)
            preserve_existing_identity(entry, existing)
            snapshots.append({"raw": dict(item), "entry": dict(entry), "mediainfo": mediainfo})
            if existing_index is None:
                history.append(entry)
                history_index[entry["unique"]] = len(history) - 1
                new_count += 1
            else:
                history[existing_index] = _merge_existing(existing, entry, rank_key)
        except Exception as err:
            logger.error(f"豆瓣中心：合并 {rank_key} 榜单条目出错：{err}")
    history = storage.save_rank_history(plugin, rank_key, history)
    logger.info(
        f"豆瓣中心：{rank['name']} 刷新完成，当前批次 {len(items or [])} 条，新增 {new_count} 条，累计 {len(history)} 条"
    )
    return (history, snapshots) if return_snapshot else history
