"""
DoubanCenter - 豆瓣档案模块
"""
import datetime
import threading
from typing import Dict, Optional

from app.chain.media import MediaChain
from app.core.metainfo import MetaInfo
from app.log import logger
from app.schemas.types import MediaType, NotificationType

from . import utils
from .doubanapi import DoubanApi
from .storage import records as storage


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
                _send_folio_notification(self, False, "豆瓣cookie可能已失效，请及时更换！")
                self._last_cookie_invalid_time = now
        self._last_cookie_check_time = now


def run_wish_scheduled(self) -> None:
    """执行豆瓣想看同步定时入口。"""
    run_wish_sync(self)


def run_wish_sync(self, api=None, request_get=None) -> None:
    """读取豆瓣想看列表，首跑建立基线，后续仅将新增条目入队。"""
    dh = api if api is not None else DoubanApi(user_cookie=getattr(self, "_folio_cookie", ""))
    items = dh.get_wish_items(
        user_id=getattr(self, "_wish_user", "") or "",
        max_pages=max(1, int(getattr(self, "_wish_max_pages", 1) or 1)),
        request_get=request_get,
    ) or []

    state = storage.read_folio_wish_state(self)
    seen = storage.read_folio_wish_seen(self)
    queue = storage.read_folio_wish_queue(self)
    seen_ids = {str(r.get("subject_id")) for r in seen if r.get("subject_id")}
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    added = 0
    for item in items:
        subject_id = str(item.get("subject_id") or "")
        if not subject_id or subject_id in seen_ids:
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
    storage.save_folio_wish_state(self, state)
    logger.info(f"豆瓣想看同步完成，新增入队 {added} 条")


WISH_RANK_KEY = "douban_wish"
WISH_RANK_NAME = "豆瓣想看"


def _default_wish_recognize(self):
    """返回默认的想看识别函数。"""
    def recognize(title, year):
        """识别想看条目对应的媒体信息。"""
        meta = MetaInfo(title)
        if year:
            meta.year = str(year)
        return MediaChain().recognize_media(meta=meta, cache=True)
    return recognize


def process_wish_queue(self, recognize=None, subscribe=None) -> None:
    """处理想看待订阅队列，识别后通过现有订阅链创建订阅。"""
    queue = storage.read_folio_wish_queue(self)
    if not queue:
        return
    processed = storage.read_folio_wish_processed(self)
    failed = storage.read_folio_wish_failed(self)
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
            failed.append({"subject_id": subject_id, "title": title, "reason": "recognize_failed",
                           "retry": int(item.get("retry", 0) or 0) + 1, "failed_at": now})
            continue
        try:
            subscriber(self, mediainfo, rank_key=WISH_RANK_KEY, rank_name=WISH_RANK_NAME, source_link=link)
        except Exception as err:
            logger.warning(f"豆瓣想看订阅失败：{title} {err}")
        processed.append({"subject_id": subject_id, "title": title, "processed_at": now})

    storage.save_folio_wish_queue(self, remaining)
    storage.save_folio_wish_processed(self, processed)
    storage.save_folio_wish_failed(self, failed)
    logger.info(f"豆瓣想看队列处理完成，处理 {len(processed)} 条，失败 {len(failed)} 条")


def _wish_seen_record(item, now):
    """构造已见想看条目的最小记录。"""
    return {"subject_id": str(item.get("subject_id") or ""), "title": item.get("title", ""), "seen_at": now}


def _wish_queue_record(item, now):
    """构造待处理想看条目的队列记录。"""
    return {
        "subject_id": str(item.get("subject_id") or ""),
        "title": item.get("title", ""),
        "year": item.get("year", ""),
        "link": item.get("link", ""),
        "poster": item.get("poster", ""),
        "wish_time": item.get("wish_time", ""),
        "enqueued_at": now,
    }


