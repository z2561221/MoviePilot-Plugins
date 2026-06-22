"""
DoubanCenter - 姒滃崟璁㈤槄寮曟搸
"""
import datetime
import hashlib
import re
import time
import xml.dom.minidom
from typing import Any, Dict, List

from app.chain.download import DownloadChain
from app.chain.subscribe import SubscribeChain
from app.core.config import settings
from app.core.metainfo import MetaInfo
from app.log import logger
from app.schemas.types import MediaType, NotificationType
from app.utils.dom import DomUtils
from app.utils.http import RequestUtils

from . import utils

RANK_HISTORY_LIMIT = 500


def _trim_history(history: List[dict], limit: int = RANK_HISTORY_LIMIT) -> List[dict]:
    """Trim rank history to the newest items."""
    if limit <= 0 or len(history) <= limit:
        return history
    return history[-limit:]


def _custom_rank_history_key(source: str) -> str:
    """为自定义 RSS 生成跨进程稳定的历史数据键。"""
    digest = hashlib.sha1((source or "").encode("utf-8")).hexdigest()[:16]
    return f"rank_history_custom_{digest}"


def _rank_media_type(rank: dict, item: dict) -> str:
    """Infer media type from rank definition and RSS item."""
    raw_type = str((item or {}).get("mtype") or "").lower()
    if raw_type in ("movie", "tv"):
        return raw_type
    key = str((rank or {}).get("key") or "").lower()
    route = str((rank or {}).get("route") or "").lower()
    if "movie" in key or "/movie" in route:
        return "movie"
    return "tv"


def _rss_default_media_type(addr: str) -> str:
    """Infer default media type from RSS URL."""
    text = str(addr or "").lower()
    if "movie_" in text or "/movie" in text:
        return "movie"
    return "tv"


def _record_history_item(history: List[dict], entry: dict) -> None:
    """Upsert a rank history entry, replacing observe placeholders in place."""
    stored = dict(entry or {})
    stored.pop("observing", None)
    unique = stored.get("unique")
    if unique:
        for index, item in enumerate(history):
            if item.get("unique") == unique:
                merged = dict(item or {})
                merged.update(stored)
                merged.pop("observing", None)
                history[index] = merged
                return
    history.append(stored)


def _history_item_subscribed(item: dict) -> bool:
    """Return True when a history entry has already produced a subscription."""
    if not isinstance(item, dict):
        return False
    return bool(item.get("subscribed") or item.get("subscribed_at"))


def _history_item_existing(item: dict) -> bool:
    """判断历史条目是否已确认存在于媒体库或订阅中。"""
    if not isinstance(item, dict):
        return False
    return bool(item.get("existing") or item.get("existing_at"))


def _history_index_by_unique(history: List[dict]) -> Dict[str, dict]:
    """Build a unique lookup for rank history entries."""
    return {
        item.get("unique"): item
        for item in history
        if isinstance(item, dict) and item.get("unique")
    }


# 闃插埛姒滃伐鍏峰嚱鏁?


def _log_anti_cheat(self, reason: str, title: str, detail: str = ""):
    """Record anti-cheat logs."""
    logs = self.get_data("anti_cheat_logs") or []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    matched = None
    kept = []
    for log in logs:
        if (
            isinstance(log, dict)
            and log.get("reason") == reason
            and log.get("title") == title
            and log.get("detail") == detail
        ):
            if matched is None:
                matched = dict(log)
            else:
                try:
                    matched["count"] = int(matched.get("count") or 1) + int(log.get("count") or 1)
                except (TypeError, ValueError):
                    matched["count"] = int(matched.get("count") or 1) + 1
            continue
        kept.append(log)
    if matched is not None:
        try:
            matched["count"] = int(matched.get("count") or 1) + 1
        except (TypeError, ValueError):
            matched["count"] = 2
        matched["time"] = now
        kept.append(matched)
        logs = kept
    else:
        logs = kept
        logs.append({
            "time": now,
            "reason": reason,
            "title": title,
            "detail": detail
        })
    # 鍙繚鐣欐渶杩?00鏉?
    if len(logs) > 100:
        logs = logs[-100:]
    self.save_data("anti_cheat_logs", logs)


