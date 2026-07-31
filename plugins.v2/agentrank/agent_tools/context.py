"""AgentRank 工具使用的受信运行上下文。"""

from dataclasses import dataclass
from datetime import datetime
import re
from types import MappingProxyType
from typing import Any, Mapping


TRUSTED_CONTEXT_KEY = "agentrank_trusted_context"
PROFILE_AGENT_ROLE = "profile"
RANKING_AGENT_ROLE = "ranking"
PRELIMINARY_AGENT_ROLE = "preliminary"
FINAL_AGENT_ROLE = "final"
FEEDBACK_AGENT_ROLE = "feedback"
CONVERSATION_AGENT_ROLE = "conversation"
AGENT_ROLES = frozenset(
    {
        PROFILE_AGENT_ROLE,
        RANKING_AGENT_ROLE,
        PRELIMINARY_AGENT_ROLE,
        FINAL_AGENT_ROLE,
        FEEDBACK_AGENT_ROLE,
        CONVERSATION_AGENT_ROLE,
    }
)
_CANDIDATE_ID_PATTERN = re.compile(r"^[A-Za-z0-9:_-]{1,128}$")
_ARCHIVE_REASON_CODES = frozenset({"ignored", "disliked"})


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


def _safe_archive_time(value: Any) -> str:
    """只保留可解析且有界的 ISO 归档时间。"""
    text = str(value or "").strip()
    if not text or len(text) > 40:
        return ""
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return text


def _minimal_archive_feedback(value: Any) -> Mapping[str, Any]:
    """将完整归档投影为排序 Agent 所需的最小安全原因码列表。"""
    raw_entries = value.get("entries") if isinstance(value, Mapping) else []
    entries = []
    for item in raw_entries or []:
        if not isinstance(item, Mapping):
            continue
        candidate_id = str(item.get("candidate_id") or "").strip()
        if not _CANDIDATE_ID_PATTERN.fullmatch(candidate_id):
            continue
        raw_reason = str(item.get("reason") or "ignored").strip()
        entries.append(
            {
                "candidate_id": candidate_id,
                "reason": (
                    raw_reason if raw_reason in _ARCHIVE_REASON_CODES else "ignored"
                ),
                "archived_at": _safe_archive_time(item.get("archived_at")),
            }
        )
    return {"entries": entries}


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
    feedback_event: Any = None
    feedback_candidate: Any = None
    confirmed_memory: Any = None
    analysis: Any = None
    pending_context: Any = None
    conversation: Any = None
    judgment_cards: Any = None
    submission_constraints: Any = None


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
    feedback_event: Any = None,
    feedback_candidate: Any = None,
    confirmed_memory: Any = None,
    analysis: Any = None,
    pending_context: Any = None,
    conversation: Any = None,
    judgment_cards: Any = None,
    submission_constraints: Any = None,
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
        archive_feedback=_deep_freeze(_minimal_archive_feedback(archive_feedback)),
        weights=_deep_freeze(weights),
        previous_profile=_deep_freeze(previous_profile),
        profile_preferences=_deep_freeze(profile_preferences),
        playback=_deep_freeze(playback),
        profile=_deep_freeze(profile),
        agent_role=trusted_role,
        feedback_event=_deep_freeze(feedback_event),
        feedback_candidate=_deep_freeze(feedback_candidate),
        confirmed_memory=_deep_freeze(confirmed_memory),
        analysis=_deep_freeze(analysis),
        pending_context=_deep_freeze(pending_context),
        conversation=_deep_freeze(conversation),
        judgment_cards=_deep_freeze(judgment_cards),
        submission_constraints=_deep_freeze(submission_constraints),
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
