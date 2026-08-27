"""AgentRank Vue 联邦组件静态合同测试。"""

from pathlib import Path


COMPONENT_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank" / "frontend" / "src" / "components"


def _read(name: str) -> str:
    return (COMPONENT_DIR / name).read_text(encoding="utf-8")


def test_advanced_options_and_agent_settings_expose_prompt_subtabs():
    """提示设置与 Agent 设定分别暴露对应的紧凑编辑入口。"""
    config = _read("Config.vue")
    assert "{ key: 'runtime', title: '运行参数'" in config
    assert "{ key: 'prompt', title: '提示设置'" in config
    assert "{ key: 'agent', title: 'Agent设定'" in config
    for field_name, title in (
        ("profile_prompt", "画像理解规则"),
        ("ranking_prompt", "榜单推荐策略"),
        ("copy_prompt", "推荐文案风格"),
        ("critic_prompt", "CinePilot Agent 扩展提示词"),
    ):
        assert field_name in config
        assert title in config
    for field_name, title in (
        ("agent_display_name", "显示名称"),
        ("persona_preset", "人设预设"),
        ("persona_prompt", "自定义语气"),
        ("interaction_mode", "交互模式"),
    ):
        assert field_name in config
        assert title in config
    assert config.index("Agent设定") < config.index("提示设置")
    assert 'v-model="form.agent_prompt"' not in config
    assert 'v-model="promptEditor.open"' in config
    assert 'v-model="promptEditor.draft"' in config
    assert "恢复默认" in config
    assert "取消" in config
    assert "应用" in config
    assert "保存配置" in config
    assert "固定安全规则（只读）" in config
    assert "最终榜单固定保存五条" in config
    assert "max-height: min(760px, calc(100dvh - 24px))" in config
    assert "agent_display_name: '克里斯蒂娜'" in config
    assert "persona_prompt: ''" in config
    assert "{ title: '克里斯蒂娜', value: 'default'" in config
    assert '<VIcon icon="mdi-account-voice" size="19" color="primary" />' in config
    assert "<span>Agent设定</span>" in config


def test_advanced_settings_expose_retention_export_and_two_safe_resets():
    """高级设置保留数据治理能力，并完全移除画像访问映射。"""
    config = _read("Config.vue")
    api = _read("api.js")
    preview = (COMPONENT_DIR.parent / "PreviewApp.vue").read_text(encoding="utf-8")
    for marker in (
        "数据管理",
        "candidate_snapshot_limit",
        "feedback_event_limit",
        "feedback_queue_limit",
        "conversation_message_limit",
        "attribution_record_limit",
        "analysis_record_limit",
        "data/export",
        "data/reset/learning",
        "data/reset/full/prepare",
        "data/reset/full",
        "fullResetPhrase.value !== '清空全部数据'",
        "MoviePilot 订阅和媒体库",
    ):
        assert marker in config
    for removed in (
        "访问控制",
        "profile_access_map: {}",
        "form.profile_access_map",
        "getHostApi(props.api, 'user/')",
        "超级用户始终可访问全部已配置画像",
    ):
        assert removed not in config
    assert "export async function getHostApi" not in api
    assert "moviePilotUsers" not in preview
    assert "confirmation_token: `preview-${Date.now()}`" in preview


def test_runtime_settings_exposes_discovery_page_switch_and_current_defaults():
    """运行设置可独立关闭发现页入口，并复用当前非隐私默认值。"""
    config = _read("Config.vue")
    assert 'discovery_page_enabled: true' in config
    assert 'v-model="form.discovery_page_enabled"' in config
    assert 'label="开启发现页"' in config
    assert 'schedule_enabled: true' in config
    assert "cron: '5 18 * * *'" in config
    assert "interaction_mode: 'auto'" in config
    assert 'v-model="form.interaction_mode"' in config
    assert "自动模式" in config and "正常模式" in config and "安静模式" in config
    assert 'candidate_pool_size: 15' in config
    assert 'playback_recent_days: 90' in config


def test_runtime_overview_retrieval_plan_wraps_without_clipping():
    """检索计划必须自适应换行，不能以固定高度隐藏过滤条件。"""
    config = _read("Config.vue")
    metric_rule = config.split(".ar-config__metric-list {", 1)[1].split("}", 1)[0]

    assert "flex-wrap: wrap" in metric_rule
    assert "max-height" not in metric_rule
    assert "overflow: hidden" not in metric_rule


def test_frontend_default_prompt_exposes_evidence_bounded_motivation_signals():
    """前端默认提示词展示受证据和隐私边界约束的观看动机协议。"""
    config = _read("Config.vue")
    for phrase in (
        "情绪体验、认知满足、叙事投入、熟悉与新奇的平衡、节奏与完成感",
        "至少两条相互独立的播放证据",
        "单一样本不得形成稳定结论",
        "弃看只能作为弱负向信号",
        "不得推断人格、焦虑、孤独、疾病、创伤",
        "观看动机只能作为软排序信号",
        "不输出心理诊断或心理学术语",
    ):
        assert phrase in config


