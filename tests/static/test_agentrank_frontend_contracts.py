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
ACTIONS = COMPONENTS / "RecommendationActions.vue"
ANALYSIS_DIALOG = COMPONENTS / "AgentAnalysisDialog.vue"
COMMENT_DIALOG = COMPONENTS / "FeedbackCommentDialog.vue"
CRITIC_DIALOG = COMPONENTS / "CriticChatDialog.vue"
PENDING_DIALOG = COMPONENTS / "PendingConfirmations.vue"
FRONTEND = ROOT / "plugins.v2" / "agentrank" / "frontend"
PREVIEW = FRONTEND / "src" / "PreviewApp.vue"
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


def test_shared_state_owns_profile_id_selection_reads_and_actions():
    """One composable owns Emby identity selection, data loading, and actions."""
    assert STATE.exists()
    source = STATE.read_text(encoding="utf-8")
    for path in (
        "config/options",
        "overview",
        "board",
        "profile",
        "run-history",
        "refresh",
        "feedback",
        "analysis",
        "analysis/comment",
        "conversation",
        "conversation/messages",
        "conversation/messages/retry",
        "conversation/commands/respond",
        "pending",
        "pending/respond",
        "attribution",
        "attribution/verify",
        "data/export",
        "data/reset/learning",
        "data/reset/full/prepare",
        "data/reset/full",
        "archive",
        "restore",
        "archive/delete",
        "profile/clear",
        "profile/tags",
        "subscribe",
    ):
        assert path in source
    assert "selectedProfileId" in source
    assert "identityOptions" in source
    assert "profile_id: targetProfile" in source
    assert "const targetProfile = activeProfileScope()" in source
    assert "{ username:" not in source
    assert "loading" in source
    assert "error" in source
    assert "if (result?.board_changed)" in source
    assert "await refreshProfileAfterMutation(targetProfile)" in source


def test_shared_state_tracks_every_async_operation_with_visible_retry():
    """共享状态层为读取与写入统一保留 loading、error 和 retry。"""
    source = STATE.read_text(encoding="utf-8")
    for marker in (
        "const operations = reactive({})",
        "function operationState(key)",
        "async function runOperation(key, task, retry, settings = {})",
        "async function retryOperation(key)",
        "state.loading = true",
        "state.error = err",
        "state.retry = typeof retry === 'function' ? retry : null",
        "const isCurrent = () => state.sequence === sequence",
        "if (isCurrent() && selectedProfileId.value === targetProfile)",
        "state.sequence += 1",
        "board.value = emptyBoard(target, username)",
        "history.value = []",
        "watch(selectedProfileId, value => ensureSecondaryScope(value), { flush: 'sync' })",
        "Promise.allSettled",
        "ensureSecondaryScope",
    ):
        assert marker in source
    assert "catch(() => {})" not in source
    assert "catch(() => { })" not in source
    for state_name in (
        "analyses",
        "activity",
        "conversation",
        "pendingCenter",
        "attribution",
        "exportedData",
        "fullResetConfirmation",
    ):
        assert state_name in source


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
    ):
        assert discovery_source in source
    assert "扩展来源" not in source
    assert "extensions: true" not in source
    assert "VCronField" in source
    assert "initialConfig" in source
    assert "emit('save'" in source
    assert "auto_subscribe_top_n" in source
    assert "candidate_pool_size" in source
    assert "confidence_threshold" in source
    assert "exclude_keywords" in source
    assert "emby_identities" in source
    assert "default_profile_id" in source
    for legacy in (
        "form.users",
        "form.default_user",
        "profile_scope",
        "subscription_sample_limit",
        "playback_source_mode",
        "playback_user_map",
    ):
        assert legacy not in source


def test_config_runtime_overview_exposes_identity_gate_and_frozen_pool_evidence():
    """运行总览展示硬依赖、画像、检索计划和冻结候选证据链。"""
    source = CONFIG.read_text(encoding="utf-8")
    for marker in (
        "Emby 画像身份",
        "Playback Reporting 硬依赖未满足",
        "profile_id: selectedProfileId.value",
        "sample_count",
        "mapped_count",
        "unmapped_count",
        "映射率",
        "schema_version",
        "retrieval_resolution_version",
        "ranking_tags",
        "candidate_source_counts",
        "candidate_exclusion_counts",
        "source_errors",
    ):
        assert marker in source
    assert "currentEnablement && !currentEnablement.allowed" in source
    assert "['ready', 'cached'].includes(currentPlayback?.status)" in source
    for step in (
        "探测依赖",
        "冻结播放",
        "生成画像",
        "冻结候选",
        "池内排序",
        "校验保存",
    ):
        assert step in source


