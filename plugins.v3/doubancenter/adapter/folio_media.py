"""按实际播放季和剧集组核验豆瓣条目的只读媒体适配器。"""

from __future__ import annotations

import datetime
import re
import unicodedata
from collections.abc import Mapping

from app.schemas.types import MediaSource, MediaType
from app.sdk.logging import logger
from app.sdk.media import MetaInfo

from ..model.identity import identity_from_media
from ..utils import resolve_media_season


class FolioLookupError(RuntimeError):
    """媒体来源调用失败，允许业务层保留待核验状态。"""


def _query(callback, **kwargs):
    """将不同来源的查询异常归一，和本模块自身的逻辑错误区分。"""
    try:
        return callback(**kwargs)
    except Exception as err:
        raise FolioLookupError(type(err).__name__) from err


def value(item, key, default=None):
    """兼容宿主媒体对象与原始详情字典。"""
    return item.get(key, default) if isinstance(item, Mapping) else getattr(item, key, default)


def _date(text):
    """提取来源日期中的首个完整年月日。"""
    match = re.search(r"(?:19|20)\d{2}-\d{2}-\d{2}", str(text or ""))
    try:
        return datetime.date.fromisoformat(match.group()) if match else None
    except ValueError:
        return None


def _number(number):
    """读取可选整数，缺失或非法时保持未知。"""
    try:
        return int(number) if number is not None else None
    except (TypeError, ValueError):
        return None


def _names(media):
    """收集正式标题和来源别名，保持搜索顺序。"""
    names = [value(media, key) for key in ("title", "name", "original_title", "original_name",
                                          "cn_name", "en_name", "hk_title", "tw_title")]
    names.extend(value(media, "names", []) or [])
    names.extend(value(media, "aka", []) or [])
    raw = value(media, "tmdb_info", {}) or {}
    names.extend(raw.get(key) for key in ("name", "title", "original_name", "original_title"))
    return list(dict.fromkeys(str(name).strip() for name in names if name))


def _title_key(name):
    """仅去掉明确的季或分段标记，禁止模糊子串匹配。"""
    text = unicodedata.normalize("NFKC", str(name or "")).casefold()
    text = re.sub(r"第\s*[0-9一二三四五六七八九十]+\s*(?:季|部(?:分)?|期)", "", text)
    text = re.sub(r"\b(?:seasons?|part|cour)[.\s]*[0-9ivx]+\b", "", text)
    text = re.sub(r"(?:\s+|(?<=[\u3400-\u9fff]))(?:iii|ii)(?=[\s:～~]|$)", "", text)
    return "".join(char for char in text if char.isalnum())


def _search_names(media):
    """长副标题可能无法检索，补主标题搜索但仍完整核验返回身份。"""
    result = []
    for name in _names(media)[:2]:
        short = re.split(r"[：:～~]", name, maxsplit=1)[0].strip()
        for candidate in (name, short if len(short) >= 2 else ""):
            if candidate and candidate not in result:
                result.append(candidate)
    return result[:3]


def _poster(path, fallback=""):
    """将 TMDB 相对图片路径补全，沿用宿主的图片域名。"""
    if not path:
        return ""
    if str(path).startswith(("https://", "http://")):
        return str(path)
    if not str(path).startswith("/"):
        return ""
    base = str(fallback).split("/t/p/", 1)[0] if "/t/p/" in str(fallback) else "https://image.tmdb.org"
    return base + "/t/p/original" + str(path)


def subject_poster(subject) -> str:
    """优先读取豆瓣详情的条目海报，不用整剧图片替代分段封面。"""
    picture = value(subject, "pic") or {}
    for poster in (value(picture, "large"), value(picture, "normal"),
                   value(subject, "poster_path"), value(subject, "cover_url")):
        if isinstance(poster, str) and poster.startswith(("https://", "http://")):
            return poster
    return ""


def load_subject_poster(chain, subject_id: str) -> str:
    """只按已经确认的豆瓣 ID 取图，拒绝缺失、错条目或错误类型的详情。"""
    subject = _query(chain.douban_info, doubanid=str(subject_id), mtype=MediaType.TV)
    actual_id = str(value(subject, "id") or value(subject, "media_id") or "")
    if actual_id != str(subject_id) or _tv_status(subject) is not True:
        raise FolioLookupError("豆瓣海报详情与已核验条目不一致")
    poster = subject_poster(subject)
    if not poster:
        raise FolioLookupError("已核验豆瓣条目暂无海报，保留原图")
    return poster


