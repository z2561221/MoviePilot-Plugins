"""榜单候选筛选、观察与订阅，传统RSS和快照共用同一处理路径。"""

import datetime
import re
from typing import Any, Optional

from app.chain.subscribe import SubscribeChain
from app.schemas.types import MediaType
from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.media import MetaInfo
from app.sdk.network import RequestUtils
from app.sdk.utilities import DomUtils

from .. import utils
from ..adapter import rss as rss_adapter
from ..model import rank as rank_model
from ..model.rank_candidate import RankCandidate
from ..storage import records as storage
from . import lifecycle, rank_notifications, rank_recognition, rank_timing
from . import observation as observation_service
from . import rank_subscription as rank_subscription_service
from . import subscription as subscription_service
from .rank_media import _resolved_media_type_name

_record_history_item = rank_model.record_history_item
_history_index_by_unique = subscription_service.history_index_by_unique
_history_item_subscribed = subscription_service.history_item_subscribed
_history_item_existing = subscription_service.history_item_existing
_year_below_min = rank_model.year_below_min

def _log_anti_cheat(self, reason: str, title: str, detail: str = "", link: str = ""):
    """记录订阅过滤日志。"""
    observation_service.log_anti_cheat(self, reason, title, detail=detail, link=link)



def _cleanup_observe_logs(self, title: str = "", unique: str = "") -> None:
    """订阅成功后清理对应条目的观察日志。"""
    observation_service.cleanup_observe_logs(self, title=title, unique=unique)



def _is_existing_media(mediainfo, meta=None) -> Optional[bool]:
    """判断媒体是否已存在订阅。"""
    return subscription_service.is_existing_media(mediainfo, meta=meta, subscribe_chain_cls=SubscribeChain)



def _record_existing_history(
    history: list[dict],
    unique: str,
    title: str = "",
    year: Any = None,
    link: str = "",
    mediainfo=None,
    rank_key: str = "",
    rank_name: str = "",
    media_type: str = "",
    season: Any = None,
    prefer_title: bool = False,
) -> None:
    """记录已存在订阅，避免后续再次进入观察队列。"""
    subscription_service.record_existing_history(
        history,
        unique,
        title=title,
        year=year,
        link=link,
        mediainfo=mediainfo,
        rank_key=rank_key,
        rank_name=rank_name,
        media_type=media_type,
        season=season,
        prefer_title=prefer_title,
    )



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



def _blacklist_description(*sources: Any) -> str:
    """汇总 RSS 原名、摘要、分类、地区与类型字段供黑名单匹配。"""
    values: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in ("original_title", "description", "category", "regions", "genres"):
            value = source.get(key)
            if isinstance(value, (list, tuple, set)):
                text = " ".join(str(item).strip() for item in value if str(item).strip())
            else:
                text = str(value or "").strip()
            if text:
                values.append(text)
    return "\n".join(values)



def _check_blacklist(self, title: str, description: str = "", link: str = "") -> bool:
    """标题或 RSS 文本字段匹配黑名单关键词时返回 True。"""
    kw = (self._blacklist_keywords or "").strip()
    if not kw:
        return False
    haystack = "\n".join([title or "", description or ""])
    for line in kw.split("\n"):
        word = line.strip()
        if word and _match_blacklist_line(word, haystack):
            logger.info(f"豆瓣中心：黑名单关键词《{word}》匹配《{title}》，跳过")
            _log_anti_cheat(self, "黑名拦截", title, f"匹配词：{word}", link=link)
            return True
    return False



def _check_observe(self, unique: str, history: list[dict], title: str = "", rank_key: str = "") -> bool:
    """条目仍处于观察期内时返回 True。"""
    return observation_service.check_observe(self, unique, history, title=title, rank_key=rank_key)



def _rc(self, key: str) -> dict:
    """读取指定榜单的订阅配置。"""
    return rank_subscription_service.rank_config(self._rank_configs, key)



def _drop_stale_observations(history: list[dict], current_candidates: set) -> None:
    """将已跌出当前候选窗口的观察条目标记为结束。"""
    observation_service.drop_stale_observations(history, current_candidates)



def _log_rank_skip(rd: dict, title: str, reason: str, result_lines: Optional[list[str]] = None) -> None:
    """输出榜单条目跳过原因。"""
    rank_name = (rd or {}).get("name") or (rd or {}).get("key") or "榜单"
    message = f"跳过《{title or '未命名条目'}》：{reason}"
    if result_lines is not None:
        result_lines.append(f"- {message}")
        return
    logger.info(f"豆瓣中心：[{rank_name}] {message}")



