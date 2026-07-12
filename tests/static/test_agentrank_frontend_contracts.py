"""AgentRank frontend API, responsive UI, and federation asset contracts."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = ROOT / "plugins.v2" / "agentrank" / "frontend" / "src" / "components"
API = COMPONENTS / "api.js"
STATE = COMPONENTS / "useAgentRankState.js"
CONFIG = COMPONENTS / "Config.vue"
APP_PAGE = COMPONENTS / "AppPage.vue"
PAGE = COMPONENTS / "Page.vue"
DASHBOARD = COMPONENTS / "Dashboard.vue"
FRONTEND = ROOT / "plugins.v2" / "agentrank" / "frontend"
DIST = ROOT / "plugins.v2" / "agentrank" / "dist"
ASSETS = DIST / "assets"


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


def test_config_advanced_navigation_uses_a_host_supported_mdi_icon():
    """Advanced settings must not reference an icon absent from MP's Iconify MDI set."""
    source = CONFIG.read_text(encoding="utf-8")
    assert "mdi-shield-check-outline" in source
    assert "mdi-shield-cog-outline" not in source


def test_app_page_is_a_vertical_top_ten_with_complete_user_actions():
    """The recommendation center implements the specified single-board experience."""
    source = APP_PAGE.read_text(encoding="utf-8")
    assert "useAgentRankState" in source
    assert "Top 10" in source
    assert "selectedUser" in source
    assert "clearProfile" in source
    assert "subscribe" in source
    assert "archive" in source
    assert "restore" in source
    assert "画像摘要" in source
    assert "权重摘要" in source
    assert "最近归档" in source
    assert "运行历史" in source
    assert "clearDialog" in source
    assert "grid-template-columns: minmax(0, 1fr)" in source
    assert "@media (max-width: 760px)" in source
    assert "min-width: 40px" in source or "min-height: 40px" in source


def test_page_has_five_management_tabs_and_backend_history_paging():
    """The detail dialog covers recommendation, profile, weights, archive, and history."""
    source = PAGE.read_text(encoding="utf-8")
    for title in ("推荐榜单", "用户画像", "权重配置", "归档区", "运行历史"):
        assert title in source
    assert "useAgentRankState" in source
    assert "subscribe" in source
    assert "archive" in source
    assert "restore" in source
    assert "deleteArchive" in source
    assert "clearDialog" in source
    assert "historyPage" in source
    assert "page_size" in source
    assert "emit('close')" in source
    assert "emit('switch')" in source


def test_dashboard_is_a_lightweight_vertical_top_five():
    """Dashboard stays compact and links to the complete recommendation center."""
    source = DASHBOARD.read_text(encoding="utf-8")
    assert "Top 5" in source
    assert ".slice(0, 5)" in source
    assert "flex-direction: column" in source
    assert "allowRefresh" in source
    assert "mdi-open-in-new" in source
    assert "username" not in source.lower()


def test_primary_surface_exposes_the_complete_semantic_state_matrix():
    """Every backend board state has a visible label and recovery message."""
    source = APP_PAGE.read_text(encoding="utf-8")
    expected = {
        "idle": "待生成",
        "running": "运行中",
        "success": "已完成",
        "sample_insufficient": "样本不足",
        "candidate_insufficient": "候选不足",
        "recommendation_incomplete": "榜单不足",
        "agent_failed": "Agent失败",
        "validation_failed": "校验失败",
        "subscription_partial_failed": "部分订阅失败",
    }
    for state, label in expected.items():
        assert state in source
        assert label in source


def test_icon_buttons_are_named_and_all_surfaces_keep_touch_targets():
    """Icon-only actions remain screen-reader named and at least 40 by 40 pixels."""
    for component in (APP_PAGE, PAGE, DASHBOARD):
        source = component.read_text(encoding="utf-8")
        icon_buttons = re.findall(r"<VBtn\b(?=[^>]*\sicon(?:=|\s))[^>]*>", source)
        assert icon_buttons, component.name
        assert all("aria-label=" in button for button in icon_buttons), component.name
        assert "min-width: 40px" in source, component.name
        assert "min-height: 40px" in source, component.name


def test_responsive_surfaces_have_390px_and_page_overflow_guards():
    """Named mobile viewport gets an explicit fallback and no page-level x overflow."""
    for component in (CONFIG, APP_PAGE, PAGE):
        source = component.read_text(encoding="utf-8")
        assert "@media (max-width: 390px)" in source, component.name
        assert "overflow-x: hidden" in source, component.name


def test_federation_exposes_and_all_built_asset_references_are_coherent():
    """The four exposes and the index entry resolve to one closed, stale-free asset graph."""
    vite = (FRONTEND / "vite.config.js").read_text(encoding="utf-8")
    for expose in ("./Config", "./Dashboard", "./Page", "./AppPage"):
        assert expose in vite

    roots = [DIST / "index.html", ASSETS / "remoteEntry.js"]
    assert all(path.exists() for path in roots)
    referenced = {ASSETS / "remoteEntry.js"}
    pending = list(roots)
    visited = set()
    pattern = re.compile(
        r"(?:\./|/assets/)([^\"'()]+\.(?:js|css))|"
        r"[\"']([^\"']+\.css)[\"']"
    )

    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        source = current.read_text(encoding="utf-8")
        for match in pattern.findall(source):
            name = next(part for part in match if part)
            asset = ASSETS / name
            if not asset.exists():
                asset = ASSETS / Path(name).name
            assert asset.exists(), f"missing asset referenced by {current.name}: {name}"
            if asset not in referenced:
                referenced.add(asset)
                if asset.suffix == ".js":
                    pending.append(asset)

    built_assets = set(ASSETS.rglob("*.js")) | set(ASSETS.rglob("*.css"))
    assert built_assets == referenced
