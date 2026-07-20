"""Agent榜单中心配置模型与校验。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Tuple

from .identity import EmbyIdentity
from ..service.prompt import DEFAULT_AGENT_PROMPT, LEGACY_DEFAULT_AGENT_PROMPT


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
}

PLAYBACK_SOURCE_MODES = {"auto", "playback_reporting", "emby_native"}


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
    discovery_page_enabled: bool = True
    onlyonce: bool = False
    schedule_enabled: bool = False
    cron: str = "0 8 * * *"
    emby_identities: List[Dict[str, Any]] = field(default_factory=list)
    default_profile_id: str = ""
    discovery_sources: Dict[str, bool] = field(
        default_factory=lambda: dict(DISCOVERY_SOURCE_DEFAULTS)
    )
    weights: Dict[str, float] = field(default_factory=lambda: dict(WEIGHT_DEFAULTS))
    media_types: List[str] = field(default_factory=lambda: ["movie", "tv", "anime"])
    profile_scope: str = "all"
    recent_days: int = 365
    subscription_sample_limit: int = 200
    minimum_samples: int = 5
    candidate_pool_size: int = 50
    confidence_threshold: float = 0.6
    exclude_keywords: List[str] = field(default_factory=list)
    action_mode: str = "notify"
    notify: bool = True
    auto_subscribe_top_n: int = 0
    auto_subscribe_limit: int = 10
    history_limit: int = 50
    profile_cache_enabled: bool = True
    rebuild_profile_each_run: bool = False
    playback_enabled: bool = True
    playback_source_mode: str = "auto"
    playback_recent_days: int = 180
    playback_completion_threshold: float = 0.85
    playback_abandon_minutes: int = 20
    playback_cache_days: int = 7
    agent_prompt: str = DEFAULT_AGENT_PROMPT

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


def _bounded_text(
    raw: Any,
    default: str,
    maximum: int,
    field_name: str,
    errors: List[str],
) -> str:
    """读取非空限长文本；无效时记录错误并回退默认值。"""
    value = str(raw or "").strip()
    if not value:
        errors.append(f"{field_name} must not be empty")
        return default
    if len(value) > maximum:
        errors.append(f"{field_name} must not exceed {maximum} characters")
        return default
    return value


def _emby_identities(value: Any, errors: List[str]) -> List[Dict[str, Any]]:
    """校验并去重不含凭据的 Emby identity 配置。"""
    if value in (None, []):
        return []
    if not isinstance(value, (list, tuple)):
        errors.append("emby_identities must be a list")
        return []
    identities: List[Dict[str, Any]] = []
    seen = set()
    for index, item in enumerate(value):
        try:
            identity = EmbyIdentity.from_dict(item)
        except (TypeError, ValueError) as error:
            errors.append(f"emby_identities[{index}] is invalid: {error}")
            continue
        if identity.profile_id in seen:
            errors.append(
                f"emby_identities[{index}] duplicates profile_id {identity.profile_id}"
            )
            continue
        seen.add(identity.profile_id)
        identities.append(identity.to_dict())
    return identities


def configured_identities(config: Mapping[str, Any]) -> List[EmbyIdentity]:
    """从规范化配置返回有效 Emby identity 列表。"""
    errors: List[str] = []
    values = _emby_identities(
        config.get("emby_identities") if isinstance(config, Mapping) else [],
        errors,
    )
    return [EmbyIdentity.from_dict(value) for value in values]


def _coerce_config(value: Mapping[str, Any] = None) -> Tuple[AgentRankConfig, List[str]]:
    """生成安全配置并同时返回全部校验错误。"""
    raw = dict(value) if isinstance(value, Mapping) else {}
    if raw.get("agent_prompt") == LEGACY_DEFAULT_AGENT_PROMPT:
        raw["agent_prompt"] = DEFAULT_AGENT_PROMPT
    errors: List[str] = [] if value is None or isinstance(value, Mapping) else [
        "config must be a mapping"
    ]
    identities = _emby_identities(raw.get("emby_identities", []), errors)
    profile_ids = {str(item["profile_id"]) for item in identities}
    default_profile_id = str(raw.get("default_profile_id") or "").strip()
    if default_profile_id and default_profile_id not in profile_ids:
        errors.append("default_profile_id must belong to emby_identities")
    enabled = bool(raw.get("enabled", False))
    if enabled and not identities:
        errors.append("emby_identities must select at least one identity when enabled")
    if enabled and identities and not default_profile_id:
        errors.append("default_profile_id is required when enabled")

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

    playback_source_mode = str(raw.get("playback_source_mode") or "auto").strip()
    if playback_source_mode not in PLAYBACK_SOURCE_MODES:
        errors.append("playback_source_mode must be auto, playback_reporting, or emby_native")
        playback_source_mode = "auto"

    auto_limit = _bounded_integer(
        raw.get("auto_subscribe_limit", 10), 10, 0, 10, "auto_subscribe_limit", errors
    )
    auto_top_n = _bounded_integer(
        raw.get("auto_subscribe_top_n", 0), 0, 0, auto_limit, "auto_subscribe_top_n", errors
    )

    config = AgentRankConfig(
        enabled=enabled,
        discovery_page_enabled=bool(raw.get("discovery_page_enabled", True)),
        onlyonce=bool(raw.get("onlyonce", False)),
        schedule_enabled=bool(raw.get("schedule_enabled", False)),
        cron=str(raw.get("cron") or "0 8 * * *").strip(),
        emby_identities=identities,
        default_profile_id=default_profile_id,
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
            raw.get("candidate_pool_size", 50),
            50,
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
        playback_enabled=bool(raw.get("playback_enabled", True)),
        playback_source_mode=playback_source_mode,
        playback_recent_days=_bounded_integer(
            raw.get("playback_recent_days", 180), 180, 1, 3650, "playback_recent_days", errors
        ),
        playback_completion_threshold=_bounded_number(
            raw.get("playback_completion_threshold", 0.85),
            0.85,
            0.5,
            1.0,
            "playback_completion_threshold",
            errors,
        ),
        playback_abandon_minutes=_bounded_integer(
            raw.get("playback_abandon_minutes", 20), 20, 1, 240, "playback_abandon_minutes", errors
        ),
        playback_cache_days=_bounded_integer(
            raw.get("playback_cache_days", 7), 7, 1, 30, "playback_cache_days", errors
        ),
        agent_prompt=_bounded_text(
            raw.get("agent_prompt", DEFAULT_AGENT_PROMPT),
            DEFAULT_AGENT_PROMPT,
            4000,
            "agent_prompt",
            errors,
        ),
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
