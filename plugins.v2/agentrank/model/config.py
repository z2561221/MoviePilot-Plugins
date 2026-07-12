"""Agent榜单中心配置模型与校验。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Tuple


WEIGHT_DEFAULTS: Dict[str, float] = {
    "type_weight": 0.8,
    "theme_weight": 0.8,
    "actor_weight": 0.5,
    "director_weight": 0.4,
    "region_weight": 0.4,
    "year_weight": 0.3,
    "rating_weight": 0.7,
    "heat_weight": 0.6,
    "freshness_weight": 0.5,
    "similarity_weight": 0.8,
}

DISCOVERY_SOURCE_DEFAULTS: Dict[str, bool] = {
    "douban": True,
    "tmdb_movies": True,
    "tmdb_tv": True,
    "bangumi": True,
    "extensions": True,
}


class ConfigValidationError(ValueError):
    """表示配置包含一个或多个可见校验错误。"""

    def __init__(self, errors: List[str]):
        """保存全部错误，便于配置页一次展示。"""
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


@dataclass
class AgentRankConfig:
    """Agent榜单中心规范化配置。"""

    enabled: bool = False
    schedule_enabled: bool = False
    cron: str = "0 8 * * *"
    users: List[str] = field(default_factory=list)
    default_user: str = ""
    discovery_sources: Dict[str, bool] = field(
        default_factory=lambda: dict(DISCOVERY_SOURCE_DEFAULTS)
    )
    weights: Dict[str, float] = field(default_factory=lambda: dict(WEIGHT_DEFAULTS))
    media_types: List[str] = field(default_factory=lambda: ["movie", "tv", "anime"])
    profile_scope: str = "all"
    recent_days: int = 365
    subscription_sample_limit: int = 200
    minimum_samples: int = 5
    candidate_pool_size: int = 100
    confidence_threshold: float = 0.6
    exclude_keywords: List[str] = field(default_factory=list)
    action_mode: str = "notify"
    notify: bool = True
    auto_subscribe_top_n: int = 0
    auto_subscribe_limit: int = 10
    history_limit: int = 50
    profile_cache_enabled: bool = True
    rebuild_profile_each_run: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] = None) -> "AgentRankConfig":
        """严格校验映射并返回配置对象。"""
        config, errors = _coerce_config(value)
        if errors:
            raise ConfigValidationError(errors)
        return config

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化的独立字典。"""
        return asdict(self)


