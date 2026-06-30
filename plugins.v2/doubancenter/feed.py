"""
DoubanCenter - 榜单订阅引擎
"""
import datetime
import re
import time
from typing import Any, Dict, List, Optional

from app.chain.subscribe import SubscribeChain
from app.core.config import settings
from app.core.metainfo import MetaInfo
from app.log import logger
from app.schemas.types import MediaType
from app.utils.dom import DomUtils
from app.utils.http import RequestUtils

from . import utils
from .adapter import bangumi as bangumi_adapter
from .adapter import rss as rss_adapter
from .model import rank as rank_model
from .service import observation as observation_service
from .service import subscription as subscription_service
from .storage import records as storage

RANK_HISTORY_LIMIT = 500
DEFAULT_OBSERVE_RANK_KEYS = rank_model.DEFAULT_OBSERVE_RANK_KEYS
BUILTIN_RANKS: List[Dict[str, Any]] = rank_model.BUILTIN_RANKS


def _trim_history(history: List[dict], limit: int = RANK_HISTORY_LIMIT) -> List[dict]:
    """裁剪榜单历史，只保留最新条目。"""
    return storage.trim_records(history, limit)


def _custom_rank_history_key(source: str) -> str:
    """为自定义 RSS 生成跨进程稳定的历史数据键。"""
    return storage.custom_rank_history_key(source)


def _rank_media_type(rank: dict, item: dict) -> str:
    """根据榜单定义和 RSS 条目推断媒体类型。"""
    return rank_model.infer_media_type(rank, item)


def _rss_default_media_type(addr: str) -> str:
    """根据 RSS 地址推断默认媒体类型。"""
    return rss_adapter.default_media_type(addr)


def _record_history_item(history: List[dict], entry: dict) -> None:
    """更新或插入榜单历史条目，并原位替换观察占位。"""
    rank_model.record_history_item(history, entry)


def _history_item_subscribed(item: dict) -> bool:
    """判断历史条目是否已经产生过订阅。"""
    return subscription_service.history_item_subscribed(item)


def _history_item_existing(item: dict) -> bool:
    """判断历史条目是否已确认存在订阅。"""
    return subscription_service.history_item_existing(item)


def _history_index_by_unique(history: List[dict]) -> Dict[str, dict]:
    """按唯一标识构建榜单历史索引。"""
    return subscription_service.history_index_by_unique(history)


# 订阅过滤与观察期工具函数


def _log_anti_cheat(self, reason: str, title: str, detail: str = "", link: str = ""):
    """记录订阅过滤日志。"""
    observation_service.log_anti_cheat(self, reason, title, detail=detail, link=link)


def _cleanup_observe_logs(self, title: str = "", unique: str = "") -> None:
    """订阅成功后清理对应条目的观察日志。"""
    observation_service.cleanup_observe_logs(self, title=title, unique=unique)


def _is_existing_media(mediainfo, meta=None) -> bool:
    """判断媒体是否已存在订阅。"""
    return subscription_service.is_existing_media(mediainfo, meta=meta, subscribe_chain_cls=SubscribeChain)


def _record_existing_history(history: List[dict], unique: str, title: str = "", year: Any = "", link: str = "", mediainfo=None) -> None:
    """记录已存在订阅，避免后续再次进入观察队列。"""
    subscription_service.record_existing_history(history, unique, title=title, year=year, link=link, mediainfo=mediainfo)


def _match_blacklist_line(line: str, haystack: str) -> bool:
    """判断一行黑名单规则是否命中文本。"""
    rule = line.strip()
    if not rule:
        return False
    case_sensitive = False
    if rule.lower().startswith("case:"):
        case_sensitive = True
        rule = rule[5:].strip()
    flags = 0 if case_sensitive else re.IGNORECASE
    if rule.lower().startswith("regex:"):
        pattern = rule[6:].strip()
        try:
            return bool(pattern and re.search(pattern, haystack, flags))
        except re.error:
            rule = pattern
    source = haystack if case_sensitive else haystack.lower()
    tokens = [token for token in re.split(r"\s+", rule) if token]
    if not tokens:
        return False
    if not case_sensitive:
        tokens = [token.lower() for token in tokens]
    return all(token in source for token in tokens)


