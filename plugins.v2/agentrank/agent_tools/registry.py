"""AgentRank 专用 Agent 工具白名单。"""

from .tools import (
    ReadAgentRankArchiveFeedbackTool,
    ReadAgentRankCandidatesTool,
    ReadAgentRankWeightsTool,
    ReadAgentRankPlaybackTool,
)


ALLOWED_AGENT_TOOL_NAMES = (
    "read_agentrank_candidates",
    "read_agentrank_archive_feedback",
    "read_agentrank_weights",
    "read_agentrank_playback",
)

AGENT_TOOL_CLASSES = (
    ReadAgentRankCandidatesTool,
    ReadAgentRankArchiveFeedbackTool,
    ReadAgentRankWeightsTool,
    ReadAgentRankPlaybackTool,
)
