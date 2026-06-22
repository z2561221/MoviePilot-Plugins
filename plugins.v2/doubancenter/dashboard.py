"""
DoubanCenter - 仪表盘模块
"""
import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.chain.media import MediaChain
from app.core.metainfo import MetaInfo
from app.schemas.types import MediaType


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
    """获取豆瓣档案数据，优先读自己的，没有则读原版豆瓣中心的"""
    data = self.get_data('folio_data') or {}
    if not data:
        data = self.get_data('folio_data', plugin_id='DoubanCenter') or {}
    return {"data": data}


def api_config(self):
    from .feed import BUILTIN_RANKS, _ren
    opts = [{"title": rd["name"], "value": rd["key"]} for rd in BUILTIN_RANKS if _ren(self, rd["key"])]
    return {"data": {"folio_pc_month": self._folio_pc_month, "folio_pc_num": self._folio_pc_num, "folio_mobile_month": self._folio_mobile_month, "folio_mobile_num": self._folio_mobile_num, "dashboard_rank_keys": self._dashboard_rank_keys or [], "rank_options": opts, "blacklist_keywords": self._blacklist_keywords or ""}}


def api_rank_history(self):
    from .feed import get_dashboard_rank_items
    rk = self._dashboard_rank_keys or []
    return {"data": {k: get_dashboard_rank_items(self, k, limit=5) for k in rk if k}}


def api_subscribe_from_rank(self, tmdb_id, media_type, title, year):
    from app.schemas.types import MediaType as MT
    from app.core.metainfo import MetaInfo
    from app.chain.subscribe import SubscribeChain
    from app.chain.download import DownloadChain
    from app.chain.media import MediaChain
    mt = MT.TV if media_type == "tv" else MT.MOVIE
    meta = MetaInfo(title)
    if year:
        meta.year = str(year)
    meta.type = mt
    mediainfo = MediaChain().recognize_media(meta=meta, mtype=mt)
    if not mediainfo:
        return {"success": False, "message": "无法识别媒体信息"}
    dc = DownloadChain()
    sc = SubscribeChain()
    ef, _ = dc.get_no_exists_info(meta=meta, mediainfo=mediainfo)
    if ef:
        return {"success": False, "message": "媒体库中已存在"}
    if sc.exists(mediainfo=mediainfo, meta=meta):
        return {"success": False, "message": "已订阅"}
    sid, msg = sc.add(title=title, year=year or "", mtype=mt, tmdbid=tmdb_id or mediainfo.tmdb_id, season=meta.begin_season if meta.type == MT.TV else None, exist_ok=True, username="豆瓣中心-仪表盘", message=False)
    return {"success": True, "message": "已添加订阅"} if sid else {"success": False, "message": msg}


def api_stats(self):
    """订阅统计：基于 subscribe_records 统计"""
    from .feed import BUILTIN_RANKS

    records = self.get_data("subscribe_records") or []
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
    records.sort(key=lambda x: x.get("time", ""), reverse=True)
    total = len(records)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = records[start:end]
    return {"data": {"items": page_items, "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size}}


def _observed_item_exists_in_library(item: dict, rank_key: str = "") -> bool:
    """检查观察队列条目是否已经存在于媒体库或订阅中。"""
    title = (item or {}).get("title") or ""
    if not title:
        return False
    try:
        from app.schemas.types import MediaType as MT
        from app.core.metainfo import MetaInfo
        from app.chain.download import DownloadChain
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
        ef, _ = DownloadChain().get_no_exists_info(meta=meta, mediainfo=mediainfo)
        if ef:
            return True
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


def api_delete_subscribe_history(self, time: str = "", title: str = "", tmdbid: Any = None):
    """删除一条豆瓣中心订阅历史记录。"""
    records = self.get_data("subscribe_records") or []
    kept = [item for item in records if not _same_record(item, time=time, title=title, tmdbid=tmdbid)]
    if len(kept) == len(records):
        return {"success": False, "message": "未找到订阅历史记录"}
    self.save_data("subscribe_records", kept)
    return {"success": True, "message": "已删除订阅历史记录"}


def api_pending_observations(self):
    """获取观察期内等待自动订阅的榜单条目。"""
    if not self._anti_cheat_enabled or int(self._observe_days or 0) <= 0:
        return {"data": []}
    from .feed import BUILTIN_RANKS, get_rank_history_by_key
    now = datetime.datetime.now()
    observe_days = int(self._observe_days or 0)
    items = []
    for rank in BUILTIN_RANKS:
        rank_key = rank["key"]
        data_key = "coming_history" if rank_key == "coming" else f"rank_history_{rank_key}"
        history = get_rank_history_by_key(self, rank_key)
        changed = False
        for item in history:
            if not isinstance(item, dict) or not item.get("observing"):
                continue
            if item.get("observe_deleted") or item.get("subscribed") or item.get("subscribed_at") or item.get("existing") or item.get("existing_at"):
                continue
            if _observed_item_exists_in_library(item, rank_key=rank_key):
                item["observing"] = False
                item["existing"] = True
                item["existing_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
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
            self.save_data(data_key, history)
    items.sort(key=lambda x: x.get("first_seen") or x.get("time") or "", reverse=True)
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
            changed = True
            break
        if changed:
            self.save_data(data_key, history)
            return {"success": True, "message": "已从观察队列删除"}
    return {"success": False, "message": "未找到观察条目"}


def _dedupe_anti_cheat_logs(logs: list) -> tuple:
    """按原因、标题和详情合并防刷日志。"""
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


def api_anti_cheat_logs(self):
    """防刷榜日志"""
    logs = self.get_data("anti_cheat_logs") or []
    logs, changed = _dedupe_anti_cheat_logs(logs)
    if changed:
        self.save_data("anti_cheat_logs", logs)
    return {"data": logs}


def api_delete_anti_cheat_log(self, time: str = "", title: str = "", reason: str = ""):
    """删除一条防刷榜日志记录。"""
    if not (time or title or reason):
        return {"success": False, "message": "缺少防刷日志标识"}
    logs = self.get_data("anti_cheat_logs") or []
    kept = [
        item for item in logs
        if not (
            isinstance(item, dict)
            and (not time or item.get("time") == time)
            and (not title or item.get("title") == title)
            and (not reason or item.get("reason") == reason)
        )
    ]
    if len(kept) == len(logs):
        return {"success": False, "message": "未找到防刷日志"}
    self.save_data("anti_cheat_logs", kept)
    return {"success": True, "message": "已删除防刷日志"}
