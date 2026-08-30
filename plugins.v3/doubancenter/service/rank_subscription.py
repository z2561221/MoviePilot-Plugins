"""豆瓣中心榜单订阅策略与运行编排服务。"""

import time
from typing import Any, Callable, Dict, List

from app.sdk.logging import logger

from ..adapter import rss as rss_adapter
from ..model import rank as rank_model
from .. import utils


def _normalize_regions_for_filter(value: Any) -> List[str]:
    """兼容旧测试宿主并统一榜单地区值。"""
    normalizer = getattr(utils, "normalize_region_values", None)
    if callable(normalizer):
        return normalizer(value)
    if isinstance(value, str):
        return [part for part in value.replace("/", " ").split() if part]
    if isinstance(value, (list, tuple, set)):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def _parse_regions_from_description(value: Any) -> List[str]:
    """兼容旧测试宿主并从描述提取地区。"""
    parser = getattr(utils, "parse_regions_from_description", None)
    return parser(value) if callable(parser) else []


def rank_config(rank_configs: Dict[str, dict], key: str) -> dict:
    """读取指定榜单的订阅配置。"""
    configs = rank_configs if isinstance(rank_configs, dict) else {}
    config = configs.get(key, {})
    return config if isinstance(config, dict) else {}


def rank_enabled(rank_configs: Dict[str, dict], key: str) -> bool:
    """判断指定榜单是否启用自动订阅。"""
    return bool(rank_config(rank_configs, key).get("enabled", False))


def rank_count(rank_configs: Dict[str, dict], key: str) -> int:
    """读取指定榜单的自动订阅候选数量。"""
    return int(rank_config(rank_configs, key).get("count", 0) or 0)


def _positive_value_text(value: Any) -> str:
    """返回正数配置的可读文本，非正数返回空字符串。"""
    if not rank_model.positive_number(value):
        return ""
    return str(value).strip()


def describe_rank_filter(
    config: dict,
    rank: dict,
    *,
    candidate_count: int = 0,
    blacklist_enabled: bool = False,
    observe_enabled: bool = False,
) -> str:
    """生成人类可读的榜单订阅筛选条件描述。"""
    config = config if isinstance(config, dict) else {}
    rank = rank if isinstance(rank, dict) else {}
    parts = [f"候选 {max(int(candidate_count or 0), 0)} 条"]
    date_mode = rank_model.rank_date_mode(rank)
    if rank.get("coming"):
        vote = _positive_value_text(config.get("vote"))
        wish = _positive_value_text(config.get("wish_count"))
        air_days = _positive_value_text(config.get("air_days"))
        if vote:
            parts.append(f"评分>={vote}")
        if wish:
            parts.append(f"想看>={wish}")
        if air_days:
            prefix = "未来上映" if date_mode == rank_model.DATE_MODE_FUTURE else "最近上映"
            parts.append(f"{prefix}<={air_days}天")
    else:
        vote = _positive_value_text(config.get("vote"))
        year = _positive_value_text(config.get("year"))
        air_days = _positive_value_text(config.get("air_days"))
        if vote:
            parts.append(f"评分>={vote}")
        if year:
            parts.append(f"年份>={year}")
        if air_days:
            prefix = "未来上映" if date_mode == rank_model.DATE_MODE_FUTURE else "最近上映"
            parts.append(f"{prefix}<={air_days}天")
    regions = _normalize_regions_for_filter(config.get("regions"))
    if regions:
        parts.append(f"地区={'/'.join(regions)}")
    if observe_enabled:
        parts.append("观察期")
    if blacklist_enabled:
        parts.append("黑名单")
    if len(parts) == 1:
        parts.append("无额外筛选")
    return "；".join(parts)


def has_global_filter(blacklist_keywords: str = "", observe_enabled: bool = False) -> bool:
    """判断是否配置了全局自动订阅安全条件。"""
    if (blacklist_keywords or "").strip():
        return True
    if observe_enabled:
        return True
    return False


def has_rank_filter(config: dict, rank: dict) -> bool:
    """判断单个榜单是否配置了自动订阅安全条件。"""
    config = config if isinstance(config, dict) else {}
    if int(config.get("count", 0) or 0) > 0:
        return True
    if _normalize_regions_for_filter(config.get("regions")):
        return True
    if (rank or {}).get("coming"):
        return (
            rank_model.positive_number(config.get("vote"))
            or rank_model.positive_number(config.get("wish_count"))
            or rank_model.positive_number(config.get("air_days"))
        )
    return (
        rank_model.positive_number(config.get("vote"))
        or rank_model.positive_number(config.get("year"))
        or rank_model.positive_number(config.get("air_days"))
    )


def region_filter_result(config: dict, item: dict = None, entry: dict = None, mediainfo: Any = None) -> tuple[bool, str]:
    """按榜单地区条件判断条目，未知地区时保守拒绝。"""
    config = config if isinstance(config, dict) else {}
    selected = _normalize_regions_for_filter(config.get("regions"))
    if not selected:
        return True, ""
    item = item if isinstance(item, dict) else {}
    entry = entry if isinstance(entry, dict) else {}
    values = _normalize_regions_for_filter(item.get("regions"))
    if not values:
        values = _normalize_regions_for_filter(entry.get("regions"))
    if not values:
        values = _parse_regions_from_description(item.get("description") or entry.get("description"))
    if not values:
        for key in ("regions", "countries", "origin_country", "production_countries", "country"):
            values = _normalize_regions_for_filter(getattr(mediainfo, key, None) if mediainfo is not None else None)
            if values:
                break
    selected_keys = {value.casefold() for value in selected}
    value_keys = {value.casefold() for value in values}
    if selected_keys & value_keys:
        return True, ""
    if not values:
        return False, "地区未知"
    return False, f"地区不匹配：{'/'.join(values)}"


