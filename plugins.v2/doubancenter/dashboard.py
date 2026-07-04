"""
DoubanCenter - 仪表盘模块
"""
from typing import Any, Dict, List, Optional, Tuple

from app.chain.media import MediaChain
from app.core.metainfo import MetaInfo
from app.schemas.types import MediaType

from .service import archive as archive_service
from .service import dashboard_config as dashboard_config_service
from .service import dashboard_folio as dashboard_folio_service
from .service import dashboard_overview as dashboard_overview_service
from .service import dashboard_rank_history as dashboard_rank_history_service
from .service import dashboard_rank_media as dashboard_rank_media_service
from .service import dashboard_rank_subscription as dashboard_rank_subscription_service
from .service import dashboard_stats as dashboard_stats_service
from .service import dashboard_subscribe_history as dashboard_subscribe_history_service
from .service import observation as observation_service
from .storage import records as storage

DETAIL_SECTION_LIMIT = 5


def get_dashboard(self, key: str, **kwargs) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
    """返回仪表盘卡片的列配置与基础属性。"""
    cols = {"cols": 12, "md": 12}
    attrs = {"refresh": 600, "border": True, "title": "豆瓣中心", "subtitle": "追剧观影时间线"}
    return cols, attrs, None


def get_timeline_items(self, mobile: bool = False) -> List[dict]:
    """返回豆瓣时间线展示条目。"""
    return dashboard_folio_service.get_timeline_items(self, mobile=mobile, poster_resolver=_resolve_folio_poster)


def _resolve_folio_poster(item: dict) -> Optional[str]:
    """识别豆瓣时间线条目的海报地址。"""
    meta = MetaInfo(item.get("subject_name"))
    meta.type = MediaType("电视剧" if not item.get("type", "") else item.get("type"))
    media_info = MediaChain().recognize_media(meta=meta, mtype=meta.type, cache=True)
    return media_info.poster_path if media_info else None


def _fin(item, limit):
    """补齐月份标题统计并限制该月展示条数。"""
    return dashboard_folio_service.finish_timeline_item(item, limit)


def api_folio_data(self):
    """获取豆瓣时间数据，优先读自己的，没有则读原版豆瓣中心的。"""
    return dashboard_folio_service.get_folio_data(self)


def api_config(self):
    """返回前端运行配置补充数据。"""
    from .feed import BUILTIN_RANKS, _ren

    return {
        "data": dashboard_config_service.build_config(
            builtin_ranks=BUILTIN_RANKS,
            rank_enabled_checker=lambda key: _ren(self, key),
            folio_pc_month=self._folio_pc_month,
            folio_pc_num=self._folio_pc_num,
            folio_mobile_month=self._folio_mobile_month,
            folio_mobile_num=self._folio_mobile_num,
            dashboard_rank_keys=self._dashboard_rank_keys,
            blacklist_keywords=self._blacklist_keywords,
            observe_days=getattr(self, "_observe_days", 0),
            observe_rank_keys=getattr(self, "_observe_rank_keys", []),
        )
    }


def _dedupe_subscribe_records(records: list) -> tuple:
    """按状态、TMDB、标题、年份和榜单合并订阅历史。"""
    return dashboard_subscribe_history_service.dedupe_records(records)


def api_rank_history(self):
    """返回前端使用的榜单历史快照。"""
    from .feed import get_dashboard_rank_items
    return dashboard_rank_history_service.build_rank_history_response(
        self,
        lambda plugin, rank_key, limit=5: get_dashboard_rank_items(plugin, rank_key, limit=limit),
    )


def api_resolve_media_from_rank(self, media_type, title, year, tmdb_id=None, bangumi_id=None):
    """识别榜单条目并返回媒体信息。"""
    from .feed import _fetch_bangumi_subject, bangumi_subject_to_media_data

    return dashboard_rank_media_service.resolve_media_from_rank(
        self,
        media_type,
        title,
        year,
        tmdb_id=tmdb_id,
        bangumi_id=bangumi_id,
        bangumi_subject_fetcher=_fetch_bangumi_subject,
        bangumi_subject_converter=bangumi_subject_to_media_data,
    )


def api_subscribe_from_rank(self, tmdb_id, media_type, title, year, bangumi_id=None):
    """根据榜单条目发起订阅。"""
    from .feed import _bangumi_subject_title, _bangumi_subject_year, _fetch_bangumi_subject

    return dashboard_rank_subscription_service.subscribe_from_rank(
        self,
        tmdb_id,
        media_type,
        title,
        year,
        bangumi_id=bangumi_id,
        bangumi_subject_fetcher=_fetch_bangumi_subject,
        bangumi_subject_title=_bangumi_subject_title,
        bangumi_subject_year=_bangumi_subject_year,
    )


