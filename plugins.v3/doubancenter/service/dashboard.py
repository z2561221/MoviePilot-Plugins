"""
DoubanCenter - 仪表盘模块
"""
from typing import Any, Optional

from app.chain.media import MediaChain
from app.schemas.types import MediaType
from app.sdk.media import MetaInfo

from ..model.identity import identity_from_media
from ..storage import records as storage
from . import archive as archive_service
from . import dashboard_config as dashboard_config_service
from . import dashboard_folio as dashboard_folio_service
from . import dashboard_overview as dashboard_overview_service
from . import dashboard_rank_history as dashboard_rank_history_service
from . import dashboard_rank_media as dashboard_rank_media_service
from . import dashboard_rank_subscription as dashboard_rank_subscription_service
from . import dashboard_stats as dashboard_stats_service
from . import dashboard_subscribe_history as dashboard_subscribe_history_service
from . import observation as observation_service

DETAIL_SECTION_LIMIT = 5

# 与已拆分领域函数完全同形的旧符号仅保留别名。
_fin = dashboard_folio_service.finish_timeline_item
_dedupe_subscribe_records = dashboard_subscribe_history_service.dedupe_records
_observed_item_subscription_exists = observation_service.observed_item_subscription_exists
_same_record = dashboard_subscribe_history_service.same_record
_archive_record_key = archive_service.archive_record_key
_archive_record_score = archive_service.archive_record_score
_same_archive_record = archive_service.same_archive_record
_update_archive_item_from_record = archive_service.update_archive_item_from_record
_dedupe_archive_records = archive_service.dedupe_archive_records
_archive_record = archive_service.archive_record
_detail_record_time = archive_service.detail_record_time
_latest_detail_indexes = archive_service.latest_detail_indexes
_archive_detail_overflow = archive_service.archive_detail_overflow
_archive_anti_cheat_overflow = archive_service.archive_anti_cheat_overflow
_anti_cheat_log_key = archive_service.anti_cheat_log_key
_remove_legacy_observation_completed_archives = archive_service.remove_legacy_observation_completed_archives
_remove_archive = archive_service.remove_archive
_dedupe_anti_cheat_logs = observation_service.dedupe_anti_cheat_logs
_observation_completion_log = observation_service.observation_completion_log


def get_dashboard(self, key: str, **kwargs) -> Optional[tuple[dict[str, Any], dict[str, Any], list[dict]]]:
    """返回仪表盘卡片的列配置与基础属性。"""
    cols = {"cols": 12, "md": 12}
    attrs = {"refresh": 600, "border": True, "title": "豆瓣中心", "subtitle": "追剧观影时间线"}
    return cols, attrs, None


def get_timeline_items(self, mobile: bool = False) -> list[dict]:
    """返回豆瓣时间线展示条目。"""
    return dashboard_folio_service.get_timeline_items(self, mobile=mobile, poster_resolver=_resolve_folio_poster)


def _resolve_folio_poster(item: dict) -> Optional[str]:
    """识别豆瓣时间线条目的海报地址。"""
    meta = MetaInfo(item.get("subject_name"))
    meta.type = MediaType("电视剧" if not item.get("type", "") else item.get("type"))
    source, media_id = identity_from_media(item)
    if source and media_id:
        media_info = MediaChain().recognize_media(
            meta=meta,
            mtype=meta.type,
            media_source=source,
            media_id=media_id,
            cache=True,
        )
    else:
        media_info = MediaChain().recognize_media(meta=meta, mtype=meta.type, cache=True)
    return media_info.poster_path if media_info else None