def _check_rank_region(self, rd: dict, item: dict, entry: dict = None, mediainfo=None, result_lines: Optional[list[str]] = None) -> bool:
    """执行榜单独立地区条件，未知地区时保守跳过并留下诊断。"""
    config = _rc(self, rd["key"])
    matched, reason = rank_subscription_service.region_filter_result(
        config, item=item, entry=entry, mediainfo=mediainfo
    )
    if matched:
        return True
    title = str((entry or {}).get("title") or (item or {}).get("title") or "")
    _log_rank_skip(rd, title, reason, result_lines=result_lines)
    selected = rank_subscription_service._normalize_regions_for_filter(config.get("regions"))
    _log_anti_cheat(
        self,
        reason,
        title,
        detail=f"榜单地区条件：{','.join(selected)}",
        link=str((entry or {}).get("link") or (item or {}).get("link") or ""),
    )
    return False



def _snapshot_media_type(rd: dict, item: dict, entry: dict, mediainfo=None):
    """根据快照条目生成 MoviePilot 媒体类型。"""
    mtype = _resolved_media_type_name(rd, item, mediainfo)
    if str((entry or {}).get("media_type") or "").lower() in ("movie", "tv"):
        mtype = str(entry.get("media_type")).lower()
    return MediaType.MOVIE if mtype == "movie" else MediaType.TV



def _snapshot_meta(item: dict, entry: dict, media_type) -> MetaInfo:
    """根据快照条目生成订阅所需的 MetaInfo。"""
    title = str((item or {}).get("title") or (entry or {}).get("original_title") or (entry or {}).get("title") or "")
    meta = MetaInfo(title)
    year = (item or {}).get("year") or (entry or {}).get("year")
    if year:
        meta.year = str(year)
    meta.type = media_type
    season = utils.normalize_season((entry or {}).get("season"))
    if season is None:
        season = (item or {}).get("season")
    meta.begin_season = utils.resolve_media_season(
        meta,
        season=season,
        titles=((entry or {}).get("original_title"), (entry or {}).get("title")),
    )
    return meta



def _snapshot_poster(mediainfo, entry: dict) -> str:
    """从识别结果或榜单快照中提取海报地址。"""
    try:
        return mediainfo.get_poster_image() or (entry or {}).get("poster")
    except Exception:
        return (entry or {}).get("poster")



def _add_sub(
    self,
    mediainfo,
    meta=None,
    rank_key="",
    rank_name="",
    source_link: str = "",
    record_title: str = "",
    record_year: Optional[str] = None,
) -> bool:
    """按 MP 默认 TMDB 语义执行自动订阅。"""
    return subscription_service.add_subscription(
        self,
        mediainfo,
        meta=meta,
        rank_key=rank_key,
        rank_name=rank_name,
        source_link=source_link,
        record_title=record_title if rank_key == "bangumi" else "",
        record_year=record_year,
        subscribe_chain_cls=SubscribeChain,
    )



def _fetch_coming_rss(self, addr: str) -> list[dict]:
    """通过 RSS 适配器拉取即将上映条目。"""
    return rss_adapter.fetch_coming(
        self,
        addr,
        request_utils_cls=RequestUtils,
        dom_utils=DomUtils,
        settings_obj=settings,
    )



def _fetch_rss(self, addr: str) -> list[dict]:
    """通过 RSS 适配器拉取通用榜单条目。"""
    return rss_adapter.fetch_rank(
        self,
        addr,
        request_utils_cls=RequestUtils,
        dom_utils=DomUtils,
        settings_obj=settings,
    )