def _add_silent_subscription(sc, title, year, mt, tmdb_id=None, bangumi_id=None):
    """按 MP 默认订阅参数静默添加订阅。"""
    return dashboard_rank_subscription_service.add_silent_subscription(
        sc,
        title,
        year,
        mt,
        tmdb_id=tmdb_id,
        bangumi_id=bangumi_id,
    )


def api_stats(self):
    """订阅统计：基于 subscribe_records 统计"""
    from .feed import BUILTIN_RANKS

    records = storage.read_subscribe_records(self)
    records, changed = _dedupe_subscribe_records(records)
    if changed:
        storage.save_subscribe_records(self, records)
    return {"data": dashboard_stats_service.build_stats(records, BUILTIN_RANKS)}


def api_subscribe_history(self, page=1, page_size=20):
    """订阅历史：基于 subscribe_records 分页"""
    return {
        "data": dashboard_subscribe_history_service.paginate_subscribe_history(
            self,
            page=page,
            page_size=page_size,
            limit=DETAIL_SECTION_LIMIT,
        )
    }


def _item_existing_subscription(item: dict) -> bool:
    """判断条目是否已标记为订阅存在。"""
    return bool(
        isinstance(item, dict)
        and (item.get("existing") or item.get("existing_at"))
        and item.get("existing_reason") == "subscribe"
    )


def _observed_item_subscription_exists(item: dict, rank_key: str = "") -> bool:
    """检查观察队列条目是否已经存在订阅。"""
    return observation_service.observed_item_subscription_exists(item, rank_key=rank_key)


def _same_record(item: dict, unique: str = "", time: str = "", title: str = "", tmdbid: Any = None) -> bool:
    """按稳定字段判断是否为同一条详情页记录。"""
    return dashboard_subscribe_history_service.same_record(item, unique=unique, time=time, title=title, tmdbid=tmdbid)


def _archive_record_key(source: str, record: dict) -> tuple:
    """生成归档记录去重键。"""
    return archive_service.archive_record_key(source, record)


def _archive_record_score(record: dict) -> int:
    """计算归档原始记录的信息完整度。"""
    return archive_service.archive_record_score(record)


def _same_archive_record(source: str, left: dict, right: dict) -> bool:
    """按来源判断两条归档原始记录是否重复。"""
    return archive_service.same_archive_record(source, left, right)


def _update_archive_item_from_record(archive: dict, source: str, record: dict, source_name: str = "") -> dict:
    """用更完整的原始记录刷新归档展示字段。"""
    return archive_service.update_archive_item_from_record(archive, source, record, source_name)


def _dedupe_archive_records(archives: list) -> tuple:
    """压缩重复归档记录，保留信息更完整的一条。"""
    return archive_service.dedupe_archive_records(archives)


def _archive_record(self, source: str, record: dict, source_name: str = "", dedupe: bool = False) -> Optional[dict]:
    """将详情页删除的记录写入归档。"""
    return archive_service.archive_record(self, source, record, source_name, dedupe=dedupe)


def _detail_record_time(record: dict) -> str:
    """返回详情页记录用于新旧排序的时间字段。"""
    return archive_service.detail_record_time(record)


def _latest_detail_indexes(records: list, limit: int = DETAIL_SECTION_LIMIT) -> set:
    """按时间选出详情页应保留的最新记录下标。"""
    return archive_service.latest_detail_indexes(records, limit)


def _archive_detail_overflow(self, records: list, source: str, source_name: str, limit: int = DETAIL_SECTION_LIMIT) -> tuple:
    """保留最新详情记录，并将超出上限的条目写入归档。"""
    return archive_service.archive_detail_overflow(self, records, source, source_name, limit)


def _archive_anti_cheat_overflow(self, logs: list, limit: int = DETAIL_SECTION_LIMIT) -> tuple:
    """分别限制黑名拦截与观察日志的详情页展示数量。"""
    return archive_service.archive_anti_cheat_overflow(self, logs, limit)


def _anti_cheat_log_key(record: dict) -> tuple:
    """生成观察日志记录的去重键。"""
    return archive_service.anti_cheat_log_key(record)


def _remove_legacy_observation_completed_archives(self) -> bool:
    """将旧版观察完成归档迁回观察日志并从归档页移除。"""
    return archive_service.remove_legacy_observation_completed_archives(self)


def _remove_archive(self, archive_id: str) -> Optional[dict]:
    """从归档列表取出并删除一条归档记录。"""
    return archive_service.remove_archive(self, archive_id)


def api_delete_subscribe_history(self, time: str = "", title: str = "", tmdbid: Any = None):
    """删除一条豆瓣中心订阅历史记录。"""
    return dashboard_subscribe_history_service.delete_subscribe_history(
        self,
        time=time,
        title=title,
        tmdbid=tmdbid,
        archive_record_callback=_archive_record,
    )


