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

    async def _build_tool_context(self, should_dispatch_reply):
        return {"should_dispatch_reply": should_dispatch_reply, "is_admin": False}

    async def process(self, message):
        self._tool_context.update(await self._build_tool_context(False))
        self.created_tools = self._initialize_tools()
        return "agent-output"

    async def cleanup(self):
        self.cleaned = True


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
tools_package = sys.modules.setdefault("app.agent.tools", ModuleType("app.agent.tools"))
base_module = sys.modules.setdefault("app.agent.tools.base", ModuleType("app.agent.tools.base"))
base_module.MoviePilotTool = MoviePilotTool
agent_module.tools = tools_package
tools_package.base = base_module
app_module.agent = agent_module

identity_module = sys.modules.setdefault("app.utils.identity", ModuleType("app.utils.identity"))
identity_module.SYSTEM_INTERNAL_USER_ID = "system"

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
        return "captured-json"

    async def cleanup(self):
        self.cleaned = True


def _trusted_context(run_id="run-1", username="alice"):
    return build_trusted_context(username, run_id, [], [], {"entries": []}, {"weights": {}})


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
    assert output == "captured-json"
    assert runner.kwargs["session_id"] == "__agentrank_run-1_alice__"
    assert runner.kwargs["replay_mode"] == ReplyMode.CAPTURE_ONLY
    assert runner.kwargs["allow_message_tools"] is False
    assert runner.kwargs["channel"] is None
    assert runner.kwargs["source"] is None
    assert runner.cleaned is True
    assert cleared == [("__agentrank_run-1_alice__", "system")]


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
    assert cleared == [("__agentrank_run-2_alice__", "system")]


def test_restricted_agent_injects_context_and_instantiates_exact_tool_classes():
    """The dedicated subclass bypasses the general factory and creates only four tools."""
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
