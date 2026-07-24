"""受限 MoviePilotAgent 会话适配器。"""

import inspect
import json
import re
from typing import Any, Callable, List, Optional, Type

from app.agent import MoviePilotAgent, ReplyMode
from app.utils.identity import SYSTEM_INTERNAL_USER_ID

from ..agent_tools.context import (
    PROFILE_AGENT_ROLE,
    RANKING_AGENT_ROLE,
    TRUSTED_CONTEXT_KEY,
    AgentRankTrustedContext,
)
from ..agent_tools.registry import (
    ALLOWED_AGENT_TOOL_NAMES,
    tool_classes_for_role,
    tool_names_for_role,
)


AGENTRANK_SYSTEM_PROMPTS = {
    PROFILE_AGENT_ROLE: "你是 Agent榜单中心的受限用户画像执行器，只能使用播放只读工具。",
    RANKING_AGENT_ROLE: "你是 Agent榜单中心的受限排序执行器，只能使用四个只读工具。",
}
AGENTRANK_SYSTEM_PROMPT = "你是 Agent榜单中心的受限执行器。"


class AgentTextUnavailableError(RuntimeError):
    """表示 Agent 完成工具调用后没有产生可捕获的合法 JSON。"""

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
        """绕过通用工具工厂，仅创建当前角色允许的只读工具。"""
        tools: List[Any] = []
        tool_classes = tool_classes_for_role(
            self._agentrank_trusted_context.agent_role
        )
        for tool_class in tool_classes:
            tool = tool_class(session_id=self.session_id, user_id=self.user_id)
            tool.set_message_attr(channel=None, source=None, username=None)
            tool.set_stream_handler(stream_handler=self.stream_handler)
            tool.set_agent_context(agent_context=self._tool_context)
            tools.append(tool)
        expected_names = tool_names_for_role(
            self._agentrank_trusted_context.agent_role
        )
        if not set(expected_names).issubset(set(ALLOWED_AGENT_TOOL_NAMES)):
            raise RuntimeError("AgentRank role whitelist exceeds global whitelist")
        if tuple(tool.name for tool in tools) != tuple(expected_names):
            raise RuntimeError("AgentRank tool registry and role whitelist diverged")
        return tools

    async def _initialize_llm(self, streaming: bool = False) -> Any:
        """直接使用 MoviePilot 内置 LLM 配置，绕过外部供应商分配事件。"""
        from app.agent.llm import LLMHelper
        from app.core.config import settings

        return await LLMHelper.get_llm(
            streaming=streaming,
            provider=settings.LLM_PROVIDER,
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            base_url_preset=settings.LLM_BASE_URL_PRESET,
            user_agent=settings.LLM_USER_AGENT,
            use_proxy=settings.LLM_USE_PROXY,
        )

    def _send_agent_tokens_usage_event(
        self,
        *,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """禁止 AgentRank 会话向 Agent Tokens 广播用量。"""
        del success, error
        return None

    async def _create_agent(self, streaming: bool = False) -> Any:
        """构建当前角色专用只读工具且无宿主扩展中间件的 Agent 图。"""
        from langchain.agents import create_agent
        from langgraph.checkpoint.memory import InMemorySaver

        model = await self._initialize_llm(streaming=streaming)
        self._sync_model_profile(model)
        self._last_agent_cache_hit = False
        return create_agent(
            model=model,
            tools=self._initialize_tools(),
            system_prompt=(
                AGENTRANK_SYSTEM_PROMPTS.get(
                    self._agentrank_trusted_context.agent_role,
                    AGENTRANK_SYSTEM_PROMPT,
                )
                + " 严格按照用户消息返回 JSON；禁止委派子代理、加载技能或记忆、"
                "管理任务、调用外部 MCP，以及使用任何未提供的工具。"
            ),
            middleware=[],
            checkpointer=InMemorySaver(),
        )


class AgentRankAgentAdapter:
    """运行一次独立榜单 Agent 并在所有路径清理图与会话记忆。"""

    _safe_scope = re.compile(r"^[A-Za-z0-9@._-]{1,96}$")
    _json_object_fence = re.compile(
        r"\A```(?:json)?[ \t]*\r?\n(?P<body>\{.*\})\r?\n```[ \t]*\Z",
        flags=re.IGNORECASE | re.DOTALL,
    )
    _json_object_trailing = re.compile(r"\A(?:```[ \t]*)?\Z")
    _host_failure_markers = (
        "智能助手执行失败",
        "处理消息时发生错误",
    )

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
        if not cls._safe_scope.fullmatch(trusted_context.agent_role):
            raise ValueError("AgentRank role scope contains unsafe characters")
        return (
            f"__agentrank_{trusted_context.agent_role}_"
            f"{trusted_context.run_id}_{trusted_context.username}__"
        )

    async def _clear_memory(self, session_id: str) -> None:
        """兼容同步与异步测试/宿主清理器。"""
        result = self._memory_clearer(session_id, self._user_id)
        if inspect.isawaitable(result):
            await result

    @classmethod
    def _normalize_captured_text(cls, value: Any) -> str:
        """仅剥离包住单个 JSON 对象的完整 Markdown 代码围栏。"""
        if not isinstance(value, str):
            return ""
        text = value.strip()
        match = cls._json_object_fence.fullmatch(text)
        if match:
            return match.group("body").strip()
        start = text.find("{")
        if start >= 0:
            try:
                _, end = json.JSONDecoder().raw_decode(text[start:])
            except json.JSONDecodeError:
                return text
            trailing = text[start + end :].strip()
            if cls._json_object_trailing.fullmatch(trailing):
                return text[start : start + end].strip()
        return text

    @classmethod
    def _is_json_object_text(cls, value: str) -> bool:
        """判断捕获文本是否恰好包含一个完整 JSON 对象。"""
        text = cls._normalize_captured_text(value)
        if not text.startswith("{"):
            return False
        try:
            payload, end = json.JSONDecoder().raw_decode(text)
        except json.JSONDecodeError:
            return False
        return isinstance(payload, dict) and not text[end:].strip()

    @classmethod
    def _host_failure_marker(cls, value: str) -> str:
        """识别宿主以普通文本返回的 Agent 执行失败标记。"""
        text = str(value or "").strip()
        return next((marker for marker in cls._host_failure_markers if marker in text), "")

    async def run(self, prompt: str, trusted_context: AgentRankTrustedContext) -> str:
        """执行捕获式 Agent 调用，并在成功或异常后清理全部会话状态。"""
        if not isinstance(trusted_context, AgentRankTrustedContext):
            raise TypeError("trusted_context must be AgentRankTrustedContext")
        session_id = self._session_id(trusted_context)
        captured_outputs: List[str] = []

        def capture_output(text: str) -> None:
            """保存宿主 output_callback 提供的候选完整文本。"""
            if isinstance(text, str):
                captured_outputs.append(text)

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
            candidates = [result, *reversed(captured_outputs)]
            normalized = [
                self._normalize_captured_text(value)
                for value in candidates
                if isinstance(value, str) and value.strip()
            ]
            for text in normalized:
                if self._is_json_object_text(text):
                    return text
            failure_marker = next(
                (self._host_failure_marker(text) for text in normalized if self._host_failure_marker(text)),
                "",
            )
            if failure_marker:
                raise AgentTextUnavailableError(
                    f"MoviePilot Agent 调用失败（{failure_marker}）"
                )
            if normalized:
                raise AgentTextUnavailableError("Agent did not produce a JSON object")
            raise AgentTextUnavailableError("Agent did not produce text output")
        finally:
            try:
                await agent.cleanup()
            finally:
                await self._clear_memory(session_id)

    async def run_profile(
        self, prompt: str, trusted_context: AgentRankTrustedContext
    ) -> str:
        """执行只允许读取播放事实的画像 Agent。"""
        if trusted_context.agent_role != PROFILE_AGENT_ROLE:
            raise ValueError("profile Agent requires profile trusted context")
        return await self.run(prompt, trusted_context)

    async def run_ranking(
        self, prompt: str, trusted_context: AgentRankTrustedContext
    ) -> str:
        """执行只允许排序冻结候选的排序 Agent。"""
        if trusted_context.agent_role != RANKING_AGENT_ROLE:
            raise ValueError("ranking Agent requires ranking trusted context")
        return await self.run(prompt, trusted_context)
