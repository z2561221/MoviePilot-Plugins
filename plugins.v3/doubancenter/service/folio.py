"""
DoubanCenter - 豆瓣档案模块
"""
import datetime
import re
from collections.abc import Mapping
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from app.chain.media import MediaChain
from app.chain.mediaserver import MediaServerChain
from app.schemas.types import MediaSource, MediaType, MessageType
from app.sdk.logging import logger
from app.sdk.media import MetaInfo
from app.sdk.services import MediaServerHelper, MediaServerIdentityHelper

from .. import utils
from ..adapter import folio_library, folio_media
from ..adapter.douban_account import DoubanApi
from ..model import folio_record
from ..model.identity import (
    convert_identity,
    identity_from_media,
    legacy_identity,
    recognize_media,
)
from ..storage import records as storage
from . import folio_watch

WISH_NOTIFY_THROTTLE_SECONDS = 6 * 60 * 60
WISH_RECOGNIZE_MAX_RETRIES = 3
FOLIO_SERIES_CACHE_KEY = "_folio_series_cache"

_PROVIDER_KEYS = {
    MediaSource.TMDB: ("Tmdb", "TMDB", "tmdb", "tmdb_id"),
    MediaSource.Douban: ("Douban", "douban", "douban_id"),
    MediaSource.Bangumi: ("Bangumi", "bangumi", "bangumi_id"),
    MediaSource.IMDb: ("Imdb", "IMDb", "imdb", "imdb_id"),
    MediaSource.TVDB: ("Tvdb", "TVDB", "tvdb", "tvdb_id"),
}

# 这三条历史记录的豆瓣 ID 已由人工核对到 TMDB，作为跨源转换暂时不可用时的
# 精确兜底。按豆瓣 ID 命中，不按裸标题猜测，避免「凡人修仙传」误命中真人版。
_FOLIO_TMDB_POSTER_FALLBACKS = {
    "30513783": {
        "tmdb_id": "94664",
        "poster_path": "https://image.tmdb.org/t/p/original/u7LWdKmEdEr6Ui3GZMsFGlKZQBd.jpg",
    },
    "37441858": {
        "tmdb_id": "296286",
        "poster_path": "https://image.tmdb.org/t/p/original/1ZkivwzRnJOTMyZvyE88EvjK4ML.jpg",
    },
    "34925294": {
        "tmdb_id": "106449",
        "poster_path": "https://image.tmdb.org/t/p/original/u1VRjvvCIVwb1MUhoxSAUimhoKZ.jpg",
    },
}


def check_cookie_periodically(self) -> None:
    """定期检测豆瓣 Cookie 是否仍然可用。"""
    now = datetime.datetime.now().timestamp()
    if not hasattr(self, '_last_cookie_check_time'):
        self._last_cookie_check_time = 0
    if now - self._last_cookie_check_time > 3600:
        if not hasattr(self, '_last_cookie_invalid_time'):
            self._last_cookie_invalid_time = 0
        try:
            _, sid = DoubanApi(user_cookie=self._folio_cookie).get_subject_id(title="肖申克的救赎")
        except Exception:
            sid = None
        if sid:
            if not hasattr(self, '_last_cookie_valid_time'):
                self._last_cookie_valid_time = 0
            if now - self._last_cookie_valid_time > 600:
                logger.info("cookie有效性检测通过")
                self._last_cookie_valid_time = now
        else:
            if now - self._last_cookie_invalid_time > 600:
                _send_wish_notification(self, "豆瓣 Cookie 可能已失效，请及时更换！", throttle_key="cookie_invalid")
                self._last_cookie_invalid_time = now
        self._last_cookie_check_time = now


def run_wish_scheduled(self) -> None:
    """执行豆瓣想看同步定时入口。"""
    run_wish_sync(self)
    process_wish_queue(self)


def run_wish_sync(self, api=None, request_get=None) -> None:
    """读取豆瓣想看列表，首跑建立基线，后续仅将新增条目入队。"""
    dh = api if api is not None else DoubanApi(user_cookie=getattr(self, "_folio_cookie", ""))
    state = storage.read_folio_wish_state(self)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        items = dh.get_wish_items(
            user_id=getattr(self, "_wish_user", "") or "",
            max_pages=max(1, int(getattr(self, "_wish_max_pages", 1) or 1)),
            days=max(0, int(getattr(self, "_wish_days", 7) or 7)),
            request_get=request_get,
        ) or []
    except Exception as err:
        state.update({"last_run": now, "last_error": f"读取想看失败：{err}"})
        storage.save_folio_wish_state(self, state)
        logger.warning(f"豆瓣想看读取失败：{err}")
        _send_wish_notification(self, f"读取想看失败：{err}", throttle_key="wish_read_failed")
        return

    seen = storage.read_folio_wish_seen(self)
    queue = storage.read_folio_wish_queue(self)
    processed = storage.read_folio_wish_processed(self)
    failed = storage.read_folio_wish_failed(self)
    seen_ids = {str(r.get("subject_id")) for r in seen if r.get("subject_id")}

    if not state.get("initialized"):
        for item in items:
            subject_id = str(item.get("subject_id") or "")
            if subject_id and subject_id not in seen_ids:
                seen_ids.add(subject_id)
                seen.append(_wish_seen_record(item, now))
        state.update({"initialized": True, "baseline_at": now, "last_run": now, "last_error": ""})
        storage.save_folio_wish_seen(self, seen)
        storage.save_folio_wish_queue(self, queue)
        storage.save_folio_wish_state(self, state)
        logger.info(f"豆瓣想看首次运行，建立基线 {len(seen)} 条，不入队")
        return

    queue_ids = {str(r.get("subject_id")) for r in queue if r.get("subject_id")}
    processed_ids = {str(r.get("subject_id")) for r in processed if r.get("subject_id")}
    retryable_failed = _latest_retryable_wish_failures(failed)
    added = 0
    recovered = 0
    for item in items:
        subject_id = str(item.get("subject_id") or "")
        if not subject_id:
            continue
        if subject_id in seen_ids:
            failed_record = retryable_failed.get(subject_id)
            retry = int((failed_record or {}).get("retry", 0) or 0)
            recognize_title = _wish_recognize_title(item.get("title"))
            failed_recognize_title = str((failed_record or {}).get("recognize_title") or "")
            reset_recognition_retries = (
                bool(failed_record)
                and retry >= WISH_RECOGNIZE_MAX_RETRIES
                and failed_recognize_title != recognize_title
            )
            if (
                failed_record
                and subject_id not in queue_ids
                and subject_id not in processed_ids
                and (retry < WISH_RECOGNIZE_MAX_RETRIES or reset_recognition_retries)
            ):
                queue_ids.add(subject_id)
                if reset_recognition_retries:
                    failed = _clear_wish_failed(failed, subject_id, reason="recognize_failed")
                queue.append(_wish_queue_record(item, now, retry=0 if reset_recognition_retries else retry))
                recovered += 1
            continue
        seen_ids.add(subject_id)
        seen.append(_wish_seen_record(item, now))
        if subject_id not in queue_ids:
            queue_ids.add(subject_id)
            queue.append(_wish_queue_record(item, now))
            added += 1
    state.update({"last_run": now, "last_error": ""})
    storage.save_folio_wish_seen(self, seen)
    storage.save_folio_wish_queue(self, queue)
    storage.save_folio_wish_failed(self, failed)
    storage.save_folio_wish_state(self, state)
    logger.info(f"豆瓣想看同步完成，新增入队 {added} 条，恢复重试 {recovered} 条")