def api_pending_observations(self):
    """获取观察期内等待自动订阅的榜单条目。"""
    if int(self._observe_days or 0) <= 0:
        return {"data": []}
    from .feed import BUILTIN_RANKS, get_rank_history_by_key
    return observation_service.pending_observations(
        self,
        ranks=BUILTIN_RANKS,
        rank_history_reader=lambda plugin, key: get_rank_history_by_key(plugin, key),
        item_existing_subscription_checker=_item_existing_subscription,
        observed_subscription_exists_checker=_observed_item_subscription_exists,
        archive_record_callback=_archive_record,
        limit=DETAIL_SECTION_LIMIT,
    )


def api_delete_observation(self, unique: str = "", rank_key: str = "", title: str = ""):
    """从观察队列删除条目，并标记为已忽略以避免再次自动进入队列。"""
    from .feed import BUILTIN_RANKS, get_rank_history_by_key
    return observation_service.delete_observation(
        self,
        unique=unique,
        rank_key=rank_key,
        title=title,
        ranks=BUILTIN_RANKS,
        rank_history_reader=lambda plugin, key: get_rank_history_by_key(plugin, key),
        archive_record_callback=_archive_record,
    )


def _dedupe_anti_cheat_logs(logs: list) -> tuple:
    """按原因、标题和详情合并观察日志。"""
    return observation_service.dedupe_anti_cheat_logs(logs)


def _finished_observation_titles(self) -> set:
    """收集已经结束观察的条目标题，用于清理观察日志。"""
    records = storage.read_subscribe_records(self)
    return observation_service.finished_observation_titles(
        subscribe_records=records,
        ranks=_rank_history_snapshots(self),
        existing_subscription_checker=_item_existing_subscription,
    )


def _observation_completion_log(item: dict, rank: dict) -> Optional[dict]:
    """从榜单历史构造观察完成日志。"""
    return observation_service.observation_completion_log(item, rank)


def _append_observation_completion_logs(self, logs: list) -> tuple:
    """补齐已订阅观察条目的观察完成日志。"""
    return observation_service.append_observation_completion_logs(
        logs,
        ranks=_rank_history_snapshots(self),
        archived_completion_titles=observation_service.archived_completion_titles(self),
    )


def _reconcile_anti_cheat_logs(self, logs: list) -> tuple:
    """合并并清理已结束观察项的观察日志。"""
    subscribe_records = storage.read_subscribe_records(self)
    return observation_service.reconcile_anti_cheat_logs(
        logs,
        subscribe_records=subscribe_records,
        ranks=_rank_history_snapshots(self),
        archived_completion_titles=observation_service.archived_completion_titles(self),
        existing_subscription_checker=_item_existing_subscription,
    )


def _rank_history_snapshots(self) -> list:
    """构造带历史数据的内置榜单快照。"""
    ranks = []
    try:
        from .feed import BUILTIN_RANKS, get_rank_history_by_key
        for rank in BUILTIN_RANKS:
            ranks.append({**rank, "history": get_rank_history_by_key(self, rank["key"])})
    except Exception:
        ranks = []
    return ranks


def api_anti_cheat_logs(self):
    """观察日志。"""
    return observation_service.list_anti_cheat_logs(
        self,
        ranks=_rank_history_snapshots(self),
        existing_subscription_checker=_item_existing_subscription,
        limit=DETAIL_SECTION_LIMIT,
    )


def api_overview(self):
    """返回设置页运行总览数据。"""
    from .feed import BUILTIN_RANKS, get_rank_history_by_key

    return dashboard_overview_service.build_overview_response(
        self,
        builtin_ranks=BUILTIN_RANKS,
        rank_history_reader=lambda plugin, key: get_rank_history_by_key(plugin, key),
        existing_subscription_checker=_item_existing_subscription,
    )


def api_archive_records(self, page: int = 1, page_size: int = 20):
    """返回详情页归档记录。"""
    return {"data": archive_service.paginate_archive_records(self, page, page_size)}


def api_restore_archive(self, archive_id: str = ""):
    """将归档记录恢复回原数据列表。"""
    return archive_service.restore_archive_record(self, archive_id, _same_record)


def api_delete_archive(self, archive_id: str = ""):
    """永久删除一条归档记录。"""
    return archive_service.delete_archive_record(self, archive_id)


def api_delete_anti_cheat_log(self, time: str = "", title: str = "", reason: str = ""):
    """删除一条观察日志记录。"""
    return observation_service.delete_anti_cheat_log(
        self,
        time=time,
        title=title,
        reason=reason,
        archive_record_callback=_archive_record,
    )
