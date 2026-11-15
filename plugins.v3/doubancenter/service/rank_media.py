"""榜单媒体识别、跨源身份保留与Bangumi历史补全。"""

import re
from typing import Any, Optional

from app.chain.media import MediaChain
from app.schemas.types import MediaSource, MediaType
from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.media import MetaInfo
from app.sdk.network import RequestUtils

from .. import utils
from ..adapter import bangumi as bangumi_adapter
from ..adapter import rss as rss_adapter
from ..model import rank as rank_model
from ..model.identity import (
    convert_identity,
    identity_payload,
    legacy_identity,
)
from ..model.identity import (
    recognize_media as recognize_with_identity,
)
from ..storage import records as storage
from . import bangumi_tmdb as bangumi_tmdb_service
from . import rank_refresh as rank_refresh_service
from . import rank_timing


def _record_douban_id(record: dict) -> str:
    """从榜单记录的身份字段或链接读取豆瓣 subject ID。"""
    if not isinstance(record, dict):
        return ""
    direct = str(record.get("douban_id") or record.get("doubanid") or "").strip()
    if direct.isdigit():
        return direct
    source, source_id = legacy_identity(
        media_source=record.get("media_source"),
        media_id=record.get("media_id"),
    )
    if source == MediaSource.Douban and source_id:
        return source_id
    for field in ("link", "unique"):
        subject_id = rss_adapter.douban_subject_id(record.get(field))
        if subject_id:
            return subject_id
    return ""



def _existing_tmdb_identity(existing: dict, douban_id: Any):
    """读取同一豆瓣条目历史中已经确认的 TMDB 身份。"""
    normalized_douban_id = str(douban_id or "").strip()
    if not normalized_douban_id or _record_douban_id(existing) != normalized_douban_id:
        return None, None
    source, media_id = legacy_identity(
        media_source=existing.get("media_source"),
        media_id=existing.get("media_id"),
        tmdb_id=existing.get("tmdb_id") or existing.get("tmdbid"),
    )
    if source == MediaSource.TMDB and media_id:
        return source, media_id
    return None, None



def _record_bangumi_id(record: dict) -> str:
    """从榜单记录中读取 Bangumi subject ID。"""
    direct = bangumi_adapter.extract_subject_id(record)
    if direct:
        return str(direct)
    source, source_id = legacy_identity(
        media_source=(record or {}).get("media_source"),
        media_id=(record or {}).get("media_id"),
    )
    return str(source_id) if source == MediaSource.Bangumi and source_id else ""



def _preferred_douban_display_title(item: dict, entry: dict, existing: Optional[dict], fallback: str) -> str:
    """从当前和历史豆瓣字段中选择稳定的中文展示标题。"""
    candidates = (
        (item or {}).get("display_title"),
        (item or {}).get("title_cn"),
        (item or {}).get("name_cn"),
        fallback,
        (existing or {}).get("original_title"),
        (existing or {}).get("title"),
    )
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value and _has_cjk_text(value):
            return value
    return str(fallback or "").strip()



def _existing_bangumi_tmdb_identity(existing: dict, bangumi_id: Any):
    """读取同一 Bangumi subject 历史中已经确认的 TMDB 身份。"""
    normalized_bangumi_id = str(bangumi_id or "").strip()
    if not normalized_bangumi_id or _record_bangumi_id(existing) != normalized_bangumi_id:
        return None, None
    source, media_id = legacy_identity(
        media_source=existing.get("media_source"),
        media_id=existing.get("media_id"),
        tmdb_id=existing.get("tmdb_id") or existing.get("tmdbid"),
    )
    if source == MediaSource.TMDB and media_id:
        return source, media_id
    return None, None



