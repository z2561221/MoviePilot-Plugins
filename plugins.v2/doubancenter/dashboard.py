"""
DoubanCenter - 仪表盘模块
"""
import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.chain.media import MediaChain
from app.core.metainfo import MetaInfo
from app.schemas.types import MediaType


DETAIL_SECTION_LIMIT = 5
DETAIL_OVERFLOW_REASON = "超过详情页显示上限归档"


def get_dashboard(self, key: str, **kwargs) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
    cols = {"cols": 12, "md": 12}
    attrs = {"refresh": 600, "border": True, "title": "豆瓣中心", "subtitle": "追剧观影时间线"}
    return cols, attrs, None


def get_timeline_items(self, mobile: bool = False) -> List[dict]:
    data: Dict = self.get_data('folio_data') or {}
    content = []
    last_month = None
    cur = None
    lm = (self._folio_mobile_month if mobile else self._folio_pc_month) - 1
    ln = self._folio_mobile_num if mobile else self._folio_pc_num
    sd = sorted(data.items(), key=lambda i: datetime.datetime.strptime(i[1]['timestamp'], "%Y-%m-%d %H:%M:%S"))
    for key, val in sd[::-1]:
        if not isinstance(val, dict):
            continue
        if not val.get('poster_path', ''):
            meta = MetaInfo(val.get("subject_name"))
            meta.type = MediaType("电视剧" if not val.get("type", '') else val.get("type"))
            mi = MediaChain().recognize_media(meta=meta, mtype=meta.type, cache=True)
            pp = mi.poster_path if mi else None
            if not pp:
                continue
        else:
            pp = val.get('poster_path')
        t = datetime.datetime.strptime(val['timestamp'], "%Y-%m-%d %H:%M:%S")
        if t.month != last_month or last_month is None:
            if lm < 1:
                break
            if last_month:
                _fin(cur, ln)
                content.append(cur)
                lm -= 1
            cur = {"component": "VTimelineItem", "props": {"size": "x-small"}, "content": [{"component": "VCol", 'props': {'style': 'padding: 0rem 0rem 0rem 0rem'}, 'content': [{'component': 'h1', 'props': {'style': 'padding:0rem 0rem 1rem 0rem;font-weight:bold;', 'class': 'text-base'}, 'html': f"{t.month}月 "}, {'component': 'VRow', 'props': {'style': 'padding: 0rem 0rem 0rem 0rem'}, 'content': []}]}]}
            last_month = t.month
        if not pp or 'original' not in pp:
            continue
        cur["content"][0]["content"][1]["content"].append({"component": "a", 'props': {'href': f'https://www.douban.com/doubanapp/dispatch?uri=/movie/{val.get("subject_id")}?from=mdouban&open=app', 'target': '_blank', 'style': 'padding: 0.2rem'}, "content": [{"component": "VCard", "props": {"class": "elevation-4"}, "content": [{"component": "VImg", "props": {"src": pp.replace("/original/", "/w200/"), "style": "width:44px;height:66px;" if mobile else "width:66px;height:99px;", "aspect-ratio": "2/3"}}]}]})
    if cur:
        _fin(cur, ln)
        content.append(cur)
    return content


def _fin(item, limit):
    n = len(item["content"][0]["content"][1]["content"])
    item["content"][0]["content"][0]["html"] += f"<span class='text-sm font-normal'>看过{n}部</span>"
    item["content"][0]["content"][1]["content"] = item["content"][0]["content"][1]["content"][:limit]


def api_folio_data(self):
    """获取豆瓣时间数据，优先读自己的，没有则读原版豆瓣中心的。"""
    data = self.get_data('folio_data') or {}
    if not data:
        data = self.get_data('folio_data', plugin_id='DoubanCenter') or {}
    return {"data": data}


def api_config(self):
    """返回前端运行配置补充数据。"""
    from .feed import BUILTIN_RANKS, _ren
    opts = [{"title": rd["name"], "value": rd["key"]} for rd in BUILTIN_RANKS if _ren(self, rd["key"])]
    return {"data": {
        "folio_pc_month": self._folio_pc_month,
        "folio_pc_num": self._folio_pc_num,
        "folio_mobile_month": self._folio_mobile_month,
        "folio_mobile_num": self._folio_mobile_num,
        "dashboard_rank_keys": self._dashboard_rank_keys or [],
        "rank_options": opts,
        "blacklist_keywords": self._blacklist_keywords or "",
        "observe_days": int(getattr(self, "_observe_days", 0) or 0),
        "observe_rank_keys": getattr(self, "_observe_rank_keys", []) or [],
    }}


def _dedupe_subscribe_records(records: list) -> tuple:
    """按状态、TMDB、标题、年份和榜单合并订阅历史。"""
    if not isinstance(records, list):
        return [], False
    merged = []
    index = {}
    changed = False
    for record in records:
        if not isinstance(record, dict):
            continue
        key = (
            str(record.get("status") or "success"),
            str(record.get("tmdbid") or ""),
            str(record.get("title") or ""),
            str(record.get("year") or ""),
            str(record.get("rank_key") or ""),
        )
        if key in index:
            target = merged[index[key]]
            if (record.get("time") or "") >= (target.get("time") or ""):
                target.update(record)
            changed = True
            continue
        index[key] = len(merged)
        merged.append(dict(record))
    if len(merged) != len(records):
        changed = True
    return merged[-500:], changed