def _library_facts(media, origin: dict) -> dict:
    """只使用实际入库集表解释库内季，识别器附带的 Cours 不具有优先权。"""
    library = origin["library_season"]
    first_date = _date(library.get("air_date"))
    count = _number(library.get("episode_count"))
    if not first_date or not count or not origin.get("mediaserver", {}).get("season_id"):
        return {"resolved": False, "reason": "缺少可核验的媒体库季集信息"}
    raw = value(media, "tmdb_info", {}) or {}
    number = _number(origin.get("season"))
    regular = next((item for item in raw.get("seasons", [])
                    if _number(item.get("season_number")) == number), {})
    poster = _poster(regular.get("poster_path"), value(media, "poster_path", ""))
    dates = [date.isoformat() for item in library.get("episodes", []) if (date := _date(item.get("air_date")))]
    return {
        "resolved": True, "reason": "", "basis": "mediaserver", "season": number,
        "native_season": number, "episode_group": "", "episode_count": count,
        "air_date": first_date.isoformat(), "year": str(first_date.year),
        "library_years": sorted({date[:4] for date in dates}), "library_episode_dates": dates,
        "poster_path": poster, "season_poster": bool(regular.get("poster_path")),
        "series_episode_count": _number(raw.get("number_of_episodes") or value(media, "number_of_episodes")),
        "series_air_date": str(raw.get("first_air_date") or value(media, "release_date") or ""),
        "series_year": str(value(media, "year", "") or "")[:4],
    }


def season_facts(media, origin: dict) -> dict:
    """从宿主已识别媒体取实际季首播日，保留剧集组与原始季的区别。"""
    if isinstance(origin.get("library_season"), dict):
        return _library_facts(media, origin)
    season = _number(origin.get("season"))
    group_id = str(origin.get("episode_group") or value(media, "episode_group") or "")
    raw = value(media, "tmdb_info", {}) or {}
    regular = raw.get("seasons") or []
    details = value(media, "season_info", []) or regular
    first_date = None
    episode_count = None
    native_season = season
    group = None
    if group_id:
        groups = value(media, "episode_groups", []) or details
        group = next((item for item in groups if _number(item.get("order")) == season
                      and item.get("episodes")), None)
        if group is None:
            return {"resolved": False, "reason": "缺少实际剧集组的季集映射"}
        episodes = group["episodes"]
        episode_count = len(episodes)
        dates = [date for item in episodes if (date := _date(item.get("air_date")))]
        first_date = min(dates) if dates else None
        native = {_number(item.get("original_season_number", item.get("season_number")))
                  for item in episodes}
        native.discard(None)
        # 剧集组可能把第 0 集特别篇放在正片开头；海报仍跟随唯一正片季。
        if len(native) > 1:
            native.discard(0)
        native_season = next(iter(native)) if len(native) == 1 else None
    else:
        season_detail = next((item for item in details
                              if _number(item.get("season_number")) == season), {})
        first_date = _date(season_detail.get("air_date"))
        episode_count = _number(season_detail.get("episode_count"))
    years = value(media, "season_years", {}) or {}
    year = str(first_date.year) if first_date else str(years.get(season, years.get(str(season), "")) or "")
    if season == 1 and not year:
        year = str(value(media, "year", "") or "")
    regular_season = next((item for item in regular
                           if _number(item.get("season_number")) == native_season), {})
    season_poster = _poster(regular_season.get("poster_path"), value(media, "poster_path", ""))
    if not season_poster and not group_id:
        season_poster = _poster(next((item.get("poster_path") for item in details
                                     if _number(item.get("season_number")) == season), ""))
    return {
        "resolved": bool(year),
        "reason": "" if year else "缺少目标季首播年份",
        "season": season,
        "episode_count": episode_count,
        "native_season": native_season,
        "episode_group": group_id,
        "air_date": first_date.isoformat() if first_date else "",
        "year": year,
        "poster_path": season_poster or value(media, "poster_path", "") or "",
        "season_poster": bool(season_poster),
        "series_episode_count": _number(raw.get("number_of_episodes") or value(media, "number_of_episodes")),
        "series_air_date": str(raw.get("first_air_date") or value(media, "first_air_date")
                               or value(media, "release_date") or ""),
        "series_year": str(value(media, "year", "") or "")[:4],
    }