WISH_RANK_KEY = "douban_wish"
WISH_RANK_NAME = "豆瓣想看"


def _wish_recognize_title(title):
    """提取豆瓣 feed 别名串中的首个主标题用于媒体识别。"""
    value = str(title or "").strip()
    primary = value.split(" / ", 1)[0].strip()
    return primary or value


def _default_wish_recognize(self):
    """返回默认的想看识别函数。"""
    def recognize(title, year, subject_id=None):
        """优先按豆瓣 subject ID 识别想看条目，失败后回退标题识别。"""
        meta = MetaInfo(_wish_recognize_title(title))
        if year:
            meta.year = str(year)
        chain = MediaChain()
        mtype = meta.type if meta.type in (MediaType.MOVIE, MediaType.TV) else None
        if subject_id:
            try:
                source, media_id = convert_identity(
                    chain,
                    target_source=MediaSource.TMDB,
                    media_source=MediaSource.Douban,
                    media_id=subject_id,
                    mtype=mtype,
                    season=getattr(meta, "begin_season", None),
                )
            except Exception as err:
                logger.warning(f"豆瓣想看《{title}》subject ID 转换 TMDB 失败：{err}")
                source, media_id = None, None
            if source and media_id:
                try:
                    mediainfo = recognize_media(
                        chain,
                        meta=meta,
                        mtype=mtype,
                        media_source=source,
                        media_id=media_id,
                    )
                except Exception as err:
                    logger.warning(f"豆瓣想看《{title}》TMDB ID {media_id} 识别失败：{err}")
                    mediainfo = None
                if mediainfo:
                    return mediainfo
        return chain.recognize_by_meta(meta)
    return recognize


def process_wish_queue(self, recognize=None, subscribe=None) -> None:
    """处理想看待订阅队列，识别后通过现有订阅链创建订阅。"""
    queue = storage.read_folio_wish_queue(self)
    if not queue:
        return
    processed = storage.read_folio_wish_processed(self)
    failed = storage.read_folio_wish_failed(self)
    state = storage.read_folio_wish_state(self)
    uses_default_recognizer = recognize is None
    recognizer = recognize or _default_wish_recognize(self)
    subscriber = subscribe
    if subscriber is None:
        from . import subscription as subscription_service
        subscriber = subscription_service.add_subscription
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    remaining = []
    for item in queue:
        subject_id = str(item.get("subject_id") or "")
        title = item.get("title") or ""
        year = item.get("year") or ""
        link = item.get("link") or ""
        mediainfo = None
        try:
            mediainfo = (
                recognizer(title, year, subject_id)
                if uses_default_recognizer
                else recognizer(title, year)
            )
        except Exception as err:
            logger.warning(f"豆瓣想看识别失败：{title} {err}")
            mediainfo = None
        if not mediainfo:
            retry = _record_wish_failed(failed, item, "recognize_failed", now)
            if retry < WISH_RECOGNIZE_MAX_RETRIES:
                remaining.append(_wish_queue_record(item, now, retry=retry))
            continue
        failed = _clear_wish_failed(failed, subject_id, reason="recognize_failed")
        subscribe_failed = False
        subscribe_reason = ""
        before_failed_records = _failed_subscribe_record_count(self, mediainfo)
        try:
            result = subscriber(self, mediainfo, rank_key=WISH_RANK_KEY, rank_name=WISH_RANK_NAME, source_link=link)
        except Exception as err:
            result = None
            subscribe_failed = True
            subscribe_reason = str(err) or "subscribe_failed"
            logger.warning(f"豆瓣想看订阅失败：{title} {err}")
        if _subscribe_result_is_failed(result) or _failed_subscribe_record_count(self, mediainfo) > before_failed_records:
            subscribe_failed = True
            subscribe_reason = _subscribe_failure_reason(result)
        if subscribe_failed:
            _record_wish_failed(failed, item, "subscribe_failed", now, subscribe_reason)
            continue
        processed.append({"subject_id": subject_id, "title": title, "processed_at": now})

    storage.save_folio_wish_queue(self, remaining)
    storage.save_folio_wish_processed(self, processed)
    storage.save_folio_wish_failed(self, failed)
    state.update({"last_run": now, "last_processed": len(processed), "last_failed": len(failed), "last_error": ""})
    storage.save_folio_wish_state(self, state)
    logger.info(f"豆瓣想看队列处理完成，处理 {len(processed)} 条，失败 {len(failed)} 条")


def _record_wish_failed(failed, item, reason, now, message=""):
    """记录想看同步失败条目并返回累计重试次数。"""
    subject_id = str(item.get("subject_id") or "")
    retry = int(item.get("retry", 0) or 0) + 1
    for record in reversed(failed):
        if str(record.get("subject_id") or "") == subject_id and record.get("reason") == reason:
            retry = int(record.get("retry", 0) or 0) + 1
            break
    record = {
        "subject_id": subject_id,
        "title": item.get("title") or "",
        "reason": reason,
        "message": message or reason,
        "retry": retry,
        "failed_at": now,
    }
    if reason == "recognize_failed":
        record["recognize_title"] = _wish_recognize_title(item.get("title"))
    failed.append(record)
    return retry


