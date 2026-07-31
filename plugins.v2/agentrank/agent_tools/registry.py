"""AgentRank 专用 Agent 工具白名单。"""

from .tools import (
    ReadAgentRankAnalysisTool,
    ReadAgentRankArchiveFeedbackTool,
    ReadAgentRankBatchContextTool,
    ReadAgentRankCandidatesTool,
    ReadAgentRankConfirmedMemoryTool,
    ReadAgentRankConversationTool,
    ReadAgentRankFeedbackEventTool,
    ReadAgentRankFinalContextTool,
    ReadAgentRankPendingContextTool,
    ReadAgentRankProfileContextTool,
    ReadAgentRankWeightsTool,
    ReadAgentRankPlaybackTool,
    SubmitAgentRankBatchResultTool,
    SubmitAgentRankFinalBoardTool,
    SubmitAgentRankProfileResultTool,
)


ALLOWED_AGENT_TOOL_NAMES = (
    "read_agentrank_candidates",
    "read_agentrank_archive_feedback",
    "read_agentrank_weights",
    "read_agentrank_playback",
)

PROFILE_AGENT_TOOL_NAMES = (
    "read_agentrank_profile_context",
    "submit_agentrank_profile_result",
)
PRELIMINARY_AGENT_TOOL_NAMES = (
    "read_agentrank_batch_context",
    "submit_agentrank_batch_result",
)
FINAL_AGENT_TOOL_NAMES = (
    "read_agentrank_final_context",
    "submit_agentrank_final_board",
)
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
        (
            *ALLOWED_AGENT_TOOL_NAMES,
            *PROFILE_AGENT_TOOL_NAMES,
            *PRELIMINARY_AGENT_TOOL_NAMES,
            *FINAL_AGENT_TOOL_NAMES,
            *FEEDBACK_AGENT_TOOL_NAMES,
            *CONVERSATION_AGENT_TOOL_NAMES,
        )
    )
)

AGENT_TOOL_CLASSES = (
    ReadAgentRankCandidatesTool,
    ReadAgentRankArchiveFeedbackTool,
    ReadAgentRankWeightsTool,
    ReadAgentRankPlaybackTool,
)

PROFILE_AGENT_TOOL_CLASSES = (
    ReadAgentRankProfileContextTool,
    SubmitAgentRankProfileResultTool,
)
PRELIMINARY_AGENT_TOOL_CLASSES = (
    ReadAgentRankBatchContextTool,
    SubmitAgentRankBatchResultTool,
)
FINAL_AGENT_TOOL_CLASSES = (
    ReadAgentRankFinalContextTool,
    SubmitAgentRankFinalBoardTool,
)
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
        (
            *AGENT_TOOL_CLASSES,
            *PROFILE_AGENT_TOOL_CLASSES,
            *PRELIMINARY_AGENT_TOOL_CLASSES,
            *FINAL_AGENT_TOOL_CLASSES,
            *FEEDBACK_AGENT_TOOL_CLASSES,
            *CONVERSATION_AGENT_TOOL_CLASSES,
        )
    )
)


def tool_classes_for_role(role: str):
    """返回指定 Agent 角色允许实例化的只读工具类。"""
    if str(role or "").strip() == "profile":
        return PROFILE_AGENT_TOOL_CLASSES
    if str(role or "").strip() == "ranking":
        return RANKING_AGENT_TOOL_CLASSES
    if str(role or "").strip() == "preliminary":
        return PRELIMINARY_AGENT_TOOL_CLASSES
    if str(role or "").strip() == "final":
        return FINAL_AGENT_TOOL_CLASSES
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
    if str(role or "").strip() == "preliminary":
        return PRELIMINARY_AGENT_TOOL_NAMES
    if str(role or "").strip() == "final":
        return FINAL_AGENT_TOOL_NAMES
    if str(role or "").strip() == "feedback":
        return FEEDBACK_AGENT_TOOL_NAMES
    if str(role or "").strip() == "conversation":
        return CONVERSATION_AGENT_TOOL_NAMES
    raise ValueError("unknown AgentRank role")
