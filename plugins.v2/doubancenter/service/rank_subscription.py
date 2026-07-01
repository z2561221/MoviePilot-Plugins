"""豆瓣中心榜单订阅策略服务。"""

from typing import Any, Dict, List

from ..model import rank as rank_model


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
    if (rank or {}).get("coming"):
        return rank_model.positive_number(config.get("wish_count")) or rank_model.positive_number(config.get("air_days"))
    return rank_model.positive_number(config.get("vote")) or rank_model.positive_number(config.get("year"))


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