def api_rank_history(self):
    from .feed import get_dashboard_rank_items
    rk = self._dashboard_rank_keys or []
    return {"data": {k: get_dashboard_rank_items(self, k, limit=5) for k in rk if k}}


def api_resolve_media_from_rank(self, media_type, title, year, tmdb_id=None, bangumi_id=None):
    """识别榜单条目并返回媒体信息。"""
    from app.schemas.types import MediaType as MT
    from app.core.metainfo import MetaInfo
    from app.chain.media import MediaChain

    mt = MT.MOVIE if media_type == "movie" else MT.TV
    meta = MetaInfo(title)
    if year:
        meta.year = str(year)
    meta.type = mt
    mediainfo = MediaChain().recognize_media(meta=meta, mtype=mt)
    if not mediainfo and bangumi_id:
        try:
            mediainfo = MediaChain().recognize_media(meta=meta, mtype=mt, bangumiid=bangumi_id)
        except TypeError:
            mediainfo = None
    if not mediainfo:
        if bangumi_id:
            from .feed import _fetch_bangumi_subject, bangumi_subject_to_media_data
            media_type_name = "电影" if mt == MT.MOVIE else "电视剧"
            subject = _fetch_bangumi_subject(self, bangumi_id)
            if subject:
                return {
                    "success": True,
                    "data": bangumi_subject_to_media_data(subject, media_type_name, fallback_title=title, bangumiid=bangumi_id),
                }
        if not tmdb_id and not bangumi_id:
            return {"success": False, "message": "无法识别媒体信息"}
        media_type_name = "电影" if mt == MT.MOVIE else "电视剧"
        mediaid_prefix = "tmdb" if tmdb_id else "bangumi"
        media_id = tmdb_id or bangumi_id
        return {
            "success": True,
            "data": {
                "title": title or "",
                "name": title or "",
                "year": year or "",
                "type": media_type_name,
                "tmdb_id": tmdb_id,
                "tmdbid": tmdb_id,
                "douban_id": None,
                "doubanid": None,
                "bangumi_id": bangumi_id,
                "bangumiid": bangumi_id,
                "mediaid_prefix": mediaid_prefix,
                "media_id": media_id,
                "poster_path": "",
                "overview": "",
                "season": getattr(meta, "begin_season", None) if mt == MT.TV else None,
                "source": "themoviedb" if tmdb_id else "bangumi",
            },
        }
    media_type_name = "电影" if mt == MT.MOVIE else "电视剧"
    poster_path = ""
    if hasattr(mediainfo, "poster_path"):
        poster_path = getattr(mediainfo, "poster_path") or ""
    if not poster_path and hasattr(mediainfo, "get_poster_image"):
        poster_path = mediainfo.get_poster_image() or ""
    return {
        "success": True,
        "data": {
            "title": getattr(mediainfo, "title", "") or title,
            "name": getattr(mediainfo, "title", "") or title,
            "year": getattr(mediainfo, "year", "") or year or "",
            "type": media_type_name,
            "tmdb_id": getattr(mediainfo, "tmdb_id", None),
            "tmdbid": getattr(mediainfo, "tmdb_id", None),
            "douban_id": getattr(mediainfo, "douban_id", None),
            "doubanid": getattr(mediainfo, "douban_id", None),
            "bangumi_id": getattr(mediainfo, "bangumi_id", None) or bangumi_id,
            "bangumiid": getattr(mediainfo, "bangumi_id", None) or bangumi_id,
            "mediaid_prefix": "tmdb" if getattr(mediainfo, "tmdb_id", None) else ("bangumi" if (getattr(mediainfo, "bangumi_id", None) or bangumi_id) else None),
            "media_id": getattr(mediainfo, "tmdb_id", None) or getattr(mediainfo, "bangumi_id", None) or bangumi_id,
            "poster_path": poster_path,
            "overview": getattr(mediainfo, "overview", "") or "",
            "season": getattr(meta, "begin_season", None) if mt == MT.TV else None,
            "source": "themoviedb" if getattr(mediainfo, "tmdb_id", None) else ("bangumi" if (getattr(mediainfo, "bangumi_id", None) or bangumi_id) else "themoviedb"),
        },
    }


def api_subscribe_from_rank(self, tmdb_id, media_type, title, year, bangumi_id=None):
    from app.schemas.types import MediaType as MT
    from app.core.metainfo import MetaInfo
    from app.chain.subscribe import SubscribeChain
    from app.chain.media import MediaChain
    mt = MT.TV if media_type == "tv" else MT.MOVIE
    meta = MetaInfo(title)
    if year:
        meta.year = str(year)
    meta.type = mt
    mediainfo = None
    if tmdb_id:
        try:
            mediainfo = MediaChain().recognize_media(meta=meta, mtype=mt, tmdbid=tmdb_id)
        except TypeError:
            mediainfo = None
    if not mediainfo:
        mediainfo = MediaChain().recognize_media(meta=meta, mtype=mt)
    if not mediainfo and bangumi_id:
        try:
            mediainfo = MediaChain().recognize_media(meta=meta, mtype=mt, bangumiid=bangumi_id)
        except TypeError:
            mediainfo = None
    if not mediainfo:
        if not bangumi_id:
            return {"success": False, "message": "无法识别媒体信息"}
        from .feed import _fetch_bangumi_subject, _bangumi_subject_title, _bangumi_subject_year
        subject = _fetch_bangumi_subject(self, bangumi_id)
        if not subject:
            return {"success": False, "message": "无法识别媒体信息"}
        sub_title = _bangumi_subject_title(subject, fallback=title)
        sub_year = _bangumi_subject_year(subject, fallback=year)
        sc = SubscribeChain()
        sid, msg = _add_silent_subscription(sc, sub_title, sub_year, mt, tmdb_id=None, bangumi_id=bangumi_id)
        if not sid:
            return {"success": False, "message": msg}
        return {"success": True, "message": "已添加订阅"}

    sc = SubscribeChain()
    if sc.exists(mediainfo=mediainfo, meta=meta):
        return {"success": False, "message": "已订阅"}
    sid, msg = _add_silent_subscription(
        sc,
        getattr(mediainfo, "title", None) or title,
        getattr(mediainfo, "year", None) or year or "",
        mt,
        tmdb_id=tmdb_id or getattr(mediainfo, "tmdb_id", None),
        bangumi_id=bangumi_id or getattr(mediainfo, "bangumi_id", None),
    )
    if not sid:
        return {"success": False, "message": msg}
    return {"success": True, "message": "已添加订阅"}


