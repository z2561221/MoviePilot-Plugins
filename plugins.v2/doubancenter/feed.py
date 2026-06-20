"""
DoubanCenter - 榜单订阅引擎
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
    """按最新记录裁剪榜单历史，避免插件数据无限增长。"""
    if limit <= 0 or len(history) <= limit:
        return history
    return history[-limit:]


def _custom_rank_history_key(source: str) -> str:
    """为自定义 RSS 生成跨进程稳定的历史数据键。"""
    digest = hashlib.sha1((source or "").encode("utf-8")).hexdigest()[:16]
    return f"rank_history_custom_{digest}"


def _rank_media_type(rank: dict, item: dict) -> str:
    """根据榜单定义和 RSS 条目判断媒体类型。"""
    raw_type = str((item or {}).get("mtype") or "").lower()
    if raw_type in ("movie", "tv"):
        return raw_type
    key = str((rank or {}).get("key") or "").lower()
    route = str((rank or {}).get("route") or "").lower()
    if "movie" in key or "/movie" in route:
        return "movie"
    return "tv"


def _rss_default_media_type(addr: str) -> str:
    """根据 RSS 地址推断默认媒体类型。"""
    text = str(addr or "").lower()
    if "movie_" in text or "/movie" in text:
        return "movie"
    return "tv"


def _record_history_item(history: List[dict], entry: dict) -> None:
    """写入榜单历史；若已有观察期占位记录则原位替换。"""
    stored = dict(entry or {})
    stored.pop("observing", None)
    unique = stored.get("unique")
    if unique:
        for index, item in enumerate(history):
            if item.get("unique") == unique:
                history[index] = stored
                return
    history.append(stored)


# 防刷榜工具函数


def _log_anti_cheat(self, reason: str, title: str, detail: str = ""):
    """记录防刷榜拦截日志"""
    logs = self.get_data("anti_cheat_logs") or []
    logs.append({
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "reason": reason,
        "title": title,
        "detail": detail
    })
    # 只保留最近100条
    if len(logs) > 100:
        logs = logs[-100:]
    self.save_data("anti_cheat_logs", logs)


def _check_blacklist(self, title: str) -> bool:
    """检查标题是否匹配黑名单关键词，匹配返回True（跳过）"""
    kw = (self._blacklist_keywords or "").strip()
    if not kw:
        return False
    for line in kw.split("\n"):
        word = line.strip()
        if word and word.lower() in title.lower():
            logger.info(f"豆瓣中心：黑名单关键词「{word}」匹配「{title}」，跳过")
            _log_anti_cheat(self, "黑名单关键词", title, f"匹配词：{word}")
            return True
    return False


def _check_observe(self, unique: str, history: List[dict], title: str = "") -> bool:
    """检查观察期：条目首次出现未满观察期则跳过订阅
    返回True表示还在观察期内（跳过）
    """
    if not self._anti_cheat_enabled:
        return False
    days = int(self._observe_days or 0)
    if days <= 0:
        return False
    now = datetime.datetime.now()
    for h in history:
        if h.get("unique") == unique:
            first_seen = h.get("first_seen") or h.get("time", "")
            if first_seen:
                try:
                    ft = datetime.datetime.strptime(first_seen, "%Y-%m-%d %H:%M:%S")
                    elapsed = (now - ft).days
                    if elapsed < days:
                        logger.info(f"豆瓣中心：条目「{h.get('title')}」观察期未满（{elapsed}/{days}天），跳过订阅")
                        _log_anti_cheat(self, "观察期未满", h.get("title", ""), f"已过{elapsed}天，需{days}天")
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
    logger.info(f"豆瓣中心：条目《{title or unique}》首次进入观察期（0/{days}天），跳过订阅")
    _log_anti_cheat(self, "观察期首次记录", title or unique, f"需观察{days}天")
    return True


def _check_anti_cheat(self, mediainfo) -> bool:
    """检查TMDB评分是否低于防刷榜阈值，低于返回True（跳过）"""
    if not self._anti_cheat_enabled:
        return False
    threshold = self._anti_cheat_min_vote
    if threshold <= 0:
        return False
    vote = mediainfo.vote_average
    if vote is None:
        logger.info(f"豆瓣中心：条目「{mediainfo.title}」无TMDB评分，跳过订阅")
        _log_anti_cheat(self, "无TMDB评分", mediainfo.title, "")
        return True
    if vote < threshold:
        logger.info(f"豆瓣中心：条目「{mediainfo.title}」TMDB评分{vote}低于阈值{threshold}，跳过订阅")
        _log_anti_cheat(self, "TMDB评分过低", mediainfo.title, f"评分{vote}，阈值{threshold}")
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


def subscribe_to_ranks(self) -> None:
    if not _has_subscription_safety_filter(self):
        logger.warning("豆瓣中心：未配置任何订阅筛选条件，已跳过自动订阅；仅刷新榜单历史以避免误触发大量订阅")
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
            logger.info(f"豆瓣中心：自定义RSS {u}")
            items = _fetch_rss(self, u)
            if items:
                _process_items(self, items, u)
            time.sleep(1)
    logger.info("豆瓣中心：榜单订阅刷新完成")


def _process_coming(self, url: str, rd: dict) -> None:
    cfg = _rc(self, rd["key"])
    min_wish = int(cfg.get("wish_count", 5000) or 5000)
    air_days = int(cfg.get("air_days", 7) or 7)
    items = _fetch_coming_rss(self, url)
    if not items:
        return
    history: List[dict] = self.get_data("coming_history") or []
    uh = {i.get("unique") for i in history}
    for item in items:
        title, link, wish = item.get("title", ""), item.get("link", ""), item.get("wish_count", 0)
        year, regions, genres = item.get("year", ""), item.get("regions", []), item.get("genres", [])
        unique = f"dc2_coming:{link or title}"
        if unique in uh or wish < min_wish:
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
        # 防刷榜：黑名单关键词
        if _check_blacklist(self, title):
            continue
        # 防刷榜：TMDB评分过滤
        if _check_anti_cheat(self, mediainfo):
            continue
        # 防刷榜：观察期
        if _check_observe(self, unique, history, title=title):
            continue
        ad = utils.get_tmdb_air_date(self.chain, mediainfo.tmdb_id, season=meta.begin_season)
        if not ad or not utils.is_within_days(ad, air_days):
            continue
        if _add_sub(self, mediainfo, meta, rank_key=rd["key"], rank_name=rd["name"]):
            # 使用TMDB识别后的中文名替换原始标题
            cn_title = mediainfo.title or title
            _record_history_item(history, {"title": cn_title, "year": year, "wish_count": wish, "air_date": ad, "link": link, "tmdbid": mediainfo.tmdb_id, "poster": mediainfo.get_poster_image(), "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "unique": unique})
            uh.add(unique)
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
    uh = {i.get("unique") for i in history}
    for item in items:
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
        if min_vote > 0 and mediainfo.vote_average and mediainfo.vote_average < min_vote:
            continue
        if min_year > 0 and mediainfo.year and int(mediainfo.year) < min_year:
            continue
        # 防刷榜：黑名单关键词
        if _check_blacklist(self, title):
            continue
        # 防刷榜：TMDB评分过滤
        if _check_anti_cheat(self, mediainfo):
            continue
        # 防刷榜：观察期
        if _check_observe(self, unique, history, title=title):
            continue
        if _add_sub(self, mediainfo, meta, rank_key=rd["key"], rank_name=rd["name"]):
            cn_title = mediainfo.title or title
            _record_history_item(history, {"title": cn_title, "year": mediainfo.year or year or "", "media_type": mtype, "link": link, "tmdbid": mediainfo.tmdb_id, "poster": mediainfo.get_poster_image(), "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "unique": unique})
            uh.add(unique)
    self.save_data(data_key, _trim_history(history))


def _process_items(self, items: List[dict], source: str) -> None:
    data_key = _custom_rank_history_key(source)
    history: List[dict] = self.get_data(data_key) or []
    uh = {i.get("unique") for i in history}
    for item in items:
        title, link, mtype, year = item.get("title", ""), item.get("link", ""), item.get("mtype", ""), item.get("year")
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
        # 防刷榜：黑名单关键词
        if _check_blacklist(self, title):
            continue
        # 防刷榜：TMDB评分过滤
        if _check_anti_cheat(self, mediainfo):
            continue
        # 防刷榜：观察期
        if _check_observe(self, unique, history, title=title):
            continue
        if _add_sub(self, mediainfo, meta):
            cn_title = mediainfo.title or title
            _record_history_item(history, {"title": cn_title, "link": link, "tmdbid": mediainfo.tmdb_id, "poster": mediainfo.get_poster_image(), "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "unique": unique})
            uh.add(unique)
    self.save_data(data_key, _trim_history(history))


def _add_sub(self, mediainfo, meta=None, rank_key="", rank_name="") -> bool:
    dc = DownloadChain()
    sc = SubscribeChain()
    ef, _ = dc.get_no_exists_info(meta=meta, mediainfo=mediainfo)
    if ef or sc.exists(mediainfo=mediainfo, meta=meta):
        return False
    res = utils.build_resolution_rule(self._resolution_filters)
    sid, msg = sc.add(title=mediainfo.title, year=mediainfo.year or "", mtype=mediainfo.type if mediainfo.type else MediaType.TV, tmdbid=mediainfo.tmdb_id, season=meta.begin_season if meta and meta.type == MediaType.TV else None, resolution=res, sites=None, exist_ok=True, username="豆瓣中心", message=False)
    if not sid:
        return False
    if self._notify:
        self.post_message(mtype=NotificationType.Subscribe, title=f"豆瓣中心：{mediainfo.title_year} 已添加订阅", text=f"类型：{'电影' if mediainfo.type == MediaType.MOVIE else '电视剧'}\n", image=mediainfo.get_message_image())
    # 保存订阅成功记录
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
    # 只保留最近500条
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
        logger.error(f"获取即将播出RSS失败：{err}")
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
            if re.search(r"第[一二三四五六七八九十\d]+季|Season\s*\d+", title, re.IGNORECASE):
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
        logger.error(f"获取RSS失败：{err}")
        return []


def get_enabled_rank_keys(self) -> List[str]:
    return [rd["key"] for rd in BUILTIN_RANKS if _ren(self, rd["key"])]


def get_rank_history_by_key(self, rank_key: str) -> List[dict]:
    if rank_key == "coming":
        return self.get_data("coming_history") or []
    data_key = f"rank_history_{rank_key}"
    return self.get_data(data_key) or []


def refresh_rank_data(self, rank_keys=None):
    """刷新RSS数据：只拉取最新榜单数据更新历史记录，不触发订阅
    rank_keys: 指定要刷新的榜单key列表，None表示刷新所有已启用的榜单
    仪表盘刷新固定拉取10条，不受count配置限制
    返回: {rank_key: [items]} 本次拉取到的完整数据
    """
    result = {}
    try:
        rsshub = utils.normalize_rss_domain(self._rsshub_domain)
        targets = [rd for rd in BUILTIN_RANKS if (rank_keys is None and _ren(self, rd["key"])) or (rank_keys and rd["key"] in rank_keys)]
        for rd in targets:
            key = rd["key"]
            # 仪表盘刷新固定拉10条，不受count配置限制
            url = f"{rsshub.rstrip('/')}{rd['route']}?limit=10"
            logger.info(f"豆瓣中心：刷新RSS [{rd['name']}] {url}")
            if rd["coming"]:
                items = _fetch_coming_rss(self, url)
            else:
                items = _fetch_rss(self, url)
            if items:
                result[key] = _merge_rank_items(self, key, items, rd)
            time.sleep(1)
        logger.info("豆瓣中心：RSS刷新完成")
    except Exception as err:
        logger.error(f"豆瓣中心：刷新RSS失败：{err}", exc_info=True)
    return result


def _merge_rank_items(self, rank_key, items, rd):
    """将RSS拉取到的条目合并到历史记录中，返回完整列表"""
    if rank_key == "coming":
        data_key = "coming_history"
    else:
        data_key = f"rank_history_{rank_key}"
    history: List[dict] = self.get_data(data_key) or []
    uh = {i.get("unique") for i in history}
    new_count = 0
    for item in items:
        try:
            title = item.get("title", "")
            link = item.get("link", "")
            if not title:
                continue
            unique = f"dc2_rank:{link or title}" if rank_key != "coming" else f"dc2_coming:{link or title}"
            if unique in uh:
                continue
            year = item.get("year", "")
            # 尝试识别媒体信息，失败时也保留条目（只是没有海报和tmdbid）
            tmdbid = None
            poster = None
            cn_title = title
            douban_id = item.get("doubanid")  # 优先用RSS中解析的豆瓣ID
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
                    # 从mediainfo获取豆瓣ID（TMDB识别结果可能包含豆瓣映射）
                    if not douban_id and hasattr(mediainfo, 'douban_id') and mediainfo.douban_id:
                        douban_id = mediainfo.douban_id
            except Exception:
                pass
            entry = {"title": cn_title, "year": year or "", "media_type": meta_type, "link": link, "tmdbid": tmdbid, "poster": poster, "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "unique": unique, "douban_id": douban_id}
            if rank_key == "coming":
                entry.update({"year": year, "wish_count": item.get("wish_count", 0)})
            _record_history_item(history, entry)
            uh.add(unique)
            new_count += 1
        except Exception as e:
            logger.error(f"豆瓣中心：合并{rank_key}条目出错：{e}")
            continue
    history = _trim_history(history)
    self.save_data(data_key, history)
    logger.info(f"豆瓣中心：{rd['name']} 刷新完成，新增 {new_count} 条，共 {len(history)} 条")
    return history


def _refresh_coming(self, url, rd):
    """只刷新即将上映榜单数据，不订阅，不应用条件过滤"""
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
    """只刷新普通榜单数据，不订阅，不应用条件过滤"""
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
            logger.error(f"豆瓣中心：刷新{rd['name']}条目出错：{e}")
            continue
    self.save_data(data_key, _trim_history(history))
    logger.info(f"豆瓣中心：{rd['name']} 刷新完成，新增 {new_count} 条")