def has_safety_filter(
    rank_configs: Dict[str, dict],
    ranks: List[dict],
    blacklist_keywords: str = "",
    observe_enabled: bool = False,
) -> bool:
    """判断当前配置是否足以安全执行自动订阅。"""
    if has_global_filter(blacklist_keywords=blacklist_keywords, observe_enabled=observe_enabled):
        return True
    return any(
        rank_enabled(rank_configs, rank.get("key", "")) and has_rank_filter(rank_config(rank_configs, rank.get("key", "")), rank)
        for rank in ranks
    )


def subscription_limits(rank_configs: Dict[str, dict], ranks: List[dict], unlimited_limit: int) -> Dict[str, int]:
    """生成运行周期每个启用榜单需要拉取的候选数量。"""
    limits: Dict[str, int] = {}
    for rank in ranks:
        key = rank["key"]
        if not rank_enabled(rank_configs, key):
            continue
        count = rank_count(rank_configs, key)
        limits[key] = max(5, count) if count > 0 else unlimited_limit
    return limits


def subscribe_ranks(
    plugin: Any,
    *,
    ranks: List[dict],
    safety_filter: Callable[[Any], bool],
    rank_enabled_callback: Callable[[Any, str], bool],
    rank_count_callback: Callable[[Any, str], int],
    process_coming: Callable[[Any, str, dict], None],
    process_general: Callable[[Any, str, dict], None],
    refresh_rank_data: Callable[[Any], Any],
    unlimited_limit: int,
    refresh_when_unsafe: bool = True,
) -> None:
    """按当前配置处理传统 RSS 订阅入口。"""
    if not safety_filter(plugin):
        logger.warning("豆瓣中心：未配置有效订阅筛选条件，跳过自动订阅，仅刷新榜单历史以避免误触发大量订阅")
        if refresh_when_unsafe:
            refresh_rank_data(plugin)
        return
    rsshub = utils.normalize_rss_domain(plugin._rsshub_domain)
    for rank in ranks:
        key = rank["key"]
        if not rank_enabled_callback(plugin, key):
            continue
        count = rank_count_callback(plugin, key)
        fetch_count = count if count > 0 else unlimited_limit
        url = rss_adapter.build_rsshub_url(rsshub, rank["route"], fetch_count)
        logger.info(f"豆瓣中心：开始处理 [{rank['name']}] {url}")
        processor = process_coming if rank["coming"] else process_general
        processor(plugin, url, rank)
        time.sleep(1)
    logger.info("豆瓣中心：榜单订阅刷新完成")


def subscribe_rank_snapshots(
    plugin: Any,
    rank_snapshots: Dict[str, dict],
    *,
    ranks: List[dict],
    safety_filter: Callable[[Any], bool],
    rank_enabled_callback: Callable[[Any, str], bool],
    rank_count_callback: Callable[[Any, str], int],
    rank_config_callback: Callable[[Any, str], dict],
    blacklist_enabled: Callable[[Any], bool],
    observe_enabled: Callable[[Any, str], bool],
    process_coming: Callable[..., None],
    process_general: Callable[..., None],
    emit_summary: Callable[[dict, str, List[str]], None],
) -> None:
    """使用本轮已识别快照执行自动订阅。"""
    if not safety_filter(plugin):
        logger.warning("豆瓣中心：未配置有效订阅筛选条件，本轮已刷新榜单展示，跳过自动订阅")
        return
    for rank in ranks:
        key = rank["key"]
        if not rank_enabled_callback(plugin, key):
            continue
        count = rank_count_callback(plugin, key)
        snapshots = ((rank_snapshots or {}).get(key) or {}).get("items") or []
        subscribe_items = snapshots if count <= 0 else snapshots[:count]
        description = describe_rank_filter(
            rank_config_callback(plugin, key),
            rank,
            candidate_count=len(subscribe_items),
            blacklist_enabled=blacklist_enabled(plugin),
            observe_enabled=observe_enabled(plugin, key),
        )
        result_lines: List[str] = []
        if not subscribe_items:
            result_lines.append("- 本轮没有可处理的订阅候选")
            emit_summary(rank, description, result_lines)
            continue
        processor = process_coming if rank["coming"] else process_general
        processor(plugin, subscribe_items, rank, result_lines=result_lines)
        emit_summary(rank, description, result_lines)
        time.sleep(1)
    logger.info("豆瓣中心：榜单订阅刷新完成")


def refresh_then_subscribe(
    plugin: Any,
    message: str,
    *,
    limit_by_rank: Callable[[Any], Dict[str, int]],
    refresh_rank_data: Callable[..., Any],
    subscribe_snapshots: Callable[[Any, Dict[str, dict]], None],
) -> None:
    """刷新榜单展示数据后，再按当前配置订阅已识别快照。"""
    logger.info(message)
    _, snapshots = refresh_rank_data(
        plugin,
        limit_by_rank=limit_by_rank(plugin),
        with_snapshots=True,
    )
    subscribe_snapshots(plugin, snapshots)