def _check_blacklist(self, title: str, description: str = "", link: str = "") -> bool:
    """标题或摘要匹配黑名单关键词时返回 True。"""
    kw = (self._blacklist_keywords or "").strip()
    if not kw:
        return False
    haystack = "\n".join([title or "", description or ""])
    for line in kw.split("\n"):
        word = line.strip()
        if word and _match_blacklist_line(word, haystack):
            logger.info(f"豆瓣中心：黑名单关键词《{word}》匹配《{title}》，跳过")
            _log_anti_cheat(self, "黑名单关键词", title, f"匹配词：{word}", link=link)
            return True
    return False


def default_observe_rank_keys() -> List[str]:
    """返回默认启用观察期的波动榜单。"""
    return observation_service.default_observe_rank_keys()


def _rank_observe_enabled(self, rank_key: str = "") -> bool:
    """判断指定榜单是否启用观察期。"""
    return observation_service.rank_observe_enabled(self, rank_key)


def _check_observe(self, unique: str, history: List[dict], title: str = "", rank_key: str = "") -> bool:
    """条目仍处于观察期内时返回 True。"""
    return observation_service.check_observe(self, unique, history, title=title, rank_key=rank_key)


def _rc(self, key: str) -> dict:
    return (self._rank_configs or {}).get(key, {})


def _ren(self, key: str) -> bool:
    return _rc(self, key).get("enabled", False)


def _rcount(self, key: str) -> int:
    return int(_rc(self, key).get("count", 0) or 0)


def _drop_stale_observations(history: List[dict], current_candidates: set) -> None:
    """将已跌出当前候选窗口的观察条目标记为结束。"""
    observation_service.drop_stale_observations(history, current_candidates)


def _positive_number(value: Any) -> bool:
    """判断值是否能解析为正数。"""
    return rank_model.positive_number(value)


def _year_below_min(value: Any, min_year: int) -> bool:
    """判断年份是否低于最低年份筛选条件。"""
    return rank_model.year_below_min(value, min_year)


def _apply_bangumi_recognition(self, item: dict, entry: dict) -> None:
    """用 MP 识别结果补全 BangumiTV 榜单的中文名和 TMDB 信息。"""
    title = str(item.get("title") or "")
    if not title:
        return
    meta = MetaInfo(title)
    year = item.get("year")
    if year:
        meta.year = str(year)
    meta.type = MediaType.TV
    tmdbid = item.get("tmdbid") or entry.get("tmdbid")
    bangumiid = _extract_bangumi_id(item) or _extract_bangumi_id(entry)
    try:
        mediainfo = _recognize_bangumi_media(self.chain, meta, tmdbid=tmdbid, bangumiid=bangumiid)
    except Exception as err:
        logger.warning(f"豆瓣中心：BangumiTV 条目《{title}》识别失败：{err}")
        return
    if not mediainfo:
        subject = _fetch_bangumi_subject(self, bangumiid)
        if subject:
            _apply_bangumi_subject(subject, entry, title=title, bangumiid=bangumiid)
        return
    cn_title = getattr(mediainfo, "title", None) or title
    if cn_title and cn_title != title:
        entry["original_title"] = title
    entry["title"] = cn_title
    entry["year"] = getattr(mediainfo, "year", None) or entry.get("year") or ""
    entry["tmdbid"] = getattr(mediainfo, "tmdb_id", None) or entry.get("tmdbid")
    entry["bangumi_id"] = getattr(mediainfo, "bangumi_id", None) or bangumiid or entry.get("bangumi_id")
    entry["bangumiid"] = entry["bangumi_id"]
    try:
        entry["poster"] = mediainfo.get_poster_image() or entry.get("poster")
    except Exception:
        pass


