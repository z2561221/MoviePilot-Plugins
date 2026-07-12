"""AgentRank 专用 Agent 工具白名单。"""

from .tools import (
    ReadAgentRankArchiveFeedbackTool,
    ReadAgentRankCandidatesTool,
    ReadAgentRankSubscriptionsTool,
    ReadAgentRankWeightsTool,
)


ALLOWED_AGENT_TOOL_NAMES = (
    "read_agentrank_subscriptions",
    "read_agentrank_candidates",
    "read_agentrank_archive_feedback",
    "read_agentrank_weights",
)

AGENT_TOOL_CLASSES = (
    ReadAgentRankSubscriptionsTool,
    ReadAgentRankCandidatesTool,
    ReadAgentRankArchiveFeedbackTool,
    ReadAgentRankWeightsTool,
)