def _add_silent_subscription(sc, title, year, mt, tmdb_id=None, bangumi_id=None):
    """按 MP 默认订阅参数静默添加订阅。"""
    kwargs = {
        "title": title,
        "year": year or "",
        "mtype": mt,
        "tmdbid": tmdb_id,
        "season": None,
        "resolution": None,
        "sites": None,
        "exist_ok": True,
        "username": "豆瓣中心",
    }
    if bangumi_id:
        try:
            return sc.add(**kwargs, bangumiid=bangumi_id)
        except TypeError:
            return sc.add(**kwargs)
    return sc.add(**kwargs)


def api_stats(self):
    """订阅统计：基于 subscribe_records 统计"""
    from .feed import BUILTIN_RANKS

    records = self.get_data("subscribe_records") or []
    records, changed = _dedupe_subscribe_records(records)
    if changed:
        self.save_data("subscribe_records", records)
    total = len(records)
    rank_names = {rank["key"]: rank["name"] for rank in BUILTIN_RANKS}
    rank_dist = {rank["key"]: 0 for rank in BUILTIN_RANKS}
    unknown_count = 0
    type_dist = {"电影": 0, "电视剧": 0}
    month_new = 0
    now = datetime.datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for r in records:
        rk = r.get("rank_key") or "unknown"
        if rk in rank_dist:
            rank_dist[rk] += 1
        else:
            unknown_count += 1
        mt = r.get("media_type", "")
        if mt in type_dist:
            type_dist[mt] += 1
        t = r.get("time", "")
        if t:
            try:
                if datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S") >= month_start:
                    month_new += 1
            except Exception:
                pass
    rank_stats = [
        {"key": rank["key"], "name": rank_names.get(rank["key"], rank["key"]), "count": rank_dist.get(rank["key"], 0)}
        for rank in BUILTIN_RANKS
    ]
    if unknown_count:
        rank_dist["unknown"] = unknown_count
        rank_stats.append({"key": "unknown", "name": "未归类", "count": unknown_count})
    return {"data": {"total": total, "rank_dist": rank_dist, "rank_stats": rank_stats, "type_dist": type_dist, "month_new": month_new}}