def _apply_bangumi_recognition(
    self,
    item: dict,
    entry: dict,
    *,
    reuse_tmdb_identity: bool = True,
):
    """展示 BGM 中文名，并用原名、母剧标题和独立季号补全 TMDB 信息。"""
    title = str(item.get("title") or "")
    if not title:
        return None
    meta = MetaInfo(title)
    year = item.get("year")
    if year:
        meta.year = str(year)
    meta.type = MediaType.TV
    tmdbid = (
        item.get("tmdb_id")
        or item.get("tmdbid")
        or entry.get("tmdb_id")
        or entry.get("tmdbid")
    ) if reuse_tmdb_identity else None
    bangumiid = _extract_bangumi_id(item) or _extract_bangumi_id(entry)
    try:
        recognition = bangumi_tmdb_service.recognize_bangumi_tmdb(
            self,
            self.chain,
            meta,
            bangumi_id=bangumiid,
            tmdb_id=tmdbid,
            season=item.get("season") or entry.get("season"),
            media_type=MediaType.TV,
            subject_fetcher=_fetch_bangumi_subject,
            subject_title=_bangumi_subject_title,
            subject_year=_bangumi_subject_year,
            meta_cls=MetaInfo,
        )
    except Exception as err:
        logger.warning(f"豆瓣中心：BangumiTV 条目《{title}》识别失败：{err}")
        return None
    mediainfo = recognition.get("mediainfo")
    subject = recognition.get("subject")
    if not subject and not mediainfo:
        subject = _fetch_bangumi_subject(self, bangumiid)
    if subject:
        _apply_bangumi_subject(subject, entry, title=title, bangumiid=bangumiid)
    if not mediainfo:
        if subject:
            display_title = str(recognition.get("title") or entry.get("title") or title or "").strip()
            original_title = str(recognition.get("original_title") or subject.get("name") or "").strip()
            if display_title:
                entry["title"] = display_title
            if original_title and original_title != display_title:
                entry["original_title"] = original_title
            else:
                entry.pop("original_title", None)
            if recognition.get("match_title"):
                entry["match_title"] = recognition["match_title"]
            if recognition.get("season") not in (None, ""):
                entry["season"] = int(recognition["season"])
        return None
    display_title = str(recognition.get("title") or entry.get("title") or title or "").strip()
    original_title = str(recognition.get("original_title") or "").strip()
    entry["title"] = display_title
    if original_title and original_title != display_title:
        entry["original_title"] = original_title
    else:
        entry.pop("original_title", None)
    entry["tmdb_title"] = recognition.get("tmdb_title") or getattr(mediainfo, "title", None) or ""
    if recognition.get("match_title"):
        entry["match_title"] = recognition["match_title"]
    if recognition.get("season") not in (None, ""):
        entry["season"] = int(recognition["season"])
    entry["source_year"] = _bangumi_subject_year(subject or {})
    entry["tmdbid"] = getattr(mediainfo, "tmdb_id", None) or tmdbid or entry.get("tmdbid")
    entry["tmdb_id"] = entry["tmdbid"]
    entry["bangumi_id"] = getattr(mediainfo, "bangumi_id", None) or bangumiid or entry.get("bangumi_id")
    entry["bangumiid"] = entry["bangumi_id"]
    entry.update(identity_payload(mediainfo, bangumi_id=bangumiid, tmdb_id=entry["tmdbid"]))
    rank_timing.resolve_release(
        self, mediainfo, entry.get("season"), entry=entry,
    )
    try:
        entry["poster"] = mediainfo.get_poster_image() or entry.get("poster")
    except Exception:
        pass
    return mediainfo



