"""
DoubanCenter - 豆瓣档案模块
"""
import datetime
import re
import threading
from collections.abc import Mapping
from typing import Dict, Optional

from app.chain.media import MediaChain
from app.sdk.logging import logger
from app.sdk.media import MetaInfo
from app.schemas.types import MediaSource, MediaType, NotificationType
# MoviePilot V3 953e084cec85 当前尚未从 SDK 导出媒体服务器 ProviderIds 适配器。
from app.application.mediaserver import MediaServerIdentityHelper

from . import utils
from .doubanapi import DoubanApi
from .model.identity import identity_from_media, legacy_identity, recognize_media
from .storage import records as storage

WISH_NOTIFY_THROTTLE_SECONDS = 6 * 60 * 60
WISH_RECOGNIZE_MAX_RETRIES = 3


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
    def recognize(title, year):
        """识别想看条目对应的媒体信息。"""
        meta = MetaInfo(_wish_recognize_title(title))
        if year:
            meta.year = str(year)
        return MediaChain().recognize_by_meta(meta)
    return recognize


def process_wish_queue(self, recognize=None, subscribe=None) -> None:
    """处理想看待订阅队列，识别后通过现有订阅链创建订阅。"""
    queue = storage.read_folio_wish_queue(self)
    if not queue:
        return
    processed = storage.read_folio_wish_processed(self)
    failed = storage.read_folio_wish_failed(self)
    state = storage.read_folio_wish_state(self)
    recognizer = recognize or _default_wish_recognize(self)
    subscriber = subscribe
    if subscriber is None:
        from .service import subscription as subscription_service
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
            mediainfo = recognizer(title, year)
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


def _event_media_identity(event_info):
    """按播放事件的可靠性顺序提取完整媒体身份。"""
    source, media_id = legacy_identity(
        media_source=getattr(event_info, "media_source", None),
        media_id=getattr(event_info, "media_id", None),
    )
    if source and media_id:
        return source, media_id

    source, media_id = legacy_identity(tmdb_id=getattr(event_info, "tmdb_id", None))
    if source and media_id:
        return source, media_id

    payload = getattr(event_info, "json_object", None)
    if isinstance(payload, Mapping):
        provider_ids = payload.get("ProviderIds")
        item = payload.get("Item")
        if not isinstance(provider_ids, Mapping) and isinstance(item, Mapping):
            provider_ids = item.get("ProviderIds")
        source, media_id = MediaServerIdentityHelper.from_provider_ids(provider_ids)
        if source and media_id:
            return source, media_id

    path = str(getattr(event_info, "item_path", None) or "")
    match = re.search(r"(?i)(?:\[|\b)tmdbid\s*[:=]\s*(\d+)", path)
    if match:
        return legacy_identity(tmdb_id=match.group(1))
    return None, None


def _process_tv_show(self, event_info, processed: Dict, played: bool = False):
    idx = event_info.item_name.index(" S")
    title = event_info.item_name[:idx]
    season_id, episode_id = map(int, [event_info.season_id, event_info.episode_id])
    media_source, media_id = _event_media_identity(event_info)
    if not played:
        logger.info(f"开始播放 {title} 第{season_id}季 第{episode_id}集")
    if episode_id < 2 and self._folio_first:
        logger.info("剧集第1集的活动不同步到豆瓣档案，跳过")
        return
    meta = MetaInfo(title)
    meta.begin_season = season_id
    meta.type = MediaType("电视剧")
    mediainfo = _recognize_media(meta, media_source=media_source, media_id=media_id)
    if not mediainfo:
        logger.warning(f'标题：{title}，媒体身份：{media_source}/{media_id}，尝试仅使用标题识别')
        meta.tmdbid = None
        mediainfo = _recognize_media(meta)
        if not mediainfo:
            logger.error('仍然未识别到媒体信息')
            return
    episodes = mediainfo.seasons.get(season_id, [])
    title = utils.format_title(title, season_id)
    status = "collect" if len(episodes) == episode_id else "do"
    if processed.get(title) and len(episodes) != episode_id:
        logger.info(f"{title} 已同步到豆瓣在看，不处理")
        return
    if _sync_to_douban(self, title, status, event_info.item_type, processed, mediainfo):
        logger.info("尝试同步之前同步失败的条目")
        self._wait_process = storage.read_folio_wait(self)
        for k, v in list(self._wait_process.items()):
            logger.info(f"尝试同步: {k}")
            _sync_to_douban(self, k, v["status"], v["type"], processed, None)


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
    if processed.get(title):
        logger.info(f"{title} 已同步到豆瓣在看，不处理")
        return
    _sync_to_douban(self, title, "collect", event_info.item_type, processed, mediainfo)


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
    return MediaType.TV if str(media_type or "").upper() == "TV" else MediaType.MOVIE


