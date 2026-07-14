"""AgentRank trusted context and four read-only Agent tool tests."""

import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_tools_test"


class MoviePilotTool:
    """Minimal host-tool stand-in for repository-only behavior tests."""

    def __init__(self, session_id, user_id, **kwargs):
        self._session_id = session_id
        self._user_id = user_id
        self._agent_context = {}

    def set_agent_context(self, agent_context=None):
        self._agent_context = agent_context or {}


app_module = sys.modules.setdefault("app", ModuleType("app"))
agent_module = sys.modules.setdefault("app.agent", ModuleType("app.agent"))
tools_package = sys.modules.setdefault("app.agent.tools", ModuleType("app.agent.tools"))
base_module = sys.modules.setdefault("app.agent.tools.base", ModuleType("app.agent.tools.base"))
base_module.MoviePilotTool = MoviePilotTool
app_module.agent = agent_module
agent_module.tools = tools_package
tools_package.base = base_module

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

context_module = importlib.import_module(f"{PACKAGE_NAME}.agent_tools.context")
registry_module = importlib.import_module(f"{PACKAGE_NAME}.agent_tools.registry")

TRUSTED_CONTEXT_KEY = context_module.TRUSTED_CONTEXT_KEY
build_trusted_context = context_module.build_trusted_context
ALLOWED_AGENT_TOOL_NAMES = registry_module.ALLOWED_AGENT_TOOL_NAMES
AGENT_TOOL_CLASSES = registry_module.AGENT_TOOL_CLASSES


def _tools_with_context(context):
    tools = []
    for tool_class in AGENT_TOOL_CLASSES:
        tool = tool_class(session_id="session", user_id="system")
        tool.set_agent_context({TRUSTED_CONTEXT_KEY: context})
        tools.append(tool)
    return tools


def test_registry_contains_exact_four_read_only_tools_with_empty_call_schemas():
    """The model can choose only a tool name, never username or run_id."""
    assert set(ALLOWED_AGENT_TOOL_NAMES) == {
        "read_agentrank_subscriptions",
        "read_agentrank_candidates",
        "read_agentrank_archive_feedback",
        "read_agentrank_weights",
    }
    assert {tool.name for tool in AGENT_TOOL_CLASSES} == set(ALLOWED_AGENT_TOOL_NAMES)
    for tool_class in AGENT_TOOL_CLASSES:
        assert tool_class.args_schema.model_fields == {}


def test_trusted_context_is_deep_copied_and_all_tools_read_expected_slice():
    """Callers cannot mutate a run snapshot after it becomes trusted context."""
    subscriptions = [{"stable_id": "tmdb:1", "title": "Subscribed"}]
    candidates = [{"candidate_id": "tmdb:2", "title": "Candidate"}]
    archive = {"entries": [{"candidate_id": "tmdb:3"}]}
    weights = {"weights": {"rating_weight": 0.7}, "media_types": ["movie"]}
    previous_profile = {"summary": "Old", "tags": ["悬疑"]}
    context = build_trusted_context(
        username="alice",
        run_id="run-1",
        subscriptions=subscriptions,
        candidates=candidates,
        archive_feedback=archive,
        weights=weights,
        previous_profile=previous_profile,
    )
    subscriptions[0]["title"] = "mutated"
    candidates.append({"candidate_id": "tmdb:999"})
    previous_profile["summary"] = "mutated"

    outputs = {
        tool.name: json.loads(asyncio.run(tool.run())) for tool in _tools_with_context(context)
    }

    assert outputs["read_agentrank_subscriptions"]["username"] == "alice"
    assert outputs["read_agentrank_subscriptions"]["run_id"] == "run-1"
    assert outputs["read_agentrank_subscriptions"]["subscriptions"][0]["title"] == "Subscribed"
    assert outputs["read_agentrank_subscriptions"]["previous_profile"] == {
        "summary": "Old",
        "tags": ["悬疑"],
    }
    assert len(outputs["read_agentrank_candidates"]["candidates"]) == 1
    assert outputs["read_agentrank_archive_feedback"]["archive_feedback"] == archive
    assert outputs["read_agentrank_weights"]["weights"] == weights


def test_tools_reject_missing_or_wrong_trusted_context():
    """General Agent sessions cannot use AgentRank tools without adapter injection."""
    for tool_class in AGENT_TOOL_CLASSES:
        tool = tool_class(session_id="session", user_id="system")
        for agent_context in ({}, {TRUSTED_CONTEXT_KEY: {"username": "alice"}}):
            tool.set_agent_context(agent_context)
            try:
                asyncio.run(tool.run())
            except PermissionError as error:
                assert "trusted" in str(error).lower()
            else:
                raise AssertionError(f"{tool.name} accepted an untrusted context")


def test_agent_tool_sources_have_no_side_effect_dependencies():
    """Tool modules may transform trusted data but cannot import mutation surfaces."""
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PLUGIN_DIR / "agent_tools").glob("*.py")
    )
    forbidden = {
        "SubscribeChain",
        "save_data",
        "del_data",
        "write_text",
        "write_bytes",
        "update_config",
        "systemconfig",
        "post_message",
        "send_message",
    }
    assert [name for name in sorted(forbidden) if name in source] == []