def _latest_retryable_wish_failures(failed):
    """按条目返回仍可恢复的最新识别失败记录。"""
    latest = {}
    for record in failed or []:
        if not isinstance(record, dict):
            continue
        subject_id = str(record.get("subject_id") or "")
        if not subject_id:
            continue
        latest[subject_id] = record
    return {
        subject_id: record for subject_id, record in latest.items()
        if record.get("reason") == "recognize_failed"
    }


def _clear_wish_failed(failed, subject_id, reason=""):
    """清理指定条目已经恢复成功的失败记录。"""
    target_id = str(subject_id or "")
    return [
        record for record in (failed or [])
        if not (
            isinstance(record, dict)
            and str(record.get("subject_id") or "") == target_id
            and (not reason or record.get("reason") == reason)
        )
    ]


def _subscribe_result_is_failed(result) -> bool:
    """判断订阅调用返回值是否明确表示失败。"""
    if not isinstance(result, dict):
        return False
    status = str(result.get("status") or result.get("result") or "").lower()
    return status in {"failed", "failure", "error"} or (result.get("ok") is False and not result.get("existing"))


def _subscribe_failure_reason(result) -> str:
    """从订阅调用结果中提取失败原因。"""
    if not isinstance(result, dict):
        return "subscribe_failed"
    return str(result.get("reason") or result.get("message") or "subscribe_failed")


def _failed_subscribe_record_count(plugin, mediainfo) -> int:
    """统计当前媒体对应的失败订阅历史记录数量。"""
    count = 0
    for record in storage.read_subscribe_records(plugin):
        if not isinstance(record, dict) or record.get("status") != "failed":
            continue
        if record.get("rank_key") != WISH_RANK_KEY:
            continue
        if str(record.get("tmdbid") or "") == str(getattr(mediainfo, "tmdb_id", "") or ""):
            count += 1
    return count


def _wish_seen_record(item, now):
    """构造已见想看条目的最小记录。"""
    return {"subject_id": str(item.get("subject_id") or ""), "title": item.get("title", ""), "seen_at": now}


def _wish_queue_record(item, now, retry=None):
    """构造待处理想看条目的队列记录。"""
    retry_count = int(item.get("retry", 0) or 0) if retry is None else int(retry or 0)
    return {
        "subject_id": str(item.get("subject_id") or ""),
        "title": item.get("title", ""),
        "year": item.get("year", ""),
        "link": item.get("link", ""),
        "poster": item.get("poster", ""),
        "wish_time": item.get("wish_time", ""),
        "enqueued_at": now,
        "retry": retry_count,
    }


def sync_log_handler(self, event_info, played: bool = False):
    """处理播放事件并同步豆瓣时间线。"""
    play_start = {"playback.start", "media.play", "PlaybackStart"}
    processed = storage.read_folio_data(self)
    self._wait_process = storage.read_folio_wait(self)
    if (event_info.event in play_start and event_info.user_name in self._folio_user.split(',')) or played:
        if played:
            logger.info(f"标记播放完成 {event_info.item_name}")
        media_type = getattr(event_info, "media_type", "")
        if getattr(self, "_folio_exclude_live_tv", True) and utils.is_live_tv_media_type(media_type):
            logger.info(f"电视直播源 {event_info.item_name}（{media_type}）已排除，不同步豆瓣时间")
            return
        ret = utils.exclude_keyword(path=event_info.item_path, keywords=self._folio_exclude)
        if not ret.get("ret", False):
            logger.info(ret.get("message", ""))
            return
        if event_info.item_type == "TV":
            _process_tv_show(self, event_info, processed, played=played)
        elif event_info.item_type == "MOV":
            _process_movie(self, event_info, processed, played=played)


def _event_payload_item(event_info) -> Mapping:
    """读取播放事件中的原始媒体服务器 Item。"""
    payload = getattr(event_info, "json_object", None)
    if not isinstance(payload, Mapping):
        return {}
    item = payload.get("Item")
    return item if isinstance(item, Mapping) else payload


def _provider_identity(provider_ids: Any, source: MediaSource):
    """从原始 ProviderIds 中提取指定来源，绕开宿主单身份优先级。"""
    if not isinstance(provider_ids, Mapping):
        return None, None
    for key in _PROVIDER_KEYS.get(source, ()):
        value = provider_ids.get(key)
        if value not in (None, "") and str(value).strip() not in {"", "0"}:
            return source, str(value).strip()
    return None, None


def _provider_id_from_item(item: Mapping, source: MediaSource):
    """兼容媒体服务器把父级来源 ID平铺在 Item 中的字段。"""
    source, media_id = _provider_identity(item.get("ProviderIds"), source)
    if source and media_id:
        return source, media_id
    names = {
        MediaSource.TMDB: ("TmdbId", "TMDBId", "tmdb_id", "SeriesTmdbId", "SeriesTMDBId"),
        MediaSource.Douban: ("DoubanId", "douban_id", "SeriesDoubanId"),
        MediaSource.Bangumi: ("BangumiId", "bangumi_id", "SeriesBangumiId"),
    }
    for key in names.get(source, ()):
        value = item.get(key)
        if value not in (None, "") and str(value).strip() not in {"", "0"}:
            return source, str(value).strip()
    return None, None


def _event_media_identity(event_info):
    """按原始 Douban、TMDB 和稳定来源顺序提取播放事件身份。"""
    item = _event_payload_item(event_info)

    # WebhookEventInfo.media_source 可能已被宿主按 TMDB 优先级固定；先读原始
    # ProviderIds，确保真实存在的 Douban ID不会被宿主的单身份适配器遮蔽。
    source, media_id = _provider_id_from_item(item, MediaSource.Douban)
    if source and media_id:
        return source, media_id

    direct_source, direct_id = legacy_identity(
        media_source=getattr(event_info, "media_source", None),
        media_id=getattr(event_info, "media_id", None),
    )
    if direct_source == MediaSource.Douban and direct_id:
        return direct_source, direct_id
    if direct_source == MediaSource.TMDB and direct_id:
        return direct_source, direct_id

    # 路径标签通常是整理时写入的主 TMDB ID，优先于 Episode 的 TVDB/IMDb。
    path = str(getattr(event_info, "item_path", None) or item.get("Path") or "")
    match = re.search(r"(?i)(?:\[|\b)tmdbid\s*[:=]\s*(\d+)", path)
    if match:
        return legacy_identity(tmdb_id=match.group(1))

    source, media_id = _provider_id_from_item(item, MediaSource.TMDB)
    if source and media_id:
        return source, media_id

    # 保留宿主已选的其它稳定来源，最后才使用其固定优先级结果。
    if direct_source and direct_id:
        return direct_source, direct_id
    source, media_id = MediaServerIdentityHelper.from_provider_ids(item.get("ProviderIds"))
    if source and media_id:
        return source, media_id
    return None, None


