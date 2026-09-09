"""
DoubanCenter - 榜单订阅引擎
"""
import datetime
import re
from typing import Any, Dict, List, Optional

from app.chain.media import MediaChain
from app.chain.subscribe import SubscribeChain
from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.media import MetaInfo
from app.sdk.network import RequestUtils
from app.sdk.utilities import DomUtils
from app.schemas.types import MediaSource, MediaType

from .. import utils
from ..adapter import bangumi as bangumi_adapter
from ..adapter import douban as douban_adapter
from ..adapter import rss as rss_adapter
from ..model import rank as rank_model
from ..model.identity import (
    convert_identity,
    identity_payload,
    legacy_identity,
    recognize_media as recognize_with_identity,
)
from . import observation as observation_service
from . import bangumi_tmdb as bangumi_tmdb_service
from . import rank_recognition as rank_recognition_service
from . import rank_refresh as rank_refresh_service
from . import rank_snapshot as rank_snapshot_service
from . import rank_subscription as rank_subscription_service
from . import subscription as subscription_service
from ..storage import records as storage

RANK_HISTORY_LIMIT = 500
UNLIMITED_RANK_FETCH_LIMIT = 50
DEFAULT_OBSERVE_RANK_KEYS = rank_model.DEFAULT_OBSERVE_RANK_KEYS
BUILTIN_RANKS: List[Dict[str, Any]] = rank_model.BUILTIN_RANKS


def get_rank_definitions(plugin) -> List[Dict[str, Any]]:
    """返回当前插件配置下的有效榜单集合。"""
    return rank_model.effective_ranks(getattr(plugin, "_custom_ranks", []))


def _trim_history(history: List[dict], limit: int = RANK_HISTORY_LIMIT) -> List[dict]:
    """裁剪榜单历史，只保留最新条目。"""
    return storage.trim_records(history, limit)


def _custom_rank_history_key(source: str) -> str:
    """为自定义 RSS 生成跨进程稳定的历史数据键。"""
    return storage.custom_rank_history_key(source)


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


def _recognize_rss_item(self, item: dict, rank: dict):
    """按条目和榜单路由识别 RSS 媒体，未知类型交给识别链自动判断。"""
    return rank_recognition_service.recognize_rss_item(
        self,
        item,
        rank,
        infer_media_type=_rank_media_type,
        resolved_media_type=_resolved_media_type_name,
        extract_bangumi_id=_extract_bangumi_id,
        fetch_bangumi_subject=_fetch_bangumi_subject,
        bangumi_subject_title=_bangumi_subject_title,
        bangumi_subject_year=_bangumi_subject_year,
    )


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


