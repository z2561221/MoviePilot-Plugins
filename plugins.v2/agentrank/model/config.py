"""Agent榜单中心配置模型与校验。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .identity import EmbyIdentity
from ..service.prompt import (
    DEFAULT_AGENT_PROMPT,
    DEFAULT_COPY_PROMPT,
    DEFAULT_CRITIC_PROMPT,
    DEFAULT_PROFILE_PROMPT,
    DEFAULT_RANKING_PROMPT,
    LEGACY_DEFAULT_AGENT_PROMPT,
    LEGACY_PLAYBACK_DEFAULT_AGENT_PROMPT,
    LEGACY_SUBSCRIPTION_DEFAULT_AGENT_PROMPT,
)


WEIGHT_DEFAULTS: Dict[str, float] = {
    "type_weight": 0.8,
    "theme_weight": 0.8,
    "actor_weight": 0.5,
    "director_weight": 0.4,
    "region_weight": 0.4,
    "year_weight": 0.9,
    "rating_weight": 0.9,
    "heat_weight": 0.9,
    "freshness_weight": 0.9,
    "similarity_weight": 0.9,
}

DISCOVERY_SOURCE_DEFAULTS: Dict[str, bool] = {
    "douban": True,
    "tmdb_movies": True,
    "tmdb_tv": True,
    "bangumi": True,
    "anilist": True,
}

NOTIFICATION_TYPE_NAMES = {
    "Download",
    "Organize",
    "Subscribe",
    "SiteMessage",
    "MediaServer",
    "Manual",
    "Plugin",
    "Agent",
    "Other",
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
    discovery_page_enabled: bool = True
    onlyonce: bool = False
    schedule_enabled: bool = True
    cron: str = "5 18 * * *"
    emby_identities: List[Dict[str, Any]] = field(default_factory=list)
    default_profile_id: str = ""
    profile_access_map: Dict[str, List[str]] = field(default_factory=dict)
    emby_library_ids: Optional[Dict[str, List[str]]] = None
    discovery_sources: Dict[str, bool] = field(
        default_factory=lambda: dict(DISCOVERY_SOURCE_DEFAULTS)
    )
    weights: Dict[str, float] = field(default_factory=lambda: dict(WEIGHT_DEFAULTS))
    minimum_samples: int = 5
    candidate_pool_size: int = 100
    confidence_threshold: float = 0.6
    action_mode: str = "notify"
    notify: bool = True
    notification_type: str = "Plugin"
    auto_subscribe_top_n: int = 0
    auto_subscribe_limit: int = 10
    history_limit: int = 50
    candidate_snapshot_limit: int = 20
    feedback_event_limit: int = 1000
    feedback_queue_limit: int = 200
    conversation_message_limit: int = 200
    attribution_record_limit: int = 500
    analysis_record_limit: int = 500
    profile_cache_enabled: bool = True
    rebuild_profile_each_run: bool = False
    playback_enabled: bool = True
    playback_recent_days: int = 90
    playback_completion_threshold: float = 0.85
    playback_abandon_minutes: int = 20
    playback_cache_days: int = 7
    profile_prompt: str = DEFAULT_PROFILE_PROMPT
    ranking_prompt: str = DEFAULT_RANKING_PROMPT
    copy_prompt: str = DEFAULT_COPY_PROMPT
    critic_prompt: str = DEFAULT_CRITIC_PROMPT

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


def _emby_library_ids(
    value: Any, profile_ids: set, errors: List[str]
) -> Optional[Dict[str, List[str]]]:
    """清洗按画像身份保存的 Emby 内容库选择；None 表示兼容旧配置的全部库。"""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        errors.append("emby_library_ids must be a mapping")
        return None
    result: Dict[str, List[str]] = {}
    for raw_profile_id, raw_ids in value.items():
        profile_id = str(raw_profile_id or "").strip()
        if profile_id not in profile_ids:
            continue
        if not isinstance(raw_ids, (list, tuple, set)):
            errors.append(f"emby_library_ids[{profile_id}] must be a list")
            continue
        result[profile_id] = _unique_strings(raw_ids)
    return result


def _profile_access_map(
    value: Any, profile_ids: set, errors: List[str]
) -> Dict[str, List[str]]:
    """清洗 MP 用户 ID 到已配置 Emby 画像身份的显式授权映射。"""
    if value in (None, {}):
        return {}
    if not isinstance(value, Mapping):
        errors.append("profile_access_map must be a mapping")
        return {}
    result: Dict[str, List[str]] = {}
    for raw_user_id, raw_profile_ids in value.items():
        try:
            user_id = str(int(str(raw_user_id).strip()))
        except (TypeError, ValueError):
            errors.append("profile_access_map keys must be positive MoviePilot user ids")
            continue
        if int(user_id) <= 0:
            errors.append("profile_access_map keys must be positive MoviePilot user ids")
            continue
        if not isinstance(raw_profile_ids, (list, tuple, set)):
            errors.append(f"profile_access_map[{user_id}] must be a list")
            continue
        requested = _unique_strings(raw_profile_ids)
        unknown = [profile_id for profile_id in requested if profile_id not in profile_ids]
        if unknown:
            errors.append(
                f"profile_access_map[{user_id}] contains unknown profile ids: "
                + ", ".join(unknown)
            )
        allowed = [profile_id for profile_id in requested if profile_id in profile_ids]
        if allowed:
            result[user_id] = allowed
    return result


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
    legacy_prompt = str(raw.get("agent_prompt") or "").strip()
    legacy_is_default = legacy_prompt in (
        DEFAULT_AGENT_PROMPT,
        LEGACY_DEFAULT_AGENT_PROMPT,
        LEGACY_PLAYBACK_DEFAULT_AGENT_PROMPT,
        LEGACY_SUBSCRIPTION_DEFAULT_AGENT_PROMPT,
    )
    if legacy_prompt and not legacy_is_default:
        raw.setdefault("profile_prompt", legacy_prompt)
        raw.setdefault("ranking_prompt", legacy_prompt)
    errors: List[str] = [] if value is None or isinstance(value, Mapping) else [
        "config must be a mapping"
    ]
    identities = _emby_identities(raw.get("emby_identities", []), errors)
    profile_ids = {str(item["profile_id"]) for item in identities}
    emby_library_ids = _emby_library_ids(
        raw.get("emby_library_ids") if "emby_library_ids" in raw else None,
        profile_ids,
        errors,
    )
    profile_access_map = _profile_access_map(
        raw.get("profile_access_map"), profile_ids, errors
    )
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

    action_mode = str(raw.get("action_mode") or "notify")
    if action_mode not in {"update", "notify", "auto_subscribe"}:
        errors.append("action_mode must be update, notify, or auto_subscribe")
        action_mode = "notify"

    notification_type = str(raw.get("notification_type") or "Plugin").strip()
    if notification_type not in NOTIFICATION_TYPE_NAMES:
        errors.append(
            "notification_type must be a valid MoviePilot NotificationType name"
        )
        notification_type = "Plugin"

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
        schedule_enabled=bool(raw.get("schedule_enabled", True)),
        cron=str(raw.get("cron") or "5 18 * * *").strip(),
        emby_identities=identities,
        default_profile_id=default_profile_id,
        profile_access_map=profile_access_map,
        emby_library_ids=emby_library_ids,
        discovery_sources=discovery_sources,
        weights=weights,
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
        action_mode=action_mode,
        notify=bool(raw.get("notify", True)),
        notification_type=notification_type,
        auto_subscribe_top_n=auto_top_n,
        auto_subscribe_limit=auto_limit,
        history_limit=_bounded_integer(
            raw.get("history_limit", 50), 50, 1, 200, "history_limit", errors
        ),
        candidate_snapshot_limit=_bounded_integer(
            raw.get("candidate_snapshot_limit", 20),
            20,
            1,
            500,
            "candidate_snapshot_limit",
            errors,
        ),
        feedback_event_limit=_bounded_integer(
            raw.get("feedback_event_limit", 1000),
            1000,
            1,
            100000,
            "feedback_event_limit",
            errors,
        ),
        feedback_queue_limit=_bounded_integer(
            raw.get("feedback_queue_limit", 200),
            200,
            1,
            100000,
            "feedback_queue_limit",
            errors,
        ),
        conversation_message_limit=_bounded_integer(
            raw.get("conversation_message_limit", 200),
            200,
            1,
            100000,
            "conversation_message_limit",
            errors,
        ),
        attribution_record_limit=_bounded_integer(
            raw.get("attribution_record_limit", 500),
            500,
            1,
            100000,
            "attribution_record_limit",
            errors,
        ),
        analysis_record_limit=_bounded_integer(
            raw.get("analysis_record_limit", 500),
            500,
            1,
            100000,
            "analysis_record_limit",
            errors,
        ),
        profile_cache_enabled=bool(raw.get("profile_cache_enabled", True)),
        rebuild_profile_each_run=bool(raw.get("rebuild_profile_each_run", False)),
        playback_enabled=bool(raw.get("playback_enabled", True)),
        playback_recent_days=_bounded_integer(
            raw.get("playback_recent_days", 90), 90, 1, 3650, "playback_recent_days", errors
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
        profile_prompt=_bounded_text(
            raw.get("profile_prompt", DEFAULT_PROFILE_PROMPT),
            DEFAULT_PROFILE_PROMPT,
            4000,
            "profile_prompt",
            errors,
        ),
        ranking_prompt=_bounded_text(
            raw.get("ranking_prompt", DEFAULT_RANKING_PROMPT),
            DEFAULT_RANKING_PROMPT,
            4000,
            "ranking_prompt",
            errors,
        ),
        copy_prompt=_bounded_text(
            raw.get("copy_prompt", DEFAULT_COPY_PROMPT),
            DEFAULT_COPY_PROMPT,
            4000,
            "copy_prompt",
            errors,
        ),
        critic_prompt=_bounded_text(
            raw.get("critic_prompt", DEFAULT_CRITIC_PROMPT),
            DEFAULT_CRITIC_PROMPT,
            4000,
            "critic_prompt",
            errors,
        ),
    )
    if not config.cron:
        errors.append("cron must not be empty")
        config.cron = "5 18 * * *"
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