def test_basic_settings_selects_stable_emby_identities_for_run_once():
    """基础设置以 Emby 实例、用户和内容库三级选择保存稳定身份。"""
    config = _read("Config.vue")
    assert 'onlyonce: false' in config
    assert 'emby_identities: []' in config
    assert "default_profile_id: ''" in config
    assert 'v-model="selectedServerName"' in config
    assert 'label="媒体库"' in config
    assert 'v-model="selectedUserProfileId"' in config
    assert 'label="用户"' in config
    assert 'v-model="selectedLibraryIds"' in config
    assert 'label="内容库筛选"' in config
    assert 'v-model="form.onlyonce"' in config
    assert 'label="立即运行"' in config
    assert "!form.emby_identities.length" in config
    assert "只同步所选用户在所选内容库" in config
    for legacy in ("form.users", "form.default_user", "playback_user_map"):
        assert legacy not in config


def test_playback_settings_enforce_reporting_and_sync_by_profile_id():
    """配置页明确 Playback Reporting 硬阻断且所有动作使用 profile_id。"""
    config = _read("Config.vue")
    assert "playback_enabled: true" in config
    assert "form.playback_enabled = true" in config
    assert 'v-model="form.playback_enabled"' not in config
    assert "Playback Reporting" in config
    assert "Playback Reporting 硬依赖未满足" in config
    assert "插件无法开启" in config
    assert "postPluginApi(props.api, 'playback/sync'" in config
    assert "{ profile_id: selectedProfileId.value }" in config
    assert "playback_source_mode" not in config
    assert "playback_user_map" not in config
    assert "不会切换到其他画像来源" in config
    assert "Emby 原生" not in config


def test_discovery_sources_and_weights_are_agent_owned():
    """配置页不再暴露发现来源或人工权重写入口。"""
    config = _read("Config.vue")
    assert "sourceOptions" not in config
    assert "选择 MoviePilot 内置发现来源" not in config
    assert "发现来源" not in config
    assert "权重设置" not in config
    assert "weightDefs" not in config
    assert "retrieval_trace" in config
    assert "本轮检索轨迹" in config
    assert "明确限制" in config
    assert "受控放宽顺序" in config
    assert "candidate_layer_counts" in config
    assert "candidate_processing_counts" in config
    assert "本轮判断依据" in config
    assert "主要证据维度" in config
    assert "候选事实来源" in config
    assert "Agent策划检索" in config


def test_profile_update_mode_describes_incremental_semantics():
    """画像更新以智能更新和每轮重建两个对称模式呈现。"""
    config = _read("Config.vue")
    assert 'v-model="profileUpdateMode"' in config
    assert 'value="smart"' in config
    assert 'value="rebuild"' in config
    assert "智能更新" in config
    assert "每轮重建" in config


def test_discovery_page_is_a_thin_host_shell_over_the_shared_page():
    """发现页只适配宿主设置弹窗，完整业务能力复用同一个 Page。"""
    app_page = _read("AppPage.vue")
    assert "import Page from './Page.vue'" in app_page
    assert "<Page" in app_page
    assert ':show-close="false"' in app_page
    assert '@switch="openSettings"' in app_page
    assert "useAgentRankState" not in app_page
    assert "RecommendationActions" not in app_page
    assert "AgentAnalysisDialog" not in app_page
    assert "CriticChatDialog" not in app_page
    assert "PendingConfirmations" not in app_page


def test_all_ranking_surfaces_use_feedback_icons_and_three_labeled_actions():
    """三处榜单共享赞踩图标及订阅、TMDB、忽略文字动作。"""
    actions = _read("RecommendationActions.vue")
    for label in ("订阅", "TMDB", "忽略"):
        assert label in actions
    for forbidden in ("豆瓣", "Bgm", "doubanSearchText", "sourceLabel", "搜索豆瓣"):
        assert forbidden not in actions
    assert "nativeSubscribe" in actions
    assert "moviepilot:nativeSubscribe" in actions
    assert "PERMISSION_DENIED" in actions
    assert "const nativeMediaType = computed(() => props.item?.media_type === 'movie' ? '电影' : '电视剧')" in actions
    assert "media.media_id = sourceId" in actions
    assert "if (result?.success === true)" in actions
    assert "emit('native-subscribe-opened', props.item?.candidate_id)" in actions
    assert "if (result?.code === 'PERMISSION_DENIED') return" in actions
    state = _read("useAgentRankState.js")
    assert "'attribution/native-drawer-opened'" in state
    assert "recordNativeDrawerOpened" in state
    assert "VDialog" not in actions
    for name in ("Dashboard.vue", "Page.vue"):
        component = _read(name)
        assert "RecommendationActions" in component
        assert "nativeSubscribe" in component
        assert "native-subscribe-opened" in component
        assert "置信度" not in component


def test_like_and_dislike_controls_are_shape_first_accessible_and_persistent():
    """赞踩使用形状状态，并在移出补位后刷新共享榜单。"""
    actions = _read("RecommendationActions.vue")
    state = _read("useAgentRankState.js")
    for icon in (
        "mdi-thumb-up-outline",
        "mdi-thumb-up",
        "mdi-thumb-down-outline",
        "mdi-thumb-down",
    ):
        assert icon in actions
    assert ":aria-pressed=" in actions
    assert actions.count('variant="tonal"') >= 5
    assert '<span class="ar-actions__label">点赞</span>' in actions
    assert '<span class="ar-actions__label">点踩</span>' in actions
    assert "likePressed ? '已点赞' : '点赞'" in actions
    assert "dislikePressed ? '已点踩' : '点踩'" in actions
    assert actions.count('class="ar-actions__button text-none"') >= 4
    assert "reactToRecommendation" in state
    assert "idempotency_key" in state
    assert "board_revision" in state
    assert "run_id: currentBoard.run_id" in state
    assert "feedback_kind" in state
    assert "if (result?.board_changed)" in state
    assert "await refreshProfileAfterMutation(targetProfile)" in state


