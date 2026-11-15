"""
DoubanCenter - 榜单订阅引擎
"""
from typing import Any, Optional

from app.sdk.logging import logger

from .. import utils as _utils_module
from ..adapter import rss as rss_adapter
from ..model import rank as rank_model
from ..storage import records as storage
from . import lifecycle
from . import observation as observation_service
from . import rank_candidates as _rank_candidates_compat
from . import rank_media as _rank_media_compat
from . import rank_recognition as rank_recognition_service
from . import rank_refresh as rank_refresh_service
from . import rank_snapshot as rank_snapshot_service
from . import rank_subscription as rank_subscription_service
from . import subscription as subscription_service

utils = _utils_module

# 旧符号是领域实现的直接别名，不承载额外流程。
_add_sub = _rank_candidates_compat._add_sub
_blacklist_description = _rank_candidates_compat._blacklist_description
_check_blacklist = _rank_candidates_compat._check_blacklist
_check_observe = _rank_candidates_compat._check_observe
_check_rank_region = _rank_candidates_compat._check_rank_region
_cleanup_observe_logs = _rank_candidates_compat._cleanup_observe_logs
_drop_stale_observations = _rank_candidates_compat._drop_stale_observations
_fetch_coming_rss = _rank_candidates_compat._fetch_coming_rss
_fetch_rss = _rank_candidates_compat._fetch_rss
_is_existing_media = _rank_candidates_compat._is_existing_media
_log_anti_cheat = _rank_candidates_compat._log_anti_cheat
_log_rank_skip = _rank_candidates_compat._log_rank_skip
_match_blacklist_line = _rank_candidates_compat._match_blacklist_line
_process_coming = _rank_candidates_compat._process_coming
_process_coming_snapshots = _rank_candidates_compat._process_coming_snapshots
_process_general = _rank_candidates_compat._process_general
_process_general_snapshots = _rank_candidates_compat._process_general_snapshots
_process_items = _rank_candidates_compat._process_items
_rc = _rank_candidates_compat._rc
_record_existing_history = _rank_candidates_compat._record_existing_history
_snapshot_media_type = _rank_candidates_compat._snapshot_media_type
_snapshot_meta = _rank_candidates_compat._snapshot_meta
_snapshot_poster = _rank_candidates_compat._snapshot_poster
_apply_bangumi_media = _rank_media_compat._apply_bangumi_media
_apply_bangumi_recognition = _rank_media_compat._apply_bangumi_recognition
_apply_bangumi_subject = _rank_media_compat._apply_bangumi_subject
_apply_display_recognition = _rank_media_compat._apply_display_recognition
_bangumi_history_repair_candidates = _rank_media_compat._bangumi_history_repair_candidates
_bangumi_subject_poster = _rank_media_compat._bangumi_subject_poster
_bangumi_subject_title = _rank_media_compat._bangumi_subject_title
_bangumi_subject_year = _rank_media_compat._bangumi_subject_year
_existing_bangumi_tmdb_identity = _rank_media_compat._existing_bangumi_tmdb_identity
_existing_tmdb_identity = _rank_media_compat._existing_tmdb_identity
_extract_bangumi_id = _rank_media_compat._extract_bangumi_id
_fetch_bangumi_subject = _rank_media_compat._fetch_bangumi_subject
_has_cjk_text = _rank_media_compat._has_cjk_text
_is_complete_bangumi_history_item = _rank_media_compat._is_complete_bangumi_history_item
_normalize_region_values = _rank_media_compat._normalize_region_values
_preferred_douban_display_title = _rank_media_compat._preferred_douban_display_title
_preserve_existing_tmdb_identity = _rank_media_compat._preserve_existing_tmdb_identity
_rank_media_type = _rank_media_compat._rank_media_type
_recognize_bangumi_media = _rank_media_compat._recognize_bangumi_media
_record_bangumi_id = _rank_media_compat._record_bangumi_id
_record_douban_id = _rank_media_compat._record_douban_id
_resolved_media_type_name = _rank_media_compat._resolved_media_type_name
bangumi_subject_to_media_data = _rank_media_compat.bangumi_subject_to_media_data
normalize_bangumi_history = _rank_media_compat.normalize_bangumi_history


# 旧函数导出兼容；核心识别的实际依赖只位于rank_media。

RANK_HISTORY_LIMIT = 500
UNLIMITED_RANK_FETCH_LIMIT = 50
DEFAULT_OBSERVE_RANK_KEYS = rank_model.DEFAULT_OBSERVE_RANK_KEYS
BUILTIN_RANKS: list[dict[str, Any]] = rank_model.BUILTIN_RANKS


def get_rank_definitions(plugin) -> list[dict[str, Any]]:
    """返回当前插件配置下的有效榜单集合。"""
    return rank_model.effective_ranks(getattr(plugin, "_custom_ranks", []))


def _trim_history(history: list[dict], limit: int = RANK_HISTORY_LIMIT) -> list[dict]:
    """裁剪榜单历史，只保留最新条目。"""
    return storage.trim_records(history, limit)


def _custom_rank_history_key(source: str) -> str:
    """为自定义 RSS 生成跨进程稳定的历史数据键。"""
    return storage.custom_rank_history_key(source)


def _recognize_rss_item(self, item: dict, rank: dict):
    """兼容RSS识别入口，识别依赖由所属服务负责。"""
    return rank_recognition_service.recognize_rss_item(self, item, rank)


def _rss_default_media_type(addr: str) -> str:
    """根据 RSS 地址推断默认媒体类型。"""
    return rss_adapter.default_media_type(addr)


def _record_history_item(history: list[dict], entry: dict) -> None:
    """更新或插入榜单历史条目，并原位替换观察占位。"""
    rank_model.record_history_item(history, entry)


