"""Agent榜单中心 MoviePilot 能力适配层。"""

from importlib import import_module
from typing import Any


__all__ = ["AgentRankAgentAdapter", "DiscoveryAdapter", "SubscriptionAdapter"]


def __getattr__(name: str) -> Any:
    """按需加载宿主适配器，避免无关模块提前初始化 MoviePilot Agent。"""
    modules = {
        "AgentRankAgentAdapter": ".agent",
        "DiscoveryAdapter": ".discovery",
        "SubscriptionAdapter": ".subscription",
    }
    if name not in modules:
        raise AttributeError(name)
    return getattr(import_module(modules[name], __name__), name)