def test_shared_state_centralizes_new_agent_workflows_and_retryable_failures():
    """评论、对话、待确认、归因和数据动作都进入同一可重试状态层。"""
    state = _read("useAgentRankState.js")
    for path in (
        "analysis",
        "analysis/comment",
        "conversation/messages",
        "conversation/messages/retry",
        "conversation/commands/respond",
        "pending/respond",
        "attribution/verify",
        "data/export",
        "data/reset/learning",
        "data/reset/full/prepare",
        "data/reset/full",
    ):
        assert path in state
    for marker in (
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
        "ensureSecondaryScope",
    ):
        assert marker in state
    assert "catch(() => {})" not in state
    for name in ("Dashboard.vue", "Page.vue"):
        component = _read(name)
        assert "@like=" in component
        assert "@dislike=" in component
        assert "result?.message" in component


def test_discovery_settings_open_embedded_config_and_use_core_save_api():
    """发现页设置入口不再依赖宿主未监听的 switch 事件。"""
    app_page = _read("AppPage.vue")
    api = _read("api.js")
    assert '@switch="openSettings"' in app_page
    assert "<Config" in app_page
    assert "emit('switch')" not in app_page
    assert "api.put('plugin/AgentRank', payload)" in api


def test_api_error_normalizer_reads_fastapi_validation_details():
    """FastAPI 字段校验数组应显示真实位置和消息，而不是只显示状态码。"""
    api = _read("api.js")
    for marker in (
        "export function extractFastApiDetail(detail)",
        "Array.isArray(detail)",
        "item.message || item.msg",
        "item.loc.map",
        "fastApiDetail.message",
        "fastApiDetail.code",
    ):
        assert marker in api


def test_ranking_surfaces_cache_overview_by_stable_profile_id():
    """榜单首屏按稳定 profile_id 聚合缓存，过期刷新失败可见且可重试。"""
    state = _read("useAgentRankState.js")
    page = _read("Page.vue")
    assert "const cacheByApi = new WeakMap()" in state
    assert "const PROFILE_CACHE_TTL_MS = 60 * 1000" in state
    assert "getPluginApi(api, 'overview', { profile_id: profileId })" in state
    assert "getPluginApi(api, 'board'" not in state
    assert "getPluginApi(api, 'profile'" not in state
    assert "{ legacyLoading: cached ? '' : 'data' }" in state
    assert "void runOperation(" in state
    assert "() => loadProfileData(profileId, { force: true })" in state
    assert "if (!initialized.value || !value || value === oldValue) return" in page


def test_profile_rebuild_only_lives_in_playback_profile_settings():
    """发现页和详情页不暴露重建入口，操作集中在播放画像并二次确认。"""
    app_page = _read("AppPage.vue")
    detail_page = _read("Page.vue")
    config = _read("Config.vue")
    for page in (app_page, detail_page):
        assert "清除画像" not in page
        assert "profile/clear" not in page
        assert "mdi-account-remove-outline" not in page
    assert "重建画像" in config
    assert '@click="requestClearProfile"' in config
    assert "postPluginApi(props.api, 'profile/clear'" in config
    assert "profile_id: selectedProfileId.value, confirm: true" in config
    assert 'v-model="clearProfileDialog"' in config
    assert "确认重建" in config


def test_detail_page_focuses_on_four_data_views_without_weights():
    """详情页展示当前榜单、画像、归档、运行历史和历史榜单，不重复承载权重配置。"""
    page = _read("Page.vue")
    for title in ("推荐榜单", "用户画像", "忽略归档", "运行历史", "历史榜单"):
        assert title in page
    assert "权重配置" not in page
    assert "weightLabels" not in page
    assert "ar-page__summary-bar" in page
    assert "ar-page__rank-copy" in page


def test_board_history_is_paginated_read_only_and_marks_cross_run_changes():
    """历史榜单通过独立分页接口读取，并明确新入榜与历史再推荐。"""
    page = _read("Page.vue")
    state = _read("useAgentRankState.js")
    assert "{ key: 'board-history', title: '历史榜单'" in page
    assert "getPluginApi(api, 'board-history'," in state
    assert "loadBoardHistory(page, pageSize)" in state
    assert "本轮新入榜" in page
    assert "历史再推荐" in page
    assert "评分。" in page
    assert "契合度" not in page
    assert "mdi-view-list-outline" in page
    assert "mdi-history-box-outline" not in page
    assert "历史快照未保存支持度" not in page
    assert "state.archive" not in page[page.index("activeTab === 'board-history'"):]
    assert "state.subscribe" not in page[page.index("activeTab === 'board-history'"):]


def test_detail_page_uses_transparent_root_and_data_surfaces():
    """详情页根容器、工具栏、统计栏、页签和表格均继承宿主背景。"""
    page = _read("Page.vue")
    root_style = next(line for line in page.splitlines() if line.startswith(".ar-page {"))
    summary_style = next(
        line for line in page.splitlines() if line.startswith(".ar-page__summary-bar {")
    )
    assert "width: 100%;" in root_style
    assert "max-width: none;" in root_style
    assert "box-sizing: border-box;" in root_style
    assert "background: transparent;" in root_style
    assert "v-theme-surface" not in root_style
    assert "flex: 0 0 auto;" in summary_style
    assert "background: transparent;" in summary_style
    assert ".ar-page__toolbar { flex: 0 0 auto; background: transparent; }" in page
    assert ".ar-page :deep(.v-tabs), .ar-page :deep(.v-table)" in page
    assert ".ar-page__content" in page and "background: transparent;" in page