def _series_payload_item(event_info) -> Mapping:
    """读取 Webhook 中可能携带的父级 Series 对象。"""
    item = _event_payload_item(event_info)
    for key in ("Series", "SeriesItem", "Parent", "SeriesInfo"):
        candidate = item.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    return {}


def _server_names_for_event(event_info) -> list[str]:
    """返回查询父级 Series 时可尝试的媒体服务器名称。"""
    payload = getattr(event_info, "json_object", None)
    names = [
        getattr(event_info, "server_name", None),
        payload.get("ServerName") if isinstance(payload, Mapping) else None,
        payload.get("source") if isinstance(payload, Mapping) else None,
    ]
    try:
        names.extend(MediaServerHelper().get_services().keys())
    except Exception:
        pass
    result = []
    for name in names:
        value = str(name or "").strip()
        if value and value not in result:
            result.append(value)
    return result


def _series_context(plugin, event_info) -> dict:
    """取得父级 Series 的标题、首播年份和媒体身份。"""
    item = _event_payload_item(event_info)
    parent = _series_payload_item(event_info)
    title = (
        parent.get("Name") or parent.get("name") or item.get("SeriesName")
        or item.get("SeriesNamePrimary") or ""
    )
    year = (
        parent.get("ProductionYear") or parent.get("Year") or parent.get("year")
        or item.get("SeriesProductionYear") or item.get("SeriesYear")
    )
    source, media_id = _provider_id_from_item(parent, MediaSource.Douban)
    if not source:
        source, media_id = _provider_id_from_item(parent, MediaSource.TMDB)
    if not source:
        source, media_id = _provider_id_from_item(parent, MediaSource.Bangumi)

    series_id = getattr(event_info, "item_id", None) or item.get("SeriesId")
    if series_id:
        cache = getattr(plugin, FOLIO_SERIES_CACHE_KEY, None)
        if not isinstance(cache, dict):
            cache = {}
        server_names = _server_names_for_event(event_info)
        cache_key = (tuple(server_names), str(series_id))
        cached = cache.get(cache_key)
        if cached is None:
            cached = None
            try:
                chain = MediaServerChain()
                for server in server_names:
                    result = chain.iteminfo(server=server, item_id=str(series_id))
                    if result:
                        cached = result
                        break
            except Exception as err:
                logger.debug(f"查询父级 Series 失败 {series_id}：{err}")
            cache[cache_key] = cached or {}
            setattr(plugin, FOLIO_SERIES_CACHE_KEY, cache)
        if cached:
            title = _value_from_mapping(cached, "title", "name") or title
            year = _value_from_mapping(cached, "year", "first_air_date", "release_date") or year
            if isinstance(year, str):
                year_match = re.search(r"(?:19|20)\d{2}", year)
                year = year_match.group(0) if year_match else year
            cached_source, cached_id = identity_from_media(cached)
            if cached_source and cached_id and source != MediaSource.Douban:
                source, media_id = cached_source, cached_id

    if isinstance(year, str):
        year_match = re.search(r"(?:19|20)\d{2}", year)
        year = year_match.group(0) if year_match else year
    return {
        "title": str(title or "").strip(),
        "year": str(year or "").strip(),
        "media_source": source,
        "media_id": media_id,
    }


def _process_tv_show(self, event_info, processed: Dict, played: bool = False):
    context = _series_context(self, event_info)
    item_name = str(getattr(event_info, "item_name", None) or "")
    idx = item_name.find(" S")
    title = context["title"] or (item_name[:idx] if idx >= 0 else item_name)
    season_id, episode_id = map(int, [event_info.season_id, event_info.episode_id])
    media_source = context.get("media_source")
    media_id = context.get("media_id")
    if not media_source or not media_id:
        media_source, media_id = _event_media_identity(event_info)
    if not played:
        logger.info(f"开始播放 {title} 第{season_id}季 第{episode_id}集")
    meta = MetaInfo(title)
    meta.begin_season = season_id
    meta.type = MediaType("电视剧")
    if context.get("year"):
        meta.year = context["year"]
    mediainfo = _recognize_media(meta, media_source=media_source, media_id=media_id)
    if mediainfo and not _recognized_media_matches_meta(mediainfo, meta):
        logger.warning(
            f"父级 Series 识别结果年份不匹配：{title} {meta.year} -> "
            f"{getattr(mediainfo, 'title', '')} {getattr(mediainfo, 'year', '')}"
        )
        mediainfo = None
    if not mediainfo:
        logger.warning(f'标题：{title}，媒体身份：{media_source}/{media_id}，尝试仅使用标题识别')
        meta.tmdbid = None
        mediainfo = _recognize_title_media(meta)
        if not mediainfo:
            logger.error('仍然未识别到媒体信息')
            return
    origin = _playback_origin(mediainfo, "TV", season_id)
    library_context = folio_library.playback_context(event_info)
    noted_library_time = False
    if library_context:
        origin["mediaserver"] = library_context
        if folio_record.library_key(origin):
            folio_watch.observe(self, origin, event_info, processed, played=played)
            noted_library_time = True
        library = folio_library.load_season(self, origin)
        if not library:
            origin["library_season"] = {}
            wait_key, _ = folio_record.find_record(self._wait_process or {}, origin, title)
            _save_waiting_playback(self, wait_key, title, "do", event_info.item_type, origin,
                                   {"resolved": False, "reason": "实际媒体库分季暂不可核验"})
            return
        origin = folio_library.bind_season(origin, library)
    if not noted_library_time:
        folio_watch.observe(self, origin, event_info, processed, played=played)
    if episode_id < 2 and self._folio_first:
        logger.info("已记录首次播放时间，第1集活动不同步到豆瓣档案")
        return
    episodes = mediainfo.seasons.get(season_id, mediainfo.seasons.get(str(season_id), []))
    if library_context:
        episodes = origin["library_season"]["episode_numbers"]
    title = utils.format_title(title, season_id)
    # 开始播放末集只证明在看；实际库内季的看过由明确已看事件推进。
    finished = bool(episodes) and episode_id == max(episodes)
    status = "collect" if finished and (played or not library_context) else "do"
    _, previous = folio_record.find_record(processed, origin, title)
    if (folio_record.origin_key(previous.get("origin") or {}) == folio_record.origin_key(origin)
            and folio_record.already_synced(previous, status)):
        logger.info(f"{title} 相同播放身份已同步，不重复处理")
        return
    if _sync_to_douban(self, title, status, event_info.item_type, processed, mediainfo, origin=origin):
        logger.info("尝试同步之前同步失败的条目")
        self._wait_process = storage.read_folio_wait(self)
        for k, v in list(self._wait_process.items()):
            retry_title = v.get("display_title") or v.get("subject_name") or k
            logger.info(f"尝试同步: {retry_title}")
            _sync_to_douban(self, retry_title, v["status"], v["type"], processed, None, origin=v.get("origin"))