def test_config_data_governance_and_critic_prompt_are_complete_and_guarded():
    """配置页完整接入访问、保留、导出、双重置和影评师扩展提示词。"""
    source = CONFIG.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    for tab in ("运行设置", "访问控制", "数据管理", "提示设置"):
        assert tab in source
    for field in (
        "profile_access_map",
        "candidate_snapshot_limit",
        "feedback_event_limit",
        "feedback_queue_limit",
        "conversation_message_limit",
        "attribution_record_limit",
        "analysis_record_limit",
        "critic_prompt",
    ):
        assert field in source
    for path in (
        "data/export",
        "data/reset/learning",
        "data/reset/full/prepare",
        "data/reset/full",
    ):
        assert path in source
    assert "getHostApi(props.api, 'user/')" in source
    assert "export async function getHostApi" in api
    assert "fullResetPhrase.value !== '彻底重置'" in source
    assert "confirmation_token" in source
    assert "MoviePilot 订阅和媒体库未受影响" in source
    assert "v-model=\"promptEditor.draft\"" in source


def test_ranking_surfaces_and_preview_use_emby_identity_contracts_only():
    """Page/AppPage/Dashboard 与预览均以 profile_id 运行并只显示安全名称。"""
    state = STATE.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    app_page = APP_PAGE.read_text(encoding="utf-8")
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    preview = PREVIEW.read_text(encoding="utf-8")
    assert "selectedProfileId" in state
    assert "profiles: new Map()" in state
    assert "profile_id: targetProfile" in state
    assert "retryForProfile" in state
    assert "Emby 用户" in page and "state.selectedUsername.value" in page
    assert '<Page' in app_page and ':show-close="false"' in app_page
    assert "default_profile_id" in dashboard
    assert "emby_identities: identities" in preview
    assert "playback_count: 36" in preview
    assert "function dataFor(path, params = {})" in preview
    assert "params.profile_id" in preview
    for source in (state, page, app_page, dashboard, preview):
        for legacy in (
            "selectedUser.value",
            "const selectedUser =",
            "loadUserData",
            "default_user",
            "available_users",
            "playback_user_map",
            "subscription_count",
        ):
            assert legacy not in source


def test_preview_fixture_persists_profile_tag_archives_for_browser_acceptance():
    """Preview fake API mirrors the production archive-and-restore semantics."""
    preview = PREVIEW.read_text(encoding="utf-8")
    assert "if (path.endsWith('profile/tags'))" in preview
    assert "archived_profile_tags: []" in preview
    assert "profile.archived_profile_tags.push" in preview
    assert "profile.archived_profile_tags = profile.archived_profile_tags.filter" in preview


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


def test_app_page_is_a_thin_host_shell_reusing_the_complete_page():
    """发现页只适配宿主设置，并完整复用 Page 业务能力。"""
    source = APP_PAGE.read_text(encoding="utf-8")
    assert "import Page from './Page.vue'" in source
    assert "import Config from './Config.vue'" in source
    assert '<Page' in source
    assert ':show-close="false"' in source
    assert '@switch="openSettings"' in source
    assert ':key="pageKey"' in source
    assert "pageKey.value += 1" in source
    assert "savePluginConfig" in source
    for duplicated in (
        "useAgentRankState",
        "RecommendationActions",
        "AgentAnalysisDialog",
        "CriticChatDialog",
        "PendingConfirmations",
        "item.reason",
    ):
        assert duplicated not in source


def test_page_has_four_management_tabs_editable_tags_and_backend_history_paging():
    """The detail dialog covers ranking, editable profile, archive, and history."""
    source = PAGE.read_text(encoding="utf-8")
    for title in ("推荐榜单", "用户画像", "忽略归档", "运行历史"):
        assert title in source
    assert "useAgentRankState" in source
    assert "subscribe" in source
    assert "archive" in source
    assert "restore" in source
    assert "deleteArchive" in source
    assert "updateProfileTag" in source
    assert "closable" in source
    assert "historyPage" in source
    assert "page_size" in source
    assert "emit('close')" in source
    assert "emit('switch'," in source
    assert "item.poster_path" in source
    assert "mdi-image-off-outline" in source
    assert "statusMetaFor(run.status)" in source
    assert "white-space: normal" in source
    assert "overflow-wrap: anywhere" in source
    assert "item.reason" in source
    assert "#error" in source


