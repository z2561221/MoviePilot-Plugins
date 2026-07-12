"""Agent榜单中心 MoviePilot 能力适配层。"""

from .subscription import SubscriptionAdapter
from .discovery import DiscoveryAdapter
from .agent import AgentRankAgentAdapter

__all__ = ["AgentRankAgentAdapter", "DiscoveryAdapter", "SubscriptionAdapter"]
