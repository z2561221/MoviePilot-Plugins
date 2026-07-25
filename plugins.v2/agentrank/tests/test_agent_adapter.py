"""Restricted MoviePilotAgent adapter lifecycle and isolation tests."""

import asyncio
import importlib
import sys
from enum import Enum
from pathlib import Path
from types import ModuleType


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_agent_adapter_test"


class ReplyMode(str, Enum):
    """Minimal host reply-mode stand-in."""

    DISPATCH = "dispatch"
    CAPTURE_ONLY = "capture_only"


class FakeStreamHandler:
    """Capture the stream handler assigned to tools."""


class MoviePilotAgent:
    """Minimal host agent exposing the hooks overridden by AgentRank."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.reply_mode = kwargs.get("replay_mode")
        self._tool_context = {}
        self.stream_handler = FakeStreamHandler()
        self.provider_resolution_calls = 0
        self.recorded_usage = []
        self.usage_events = []

    async def _build_tool_context(self, should_dispatch_reply):
        return {"should_dispatch_reply": should_dispatch_reply, "is_admin": False}

    async def process(self, message):
        self._tool_context.update(await self._build_tool_context(False))
        self.created_tools = self._initialize_tools()
        return "agent-output"

    async def cleanup(self):
        self.cleaned = True

    async def _resolve_llm_runtime_config(self):
        self.provider_resolution_calls += 1
        self._llm_provider_selection = {
            "selected_provider_id": "agenttokens-provider-id",
            "selected_provider_name": "Agent Tokens Provider",
            "provider": "agenttokens-provider",
            "model": "agenttokens-model-id",
            "source": "agenttokens",
        }
        return {
            "provider": "agenttokens-provider",
            "model": "agenttokens-model-id",
            "api_key": "agenttokens-key",
            "base_url": "https://agenttokens.invalid/v1",
            "base_url_preset": "agenttokens-preset",
            "user_agent": "MoviePilot-test",
            "use_proxy": False,
            "thinking_level": "medium",
        }

    async def _initialize_llm(self, streaming=False):
        runtime_config = await self._resolve_llm_runtime_config()
        return await LLMHelper.get_llm(streaming=streaming, **runtime_config)

    def _record_usage(self, usage):
        self.recorded_usage.append(usage)

    def _send_agent_tokens_usage_event(self, *, success, error=None):
        self.usage_events.append({"success": success, "error": error})

    def _sync_model_profile(self, model):
        self.synced_model = model


class LLMHelper:
    """Record the provider configuration resolved by the host Agent."""

    calls = []

    @classmethod
    async def get_llm(cls, **kwargs):
        """Return a deterministic model while preserving call arguments."""
        cls.calls.append(kwargs)
        return "builtin-model"


class MoviePilotTool:
    """Minimal host tool with context setter hooks."""

    def __init__(self, session_id, user_id, **kwargs):
        self._session_id = session_id
        self._user_id = user_id

    def set_message_attr(self, channel=None, source=None, username=None):
        self.message_attr = (channel, source, username)

    def set_stream_handler(self, stream_handler=None):
        self.stream_handler = stream_handler

    def set_agent_context(self, agent_context=None):
        self._agent_context = agent_context


app_module = sys.modules.setdefault("app", ModuleType("app"))
agent_module = sys.modules.setdefault("app.agent", ModuleType("app.agent"))
agent_module.MoviePilotAgent = MoviePilotAgent
agent_module.ReplyMode = ReplyMode
llm_module = sys.modules.setdefault("app.agent.llm", ModuleType("app.agent.llm"))
llm_module.LLMHelper = LLMHelper
tools_package = sys.modules.setdefault("app.agent.tools", ModuleType("app.agent.tools"))
base_module = sys.modules.setdefault("app.agent.tools.base", ModuleType("app.agent.tools.base"))
base_module.MoviePilotTool = MoviePilotTool
agent_module.tools = tools_package
tools_package.base = base_module
app_module.agent = agent_module


class UsageMiddleware:
    """Minimal host usage middleware retaining the callback contract."""

    def __init__(self, *, on_usage=None):
        self.on_usage = on_usage


middleware_package = sys.modules.setdefault(
    "app.agent.middleware", ModuleType("app.agent.middleware")
)
usage_module = sys.modules.setdefault(
    "app.agent.middleware.usage", ModuleType("app.agent.middleware.usage")
)
usage_module.UsageMiddleware = UsageMiddleware
middleware_package.usage = usage_module
agent_module.middleware = middleware_package

identity_module = sys.modules.setdefault("app.utils.identity", ModuleType("app.utils.identity"))
identity_module.SYSTEM_INTERNAL_USER_ID = "system"

created_agent_calls = []


def create_agent(**kwargs):
    """Record the exact graph construction arguments."""
    created_agent_calls.append(kwargs)
    return kwargs


class InMemorySaver:
    """Minimal LangGraph checkpointer stand-in."""


langchain_module = sys.modules.setdefault("langchain", ModuleType("langchain"))
langchain_agents_module = sys.modules.setdefault(
    "langchain.agents", ModuleType("langchain.agents")
)
langchain_agents_module.create_agent = create_agent
langchain_module.agents = langchain_agents_module
langgraph_module = sys.modules.setdefault("langgraph", ModuleType("langgraph"))
langgraph_checkpoint_module = sys.modules.setdefault(
    "langgraph.checkpoint", ModuleType("langgraph.checkpoint")
)
langgraph_memory_module = sys.modules.setdefault(
    "langgraph.checkpoint.memory", ModuleType("langgraph.checkpoint.memory")
)
langgraph_memory_module.InMemorySaver = InMemorySaver
langgraph_module.checkpoint = langgraph_checkpoint_module
langgraph_checkpoint_module.memory = langgraph_memory_module

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

context_module = importlib.import_module(f"{PACKAGE_NAME}.agent_tools.context")
registry_module = importlib.import_module(f"{PACKAGE_NAME}.agent_tools.registry")
adapter_module = importlib.import_module(f"{PACKAGE_NAME}.adapter.agent")

TRUSTED_CONTEXT_KEY = context_module.TRUSTED_CONTEXT_KEY
build_trusted_context = context_module.build_trusted_context
AGENT_TOOL_CLASSES = registry_module.AGENT_TOOL_CLASSES
AgentRankAgentAdapter = adapter_module.AgentRankAgentAdapter
RestrictedAgentRankAgent = adapter_module.RestrictedAgentRankAgent


class FakeRunner:
    """Record adapter constructor arguments and optional process failure."""

    instances = []
    fail = False

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.cleaned = False
        self.__class__.instances.append(self)

    async def process(self, prompt):
        self.prompt = prompt
        if self.__class__.fail:
            raise RuntimeError("agent failed")
        return '{"recommendations": []}'

    async def cleanup(self):
        self.cleaned = True


class FakeCallbackRunner(FakeRunner):
    """模拟当前宿主仅通过 output_callback 返回捕获文本。"""

    async def process(self, prompt):
        self.prompt = prompt
        self.kwargs["output_callback"]("partial")
        self.kwargs["output_callback"]('{"recommendations": []}')
        return None


class FakeEmptyRunner(FakeRunner):
    """Return only blank process and callback output."""

    async def process(self, prompt):
        """Simulate a completed Agent call without usable text."""
        self.prompt = prompt
        self.kwargs["output_callback"]("   ")
        return "\n\t"


class FakeFencedRunner(FakeRunner):
    """Return one JSON object wrapped by a model-generated code fence."""

    async def process(self, prompt):
        """Simulate a strict payload with only presentation wrapping."""
        self.prompt = prompt
        self.kwargs["output_callback"](
            "```json\n{\"recommendations\": []}\n```"
        )
        return None


class FakeHostErrorRunner(FakeRunner):
    """模拟宿主把执行异常包装成普通文本返回。"""

    async def process(self, prompt):
        """返回 MoviePilot 当前使用的 Agent 失败文案。"""
        self.prompt = prompt
        return "智能助手执行失败: upstream unavailable"


class FakeProseRunner(FakeRunner):
    """模拟模型返回解释性自然语言而不是 JSON。"""

    async def process(self, prompt):
        """返回一段不应进入领域 parser 的自然语言。"""
        self.prompt = prompt
        return "我会先分析这些候选，然后给出推荐。"


class FakeErrorResultWithJsonCallbackRunner(FakeRunner):
    """模拟返回值失败但最终回调已经包含合法 JSON。"""

    async def process(self, prompt):
        """同时提供宿主错误返回值与合法 JSON 回调。"""
        self.prompt = prompt
        self.kwargs["output_callback"]('{"recommendations": []}')
        return "处理消息时发生错误: stale host result"


class FakeStreamBufferRunner(FakeRunner):
    """模拟新版宿主只在 Agent 流式缓冲区保留最终文本。"""

    async def process(self, prompt):
        """写入 `_streamed_output`，但不触发回调且返回空值。"""
        self.prompt = prompt
        self._streamed_output = '{"recommendations": []}'
        return None


class FakeStructuredResultRunner(FakeRunner):
    """模拟宿主把最终文本包装在结构化返回值中。"""

    async def process(self, prompt):
        """返回包含 content 文本槽位的结构化结果。"""
        self.prompt = prompt
        return {"content": '{"recommendations": []}', "metadata": {"ok": True}}


def _trusted_context(run_id="run-1", username="alice", agent_role="ranking"):
    return build_trusted_context(
        username,
        run_id,
        [],
        {"entries": []},
        {"weights": {}},
        playback={"source": "playback_reporting", "samples": []},
        agent_role=agent_role,
    )


def test_adapter_uses_exact_capture_only_session_and_cleans_success():
    """A successful call uses one private session and always clears resources."""
    FakeRunner.instances.clear()
    FakeRunner.fail = False
    cleared = []
    adapter = AgentRankAgentAdapter(
        agent_factory=FakeRunner,
        memory_clearer=lambda session_id, user_id: cleared.append((session_id, user_id)),
    )

    output = asyncio.run(adapter.run("rank now", _trusted_context()))

    runner = FakeRunner.instances[-1]
    assert output == '{"recommendations": []}'
    assert runner.kwargs["session_id"] == "__agentrank_ranking_run-1_alice__"
    assert runner.kwargs["replay_mode"] == ReplyMode.CAPTURE_ONLY
    assert runner.kwargs["allow_message_tools"] is False
    assert runner.kwargs["channel"] is None
    assert runner.kwargs["source"] is None
    assert runner.cleaned is True
    assert cleared == [("__agentrank_ranking_run-1_alice__", "system")]


def test_adapter_cleans_agent_and_memory_when_process_fails():
    """Agent exceptions cannot leave a live graph or conversation memory."""
    FakeRunner.instances.clear()
    FakeRunner.fail = True
    cleared = []
    adapter = AgentRankAgentAdapter(
        agent_factory=FakeRunner,
        memory_clearer=lambda session_id, user_id: cleared.append((session_id, user_id)),
    )

    try:
        asyncio.run(adapter.run("rank now", _trusted_context("run-2")))
    except RuntimeError as error:
        assert str(error) == "agent failed"
    else:
        raise AssertionError("agent failure was swallowed")

    assert FakeRunner.instances[-1].cleaned is True
    assert cleared == [("__agentrank_ranking_run-2_alice__", "system")]


def test_adapter_uses_capture_callback_when_host_process_returns_none():
    """当前宿主成功路径返回 None 时仍应取得回调中的最终文本。"""
    FakeCallbackRunner.instances.clear()
    cleared = []
    adapter = AgentRankAgentAdapter(
        agent_factory=FakeCallbackRunner,
        memory_clearer=lambda session_id, user_id: cleared.append((session_id, user_id)),
    )

    output = asyncio.run(adapter.run("rank now", _trusted_context()))

    runner = FakeCallbackRunner.instances[-1]
    assert output == '{"recommendations": []}'
    assert callable(runner.kwargs["output_callback"])
    assert runner.cleaned is True
    assert cleared == [("__agentrank_ranking_run-1_alice__", "system")]


def test_adapter_rejects_blank_process_and_callback_output():
    """Blank host output is a retryable Agent failure, not invalid JSON."""
    FakeEmptyRunner.instances.clear()
    cleared = []
    adapter = AgentRankAgentAdapter(
        agent_factory=FakeEmptyRunner,
        memory_clearer=lambda session_id, user_id: cleared.append((session_id, user_id)),
    )

    try:
        asyncio.run(adapter.run("rank now", _trusted_context()))
    except adapter_module.AgentTextUnavailableError as error:
        assert error.retryable is True
    else:
        raise AssertionError("blank Agent output was accepted")

    assert FakeEmptyRunner.instances[-1].cleaned is True
    assert cleared == [("__agentrank_ranking_run-1_alice__", "system")]


def test_adapter_unwraps_only_a_complete_json_object_fence():
    """One full JSON fence is normalized without accepting prose wrappers."""
    adapter = AgentRankAgentAdapter(
        agent_factory=FakeFencedRunner,
        memory_clearer=lambda *_: None,
    )

    output = asyncio.run(adapter.run("rank now", _trusted_context()))

    assert output == '{"recommendations": []}'


def test_adapter_classifies_host_failure_text_as_retryable_agent_error():
    """宿主失败文案不得伪装成 JSON 校验错误。"""
    adapter = AgentRankAgentAdapter(
        agent_factory=FakeHostErrorRunner,
        memory_clearer=lambda *_: None,
    )

    try:
        asyncio.run(adapter.run("rank now", _trusted_context()))
    except adapter_module.AgentTextUnavailableError as error:
        assert error.retryable is True
        assert "智能助手执行失败" in str(error)
        assert "upstream unavailable" not in str(error)
    else:
        raise AssertionError("host Agent failure text was accepted")


def test_adapter_rejects_prose_as_retryable_agent_error():
    """自然语言不能再落入 JSON parser 形成误导性的校验失败。"""
    adapter = AgentRankAgentAdapter(
        agent_factory=FakeProseRunner,
        memory_clearer=lambda *_: None,
    )

    try:
        asyncio.run(adapter.run("rank now", _trusted_context()))
    except adapter_module.AgentTextUnavailableError as error:
        assert error.retryable is True
        assert str(error) == "Agent did not produce a JSON object"
    else:
        raise AssertionError("prose Agent output was accepted")


def test_adapter_prefers_valid_callback_json_over_host_error_result():
    """返回值与回调冲突时优先采用完整 JSON 对象。"""
    adapter = AgentRankAgentAdapter(
        agent_factory=FakeErrorResultWithJsonCallbackRunner,
        memory_clearer=lambda *_: None,
    )

    output = asyncio.run(adapter.run("rank now", _trusted_context()))

    assert output == '{"recommendations": []}'
    assert (
        adapter._normalize_captured_text(
            "结果如下：\n```json\n{\"recommendations\": []}\n```"
        )
        == '{"recommendations": []}'
    )
    assert (
        adapter._normalize_captured_text(
            "```json\n{\"recommendations\": []}\n```\n额外说明"
        )
        == "```json\n{\"recommendations\": []}\n```\n额外说明"
    )
    assert (
        adapter._normalize_captured_text(
            "结果如下：\n{\"recommendations\": []}\n```"
        )
        == '{"recommendations": []}'
    )
    assert (
        adapter._normalize_captured_text(
            '{"recommendations": []}\n{"recommendations": []}'
        )
        == '{"recommendations": []}\n{"recommendations": []}'
    )


def test_adapter_reads_host_streamed_output_when_callback_and_process_are_empty():
    """宿主只保留 `_streamed_output` 时仍应取得最终 JSON。"""
    adapter = AgentRankAgentAdapter(
        agent_factory=FakeStreamBufferRunner,
        memory_clearer=lambda *_: None,
    )

    output = asyncio.run(adapter.run("rank now", _trusted_context()))

    assert output == '{"recommendations": []}'


def test_adapter_reads_structured_process_result_text_slot():
    """宿主返回 tuple/dict 等结构化结果时读取明确的文本槽位。"""
    adapter = AgentRankAgentAdapter(
        agent_factory=FakeStructuredResultRunner,
        memory_clearer=lambda *_: None,
    )

    output = asyncio.run(adapter.run("rank now", _trusted_context()))

    assert output == '{"recommendations": []}'


def test_profile_role_uses_separate_session_and_single_playback_tool():
    """画像角色使用独立 session，并且只能实例化播放工具。"""
    FakeRunner.instances.clear()
    FakeRunner.fail = False
    adapter = AgentRankAgentAdapter(
        agent_factory=FakeRunner, memory_clearer=lambda *_: None
    )
    trusted = _trusted_context(agent_role="profile")

    output = asyncio.run(adapter.run_profile("profile", trusted))

    assert output == '{"recommendations": []}'
    runner = FakeRunner.instances[-1]
    assert runner.kwargs["session_id"] == "__agentrank_profile_run-1_alice__"
    assert runner.kwargs["trusted_context"].agent_role == "profile"


def test_restricted_agent_injects_context_and_instantiates_exact_tool_classes():
    """The dedicated subclass bypasses the general factory and creates only five tools."""
    trusted = _trusted_context()
    agent = RestrictedAgentRankAgent(
        session_id="__agentrank_run-1_alice__",
        user_id="system",
        username="alice",
        trusted_context=trusted,
        replay_mode=ReplyMode.CAPTURE_ONLY,
        allow_message_tools=False,
    )

    context = asyncio.run(agent._build_tool_context(False))
    agent._tool_context.update(context)
    tools = agent._initialize_tools()

    assert context[TRUSTED_CONTEXT_KEY] is trusted
    assert context["should_dispatch_reply"] is False
    assert tuple(type(tool) for tool in tools) == tuple(AGENT_TOOL_CLASSES)
    assert {tool.name for tool in tools} == {tool.name for tool in AGENT_TOOL_CLASSES}
    assert all(tool._agent_context is agent._tool_context for tool in tools)
    assert all(tool.message_attr == (None, None, None) for tool in tools)


def test_restricted_profile_agent_instantiates_only_playback_tool():
    """画像 Agent 的图中不得出现候选、归档或权重工具。"""
    trusted = _trusted_context(agent_role="profile")
    agent = RestrictedAgentRankAgent(
        session_id="__agentrank_profile_run-1_alice__",
        user_id="system",
        username="alice",
        trusted_context=trusted,
        replay_mode=ReplyMode.CAPTURE_ONLY,
        allow_message_tools=False,
    )

    agent._tool_context.update(asyncio.run(agent._build_tool_context(False)))
    tools = agent._initialize_tools()

    assert [tool.name for tool in tools] == ["read_agentrank_playback"]


def test_restricted_agent_builds_graph_with_provider_resolution_and_usage_only():
    """受限图继承宿主 Provider 分配，并且只保留用量统计中间件。"""
    created_agent_calls.clear()
    LLMHelper.calls.clear()
    agent = RestrictedAgentRankAgent(
        session_id="__agentrank_run-1_alice__",
        user_id="system",
        username="alice",
        trusted_context=_trusted_context(),
        replay_mode=ReplyMode.CAPTURE_ONLY,
        allow_message_tools=False,
    )
    agent._tool_context.update(asyncio.run(agent._build_tool_context(False)))

    graph = asyncio.run(agent._create_agent(streaming=False))

    assert graph is created_agent_calls[-1]
    assert graph["model"] == "builtin-model"
    assert agent.provider_resolution_calls == 1
    assert RestrictedAgentRankAgent._initialize_llm is MoviePilotAgent._initialize_llm
    assert LLMHelper.calls == [
        {
            "streaming": False,
            "provider": "agenttokens-provider",
            "model": "agenttokens-model-id",
            "api_key": "agenttokens-key",
            "base_url": "https://agenttokens.invalid/v1",
            "base_url_preset": "agenttokens-preset",
            "user_agent": "MoviePilot-test",
            "use_proxy": False,
            "thinking_level": "medium",
        }
    ]
    assert tuple(tool.name for tool in graph["tools"]) == tuple(
        tool.name for tool in AGENT_TOOL_CLASSES
    )
    assert len(graph["middleware"]) == 1
    usage_middleware = graph["middleware"][0]
    assert isinstance(usage_middleware, UsageMiddleware)
    usage_middleware.on_usage({"total_tokens": 42})
    assert agent.recorded_usage == [{"total_tokens": 42}]
    assert "四个只读工具" in graph["system_prompt"]
    assert isinstance(graph["checkpointer"], InMemorySaver)


def test_restricted_agent_inherits_agent_tokens_usage_broadcast():
    """AgentRank 必须继承宿主的 Agent Tokens 用量广播。"""
    agent = RestrictedAgentRankAgent(
        session_id="__agentrank_run-1_alice__",
        user_id="system",
        username="alice",
        trusted_context=_trusted_context(),
        replay_mode=ReplyMode.CAPTURE_ONLY,
        allow_message_tools=False,
    )

    assert (
        RestrictedAgentRankAgent._send_agent_tokens_usage_event
        is MoviePilotAgent._send_agent_tokens_usage_event
    )
    agent._send_agent_tokens_usage_event(success=True)
    agent._send_agent_tokens_usage_event(success=False, error="failed")
    assert agent.usage_events == [
        {"success": True, "error": None},
        {"success": False, "error": "failed"},
    ]


def test_session_scope_rejects_separator_injection():
    """Untrusted usernames and run IDs cannot alter the private session namespace."""
    adapter = AgentRankAgentAdapter(agent_factory=FakeRunner, memory_clearer=lambda *_: None)
    bad_context = _trusted_context(run_id="run/escape", username="alice")

    try:
        asyncio.run(adapter.run("rank", bad_context))
    except ValueError as error:
        assert "session scope" in str(error)
    else:
        raise AssertionError("unsafe session scope was accepted")
