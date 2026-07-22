"""Executable red gates for AgentRank domain and restricted Agent contracts."""

import ast
from pathlib import Path

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
EXPECTED_TOOL_NAMES = {
    "read_agentrank_candidates",
    "read_agentrank_archive_feedback",
    "read_agentrank_weights",
    "read_agentrank_playback",
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
        "model/retrieval.py": {"RetrievalFilters", "RetrievalPlan"},
        "model/board.py": {"RecommendationBoard"},
        "model/archive.py": {"ArchiveFeedback"},
        "model/run.py": {"RecommendationRun"},
        "storage/repository.py": {"AgentRankRepository"},
    }
    for relative_path, expected_classes in required_modules.items():
        tree = ast.parse(_source(relative_path))
        classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
        assert expected_classes <= classes


def test_agent_tool_registry_is_an_exact_read_only_whitelist():
    """The Agent tool registry contains exactly the four trusted read tools."""
    source = _source("agent_tools/registry.py")
    assert _assigned_string_collection(source, "ALLOWED_AGENT_TOOL_NAMES") == EXPECTED_TOOL_NAMES
    assert "AGENT_TOOL_CLASSES" in source


def test_subscription_profile_input_chain_is_removed():
    """订阅样本画像服务、模型和编排依赖不得回到生产链。"""
    assert not (PLUGIN_DIR / "service" / "profile_input.py").exists()
    assert not (PLUGIN_DIR / "model" / "subscription.py").exists()
    for relative_path in (
        "service/recommendation.py",
        "service/runtime.py",
        "agent_tools/tools.py",
        "agent_tools/registry.py",
    ):
        source = _source(relative_path)
        for forbidden in (
            "ProfileInputService",
            "ProfileInputResult",
            "SubscriptionSample",
            "read_agentrank_subscriptions",
        ):
            assert forbidden not in source


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

    assert "async def _create_agent" in source
    assert "async def _initialize_llm" in source
    assert "LLMHelper.get_llm" in source
    assert "settings.LLM_PROVIDER" in source
    assert "_send_agent_tokens_usage_event" in source
    assert "AgentLLMProvider" not in source
    assert "_resolve_llm_runtime_config" not in source
    assert "middleware=[]" in source
    assert "tools=self._initialize_tools()" in source
    for forbidden_graph_extension in (
        "_initialize_mcp_tools",
        "_initialize_subagent_tools",
        "SkillsMiddleware",
        "create_subagent_middlewares",
        "JobsMiddleware",
        "MemoryMiddleware",
    ):
        assert forbidden_graph_extension not in source


def test_agent_tools_take_username_and_run_id_only_from_trusted_context():
    """Tool call schemas must not let the model choose another user or run."""
    source = _source("agent_tools/context.py")
    assert "username" in source
    assert "run_id" in source
    assert "trusted_context" in source
    tools_source = _source("agent_tools/tools.py")
    assert "args_schema" in tools_source
    assert "save_data" not in tools_source
    assert "SubscribeChain" not in tools_source
    assert "post_message" not in tools_source


def test_runtime_injects_controlled_tmdb_keyword_resolution():
    """运行时通过宿主适配器注入唯一关键词解析，不在 service 直接发 HTTP。"""
    runtime_source = _source("service/runtime.py")
    resolver_source = _source("service/keyword_resolution.py")
    adapter_source = _source("adapter/tmdb_keyword.py")
    assert "ControlledRetrievalPlanResolver" in runtime_source
    assert "TmdbKeywordAdapter().search" in runtime_source
    assert "TmdbApi" not in resolver_source
    assert "TmdbApi" in adapter_source
    assert "requests" not in adapter_source


def test_discovery_provider_contract_has_global_raw_cap_and_recipe_boundary():
    """发现 Provider 必须保留 150 原始上限与 recipe 观测边界。"""
    source = _source("adapter/discovery.py")
    assert "DEFAULT_RAW_FETCH_LIMIT = 150" in source
    assert "class ProviderRequest" in source
    assert "class MoviePilotProvider" in source
    assert "request_recipes" in source
    assert "fetch_recommendations" in source
    assert "BeautifulSoup" not in source
    assert "requests.get" not in source


def test_layered_recall_contract_has_fixed_default_quotas_and_minimum_gate():
    """分层召回必须固定默认配额并在排序前执行 20 条门槛。"""
    discovery = _source("adapter/discovery.py")
    candidate = _source("service/candidate.py")
    recommendation = _source("service/recommendation.py")
    for layer, quota in {
        '"exact": 25': 25,
        '"relaxed": 10': 10,
        '"adjacent": 5': 5,
        '"public_recommend": 10': 10,
    }.items():
        assert layer in discovery
        assert quota > 0
    assert "def fetch_layered(" in discovery
    assert 'marked["recall_pass"] = recall_pass' in discovery
    assert "DEFAULT_MINIMUM_FROZEN_CANDIDATES = 20" in candidate
    assert "len(candidates) < minimum_frozen_candidates" in recommendation


def test_sidebar_entry_respects_discovery_page_switch():
    """侧栏发现入口必须同时受插件状态和独立开关控制。"""
    source = _source("__init__.py")
    assert 'self._config.get("discovery_page_enabled", True)' in source
