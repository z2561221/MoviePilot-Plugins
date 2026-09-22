"""同一榜单快照内复用已核验身份的原生季日期。"""

from app.schemas.types import MediaSource

from .. import utils
from ..model.identity import identity_from_media, legacy_identity


def _tmdb_id(mediainfo, entry: dict) -> int | None:
    """原生 TMDB 身份优先，其它来源只能使用明确的 TMDB 字段。"""
    source, media_id = identity_from_media(mediainfo)
    if source != MediaSource.TMDB:
        source, media_id = legacy_identity(
            tmdb_id=(getattr(mediainfo, "tmdb_id", None)
                     or entry.get("tmdb_id") or entry.get("tmdbid")),
        )
    if source != MediaSource.TMDB or isinstance(media_id, bool):
        return None
    text = str(media_id or "").strip()
    return int(text) if text.isdecimal() and int(text) > 0 else None


def resolve_release(plugin, mediainfo, season, *, entry=None, require_date=False):
    """日期随当前身份和季号保存，避免重复查询及跨媒体复用。"""
    entry = entry if isinstance(entry, dict) else {}
    tmdb_id = _tmdb_id(mediainfo, entry)
    target_season = utils.normalize_season(season)
    if season is not None and target_season is None:
        return "", None
    season = target_season
    cached = entry.get("release_facts") or {}
    same_target = (
        isinstance(cached, dict) and tmdb_id is not None
        and cached.get("tmdb_id") == tmdb_id and cached.get("season") == season
    )
    cached_date = cached.get("air_date") if same_target else None
    year, air_date = utils.get_media_release(
        mediainfo, season=season, source_year=entry.get("source_year"),
        require_date=require_date or bool(cached_date),
        season_date_loader=lambda target: cached_date or utils.get_tmdb_air_date(
            plugin.chain, tmdb_id, season=target,
        ),
    )
    entry.update(year=year, air_date=air_date, release_facts={
        "tmdb_id": tmdb_id, "season": season, "air_date": air_date,
    })
    return year, air_date
