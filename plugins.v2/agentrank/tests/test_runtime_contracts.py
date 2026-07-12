"""Executable red gates for AgentRank domain and restricted Agent contracts."""

import ast
from pathlib import Path

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
EXPECTED_TOOL_NAMES = {
    "read_agentrank_subscriptions",
    "read_agentrank_candidates",
    "read_agentrank_archive_feedback",
    "read_agentrank_weights",
}
FORBIDDEN_AGENT_CAPABILITIES = {
    "subscribe",
    "subscription_create",
    "write_file",
    "delete_file",
    "system_setting",
    "update_setting",
    "send_message",
    "post_message",
}


def _source(relative_path: str) -> str:
    path = PLUGIN_DIR / relative_path
    assert path.exists(), f"required contract module is not implemented: {relative_path}"
    return path.read_text(encoding="utf-8")


def _assigned_string_collection(source: str, variable_name: str) -> set[str]:
    tree = ast.parse(source)
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        if not any(isinstance(target, ast.Name) and target.id == variable_name for target in targets):
            continue
        value = ast.literal_eval(statement.value)
        return set(value)
    raise AssertionError(f"{variable_name} must be a module-level literal collection")


def test_per_user_domain_and_storage_contract_exists():
    """User/run scoped domain records and the storage boundary must be explicit."""
    required_modules = {
        "model/candidate.py": {"Candidate"},
        "model/profile.py": {"UserProfile"},
        "model/board.py": {"RecommendationBoard"},
        "model/archive.py": {"ArchiveFeedback"},
        "model/run.py": {"RecommendationRun"},
        "storage/repository.py": {"AgentRankRepository"},
    }
    for relative_path, expected_classes in required_modules.items():
        tree = ast.parse(_source(relative_path))
        classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
        assert expected_classes <= classes


@pytest.mark.xfail(
    strict=True,
    reason="Phase 3 has not implemented the four read-only AgentRank tools yet",
)
def test_agent_tool_registry_is_an_exact_read_only_whitelist():
    """The Agent tool registry contains exactly the four trusted read tools."""
    source = _source("agent_tools/registry.py")
    assert _assigned_string_collection(source, "ALLOWED_AGENT_TOOL_NAMES") == EXPECTED_TOOL_NAMES
    lowered = source.lower()
    assert not (FORBIDDEN_AGENT_CAPABILITIES & set(lowered.replace("-", "_").split()))


@pytest.mark.xfail(
    strict=True,
    reason="Phase 3 has not implemented the restricted MoviePilotAgent adapter yet",
)
def test_agent_adapter_is_capture_only_and_never_loads_general_tools():
    """The ranking session uses capture-only mode and opts into its exact tool set."""
    source = _source("adapter/agent.py")
    assert "MoviePilotAgent" in source
    assert "ReplyMode.CAPTURE_ONLY" in source
    assert "ALLOWED_AGENT_TOOL_NAMES" in source
    assert "ToolFactory.get_tools()" not in source
    assert "load_all_tools" not in source
    for forbidden in FORBIDDEN_AGENT_CAPABILITIES:
        assert forbidden not in source.lower()


@pytest.mark.xfail(
    strict=True,
    reason="Phase 3 has not implemented trusted run/user Agent context yet",
)
def test_agent_tools_take_username_and_run_id_only_from_trusted_context():
    """Tool call schemas must not let the model choose another user or run."""
    source = _source("agent_tools/context.py")
    assert "username" in source
    assert "run_id" in source
    assert "trusted_context" in source
    assert '"username"' not in source.split("args_schema", 1)[-1]
    assert '"run_id"' not in source.split("args_schema", 1)[-1]