def api_subscribe_history(self, page=1, page_size=20):
    """订阅历史：基于 subscribe_records 分页"""
    records = self.get_data("subscribe_records") or []
    records, changed = _dedupe_subscribe_records(records)
    records.sort(key=lambda x: x.get("time", ""), reverse=True)
    records, overflow_changed = _archive_detail_overflow(self, records, "subscribe_history", "订阅历史")
    if changed or overflow_changed:
        self.save_data("subscribe_records", records)
    total = len(records)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = records[start:end]
    return {"data": {"items": page_items, "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size}}


def _item_existing_subscription(item: dict) -> bool:
    """判断条目是否已标记为订阅存在。"""
    return bool(
        isinstance(item, dict)
        and (item.get("existing") or item.get("existing_at"))
        and item.get("existing_reason") == "subscribe"
    )


def _observed_item_subscription_exists(item: dict, rank_key: str = "") -> bool:
    """检查观察队列条目是否已经存在订阅。"""
    title = (item or {}).get("title") or ""
    if not title:
        return False
    try:
        from app.schemas.types import MediaType as MT
        from app.core.metainfo import MetaInfo
        from app.chain.subscribe import SubscribeChain
        from app.chain.media import MediaChain

        raw_type = str((item or {}).get("mtype") or (item or {}).get("media_type") or "").lower()
        if raw_type in ("movie", "电影") or rank_key == "movie_weekly":
            media_type = MT.MOVIE
        else:
            media_type = MT.TV
        meta = MetaInfo(title)
        year = (item or {}).get("year") or ""
        if year:
            meta.year = str(year)
        meta.type = media_type
        mediainfo = MediaChain().recognize_media(meta=meta, mtype=media_type)
        if not mediainfo:
            return False
        return bool(SubscribeChain().exists(mediainfo=mediainfo, meta=meta))
    except Exception:
        return False


def _same_record(item: dict, unique: str = "", time: str = "", title: str = "", tmdbid: Any = None) -> bool:
    """按稳定字段判断是否为同一条详情页记录。"""
    if not isinstance(item, dict):
        return False
    if unique and item.get("unique") == unique:
        return True
    if tmdbid not in (None, "") and str(item.get("tmdbid") or "") == str(tmdbid):
        if not title or item.get("title") == title:
            return True
    if time and item.get("time") == time:
        if not title or item.get("title") == title:
            return True
    return False


def _archive_record_key(source: str, record: dict) -> tuple:
    """生成归档记录去重键。"""
    if not isinstance(record, dict):
        return (source, "")
    return (
        source,
        str(record.get("unique") or ""),
        str(record.get("tmdbid") or record.get("tmdb_id") or ""),
        str(record.get("title") or ""),
        str(record.get("reason") or ""),
        str(record.get("detail") or ""),
        str(record.get("time") or ""),
        str(record.get("link") or ""),
    )


def _archive_record_score(record: dict) -> int:
    """计算归档原始记录的信息完整度。"""
    if not isinstance(record, dict):
        return 0
    score = sum(1 for value in record.values() if value not in (None, "", [], {}))
    for field in ("unique", "poster", "tmdbid", "rank_key", "rank_name", "first_seen", "subscribed_at"):
        if record.get(field):
            score += 5
    return score


def _same_archive_record(source: str, left: dict, right: dict) -> bool:
    """按来源判断两条归档原始记录是否重复。"""
    return _archive_record_key(source, left) == _archive_record_key(source, right)


def _update_archive_item_from_record(archive: dict, source: str, record: dict, source_name: str = "") -> dict:
    """用更完整的原始记录刷新归档展示字段。"""
    copied = dict(record)
    archive.update({
        "source": source,
        "source_name": source_name or archive.get("source_name") or source,
        "title": copied.get("title") or archive.get("title") or "",
        "time": copied.get("time") or copied.get("first_seen") or archive.get("time") or "",
        "rank_key": copied.get("rank_key") or archive.get("rank_key") or "",
        "rank_name": copied.get("rank_name") or archive.get("rank_name") or "",
        "reason": copied.get("reason") or archive.get("reason") or "",
        "record": copied,
    })
    return archive


def _dedupe_archive_records(archives: list) -> tuple:
    """压缩重复归档记录，保留信息更完整的一条。"""
    if not isinstance(archives, list):
        return [], False
    merged = []
    changed = False
    for archive in archives:
        if not isinstance(archive, dict):
            changed = True
            continue
        source = str(archive.get("source") or "")
        record = archive.get("record") or {}
        duplicate_index = None
        for index, existing in enumerate(merged):
            if str(existing.get("source") or "") != source:
                continue
            if _same_archive_record(source, existing.get("record") or {}, record):
                duplicate_index = index
                break
        if duplicate_index is None:
            merged.append(archive)
            continue
        changed = True
        existing = merged[duplicate_index]
        if _archive_record_score(record) > _archive_record_score(existing.get("record") or {}):
            merged[duplicate_index] = archive
    return merged[-500:], changed or len(merged) != len(archives)


def _archive_record(self, source: str, record: dict, source_name: str = "", dedupe: bool = False) -> Optional[dict]:
    """将详情页删除的记录写入归档。"""
    if not isinstance(record, dict):
        return None
    archives = self.get_data("archive_records") or []
    if not isinstance(archives, list):
        archives = []
    if dedupe:
        for index, archive in enumerate(archives):
            if not isinstance(archive, dict) or archive.get("source") != source:
                continue
            if _same_archive_record(source, archive.get("record") or {}, record):
                if _archive_record_score(record) > _archive_record_score(archive.get("record") or {}):
                    archives[index] = _update_archive_item_from_record(archive, source, record, source_name)
                    self.save_data("archive_records", archives)
                    return archives[index]
                return archive
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    archive_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
    copied = dict(record)
    item = {
        "id": archive_id,
        "source": source,
        "source_name": source_name or source,
        "title": copied.get("title") or "",
        "time": copied.get("time") or copied.get("first_seen") or "",
        "rank_key": copied.get("rank_key") or "",
        "rank_name": copied.get("rank_name") or "",
        "reason": copied.get("reason") or "",
        "archived_at": now,
        "record": copied,
    }
    archives.append(item)
    if len(archives) > 500:
        archives = archives[-500:]
    self.save_data("archive_records", archives)
    return item


def _detail_record_time(record: dict) -> str:
    """返回详情页记录用于新旧排序的时间字段。"""
    if not isinstance(record, dict):
        return ""
    return str(record.get("time") or record.get("first_seen") or record.get("archived_at") or "")


def _latest_detail_indexes(records: list, limit: int = DETAIL_SECTION_LIMIT) -> set:
    """按时间选出详情页应保留的最新记录下标。"""
    indexed = [(index, record) for index, record in enumerate(records) if isinstance(record, dict)]
    ordered = sorted(indexed, key=lambda pair: (_detail_record_time(pair[1]), pair[0]), reverse=True)
    return {index for index, _ in ordered[:limit]}


def _archive_detail_overflow(self, records: list, source: str, source_name: str, limit: int = DETAIL_SECTION_LIMIT) -> tuple:
    """保留最新详情记录，并将超出上限的条目写入归档。"""
    if not isinstance(records, list) or len(records) <= limit:
        return records if isinstance(records, list) else [], False
    keep_indexes = _latest_detail_indexes(records, limit)
    kept = []
    changed = False
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            changed = True
            continue
        if index in keep_indexes:
            kept.append(record)
            continue
        archive_record = dict(record)
        archive_record.setdefault("reason", record.get("reason") or DETAIL_OVERFLOW_REASON)
        _archive_record(self, source, archive_record, source_name, dedupe=True)
        changed = True
    return kept, changed


def _archive_anti_cheat_overflow(self, logs: list, limit: int = DETAIL_SECTION_LIMIT) -> tuple:
    """分别限制黑名拦截与观察日志的详情页展示数量。"""
    if not isinstance(logs, list):
        return [], False
    blacklist_indexes = []
    observe_indexes = []
    for index, log in enumerate(logs):
        if not isinstance(log, dict):
            continue
        if str(log.get("reason") or "") == "黑名单关键词":
            blacklist_indexes.append(index)
        else:
            observe_indexes.append(index)

    keep_indexes = set()
    changed = False
    for indexes, source_name in ((blacklist_indexes, "黑名拦截"), (observe_indexes, "观察日志")):
        if len(indexes) <= limit:
            keep_indexes.update(indexes)
            continue
        ordered = sorted(indexes, key=lambda item_index: (_detail_record_time(logs[item_index]), item_index), reverse=True)
        keep_indexes.update(ordered[:limit])
        for item_index in ordered[limit:]:
            _archive_record(self, "anti_cheat_log", logs[item_index], source_name, dedupe=True)
            changed = True
    kept = [log for index, log in enumerate(logs) if index in keep_indexes]
    return kept, changed


def _anti_cheat_log_key(record: dict) -> tuple:
    """生成观察日志记录的去重键。"""
    if not isinstance(record, dict):
        return ("", "", "", "", "")
    return (
        str(record.get("title") or ""),
        str(record.get("reason") or ""),
        str(record.get("detail") or ""),
        str(record.get("time") or ""),
        str(record.get("link") or ""),
    )


def _remove_legacy_observation_completed_archives(self) -> bool:
    """将旧版观察完成归档迁回观察日志并从归档页移除。"""
    archives = self.get_data("archive_records") or []
    if not isinstance(archives, list):
        return False
    logs = self.get_data("anti_cheat_logs") or []
    if not isinstance(logs, list):
        logs = []
    existing_log_keys = {_anti_cheat_log_key(log) for log in logs if isinstance(log, dict)}
    kept_archives = []
    changed = False
    for archive in archives:
        if not isinstance(archive, dict):
            changed = True
            continue
        if archive.get("source") != "observation_completed":
            kept_archives.append(archive)
            continue
        record = dict(archive.get("record") or {})
        record["title"] = record.get("title") or archive.get("title") or ""
        record["time"] = record.get("time") or archive.get("time") or ""
        record["reason"] = record.get("reason") or "观察期完成"
        key = _anti_cheat_log_key(record)
        if key not in existing_log_keys:
            logs.append(record)
            existing_log_keys.add(key)
        changed = True
    if changed:
        self.save_data("archive_records", kept_archives)
        self.save_data("anti_cheat_logs", logs[-100:])
    return changed


def _remove_archive(self, archive_id: str) -> Optional[dict]:
    """从归档列表取出并删除一条归档记录。"""
    archives = self.get_data("archive_records") or []
    if not isinstance(archives, list):
        return None
    removed = None
    kept = []
    for item in archives:
        if isinstance(item, dict) and item.get("id") == archive_id and removed is None:
            removed = item
            continue
        kept.append(item)
    if removed:
        self.save_data("archive_records", kept)
    return removed


def api_delete_subscribe_history(self, time: str = "", title: str = "", tmdbid: Any = None):
    """删除一条豆瓣中心订阅历史记录。"""
    records = self.get_data("subscribe_records") or []
    removed = [item for item in records if _same_record(item, time=time, title=title, tmdbid=tmdbid)]
    kept = [item for item in records if item not in removed]
    if len(kept) == len(records):
        return {"success": False, "message": "未找到订阅历史记录"}
    archive = None
    for item in removed:
        archive = _archive_record(self, "subscribe_history", item, "订阅历史") or archive
    self.save_data("subscribe_records", kept)
    return {"success": True, "message": "已归档订阅历史记录", "archive_id": archive.get("id") if archive else ""}


def api_pending_observations(self):
    """获取观察期内等待自动订阅的榜单条目。"""
    if int(self._observe_days or 0) <= 0:
        return {"data": []}
    from .feed import BUILTIN_RANKS, get_rank_history_by_key
    now = datetime.datetime.now()
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    observe_days = int(self._observe_days or 0)
    items = []
    histories = {}
    changed_rank_keys = set()
    for rank in BUILTIN_RANKS:
        rank_key = rank["key"]
        data_key = "coming_history" if rank_key == "coming" else f"rank_history_{rank_key}"
        history = get_rank_history_by_key(self, rank_key)
        histories[rank_key] = (data_key, history)
        changed = False
        for item in history:
            if not isinstance(item, dict) or not item.get("observing"):
                continue
            if item.get("observe_deleted") or item.get("subscribed") or item.get("subscribed_at") or _item_existing_subscription(item):
                continue
            if _observed_item_subscription_exists(item, rank_key=rank_key):
                item["observing"] = False
                item["existing"] = True
                item["existing_at"] = now_text
                item["existing_reason"] = "subscribe"
                changed = True
                continue
            first_seen = item.get("first_seen") or item.get("time") or ""
            elapsed_days = 0
            if first_seen:
                try:
                    first_seen_at = datetime.datetime.strptime(first_seen, "%Y-%m-%d %H:%M:%S")
                    elapsed_days = max((now - first_seen_at).days, 0)
                except Exception:
                    elapsed_days = 0
            pending = dict(item)
            pending.update({
                "rank_key": rank_key,
                "rank_name": rank["name"],
                "observe_days": observe_days,
                "elapsed_days": elapsed_days,
                "remaining_days": max(observe_days - elapsed_days, 0),
            })
            items.append(pending)
        if changed:
            changed_rank_keys.add(rank_key)
    items.sort(key=lambda x: x.get("first_seen") or x.get("time") or "", reverse=True)
    if len(items) > DETAIL_SECTION_LIMIT:
        overflow = items[DETAIL_SECTION_LIMIT:]
        items = items[:DETAIL_SECTION_LIMIT]
        for pending in overflow:
            if not isinstance(pending, dict):
                continue
            rank_key = pending.get("rank_key") or ""
            data_key, history = histories.get(rank_key, ("", []))
            target_unique = pending.get("unique")
            target_title = pending.get("title")
            for item in history:
                if not isinstance(item, dict):
                    continue
                same_unique = target_unique and item.get("unique") == target_unique
                same_title = not target_unique and target_title and item.get("title") == target_title
                if not (same_unique or same_title):
                    continue
                item["observing"] = False
                item["observe_deleted"] = True
                item["observe_deleted_at"] = now_text
                item["observe_deleted_reason"] = DETAIL_OVERFLOW_REASON
                changed_rank_keys.add(rank_key)
                break
            record = dict(pending)
            record["reason"] = DETAIL_OVERFLOW_REASON
            _archive_record(self, "observation", record, "观察队列", dedupe=True)
    for rank_key in changed_rank_keys:
        data_key, history = histories.get(rank_key, ("", []))
        if data_key:
            self.save_data(data_key, history)
    return {"data": items}


def api_delete_observation(self, unique: str = "", rank_key: str = "", title: str = ""):
    """从观察队列删除条目，并标记为已忽略以避免再次自动进入队列。"""
    if not unique:
        return {"success": False, "message": "缺少观察条目标识"}
    from .feed import BUILTIN_RANKS, get_rank_history_by_key
    rank_keys = [rank_key] if rank_key else [rank["key"] for rank in BUILTIN_RANKS]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for key in rank_keys:
        data_key = "coming_history" if key == "coming" else f"rank_history_{key}"
        history = get_rank_history_by_key(self, key)
        changed = False
        for item in history:
            if not isinstance(item, dict) or item.get("unique") != unique:
                continue
            item["observing"] = False
            item["observe_deleted"] = True
            item["observe_deleted_at"] = now
            if title:
                item["title"] = item.get("title") or title
            record = dict(item)
            record["rank_key"] = key
            changed = True
            break
        if changed:
            archive = _archive_record(self, "observation", record, "观察队列")
            self.save_data(data_key, history)
            return {"success": True, "message": "已归档观察条目", "archive_id": archive.get("id") if archive else ""}
    return {"success": False, "message": "未找到观察条目"}


def _dedupe_anti_cheat_logs(logs: list) -> tuple:
    """按原因、标题和详情合并观察日志。"""
    if not isinstance(logs, list):
        return [], False
    merged = []
    index = {}
    changed = False
    for log in logs:
        if not isinstance(log, dict):
            continue
        key = (log.get("reason") or "", log.get("title") or "", log.get("detail") or "")
        if key in index:
            target = merged[index[key]]
            try:
                target["count"] = int(target.get("count") or 1) + int(log.get("count") or 1)
            except (TypeError, ValueError):
                target["count"] = int(target.get("count") or 1) + 1
            if (log.get("time") or "") >= (target.get("time") or ""):
                target["time"] = log.get("time")
            changed = True
            continue
        copied = dict(log)
        if int(copied.get("count") or 1) > 1:
            copied["count"] = int(copied.get("count") or 1)
        index[key] = len(merged)
        merged.append(copied)
    if len(merged) != len(logs):
        changed = True
    return merged[-100:], changed


def _finished_observation_titles(self) -> set:
    """收集已经结束观察的条目标题，用于清理观察日志。"""
    titles = set()
    records = self.get_data("subscribe_records") or []
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, dict):
                continue
            status = str(record.get("status") or "success")
            title = str(record.get("title") or "")
            if title and status != "failed":
                titles.add(title)
    try:
        from .feed import BUILTIN_RANKS, get_rank_history_by_key
        for rank in BUILTIN_RANKS:
            history = get_rank_history_by_key(self, rank["key"])
            if not isinstance(history, list):
                continue
            for item in history:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "")
                if not title:
                    continue
                finished = (
                    item.get("subscribed")
                    or item.get("subscribed_at")
                    or _item_existing_subscription(item)
                    or (item.get("observing") is False and (item.get("observe_dropped_at") or item.get("observe_deleted_at")))
                )
                if finished:
                    titles.add(title)
    except Exception:
        pass
    return titles