def test_detail_mobile_header_and_progress_rows_do_not_overlap():
    """窄屏进度区不可被压缩，CinePilot 入口与其他操作保持同一顺序。"""
    page = _read("Page.vue")

    assert ".ar-page__summary-bar { flex: 0 0 auto;" in page
    assert ".ar-page__critic-badge { order: 2; }" in page


def test_cinepilot_dialog_is_viewport_bounded_and_only_messages_scroll():
    """对话卡片固定在视口内，内容增长只能推动消息区内部滚动。"""
    dialog = _read("CriticChatDialog.vue")

    assert 'content-class="ar-chat-dialog"' in dialog
    assert ":global(.ar-chat-dialog)" in dialog
    assert "max-height: calc(100dvh - 32px)" in dialog
    assert ".ar-chat { width: 100%; height: 100%; min-height: 0; max-height: 100%;" in dialog
    assert ".ar-chat__messages { flex: 1 1 0; min-height: 0; overflow-y: auto;" in dialog


def test_profile_view_edits_archives_restores_preferences_and_shows_board_matches():
    """画像页支持标签增删归档恢复，并继续展示本轮命中。"""
    page = _read("Page.vue")
    state = _read("useAgentRankState.js")
    assert "state.profile.value?.negative_tags" in page
    assert "item.match_tags || []" in page
    assert "state.updateProfileTag(kind, 'add', tag)" in page
    assert "state.updateProfileTag(kind, 'remove', tag)" in page
    assert "state.updateProfileTag(item.kind, 'restore', item.tag)" in page
    assert "state.profile.value?.archived_profile_tags" in page
    assert "closable" in page
    for label in ("播放样本", "偏好标签", "避雷标签", "本轮命中", "归档标签", "恢复标签"):
        assert label in page
    assert "ar-page__profile-groups" in page
    assert "getPluginApi(api, 'overview', { profile_id: profileId })" in state
    assert "'profile/tags'" in state


def test_discovery_page_contains_only_ranking_content_and_no_success_banner():
    """发现页移除右栏摘要，并且成功状态不展示提示文案。"""
    app_page = _read("AppPage.vue")
    for label in ("画像摘要", "权重摘要", "最近归档", "运行历史"):
        assert label not in app_page
    assert "ar-app-page__aside" not in app_page
    assert "榜单刷新已完成" not in app_page
    assert "board.value?.message" not in app_page


def test_ranking_posters_do_not_force_eager_loading():
    """实际渲染榜单的共享页面与仪表盘均按需加载海报。"""
    for name in ("Dashboard.vue", "Page.vue"):
        assert "<VImg" in _read(name)
        assert " eager>" not in _read(name)
    assert "<Page" in _read("AppPage.vue")


def test_ranking_copy_wraps_fully_without_toggle_controls():
    """共享 Page 的理由和简介始终完整换行，发现页直接复用该行为。"""
    app_page = _read("AppPage.vue")
    page = _read("Page.vue")
    assert "<Page" in app_page
    assert "推荐：" in page
    assert "简介：" in page
    assert "toggleCopy(item, 'reason')" not in page
    assert "toggleCopy(item, 'summary')" not in page
    assert ".ar-page__copy-toggle" not in page
    assert ".ar-page__copy-text--reason," in page
    assert "display: block; overflow: visible; -webkit-line-clamp: initial;" in page


def test_mobile_detail_tabs_scroll_in_one_row_without_visible_scrollbar():
    """详情页四个入口在移动端保持同排横滑并隐藏滚动条。"""
    page = _read("Page.vue")
    assert '<nav class="ar-page__tabs"' in page
    assert "show-arrows" not in page
    assert '<VList density="compact" nav class="ar-page__tab-list">' in page
    assert '<template #prepend><VIcon :icon="tab.icon"' in page
    assert ".ar-page__tabs { min-height: 40px; overflow-x: auto; }" in page
    assert "width: max-content; min-width: max-content; flex-wrap: nowrap" in page
    assert "flex: 0 0 auto; min-width: 112px" in page
    assert ".ar-page__tabs::-webkit-scrollbar { display: none; }" in page
    assert "scrollbar-width: none" in page
    assert "functionTabsExpanded" not in page
    assert "toggleFunctionTabs" not in page


def test_mobile_detail_hides_idle_runtime_and_wraps_copy_without_toggles():
    """详情页空闲态不挤占页签，移动端理由与简介完整换行。"""
    page = _read("Page.vue")
    assert 'v-if="state.isRunning.value"' in page
    assert "运行就绪" not in page
    assert 'class="ar-page__progress"' in page
    assert "克里斯蒂娜" in page
    assert "state.runProgress.value?.message" in page
    assert "state.runProgress.value?.stage_index" in page
    assert ".ar-page__progress { grid-column: 1 / -1;" in page
    assert ".ar-page__runtime-chip { display: none; }" in page
    assert ".ar-page__rank-copy { grid-template-columns: 34px minmax(0, 1fr); }" in page
    assert ".ar-page__copy-toggle" not in page
    assert ".ar-page__copy-text--intro {" in page
    assert "display: block; overflow: visible; -webkit-line-clamp: initial;" in page