def sync_log_handler(self, event_info, played: bool = False):
    """处理播放事件并同步豆瓣时间线。"""
    play_start = {"playback.start", "media.play", "PlaybackStart"}
    processed = storage.read_folio_data(self)
    self._wait_process = storage.read_folio_wait(self)
    if (event_info.event in play_start and event_info.user_name in self._folio_user.split(',')) or played:
        if played:
            logger.info(f"标记播放完成 {event_info.item_name}")
        ret = utils.exclude_keyword(path=event_info.item_path, keywords=self._folio_exclude)
        if not ret.get("ret", False):
            logger.info(ret.get("message", ""))
            return
        if event_info.item_type == "TV":
            _process_tv_show(self, event_info, processed, played=played)
        elif event_info.item_type == "MOV":
            _process_movie(self, event_info, processed, played=played)


def _process_tv_show(self, event_info, processed: Dict, played: bool = False):
    idx = event_info.item_name.index(" S")
    title = event_info.item_name[:idx]
    season_id, episode_id = map(int, [event_info.season_id, event_info.episode_id])
    tmdb_id = event_info.tmdb_id
    if not played:
        logger.info(f"开始播放 {title} 第{season_id}季 第{episode_id}集")
    if episode_id < 2 and self._folio_first:
        logger.info("剧集第1集的活动不同步到豆瓣档案，跳过")
        return
    meta = MetaInfo(title)
    meta.begin_season = season_id
    meta.type = MediaType("电视剧")
    mediainfo = _recognize_media(meta, tmdb_id)
    if not mediainfo:
        logger.warning(f'标题：{title}，tmdbid：{tmdb_id}，尝试仅使用标题识别')
        meta.tmdbid = None
        mediainfo = _recognize_media(meta, None)
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
        for k, v in self._wait_process.items():
            logger.info(f"尝试同步: {k}")
            _sync_to_douban(self, k, v["status"], v["type"], processed, None)


def _process_movie(self, event_info, processed: Dict, played: bool = False):
    title = event_info.item_name
    if not played:
        logger.info(f"开始播放 {title}")
    meta = MetaInfo(title)
    meta.type = MediaType("电影")
    mediainfo = _recognize_media(meta, event_info.tmdb_id)
    if not mediainfo:
        logger.warning(f'标题：{title}，tmdbid：{event_info.tmdb_id}，尝试仅使用标题识别')
        meta.tmdbid = None
        mediainfo = _recognize_media(meta, None)
        if not mediainfo:
            logger.error('仍然未识别到媒体信息')
            return
    if processed.get(title):
        logger.info(f"{title} 已同步到豆瓣在看，不处理")
        return
    _sync_to_douban(self, title, "collect", event_info.item_type, processed, mediainfo)


def _recognize_media(meta, tmdb_id: Optional[int]):
    return MediaChain().recognize_media(meta=meta, mtype=meta.type, tmdbid=tmdb_id, cache=True)


def _sync_to_douban(self, title: str, status: str, mediaType: str, processed: Dict, mediainfo=None) -> bool:
    logger.info(f"开始尝试获取 {title} 豆瓣id")
    dh = DoubanApi(user_cookie=self._folio_cookie)
    search = f"{title} {mediainfo.year}" if mediainfo and mediainfo.year else title
    name, sid = dh.get_subject_id(title=search)
    if not sid and search != title:
        logger.info(f"带年份搜索无结果，回退到原标题: {title}")
        name, sid = dh.get_subject_id(title=title)
    if sid:
        poster = mediainfo.poster_path if mediainfo else ""
        logger.info(f"查询：{title} => 匹配豆瓣：{name}")
        if dh.set_watching_status(subject_id=sid, status=status, private=self._folio_private):
            processed[title] = {
                "subject_id": sid, "subject_name": name,
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
        else:
            logger.error(f'{title} 同步到档案失败')
            if title not in (self._wait_process or {}):
                self._wait_process[title] = {"subject_id": sid, "subject_name": name, "status": status, "poster_path": poster, "type": mediaType}
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