def _observation_completion_log(item: dict, rank: dict) -> Optional[dict]:
    """从榜单历史构造观察完成日志。"""
    if not isinstance(item, dict) or not isinstance(rank, dict):
        return None
    title = str(item.get("title") or "")
    first_seen = str(item.get("first_seen") or "")
    subscribed_at = str(item.get("subscribed_at") or "")
    if not title or not first_seen or not (item.get("subscribed") or subscribed_at):
        return None
    record = dict(item)
    record.update({
        "time": subscribed_at or str(item.get("time") or first_seen),
        "reason": "观察期完成",
        "title": title,
        "detail": f"{rank.get('name') or rank.get('key') or ''}：{first_seen} -> {subscribed_at or '已订阅'}",
        "link": item.get("link") or "",
        "rank_key": rank.get("key") or item.get("rank_key") or "",
        "rank_name": rank.get("name") or item.get("rank_name") or "",
        "first_seen": first_seen,
        "subscribed_at": subscribed_at,
    })
    return record


def _append_observation_completion_logs(self, logs: list) -> tuple:
    """补齐已订阅观察条目的观察完成日志。"""
    if not isinstance(logs, list):
        logs = []
    changed = False
    existing_titles = {
        str(log.get("title") or "")
        for log in logs
        if isinstance(log, dict) and str(log.get("reason") or "") == "观察期完成"
    }
    archives = self.get_data("archive_records") or []
    if isinstance(archives, list):
        for archive in archives:
            if not isinstance(archive, dict):
                continue
            record = archive.get("record") or {}
            if archive.get("source") == "anti_cheat_log" and str(record.get("reason") or "") == "观察期完成":
                existing_titles.add(str(record.get("title") or archive.get("title") or ""))
    try:
        from .feed import BUILTIN_RANKS, get_rank_history_by_key
        for rank in BUILTIN_RANKS:
            history = get_rank_history_by_key(self, rank["key"])
            if not isinstance(history, list):
                continue
            for item in history:
                record = _observation_completion_log(item, rank)
                if not record or str(record.get("title") or "") in existing_titles:
                    continue
                logs.append(record)
                existing_titles.add(str(record.get("title") or ""))
                changed = True
    except Exception:
        return logs, changed
    if len(logs) > 100:
        logs = logs[-100:]
        changed = True
    return logs, changed