def _is_existing_media(mediainfo, meta=None) -> bool:
    """判断媒体是否已存在于媒体库或订阅中。"""
    try:
        ef, _ = DownloadChain().get_no_exists_info(meta=meta, mediainfo=mediainfo)
        if ef:
            return True
    except Exception as err:
        logger.warning(f"豆瓣中心：检查媒体库存在状态失败：{err}")
    try:
        if SubscribeChain().exists(mediainfo=mediainfo, meta=meta):
            return True
    except Exception as err:
        logger.warning(f"豆瓣中心：检查订阅存在状态失败：{err}")
    return False


def _record_existing_history(history: List[dict], unique: str, title: str = "", year: Any = "", link: str = "", mediainfo=None) -> None:
    """记录已存在媒体，避免后续再次进入观察队列。"""
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
    }
    try:
        entry["poster"] = mediainfo.get_poster_image() if mediainfo else ""
    except Exception:
        entry["poster"] = ""
    _record_history_item(history, entry)


def _check_blacklist(self, title: str) -> bool:
    """Return True when the title matches a blacklist keyword."""
    kw = (self._blacklist_keywords or "").strip()
    if not kw:
        return False
    for line in kw.split("\n"):
        word = line.strip()
        if word and word.lower() in title.lower():
            logger.info(f"豆瓣中心：黑名单关键词《{word}》匹配《{title}》，跳过")
            _log_anti_cheat(self, "黑名单关键词", title, f"匹配词：{word}")
            return True
    return False


def _check_observe(self, unique: str, history: List[dict], title: str = "") -> bool:
    """Return True when the item is still inside the observe window."""

    if not self._anti_cheat_enabled:
        return False
    days = int(self._observe_days or 0)
    if days <= 0:
        return False
    now = datetime.datetime.now()
    for h in history:
        if h.get("unique") == unique:
            if h.get("observe_deleted"):
                logger.info(f"豆瓣中心：条目《{h.get('title') or title or unique}》已从观察队列删除，跳过订阅")
                return True
            first_seen = h.get("first_seen") or h.get("time", "")
            if first_seen:
                try:
                    ft = datetime.datetime.strptime(first_seen, "%Y-%m-%d %H:%M:%S")
                    elapsed = (now - ft).days
                    if elapsed < days:
                        h["first_seen"] = first_seen
                        h["observing"] = True
                        logger.info(f"豆瓣中心：条目《{h.get('title')}》观察期未满（{elapsed}/{days} 天），跳过订阅")
                        _log_anti_cheat(self, "观察期未满", h.get("title", ""), f"已过 {elapsed} 天，需要 {days} 天")
                        return True
                    return False
                except Exception:
                    pass
            h["time"] = now.strftime("%Y-%m-%d %H:%M:%S")
            h["first_seen"] = h["time"]
            h["observing"] = True
            return True
    observed_at = now.strftime("%Y-%m-%d %H:%M:%S")
    history.append({
        "title": title or unique,
        "time": observed_at,
        "first_seen": observed_at,
        "unique": unique,
        "observing": True,
    })
    logger.info(f"豆瓣中心：条目《{title or unique}》首次进入观察期（0/{days} 天），跳过订阅")
    _log_anti_cheat(self, "观察期首次记录", title or unique, f"需要观察 {days} 天")
    return True


def _check_anti_cheat(self, mediainfo) -> bool:
    """Return True when TMDB vote is below the anti-cheat threshold."""
    if not self._anti_cheat_enabled:
        return False
    threshold = self._anti_cheat_min_vote
    if threshold <= 0:
        return False
    vote = mediainfo.vote_average
    try:
        vote_value = float(vote or 0)
    except (TypeError, ValueError):
        vote_value = 0
    if vote_value <= 0:
        logger.info(f"豆瓣中心：条目《{mediainfo.title}》暂无 TMDB 评分，忽略评分筛选")
        return False
    if vote_value < threshold:
        logger.info(f"豆瓣中心：条目《{mediainfo.title}》TMDB 评分 {vote_value} 低于阈值 {threshold}，跳过订阅")
        _log_anti_cheat(self, "TMDB评分过低", mediainfo.title, f"评分 {vote_value}，阈值 {threshold}")
        return True
    return False

