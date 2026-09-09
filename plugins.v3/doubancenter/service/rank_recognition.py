"""豆瓣中心榜单条目识别编排服务。"""

from typing import Any, Callable, Tuple

from app.schemas.types import MediaType
from app.sdk.media import MetaInfo

from .. import utils
from . import bangumi_tmdb as bangumi_tmdb_service


def recognize_rss_item(
    plugin: Any,
    item: dict,
    rank: dict,
    *,
    infer_media_type: Callable[[dict, dict], str],
    resolved_media_type: Callable[[dict, dict, Any], str],
    extract_bangumi_id: Callable[[dict], Any],
    fetch_bangumi_subject: Callable[[Any, Any], Any],
    bangumi_subject_title: Callable[..., str],
    bangumi_subject_year: Callable[..., str],
) -> Tuple[Any, Any, str]:
    """按榜单路由识别 RSS 媒体，未知类型交给宿主自动判断。"""
    item = item if isinstance(item, dict) else {}
    rank = rank if isinstance(rank, dict) else {}
    meta = MetaInfo(str(item.get("title") or ""))
    meta.begin_season = utils.resolve_media_season(meta, season=item.get("season"))
    if item.get("year"):
        meta.year = str(item.get("year"))
    inferred = infer_media_type(rank, item)
    if str(rank.get("key") or "") == "bangumi":
        meta.type = MediaType.TV
        recognition = bangumi_tmdb_service.recognize_bangumi_tmdb(
            plugin,
            plugin.chain,
            meta,
            bangumi_id=extract_bangumi_id(item),
            tmdb_id=item.get("tmdb_id") or item.get("tmdbid"),
            season=item.get("season"),
            media_type=MediaType.TV,
            subject_fetcher=fetch_bangumi_subject,
            subject_title=bangumi_subject_title,
            subject_year=bangumi_subject_year,
            meta_cls=MetaInfo,
        )
        if recognition.get("season") not in (None, ""):
            meta.begin_season = int(recognition["season"])
        if recognition.get("title"):
            item["display_title"] = recognition["title"]
        return meta, recognition.get("mediainfo"), "tv"
    if inferred in ("movie", "tv"):
        meta.type = MediaType.MOVIE if inferred == "movie" else MediaType.TV
        mediainfo = plugin.chain.recognize_media(meta=meta, mtype=meta.type)
    else:
        try:
            mediainfo = plugin.chain.recognize_media(meta=meta)
        except TypeError:
            mediainfo = plugin.chain.recognize_media(meta=meta, mtype=MediaType.TV)
    return meta, mediainfo, resolved_media_type(rank, item, mediainfo)


def recognize_snapshot_item(
    plugin: Any,
    rank_key: str,
    item: dict,
    entry: dict,
    rank: dict,
    existing: dict,
    *,
    apply_bangumi: Callable[[Any, dict, dict], Any],
    apply_display: Callable[..., Any],
    douban_original_title_fetcher: Callable[..., Any],
):
    """按榜单类型选择 Bangumi 或通用展示识别器。"""
    if rank_key == "bangumi":
        return apply_bangumi(plugin, item, entry)
    return apply_display(
        plugin,
        item,
        entry,
        rank_key,
        rank,
        douban_original_title_fetcher=douban_original_title_fetcher,
        existing=existing,
    )
