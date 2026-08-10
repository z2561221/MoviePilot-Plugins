"""Agent榜单中心四个只读 Agent 工具。"""

from .context import TRUSTED_CONTEXT_KEY, AgentRankTrustedContext, build_trusted_context

__all__ = [
    "AGENT_TOOL_CLASSES",
    "ALLOWED_AGENT_TOOL_NAMES",
    "TRUSTED_CONTEXT_KEY",
    "AgentRankTrustedContext",
    "build_trusted_context",
]


def __getattr__(name: str):
    """仅在显式访问 registry 导出时加载 MoviePilotTool 宿主依赖。"""
    if name in {"AGENT_TOOL_CLASSES", "ALLOWED_AGENT_TOOL_NAMES"}:
        from .registry import AGENT_TOOL_CLASSES, ALLOWED_AGENT_TOOL_NAMES

        return {
            "AGENT_TOOL_CLASSES": AGENT_TOOL_CLASSES,
            "ALLOWED_AGENT_TOOL_NAMES": ALLOWED_AGENT_TOOL_NAMES,
        }[name]
    raise AttributeError(name)
