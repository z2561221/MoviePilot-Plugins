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


def check_cookie_periodically(self) -> None:
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


def sync_log_handler(self, event_info, played: bool = False):
    play_start = {"playback.start", "media.play", "PlaybackStart"}
    processed = self.get_data('folio_data') or {}
    self._wait_process = self.get_data('folio_wait') or {}
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
        self._wait_process = self.get_data('folio_wait') or {}
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
            self.save_data('folio_data', processed)
            self.save_data('folio_wait', self._wait_process)
            logger.info(f"{title} 同步到档案成功")
            _send_folio_notification(self, True, f"《{title}》已成功同步到豆瓣档案。")
            return True
        else:
            logger.error(f'{title} 同步到档案失败')
            if title not in (self._wait_process or {}):
                self._wait_process[title] = {"subject_id": sid, "subject_name": name, "status": status, "poster_path": poster, "type": mediaType}
                self.save_data('folio_wait', self._wait_process)
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