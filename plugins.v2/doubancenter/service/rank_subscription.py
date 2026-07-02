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
    if rank.get("coming"):
        wish = _positive_value_text(config.get("wish_count"))
        air_days = _positive_value_text(config.get("air_days"))
        if wish:
            parts.append(f"想看>={wish}")
        if air_days:
            parts.append(f"上映<={air_days}天")
    else:
        vote = _positive_value_text(config.get("vote"))
        year = _positive_value_text(config.get("year"))
        if vote:
            parts.append(f"评分>={vote}")
        if year:
            parts.append(f"年份>={year}")
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