BUILTIN_RANKS: List[Dict[str, Any]] = [
    {"key": "coming", "name": "即将上映", "route": "/douban/tv/coming", "coming": True, "filters": ["wish_count", "air_days"]},
    {"key": "tv_real_time", "name": "实时热门", "route": "/douban/list/tv_real_time_hotest", "coming": False, "filters": ["vote", "year"]},
    {"key": "tv_chinese", "name": "华语口碑", "route": "/douban/list/tv_chinese_best_weekly", "coming": False, "filters": ["vote", "year"]},
    {"key": "tv_global", "name": "全球口碑", "route": "/douban/list/tv_global_best_weekly", "coming": False, "filters": ["vote", "year"]},
    {"key": "movie_weekly", "name": "电影口碑", "route": "/douban/list/movie_weekly_best", "coming": False, "filters": ["vote", "year"]},
    {"key": "bangumi", "name": "BangumiTV", "route": "/bangumi.tv/anime/followrank", "coming": False, "filters": ["vote", "year"]},
]


def _rc(self, key: str) -> dict:
    return (self._rank_configs or {}).get(key, {})


def _ren(self, key: str) -> bool:
    return _rc(self, key).get("enabled", False)


def _rcount(self, key: str) -> int:
    return int(_rc(self, key).get("count", 10) or 10)


def _positive_number(value: Any) -> bool:
    try:
        return float(value or 0) > 0
    except (TypeError, ValueError):
        return False


def _year_below_min(value: Any, min_year: int) -> bool:
    """判断年份是否低于最低年份筛选条件。"""
    if min_year <= 0 or value in (None, ""):
        return False
    try:
        return int(str(value)[:4]) < min_year
    except (TypeError, ValueError):
        return False


def _has_global_subscription_filter(self) -> bool:
    if self._region_filters or self._genre_filters or self._resolution_filters:
        return True
    if (self._blacklist_keywords or "").strip():
        return True
    if not self._anti_cheat_enabled:
        return False
    if int(self._observe_days or 0) > 0:
        return True
    return _positive_number(self._anti_cheat_min_vote)


def _has_rank_subscription_filter(self, rd: dict) -> bool:
    cfg = _rc(self, rd["key"])
    if rd["coming"]:
        return _positive_number(cfg.get("wish_count")) or _positive_number(cfg.get("air_days"))
    return _positive_number(cfg.get("vote")) or _positive_number(cfg.get("year"))


def _has_subscription_safety_filter(self) -> bool:
    if _has_global_subscription_filter(self):
        return True
    return any(
        _ren(self, rd["key"]) and _has_rank_subscription_filter(self, rd)
        for rd in BUILTIN_RANKS
    )


def subscribe_to_ranks(self, refresh_when_unsafe: bool = True) -> None:
    """按当前配置执行榜单订阅，必要时只刷新榜单历史。"""
    if not _has_subscription_safety_filter(self):
        logger.warning("豆瓣中心：未配置有效订阅筛选条件，跳过自动订阅，仅刷新榜单历史以避免误触发大量订阅")
        if refresh_when_unsafe:
            refresh_rank_data(self)
        return

    rsshub = utils.normalize_rss_domain(self._rsshub_domain)
    for rd in BUILTIN_RANKS:
        key = rd["key"]
        if not _ren(self, key):
            continue
        count = _rcount(self, key)
        url = f"{rsshub.rstrip('/')}{rd['route']}?limit={count}"
        logger.info(f"豆瓣中心：开始处理 [{rd['name']}] {url}")
        if rd["coming"]:
            _process_coming(self, url, rd)
        else:
            _process_general(self, url, rd)
        time.sleep(1)
    for cu in (self._custom_rss_addrs or []):
        u = cu.strip()
        if u:
            logger.info(f"豆瓣中心：自定义 RSS {u}")
            items = _fetch_rss(self, u)
            if items:
                _process_items(self, items, u)
            time.sleep(1)
    logger.info("豆瓣中心：榜单订阅刷新完成")