def _apply_display_recognition(self, item: dict, entry: dict, rank_key: str, rd: dict) -> None:
    """刷新榜单展示数据时用 MP 识别结果补全标题、海报和 TMDB 信息。"""
    title = str(item.get("title") or "")
    if not title:
        return
    meta = MetaInfo(title)
    year = item.get("year")
    if year:
        meta.year = str(year)
    media_type = MediaType.TV if rank_key == "coming" else (MediaType.MOVIE if _rank_media_type(rd, item) == "movie" else MediaType.TV)
    meta.type = media_type
    try:
        mediainfo = self.chain.recognize_media(meta=meta, mtype=media_type)
    except Exception as err:
        logger.warning(f"豆瓣中心：刷新榜单条目《{title}》识别失败：{err}")
        return
    if not mediainfo:
        return
    cn_title = getattr(mediainfo, "title", None) or title
    if cn_title and cn_title != title:
        entry["original_title"] = title
    entry["title"] = cn_title
    entry["year"] = getattr(mediainfo, "year", None) or entry.get("year") or ""
    entry["media_type"] = "movie" if media_type == MediaType.MOVIE else "tv"
    entry["tmdbid"] = getattr(mediainfo, "tmdb_id", None) or entry.get("tmdbid")
    if getattr(mediainfo, "bangumi_id", None):
        entry["bangumi_id"] = getattr(mediainfo, "bangumi_id", None)
        entry["bangumiid"] = entry["bangumi_id"]
    try:
        entry["poster"] = mediainfo.get_poster_image() or entry.get("poster")
    except Exception:
        pass


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
    """按 TMDB、Bangumi、标题顺序调用 MP 媒体识别。"""
    attempts = []
    if tmdbid and bangumiid:
        attempts.append({"tmdbid": tmdbid, "bangumiid": bangumiid})
    if bangumiid:
        attempts.append({"bangumiid": bangumiid})
    if tmdbid:
        attempts.append({"tmdbid": tmdbid})
    attempts.append({})

    last_type_error = None
    for extra in attempts:
        try:
            mediainfo = chain.recognize_media(meta=meta, mtype=MediaType.TV, **extra)
            if mediainfo:
                return mediainfo
        except TypeError as err:
            last_type_error = err
            continue
    if last_type_error:
        raise last_type_error
    return None


def _extract_bangumi_id(item: dict) -> Optional[str]:
    """从 BangumiTV 榜单条目中提取 Bangumi subject id。"""
    return bangumi_adapter.extract_subject_id(item)


def _has_cjk_text(value: Any) -> bool:
    """判断文本中是否包含中日韩统一表意文字。"""
    return bangumi_adapter.has_cjk_text(value)


def _normalize_bangumi_history(self, history: List[dict]) -> List[dict]:
    """迁移旧 BangumiTV 榜单缓存，补齐中文名和 TMDB 信息。"""
    if not isinstance(history, list):
        return []
    changed = False
    for item in history:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if not title:
            continue
        if item.get("tmdbid") and _has_cjk_text(title):
            continue
        before = (
            item.get("title"),
            item.get("year"),
            item.get("tmdbid"),
            item.get("poster"),
            item.get("original_title"),
        )
        _apply_bangumi_recognition(self, item, item)
        after = (
            item.get("title"),
            item.get("year"),
            item.get("tmdbid"),
            item.get("poster"),
            item.get("original_title"),
        )
        if after != before:
            changed = True
    if changed:
        storage.save_rank_history(self, "bangumi", history)
    return history


def _has_global_subscription_filter(self) -> bool:
    if (self._blacklist_keywords or "").strip():
        return True
    if _rank_observe_enabled(self):
        return True
    return False


def _has_rank_subscription_filter(self, rd: dict) -> bool:
    cfg = _rc(self, rd["key"])
    if int(cfg.get("count", 0) or 0) > 0:
        return True
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
        if count <= 0:
            logger.info(f"豆瓣中心：[{rd['name']}] 自动订阅数量为 0，跳过订阅候选")
            continue
        url = f"{rsshub.rstrip('/')}{rd['route']}?limit={count}"
        logger.info(f"豆瓣中心：开始处理 [{rd['name']}] {url}")
        if rd["coming"]:
            _process_coming(self, url, rd)
        else:
            _process_general(self, url, rd)
        time.sleep(1)
    for cu in (getattr(self, "_custom_rss_addrs", []) or []):
        u = cu.strip()
        if u:
            logger.info(f"豆瓣中心：自定义 RSS 已在本轮改造中跳过：{u}")
    logger.info("豆瓣中心：榜单订阅刷新完成")