def test_desktop_detail_fits_five_compact_rows_and_dashboard_copy_wraps():
    """桌面详情页压缩至完整五条，仪表盘推荐文案不再单行省略。"""
    page = _read("Page.vue")
    dashboard = _read("Dashboard.vue")
    assert "height: min(900px, calc(100dvh - 16px))" in page
    assert "min-height: 88px" in page
    assert "width: 50px; height: 75px" in page
    assert "gap: 6px" in next(
        line for line in page.splitlines() if line.startswith(".ar-page__ranking,")
    )
    assert 'class="ar-dashboard__copy text-caption"' in dashboard
    assert ".ar-dashboard__copy { white-space: normal; overflow-wrap: anywhere;" in dashboard
    assert 'class="text-caption text-truncate">推荐：' not in dashboard


def test_ranking_actions_keep_three_labels_and_wrap_without_container_collapse():
    """三项动作始终保留文字，并通过换行适配狭窄容器。"""
    actions = _read("RecommendationActions.vue")
    assert "mdi-bookmark-plus-outline" in actions
    assert 'prepend-icon="mdi-eye-off-outline"' in actions
    assert '<VTooltip text="打开 TMDB"' in actions
    assert 'prepend-icon="mdi-movie-open-outline"' in actions
    assert 'class="ar-actions__button ar-actions__button--tmdb text-none"' in actions
    assert 'color="info"' not in actions
    assert "color: #0288d1 !important;" in actions
    assert "color: color-mix(in srgb, #0288d1 78%, rgb(var(--v-theme-on-surface)) 22%) !important;" in actions
    assert 'prepend-icon="mdi-open-in-new"' not in actions
    assert 'https://search.douban.com/movie/subject_search?search_text=' not in actions
    assert "sourceAvailable" not in actions
    assert "container: actions / inline-size" not in actions
    assert "@container actions" not in actions
    assert "flex-wrap: wrap" in actions
    for label in ("订阅", "TMDB", "忽略"):
        if label == "订阅":
            assert "alreadySubscribed ? '已订阅' : '订阅'" in actions
        else:
            assert f'<span class="ar-actions__label">{label}</span>' in actions
            assert actions.count(f'<span class="ar-actions__label">{label}</span>') == 1
    for name, fit_score_class in (
        ("Dashboard.vue", "ar-dashboard__fit-score"),
        ("Page.vue", "ar-page__fit-score"),
    ):
        component = _read(name)
        assert ".slice(0, 5)" in component
        assert "置信度" not in component
        assert "fit_score" in component
        assert "契合度" not in component
        assert "rawScore === null || rawScore === undefined || rawScore === ''" in component
        assert "support?.percentage" not in component
        assert component.index(fit_score_class) < component.index("<RecommendationActions")
        fit_score_rule = next(
            line for line in component.splitlines()
            if line.startswith(f".{fit_score_class} {{")
        )
        if name == "Dashboard.vue":
            assert "margin-left: auto" in fit_score_rule
        else:
            assert "margin-left: auto" not in fit_score_rule
    app_page = _read("AppPage.vue")
    page = _read("Page.vue")
    assert "<Page" in app_page
    assert page.index('icon="mdi-text-box-search-outline"') < page.index("ar-page__fit-score") < page.index("<RecommendationActions")
    assert "item.in_library && item.watch_status === 'unwatched'" in page
    assert ">未观看</VChip>" in page
    assert ".ar-page__analysis-score { display: flex;" in page
    assert ".ar-page__analysis-score { order: 1; }" in page
    assert ".ar-page__rank-actions :deep(.ar-actions) { order: 2; flex: 1 0 100%; justify-content: flex-end; }" in page
    assert "ar-page__evidence-summary" not in page
    assert "净支持" not in page
    assert actions.index(":aria-label=\"alreadySubscribed ? '已订阅' : '订阅'\"") < actions.index('aria-label="打开 TMDB"') < actions.index('aria-label="忽略"')
    assert actions.index('aria-label="忽略"') < actions.index("likePressed ? '已点赞' : '点赞'") < actions.index("dislikePressed ? '已点踩' : '点踩'")


def test_config_uses_four_main_sections_and_places_execution_controls_once():
    """配置页保留四个主区，策略由 Agent 接管，基础设置集中。"""
    config = _read("Config.vue")
    for key, title in (
        ("overview", "运行总览"),
        ("basic", "基础设置"),
        ("profile", "画像学习"),
        ("agent", "Agent设定"),
        ("advanced", "高级选项"),
    ):
        assert f"{{ key: '{key}', title: '{title}'" in config
    assert "条件筛选" not in config
    assert "{ key: 'behavior'" not in config
    for group in ("画像来源", "运行计划", "页面入口", "榜单行为", "后台提醒"):
        assert f"<span>{group}</span>" in config
    assert "activeProfile" in config
    assert "activeStrategy" not in config
    assert "activeMain.value === 'basic' ? []" in config
    assert config.count('v-model.number="form.candidate_pool_size"') == 1
    assert "最低支持度" in config
    assert 'label="安全上限"' not in config
    assert 'label="订阅数量"' in config
    assert '<VSelect v-model="selectedLibraryIds"' in config
    assert 'item-title="title" item-value="value"' in config
    assert "selectedLibraryOverflowCount" in config
    assert "index === 0" in config
    assert "index === 1" in config
    assert "ar-config__select-summary-primary" in config
    assert "ar-config__select-summary-count" in config
    assert "selectedLibraryNames.slice(1).join('、')" in config
    assert "index < 2" not in config
    assert "index === 2" not in config
    assert 'v-model="form.media_types"' not in config
    assert 'v-model="form.exclude_keywords"' not in config
    assert "negative_keyword: '避雷命中'" in config