def _history_item_subscribed(item: dict) -> bool:
    """判断历史条目是否已经产生过订阅。"""
    return subscription_service.history_item_subscribed(item)


def _history_item_existing(item: dict) -> bool:
    """判断历史条目是否已确认存在订阅。"""
    return subscription_service.history_item_existing(item)


def _history_index_by_unique(history: list[dict]) -> dict[str, dict]:
    """按唯一标识构建榜单历史索引。"""
    return subscription_service.history_index_by_unique(history)


# 订阅过滤与观察期工具函数


def default_observe_rank_keys() -> list[str]:
    """返回默认启用观察期的波动榜单。"""
    return observation_service.default_observe_rank_keys()


def _rank_observe_enabled(self, rank_key: str = "") -> bool:
    """判断指定榜单是否启用观察期。"""
    return observation_service.rank_observe_enabled(self, rank_key)


def _ren(self, key: str) -> bool:
    """判断指定榜单是否启用自动订阅。"""
    return rank_subscription_service.rank_enabled(self._rank_configs, key)


def _rcount(self, key: str) -> int:
    """读取指定榜单的自动订阅候选数量。"""
    return rank_subscription_service.rank_count(self._rank_configs, key)


def _positive_number(value: Any) -> bool:
    """判断值是否能解析为正数。"""
    return rank_model.positive_number(value)


def _year_below_min(value: Any, min_year: int) -> bool:
    """判断年份是否低于最低年份筛选条件。"""
    return rank_model.year_below_min(value, min_year)


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


def _subscription_limit_by_rank(self) -> dict[str, int]:
    """生成运行周期每个启用榜单需要拉取的候选数量。"""
    return rank_subscription_service.subscription_limits(
        self._rank_configs,
        get_rank_definitions(self),
        UNLIMITED_RANK_FETCH_LIMIT,
    )


def _blacklist_enabled(self) -> bool:
    """判断当前是否启用了黑名单筛选。"""
    return bool((getattr(self, "_blacklist_keywords", "") or "").strip())


def _emit_rank_subscription_summary(rd: dict, description: str, result_lines: list[str]) -> None:
    """输出单个榜单的订阅筛选摘要。"""
    rank_name = (rd or {}).get("name") or (rd or {}).get("key") or "榜单"
    lines = [
        f"豆瓣中心：[{rank_name}] 订阅筛选完成",
        f"筛选条件：{description}",
        "处理结果：",
    ]
    lines.extend(result_lines or ["- 无订阅动作"])
    logger.info("\n".join(lines))


def subscribe_to_rank_snapshots(self, rank_snapshots: dict[str, dict]) -> None:
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


def _refresh_then_subscribe(self, message: str) -> None:
    """刷新榜单展示数据后，再按当前订阅配置执行订阅。"""
    rank_subscription_service.refresh_then_subscribe(
        self,
        message,
        limit_by_rank=_subscription_limit_by_rank,
        refresh_rank_data=refresh_rank_data,
        subscribe_snapshots=subscribe_to_rank_snapshots,
    )


@lifecycle.managed
def run_once(self) -> None:
    """立即刷新榜单数据，并按当前订阅配置执行订阅。"""
    _refresh_then_subscribe(self, "豆瓣中心：立即运行开始，先刷新 RSS 榜单，再按配置执行订阅")


@lifecycle.managed
def run_scheduled(self) -> None:
    """定时刷新榜单数据，并按当前订阅配置执行订阅。"""
    _refresh_then_subscribe(self, "豆瓣中心：定时运行开始，先刷新 RSS 榜单，再按配置执行订阅")


def _write_subscribe_record(self, mediainfo, rank_key: str = "", rank_name: str = "", status: str = "success", reason: str = "", source_link: str = "") -> None:
    """写入自动订阅历史记录。"""
    subscription_service.write_subscribe_record(self, mediainfo, rank_key=rank_key, rank_name=rank_name, status=status, reason=reason, source_link=source_link)


def get_enabled_rank_keys(self) -> list[str]:
    """返回当前配置中启用的榜单 key。"""
    return [rd["key"] for rd in get_rank_definitions(self) if _ren(self, rd["key"])]


def get_rank_history_by_key(self, rank_key: str) -> list[dict]:
    """只读指定榜单历史，不在页面读取阶段执行媒体识别。"""
    return storage.read_rank_history(self, rank_key)


def _dashboard_rank_sort_key(item: dict) -> tuple:
    """生成仪表盘榜单排序键。"""
    return rank_refresh_service.dashboard_rank_sort_key(item)


def get_dashboard_rank_items(self, rank_key: str, limit: int = 5) -> list[dict]:
    """返回最新 RSS 批次中的仪表盘榜单条目。"""
    history = get_rank_history_by_key(self, rank_key)
    return rank_refresh_service.dashboard_rank_items(history, limit=limit)


def refresh_rank_data(self, rank_keys=None, limit_by_rank: Optional[dict[str, int]] = None, with_snapshots: bool = False):
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


def _recognize_snapshot_item(self, rank_key, item, entry, rd, existing):
    """兼容快照识别入口。"""
    return rank_recognition_service.recognize_snapshot_item(self, rank_key, item, entry, rd, existing)


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
    """兼容旧刷新入口，统一使用快照合并。"""
    items = _fetch_coming_rss(self, url)
    if items:
        return _merge_rank_items(self, rd["key"], items, rd)


def _refresh_general(self, url, rd):
    """兼容旧刷新入口，统一使用快照合并。"""
    items = _fetch_rss(self, url)
    if items:
        return _merge_rank_items(self, rd["key"], items, rd)
