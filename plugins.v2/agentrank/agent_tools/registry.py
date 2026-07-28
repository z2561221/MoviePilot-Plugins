"""AgentRank 专用 Agent 工具白名单。"""

from .tools import (
    ReadAgentRankAnalysisTool,
    ReadAgentRankArchiveFeedbackTool,
    ReadAgentRankCandidatesTool,
    ReadAgentRankConfirmedMemoryTool,
    ReadAgentRankConversationTool,
    ReadAgentRankFeedbackEventTool,
    ReadAgentRankPendingContextTool,
    ReadAgentRankWeightsTool,
    ReadAgentRankPlaybackTool,
)


ALLOWED_AGENT_TOOL_NAMES = (
    "read_agentrank_candidates",
    "read_agentrank_archive_feedback",
    "read_agentrank_weights",
    "read_agentrank_playback",
)

PROFILE_AGENT_TOOL_NAMES = ("read_agentrank_playback",)
RANKING_AGENT_TOOL_NAMES = (
    "read_agentrank_candidates",
    "read_agentrank_archive_feedback",
    "read_agentrank_weights",
    "read_agentrank_playback",
)
FEEDBACK_AGENT_TOOL_NAMES = (
    "read_agentrank_feedback_event",
    "read_agentrank_analysis",
    "read_agentrank_confirmed_memory",
    "read_agentrank_pending_context",
)
CONVERSATION_AGENT_TOOL_NAMES = (
    "read_agentrank_conversation",
    "read_agentrank_playback",
    "read_agentrank_candidates",
    "read_agentrank_analysis",
    "read_agentrank_confirmed_memory",
    "read_agentrank_pending_context",
)
ALL_AGENT_TOOL_NAMES = tuple(
    dict.fromkeys(
        (*ALLOWED_AGENT_TOOL_NAMES, *FEEDBACK_AGENT_TOOL_NAMES, *CONVERSATION_AGENT_TOOL_NAMES)
    )
)

AGENT_TOOL_CLASSES = (
    ReadAgentRankCandidatesTool,
    ReadAgentRankArchiveFeedbackTool,
    ReadAgentRankWeightsTool,
    ReadAgentRankPlaybackTool,
)

PROFILE_AGENT_TOOL_CLASSES = (ReadAgentRankPlaybackTool,)
RANKING_AGENT_TOOL_CLASSES = (
    ReadAgentRankCandidatesTool,
    ReadAgentRankArchiveFeedbackTool,
    ReadAgentRankWeightsTool,
    ReadAgentRankPlaybackTool,
)
FEEDBACK_AGENT_TOOL_CLASSES = (
    ReadAgentRankFeedbackEventTool,
    ReadAgentRankAnalysisTool,
    ReadAgentRankConfirmedMemoryTool,
    ReadAgentRankPendingContextTool,
)
CONVERSATION_AGENT_TOOL_CLASSES = (
    ReadAgentRankConversationTool,
    ReadAgentRankPlaybackTool,
    ReadAgentRankCandidatesTool,
    ReadAgentRankAnalysisTool,
    ReadAgentRankConfirmedMemoryTool,
    ReadAgentRankPendingContextTool,
)
ALL_AGENT_TOOL_CLASSES = tuple(
    dict.fromkeys(
        (*AGENT_TOOL_CLASSES, *FEEDBACK_AGENT_TOOL_CLASSES, *CONVERSATION_AGENT_TOOL_CLASSES)
    )
)


def tool_classes_for_role(role: str):
    """返回指定 Agent 角色允许实例化的只读工具类。"""
    if str(role or "").strip() == "profile":
        return PROFILE_AGENT_TOOL_CLASSES
    if str(role or "").strip() == "ranking":
        return RANKING_AGENT_TOOL_CLASSES
    if str(role or "").strip() == "feedback":
        return FEEDBACK_AGENT_TOOL_CLASSES
    if str(role or "").strip() == "conversation":
        return CONVERSATION_AGENT_TOOL_CLASSES
    raise ValueError("unknown AgentRank role")


def tool_names_for_role(role: str):
    """返回指定 Agent 角色允许使用的工具名称。"""
    if str(role or "").strip() == "profile":
        return PROFILE_AGENT_TOOL_NAMES
    if str(role or "").strip() == "ranking":
        return RANKING_AGENT_TOOL_NAMES
    if str(role or "").strip() == "feedback":
        return FEEDBACK_AGENT_TOOL_NAMES
    if str(role or "").strip() == "conversation":
        return CONVERSATION_AGENT_TOOL_NAMES
    raise ValueError("unknown AgentRank role")