@lifecycle.rank_locked
def _process_snapshots(self, snapshots, rd, *, coming, result_lines=None):
    """两种榜单只保留各自筛选策略，共用查重、观察、订阅及保存流程。"""
    cfg = _rc(self, rd["key"])
    min_vote = float(cfg.get("vote", 0) or 0)
    min_year = int(cfg.get("year", 0) or 0) if not coming else 0
    min_wish = int(cfg.get("wish_count", 0) or 0) if coming else 0
    air_days = int(cfg.get("air_days", 0) or 0)
    date_mode = rank_model.DATE_MODE_FUTURE if coming else rank_model.rank_date_mode(rd)
    history = storage.read_rank_history(self, rd["key"])
    history_index = _history_index_by_unique(history)
    current_candidates = set()
    for snapshot in snapshots or []:
        candidate = RankCandidate.from_snapshot(snapshot)
        if candidate is None:
            continue
        item, entry = candidate.raw, candidate.entry
        title = str(entry.get("title") or item.get("title") or "")
        if not title:
            continue
        link = entry.get("link") or item.get("link") or ""
        year = entry.get("year") or item.get("year") or ""
        wish = int(entry.get("wish_count") or item.get("wish_count") or 0) if coming else 0
        prefix = "dc2_coming" if coming else "dc2_rank"
        unique = entry.get("unique") or f"{prefix}:{link or item.get('title') or title}"
        current_candidates.add(unique)
        previous = history_index.get(unique)
        if ((previous or {}).get("observe_deleted") or _history_item_subscribed(previous) or _history_item_existing(previous)):
            _log_rank_skip(rd, title, "历史中已订阅或已存在", result_lines=result_lines)
            continue
        if _check_blacklist(self, title, description=_blacklist_description(entry, item), link=link):
            _log_rank_skip(rd, title, "命中黑名单", result_lines=result_lines)
            continue
        if coming and min_wish > 0 and wish < min_wish:
            _log_rank_skip(rd, title, f"想看 {wish} < {min_wish}", result_lines=result_lines)
            continue
        mediainfo = candidate.resolve()
        if not mediainfo:
            _log_rank_skip(rd, title, "TMDB 识别无结果", result_lines=result_lines)
            continue
        media_type = MediaType.TV if coming else _snapshot_media_type(rd, item, entry, mediainfo)
        meta = candidate.meta or _snapshot_meta(item, entry, media_type)
        if not coming:
            entry["source_year"] = (entry.get("source_year") or item.get("source_year")
                                    or (item.get("year") if rd.get("key") != "bangumi" else ""))
            year, air_date = rank_timing.resolve_release(self, mediainfo, meta.begin_season, entry=entry, require_date=air_days > 0)
            if min_year > 0 and not year:
                _log_rank_skip(rd, title, "未获取到本季年份，保留待重试", result_lines=result_lines)
                continue
            if _year_below_min(year, min_year):
                _log_rank_skip(rd, title, f"年份 {year} < {min_year}", result_lines=result_lines)
                continue
        if not _check_rank_region(self, rd, item, entry, mediainfo, result_lines=result_lines):
            continue
        vote_average = getattr(mediainfo, "vote_average", None)
        if min_vote > 0 and vote_average and vote_average < min_vote:
            _log_rank_skip(rd, title, f"评分 {vote_average} < {min_vote}", result_lines=result_lines)
            continue
        mtype = "tv" if coming else _resolved_media_type_name(rd, item, mediainfo)
        existing_state = _is_existing_media(mediainfo, meta)
        if existing_state is None:
            logger.warning(f"豆瓣中心：条目《{getattr(mediainfo, 'title', '')}》订阅状态未知，保留记录待下轮重试")
            continue
        if existing_state:
            _log_rank_skip(rd, getattr(mediainfo, "title", "") or title, "已存在订阅，跳过观察与订阅", result_lines=result_lines)
            _record_existing_history(history, unique, title=title, year=year, link=link, mediainfo=mediainfo,
                                     rank_key=rd["key"], rank_name=rd["name"], media_type=mtype,
                                     season=meta.begin_season, prefer_title=not coming and rd["key"] == "bangumi")
            _cleanup_observe_logs(self, title=title, unique=unique)
            _cleanup_observe_logs(self, title=getattr(mediainfo, "title", ""), unique=unique)
            history_index[unique] = {"existing": True, "existing_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "existing_reason": "subscribe"}
            continue
        if coming:
            air_date = utils.get_tmdb_air_date(self.chain, mediainfo.tmdb_id, season=meta.begin_season, mediainfo=mediainfo)
        if air_days > 0:
            if not air_date:
                target = f"第{meta.begin_season}季首播日期" if coming and meta.begin_season is not None else "上映日期"
                _log_rank_skip(rd, title, f"未获取到{target}，下轮重试" if coming else "未获取到上映日期", result_lines=result_lines)
                continue
            within_window = (utils.is_within_days(air_date, air_days) if date_mode == rank_model.DATE_MODE_FUTURE
                             else utils.is_within_recent_days(air_date, air_days))
            if not within_window:
                label = "未来" if date_mode == rank_model.DATE_MODE_FUTURE else "最近"
                _log_rank_skip(rd, title, f"上映日期 {air_date} 不在{label} {air_days} 天内", result_lines=result_lines)
                continue
        if _check_observe(self, unique, history, title=title, rank_key=rd["key"]):
            rank_notifications.enrich_observation(history, unique, rd, item, mediainfo, meta,
                                                 year=year, air_date=air_date, media_type=mtype)
            _log_rank_skip(rd, title, "观察期规则拦截", result_lines=result_lines)
            continue
        display_title = entry.get("title") or item.get("display_title") or title
        options = {} if coming else {"record_title": display_title, "record_year": year}
        if _add_sub(self, mediainfo, meta, rank_key=rd["key"], rank_name=rd["name"], source_link=link, **options):
            cn_title = mediainfo.title or title
            subscribed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            record = {"title": display_title if not coming and rd["key"] == "bangumi" else cn_title,
                      "year": year, "air_date": air_date, "link": link, "tmdbid": mediainfo.tmdb_id,
                      "poster": _snapshot_poster(mediainfo, entry), "time": subscribed_at,
                      "unique": unique, "subscribed": True, "subscribed_at": subscribed_at,
                      "rank_key": rd["key"], "rank_name": rd["name"], "media_type": mtype, "season": meta.begin_season}
            if coming:
                record["wish_count"] = wish
            else:
                record["tmdb_title"] = entry.get("tmdb_title") or getattr(mediainfo, "title", None) or ""
            _record_history_item(history, record)
            history_index[unique] = {"subscribed": True, "subscribed_at": subscribed_at}
            if result_lines is not None:
                result_lines.append(f"- 已订阅《{cn_title}》")
            else:
                logger.info(f"豆瓣中心：[{rd['name']}] 已订阅《{cn_title}》")
    _drop_stale_observations(history, current_candidates)
    storage.save_rank_history(self, rd["key"], history)
    rank_notifications.send_pending(self, rd)


def _process_coming_snapshots(self, snapshots, rd, result_lines=None):
    return _process_snapshots(self, snapshots, rd, coming=True, result_lines=result_lines)


def _process_general_snapshots(self, snapshots, rd, result_lines=None):
    return _process_snapshots(self, snapshots, rd, coming=False, result_lines=result_lines)






def _recognize_rss_item(plugin, item, rank):
    return rank_recognition.recognize_rss_item(plugin, item, rank)


@lifecycle.rank_locked
def _process_coming(plugin, url: str, rank: dict) -> None:
    """旧RSS入口只构建延迟识别候选，筛选/观察/写入与快照共用。"""
    items = _fetch_coming_rss(plugin, url)
    if not items:
        return
    def resolve(item):
        meta = _snapshot_meta(item, {}, MediaType.TV)
        return meta, plugin.chain.recognize_media(meta=meta, mtype=MediaType.TV), "tv"
    candidates = [RankCandidate(raw=item, resolver=lambda item=item: resolve(item)) for item in items]
    _process_coming_snapshots(plugin, candidates, rank)


@lifecycle.rank_locked
def _process_general(plugin, url: str, rank: dict) -> None:
    """旧RSS入口保留标题识别方式，复用完整候选处理与副作用边界。"""
    items = _fetch_rss(plugin, url)
    if not items:
        return
    candidates = [RankCandidate(raw=item, resolver=lambda item=item: _recognize_rss_item(plugin, item, rank)) for item in items]
    _process_general_snapshots(plugin, candidates, rank)


def _process_items(self, items: list[dict], source: str) -> None:
    history: list[dict] = storage.read_rank_history(self, source)
    history_index = _history_index_by_unique(history)
    for item in items:
        title, link, mtype, year = item.get("title", ""), item.get("link", ""), item.get("mtype", ""), item.get("year")
        if not title:
            continue
        unique = f"dc2_rank:{link or title}"
        if _history_item_subscribed(history_index.get(unique)) or _history_item_existing(history_index.get(unique)):
            continue
        if _check_blacklist(self, title, description=_blacklist_description(item), link=link):
            continue
        meta, mediainfo, mtype = _recognize_rss_item(self, item, {"key": source})
        if not mediainfo:
            continue
        existing_state = _is_existing_media(mediainfo, meta)
        if existing_state is None:
            logger.warning(f"豆瓣中心：条目《{getattr(mediainfo, 'title', '')}》订阅状态未知，保留记录待下轮重试")
            continue
        if existing_state:
            logger.info(f"豆瓣中心：条目《{mediainfo.title or title}》已存在订阅，跳过观察与订阅")
            _record_existing_history(
                history,
                unique,
                title=title,
                year=year,
                link=link,
                mediainfo=mediainfo,
                rank_key=source,
                rank_name=source,
                media_type=mtype,
                season=meta.begin_season,
            )
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
            _record_history_item(history, {
                "title": cn_title,
                "link": link,
                "tmdbid": mediainfo.tmdb_id,
                "poster": mediainfo.get_poster_image(),
                "time": subscribed_at,
                "unique": unique,
                "subscribed": True,
                "subscribed_at": subscribed_at,
                "rank_key": source,
                "rank_name": source,
                "media_type": mtype,
                "season": meta.begin_season,
            })
            history_index[unique] = {"subscribed": True, "subscribed_at": subscribed_at}
    storage.save_rank_history(self, source, history)