def _process_movie(self, event_info, processed: Dict, played: bool = False):
    title = event_info.item_name
    if not played:
        logger.info(f"开始播放 {title}")
    meta = MetaInfo(title)
    meta.type = MediaType("电影")
    media_source, media_id = _event_media_identity(event_info)
    mediainfo = _recognize_media(meta, media_source=media_source, media_id=media_id)
    if not mediainfo:
        logger.warning(f'标题：{title}，媒体身份：{media_source}/{media_id}，尝试仅使用标题识别')
        meta.tmdbid = None
        mediainfo = _recognize_media(meta)
        if not mediainfo:
            logger.error('仍然未识别到媒体信息')
            return
    origin = _playback_origin(mediainfo, "MOV")
    _, previous = folio_record.find_record(processed, origin, title)
    if previous:
        logger.info(f"{title} 已同步到豆瓣在看，不处理")
        return
    _sync_to_douban(self, title, "collect", event_info.item_type, processed, mediainfo, origin=origin)


def _playback_origin(mediainfo, media_type: str, season=None) -> dict:
    """保存播放器实际使用的媒体身份、季号和剧集组。"""
    source, media_id = identity_from_media(mediainfo)
    return {
        "media_source": getattr(source, "value", source) or "",
        "media_id": str(media_id or ""),
        "type": folio_record.media_kind(media_type),
        "season": season,
        "episode_group": str(getattr(mediainfo, "episode_group", None) or ""),
    }


def _recognize_media(
    meta,
    media_source=None,
    media_id=None,
    tmdb_id: Optional[int] = None,
):
    """通过 V3 媒体身份对识别豆瓣时间条目。"""
    return recognize_media(
        MediaChain(),
        meta=meta,
        mtype=meta.type,
        media_source=media_source,
        media_id=media_id,
        tmdb_id=tmdb_id,
        cache=True,
    )


def _recognized_media_matches_meta(mediainfo, meta) -> bool:
    """校验识别结果的类型、标题和父级年份。"""
    expected_type = getattr(meta, "type", None)
    actual_type = getattr(mediainfo, "type", None)
    if expected_type and actual_type and actual_type != expected_type:
        return False
    expected_year = str(getattr(meta, "year", None) or "").strip()
    actual_year = str(getattr(mediainfo, "year", None) or "").strip()
    if expected_year and actual_year and expected_year != actual_year[:4]:
        return False
    expected_title = _normalize_subject_title(getattr(meta, "title", ""))
    actual_title = _normalize_subject_title(getattr(mediainfo, "title", ""))
    return not expected_title or not actual_title or expected_title == actual_title


def _recognize_title_media(meta):
    """按标题、年份和类型筛选媒体候选，歧义时拒绝盲选。"""
    try:
        candidates = MediaChain().search_medias(meta, media_source=MediaSource.TMDB) or []
    except Exception as err:
        logger.debug(f"标题候选搜索不可用，回退标准识别：{err}")
        return _recognize_media(meta)

    valid = [candidate for candidate in candidates if _recognized_media_matches_meta(candidate, meta)]
    unique = []
    seen = set()
    for candidate in valid:
        source, media_id = identity_from_media(candidate)
        identity = (str(source or ""), str(media_id or ""))
        if identity == ("", "") or identity in seen:
            continue
        seen.add(identity)
        unique.append(candidate)
    if len(unique) == 1:
        return unique[0]
    if len(unique) > 1:
        logger.warning(
            f"标题识别存在多个同名同年候选，拒绝盲选：{getattr(meta, 'title', '')} {getattr(meta, 'year', '')}"
        )
        return None
    return _recognize_media(meta)


def _normalize_subject_title(value: str) -> str:
    """清理年份、季号和标点，生成豆瓣条目标题比较键。"""
    text = str(value or "").strip()
    text = re.sub(r"\s*[（(]?\s*(?:19|20)\d{2}\s*[）)]?\s*$", "", text)
    text = re.sub(r"\s*(?:第\s*\d+\s*季|第\s*[一二三四五六七八九十]+\s*季|S\s*\d+|Season\s*\d+)\s*$", "", text, flags=re.IGNORECASE)
    return re.sub(r"[^0-9A-Za-z\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+", "", text).casefold()


def _subject_title_matches(query: str, candidate: str) -> bool:
    """判断豆瓣搜索候选是否与目标主标题精确对应。"""
    query_key = _normalize_subject_title(query)
    candidate_key = _normalize_subject_title(candidate)
    return bool(query_key and candidate_key and query_key == candidate_key)


def _media_type_for_douban(media_type: str) -> MediaType:
    """把媒体服务器类型转换为 V3 豆瓣链媒体类型。"""
    value = str(media_type or "").strip().upper()
    return MediaType.TV if value in {"TV", "电视剧", "剧集", "SERIES"} else MediaType.MOVIE