def _unique_strings(value: Any) -> List[str]:
    """将列表清洗为保持顺序的非空唯一字符串。"""
    if not isinstance(value, (list, tuple, set)):
        return []
    result: List[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _bounded_number(
    raw: Any,
    default: float,
    minimum: float,
    maximum: float,
    field_name: str,
    errors: List[str],
) -> float:
    """读取有界数值；无效时记录错误并回退默认值。"""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        errors.append(f"{field_name} must be a number between {minimum} and {maximum}")
        return default
    if not minimum <= value <= maximum:
        errors.append(f"{field_name} must be between {minimum} and {maximum}")
        return default
    return value


def _bounded_integer(
    raw: Any,
    default: int,
    minimum: int,
    maximum: int,
    field_name: str,
    errors: List[str],
) -> int:
    """读取有界整数；无效时记录错误并回退默认值。"""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        errors.append(f"{field_name} must be an integer between {minimum} and {maximum}")
        return default
    if not minimum <= value <= maximum:
        errors.append(f"{field_name} must be between {minimum} and {maximum}")
        return default
    return value


def _coerce_config(value: Mapping[str, Any] = None) -> Tuple[AgentRankConfig, List[str]]:
    """生成安全配置并同时返回全部校验错误。"""
    raw = dict(value) if isinstance(value, Mapping) else {}
    errors: List[str] = [] if value is None or isinstance(value, Mapping) else [
        "config must be a mapping"
    ]
    users = _unique_strings(raw.get("users", []))
    default_user = str(raw.get("default_user") or "").strip()
    if default_user and default_user not in users:
        errors.append("default_user must belong to users")

    raw_weights = raw.get("weights") if isinstance(raw.get("weights"), Mapping) else {}
    weights: Dict[str, float] = {}
    for name, default in WEIGHT_DEFAULTS.items():
        candidate = raw_weights.get(name, raw.get(name, default))
        weights[name] = _bounded_number(candidate, default, 0.0, 1.0, name, errors)

    raw_sources = raw.get("discovery_sources")
    source_values = raw_sources if isinstance(raw_sources, Mapping) else {}
    discovery_sources = {
        name: bool(source_values.get(name, default))
        for name, default in DISCOVERY_SOURCE_DEFAULTS.items()
    }

    media_types = _unique_strings(raw.get("media_types", ["movie", "tv", "anime"]))
    unsupported_types = sorted(set(media_types) - {"movie", "tv", "anime"})
    if unsupported_types or not media_types:
        errors.append("media_types must contain only movie, tv, or anime")
        media_types = ["movie", "tv", "anime"]

    profile_scope = str(raw.get("profile_scope") or "all")
    if profile_scope not in {"recent", "all"}:
        errors.append("profile_scope must be recent or all")
        profile_scope = "all"

    action_mode = str(raw.get("action_mode") or "notify")
    if action_mode not in {"update", "notify", "auto_subscribe"}:
        errors.append("action_mode must be update, notify, or auto_subscribe")
        action_mode = "notify"

    auto_limit = _bounded_integer(
        raw.get("auto_subscribe_limit", 10), 10, 0, 10, "auto_subscribe_limit", errors
    )
    auto_top_n = _bounded_integer(
        raw.get("auto_subscribe_top_n", 0), 0, 0, auto_limit, "auto_subscribe_top_n", errors
    )

    config = AgentRankConfig(
        enabled=bool(raw.get("enabled", False)),
        schedule_enabled=bool(raw.get("schedule_enabled", False)),
        cron=str(raw.get("cron") or "0 8 * * *").strip(),
        users=users,
        default_user=default_user,
        discovery_sources=discovery_sources,
        weights=weights,
        media_types=media_types,
        profile_scope=profile_scope,
        recent_days=_bounded_integer(
            raw.get("recent_days", 365), 365, 1, 3650, "recent_days", errors
        ),
        subscription_sample_limit=_bounded_integer(
            raw.get("subscription_sample_limit", 200),
            200,
            1,
            1000,
            "subscription_sample_limit",
            errors,
        ),
        minimum_samples=_bounded_integer(
            raw.get("minimum_samples", 5), 5, 1, 100, "minimum_samples", errors
        ),
        candidate_pool_size=_bounded_integer(
            raw.get("candidate_pool_size", 100),
            100,
            10,
            500,
            "candidate_pool_size",
            errors,
        ),
        confidence_threshold=_bounded_number(
            raw.get("confidence_threshold", 0.6),
            0.6,
            0.0,
            1.0,
            "confidence_threshold",
            errors,
        ),
        exclude_keywords=_unique_strings(raw.get("exclude_keywords", [])),
        action_mode=action_mode,
        notify=bool(raw.get("notify", True)),
        auto_subscribe_top_n=auto_top_n,
        auto_subscribe_limit=auto_limit,
        history_limit=_bounded_integer(
            raw.get("history_limit", 50), 50, 1, 200, "history_limit", errors
        ),
        profile_cache_enabled=bool(raw.get("profile_cache_enabled", True)),
        rebuild_profile_each_run=bool(raw.get("rebuild_profile_each_run", False)),
    )
    if not config.cron:
        errors.append("cron must not be empty")
        config.cron = "0 8 * * *"
    return config, errors


def default_config() -> Dict[str, Any]:
    """返回配置页使用的完整默认模型。"""
    return AgentRankConfig().to_dict()


def normalize_config(config: dict = None) -> Dict[str, Any]:
    """容错清洗插件配置并附带可见校验错误。"""
    normalized, errors = _coerce_config(config)
    result = normalized.to_dict()
    result["_validation_errors"] = errors
    return result
