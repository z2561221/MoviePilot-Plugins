"""AgentRank frontend API, shared state, and Config source contracts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = ROOT / "plugins.v2" / "agentrank" / "frontend" / "src" / "components"
API = COMPONENTS / "api.js"
STATE = COMPONENTS / "useAgentRankState.js"
CONFIG = COMPONENTS / "Config.vue"


def test_frontend_api_uses_injected_bearer_client_without_token_or_fetch():
    """All browser calls go through the injected MoviePilot API client."""
    source = API.read_text(encoding="utf-8")
    assert "api.get(" in source
    assert "api.post(" in source
    assert "params" in source
    assert "fetch(" not in source
    assert "API_TOKEN" not in source
    assert "token=" not in source


def test_shared_state_covers_all_read_and_mutation_surfaces():
    """One composable owns username selection, data loading, and actions."""
    assert STATE.exists()
    source = STATE.read_text(encoding="utf-8")
    for path in (
        "config/options",
        "overview",
        "board",
        "profile",
        "run-history",
        "refresh",
        "archive",
        "restore",
        "archive/delete",
        "profile/clear",
        "subscribe",
    ):
        assert path in source
    assert "selectedUser" in source
    assert "loading" in source
    assert "error" in source


def test_config_is_the_authoritative_complete_weight_write_surface():
    """Config exposes all specified controls and emits the complete form."""
    source = CONFIG.read_text(encoding="utf-8")
    for tab in (
        "运行总览",
        "基础设置",
        "发现来源",
        "权重设置",
        "条件筛选",
        "榜单行为",
        "高级选项",
    ):
        assert tab in source
    for weight in (
        "type_weight",
        "theme_weight",
        "actor_weight",
        "director_weight",
        "region_weight",
        "year_weight",
        "rating_weight",
        "heat_weight",
        "freshness_weight",
        "similarity_weight",
    ):
        assert weight in source
    for discovery_source in (
        "douban",
        "tmdb_movies",
        "tmdb_tv",
        "bangumi",
        "extensions",
    ):
        assert discovery_source in source
    assert "VCronField" in source
    assert "initialConfig" in source
    assert "emit('save'" in source
    assert "auto_subscribe_top_n" in source
    assert "candidate_pool_size" in source
    assert "confidence_threshold" in source
    assert "exclude_keywords" in source


def test_config_has_stable_desktop_and_dedicated_mobile_layout():
    """Config follows the shared stable-window and mobile navigation pattern."""
    source = CONFIG.read_text(encoding="utf-8")
    assert "height: clamp(760px" in source
    assert "width: 160px" in source
    assert "@media (max-width: 760px)" in source
    assert "overflow-x: auto" in source
    assert "min-width: max-content" in source
    assert "ar-config__window--overview" in source
