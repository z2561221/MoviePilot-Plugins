"""AgentRank 工具使用的受信运行上下文。"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


TRUSTED_CONTEXT_KEY = "agentrank_trusted_context"
PROFILE_AGENT_ROLE = "profile"
RANKING_AGENT_ROLE = "ranking"
AGENT_ROLES = frozenset({PROFILE_AGENT_ROLE, RANKING_AGENT_ROLE})


def _deep_freeze(value: Any) -> Any:
    """深复制并冻结 JSON 类数据，阻止调用方在运行中篡改快照。"""
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _deep_freeze(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(item) for item in value)
    return value


def to_jsonable(value: Any) -> Any:
    """将冻结数据恢复为可序列化的独立容器。"""
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [to_jsonable(item) for item in value]
    return value


@dataclass(frozen=True)
class AgentRankTrustedContext:
    """表示一次榜单运行绑定的只读用户数据切片。"""

    username: str
    run_id: str
    candidates: Any
    archive_feedback: Any
    weights: Any
    previous_profile: Any
    profile_preferences: Any
    playback: Any
    profile: Any = None
    agent_role: str = RANKING_AGENT_ROLE


def build_trusted_context(
    username: str,
    run_id: str,
    candidates: Any,
    archive_feedback: Any,
    weights: Any,
    previous_profile: Any = None,
    profile_preferences: Any = None,
    playback: Any = None,
    profile: Any = None,
    agent_role: str = RANKING_AGENT_ROLE,
) -> AgentRankTrustedContext:
    """校验作用域与 Agent 角色并构造不可变的受信上下文。"""
    trusted_username = str(username or "").strip()
    trusted_run_id = str(run_id or "").strip()
    if not trusted_username or not trusted_run_id:
        raise ValueError("trusted_context requires username and run_id")
    trusted_role = str(agent_role or "").strip()
    if trusted_role not in AGENT_ROLES:
        raise ValueError("trusted_context agent_role is invalid")
    return AgentRankTrustedContext(
        username=trusted_username,
        run_id=trusted_run_id,
        candidates=_deep_freeze(candidates),
        archive_feedback=_deep_freeze(archive_feedback),
        weights=_deep_freeze(weights),
        previous_profile=_deep_freeze(previous_profile),
        profile_preferences=_deep_freeze(profile_preferences),
        playback=_deep_freeze(playback),
        profile=_deep_freeze(profile),
        agent_role=trusted_role,
    )


def resolve_trusted_context(agent_context: Mapping[str, Any]) -> AgentRankTrustedContext:
    """从宿主共享上下文读取并验证 AgentRank 专用对象。"""
    trusted_context = (
        agent_context.get(TRUSTED_CONTEXT_KEY)
        if isinstance(agent_context, Mapping)
        else None
    )
    if not isinstance(trusted_context, AgentRankTrustedContext):
        raise PermissionError("AgentRank trusted context is missing or invalid")
    if not trusted_context.username or not trusted_context.run_id:
        raise PermissionError("AgentRank trusted context scope is invalid")
    if trusted_context.agent_role not in AGENT_ROLES:
        raise PermissionError("AgentRank trusted context role is invalid")
    return trusted_context