def _apply_display_recognition(
    self,
    item: dict,
    entry: dict,
    rank_key: str,
    rd: dict,
    douban_original_title_fetcher=None,
    existing: Optional[dict] = None,
    media_chain_cls=MediaChain,
):
    """刷新榜单展示数据时用 MP 识别结果补全标题、海报和 TMDB 信息。"""
    title = str(item.get("title") or "")
    if not title:
        return None
    meta = MetaInfo(title)
    year = item.get("year")
    if year:
        meta.year = str(year)
    inferred_type = "tv" if rank_key == "coming" else _rank_media_type(rd, item)
    media_type = MediaType.MOVIE if inferred_type == "movie" else MediaType.TV
    meta.type = media_type
    meta.begin_season = utils.resolve_media_season(
        meta,
        season=item.get("season"),
        titles=(entry.get("title"), (existing or {}).get("title")),
    )
    if media_type == MediaType.TV and meta.begin_season is not None:
        entry["season"] = meta.begin_season
    source, source_id = legacy_identity(
        media_source=item.get("media_source") or entry.get("media_source"),
        media_id=item.get("media_id") or entry.get("media_id"),
        tmdb_id=item.get("tmdb_id") or item.get("tmdbid") or entry.get("tmdbid"),
        douban_id=item.get("douban_id") or item.get("doubanid") or entry.get("douban_id"),
        bangumi_id=item.get("bangumi_id") or item.get("bangumiid") or entry.get("bangumi_id"),
    )
    recognized_source = source
    recognized_id = source_id
    mediainfo = None
    recognition_chain = self.chain
    if source == MediaSource.Douban and source_id:
        entry["douban_id"] = source_id
        conversion_chain = self.chain
        if not callable(getattr(conversion_chain, "convert_media_identity", None)):
            conversion_chain = media_chain_cls()
        recognition_chain = conversion_chain
        recognized_source, recognized_id = _existing_tmdb_identity(existing or {}, source_id)
        if not recognized_source or not recognized_id:
            try:
                recognized_source, recognized_id = convert_identity(
                    conversion_chain,
                    target_source=MediaSource.TMDB,
                    media_source=source,
                    media_id=source_id,
                    mtype=media_type,
                    season=getattr(meta, "begin_season", None),
                    fallback_title_loader=(
                        lambda: douban_original_title_fetcher(self, source_id)
                        if callable(douban_original_title_fetcher)
                        else []
                    ),
                )
            except Exception as err:
                logger.warning(f"豆瓣中心：榜单条目《{title}》豆瓣 ID {source_id} 转换 TMDB 失败：{err}")
                return None
        if not recognized_source or not recognized_id:
            logger.info(f"豆瓣中心：榜单条目《{title}》豆瓣 ID {source_id} 暂无 TMDB 映射，保留豆瓣身份")
            return None
    try:
        if recognized_source and recognized_id:
            mediainfo = recognize_with_identity(
                recognition_chain,
                meta=meta,
                mtype=media_type,
                media_source=recognized_source,
                media_id=recognized_id,
            )
        elif inferred_type == "unknown":
            try:
                mediainfo = self.chain.recognize_media(meta=meta)
            except TypeError:
                mediainfo = self.chain.recognize_media(meta=meta, mtype=media_type)
        else:
            mediainfo = self.chain.recognize_media(meta=meta, mtype=media_type)
    except Exception as err:
        logger.warning(f"豆瓣中心：刷新榜单条目《{title}》识别失败：{err}")
        return None
    if not mediainfo:
        if recognized_source == MediaSource.TMDB and recognized_id:
            logger.warning(f"豆瓣中心：榜单条目《{title}》已转换 TMDB ID {recognized_id}，但详情识别无结果")
        return None
    tmdb_title = str(getattr(mediainfo, "title", None) or "").strip()
    if tmdb_title:
        entry["tmdb_title"] = tmdb_title
    else:
        entry.pop("tmdb_title", None)
    entry["title"] = _preferred_douban_display_title(item, entry, existing, title)
    entry.pop("original_title", None)
    entry["source_year"] = str(item.get("year") or "")
    resolved_type = _resolved_media_type_name(rd, item, mediainfo)
    entry["media_type"] = "movie" if resolved_type == "movie" else ("tv" if resolved_type == "tv" else "unknown")
    entry["tmdbid"] = (
        getattr(mediainfo, "tmdb_id", None)
        or (recognized_id if recognized_source == MediaSource.TMDB else None)
        or entry.get("tmdbid")
    )
    if getattr(mediainfo, "bangumi_id", None):
        entry["bangumi_id"] = getattr(mediainfo, "bangumi_id", None)
        entry["bangumiid"] = entry["bangumi_id"]
    entry.update(identity_payload(
        mediainfo,
        media_source=recognized_source,
        media_id=recognized_id,
        tmdb_id=entry.get("tmdbid"),
        bangumi_id=entry.get("bangumiid"),
    ))
    rank_timing.resolve_release(
        self, mediainfo, meta.begin_season, entry=entry,
    )
    try:
        entry["poster"] = mediainfo.get_poster_image() or entry.get("poster")
    except Exception:
        pass
    if not entry.get("regions"):
        for key in ("regions", "countries", "origin_country", "production_countries", "country"):
            values = _normalize_region_values(getattr(mediainfo, key, None))
            if values:
                entry["regions"] = values
                entry["region_source"] = "mediainfo"
                break
    return mediainfo