def test_mobile_page_and_config_keep_only_one_hidden_scroll_surface():
    """移动端主页面扣除宿主导航，配置页外层固定且只允许内容窗滚动。"""
    page = _read("Page.vue")
    app_page = _read("AppPage.vue")
    config = _read("Config.vue")

    assert ":class=\"{ 'ar-page--app': !showClose }\"" in page
    assert "var(--layout-navbar-block-size, 4rem)" in page
    assert ".ar-page__content::-webkit-scrollbar { display: none; }" in page
    assert "overflow: hidden;" in app_page
    assert "onMounted(lockHostScroll)" in app_page
    assert "onBeforeUnmount(unlockHostScroll)" in app_page
    assert "agentRankScrollLocks" in app_page
    assert ":global(.ar-app-page-host-lock)" in app_page
    assert "overflow-y: hidden !important;" in app_page
    assert ":global(.ar-app-page-host-lock .layout-footer)" in app_page
    assert "display: none !important;" in app_page
    assert "height: min(876px, calc(100dvh - 48px))" in config
    assert ".ar-config__card { width: 100%; height: 100%; min-height: 0;" in config
    assert ".ar-config__window::-webkit-scrollbar { display: none; }" in config
    assert ".ar-config__subtabs::-webkit-scrollbar { display: none; }" in config
    assert 'class="ar-config__header-brand"' in config
    assert 'class="ar-config__header-copy"' in config
    assert 'class="ar-config__enabled"' in config
    assert '<VCardItem class="ar-config__header">' not in config
    assert "{ key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard'" in config
    assert "{ key: 'agent', title: 'Agent设定', icon: 'mdi-account-voice'" in config
    assert ".ar-config__mode-toggle { flex-direction: row; }" in config
    assert ".ar-config__mode-toggle { flex-direction: column; }" not in config


def test_notification_type_and_low_interruption_state_are_user_visible_without_scores():
    """基础设置可选完整通知类型，画像只显示三档状态而不暴露精确成熟度。"""
    config = _read("Config.vue")
    page = _read("Page.vue")
    assert 'notification_type: \'Plugin\'' in config
    assert 'v-model="form.notification_type"' in config
    assert "notificationTypeOptions" in config
    for label in ("探索中", "趋于稳定", "低打扰"):
        assert label in page
    for forbidden in ("画像成熟度", "成熟度百分比", "questioning_score"):
        assert forbidden not in page


def test_cinepilot_chat_is_immediate_bounded_and_retryable():
    """对话立即显示排队状态，持续以服务端状态为准并支持后端失败重试。"""
    chat = _read("CriticChatDialog.vue")
    state = _read("useAgentRankState.js")
    assert "克里斯蒂娜" in chat
    assert "['queued', 'processing'].includes" in chat
    assert "frontendTimeoutMs" not in chat
    assert "markFrontendTimeout" not in chat
    assert "status: 'retryable_failed'" not in chat
    assert "startPolling()" in chat
    assert "conversation/messages/retry" in state
    assert "loadConversation({ markRead = false } = {})" in state
    assert "conversation/status" in state
    assert "loadConversation({ markRead: true })" in chat
    assert "reminder_policy" not in state


def test_cinepilot_entry_has_persistent_unread_reply_badge():
    """对话入口展示后端持久化的未读回复数，并在页面级轮询异步结果。"""
    page = _read("Page.vue")
    state = _read("useAgentRankState.js")
    assert 'class="ar-page__critic-badge"' in page
    assert "criticUnreadCount" in page
    assert "!criticDialog && criticUnreadCount > 0" in page
    assert "state.loadConversationStatus()" in page
    assert "has_pending ? 2000 : 15000" in page
    assert "const conversationStatus = ref(emptyConversationStatus())" in state


def test_pending_center_uses_symmetric_actions_without_reminders():
    """三类待处理项使用锁定文案，前端不再暴露时效提醒。"""
    pending = _read("PendingConfirmations.vue")
    for label in (
        "确认执行",
        "拒绝执行",
        "确认采纳",
        "拒绝采纳",
        "提交回答",
        "关闭问询",
    ):
        assert label in pending
    for forbidden in ("稍后", "1天后", "3天后", "7天后", "不提醒", "reminder"):
        assert forbidden not in pending
    assert "const bodyRef = ref(null)" in pending
    assert 'ref="bodyRef"' in pending
    assert "function resetBodyScroll()" in pending
    assert "element.scrollTop = 0" in pending
    assert "const loadedViews = reactive({ pending: false, resolved: false })" in pending
    assert ':height="smAndDown ? undefined : 760"' in pending
    assert "operation.loading && loadedViews[activeView]" in pending
    assert "operation.loading && !loadedViews[activeView]" in pending
    assert "void load(value)" in pending
    assert "await load()" not in pending
    assert ".ar-pending__content { position: relative; min-height: 100%; }" in pending
    assert ".ar-pending__state { min-height: 100%;" in pending
    assert "overflow: hidden" in pending
    assert "overscroll-behavior: contain" in pending