def run_once(self) -> None:
    """立即刷新榜单数据，并按当前订阅配置执行订阅。"""
    logger.info("豆瓣中心：立即运行开始，先刷新 RSS 榜单，再按配置执行订阅")
    refresh_rank_data(self)
    subscribe_to_ranks(self, refresh_when_unsafe=False)


def _process_coming(self, url: str, rd: dict) -> None:
    cfg = _rc(self, rd["key"])
    min_wish = int(cfg.get("wish_count", 5000) or 5000)
    air_days = int(cfg.get("air_days", 7) or 7)
    items = _fetch_coming_rss(self, url)
    if not items:
        return
    history: List[dict] = self.get_data("coming_history") or []
    history_index = _history_index_by_unique(history)
    for item in items:
        title, link, wish = item.get("title", ""), item.get("link", ""), item.get("wish_count", 0)
        year, regions, genres = item.get("year", ""), item.get("regions", []), item.get("genres", [])
        if not title:
            continue
        unique = f"dc2_coming:{link or title}"
        if _history_item_subscribed(history_index.get(unique)) or _history_item_existing(history_index.get(unique)):
            continue
        if _check_blacklist(self, title):
            continue
        if wish < min_wish:
            continue
        if not utils.match_any_filter(regions, self._region_filters) or not utils.match_any_filter(genres, self._genre_filters):
            continue
        meta = MetaInfo(title)
        if year:
            meta.year = str(year)
        meta.type = MediaType.TV
        mediainfo = self.chain.recognize_media(meta=meta, mtype=MediaType.TV)
        if not mediainfo:
            continue
        # 闃插埛姒滐細TMDB璇勫垎杩囨护
        if _check_anti_cheat(self, mediainfo):
            continue
        if _is_existing_media(mediainfo, meta):
            logger.info(f"豆瓣中心：条目《{mediainfo.title or title}》已在媒体库或订阅中，跳过观察与订阅")
            _record_existing_history(history, unique, title=title, year=year, link=link, mediainfo=mediainfo)
            history_index[unique] = {"existing": True, "existing_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            continue
        ad = utils.get_tmdb_air_date(self.chain, mediainfo.tmdb_id, season=meta.begin_season)
        if not ad or not utils.is_within_days(ad, air_days):
            continue
        # 闃插埛姒滐細瑙傚療鏈?
        if _check_observe(self, unique, history, title=title):
            continue
        if _add_sub(self, mediainfo, meta, rank_key=rd["key"], rank_name=rd["name"]):
            # 浣跨敤TMDB璇嗗埆鍚庣殑涓枃鍚嶆浛鎹㈠師濮嬫爣棰?
            cn_title = mediainfo.title or title
            subscribed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _record_history_item(history, {"title": cn_title, "year": year, "wish_count": wish, "air_date": ad, "link": link, "tmdbid": mediainfo.tmdb_id, "poster": mediainfo.get_poster_image(), "time": subscribed_at, "unique": unique, "subscribed": True, "subscribed_at": subscribed_at})
            history_index[unique] = {"subscribed": True, "subscribed_at": subscribed_at}
    self.save_data("coming_history", _trim_history(history))


def _process_general(self, url: str, rd: dict) -> None:
    cfg = _rc(self, rd["key"])
    min_vote = float(cfg.get("vote", 0) or 0)
    min_year = int(cfg.get("year", 0) or 0)
    items = _fetch_rss(self, url)
    if not items:
        return
    data_key = f"rank_history_{rd['key']}"
    history: List[dict] = self.get_data(data_key) or []
    history_index = _history_index_by_unique(history)
    for item in items:
        title, link, year = item.get("title", ""), item.get("link", ""), item.get("year")
        mtype = _rank_media_type(rd, item)
        if not title:
            continue
        unique = f"dc2_rank:{link or title}"
        if _history_item_subscribed(history_index.get(unique)) or _history_item_existing(history_index.get(unique)):
            continue
        if _check_blacklist(self, title):
            continue
        if _year_below_min(year, min_year):
            continue
        meta = MetaInfo(title)
        if year:
            meta.year = str(year)
        meta.type = MediaType.MOVIE if mtype == "movie" else MediaType.TV
        mediainfo = self.chain.recognize_media(meta=meta, mtype=meta.type)
        if not mediainfo:
            continue
        if min_vote > 0 and mediainfo.vote_average and mediainfo.vote_average < min_vote:
            continue
        if _year_below_min(mediainfo.year, min_year):
            continue
        # 闃插埛姒滐細TMDB璇勫垎杩囨护
        if _check_anti_cheat(self, mediainfo):
            continue
        if _is_existing_media(mediainfo, meta):
            logger.info(f"豆瓣中心：条目《{mediainfo.title or title}》已在媒体库或订阅中，跳过观察与订阅")
            _record_existing_history(history, unique, title=title, year=year, link=link, mediainfo=mediainfo)
            history_index[unique] = {"existing": True, "existing_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            continue
        # 闃插埛姒滐細瑙傚療鏈?
        if _check_observe(self, unique, history, title=title):
            continue
        if _add_sub(self, mediainfo, meta, rank_key=rd["key"], rank_name=rd["name"]):
            cn_title = mediainfo.title or title
            subscribed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _record_history_item(history, {"title": cn_title, "year": mediainfo.year or year or "", "media_type": mtype, "link": link, "tmdbid": mediainfo.tmdb_id, "poster": mediainfo.get_poster_image(), "time": subscribed_at, "unique": unique, "subscribed": True, "subscribed_at": subscribed_at})
            history_index[unique] = {"subscribed": True, "subscribed_at": subscribed_at}
    self.save_data(data_key, _trim_history(history))


def _process_items(self, items: List[dict], source: str) -> None:
    data_key = _custom_rank_history_key(source)
    history: List[dict] = self.get_data(data_key) or []
    history_index = _history_index_by_unique(history)
    for item in items:
        title, link, mtype, year = item.get("title", ""), item.get("link", ""), item.get("mtype", ""), item.get("year")
        if not title:
            continue
        unique = f"dc2_rank:{link or title}"
        if _history_item_subscribed(history_index.get(unique)) or _history_item_existing(history_index.get(unique)):
            continue
        if _check_blacklist(self, title):
            continue
        meta = MetaInfo(title)
        if year:
            meta.year = str(year)
        meta.type = MediaType.MOVIE if mtype == "movie" else MediaType.TV
        mediainfo = self.chain.recognize_media(meta=meta, mtype=meta.type)
        if not mediainfo:
            continue
        # 闃插埛姒滐細TMDB璇勫垎杩囨护
        if _check_anti_cheat(self, mediainfo):
            continue
        if _is_existing_media(mediainfo, meta):
            logger.info(f"豆瓣中心：条目《{mediainfo.title or title}》已在媒体库或订阅中，跳过观察与订阅")
            _record_existing_history(history, unique, title=title, year=year, link=link, mediainfo=mediainfo)
            history_index[unique] = {"existing": True, "existing_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            continue
        # 闃插埛姒滐細瑙傚療鏈?
        if _check_observe(self, unique, history, title=title):
            continue
        if _add_sub(self, mediainfo, meta):
            cn_title = mediainfo.title or title
            subscribed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _record_history_item(history, {"title": cn_title, "link": link, "tmdbid": mediainfo.tmdb_id, "poster": mediainfo.get_poster_image(), "time": subscribed_at, "unique": unique, "subscribed": True, "subscribed_at": subscribed_at})
            history_index[unique] = {"subscribed": True, "subscribed_at": subscribed_at}
    self.save_data(data_key, _trim_history(history))


def _add_sub(self, mediainfo, meta=None, rank_key="", rank_name="") -> bool:
    if _is_existing_media(mediainfo, meta):
        return False
    sc = SubscribeChain()
    res = utils.build_resolution_rule(self._resolution_filters)
    sid, msg = sc.add(title=mediainfo.title, year=mediainfo.year or "", mtype=mediainfo.type if mediainfo.type else MediaType.TV, tmdbid=mediainfo.tmdb_id, season=meta.begin_season if meta and meta.type == MediaType.TV else None, resolution=res, sites=None, exist_ok=True, username="璞嗙摚涓績", message=False)
    if not sid:
        return False
    if self._notify:
        media_type_name = "电影" if mediainfo.type == MediaType.MOVIE else "电视剧"
        self.post_message(mtype=NotificationType.Subscribe, title=f"豆瓣中心：{mediainfo.title_year} 已添加订阅", text=f"类型：{media_type_name}\n", image=mediainfo.get_message_image())
    subs = self.get_data("subscribe_records") or []
    subs.append({
        "title": mediainfo.title,
        "year": mediainfo.year or "",
        "tmdbid": mediainfo.tmdb_id,
        "poster": mediainfo.get_poster_image(),
        "media_type": "电影" if mediainfo.type == MediaType.MOVIE else "电视剧",
        "rank_key": rank_key,
        "rank_name": rank_name,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    # 鍙繚鐣欐渶杩?00鏉?
    if len(subs) > 500:
        subs = subs[-500:]
    self.save_data("subscribe_records", subs)
    return True


def _fetch_coming_rss(self, addr: str) -> List[dict]:
    try:
        ret = RequestUtils(proxies=settings.PROXY).get_res(addr) if self._proxy else RequestUtils().get_res(addr)
        if not ret:
            return []
        dom = xml.dom.minidom.parseString(ret.text)
        root = dom.documentElement
        result = []
        for item in root.getElementsByTagName("item"):
            title = DomUtils.tag_value(item, "title", default="")
            link = DomUtils.tag_value(item, "link", default="")
            desc = DomUtils.tag_value(item, "description", default="")
            cat = DomUtils.tag_value(item, "category", default="")
            if not title and not link:
                continue
            result.append({"title": title, "link": link, "description": desc, "wish_count": utils.parse_wish_count(desc), "year": utils.parse_year(cat), "regions": utils.parse_regions_and_genres(cat)[0], "genres": utils.parse_regions_and_genres(cat)[1]})
        return result
    except Exception as err:
        logger.error(f"获取即将上映 RSS 失败：{err}")
        return []


def _fetch_rss(self, addr: str) -> List[dict]:
    try:
        ret = RequestUtils(proxies=settings.PROXY).get_res(addr) if self._proxy else RequestUtils().get_res(addr)
        if not ret:
            return []
        dom = xml.dom.minidom.parseString(ret.text)
        root = dom.documentElement
        result = []
        default_mtype = _rss_default_media_type(addr)
        for item in root.getElementsByTagName("item"):
            title = DomUtils.tag_value(item, "title", default="")
            link = DomUtils.tag_value(item, "link", default="")
            desc = DomUtils.tag_value(item, "description", default="")
            if not title:
                continue
            mtype = default_mtype
            if re.search(r"绗琜涓€浜屼笁鍥涗簲鍏竷鍏節鍗乗d]+瀛Season\s*\d+", title, re.IGNORECASE):
                mtype = "tv"
            doubanid = None
            if link:
                m = re.search(r"/subject/(\d+)/?", link)
                if m:
                    doubanid = m.group(1)
            year = None
            if desc:
                m = re.search(r"\b(19|20)\d{2}\b", desc)
                if m:
                    year = m.group(0)
            result.append({"title": title, "link": link, "mtype": mtype, "doubanid": doubanid, "year": year})
        return result
    except Exception as err:
        logger.error(f"获取 RSS 失败：{err}")
        return []


def get_enabled_rank_keys(self) -> List[str]:
    return [rd["key"] for rd in BUILTIN_RANKS if _ren(self, rd["key"])]


def get_rank_history_by_key(self, rank_key: str) -> List[dict]:
    if rank_key == "coming":
        return self.get_data("coming_history") or []
    data_key = f"rank_history_{rank_key}"
    return self.get_data(data_key) or []


def _dashboard_rank_sort_key(item: dict) -> tuple:
    """Build a dashboard sort key for the latest RSS rank order."""
    try:
        rank_index = int(item.get("rank_index"))
    except (TypeError, ValueError):
        rank_index = 10 ** 9
    return rank_index, str(item.get("title") or "")


def get_dashboard_rank_items(self, rank_key: str, limit: int = 5) -> List[dict]:
    """Return dashboard items from the latest RSS refresh batch."""
    history = [item for item in get_rank_history_by_key(self, rank_key) if isinstance(item, dict)]
    if not history:
        return []

    latest_batch = max((str(item.get("rank_refreshed_at") or "") for item in history), default="")
    if latest_batch:
        current_items = [item for item in history if str(item.get("rank_refreshed_at") or "") == latest_batch]
        current_items.sort(key=_dashboard_rank_sort_key)
        return current_items[:limit]

    return list(reversed(history[-limit:]))


def refresh_rank_data(self, rank_keys=None):
    """Refresh RSS rank data for dashboard display without subscribing."""
    # rank_keys: optional list of rank keys to refresh.
    # Dashboard refresh always pulls 10 items regardless of count config.
    # Returns: {rank_key: [items]} for the current refresh result.

    result = {}
    try:
        rsshub = utils.normalize_rss_domain(self._rsshub_domain)
        targets = [rd for rd in BUILTIN_RANKS if (rank_keys is None and _ren(self, rd["key"])) or (rank_keys and rd["key"] in rank_keys)]
        for rd in targets:
            key = rd["key"]
            # 浠〃鐩樺埛鏂板浐瀹氭媺10鏉★紝涓嶅彈count閰嶇疆闄愬埗
            url = f"{rsshub.rstrip('/')}{rd['route']}?limit=10"
            logger.info(f"豆瓣中心：刷新 RSS [{rd['name']}] {url}")
            if rd["coming"]:
                items = _fetch_coming_rss(self, url)
            else:
                items = _fetch_rss(self, url)
            if items:
                _merge_rank_items(self, key, items, rd)
                result[key] = get_dashboard_rank_items(self, key, limit=5)
            time.sleep(1)
        logger.info("豆瓣中心：RSS 刷新完成")
    except Exception as err:
        logger.error(f"豆瓣中心：刷新 RSS 失败：{err}", exc_info=True)
    return result


def _merge_rank_items(self, rank_key, items, rd):
    """Merge fetched RSS rank items into history and update current batch order."""
    if rank_key == "coming":
        data_key = "coming_history"
    else:
        data_key = f"rank_history_{rank_key}"
    history: List[dict] = self.get_data(data_key) or []
    history_index = {
        item.get("unique"): index
        for index, item in enumerate(history)
        if isinstance(item, dict) and item.get("unique")
    }
    new_count = 0
    refresh_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for rank_index, item in enumerate(items):
        try:
            title = item.get("title", "")
            link = item.get("link", "")
            if not title:
                continue
            unique = f"dc2_rank:{link or title}" if rank_key != "coming" else f"dc2_coming:{link or title}"
            year = item.get("year", "")
            # 灏濊瘯璇嗗埆濯掍綋淇℃伅锛屽け璐ユ椂涔熶繚鐣欐潯鐩紙鍙槸娌℃湁娴锋姤鍜宼mdbid锛?
            tmdbid = None
            poster = None
            cn_title = title
            douban_id = item.get("doubanid")  # 浼樺厛鐢≧SS涓В鏋愮殑璞嗙摚ID
            meta_type = "tv" if rank_key == "coming" else _rank_media_type(rd, item)
            try:
                meta = MetaInfo(title)
                if year:
                    meta.year = str(year)
                meta.type = MediaType.MOVIE if meta_type == "movie" else MediaType.TV
                mediainfo = self.chain.recognize_media(meta=meta, mtype=meta.type)
                if mediainfo:
                    tmdbid = mediainfo.tmdb_id
                    poster = mediainfo.get_poster_image()
                    cn_title = mediainfo.title or title
                    year = mediainfo.year or year
                    if not douban_id and hasattr(mediainfo, "douban_id") and mediainfo.douban_id:
                        douban_id = mediainfo.douban_id
            except Exception:
                pass
            entry = {
                "title": cn_title,
                "year": year or "",
                "media_type": meta_type,
                "link": link,
                "tmdbid": tmdbid,
                "poster": poster,
                "time": refresh_time,
                "unique": unique,
                "douban_id": douban_id,
                "rank_index": rank_index,
                "rank_order": rank_index + 1,
                "rank_key": rank_key,
                "rank_name": rd.get("name", ""),
                "rank_refreshed_at": refresh_time,
            }
            if rank_key == "coming":
                entry.update({"year": year, "wish_count": item.get("wish_count", 0)})
            existing_index = history_index.get(unique)
            if existing_index is None:
                history.append(entry)
                history_index[unique] = len(history) - 1
                new_count += 1
            else:
                existing = history[existing_index] if isinstance(history[existing_index], dict) else {}
                merged = dict(existing)
                merged.update(entry)
                if existing.get("observing"):
                    merged["observing"] = True
                    if existing.get("first_seen"):
                        merged["first_seen"] = existing.get("first_seen")
                    elif existing.get("time"):
                        merged["first_seen"] = existing.get("time")
                if existing.get("observe_deleted"):
                    merged["observe_deleted"] = True
                    if existing.get("observe_deleted_at"):
                        merged["observe_deleted_at"] = existing.get("observe_deleted_at")
                history[existing_index] = merged
        except Exception as err:
            logger.error(f"豆瓣中心：合并 {rank_key} 榜单条目出错：{err}")
            continue
    history = _trim_history(history)
    self.save_data(data_key, history)
    logger.info(
        f"豆瓣中心：{rd['name']} 刷新完成，当前批次 {len(items)} 条，新增 {new_count} 条，累计 {len(history)} 条"
    )
    return history


def _refresh_coming(self, url, rd):
    """Refresh coming-soon rank data without triggering subscriptions."""
    items = _fetch_coming_rss(self, url)
    if not items:
        return
    history: List[dict] = self.get_data("coming_history") or []
    uh = {i.get("unique") for i in history}
    new_count = 0
    for item in items:
        try:
            title, link = item.get("title", ""), item.get("link", "")
            year = item.get("year", "")
            unique = f"dc2_coming:{link or title}"
            if unique in uh:
                continue
            meta = MetaInfo(title)
            if year:
                meta.year = str(year)
            meta.type = MediaType.TV
            mediainfo = self.chain.recognize_media(meta=meta, mtype=MediaType.TV)
            if not mediainfo:
                continue
            cn_title = mediainfo.title or title
            _record_history_item(history, {"title": cn_title, "year": year, "wish_count": item.get("wish_count", 0), "link": link, "tmdbid": mediainfo.tmdb_id, "poster": mediainfo.get_poster_image(), "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "unique": unique})
            uh.add(unique)
            new_count += 1
        except Exception as e:
            logger.error(f"豆瓣中心：刷新即将上映条目出错：{e}")
            continue
    self.save_data("coming_history", _trim_history(history))
    logger.info(f"豆瓣中心：即将上映刷新完成，新增 {new_count} 条")


def _refresh_general(self, url, rd):
    """Refresh general rank data without triggering subscriptions."""
    items = _fetch_rss(self, url)
    if not items:
        return
    data_key = f"rank_history_{rd['key']}"
    history: List[dict] = self.get_data(data_key) or []
    uh = {i.get("unique") for i in history}
    new_count = 0
    for item in items:
        try:
            title, link, year = item.get("title", ""), item.get("link", ""), item.get("year")
            mtype = _rank_media_type(rd, item)
            if not title:
                continue
            unique = f"dc2_rank:{link or title}"
            if unique in uh:
                continue
            meta = MetaInfo(title)
            if year:
                meta.year = str(year)
            meta.type = MediaType.MOVIE if mtype == "movie" else MediaType.TV
            mediainfo = self.chain.recognize_media(meta=meta, mtype=meta.type)
            if not mediainfo:
                continue
            cn_title = mediainfo.title or title
            _record_history_item(history, {"title": cn_title, "link": link, "tmdbid": mediainfo.tmdb_id, "poster": mediainfo.get_poster_image(), "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "unique": unique})
            uh.add(unique)
            new_count += 1
        except Exception as e:
            logger.error(f"豆瓣中心：刷新 {rd['name']} 条目出错：{e}")
            continue
    self.save_data(data_key, _trim_history(history))
    logger.info(f"豆瓣中心：{rd['name']} 刷新完成，新增 {new_count} 条")