def _preserve_existing_tmdb_identity(entry: dict, existing: dict) -> None:
    """本轮识别暂时失败时保留历史中已经确认的 TMDB 主身份。"""
    current_source, current_id = legacy_identity(
        media_source=entry.get("media_source"),
        media_id=entry.get("media_id"),
        tmdb_id=entry.get("tmdb_id") or entry.get("tmdbid"),
    )
    if current_source == MediaSource.TMDB and current_id:
        return
    preserve_bangumi = False
    current_bangumi_id = _record_bangumi_id(entry)
    if current_bangumi_id:
        existing_source, existing_id = _existing_bangumi_tmdb_identity(existing, current_bangumi_id)
        preserve_bangumi = bool(existing_source and existing_id)
    else:
        if current_source not in (None, MediaSource.Douban):
            return
        current_douban_id = _record_douban_id(entry)
        if not current_douban_id:
            return
        existing_source, existing_id = _existing_tmdb_identity(existing, current_douban_id)
    if not existing_source or not existing_id:
        return
    try:
        normalized_tmdb_id = int(existing_id)
    except (TypeError, ValueError):
        return
    if normalized_tmdb_id <= 0:
        return
    entry["media_source"] = MediaSource.TMDB.value
    entry["media_id"] = str(normalized_tmdb_id)
    entry["tmdb_id"] = normalized_tmdb_id
    entry["tmdbid"] = entry["tmdb_id"]
    if existing.get("poster") and (not preserve_bangumi or not entry.get("poster")):
        entry["poster"] = existing.get("poster")
    if not entry.get("tmdb_title"):
        tmdb_title = str(existing.get("tmdb_title") or "").strip()
        if not tmdb_title and not preserve_bangumi:
            legacy_title = str(existing.get("title") or "").strip()
            legacy_original_title = str(existing.get("original_title") or "").strip()
            current_title = str(entry.get("title") or "").strip()
            if legacy_title and legacy_original_title and legacy_original_title == current_title:
                tmdb_title = legacy_title
        if tmdb_title:
            entry["tmdb_title"] = tmdb_title
    if preserve_bangumi:
        resolved_bangumi_id = (
            entry.get("bangumi_id")
            or entry.get("bangumiid")
            or existing.get("bangumi_id")
            or existing.get("bangumiid")
            or current_bangumi_id
        )
        entry["bangumi_id"] = resolved_bangumi_id
        entry["bangumiid"] = resolved_bangumi_id
        if not entry.get("bangumi_title_source") and existing.get("bangumi_title_source"):
            entry["bangumi_title_source"] = existing.get("bangumi_title_source")
            if existing.get("title"):
                entry["title"] = existing.get("title")
            if existing.get("original_title"):
                entry["original_title"] = existing.get("original_title")
        elif not entry.get("original_title") and existing.get("original_title"):
            entry["original_title"] = existing.get("original_title")
        for field in ("match_title", "season"):
            if entry.get(field) in (None, "") and existing.get(field) not in (None, ""):
                entry[field] = existing.get(field)
    else:
        entry.pop("original_title", None)



def _fetch_bangumi_subject(self, bangumiid: Any) -> Optional[dict]:
    """通过 Bangumi subject id 获取官方条目详情。"""
    return bangumi_adapter.fetch_subject(self, bangumiid, request_utils_cls=RequestUtils, settings_obj=settings)



def _bangumi_subject_title(subject: dict, fallback: str = "") -> str:
    """从 Bangumi subject 详情提取优先中文标题。"""
    return bangumi_adapter.subject_title(subject, fallback=fallback)



def _bangumi_subject_year(subject: dict, fallback: Any = "") -> str:
    """从 Bangumi subject 详情提取年份。"""
    return bangumi_adapter.subject_year(subject, fallback=fallback)



def _bangumi_subject_poster(subject: dict) -> str:
    """从 Bangumi subject 详情提取海报。"""
    return bangumi_adapter.subject_poster(subject)



def _apply_bangumi_subject(subject: dict, entry: dict, title: str = "", bangumiid: Any = None) -> None:
    """用 Bangumi subject 详情补全榜单条目。"""
    bangumi_adapter.apply_subject(subject, entry, title=title, bangumiid=bangumiid)



