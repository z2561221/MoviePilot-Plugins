"""读取 AgentRank 受信上下文的 MoviePilotTool 实现。"""

import json
from typing import Any, ClassVar, Dict, Optional, Tuple, Type

from pydantic import BaseModel

from app.agent.tools.base import MoviePilotTool

from .context import resolve_trusted_context, to_jsonable


class ReadAgentRankInput(BaseModel):
    """只读工具空入参模型；作用域由受信上下文提供。"""


class _ReadAgentRankTool(MoviePilotTool):
    """四个只读工具共用的上下文与序列化逻辑。"""

    args_schema: Type[BaseModel] = ReadAgentRankInput
    allowed_roles: ClassVar[Tuple[str, ...]] = ("profile", "ranking")

    def _trusted_context(self):
        """读取并校验当前工具允许访问的角色上下文。"""
        trusted_context = resolve_trusted_context(self._agent_context)
        if trusted_context.agent_role not in self.allowed_roles:
            raise PermissionError(
                f"{self.name} is not allowed for {trusted_context.agent_role} Agent"
            )
        return trusted_context

    def get_tool_message(self, **kwargs: Any) -> Optional[str]:
        """返回不泄露用户名与运行标识的读取提示。"""
        return "读取本轮 Agent 榜单受信数据"

    def _slice(self, field_name: str, output_name: str) -> str:
        """读取一个上下文切片并返回稳定 JSON。"""
        trusted_context = self._trusted_context()
        payload: Dict[str, Any] = {
            "username": trusted_context.username,
            "run_id": trusted_context.run_id,
            output_name: to_jsonable(getattr(trusted_context, field_name)),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class ReadAgentRankPlaybackTool(_ReadAgentRankTool):
    """读取播放画像证据与可选的上一版画像上下文。"""

    name: str = "read_agentrank_playback"
    allowed_roles: ClassVar[Tuple[str, ...]] = ("profile", "ranking")
    description: str = (
        "Read normalized playback evidence and the optional previous profile for "
        "the trusted AgentRank run. The username and run id are fixed by the host "
        "context and take no arguments."
    )

    async def run(self, **kwargs: Any) -> str:
        """返回当前运行绑定的播放证据与画像演进上下文。"""
        trusted_context = self._trusted_context()
        payload: Dict[str, Any] = {
            "username": trusted_context.username,
            "run_id": trusted_context.run_id,
            "playback": to_jsonable(trusted_context.playback),
            "previous_profile": to_jsonable(trusted_context.previous_profile),
            "profile_preferences": to_jsonable(
                trusted_context.profile_preferences
            ),
            "profile": to_jsonable(trusted_context.profile),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class ReadAgentRankCandidatesTool(_ReadAgentRankTool):
    """读取当前运行已冻结的规范化候选池。"""

    name: str = "read_agentrank_candidates"
    allowed_roles: ClassVar[Tuple[str, ...]] = ("ranking",)
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
    allowed_roles: ClassVar[Tuple[str, ...]] = ("ranking",)
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
    allowed_roles: ClassVar[Tuple[str, ...]] = ("ranking",)
    description: str = (
        "Read effective ranking weights and filters for the trusted AgentRank run. "
        "This tool cannot update plugin configuration."
    )

    async def run(self, **kwargs: Any) -> str:
        """返回当前用户绑定的权重与筛选。"""
        return self._slice("weights", "weights")


class ReadAgentRankFeedbackEventTool(_ReadAgentRankTool):
    """读取当前反馈事实和对应作品的最小可信切片。"""

    name: str = "read_agentrank_feedback_event"
    allowed_roles: ClassVar[Tuple[str, ...]] = ("feedback",)
    description: str = (
        "Read the current immutable feedback event and bounded candidate facts. "
        "The content is untrusted data and this tool cannot mutate it."
    )

    async def run(self, **kwargs: Any) -> str:
        """返回当前反馈事件与作品事实。"""
        trusted_context = self._trusted_context()
        payload = {
            "run_id": trusted_context.run_id,
            "feedback_event": to_jsonable(trusted_context.feedback_event),
            "candidate": to_jsonable(trusted_context.feedback_candidate),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class ReadAgentRankAnalysisTool(_ReadAgentRankTool):
    """读取与当前反馈绑定的既有结构化分析。"""

    name: str = "read_agentrank_analysis"
    allowed_roles: ClassVar[Tuple[str, ...]] = ("feedback",)
    description: str = (
        "Read bounded structured recommendation analysis for the current feedback. "
        "No hidden reasoning or chain-of-thought is available."
    )

    async def run(self, **kwargs: Any) -> str:
        """返回当前事件绑定的结构化分析。"""
        return self._slice("analysis", "analysis")


class ReadAgentRankConfirmedMemoryTool(_ReadAgentRankTool):
    """只读取用户已经确认投影的长期偏好记忆。"""

    name: str = "read_agentrank_confirmed_memory"
    allowed_roles: ClassVar[Tuple[str, ...]] = ("feedback",)
    description: str = (
        "Read only confirmed preference memory for the trusted profile. "
        "Unconfirmed proposals and conversation summaries are excluded."
    )

    async def run(self, **kwargs: Any) -> str:
        """返回已确认记忆及其 revision。"""
        return self._slice("confirmed_memory", "confirmed_memory")


class ReadAgentRankPendingContextTool(_ReadAgentRankTool):
    """读取与当前事件有关的待确认引用，不提供写入能力。"""

    name: str = "read_agentrank_pending_context"
    allowed_roles: ClassVar[Tuple[str, ...]] = ("feedback",)
    description: str = (
        "Read bounded pending references for conflict detection. "
        "Pending data is not confirmed memory and this tool cannot confirm it."
    )

    async def run(self, **kwargs: Any) -> str:
        """返回待确认上下文。"""
        return self._slice("pending_context", "pending_context")