def _reconcile_anti_cheat_logs(self, logs: list) -> tuple:
    """合并并清理已结束观察项的观察日志。"""
    logs, changed = _dedupe_anti_cheat_logs(logs)
    finished_titles = _finished_observation_titles(self)
    if finished_titles:
        observe_reasons = {"观察期首次记录", "观察期未满"}
        kept = []
        for log in logs:
            if (
                isinstance(log, dict)
                and str(log.get("reason") or "") in observe_reasons
                and str(log.get("title") or "") in finished_titles
            ):
                changed = True
                continue
            kept.append(log)
        logs = kept
    logs, completion_logs_changed = _append_observation_completion_logs(self, logs)
    changed = changed or completion_logs_changed
    return logs, changed


def api_anti_cheat_logs(self):
    """观察日志。"""
    _remove_legacy_observation_completed_archives(self)
    logs = self.get_data("anti_cheat_logs") or []
    logs, changed = _reconcile_anti_cheat_logs(self, logs)
    logs, overflow_changed = _archive_anti_cheat_overflow(self, logs)
    if changed or overflow_changed:
        self.save_data("anti_cheat_logs", logs)
    return {"data": logs}


def api_overview(self):
    """返回设置页运行总览数据。"""
    from .feed import BUILTIN_RANKS, get_rank_history_by_key

    _remove_legacy_observation_completed_archives(self)
    subscribe_records = self.get_data("subscribe_records") or []
    if not isinstance(subscribe_records, list):
        subscribe_records = []
    subscribe_records, changed_subscribe_records = _dedupe_subscribe_records(subscribe_records)
    if changed_subscribe_records:
        self.save_data("subscribe_records", subscribe_records)
    anti_cheat_logs = self.get_data("anti_cheat_logs") or []
    if not isinstance(anti_cheat_logs, list):
        anti_cheat_logs = []
    anti_cheat_logs, changed_anti_cheat_logs = _reconcile_anti_cheat_logs(self, anti_cheat_logs)
    if changed_anti_cheat_logs:
        self.save_data("anti_cheat_logs", anti_cheat_logs)
    archive_records = self.get_data("archive_records") or []
    if not isinstance(archive_records, list):
        archive_records = []
    archive_records, changed_archive_records = _dedupe_archive_records(archive_records)
    if changed_archive_records:
        self.save_data("archive_records", archive_records)
    folio_data = self.get_data("folio_data") or {}
    if not isinstance(folio_data, dict):
        folio_data = {}

    rank_items = 0
    last_refresh = ""
    pending_observations = 0
    ignored_observations = 0
    for rank in BUILTIN_RANKS:
        rank_key = rank["key"]
        history = get_rank_history_by_key(self, rank_key)
        if not isinstance(history, list):
            continue
        rank_items += len(history)
        for item in history:
            if not isinstance(item, dict):
                continue
            refreshed_at = item.get("rank_refreshed_at") or ""
            if refreshed_at > last_refresh:
                last_refresh = refreshed_at
            if item.get("observe_deleted"):
                ignored_observations += 1
            if item.get("observing") and not item.get("observe_deleted") and not item.get("subscribed") and not _item_existing_subscription(item):
                pending_observations += 1

    stats = api_stats(self).get("data", {})
    enabled_ranks = sum(
        1
        for cfg in (getattr(self, "_rank_configs", {}) or {}).values()
        if isinstance(cfg, dict) and cfg.get("enabled")
    )
    blacklist_hits = sum(
        1
        for item in anti_cheat_logs
        if isinstance(item, dict) and "黑名单" in str(item.get("reason") or "")
    )
    return {
        "code": 0,
        "cards": {
            "rss": {
                "enabled": enabled_ranks,
                "total": len(BUILTIN_RANKS),
                "items": rank_items,
                "last_refresh": last_refresh,
            },
            "subscribe": {
                "enabled": bool(getattr(self, "_enabled", False)),
                "total": len(subscribe_records),
                "month_new": int(stats.get("month_new") or 0),
            },
            "archive": {
                "enabled": True,
                "total": len(archive_records),
                "pending": pending_observations,
                "ignored": ignored_observations,
            },
            "observe": {
                "enabled": bool(int(getattr(self, "_observe_days", 0) or 0) > 0 and getattr(self, "_observe_rank_keys", [])),
                "days": int(getattr(self, "_observe_days", 0) or 0),
                "pending": pending_observations,
                "ignored": ignored_observations,
            },
            "folio": {
                "enabled": bool(getattr(self, "_folio_enabled", False)),
                "items": len(folio_data),
                "user": getattr(self, "_folio_user", "") or "",
            },
        },
        "attention": {
            "pending_observations": pending_observations,
            "subscribe_records": len(subscribe_records),
            "month_new": int(stats.get("month_new") or 0),
            "anti_cheat_logs": len(anti_cheat_logs),
            "blacklist_hits": blacklist_hits,
        },
        "governance": {
            "archive_records": len(archive_records),
            "ignored_observations": ignored_observations,
            "anti_cheat_logs": len(anti_cheat_logs),
            "subscribe_records": len(subscribe_records),
        },
        "stats": stats,
        "flows": [
            {"label": "榜单订阅", "steps": ["榜单刷新", "条件筛选", "观察入池", "自动订阅", "记录写入"]},
            {"label": "归档治理", "steps": ["条目删除", "归档入库", "手动恢复", "记录清理"]},
            {"label": "豆瓣时间", "steps": ["媒体事件", "条目识别", "豆瓣同步", "时间写入"]},
        ],
    }