def bangumi_subject_to_media_data(subject: dict, media_type_name: str, fallback_title: str = "", bangumiid: Any = None) -> dict:
    """将 Bangumi subject 详情转换为前端可展示的媒体对象。"""
    return bangumi_adapter.subject_to_media_data(
        subject,
        media_type_name,
        fallback_title=fallback_title,
        bangumiid=bangumiid,
    )



def _recognize_bangumi_media(chain, meta: MetaInfo, tmdbid: Any = None, bangumiid: Any = None):
    """兼容旧调用方，按标题+年份优先返回 TMDB 媒体对象。"""
    recognition = bangumi_tmdb_service.recognize_bangumi_tmdb(
        None,
        chain,
        meta,
        bangumi_id=bangumiid,
        tmdb_id=tmdbid,
        media_type=MediaType.TV,
    )
    return recognition.get("mediainfo")



def _extract_bangumi_id(item: dict) -> Optional[str]:
    """从 BangumiTV 榜单条目中提取 Bangumi subject id。"""
    return bangumi_adapter.extract_subject_id(item)



def _has_cjk_text(value: Any) -> bool:
    """判断文本中是否包含中日韩统一表意文字。"""
    return bangumi_adapter.has_cjk_text(value)



def _is_complete_bangumi_history_item(item: dict) -> bool:
    """判断 Bangumi 历史条目是否已有完整且一致的展示身份。"""
    bangumiid = _extract_bangumi_id(item)
    if not bangumiid or not item.get("poster") or not item.get("bangumi_title_source"):
        return False
    media_source = str(item.get("media_source") or "")
    media_id = str(item.get("media_id") or "")
    if media_source == MediaSource.TMDB.value and media_id:
        if not item.get("tmdb_title"):
            return False
        source_title = str(item.get("original_title") or item.get("title") or "").strip()
        if not source_title:
            return True
        seasonal_candidates = bangumi_tmdb_service._seasonal_title_candidates(
            MetaInfo(source_title),
            source_title,
            meta_cls=MetaInfo,
        )
        if not seasonal_candidates:
            return True
        try:
            stored_season = int(item.get("season"))
        except (TypeError, ValueError):
            return False
        stored_match_title = str(item.get("match_title") or "").strip().casefold()
        return any(
            stored_season == season and stored_match_title == candidate_title.casefold()
            for candidate_title, season in seasonal_candidates
        )
    return False



def _bangumi_history_repair_candidates(history: list[dict]) -> list[dict]:
    """只生成当前榜单快照中的 Bangumi 修复对象，避免阻塞插件启动。"""
    candidates = rank_refresh_service.dashboard_rank_items(history, limit=5)
    result = []
    seen = set()
    for item in candidates:
        if not isinstance(item, dict) or id(item) in seen:
            continue
        seen.add(id(item))
        result.append(item)
    return result



def _apply_bangumi_media(mediainfo: Any, entry: dict, title: str, bangumiid: Any) -> None:
    """用宿主 Bangumi 身份识别结果补全历史条目并保留既有 TMDB 主身份。"""
    media_source = str(entry.get("media_source") or "")
    media_id = entry.get("media_id")
    cn_title = str(getattr(mediainfo, "title", None) or title or "")
    if cn_title and cn_title != title:
        entry["original_title"] = title
    entry["title"] = cn_title
    entry["year"] = str(getattr(mediainfo, "year", None) or entry.get("year") or "")
    resolved_bangumi_id = getattr(mediainfo, "bangumi_id", None) or bangumiid
    entry["bangumi_id"] = resolved_bangumi_id
    entry["bangumiid"] = resolved_bangumi_id
    poster = str(getattr(mediainfo, "poster_path", None) or "")
    if not poster and hasattr(mediainfo, "get_poster_image"):
        try:
            poster = str(mediainfo.get_poster_image() or "")
        except Exception:
            poster = ""
    entry["poster"] = poster or entry.get("poster")
    if media_source == MediaSource.TMDB.value and media_id not in (None, ""):
        entry["media_source"] = MediaSource.TMDB.value
        entry["media_id"] = str(media_id)
    else:
        entry["media_source"] = MediaSource.Bangumi.value
        entry["media_id"] = str(resolved_bangumi_id)