def _record_existing_history(
    history: List[dict],
    unique: str,
    title: str = "",
    year: Any = "",
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
    values: List[str] = []
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


def _normalize_region_values(value: Any) -> List[str]:
    """统一地区字段并兼容最小测试宿主。"""
    normalizer = getattr(utils, "normalize_region_values", None)
    if callable(normalizer):
        return normalizer(value)
    if isinstance(value, str):
        return [part for part in re.split(r"[\s、,，/|；;]+", value) if part]
    if isinstance(value, (list, tuple, set)):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


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
    """读取指定榜单的订阅配置。"""
    return rank_subscription_service.rank_config(self._rank_configs, key)


def _ren(self, key: str) -> bool:
    """判断指定榜单是否启用自动订阅。"""
    return rank_subscription_service.rank_enabled(self._rank_configs, key)


def _rcount(self, key: str) -> int:
    """读取指定榜单的自动订阅候选数量。"""
    return rank_subscription_service.rank_count(self._rank_configs, key)


def _drop_stale_observations(history: List[dict], current_candidates: set) -> None:
    """将已跌出当前候选窗口的观察条目标记为结束。"""
    observation_service.drop_stale_observations(history, current_candidates)


def _positive_number(value: Any) -> bool:
    """判断值是否能解析为正数。"""
    return rank_model.positive_number(value)


def _year_below_min(value: Any, min_year: int) -> bool:
    """判断年份是否低于最低年份筛选条件。"""
    return rank_model.year_below_min(value, min_year)


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
    entry["year"] = recognition.get("year") or getattr(mediainfo, "year", None) or entry.get("year") or ""
    entry["tmdbid"] = getattr(mediainfo, "tmdb_id", None) or tmdbid or entry.get("tmdbid")
    entry["tmdb_id"] = entry["tmdbid"]
    entry["bangumi_id"] = getattr(mediainfo, "bangumi_id", None) or bangumiid or entry.get("bangumi_id")
    entry["bangumiid"] = entry["bangumi_id"]
    entry.update(identity_payload(mediainfo, bangumi_id=bangumiid, tmdb_id=entry["tmdbid"]))
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
    entry["year"] = getattr(mediainfo, "year", None) or entry.get("year") or ""
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


def _bangumi_history_repair_candidates(history: List[dict]) -> List[dict]:
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


def normalize_bangumi_history(self, history: List[dict], max_repairs: int = 10) -> List[dict]:
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


def _has_global_subscription_filter(self) -> bool:
    """判断是否配置了全局自动订阅安全条件。"""
    return rank_subscription_service.has_global_filter(
        blacklist_keywords=self._blacklist_keywords,
        observe_enabled=_rank_observe_enabled(self),
    )


def _has_rank_subscription_filter(self, rd: dict) -> bool:
    """判断单个榜单是否配置了自动订阅安全条件。"""
    return rank_subscription_service.has_rank_filter(_rc(self, rd["key"]), rd)


def _has_subscription_safety_filter(self) -> bool:
    """判断当前配置是否足以安全执行自动订阅。"""
    return rank_subscription_service.has_safety_filter(
        self._rank_configs,
        get_rank_definitions(self),
        blacklist_keywords=self._blacklist_keywords,
        observe_enabled=_rank_observe_enabled(self),
    )


def subscribe_to_ranks(self, refresh_when_unsafe: bool = True) -> None:
    """按当前配置执行榜单订阅，必要时只刷新榜单历史。"""
    rank_subscription_service.subscribe_ranks(
        self,
        ranks=get_rank_definitions(self),
        safety_filter=_has_subscription_safety_filter,
        rank_enabled_callback=_ren,
        rank_count_callback=_rcount,
        process_coming=_process_coming,
        process_general=_process_general,
        refresh_rank_data=refresh_rank_data,
        unlimited_limit=UNLIMITED_RANK_FETCH_LIMIT,
        refresh_when_unsafe=refresh_when_unsafe,
    )


def _subscription_limit_by_rank(self) -> Dict[str, int]:
    """生成运行周期每个启用榜单需要拉取的候选数量。"""
    return rank_subscription_service.subscription_limits(
        self._rank_configs,
        get_rank_definitions(self),
        UNLIMITED_RANK_FETCH_LIMIT,
    )


def _blacklist_enabled(self) -> bool:
    """判断当前是否启用了黑名单筛选。"""
    return bool((getattr(self, "_blacklist_keywords", "") or "").strip())


def _emit_rank_subscription_summary(rd: dict, description: str, result_lines: List[str]) -> None:
    """输出单个榜单的订阅筛选摘要。"""
    rank_name = (rd or {}).get("name") or (rd or {}).get("key") or "榜单"
    lines = [
        f"豆瓣中心：[{rank_name}] 订阅筛选完成",
        f"筛选条件：{description}",
        "处理结果：",
    ]
    lines.extend(result_lines or ["- 无订阅动作"])
    logger.info("\n".join(lines))


def _log_rank_skip(rd: dict, title: str, reason: str, result_lines: Optional[List[str]] = None) -> None:
    """输出榜单条目跳过原因。"""
    rank_name = (rd or {}).get("name") or (rd or {}).get("key") or "榜单"
    message = f"跳过《{title or '未命名条目'}》：{reason}"
    if result_lines is not None:
        result_lines.append(f"- {message}")
        return
    logger.info(f"豆瓣中心：[{rank_name}] {message}")


def _check_rank_region(self, rd: dict, item: dict, entry: dict = None, mediainfo=None, result_lines: Optional[List[str]] = None) -> bool:
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


def subscribe_to_rank_snapshots(self, rank_snapshots: Dict[str, dict]) -> None:
    """使用本轮已识别榜单快照执行自动订阅。"""
    rank_subscription_service.subscribe_rank_snapshots(
        self,
        rank_snapshots,
        ranks=get_rank_definitions(self),
        safety_filter=_has_subscription_safety_filter,
        rank_enabled_callback=_ren,
        rank_count_callback=_rcount,
        rank_config_callback=_rc,
        blacklist_enabled=_blacklist_enabled,
        observe_enabled=_rank_observe_enabled,
        process_coming=_process_coming_snapshots,
        process_general=_process_general_snapshots,
        emit_summary=_emit_rank_subscription_summary,
    )


def _process_coming_snapshots(self, snapshots: List[dict], rd: dict, result_lines: Optional[List[str]] = None) -> None:
    """处理即将上映榜单的已识别订阅候选。"""
    cfg = _rc(self, rd["key"])
    min_wish = int(cfg.get("wish_count", 0) or 0)
    air_days = int(cfg.get("air_days", 0) or 0)
    min_vote = float(cfg.get("vote", 0) or 0)
    history: List[dict] = storage.read_rank_history(self, rd["key"])
    history_index = _history_index_by_unique(history)
    current_candidates = set()
    for snapshot in snapshots or []:
        if not isinstance(snapshot, dict):
            continue
        item = snapshot.get("raw") if isinstance(snapshot.get("raw"), dict) else {}
        entry = snapshot.get("entry") if isinstance(snapshot.get("entry"), dict) else {}
        title = str(entry.get("title") or item.get("title") or "")
        link = entry.get("link") or item.get("link") or ""
        year = entry.get("year") or item.get("year") or ""
        wish = int(entry.get("wish_count") or item.get("wish_count") or 0)
        unique = entry.get("unique") or f"dc2_coming:{link or item.get('title') or title}"
        if not title:
            continue
        current_candidates.add(unique)
        if _history_item_subscribed(history_index.get(unique)) or _history_item_existing(history_index.get(unique)):
            _log_rank_skip(rd, title, "历史中已订阅或已存在", result_lines=result_lines)
            continue
        blacklist_description = _blacklist_description(entry, item)
        if _check_blacklist(self, title, description=blacklist_description, link=link):
            _log_rank_skip(rd, title, "命中黑名单", result_lines=result_lines)
            continue
        if min_wish > 0 and wish < min_wish:
            _log_rank_skip(rd, title, f"想看 {wish} < {min_wish}", result_lines=result_lines)
            continue
        mediainfo = snapshot.get("mediainfo")
        if not mediainfo:
            _log_rank_skip(rd, title, "TMDB 识别无结果", result_lines=result_lines)
            continue
        if not _check_rank_region(self, rd, item, entry, mediainfo, result_lines=result_lines):
            continue
        vote_average = getattr(mediainfo, "vote_average", None)
        if min_vote > 0 and vote_average and vote_average < min_vote:
            _log_rank_skip(rd, title, f"评分 {vote_average} < {min_vote}", result_lines=result_lines)
            continue
        meta = _snapshot_meta(item, entry, MediaType.TV)
        if _is_existing_media(mediainfo, meta):
            _log_rank_skip(rd, getattr(mediainfo, "title", "") or title, "已存在订阅，跳过观察与订阅", result_lines=result_lines)
            _record_existing_history(
                history,
                unique,
                title=title,
                year=year,
                link=link,
                mediainfo=mediainfo,
                rank_key=rd["key"],
                rank_name=rd["name"],
                media_type="tv",
                season=meta.begin_season,
            )
            _cleanup_observe_logs(self, title=title, unique=unique)
            _cleanup_observe_logs(self, title=getattr(mediainfo, "title", ""), unique=unique)
            history_index[unique] = {"existing": True, "existing_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "existing_reason": "subscribe"}
            continue
        ad = utils.get_tmdb_air_date(self.chain, mediainfo.tmdb_id, season=meta.begin_season)
        if air_days > 0:
            if not ad:
                _log_rank_skip(rd, title, "未获取到上映日期", result_lines=result_lines)
                continue
            if not utils.is_within_days(ad, air_days):
                _log_rank_skip(rd, title, f"上映日期 {ad} 不在未来 {air_days} 天内", result_lines=result_lines)
                continue
        if _check_observe(self, unique, history, title=title, rank_key=rd["key"]):
            _log_rank_skip(rd, title, "观察期规则拦截", result_lines=result_lines)
            continue
        if _add_sub(self, mediainfo, meta, rank_key=rd["key"], rank_name=rd["name"], source_link=link):
            cn_title = mediainfo.title or title
            subscribed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _record_history_item(history, {
                "title": cn_title,
                "year": year,
                "wish_count": wish,
                "air_date": ad,
                "link": link,
                "tmdbid": mediainfo.tmdb_id,
                "poster": _snapshot_poster(mediainfo, entry),
                "time": subscribed_at,
                "unique": unique,
                "subscribed": True,
                "subscribed_at": subscribed_at,
                "rank_key": rd["key"],
                "rank_name": rd["name"],
                "media_type": "tv",
                "season": meta.begin_season,
            })
            history_index[unique] = {"subscribed": True, "subscribed_at": subscribed_at}
            if result_lines is not None:
                result_lines.append(f"- 已订阅《{cn_title}》")
            else:
                logger.info(f"豆瓣中心：[{rd['name']}] 已订阅《{cn_title}》")
    _drop_stale_observations(history, current_candidates)
    storage.save_rank_history(self, rd["key"], history)


def _process_general_snapshots(self, snapshots: List[dict], rd: dict, result_lines: Optional[List[str]] = None) -> None:
    """处理普通榜单的已识别订阅候选。"""
    cfg = _rc(self, rd["key"])
    min_vote = float(cfg.get("vote", 0) or 0)
    min_year = int(cfg.get("year", 0) or 0)
    air_days = int(cfg.get("air_days", 0) or 0)
    date_mode = rank_model.rank_date_mode(rd)
    history: List[dict] = storage.read_rank_history(self, rd["key"])
    history_index = _history_index_by_unique(history)
    current_candidates = set()
    for snapshot in snapshots or []:
        if not isinstance(snapshot, dict):
            continue
        item = snapshot.get("raw") if isinstance(snapshot.get("raw"), dict) else {}
        entry = snapshot.get("entry") if isinstance(snapshot.get("entry"), dict) else {}
        title = str(entry.get("title") or item.get("title") or "")
        link = entry.get("link") or item.get("link") or ""
        year = entry.get("year") or item.get("year")
        mtype = str(entry.get("media_type") or _rank_media_type(rd, item))
        unique = entry.get("unique") or f"dc2_rank:{link or item.get('title') or title}"
        if not title:
            continue
        current_candidates.add(unique)
        if _history_item_subscribed(history_index.get(unique)) or _history_item_existing(history_index.get(unique)):
            _log_rank_skip(rd, title, "历史中已订阅或已存在", result_lines=result_lines)
            continue
        blacklist_description = _blacklist_description(entry, item)
        if _check_blacklist(self, title, description=blacklist_description, link=link):
            _log_rank_skip(rd, title, "命中黑名单", result_lines=result_lines)
            continue
        if _year_below_min(year, min_year):
            _log_rank_skip(rd, title, f"年份 {year} < {min_year}", result_lines=result_lines)
            continue
        mediainfo = snapshot.get("mediainfo")
        if not mediainfo:
            _log_rank_skip(rd, title, "TMDB 识别无结果", result_lines=result_lines)
            continue
        if not _check_rank_region(self, rd, item, entry, mediainfo, result_lines=result_lines):
            continue
        vote_average = getattr(mediainfo, "vote_average", None)
        if min_vote > 0 and vote_average and vote_average < min_vote:
            _log_rank_skip(rd, title, f"评分 {vote_average} < {min_vote}", result_lines=result_lines)
            continue
        if _year_below_min(getattr(mediainfo, "year", None), min_year):
            _log_rank_skip(rd, title, f"识别年份 {getattr(mediainfo, 'year', '')} < {min_year}", result_lines=result_lines)
            continue
        media_type = _snapshot_media_type(rd, item, entry, mediainfo)
        mtype = _resolved_media_type_name(rd, item, mediainfo)
        meta = _snapshot_meta(item, entry, media_type)
        if _is_existing_media(mediainfo, meta):
            _log_rank_skip(rd, getattr(mediainfo, "title", "") or title, "已存在订阅，跳过观察与订阅", result_lines=result_lines)
            _record_existing_history(
                history,
                unique,
                title=title,
                year=year,
                link=link,
                mediainfo=mediainfo,
                rank_key=rd["key"],
                rank_name=rd["name"],
                media_type=mtype,
                season=meta.begin_season,
                prefer_title=rd["key"] == "bangumi",
            )
            _cleanup_observe_logs(self, title=title, unique=unique)
            _cleanup_observe_logs(self, title=getattr(mediainfo, "title", ""), unique=unique)
            history_index[unique] = {"existing": True, "existing_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "existing_reason": "subscribe"}
            continue
        air_date = None
        if air_days > 0:
            air_date = utils.get_media_release_date(mediainfo, season=meta.begin_season)
            if not air_date:
                _log_rank_skip(rd, title, "未获取到上映日期", result_lines=result_lines)
                continue
            within_window = (
                utils.is_within_days(air_date, air_days)
                if date_mode == rank_model.DATE_MODE_FUTURE
                else utils.is_within_recent_days(air_date, air_days)
            )
            if not within_window:
                window_label = "未来" if date_mode == rank_model.DATE_MODE_FUTURE else "最近"
                _log_rank_skip(rd, title, f"上映日期 {air_date} 不在{window_label} {air_days} 天内", result_lines=result_lines)
                continue
        if _check_observe(self, unique, history, title=title, rank_key=rd["key"]):
            _log_rank_skip(rd, title, "观察期规则拦截", result_lines=result_lines)
            continue
        if _add_sub(
            self,
            mediainfo,
            meta,
            rank_key=rd["key"],
            rank_name=rd["name"],
            source_link=link,
            record_title=title,
        ):
            cn_title = mediainfo.title or title
            stored_title = title if rd["key"] == "bangumi" else cn_title
            subscribed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _record_history_item(history, {
                "title": stored_title,
                "year": mediainfo.year or year or "",
                "air_date": air_date,
                "link": link,
                "tmdbid": mediainfo.tmdb_id,
                "poster": _snapshot_poster(mediainfo, entry),
                "time": subscribed_at,
                "unique": unique,
                "subscribed": True,
                "subscribed_at": subscribed_at,
                "rank_key": rd["key"],
                "rank_name": rd["name"],
                "media_type": mtype,
                "season": meta.begin_season,
                "tmdb_title": entry.get("tmdb_title") or getattr(mediainfo, "title", None) or "",
            })
            history_index[unique] = {"subscribed": True, "subscribed_at": subscribed_at}
            if result_lines is not None:
                result_lines.append(f"- 已订阅《{cn_title}》")
            else:
                logger.info(f"豆瓣中心：[{rd['name']}] 已订阅《{cn_title}》")
    _drop_stale_observations(history, current_candidates)
    storage.save_rank_history(self, rd["key"], history)


def _refresh_then_subscribe(self, message: str) -> None:
    """刷新榜单展示数据后，再按当前订阅配置执行订阅。"""
    rank_subscription_service.refresh_then_subscribe(
        self,
        message,
        limit_by_rank=_subscription_limit_by_rank,
        refresh_rank_data=refresh_rank_data,
        subscribe_snapshots=subscribe_to_rank_snapshots,
    )


def run_once(self) -> None:
    """立即刷新榜单数据，并按当前订阅配置执行订阅。"""
    _refresh_then_subscribe(self, "豆瓣中心：立即运行开始，先刷新 RSS 榜单，再按配置执行订阅")


def run_scheduled(self) -> None:
    """定时刷新榜单数据，并按当前订阅配置执行订阅。"""
    _refresh_then_subscribe(self, "豆瓣中心：定时运行开始，先刷新 RSS 榜单，再按配置执行订阅")


def _process_coming(self, url: str, rd: dict) -> None:
    cfg = _rc(self, rd["key"])
    min_wish = int(cfg.get("wish_count", 0) or 0)
    air_days = int(cfg.get("air_days", 0) or 0)
    min_vote = float(cfg.get("vote", 0) or 0)
    items = _fetch_coming_rss(self, url)
    if not items:
        return
    history: List[dict] = storage.read_rank_history(self, rd["key"])
    history_index = _history_index_by_unique(history)
    current_candidates = set()
    for item in items:
        title, link, wish = item.get("title", ""), item.get("link", ""), item.get("wish_count", 0)
        year = item.get("year", "")
        if not title:
            continue
        unique = f"dc2_coming:{link or title}"
        current_candidates.add(unique)
        if _history_item_subscribed(history_index.get(unique)) or _history_item_existing(history_index.get(unique)):
            continue
        if _check_blacklist(self, title, description=_blacklist_description(item), link=link):
            continue
        if min_wish > 0 and wish < min_wish:
            continue
        meta = _snapshot_meta(item, {}, MediaType.TV)
        mediainfo = self.chain.recognize_media(meta=meta, mtype=MediaType.TV)
        if not mediainfo:
            continue
        if not _check_rank_region(self, rd, item, {}, mediainfo):
            continue
        vote_average = getattr(mediainfo, "vote_average", None)
        if min_vote > 0 and vote_average and vote_average < min_vote:
            continue
        if _is_existing_media(mediainfo, meta):
            logger.info(f"豆瓣中心：条目《{mediainfo.title or title}》已存在订阅，跳过观察与订阅")
            _record_existing_history(
                history,
                unique,
                title=title,
                year=year,
                link=link,
                mediainfo=mediainfo,
                rank_key=rd["key"],
                rank_name=rd["name"],
                media_type="tv",
                season=meta.begin_season,
            )
            _cleanup_observe_logs(self, title=title, unique=unique)
            _cleanup_observe_logs(self, title=mediainfo.title, unique=unique)
            history_index[unique] = {"existing": True, "existing_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "existing_reason": "subscribe"}
            continue
        ad = utils.get_tmdb_air_date(self.chain, mediainfo.tmdb_id, season=meta.begin_season)
        if air_days > 0:
            if not ad:
                _log_rank_skip(rd, title, "未获取到上映日期")
                continue
            if not utils.is_within_days(ad, air_days):
                _log_rank_skip(rd, title, f"上映日期 {ad} 不在未来 {air_days} 天内")
                continue
        # 观察期：仅对选中的波动榜单延迟订阅。
        if _check_observe(self, unique, history, title=title, rank_key=rd["key"]):
            continue
        if _add_sub(self, mediainfo, meta, rank_key=rd["key"], rank_name=rd["name"], source_link=link):
            # 使用 TMDB 识别后的中文名替换原始标题
            cn_title = mediainfo.title or title
            subscribed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _record_history_item(history, {
                "title": cn_title,
                "year": year,
                "wish_count": wish,
                "air_date": ad,
                "link": link,
                "tmdbid": mediainfo.tmdb_id,
                "poster": mediainfo.get_poster_image(),
                "time": subscribed_at,
                "unique": unique,
                "subscribed": True,
                "subscribed_at": subscribed_at,
                "rank_key": rd["key"],
                "rank_name": rd["name"],
                "media_type": "tv",
                "season": meta.begin_season,
            })
            history_index[unique] = {"subscribed": True, "subscribed_at": subscribed_at}
    _drop_stale_observations(history, current_candidates)
    storage.save_rank_history(self, rd["key"], history)


def _process_general(self, url: str, rd: dict) -> None:
    cfg = _rc(self, rd["key"])
    min_vote = float(cfg.get("vote", 0) or 0)
    min_year = int(cfg.get("year", 0) or 0)
    air_days = int(cfg.get("air_days", 0) or 0)
    date_mode = rank_model.rank_date_mode(rd)
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
        if _check_blacklist(self, title, description=_blacklist_description(item), link=link):
            continue
        if _year_below_min(year, min_year):
            continue
        meta, mediainfo, mtype = _recognize_rss_item(self, item, rd)
        if not mediainfo:
            continue
        if not _check_rank_region(self, rd, item, {}, mediainfo):
            continue
        if min_vote > 0 and mediainfo.vote_average and mediainfo.vote_average < min_vote:
            continue
        if _year_below_min(mediainfo.year, min_year):
            continue
        if _is_existing_media(mediainfo, meta):
            logger.info(f"豆瓣中心：条目《{mediainfo.title or title}》已存在订阅，跳过观察与订阅")
            _record_existing_history(
                history,
                unique,
                title=title,
                year=year,
                link=link,
                mediainfo=mediainfo,
                rank_key=rd["key"],
                rank_name=rd["name"],
                media_type=mtype,
                season=getattr(meta, "begin_season", None),
                prefer_title=rd["key"] == "bangumi",
            )
            _cleanup_observe_logs(self, title=title, unique=unique)
            _cleanup_observe_logs(self, title=mediainfo.title, unique=unique)
            history_index[unique] = {"existing": True, "existing_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "existing_reason": "subscribe"}
            continue
        air_date = None
        if air_days > 0:
            air_date = utils.get_media_release_date(mediainfo, season=meta.begin_season)
            if not air_date:
                _log_rank_skip(rd, title, "未获取到上映日期")
                continue
            within_window = (
                utils.is_within_days(air_date, air_days)
                if date_mode == rank_model.DATE_MODE_FUTURE
                else utils.is_within_recent_days(air_date, air_days)
            )
            if not within_window:
                window_label = "未来" if date_mode == rank_model.DATE_MODE_FUTURE else "最近"
                _log_rank_skip(rd, title, f"上映日期 {air_date} 不在{window_label} {air_days} 天内")
                continue
        # 观察期：仅对选中的波动榜单延迟订阅。
        if _check_observe(self, unique, history, title=title, rank_key=rd["key"]):
            continue
        display_title = str(item.get("display_title") or title)
        if _add_sub(
            self,
            mediainfo,
            meta,
            rank_key=rd["key"],
            rank_name=rd["name"],
            source_link=link,
            record_title=display_title,
        ):
            cn_title = mediainfo.title or title
            stored_title = display_title if rd["key"] == "bangumi" else cn_title
            subscribed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _record_history_item(history, {
                "title": stored_title,
                "year": mediainfo.year or year or "",
                "air_date": air_date,
                "media_type": mtype,
                "link": link,
                "tmdbid": mediainfo.tmdb_id,
                "poster": mediainfo.get_poster_image(),
                "time": subscribed_at,
                "unique": unique,
                "subscribed": True,
                "subscribed_at": subscribed_at,
                "rank_key": rd["key"],
                "rank_name": rd["name"],
                "season": getattr(meta, "begin_season", None),
                "tmdb_title": getattr(mediainfo, "title", None) or "",
            })
            history_index[unique] = {"subscribed": True, "subscribed_at": subscribed_at}
    _drop_stale_observations(history, current_candidates)
    storage.save_rank_history(self, rd["key"], history)


def _process_items(self, items: List[dict], source: str) -> None:
    history: List[dict] = storage.read_rank_history(self, source)
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
        if _is_existing_media(mediainfo, meta):
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


def _write_subscribe_record(self, mediainfo, rank_key: str = "", rank_name: str = "", status: str = "success", reason: str = "", source_link: str = "") -> None:
    """写入自动订阅历史记录。"""
    subscription_service.write_subscribe_record(self, mediainfo, rank_key=rank_key, rank_name=rank_name, status=status, reason=reason, source_link=source_link)


def _add_sub(
    self,
    mediainfo,
    meta=None,
    rank_key="",
    rank_name="",
    source_link: str = "",
    record_title: str = "",
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
        subscribe_chain_cls=SubscribeChain,
    )


def _fetch_coming_rss(self, addr: str) -> List[dict]:
    """通过 RSS 适配器拉取即将上映条目。"""
    return rss_adapter.fetch_coming(
        self,
        addr,
        request_utils_cls=RequestUtils,
        dom_utils=DomUtils,
        settings_obj=settings,
    )


def _fetch_rss(self, addr: str) -> List[dict]:
    """通过 RSS 适配器拉取通用榜单条目。"""
    return rss_adapter.fetch_rank(
        self,
        addr,
        request_utils_cls=RequestUtils,
        dom_utils=DomUtils,
        settings_obj=settings,
    )


def get_enabled_rank_keys(self) -> List[str]:
    """返回当前配置中启用的榜单 key。"""
    return [rd["key"] for rd in get_rank_definitions(self) if _ren(self, rd["key"])]


def get_rank_history_by_key(self, rank_key: str) -> List[dict]:
    """只读指定榜单历史，不在页面读取阶段执行媒体识别。"""
    return storage.read_rank_history(self, rank_key)


def _dashboard_rank_sort_key(item: dict) -> tuple:
    """生成仪表盘榜单排序键。"""
    return rank_refresh_service.dashboard_rank_sort_key(item)


def get_dashboard_rank_items(self, rank_key: str, limit: int = 5) -> List[dict]:
    """返回最新 RSS 批次中的仪表盘榜单条目。"""
    history = get_rank_history_by_key(self, rank_key)
    return rank_refresh_service.dashboard_rank_items(history, limit=limit)


def refresh_rank_data(self, rank_keys=None, limit_by_rank: Optional[Dict[str, int]] = None, with_snapshots: bool = False):
    """刷新 RSS 榜单数据供仪表盘展示，不触发订阅。"""
    return rank_refresh_service.refresh_rank_data(
        self,
        ranks=get_rank_definitions(self),
        rank_enabled=_ren,
        fetch_coming=_fetch_coming_rss,
        fetch_general=_fetch_rss,
        merge_items=_merge_rank_items,
        dashboard_items=get_dashboard_rank_items,
        rank_keys=rank_keys,
        limit_by_rank=limit_by_rank,
        with_snapshots=with_snapshots,
    )


def _recognize_snapshot_item(self, rank_key: str, item: dict, entry: dict, rd: dict, existing: dict):
    """按榜单类型执行快照识别。"""
    return rank_recognition_service.recognize_snapshot_item(
        self,
        rank_key,
        item,
        entry,
        rd,
        existing,
        apply_bangumi=_apply_bangumi_recognition,
        apply_display=_apply_display_recognition,
        douban_original_title_fetcher=douban_adapter.fetch_mobile_original_titles,
    )


def _merge_rank_items(self, rank_key, items, rd, return_snapshot: bool = False):
    """通过快照服务合并 RSS 榜单条目。"""
    return rank_snapshot_service.merge_rank_items(
        self,
        rank_key,
        items,
        rd,
        infer_media_type=_rank_media_type,
        recognize_item=_recognize_snapshot_item,
        preserve_existing_identity=_preserve_existing_tmdb_identity,
        return_snapshot=return_snapshot,
    )


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
            _record_history_item(history, {
                "title": cn_title,
                "year": year,
                "wish_count": item.get("wish_count", 0),
                "link": link,
                "tmdbid": mediainfo.tmdb_id,
                "poster": mediainfo.get_poster_image(),
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "unique": unique,
                "rank_key": rd["key"],
                "rank_name": rd["name"],
                "media_type": "tv",
            })
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
            if not title:
                continue
            unique = f"dc2_rank:{link or title}"
            if unique in uh:
                continue
            _, mediainfo, mtype = _recognize_rss_item(self, item, rd)
            if not mediainfo:
                continue
            cn_title = mediainfo.title or title
            _record_history_item(history, {
                "title": cn_title,
                "year": mediainfo.year or year or "",
                "link": link,
                "tmdbid": mediainfo.tmdb_id,
                "poster": mediainfo.get_poster_image(),
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "unique": unique,
                "rank_key": rd["key"],
                "rank_name": rd["name"],
                "media_type": mtype,
            })
            uh.add(unique)
            new_count += 1
        except Exception as e:
            logger.error(f"豆瓣中心：刷新 {rd['name']} 条目出错：{e}")
            continue
    storage.save_rank_history(self, rd["key"], history)
    logger.info(f"豆瓣中心：{rd['name']} 刷新完成，新增 {new_count} 条")