def api_archive_records(self, page: int = 1, page_size: int = 20):
    """返回详情页归档记录。"""
    _remove_legacy_observation_completed_archives(self)
    archives = self.get_data("archive_records") or []
    if not isinstance(archives, list):
        archives = []
    archives = [item for item in archives if isinstance(item, dict)]
    archives, changed = _dedupe_archive_records(archives)
    if changed:
        self.save_data("archive_records", archives)
    archives.sort(key=lambda x: x.get("archived_at", ""), reverse=True)
    total = len(archives)
    start = (int(page) - 1) * int(page_size)
    end = start + int(page_size)
    return {"data": {"items": archives[start:end], "total": total, "page": int(page), "page_size": int(page_size), "total_pages": (total + int(page_size) - 1) // int(page_size)}}


def api_restore_archive(self, archive_id: str = ""):
    """将归档记录恢复回原数据列表。"""
    if not archive_id:
        return {"success": False, "message": "缺少归档标识"}
    archive = _remove_archive(self, archive_id)
    if not archive:
        return {"success": False, "message": "未找到归档记录"}
    source = archive.get("source")
    record = archive.get("record") or {}
    if source == "subscribe_history":
        records = self.get_data("subscribe_records") or []
        if not any(_same_record(item, unique=record.get("unique", ""), time=record.get("time", ""), title=record.get("title", ""), tmdbid=record.get("tmdbid")) for item in records):
            records.append(record)
        self.save_data("subscribe_records", records)
    elif source == "anti_cheat_log":
        logs = self.get_data("anti_cheat_logs") or []
        logs.append(record)
        self.save_data("anti_cheat_logs", logs[-100:])
    elif source == "observation":
        rank_key = record.get("rank_key") or archive.get("rank_key") or ""
        if not rank_key:
            return {"success": False, "message": "归档缺少榜单标识"}
        data_key = "coming_history" if rank_key == "coming" else f"rank_history_{rank_key}"
        history = self.get_data(data_key) or []
        restored = False
        for item in history:
            if isinstance(item, dict) and item.get("unique") == record.get("unique"):
                item.update(record)
                item["observing"] = True
                item["observe_deleted"] = False
                restored = True
                break
        if not restored:
            record["observing"] = True
            record["observe_deleted"] = False
            history.append(record)
        self.save_data(data_key, history)
    else:
        return {"success": False, "message": "未知归档类型"}
    return {"success": True, "message": "已恢复归档记录"}


def api_delete_archive(self, archive_id: str = ""):
    """永久删除一条归档记录。"""
    if not archive_id:
        return {"success": False, "message": "缺少归档标识"}
    archive = _remove_archive(self, archive_id)
    if not archive:
        return {"success": False, "message": "未找到归档记录"}
    return {"success": True, "message": "已删除归档记录"}


def api_delete_anti_cheat_log(self, time: str = "", title: str = "", reason: str = ""):
    """删除一条观察日志记录。"""
    if not (time or title or reason):
        return {"success": False, "message": "缺少观察日志标识"}
    logs = self.get_data("anti_cheat_logs") or []
    removed = [
        item for item in logs
        if (
            isinstance(item, dict)
            and (not time or item.get("time") == time)
            and (not title or item.get("title") == title)
            and (not reason or item.get("reason") == reason)
        )
    ]
    kept = [item for item in logs if item not in removed]
    if len(kept) == len(logs):
        return {"success": False, "message": "未找到观察日志"}
    archive = None
    for item in removed:
        archive = _archive_record(self, "anti_cheat_log", item, "观察日志") or archive
    self.save_data("anti_cheat_logs", kept)
    return {"success": True, "message": "已归档观察日志", "archive_id": archive.get("id") if archive else ""}