def test_detail_mobile_navigation_matches_download_center_and_wraps():
    """详情页复用下载中心导航结构，并在移动端完整换行。"""
    source = PAGE.read_text(encoding="utf-8")
    assert '<VList density="compact" nav class="ar-page__tab-list">' in source
    assert 'rounded="lg"' in source
    assert ".ar-page__tab-list { display: flex; flex-wrap: nowrap" in source
    assert "min-width: max-content" in source
    assert "padding: 8px 12px !important" in source
    assert ".ar-page__tabs { min-height: 40px; overflow-x: hidden; }" in source
    assert "width: 100%; min-width: 0; flex-wrap: wrap" in source
    assert "flex: 1 1 calc(50% - 3px); min-width: 0" in source
    assert "functionTabsExpanded" not in source
    assert "toggleFunctionTabs" not in source


def test_page_mobile_runtime_and_copy_layout_stay_readable():
    """Idle status is removed and mobile recommendation copy wraps without toggles."""
    source = PAGE.read_text(encoding="utf-8")
    assert 'v-if="state.isRunning.value"' in source
    assert "运行就绪" not in source
    assert ".ar-page__rank-copy { grid-template-columns: 34px minmax(0, 1fr); }" in source
    assert ".ar-page__copy-toggle" not in source
    assert "toggleCopy(item, 'reason')" not in source
    assert "toggleCopy(item, 'summary')" not in source
    assert "display: block; overflow: visible; -webkit-line-clamp: initial;" in source


def test_discovery_inherits_full_mobile_copy_layout_from_page():
    """发现页通过同一 Page 获得完整换行和无展开控件的移动布局。"""
    app_page = APP_PAGE.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    assert '<Page' in app_page
    assert ".ar-page__rank-copy { grid-template-columns: 34px minmax(0, 1fr); }" in page
    assert ".ar-page__copy-toggle" not in page
    assert "toggleCopy(item, 'reason')" not in page
    assert "toggleCopy(item, 'summary')" not in page
    assert "display: block; overflow: visible; -webkit-line-clamp: initial;" in page


def test_analysis_comment_chat_and_pending_ui_are_reachable_and_safe():
    """结构化分析、评论、对话和待处理从详情及复用发现页均可到达。"""
    page = PAGE.read_text(encoding="utf-8")
    app_page = APP_PAGE.read_text(encoding="utf-8")
    for component in (ANALYSIS_DIALOG, COMMENT_DIALOG, CRITIC_DIALOG, PENDING_DIALOG):
        assert component.exists(), component.name
    for name in (
        "AgentAnalysisDialog",
        "FeedbackCommentDialog",
        "CriticChatDialog",
        "PendingConfirmations",
    ):
        assert name in page
        assert name not in app_page
    assert "openAnalysis(item)" in page
    assert "打开 CinePilot Agent" in page
    assert "打开待处理中心" in page
    assert "state.loadPendingCenter()" in page
    assert '<Page' in app_page
    analysis = ANALYSIS_DIALOG.read_text(encoding="utf-8")
    assert "positive_evidence" in analysis
    assert "counter_evidence" in analysis
    assert "uncertainties" in analysis
    assert "comment-edit-outline" in analysis
    for forbidden in ("思维链", "chain of thought", "prompt_fingerprint", "system prompt"):
        assert forbidden not in analysis.lower()


def test_critic_and_pending_dialogs_preserve_deferred_work_and_use_mobile_fullscreen():
    """移动端对话全屏，失败可重试，待处理动作对称且没有提醒。"""
    critic = CRITIC_DIALOG.read_text(encoding="utf-8")
    pending = PENDING_DIALOG.read_text(encoding="utf-8")
    comment = COMMENT_DIALOG.read_text(encoding="utf-8")
    analysis = ANALYSIS_DIALOG.read_text(encoding="utf-8")
    for source in (critic, pending, comment, analysis):
        assert "useDisplay" in source
        assert ':fullscreen="smAndDown"' in source
        assert "@media (max-width: 760px)" in source
    for marker in (
        "sendConversationMessage",
        "retryConversationMessage",
        "respondConversationCommand",
        "pending_confirmation",
        "draft.value",
    ):
        assert marker in critic
    for marker in (
        "respondPending",
        "answerQuestion",
        "'reject'",
        "'confirm'",
        "'close'",
        "提交回答",
        "关闭问询",
        "确认采纳",
        "拒绝采纳",
        "确认执行",
        "拒绝执行",
    ):
        assert marker in pending
    for removed in ("in_1_day", "in_3_days", "in_7_days", "never", "不提醒"):
        assert removed not in pending
    assert "commentOnAnalysis" in comment
    assert "localError" in critic and "localError" in pending