def _media_season(title: str, mediainfo=None) -> Optional[int]:
    """提取跨源转换需要的剧集季号。"""
    explicit = re.search(r"(?:第\s*(\d+)\s*季|\bS(\d+)\b)", title, re.IGNORECASE)
    value = next((part for part in explicit.groups() if part), None) if explicit else None
    if value is None:
        value = getattr(mediainfo, "season", None) if mediainfo is not None else None
    if value is None:
        value = getattr(MetaInfo(title), "begin_season", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _value_from_mapping(value, *keys):
    """从字典或对象读取第一个非空字段。"""
    for key in keys:
        current = value.get(key) if isinstance(value, Mapping) else getattr(value, key, None)
        if current not in (None, ""):
            return current
    return None


def _poster_from_douban(value) -> str:
    """从豆瓣转换结果或媒体对象中提取海报地址。"""
    direct = _value_from_mapping(value, "poster_path", "cover_url", "image", "poster")
    if direct:
        return str(direct)
    for key in ("pic", "cover", "cover_img"):
        nested = _value_from_mapping(value, key)
        if isinstance(nested, Mapping):
            poster = _value_from_mapping(nested, "large", "normal", "url")
            if poster:
                return str(poster)
    return ""


def _is_douban_poster_url(value: str) -> bool:
    """识别旧档案中的豆瓣原图地址。"""
    host = (urlparse(str(value or "")).hostname or "").lower().rstrip(".")
    return bool(re.fullmatch(r"img\d*\.doubanio\.com", host))


def _poster_from_tmdb_media(value) -> str:
    """仅从明确拥有 TMDB 身份的媒体对象提取海报。"""
    source, media_id = identity_from_media(value)
    poster = _value_from_mapping(value, "poster_path", "poster", "image")
    if source == MediaSource.TMDB and media_id and poster:
        return str(poster)
    return ""


def _canonical_douban_id_from_poster(poster: str, current_id: str = "") -> str:
    """只修复已核实的真人版错配，不从共用海报推断任意分季身份。"""
    if str(current_id) != "35861087":
        return ""
    normalized = str(poster or "").split("?", 1)[0].rstrip("/")
    if not normalized:
        return ""
    for douban_id, fallback in _FOLIO_TMDB_POSTER_FALLBACKS.items():
        expected = str(fallback.get("poster_path") or "").split("?", 1)[0].rstrip("/")
        if douban_id == "34925294" and expected and normalized == expected:
            return str(douban_id)
    return ""


def _douban_match_from_identity(title: str, media_type: str, mediainfo=None):
    """用已确认的媒体身份转换豆瓣条目，不成功时不退化为标题搜索。"""
    source, media_id = identity_from_media(mediainfo) if mediainfo is not None else (None, None)
    if not source or not media_id:
        return None, None, "", False
    if source == MediaSource.Douban:
        return (
            _value_from_mapping(mediainfo, "title", "name") or title,
            str(media_id),
            _poster_from_douban(mediainfo),
            True,
        )
    chain = MediaChain()
    season = _media_season(title, mediainfo)
    conversion_kwargs = {
        "target_source": MediaSource.Douban,
        "media_source": source,
        "media_id": str(media_id),
        "mtype": _media_type_for_douban(media_type),
        "season": season,
    }
    try:
        converted = chain.convert_media_identity(**conversion_kwargs)
        if not converted and season is not None:
            logger.info(f"{title} 未匹配到分季豆瓣条目，尝试复用整剧媒体身份")
            conversion_kwargs["season"] = None
            converted = chain.convert_media_identity(**conversion_kwargs)
    except Exception as err:
        logger.warning(f"{title} 媒体身份转换豆瓣失败：{err}")
        return None, None, "", True
    subject_id = _value_from_mapping(converted, "id", "douban_id", "doubanid", "media_id")
    if not subject_id:
        return None, None, "", True
    return (
        _value_from_mapping(converted, "title", "name") or title,
        str(subject_id),
        _poster_from_douban(converted),
        True,
    )


def _load_douban_media(subject_id: str, title: str, media_type: str):
    """按豆瓣 subject ID 回读媒体详情，用于补齐正式名称和海报。"""
    meta = MetaInfo(title)
    meta.type = _media_type_for_douban(media_type)
    try:
        return _recognize_media(
            meta,
            media_source=MediaSource.Douban,
            media_id=str(subject_id),
        )
    except Exception as err:
        logger.warning(f"回读豆瓣 subject {subject_id} 详情失败：{err}")
        return None


def _load_tmdb_media(tmdb_id: str, title: str, media_type: str, year: str = ""):
    """按 TMDB ID 回读媒体详情，用于取得官方 TMDB 海报。"""
    meta = MetaInfo(title)
    meta.type = _media_type_for_douban(media_type)
    if year:
        meta.year = str(year)
    try:
        return _recognize_media(
            meta,
            media_source=MediaSource.TMDB,
            media_id=str(tmdb_id),
        )
    except Exception as err:
        logger.warning(f"回读 TMDB {tmdb_id} 详情失败：{err}")
        return None


def _tmdb_poster_for_record(self, title: str, record: Mapping, detail=None) -> str:
    """把豆瓣时间记录转换为 TMDB 海报，失败时使用已核对的精确兜底。"""
    if record.get("identity_status") == "verified" and record.get("origin"):
        # 经分季核验后只复用该季的图片依据，不能退回首部的固定海报。
        return str((record.get("season_facts") or {}).get("poster_path") or "")
    source, media_id = identity_from_media(record)
    if not source or not media_id:
        return ""

    # 已经核对过的历史记录直接使用固定 TMDB 地址，避免恢复过程再次受标题、
    # 年份或第三方转换服务波动影响。
    fallback = _FOLIO_TMDB_POSTER_FALLBACKS.get(str(media_id)) if source == MediaSource.Douban else None
    if fallback:
        logger.info(f"{title} 使用已核对的 TMDB 海报：{fallback['tmdb_id']}")
        return fallback["poster_path"]

    subject_name = str(record.get("subject_name") or title)
    media_type = str(record.get("type") or "TV")
    year = str(record.get("year") or "")
    detail_source, detail_id = identity_from_media(detail) if detail is not None else (None, None)
    tmdb_id = (
        str(detail_id)
        if detail_source == MediaSource.TMDB and detail_id
        else str(media_id) if source == MediaSource.TMDB else ""
    )
    if source == MediaSource.Douban and not (detail_source == MediaSource.TMDB and detail_id):
        try:
            converted_source, converted_id = convert_identity(
                MediaChain(),
                target_source=MediaSource.TMDB,
                media_source=source,
                media_id=media_id,
                mtype=_media_type_for_douban(media_type),
                season=_media_season(subject_name, detail),
            )
        except Exception as err:
            logger.warning(f"{title} 豆瓣 ID {media_id} 转换 TMDB 失败：{err}")
            converted_source, converted_id = None, None
        if converted_source == MediaSource.TMDB and converted_id:
            tmdb_id = str(converted_id)

    if tmdb_id:
        tmdb_media = _load_tmdb_media(tmdb_id, subject_name, media_type, year=year)
        poster = _poster_from_tmdb_media(tmdb_media)
        if poster:
            return poster

    return ""


def _resolve_douban_subject(self, title: str, media_type: str, mediainfo=None, api=None):
    """按身份转换、失败记录和严格标题搜索顺序解析豆瓣 subject。"""
    name, subject_id, poster, had_identity = _douban_match_from_identity(title, media_type, mediainfo)
    if subject_id:
        return name, subject_id, poster

    wait_record = (self._wait_process or {}).get(title) or {}
    wait_source, wait_id = legacy_identity(
        media_source=wait_record.get("media_source"),
        media_id=wait_record.get("media_id"),
        douban_id=wait_record.get("subject_id"),
    )
    subject_id = str(wait_id or "") if wait_source == MediaSource.Douban else ""
    if subject_id:
        name = wait_record.get("subject_name") or title
        poster = wait_record.get("poster_path") or wait_record.get("poster") or ""
        return name, subject_id, poster

    if had_identity:
        logger.warning(f"{title} 已有媒体身份但未转换出豆瓣 ID，跳过标题兜底")
        return None, None, ""

    dh = api or DoubanApi(user_cookie=self._folio_cookie)
    search = f"{title} {getattr(mediainfo, 'year', '')}".strip() if mediainfo and getattr(mediainfo, "year", None) else title
    name, subject_id = dh.get_subject_id(title=search)
    if not subject_id and search != title:
        logger.info(f"带年份搜索无结果，回退到原标题: {title}")
        name, subject_id = dh.get_subject_id(title=title)
    if subject_id and not _subject_title_matches(title, name):
        logger.warning(f"豆瓣候选标题不匹配，拒绝写入：{title} -> {name}")
        return None, None, ""
    return name, subject_id, ""


def _validated_playback_subject(title, mediainfo, origin, previous, waiting):
    """已核验的季身份可复用，否则先执行严格分季匹配。"""
    for record in (previous, waiting):
        if (record.get("identity_status") == "verified"
                and (not folio_record.library_key(origin) or record.get("identity_scope") == "library_season")
                and folio_record.origin_key(record.get("origin") or {}) == folio_record.origin_key(origin)
                and record.get("subject_id")):
            return {
                "resolved": True, "subject_id": str(record["subject_id"]),
                "subject_name": record.get("subject_name") or title,
                "poster_path": record.get("poster_path") or (record.get("season_facts") or {}).get("poster_path") or "",
                 "identity_scope": record.get("identity_scope") or "season",
                "related_subjects": record.get("related_subjects") or [],
                "facts": record.get("season_facts") or {},
            }
    try:
        chain = MediaChain()
        if mediainfo is None:
            mediainfo = folio_media.load_playback_media(chain, origin, title)
        if mediainfo is None:
            return {"resolved": False, "reason": "缺少可核验的原始播放媒体"}
        return folio_media.resolve_tv_subject(chain, mediainfo, origin)
    except (folio_media.FolioLookupError, ValueError, TypeError, AttributeError) as err:
        logger.warning(f"{title} 分季媒体查询失败：{type(err).__name__}", exc_info=True)
        return {"resolved": False, "reason": "分季媒体查询失败，等待后续重试"}


def _save_waiting_playback(self, key, title, status, media_type, origin, verified, poster=""):
    """按播放身份保留待重试项，不让后来的在看事件覆盖看过状态。"""
    self._wait_process = self._wait_process or {}
    previous = self._wait_process.get(key) or {}
    record = {
        **previous, "display_title": title,
        "status": "collect" if previous.get("status") == "collect" else status,
        "type": media_type,
    }
    if origin:
        record["origin"] = dict(origin)
    if verified:
        record["identity_status"] = "verified" if verified.get("resolved") else "unresolved"
        record["identity_reason"] = verified.get("reason") or ""
        record["season_facts"] = verified.get("facts") or {}
    if verified.get("resolved"):
        record.update({
            "subject_id": str(verified["subject_id"]),
            "subject_name": verified["subject_name"],
            "media_source": MediaSource.Douban.value,
            "media_id": str(verified["subject_id"]),
            "identity_scope": verified["identity_scope"], "poster_path": poster,
        })
    self._wait_process[key] = record
    storage.save_folio_wait(self, self._wait_process)


def _sync_to_douban(
    self, title: str, status: str, mediaType: str, processed: Dict, mediainfo=None, *, origin=None,
) -> bool:
    """按播放身份核验并同步，未确认的剧集季禁止写入豆瓣。"""
    logger.info(f"开始尝试获取 {title} 豆瓣id")
    is_tv = folio_record.media_kind(mediaType) == "tv"
    if is_tv and not origin and mediainfo is not None:
        origin = _playback_origin(mediainfo, mediaType, _media_season(title, mediainfo) or 1)
    if is_tv and not folio_record.origin_key(origin or {}):
        logger.warning(f"{title} 缺少原始播放身份，保留旧待重试条目，暂不写入豆瓣")
        return False
    record_key, previous = folio_record.find_record(processed, origin or {}, title)
    if previous.get("identity_scope") == "library_season" and not folio_record.library_key(origin or {}):
        # 已修复的真实季接管旧 Cours 待重试项，不能重新写回旧分组身份。
        origin = previous["origin"]
    if (origin and not origin.get("library_season")
            and (origin.get("mediaserver") or (is_tv and mediainfo is None))):
        # 旧重试没有服务器字段时也先查唯一库内季，避免新旧剧集组各写一条。
        library = folio_library.load_season(self, origin, refresh=True)
        if not library and origin.get("mediaserver"):
            wait_key, _ = folio_record.find_record(self._wait_process or {}, origin, title)
            _save_waiting_playback(self, wait_key, title, status, mediaType, origin,
                                   {"resolved": False, "reason": "实际媒体库分季暂不可核验"})
            return False
        if library:
            origin = folio_library.bind_season(origin, library)
            record_key, previous = folio_record.find_record(processed, origin, title)
    wait_key, waiting = folio_record.find_record(self._wait_process or {}, origin or {}, title)
    same_waiting_origin = folio_record.origin_key(waiting.get("origin") or {}) == folio_record.origin_key(origin or {})
    if waiting.get("status") == "collect" and same_waiting_origin:
        status = "collect"
    if (origin and folio_record.origin_key(previous.get("origin") or {}) == folio_record.origin_key(origin)
            and folio_record.already_synced(previous, status)):
        return True
    dh = DoubanApi(user_cookie=self._folio_cookie)
    verified = {}
    if is_tv:
        verified = _validated_playback_subject(title, mediainfo, origin, previous, waiting)
        if not verified.get("resolved"):
            logger.warning(f"{title} 分季身份待核实，暂不写入豆瓣：{verified.get('reason', '')}")
            _save_waiting_playback(self, wait_key, title, status, mediaType, origin, verified)
            return False
        name, sid, poster = verified["subject_name"], verified["subject_id"], verified.get("poster_path", "")
    else:
        name, sid, poster = _resolve_douban_subject(self, title, mediaType, mediainfo, api=dh)
    if sid and not poster:
        detail = _load_douban_media(sid, name or title, mediaType)
        if detail:
            name = _value_from_mapping(detail, "title", "name") or name or title
            poster = _poster_from_douban(detail)
    # 已核验条目优先使用各自的豆瓣海报，缺图时沿用 TMDB 回退。
    poster = verified.get("poster_path") or _FOLIO_TMDB_POSTER_FALLBACKS.get(str(sid), {}).get("poster_path", "")
    if not poster:
        poster = _poster_from_tmdb_media(mediainfo)
    if not poster:
        poster = _tmdb_poster_for_record(
            self,
            title,
            {
                "media_source": MediaSource.Douban.value,
                "media_id": str(sid or ""),
                "subject_name": name or title,
                "type": mediaType,
            },
            detail=mediainfo,
        )
    if sid:
        logger.info(f"查询：{title} => 匹配豆瓣：{name}")
        if dh.set_watching_status(subject_id=sid, status=status, private=self._folio_private):
            record = {
                **previous,
                "subject_id": sid, "subject_name": name or title,
                "media_source": MediaSource.Douban.value, "media_id": str(sid),
                **folio_watch.sync_fields(self, origin or {}, previous),
                "poster_path": poster,
                "type": "电视剧" if is_tv else "电影",
                "watch_status": status,
            }
            if origin:
                record["origin"] = dict(origin)
                record["display_title"] = (folio_record.library_title(name or title)
                                           if folio_record.library_key(origin) else name or title)
            if verified:
                record.update({
                    "identity_status": "verified", "identity_scope": verified["identity_scope"],
                    "season_facts": verified.get("facts") or {},
                    "related_subjects": verified.get("related_subjects") or [],
                    "season_label": f"第{origin['season']}季" if origin.get("season") is not None else "",
                })
            processed[record_key] = record
            if wait_key in (self._wait_process or {}):
                del self._wait_process[wait_key]
            storage.save_folio_data(self, processed)
            storage.save_folio_wait(self, self._wait_process)
            logger.info(f"{title} 同步到档案成功")
            _send_folio_notification(self, True, f"《{title}》已成功同步到豆瓣档案。")
            return True
        logger.error(f'{title} 同步到档案失败')
        if verified:
            _save_waiting_playback(self, wait_key, title, status, mediaType, origin, verified, poster)
        else:
            self._wait_process = self._wait_process or {}
            self._wait_process[wait_key] = {
                "subject_id": sid,
                "subject_name": name or title,
                "media_source": MediaSource.Douban.value,
                "media_id": str(sid),
                "status": status,
                "poster_path": poster,
                "type": mediaType,
            }
            if origin:
                self._wait_process[wait_key]["origin"] = dict(origin)
            storage.save_folio_wait(self, self._wait_process)
        logger.error(f'{title} 添加到待同步列表')
        _send_folio_notification(self, False, f"《{title}》同步到豆瓣档案失败")
    else:
        logger.warning(f"获取 {title} subject_id 失败")
    return False


def repair_folio_history(self) -> int:
    """修复豆瓣时间线中可确认的标题、身份和海报缺失。"""
    data = storage.read_folio_data(self)
    if not isinstance(data, dict):
        return 0
    changed = 0
    for title, record in data.items():
        if not isinstance(record, dict):
            continue
        media_type = str(record.get("type") or "TV")
        source, media_id = identity_from_media(record)
        if source != MediaSource.Douban or not media_id:
            continue

        subject_name = str(record.get("subject_name") or title)
        poster = str(record.get("poster_path") or "")
        detail = None
        if not poster or (_is_douban_poster_url(poster) and record.get("identity_status") != "verified"):
            poster = _tmdb_poster_for_record(self, title, record)
            if not poster:
                detail = _load_douban_media(str(media_id), subject_name, media_type)
                subject_name = _value_from_mapping(detail, "title", "name") or subject_name
                poster = _tmdb_poster_for_record(self, title, record, detail=detail)

        # 共用整剧海报不是分季身份凭据；只保留已核实的历史错配修正。
        canonical_douban_id = (
            _canonical_douban_id_from_poster(poster, str(media_id))
            if record.get("identity_status") != "verified" else ""
        )
        if canonical_douban_id:
            media_id = canonical_douban_id

        updates = {
            "subject_id": str(media_id),
            "subject_name": subject_name,
            "media_source": MediaSource.Douban.value,
            "media_id": str(media_id),
            "poster_path": poster,
        }
        record_changed = False
        for key, value in updates.items():
            if value and record.get(key) != value:
                record[key] = value
                record_changed = True
        if record_changed:
            changed += 1
    if changed:
        storage.save_folio_data(self, data)
        logger.info(f"豆瓣时间线历史数据修复完成，更新 {changed} 条记录")
    return changed


def _send_folio_notification(self, success: bool, message: str):
    if not self._folio_notify:
        return
    t = f"豆瓣观影档案 {'成功' if success else '失败'}"
    msg = message.strip() + f"\n时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        self.post_message(mtype=MessageType.MediaServer, title=t, text=msg, parse_mode="plain")
    except Exception as e:
        logger.error(f'{self.plugin_name} 发送通知失败: {e}')


def _send_wish_notification(self, message: str, throttle_key: str = "wish", throttle_seconds: int = WISH_NOTIFY_THROTTLE_SECONDS):
    """通过同步想看通知开关发送失败消息，并按类型节流。"""
    if not getattr(self, "_wish_notify", False):
        return
    now_ts = datetime.datetime.now().timestamp()
    last_map = getattr(self, "_wish_notification_last_times", None)
    if not isinstance(last_map, dict):
        last_map = {}
    last_ts = float(last_map.get(throttle_key, 0) or 0)
    if throttle_seconds and now_ts - last_ts < throttle_seconds:
        return
    last_map[throttle_key] = now_ts
    self._wish_notification_last_times = last_map
    msg = message.strip() + f"\n时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        self.post_message(mtype=MessageType.MediaServer, title="豆瓣想看同步失败", text=msg, parse_mode="plain")
    except Exception as e:
        logger.error(f'{self.plugin_name} 发送同步想看通知失败: {e}')