def test_native_subscribe_payload_uses_v3_identity_without_source_buttons():
    """原生订阅从旧别名回填 V3 身份对，且动作栏不再暴露来源按钮。"""
    actions = _read("RecommendationActions.vue")
    for alias in ("tmdb_id", "themoviedb", "doubanid", "bangumiid", "anilistid"):
        assert alias in actions
    assert "mediaid_prefix" not in actions
    assert "media_source" in actions
    assert "media_id" in actions
    assert "props.item?.original_title" not in actions
    assert "doubanSearchText" not in actions
    assert "sourceLabel" not in actions


def test_dashboard_assigns_an_explicit_fourth_action_column_and_mobile_row():
    """仪表盘显式分配操作列，窄屏降级为整行，避免按钮叠加。"""
    dashboard = _read("Dashboard.vue")
    assert "minmax(0, max-content)" in dashboard
    assert "grid-column: 4; grid-row: 1 / span 2" in dashboard
    assert ".ar-dashboard__rank, .ar-dashboard__poster { grid-row: 1; }" in dashboard
    assert "grid-column: 1 / -1; grid-row: 2" in dashboard
    assert ".ar-dashboard__controls :deep(.ar-actions) { order: 1; }" in dashboard
    assert ".ar-dashboard__fit-score { order: 2; margin-left: auto; }" in dashboard


def test_runtime_history_uses_chinese_fallbacks_for_unknown_internal_codes():
    """未知阶段、来源和播放状态不再直出内部英文 key。"""
    page = _read("Page.vue")
    config = _read("Config.vue")
    notification = (COMPONENT_DIR.parents[2] / "service" / "notification.py").read_text(encoding="utf-8")
    for label in ("其他阶段", "其他来源", "其他排除原因", "状态未知", "运行异常"):
        assert label in page
    for label in ("播放记录服务", "其他来源", "其他排除原因", "运行异常"):
        assert label in config
    assert "})[value] || '未评估'" in config
    assert "STATUS_LABELS.get(str(status or ''), '运行异常')" in notification


def test_runtime_history_formats_durations_in_minutes_after_sixty_seconds():
    """运行历史超过一分钟后使用分秒显示，整分钟不保留多余秒数。"""
    page = _read("Page.vue")

    for expression in (
        "const totalSeconds = Math.round(ms / 1000)",
        "if (totalSeconds < 60) return `${totalSeconds}秒`",
        "`${minutes}分${seconds}秒`",
        "`${minutes}分钟`",
    ):
        assert expression in page
    assert "toFixed(ms < 10000 ? 1 : 0)" not in page


def test_runtime_history_uses_actual_model_as_primary_metric():
    """运行历史主指标显示实际模型，调用次数只保留在展开详情。"""
    page = _read("Page.vue")

    assert "function historyModelText(run)" in page
    assert "function historyAgentCalls(run)" in page
    assert "run?.metrics?.agent_provenance" in page
    assert "run?.metrics?.agent_model" in page
    assert "'模型来源未返回'" in page
    assert "`${item.provider} · ${item.model}`" in page
    assert '{{ historyModelText(run) }}' in page
    assert "供应商 / 模型" in page
    assert "run.metrics?.model_call_count ?? run.metrics?.agent_calls ?? 0" in page
    assert '<strong>{{ run.metrics?.agent_calls ?? 0 }}</strong><span>模型调用</span>' not in page
    assert "模型调用 {{ call.modelCalls }} 次" in page
    assert "{{ call.duration }}" in page
    assert "{{ call.failure }}" in page
    assert "ar-page__history-model" in page
    assert "ar-page__history-agent-calls" in page


def test_runtime_history_exposes_versioned_policy_in_chinese():
    """运行历史显示策略版本、记忆版本与证据数，并翻译策略阶段状态。"""
    page = _read("Page.vue")

    assert "policy: '确定策略'" in page
    assert "policy_failed: '策略生成失败'" in page
    assert "policy_superseded: '偏好已更新，请重新生成'" in page
    assert "function historyPolicyText(run)" in page
    assert "metrics.policy_version" in page
    assert "metrics.policy_memory_revision" in page
    assert "metrics.policy_evidence_count" in page
    assert "排序策略" in page
    assert "repeat(7, minmax(90px, 1fr))" in page


def test_runtime_history_explains_agent_and_safe_fallback_selection_sources():
    """运行历史用中文分别展示 Agent 选择和安全补位数量。"""
    page = _read("Page.vue")

    assert "function historySelectionSourceText(run)" in page
    assert "metrics.selection_source_counts" in page
    assert "metrics.agent_selected_count" in page
    assert "metrics.safe_fallback_selected_count" in page
    assert "Agent 选择 ${agent} 条；安全补位 ${fallback} 条" in page
    assert "<span>选择来源</span>" in page


def test_runtime_history_explains_validation_drop_reasons_in_chinese():
    """运行历史汇总首轮和补选的校验丢弃原因。"""
    page = _read("Page.vue")

    assert "function historyValidationDropText(run)" in page
    assert "run?.metrics?.validation_drops" in page
    assert "run?.metrics?.refill_drops" in page
    assert "仍使用旧支持度字段" in page
    assert "支持度无效" in page
    assert "简介超过30字" in page
    assert "具体匹配证据不足" in page
    assert "可验证正向证据不足" in page
    assert "<span>校验丢弃</span>" in page