def _media_season(title: str, mediainfo=None) -> Optional[int]:
    """提取跨源转换需要的剧集季号。"""
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
    try:
        converted = chain.convert_media_identity(
            target_source=MediaSource.Douban,
            media_source=source,
            media_id=str(media_id),
            mtype=_media_type_for_douban(media_type),
            season=_media_season(title, mediainfo),
        )
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


def _sync_to_douban(self, title: str, status: str, mediaType: str, processed: Dict, mediainfo=None) -> bool:
    """解析并写入豆瓣观看状态，优先复用身份和已有 subject。"""
    logger.info(f"开始尝试获取 {title} 豆瓣id")
    dh = DoubanApi(user_cookie=self._folio_cookie)
    name, sid, poster = _resolve_douban_subject(self, title, mediaType, mediainfo, api=dh)
    if sid and not poster:
        detail = _load_douban_media(sid, name or title, mediaType)
        if detail:
            name = _value_from_mapping(detail, "title", "name") or name or title
            poster = _poster_from_douban(detail)
    poster = poster or (getattr(mediainfo, "poster_path", "") if mediainfo else "")
    if sid:
        logger.info(f"查询：{title} => 匹配豆瓣：{name}")
        if dh.set_watching_status(subject_id=sid, status=status, private=self._folio_private):
            processed[title] = {
                "subject_id": sid, "subject_name": name or title,
                "media_source": MediaSource.Douban.value, "media_id": str(sid),
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "poster_path": poster,
                "type": "电视剧" if mediaType == "TV" else "电影"
            }
            if title in (self._wait_process or {}):
                del self._wait_process[title]
            storage.save_folio_data(self, processed)
            storage.save_folio_wait(self, self._wait_process)
            logger.info(f"{title} 同步到档案成功")
            _send_folio_notification(self, True, f"《{title}》已成功同步到豆瓣档案。")
            return True
        logger.error(f'{title} 同步到档案失败')
        if title not in (self._wait_process or {}):
            self._wait_process[title] = {
                "subject_id": sid,
                "subject_name": name or title,
                "media_source": MediaSource.Douban.value,
                "media_id": str(sid),
                "status": status,
                "poster_path": poster,
                "type": mediaType,
            }
            storage.save_folio_wait(self, self._wait_process)
            logger.error(f'{title} 添加到待同步列表')
        _send_folio_notification(self, False, f"《{title}》同步到豆瓣档案失败")
    else:
        logger.warning(f"获取 {title} subject_id 失败")
    return False


def _send_folio_notification(self, success: bool, message: str):
    if not self._folio_notify:
        return
    t = f"豆瓣观影档案 {'成功' if success else '失败'}"
    msg = message.strip() + f"\n时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        self.post_message(mtype=NotificationType.MediaServer, title=t, text=msg)
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
        self.post_message(mtype=NotificationType.MediaServer, title="豆瓣想看同步失败", text=msg)
    except Exception as e:
        logger.error(f'{self.plugin_name} 发送同步想看通知失败: {e}')