def api_config(self):
    """返回前端运行配置补充数据。"""
    from .rank_pipeline import _ren, get_rank_definitions

    ranks = get_rank_definitions(self)

    return {
        "data": dashboard_config_service.build_config(
            builtin_ranks=ranks,
            custom_ranks=getattr(self, "_custom_ranks", []),
            rank_enabled_checker=lambda key: _ren(self, key),
            dashboard_rank_keys=self._dashboard_rank_keys,
            blacklist_keywords=self._blacklist_keywords,
            observe_days=getattr(self, "_observe_days", 0),
            observe_rank_keys=getattr(self, "_observe_rank_keys", []),
            wish_enabled=getattr(self, "_wish_enabled", False),
            wish_cron=getattr(self, "_wish_cron", ""),
            wish_user=getattr(self, "_wish_user", ""),
            wish_notify=getattr(self, "_wish_notify", False),
            wish_onlyonce=getattr(self, "_wish_onlyonce", False),
            wish_max_pages=getattr(self, "_wish_max_pages", 1),
            wish_days=getattr(self, "_wish_days", 7),
            wish_state=storage.read_folio_wish_state(self),
            wish_queue=storage.read_folio_wish_queue(self),
            wish_processed=storage.read_folio_wish_processed(self),
            wish_failed=storage.read_folio_wish_failed(self),
        )
    }


def api_rank_history(self):
    """返回前端使用的榜单历史快照。"""
    from .rank_pipeline import get_dashboard_rank_items
    return dashboard_rank_history_service.build_rank_history_response(
        self,
        lambda plugin, rank_key, limit=5: get_dashboard_rank_items(plugin, rank_key, limit=limit),
    )


def api_resolve_media_from_rank(
    self,
    media_type,
    title,
    year,
    tmdb_id=None,
    bangumi_id=None,
    media_source=None,
    media_id=None,
    season=None,
):
    """识别榜单条目并返回媒体信息。"""
    from .rank_pipeline import _fetch_bangumi_subject, bangumi_subject_to_media_data

    return dashboard_rank_media_service.resolve_media_from_rank(
        self,
        media_type,
        title,
        year,
        tmdb_id=tmdb_id,
        bangumi_id=bangumi_id,
        media_source=media_source,
        media_id=media_id,
        season=season,
        bangumi_subject_fetcher=_fetch_bangumi_subject,
        bangumi_subject_converter=bangumi_subject_to_media_data,
    )