def _refresh_then_subscribe(self, message: str) -> None:
    """刷新榜单展示数据后，再按当前订阅配置执行订阅。"""
    logger.info(message)
    refresh_rank_data(self)
    subscribe_to_ranks(self, refresh_when_unsafe=False)


def run_once(self) -> None:
    """立即刷新榜单数据，并按当前订阅配置执行订阅。"""
    _refresh_then_subscribe(self, "豆瓣中心：立即运行开始，先刷新 RSS 榜单，再按配置执行订阅")


def run_scheduled(self) -> None:
    """定时刷新榜单数据，并按当前订阅配置执行订阅。"""
    _refresh_then_subscribe(self, "豆瓣中心：定时运行开始，先刷新 RSS 榜单，再按配置执行订阅")


def _process_coming(self, url: str, rd: dict) -> None:
    cfg = _rc(self, rd["key"])
    min_wish = int(cfg.get("wish_count", 5000) or 5000)
    air_days = int(cfg.get("air_days", 7) or 7)
    items = _fetch_coming_rss(self, url)
    if not items:
        return
    history: List[dict] = storage.read_rank_history(self, rd["key"])
    history_index = _history_index_by_unique(history)
    for item in items:
        title, link, wish = item.get("title", ""), item.get("link", ""), item.get("wish_count", 0)
        year = item.get("year", "")
        if not title:
            continue
        unique = f"dc2_coming:{link or title}"
        if _history_item_subscribed(history_index.get(unique)) or _history_item_existing(history_index.get(unique)):
            continue
        if _check_blacklist(self, title, description=item.get("description", ""), link=link):
            continue
        if wish < min_wish:
            continue
        meta = MetaInfo(title)
        if year:
            meta.year = str(year)
        meta.type = MediaType.TV
        mediainfo = self.chain.recognize_media(meta=meta, mtype=MediaType.TV)
        if not mediainfo:
            continue
        if _is_existing_media(mediainfo, meta):
            logger.info(f"豆瓣中心：条目《{mediainfo.title or title}》已存在订阅，跳过观察与订阅")
            _record_existing_history(history, unique, title=title, year=year, link=link, mediainfo=mediainfo)
            _cleanup_observe_logs(self, title=title, unique=unique)
            _cleanup_observe_logs(self, title=mediainfo.title, unique=unique)
            history_index[unique] = {"existing": True, "existing_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "existing_reason": "subscribe"}
            continue
        ad = utils.get_tmdb_air_date(self.chain, mediainfo.tmdb_id, season=meta.begin_season)
        if not ad or not utils.is_within_days(ad, air_days):
            continue
        # 观察期：仅对选中的波动榜单延迟订阅。
        if _check_observe(self, unique, history, title=title, rank_key=rd["key"]):
            continue
        if _add_sub(self, mediainfo, meta, rank_key=rd["key"], rank_name=rd["name"], source_link=link):
            # 使用 TMDB 识别后的中文名替换原始标题
            cn_title = mediainfo.title or title
            subscribed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _record_history_item(history, {"title": cn_title, "year": year, "wish_count": wish, "air_date": ad, "link": link, "tmdbid": mediainfo.tmdb_id, "poster": mediainfo.get_poster_image(), "time": subscribed_at, "unique": unique, "subscribed": True, "subscribed_at": subscribed_at})
            history_index[unique] = {"subscribed": True, "subscribed_at": subscribed_at}
    storage.save_rank_history(self, rd["key"], history)


def _process_general(self, url: str, rd: dict) -> None:
    cfg = _rc(self, rd["key"])
    min_vote = float(cfg.get("vote", 0) or 0)
    min_year = int(cfg.get("year", 0) or 0)
    items = _fetch_rss(self, url)
    if not items:
        return
    history: List[dict] = storage.read_rank_history(self, rd["key"])
    history_index = _history_index_by_unique(history)
    current_candidates = set()
    for item in items:
        title, link, year = item.get("title", ""), item.get("link", ""), item.get("year")
        mtype = _rank_media_type(rd, item)
        if not title:
            continue
        unique = f"dc2_rank:{link or title}"
        current_candidates.add(unique)
        if _history_item_subscribed(history_index.get(unique)) or _history_item_existing(history_index.get(unique)):
            continue
        if _check_blacklist(self, title, description=item.get("description", ""), link=link):
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
        if _is_existing_media(mediainfo, meta):
            logger.info(f"豆瓣中心：条目《{mediainfo.title or title}》已存在订阅，跳过观察与订阅")
            _record_existing_history(history, unique, title=title, year=year, link=link, mediainfo=mediainfo)
            _cleanup_observe_logs(self, title=title, unique=unique)
            _cleanup_observe_logs(self, title=mediainfo.title, unique=unique)
            history_index[unique] = {"existing": True, "existing_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "existing_reason": "subscribe"}
            continue
        # 观察期：仅对选中的波动榜单延迟订阅。
        if _check_observe(self, unique, history, title=title, rank_key=rd["key"]):
            continue
        if _add_sub(self, mediainfo, meta, rank_key=rd["key"], rank_name=rd["name"], source_link=link):
            cn_title = mediainfo.title or title
            subscribed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _record_history_item(history, {"title": cn_title, "year": mediainfo.year or year or "", "media_type": mtype, "link": link, "tmdbid": mediainfo.tmdb_id, "poster": mediainfo.get_poster_image(), "time": subscribed_at, "unique": unique, "subscribed": True, "subscribed_at": subscribed_at})
            history_index[unique] = {"subscribed": True, "subscribed_at": subscribed_at}
    _drop_stale_observations(history, current_candidates)
    storage.save_rank_history(self, rd["key"], history)


def _process_items(self, items: List[dict], source: str) -> None:
    history: List[dict] = storage.read_custom_rank_history(self, source)
    history_index = _history_index_by_unique(history)
    for item in items:
        title, link, mtype, year = item.get("title", ""), item.get("link", ""), item.get("mtype", ""), item.get("year")
        if not title:
            continue
        unique = f"dc2_rank:{link or title}"
        if _history_item_subscribed(history_index.get(unique)) or _history_item_existing(history_index.get(unique)):
            continue
        if _check_blacklist(self, title, description=item.get("description", ""), link=link):
            continue
        meta = MetaInfo(title)
        if year:
            meta.year = str(year)
        meta.type = MediaType.MOVIE if mtype == "movie" else MediaType.TV
        mediainfo = self.chain.recognize_media(meta=meta, mtype=meta.type)
        if not mediainfo:
            continue
        if _is_existing_media(mediainfo, meta):
            logger.info(f"豆瓣中心：条目《{mediainfo.title or title}》已存在订阅，跳过观察与订阅")
            _record_existing_history(history, unique, title=title, year=year, link=link, mediainfo=mediainfo)
            _cleanup_observe_logs(self, title=title, unique=unique)
            _cleanup_observe_logs(self, title=mediainfo.title, unique=unique)
            history_index[unique] = {"existing": True, "existing_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "existing_reason": "subscribe"}
            continue
        # 观察期：仅对自定义源显式配置时延迟订阅。
        if _check_observe(self, unique, history, title=title, rank_key=source):
            continue
        if _add_sub(self, mediainfo, meta, source_link=link):
            cn_title = mediainfo.title or title
            subscribed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _record_history_item(history, {"title": cn_title, "link": link, "tmdbid": mediainfo.tmdb_id, "poster": mediainfo.get_poster_image(), "time": subscribed_at, "unique": unique, "subscribed": True, "subscribed_at": subscribed_at})
            history_index[unique] = {"subscribed": True, "subscribed_at": subscribed_at}
    storage.save_custom_rank_history(self, source, history)


def _write_subscribe_record(self, mediainfo, rank_key: str = "", rank_name: str = "", status: str = "success", reason: str = "", source_link: str = "") -> None:
    """写入自动订阅历史记录。"""
    subscription_service.write_subscribe_record(self, mediainfo, rank_key=rank_key, rank_name=rank_name, status=status, reason=reason, source_link=source_link)


def _add_sub(self, mediainfo, meta=None, rank_key="", rank_name="", source_link: str = "") -> bool:
    """按 MP 默认 TMDB 语义执行自动订阅。"""
    return subscription_service.add_subscription(
        self,
        mediainfo,
        meta=meta,
        rank_key=rank_key,
        rank_name=rank_name,
        source_link=source_link,
        subscribe_chain_cls=SubscribeChain,
    )


def _fetch_coming_rss(self, addr: str) -> List[dict]:
    rss_adapter.RequestUtils = RequestUtils
    rss_adapter.DomUtils = DomUtils
    return rss_adapter.fetch_coming(self, addr)


def _fetch_rss(self, addr: str) -> List[dict]:
    rss_adapter.RequestUtils = RequestUtils
    rss_adapter.DomUtils = DomUtils
    return rss_adapter.fetch_rank(self, addr)


def get_enabled_rank_keys(self) -> List[str]:
    return [rd["key"] for rd in BUILTIN_RANKS if _ren(self, rd["key"])]


def get_rank_history_by_key(self, rank_key: str) -> List[dict]:
    history = storage.read_rank_history(self, rank_key)
    if rank_key == "bangumi":
        return _normalize_bangumi_history(self, history)
    return history


def _dashboard_rank_sort_key(item: dict) -> tuple:
    """生成仪表盘榜单排序键。"""
    try:
        rank_index = int(item.get("rank_index"))
    except (TypeError, ValueError):
        rank_index = 10 ** 9
    return rank_index, str(item.get("title") or "")


def get_dashboard_rank_items(self, rank_key: str, limit: int = 5) -> List[dict]:
    """返回最新 RSS 批次中的仪表盘榜单条目。"""
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
    """刷新 RSS 榜单数据供仪表盘展示，不触发订阅。"""
    # rank_keys: 可选的榜单 key 列表。
    # 仪表盘刷新固定拉取 10 条，不受 count 配置限制。
    # 返回：{rank_key: [items]}，代表本次刷新结果。

    result = {}
    try:
        rsshub = utils.normalize_rss_domain(self._rsshub_domain)
        targets = [rd for rd in BUILTIN_RANKS if (rank_keys is None and _ren(self, rd["key"])) or (rank_keys and rd["key"] in rank_keys)]
        for rd in targets:
            key = rd["key"]
            # 仪表盘刷新只拉取 5 条轻量展示数据。
            url = f"{rsshub.rstrip('/')}{rd['route']}?limit=5"
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
    """合并拉取到的 RSS 榜单条目，并更新当前批次顺序。"""
    history: List[dict] = storage.read_rank_history(self, rank_key)
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
            tmdbid = item.get("tmdbid")
            poster = item.get("poster")
            cn_title = title
            douban_id = item.get("doubanid")  # 优先使用 RSS 中解析的豆瓣 ID
            meta_type = "tv" if rank_key == "coming" else _rank_media_type(rd, item)
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
                _apply_display_recognition(self, item, entry, rank_key, rd)
            elif rank_key == "bangumi":
                _apply_bangumi_recognition(self, item, entry)
            else:
                _apply_display_recognition(self, item, entry, rank_key, rd)
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
    history = storage.save_rank_history(self, rank_key, history)
    logger.info(
        f"豆瓣中心：{rd['name']} 刷新完成，当前批次 {len(items)} 条，新增 {new_count} 条，累计 {len(history)} 条"
    )
    return history


def _refresh_coming(self, url, rd):
    """只刷新即将上映榜单数据，不触发订阅。"""
    items = _fetch_coming_rss(self, url)
    if not items:
        return
    history: List[dict] = storage.read_rank_history(self, rd["key"])
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
    storage.save_rank_history(self, rd["key"], history)
    logger.info(f"豆瓣中心：即将上映刷新完成，新增 {new_count} 条")


def _refresh_general(self, url, rd):
    """只刷新普通榜单数据，不触发订阅。"""
    items = _fetch_rss(self, url)
    if not items:
        return
    history: List[dict] = storage.read_rank_history(self, rd["key"])
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
    storage.save_rank_history(self, rd["key"], history)
    logger.info(f"豆瓣中心：{rd['name']} 刷新完成，新增 {new_count} 条")
