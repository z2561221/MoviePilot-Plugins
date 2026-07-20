"""受限 MoviePilotAgent 会话适配器。"""

import inspect
import re
from typing import Any, Callable, List, Type

from app.agent import MoviePilotAgent, ReplyMode
from app.utils.identity import SYSTEM_INTERNAL_USER_ID

from ..agent_tools.context import (
    TRUSTED_CONTEXT_KEY,
    AgentRankTrustedContext,
)
from ..agent_tools.registry import AGENT_TOOL_CLASSES, ALLOWED_AGENT_TOOL_NAMES


AGENTRANK_SYSTEM_PROMPT = (
    "你是 Agent榜单中心的受限排序执行器。只能使用当前提供的四个只读工具，"
    "并严格按照用户消息返回一个 JSON 对象。禁止委派子代理、加载技能或记忆、"
    "管理任务、调用外部 MCP，以及使用任何未提供的工具。"
)


class AgentTextUnavailableError(RuntimeError):
    """表示 Agent 完成工具调用后没有产生可捕获文本。"""

    retryable = True


class RestrictedAgentRankAgent(MoviePilotAgent):
    """只实例化 AgentRank 四工具并注入单次运行上下文的内置 Agent。"""

    def __init__(self, trusted_context: AgentRankTrustedContext, **kwargs: Any):
        """强制捕获模式、无消息渠道和无消息工具。"""
        self._agentrank_trusted_context = trusted_context
        kwargs["replay_mode"] = ReplyMode.CAPTURE_ONLY
        kwargs["allow_message_tools"] = False
        kwargs["channel"] = None
        kwargs["source"] = None
        super().__init__(**kwargs)

    async def _build_tool_context(self, should_dispatch_reply: bool) -> dict:
        """扩展宿主上下文并强制禁止回复派发。"""
        context = await super()._build_tool_context(False)
        context["should_dispatch_reply"] = False
        context[TRUSTED_CONTEXT_KEY] = self._agentrank_trusted_context
        return context

    def _initialize_tools(self) -> List[Any]:
        """绕过通用工具工厂，仅创建白名单中的四个只读工具。"""
        tools: List[Any] = []
        for tool_class in AGENT_TOOL_CLASSES:
            tool = tool_class(session_id=self.session_id, user_id=self.user_id)
            tool.set_message_attr(channel=None, source=None, username=None)
            tool.set_stream_handler(stream_handler=self.stream_handler)
            tool.set_agent_context(agent_context=self._tool_context)
            tools.append(tool)
        if tuple(tool.name for tool in tools) != tuple(ALLOWED_AGENT_TOOL_NAMES):
            raise RuntimeError("AgentRank tool registry and whitelist diverged")
        return tools

    async def _create_agent(self, streaming: bool = False) -> Any:
        """构建仅含四个只读工具且无宿主扩展中间件的 Agent 图。"""
        from langchain.agents import create_agent
        from langgraph.checkpoint.memory import InMemorySaver

        model = await self._initialize_llm(streaming=streaming)
        self._sync_model_profile(model)
        self._last_agent_cache_hit = False
        return create_agent(
            model=model,
            tools=self._initialize_tools(),
            system_prompt=AGENTRANK_SYSTEM_PROMPT,
            middleware=[],
            checkpointer=InMemorySaver(),
        )


class AgentRankAgentAdapter:
    """运行一次独立榜单 Agent 并在所有路径清理图与会话记忆。"""

    _safe_scope = re.compile(r"^[A-Za-z0-9@._-]{1,96}$")

    def __init__(
        self,
        agent_factory: Type[Any] = RestrictedAgentRankAgent,
        memory_clearer: Callable[[str, str], Any] = None,
        user_id: str = SYSTEM_INTERNAL_USER_ID,
    ):
        """允许测试注入 Agent 工厂和内存清理器。"""
        self._agent_factory = agent_factory
        self._memory_clearer = memory_clearer or self._default_memory_clearer
        self._user_id = str(user_id or SYSTEM_INTERNAL_USER_ID)

    @staticmethod
    def _default_memory_clearer(session_id: str, user_id: str) -> None:
        """通过宿主 memory_manager 清除专用会话记忆。"""
        from app.agent.memory import memory_manager

        memory_manager.clear_memory(session_id, user_id)

    @classmethod
    def _session_id(cls, trusted_context: AgentRankTrustedContext) -> str:
        """构造不可注入分隔符的专用会话标识。"""
        if not cls._safe_scope.fullmatch(trusted_context.run_id) or not cls._safe_scope.fullmatch(
            trusted_context.username
        ):
            raise ValueError("AgentRank session scope contains unsafe characters")
        return f"__agentrank_{trusted_context.run_id}_{trusted_context.username}__"

    async def _clear_memory(self, session_id: str) -> None:
        """兼容同步与异步测试/宿主清理器。"""
        result = self._memory_clearer(session_id, self._user_id)
        if inspect.isawaitable(result):
            await result

    async def run(self, prompt: str, trusted_context: AgentRankTrustedContext) -> str:
        """执行捕获式 Agent 调用，并在成功或异常后清理全部会话状态。"""
        if not isinstance(trusted_context, AgentRankTrustedContext):
            raise TypeError("trusted_context must be AgentRankTrustedContext")
        session_id = self._session_id(trusted_context)
        captured_output = ""

        def capture_output(text: str) -> None:
            """保存宿主 output_callback 提供的最新完整文本。"""
            nonlocal captured_output
            if isinstance(text, str):
                captured_output = text

        agent = self._agent_factory(
            session_id=session_id,
            user_id=self._user_id,
            channel=None,
            source=None,
            username=trusted_context.username,
            replay_mode=ReplyMode.CAPTURE_ONLY,
            allow_message_tools=False,
            trusted_context=trusted_context,
            output_callback=capture_output,
        )
        try:
            result = await agent.process(str(prompt or ""))
            if isinstance(result, str):
                return result
            if captured_output:
                return captured_output
            raise AgentTextUnavailableError("Agent did not produce text output")
        finally:
            try:
                await agent.cleanup()
            finally:
                await self._clear_memory(session_id)