def normalize_bangumi_history(self, history: list[dict], max_repairs: int = 10) -> list[dict]:
    """按 BGM 原名重新识别当前快照，并补齐中文展示名、TMDB 身份、海报和季号。"""
    if not isinstance(history, list):
        return []
    changed = False
    repair_count = 0
    for item in _bangumi_history_repair_candidates(history):
        title = item.get("title")
        if not title or not _extract_bangumi_id(item):
            continue
        if _is_complete_bangumi_history_item(item):
            continue
        if max_repairs > 0 and repair_count >= max_repairs:
            break
        before = (
            item.get("title"),
            item.get("year"),
            item.get("tmdbid"),
            item.get("tmdb_id"),
            item.get("poster"),
            item.get("original_title"),
            item.get("bangumiid"),
            item.get("bangumi_id"),
            item.get("media_source"),
            item.get("media_id"),
            item.get("tmdb_title"),
            item.get("match_title"),
            item.get("season"),
            item.get("bangumi_title_source"),
        )
        existing_tmdb_identity = (
            item.get("media_source"),
            item.get("media_id"),
            item.get("tmdb_id"),
            item.get("tmdbid"),
        )
        bangumiid = _extract_bangumi_id(item)
        source_title = str(item.get("original_title") or title or "")
        repair_item = dict(item)
        repair_item["title"] = source_title
        mediainfo = _apply_bangumi_recognition(
            self,
            repair_item,
            item,
            reuse_tmdb_identity=False,
        )
        if (
            not mediainfo
            and str(existing_tmdb_identity[0] or "") == MediaSource.TMDB.value
            and existing_tmdb_identity[1] not in (None, "")
        ):
            item["media_source"] = MediaSource.TMDB.value
            item["media_id"] = str(existing_tmdb_identity[1])
            if existing_tmdb_identity[2] not in (None, ""):
                item["tmdb_id"] = existing_tmdb_identity[2]
            if existing_tmdb_identity[3] not in (None, ""):
                item["tmdbid"] = existing_tmdb_identity[3]
        if not mediainfo and not item.get("poster"):
            meta = MetaInfo(str(title))
            meta.type = MediaType.TV
            if item.get("year"):
                meta.year = str(item.get("year"))
            try:
                mediainfo = recognize_with_identity(
                    self.chain,
                    meta=meta,
                    mtype=MediaType.TV,
                    media_source=MediaSource.Bangumi,
                    media_id=bangumiid,
                )
            except Exception as err:
                logger.warning(f"豆瓣中心：BangumiTV 历史条目《{title}》身份修复失败：{err}")
                mediainfo = None
            if mediainfo:
                _apply_bangumi_media(mediainfo, item, str(title), bangumiid)
        repair_count += 1
        after = (
            item.get("title"),
            item.get("year"),
            item.get("tmdbid"),
            item.get("tmdb_id"),
            item.get("poster"),
            item.get("original_title"),
            item.get("bangumiid"),
            item.get("bangumi_id"),
            item.get("media_source"),
            item.get("media_id"),
            item.get("tmdb_title"),
            item.get("match_title"),
            item.get("season"),
            item.get("bangumi_title_source"),
        )
        if after != before:
            changed = True
    if changed:
        history = storage.save_rank_history(self, "bangumi", history)
    return history



def _normalize_region_values(value: Any) -> list[str]:
    """统一地区字段并兼容最小测试宿主。"""
    normalizer = getattr(utils, "normalize_region_values", None)
    if callable(normalizer):
        return normalizer(value)
    if isinstance(value, str):
        return [part for part in re.split(r"[\s、,，/|；;]+", value) if part]
    if isinstance(value, (list, tuple, set)):
        return [str(part).strip() for part in value if str(part).strip()]
    return []



def _rank_media_type(rank: dict, item: dict) -> str:
    """根据榜单定义和 RSS 条目推断媒体类型。"""
    return rank_model.infer_media_type(rank, item)



def _resolved_media_type_name(rank: dict, item: dict, mediainfo=None) -> str:
    """综合 RSS 字段、已知路由和媒体识别结果确定类型。"""
    inferred = _rank_media_type(rank, item)
    if inferred in ("movie", "tv"):
        return inferred
    raw = str(getattr(mediainfo, "type", "") or "").lower()
    if "movie" in raw or "电影" in raw:
        return "movie"
    if "tv" in raw or "电视剧" in raw or "series" in raw:
        return "tv"
    return "unknown"
