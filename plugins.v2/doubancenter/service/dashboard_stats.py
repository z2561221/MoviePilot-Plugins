"""豆瓣中心仪表盘统计服务。"""

import datetime
from typing import Any, Dict, List, Optional


EXTRA_SUBSCRIPTION_RANK_NAMES = {
    "douban_wish": "豆瓣想看",
}


def build_stats(records: List[dict], builtin_ranks: List[dict], now: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """基于订阅记录聚合仪表盘统计数据。"""
    records = [record for record in records if isinstance(record, dict)]
    rank_names = {rank["key"]: rank["name"] for rank in builtin_ranks if isinstance(rank, dict) and "key" in rank}
    for rank_key, rank_name in EXTRA_SUBSCRIPTION_RANK_NAMES.items():
        if any(record.get("rank_key") == rank_key for record in records):
            rank_names[rank_key] = rank_name
    rank_dist = {rank_key: 0 for rank_key in rank_names}
    unknown_count = 0
    type_dist = {"电影": 0, "电视剧": 0}
    month_new = 0
    current = now or datetime.datetime.now()
    month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    for record in records:
        rank_key = record.get("rank_key") or "unknown"
        if rank_key in rank_dist:
            rank_dist[rank_key] += 1
        else:
            unknown_count += 1

        media_type = record.get("media_type", "")
        if media_type in type_dist:
            type_dist[media_type] += 1

        timestamp = record.get("time", "")
        if timestamp:
            try:
                if datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S") >= month_start:
                    month_new += 1
            except Exception:
                pass

    rank_stats = [
        {"key": rank_key, "name": rank_name, "count": rank_dist.get(rank_key, 0)}
        for rank_key, rank_name in rank_names.items()
    ]
    if unknown_count:
        rank_dist["unknown"] = unknown_count
        rank_stats.append({"key": "unknown", "name": "未归类", "count": unknown_count})

    return {
        "total": len(records),
        "rank_dist": rank_dist,
        "rank_stats": rank_stats,
        "type_dist": type_dist,
        "month_new": month_new,
    }
