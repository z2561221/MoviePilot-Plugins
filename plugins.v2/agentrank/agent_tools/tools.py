"""读取 AgentRank 受信上下文的 MoviePilotTool 实现。"""

import json
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel

from app.agent.tools.base import MoviePilotTool

from .context import resolve_trusted_context, to_jsonable


class ReadAgentRankInput(BaseModel):
    """只读工具空入参模型；作用域由受信上下文提供。"""


class _ReadAgentRankTool(MoviePilotTool):
    """四个只读工具共用的上下文与序列化逻辑。"""

    args_schema: Type[BaseModel] = ReadAgentRankInput

    def get_tool_message(self, **kwargs: Any) -> Optional[str]:
        """返回不泄露用户名与运行标识的读取提示。"""
        return "读取本轮 Agent 榜单受信数据"

    def _slice(self, field_name: str, output_name: str) -> str:
        """读取一个上下文切片并返回稳定 JSON。"""
        trusted_context = resolve_trusted_context(self._agent_context)
        payload: Dict[str, Any] = {
            "username": trusted_context.username,
            "run_id": trusted_context.run_id,
            output_name: to_jsonable(getattr(trusted_context, field_name)),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class ReadAgentRankSubscriptionsTool(_ReadAgentRankTool):
    """读取当前订阅样本和可选的上一版画像。"""

    name: str = "read_agentrank_subscriptions"
    description: str = (
        "Read normalized subscription samples and the optional previous profile for "
        "the trusted AgentRank run. The username and run id are fixed by the host "
        "context and take no arguments."
    )

    async def run(self, **kwargs: Any) -> str:
        """返回当前运行绑定的订阅样本与受控画像演进上下文。"""
        trusted_context = resolve_trusted_context(self._agent_context)
        payload: Dict[str, Any] = {
            "username": trusted_context.username,
            "run_id": trusted_context.run_id,
            "subscriptions": to_jsonable(trusted_context.subscriptions),
            "previous_profile": to_jsonable(trusted_context.previous_profile),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class ReadAgentRankCandidatesTool(_ReadAgentRankTool):
    """读取当前运行已冻结的规范化候选池。"""

    name: str = "read_agentrank_candidates"
    description: str = (
        "Read the frozen candidate pool for the trusted AgentRank run. "
        "Recommendations must only reference candidate_id values from this result."
    )

    async def run(self, **kwargs: Any) -> str:
        """返回当前运行绑定的候选池。"""
        return self._slice("candidates", "candidates")


class ReadAgentRankArchiveFeedbackTool(_ReadAgentRankTool):
    """读取当前用户有效的忽略归档反馈。"""

    name: str = "read_agentrank_archive_feedback"
    description: str = (
        "Read active archive feedback for the trusted AgentRank user. "
        "This tool cannot restore or mutate archive entries."
    )

    async def run(self, **kwargs: Any) -> str:
        """返回当前用户绑定的归档反馈。"""
        return self._slice("archive_feedback", "archive_feedback")


class ReadAgentRankWeightsTool(_ReadAgentRankTool):
    """读取当前用户生效权重与筛选条件。"""

    name: str = "read_agentrank_weights"
    description: str = (
        "Read effective ranking weights and filters for the trusted AgentRank run. "
        "This tool cannot update plugin configuration."
    )

    async def run(self, **kwargs: Any) -> str:
        """返回当前用户绑定的权重与筛选。"""
        return self._slice("weights", "weights")