def test_preview_status_selector_uses_chinese_titles_for_internal_codes():
    """预览夹具展示中文状态标题但保留后端内部状态码。"""
    preview = (COMPONENT_DIR.parent / "PreviewApp.vue").read_text(encoding="utf-8")
    assert "{ title: '画像输出校验失败', value: 'profile_validation_failed' }" in preview
    assert "{ title: '已完成', value: 'success' }" in preview
    assert "generated: '已生成'" in _read("Config.vue")


def test_preview_profile_tag_actions_persist_archive_and_restore_state():
    """浏览器夹具必须真实模拟画像标签归档与恢复，避免只验证按钮消失。"""
    preview = (COMPONENT_DIR.parent / "PreviewApp.vue").read_text(encoding="utf-8")
    assert "if (path.endsWith('profile/tags'))" in preview
    assert "archived_profile_tags: []" in preview
    assert "profile.archived_profile_tags.push" in preview
    assert "profile.archived_profile_tags = profile.archived_profile_tags.filter" in preview


def test_preview_board_history_returns_snapshot_rows_with_change_markers():
    """预览夹具能覆盖历史榜单分页和跨轮次变化标记。"""
    preview = (COMPONENT_DIR.parent / "PreviewApp.vue").read_text(encoding="utf-8")
    assert "path.endsWith('board-history')" in preview
    assert "history_state: index === 0 || itemIndex === 0 ? 'new' : 'repeat'" in preview
    assert "new_count: index === 0 ? 5 : 1" in preview
    assert "overlap_count: index === 0 ? 0 : 4" in preview


def test_visible_ranking_copy_avoids_generic_english_ui_terms():
    """榜单可见文案不再直出 Top、identity 与毫秒缩写。"""
    dashboard = _read("Dashboard.vue")
    app_page = _read("AppPage.vue")
    page = _read("Page.vue")
    config = _read("Config.vue")
    for source in (dashboard, app_page, page):
        assert "Top 5" not in source
        assert "Top 10" not in source
    assert "Emby identity" not in app_page
    assert "Emby identity" not in config
    assert "`${Number(value)} ms`" not in config
    assert "毫秒" in config


def test_run_history_translates_agent_attempt_prefixes():
    """运行历史把后端尝试前缀转换成中文阶段文案。"""
    page = _read("Page.vue")
    assert "'画像第 $1 次：'" in page
    assert "'排序第 $1 次：'" in page
    assert "'补选第 $1 次：'" in page


def test_run_history_translates_common_agent_validation_errors():
    """运行历史把常见 Agent JSON 校验错误转换成中文。"""
    page = _read("Page.vue")
    assert "Agent 输出不是有效的 JSON 对象：内容为空或格式错误" in page
    assert "Agent 输出不是文本" in page
    assert "存在多余内容" in page


def test_run_history_translates_internal_stage_status_codes():
    """运行历史把流水线内部状态码转换成中文。"""
    page = _read("Page.vue")
    for code, label in (
        ("candidate_insufficient", "候选不足"),
        ("recommendation_incomplete", "榜单不足"),
        ("profile_validation_failed", "画像校验失败"),
        ("ranking_validation_failed", "排序校验失败"),
    ):
        assert f"{code}: '{label}'" in page


def test_run_history_translates_watched_and_disliked_exclusion_codes():
    """运行历史将已观看和作品级点踩排除码分别转换为中文。"""
    page = _read("Page.vue")
    config = _read("Config.vue")
    assert "watched: '已观看'" in page
    assert "watched: '已观看'" in config
    assert "disliked: '已点踩'" in page
    assert "disliked: '已点踩'" in config


def test_run_history_exposes_candidate_timing_cache_and_ranking_diagnostics():
    """运行历史细节可读展示候选子阶段、画像缓存和排序备用统计。"""
    page = _read("Page.vue")

    for text in (
        "candidate_recall_ms",
        "candidate_normalize_ms",
        "candidate_recognition_ms",
        "candidate_filter_ms",
        "candidate_snapshot_ms",
        "candidate_processing_counts",
        "profile_cache_miss_reason",
        "ranking_valid_count",
        "ranking_reserve_count",
        "ranking_fallback_count",
        "ranking_fallback_reason",
        "preliminary_batch_count",
        "judgment_card_cache_hit_count",
        "preliminary_failed_count",
        "preliminary_ms",
        "final_ms",
        "agent_repair_count",
        "final_retry_count",
        "final_input_source",
        "候选耗时",
        "候选处理",
        "画像缓存",
        "初赛批次",
        "阶段耗时",
        "修正次数",
        "降级来源",
        "排序校验",
        "保底",
    ):
        assert text in page


def test_config_uses_frozen_candidate_target_and_tournament_pipeline():
    """配置页固定 10-15 条冻结目标，并展示初赛到决赛的实际链路。"""
    config = _read("Config.vue")

    assert 'candidate_pool_size: 15' in config
    assert 'min="10" max="15" label="冻结候选目标"' in config
    for title in ("冻结候选", "初赛判断", "决赛榜单"):
        assert f"title: '{title}'" in config
    assert "title: '池内排序'" not in config


def test_profile_filter_aliases_are_removed_from_user_configuration():
    """长期画像不再在配置页展示固定检索过滤别名。"""
    config = _read("Config.vue")
    for marker in (
        "genres: '题材'",
        "languages: '语言'",
        "release_year_min: '最早年份'",
        "release_year_max: '最晚年份'",
    ):
        assert marker not in config
    assert "retrieval_trace" in config
