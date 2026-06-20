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
    return {"data": {"folio_pc_month": self._folio_pc_month, "folio_pc_num": self._folio_pc_num, "folio_mobile_month": self._folio_mobile_month, "folio_mobile_num": self._folio_mobile_num, "dashboard_rank_keys": self._dashboard_rank_keys or [], "rank_options": opts}}


def api_rank_history(self):
    from .feed import get_rank_history_by_key
    rk = self._dashboard_rank_keys or []
    return {"data": {k: list(reversed(get_rank_history_by_key(self, k)[-5:])) for k in rk if k}}


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
    records = self.get_data("subscribe_records") or []
    total = len(records)
    rank_dist = {}
    type_dist = {"电影": 0, "电视剧": 0}
    month_new = 0
    now = datetime.datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for r in records:
        rk = r.get("rank_key", "unknown")
        rank_dist[rk] = rank_dist.get(rk, 0) + 1
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
    return {"data": {"total": total, "rank_dist": rank_dist, "type_dist": type_dist, "month_new": month_new}}


def api_subscribe_history(self, page=1, page_size=20):
    """订阅历史：基于 subscribe_records 分页"""
    records = self.get_data("subscribe_records") or []
    records.sort(key=lambda x: x.get("time", ""), reverse=True)
    total = len(records)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = records[start:end]
    return {"data": {"items": page_items, "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size}}


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
        for item in get_rank_history_by_key(self, rank_key):
            if not isinstance(item, dict) or not item.get("observing"):
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
    items.sort(key=lambda x: x.get("first_seen") or x.get("time") or "", reverse=True)
    return {"data": items}


def api_anti_cheat_logs(self):
    """防刷榜日志"""
    logs = self.get_data("anti_cheat_logs") or []
    return {"data": logs}