def api_subscribe_from_rank(
    self,
    tmdb_id,
    media_type,
    title,
    year,
    bangumi_id=None,
    media_source=None,
    media_id=None,
    rank_key="",
    rank_name="",
    source_link="",
    season=None,
    with_result=False,
):
    """根据榜单条目发起订阅。"""
    from .rank_pipeline import (
        _bangumi_subject_title,
        _bangumi_subject_year,
        _fetch_bangumi_subject,
    )

    return dashboard_rank_subscription_service.subscribe_from_rank(
        self,
        tmdb_id,
        media_type,
        title,
        year,
        bangumi_id=bangumi_id,
        media_source=media_source,
        media_id=media_id,
        bangumi_subject_fetcher=_fetch_bangumi_subject,
        bangumi_subject_title=_bangumi_subject_title,
        bangumi_subject_year=_bangumi_subject_year,
        rank_key=rank_key,
        rank_name=rank_name,
        source_link=source_link,
        season=season,
        **({"with_result": True} if with_result else {}),
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


def maintain_records(self):
    """初始化时治理旧记录，后续写入直接批量归档，页面查询保持只读。"""
    archive_service.remove_legacy_observation_completed_archives(self)
    records = storage.read_subscribe_records(self)
    deduped, changed = _dedupe_subscribe_records(records)
    if changed or len(deduped) > DETAIL_SECTION_LIMIT:
        deduped, _ = archive_service.archive_detail_overflow(self, deduped, "subscribe_history", "订阅历史")
        storage.save_subscribe_records(self, deduped)
    archives = storage.read_archive_records(self)
    normalized = [archive_service.normalize_archive_item(item) for item in archives if isinstance(item, dict)]
    deduped, changed = archive_service.dedupe_archive_records(normalized)
    if changed or normalized != archives:
        storage.save_archive_records(self, deduped)


def api_stats(self):
    """订阅统计：基于 subscribe_records 统计"""
    from .rank_pipeline import get_rank_definitions

    records = storage.read_subscribe_records(self)
    records, _ = _dedupe_subscribe_records(records)
    return {"data": dashboard_stats_service.build_stats(records, get_rank_definitions(self))}


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


def api_delete_subscribe_history(
    self,
    time: str = "",
    title: str = "",
    tmdbid: Any = None,
    media_source: Any = None,
    media_id: Any = None,
):
    """删除一条豆瓣中心订阅历史记录。"""
    return dashboard_subscribe_history_service.delete_subscribe_history(
        self,
        time=time,
        title=title,
        tmdbid=tmdbid,
        media_source=media_source,
        media_id=media_id,
        archive_record_callback=_archive_record,
    )


def api_pending_observations(self):
    """获取观察期内等待自动订阅的榜单条目。"""
    if int(self._observe_days or 0) <= 0:
        return {"data": []}
    from .rank_pipeline import get_rank_definitions, get_rank_history_by_key
    return observation_service.pending_observations(
        self,
        ranks=get_rank_definitions(self),
        rank_history_reader=lambda plugin, key: get_rank_history_by_key(plugin, key),
        item_existing_subscription_checker=_item_existing_subscription,
        observed_subscription_exists_checker=_observed_item_subscription_exists,
        archive_record_callback=_archive_record,
        limit=DETAIL_SECTION_LIMIT,
        read_only=True,
    )


def api_delete_observation(self, unique: str = "", rank_key: str = "", title: str = ""):
    """从观察队列删除条目，并标记为已忽略以避免再次自动进入队列。"""
    from .rank_pipeline import get_rank_definitions, get_rank_history_by_key
    return observation_service.delete_observation(
        self,
        unique=unique,
        rank_key=rank_key,
        title=title,
        ranks=get_rank_definitions(self),
        rank_history_reader=lambda plugin, key: get_rank_history_by_key(plugin, key),
        archive_record_callback=_archive_record,
    )


def _finished_observation_titles(self) -> set:
    """收集已经结束观察的条目标题，用于清理观察日志。"""
    records = storage.read_subscribe_records(self)
    return observation_service.finished_observation_titles(
        subscribe_records=records,
        ranks=_rank_history_snapshots(self),
        existing_subscription_checker=_item_existing_subscription,
    )


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
    """构造带历史数据的有效榜单快照。"""
    ranks = []
    try:
        from .rank_pipeline import get_rank_definitions, get_rank_history_by_key
        for rank in get_rank_definitions(self):
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
        read_only=True,
    )


def api_overview(self):
    """返回设置页运行总览数据。"""
    from .rank_pipeline import get_rank_definitions, get_rank_history_by_key

    return dashboard_overview_service.build_overview_response(
        self,
        builtin_ranks=get_rank_definitions(self),
        rank_history_reader=lambda plugin, key: get_rank_history_by_key(plugin, key),
        existing_subscription_checker=_item_existing_subscription,
    )


def api_archive_records(self, page: int = 1, page_size: int = 20):
    """返回详情页归档记录。"""
    return {"data": archive_service.paginate_archive_records(self, page, page_size)}


def api_restore_archive(self, archive_id: str = ""):
    """将归档记录恢复回原数据列表。"""
    return archive_service.restore_archive_record(self, archive_id, _same_record)


def api_delete_anti_cheat_log(self, time: str = "", title: str = "", reason: str = ""):
    """删除一条观察日志记录。"""
    return observation_service.delete_anti_cheat_log(
        self,
        time=time,
        title=title,
        reason=reason,
        archive_record_callback=_archive_record,
    )


def api_folio_data(self, raw: bool = False):
    """适配控制层的self命名参数，业务委托给时间线服务。"""
    return dashboard_folio_service.get_folio_data(self, raw=raw)


def api_delete_archive(self, archive_id: str = ""):
    """适配控制层的self命名参数，业务委托给归档服务。"""
    return archive_service.delete_archive_record(self, archive_id)