def test_dashboard_is_a_lightweight_vertical_top_five():
    """Dashboard stays compact and links to the complete recommendation center."""
    source = DASHBOARD.read_text(encoding="utf-8")
    assert "精选前5名" in source
    assert "Top 5" not in source
    assert ".slice(0, 5)" in source
    assert "flex-direction: column" in source
    assert "allowRefresh" in source
    assert "mdi-open-in-new" in source
    assert "fullBoardHref" in source
    assert "#/plugin-app/" in source
    assert "window.location.hash = fullBoardHref.value.slice(1)" in source
    assert '@click="openFullBoard"' in source
    assert "emit('action'" not in source
    assert "username" not in source.lower()
    assert "item.poster_path" in source
    assert "ar-dashboard__poster" in source
    assert "#error" in source
    assert "item.reason" in source


def test_all_ranking_surfaces_use_feedback_icons_and_host_native_subscribe():
    """榜单共享同尺寸文字赞踩，并把电视剧订阅交给宿主原生抽屉。"""
    actions = ACTIONS.read_text(encoding="utf-8")
    for label in ("订阅", "TMDB", "忽略", "喜欢", "不喜欢"):
        assert f'<span class="ar-actions__label">{label}</span>' in actions
        assert actions.count(f'<span class="ar-actions__label">{label}</span>') == 1
    for forbidden in ("豆瓣", "Bgm", "搜索豆瓣", "doubanSearchText", "sourceLabel"):
        assert forbidden not in actions
    assert "nativeSubscribe" in actions
    assert "moviepilot:nativeSubscribe" in actions
    assert "PERMISSION_DENIED" in actions
    for icon in (
        "mdi-thumb-up-outline",
        "mdi-thumb-up",
        "mdi-thumb-down-outline",
        "mdi-thumb-down",
    ):
        assert icon in actions
    assert ":aria-pressed=" in actions
    assert actions.count('variant="tonal"') == 5
    assert ".ar-actions__button { flex: 0 0 auto; min-width: 68px; min-height: 40px;" in actions
    for component_path in (DASHBOARD, PAGE):
        source = component_path.read_text(encoding="utf-8")
        assert ".slice(0, 5)" in source
        assert "nativeSubscribe" in source
        assert "@like=" in source
        assert "@dislike=" in source
        assert "置信度" not in source
        assert "{{ item.support?.percentage ?? '—' }}" in source
        assert "{{ item.support ? '%' : '' }}" in source
    assert '<Page' in APP_PAGE.read_text(encoding="utf-8")
    for component_path, support_class in (
        (DASHBOARD, "ar-dashboard__support"),
        (PAGE, "ar-page__support"),
    ):
        support_rule = next(
            line for line in component_path.read_text(encoding="utf-8").splitlines()
            if line.startswith(f".{support_class} {{")
        )
        assert "margin-left: auto" in support_rule
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    assert ".ar-dashboard__controls :deep(.ar-actions) { order: 1; }" in dashboard
    assert ".ar-dashboard__support { order: 2; margin-left: auto; }" in dashboard


def test_primary_surface_exposes_the_complete_semantic_state_matrix():
    """Every backend board state has a visible label and recovery message."""
    source = PAGE.read_text(encoding="utf-8")
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
    for component in (PAGE, DASHBOARD):
        source = component.read_text(encoding="utf-8")
        icon_buttons = re.findall(r"<VBtn\b(?=[^>]*\sicon(?:=|\s))[^>]*>", source)
        assert icon_buttons, component.name
        assert all("aria-label=" in button for button in icon_buttons), component.name
        assert "min-width: 40px" in source, component.name
        assert "min-height: 40px" in source, component.name
    app_page = APP_PAGE.read_text(encoding="utf-8")
    assert '<Page' in app_page
    assert re.findall(r"<VBtn\b(?=[^>]*\sicon(?:=|\s))[^>]*>", app_page) == []


def test_responsive_surfaces_have_390px_and_page_overflow_guards():
    """Named mobile viewport gets an explicit fallback and no page-level x overflow."""
    for component in (CONFIG, PAGE):
        source = component.read_text(encoding="utf-8")
        assert "@media (max-width: 390px)" in source, component.name
        assert "overflow-x: hidden" in source, component.name
    app_page = APP_PAGE.read_text(encoding="utf-8")
    assert "width: 100%" in app_page and "min-width: 0" in app_page
    assert '<Page' in app_page


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
    shared_assets = {
        asset
        for asset in built_assets
        if asset.relative_to(ASSETS).parts[0].startswith("__federation_shared_")
    }
    assert len(shared_assets) <= 1
    referenced.update(shared_assets)
    assert built_assets == referenced