def _candidate_dates(candidate):
    """保留全部地区首播日，避免仅使用首个中国大陆上映日。"""
    dates = []
    for key in ("release_date", "first_air_date", "pubdate", "pubdates"):
        entries = value(candidate, key) or []
        for entry in entries if isinstance(entries, (list, tuple)) else [entries]:
            if date := _date(entry):
                dates.append(date)
    return dates


def _same_title(media, candidate):
    """校验规范化后的完整标题或正式别名。"""
    left = {_title_key(name) for name in _names(media)}
    right = {_title_key(name) for name in _names(candidate)}
    return bool((left & right) - {""})


def _same_series(chain, media, candidate):
    """标题的繁简或译名不一致时，用反向媒体身份确认，禁止模糊包含。"""
    if _same_title(media, candidate):
        return True
    source, source_id = identity_from_media(media)
    candidate_id = str(value(candidate, "id") or value(candidate, "media_id") or "")
    if source != MediaSource.TMDB or not candidate_id:
        return False
    try:
        matched = _query(chain.convert_media_identity,
            target_source=MediaSource.TMDB, media_source=MediaSource.Douban,
            media_id=candidate_id, mtype=MediaType.TV,
        )
    except FolioLookupError:
        logger.debug("分季候选反向身份查询失败", exc_info=True)
        return False
    return str(value(matched, "id") or value(matched, "media_id") or "") == str(source_id)


def _tv_status(candidate):
    """区分明确电视剧、明确电影和缺字段的跨源摘要。"""
    actual = value(candidate, "is_tv")
    if isinstance(actual, bool):
        return actual
    actual = value(candidate, "type") or value(candidate, "media_type")
    actual = str(getattr(actual, "value", actual) or "").lower()
    if actual in {"tv", "series", "电视剧", "剧集"}:
        return True
    return False if actual in {"movie", "mov", "电影"} else None


def _season_match_basis(candidate, facts):
    """优先首播日期；地区日期不同时同时核验年份、部号和本季集数。"""
    expected_date = _date(facts["air_date"])
    dates = _candidate_dates(candidate)
    if expected_date and dates and min(abs((date - expected_date).days) for date in dates) <= 7:
        return "premiere_date"
    # 豆瓣可能把前一周的序章计入首播；库内未收序章时仍以完整入库季为一条。
    if (facts.get("basis") == "mediaserver" and expected_date
            and any(0 <= (expected_date - date).days <= 14 for date in dates)):
        return "library_premiere_with_prologue"
    candidate_year = str(value(candidate, "year", "") or "")[:4]
    if not candidate_year or candidate_year != facts["year"]:
        return ""
    # 只有年份不足以区分同年分割放送的剧集组。
    if facts["episode_group"]:
        return ""
    count = _number(value(candidate, "episodes_count"))
    if not count or count != facts["episode_count"]:
        return ""
    title = str(value(candidate, "title") or value(candidate, "name") or "")
    title = re.sub(r"第\s*([0-9一二三四五六七八九十百]+)\s*部", r"第\1季", title)
    declared = resolve_media_season(MetaInfo(title), titles=(title,))
    if declared is None:
        declared = 1
    return "season_year_episode_count" if declared == facts["native_season"] else ""


def _covers_series(candidate, facts):
    """整剧回退同时要求集数覆盖和整剧首播日期一致。"""
    count = _number(value(candidate, "episodes_count"))
    total = facts["series_episode_count"]
    if not count or not total or total <= 0 or count < total:
        return False
    first_date = _date(facts["series_air_date"])
    dates = _candidate_dates(candidate)
    if first_date and dates:
        return any(abs((date - first_date).days) <= 7 for date in dates)
    return bool(facts["series_year"] and str(value(candidate, "year") or "")[:4] == facts["series_year"])


def load_playback_media(chain, origin: dict, title: str = ""):
    """按源身份和明确剧集组加载完整媒体，供重试与历史修复复用。"""
    meta = MetaInfo(title)
    meta.type = MediaType.TV
    meta.begin_season = origin.get("season")
    kwargs = {
        "meta": meta, "media_source": origin["media_source"],
        "media_id": str(origin["media_id"]), "mtype": MediaType.TV, "cache": True,
    }
    if origin.get("episode_group"):
        kwargs["episode_group"] = origin["episode_group"]
    media = _query(chain.recognize_media, **kwargs)
    source, media_id = identity_from_media(media)
    if (str(getattr(source, "value", source) or "") != origin["media_source"]
            or str(media_id or "") != str(origin["media_id"])):
        return None
    return media


def resolve_tv_subject(chain, media, origin: dict) -> dict:
    """核验分季候选；整剧 IMDb 结果也必须通过日期或整剧覆盖范围校验。"""
    facts = season_facts(media, origin)
    if not facts["resolved"]:
        return {"resolved": False, "reason": facts["reason"], "facts": facts}
    source, source_id = identity_from_media(media)
    if not source or not source_id:
        return {"resolved": False, "reason": "缺少源媒体身份", "facts": facts}
    candidates = {}
    if source == MediaSource.Douban:
        candidates[str(source_id)] = value(media, "douban_info", {}) or media
    else:
        try:
            converted = _query(chain.convert_media_identity,
                target_source=MediaSource.Douban, media_source=source,
                media_id=str(source_id), mtype=MediaType.TV, season=facts["native_season"],
            )
        except FolioLookupError:
            logger.debug("分季候选跨源转换失败，继续核验搜索结果", exc_info=True)
            converted = None
        candidate_id = value(converted, "id") or value(converted, "media_id")
        if candidate_id:
            candidates[str(candidate_id)] = converted
    names = _names(media)
    # 搜索结果不直接采信，随后按源身份、季首播日和类型共同核验。
    if source != MediaSource.Douban or facts.get("basis") == "mediaserver":
        for year in facts.get("library_years") or [facts["year"]]:
            for name in _search_names(media):
                meta = MetaInfo(name)
                meta.type = MediaType.TV
                meta.year = year
                for candidate in (_query(chain.search_medias, meta=meta, media_source=MediaSource.Douban) or [])[:20]:
                    candidate_source, candidate_id = identity_from_media(candidate)
                    if candidate_source == MediaSource.Douban and candidate_id:
                        candidates[str(candidate_id)] = candidate
    exact, whole, checks, related = [], [], [], []
    for candidate_id, summary in candidates.items():
        check = {"id": candidate_id, "summary_title": value(summary, "title") or "",
                 "summary_type": str(value(summary, "type") or ""), "stage": "summary_type"}
        checks.append(check)
        if _tv_status(summary) is False:
            continue
        check["stage"] = "summary_year"
        summary_year = str(value(summary, "year", "") or "")[:4]
        if summary_year and summary_year != facts["year"] and not _same_title(media, summary):
            continue
        detail = _query(chain.douban_info, doubanid=candidate_id, mtype=MediaType.TV)
        check.update(stage="detail_type", title=value(detail, "title") or "",
                     detail_type=str(value(detail, "type") or ""), is_tv=value(detail, "is_tv"),
                     dates=[date.isoformat() for date in _candidate_dates(detail)],
                     episodes_count=_number(value(detail, "episodes_count")))
        if not detail or _tv_status(detail) is not True:
            continue
        if isinstance(detail, Mapping):
            detail = {**detail, "id": candidate_id}
        check["stage"] = "series_identity"
        if not _same_series(chain, media, detail):
            continue
        check["stage"] = "season_date"
        item = {
            "resolved": True, "subject_id": candidate_id,
            "subject_name": value(detail, "title") or value(detail, "name") or (names[0] if names else ""),
            "poster_path": subject_poster(detail) or facts["poster_path"], "facts": facts,
        }
        if facts.get("basis") == "mediaserver":
            dates = [_date(date) for date in facts["library_episode_dates"]]
            for date in _candidate_dates(detail):
                if dates and -14 <= (date - min(dates)).days and (date - max(dates)).days <= 7:
                    related.append({"subject_id": candidate_id, "subject_name": item["subject_name"],
                                    "air_date": date.isoformat()})
                    break
        if _covers_series(detail, facts):
            check["stage"] = "series_match"
            whole.append({**item, "identity_scope": "series"})
        elif basis := _season_match_basis(detail, facts):
            check["stage"] = "season_match"
            check["match_basis"] = basis
            exact.append({**item, "identity_scope": "season"})
    matches = exact or whole
    if len(matches) == 1:
        result = {**matches[0], "checks": checks}
        if facts.get("basis") == "mediaserver":
            result.update(identity_scope="library_season", related_subjects=sorted(
                related, key=lambda item: (item["air_date"], item["subject_id"]),
            ))
        return result
    return {
        "resolved": False,
        "reason": "分季豆瓣候选不唯一" if matches else "未找到通过季首播日校验的豆瓣条目",
        "facts": facts,
        "checks": checks,
    }
