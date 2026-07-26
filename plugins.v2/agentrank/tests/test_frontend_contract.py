"""AgentRank Vue 联邦组件静态合同测试。"""

from pathlib import Path


COMPONENT_DIR = Path(__file__).resolve().parents[1] / "frontend" / "src" / "components"


def _read(name: str) -> str:
    return (COMPONENT_DIR / name).read_text(encoding="utf-8")


def test_advanced_options_exposes_four_character_prompt_subtab():
    """提示词入口位于高级选项的四字二级标签。"""
    config = _read("Config.vue")
    assert "{ key: 'runtime', title: '运行设置'" in config
    assert "{ key: 'prompt', title: '提示设置'" in config
    assert "Agent排序提示词" in config
    assert "恢复默认" in config


def test_runtime_settings_exposes_discovery_page_switch_and_current_defaults():
    """运行设置可独立关闭发现页入口，并复用当前非隐私默认值。"""
    config = _read("Config.vue")
    assert 'discovery_page_enabled: true' in config
    assert 'v-model="form.discovery_page_enabled"' in config
    assert 'label="开启发现页"' in config
    assert 'schedule_enabled: true' in config
    assert "cron: '5 18 * * *'" in config
    assert 'candidate_pool_size: 100' in config
    assert 'playback_recent_days: 90' in config


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
    assert 'label="媒体库（Emby 服务实例）"' in config
    assert 'v-model="selectedUserProfileId"' in config
    assert 'label="用户"' in config
    assert 'v-model="selectedLibraryIds"' in config
    assert 'label="内容库筛选"' in config
    assert 'v-model="form.onlyonce"' in config
    assert 'label="立即运行一次"' in config
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


def test_discovery_source_options_follow_host_capability_and_include_anilist():
    """配置页按宿主能力动态展示来源，并兼容 AniList 内置来源。"""
    config = _read("Config.vue")
    assert "扩展来源" not in config
    assert "extensions: true" not in config
    assert "选择 MoviePilot 内置发现来源" in config
    assert "const sourceOptions = ref([])" in config
    assert "sourceOptions.value.filter(item => item && item.available !== false)" in config
    assert "anilist: { title: 'AniList'" in config


def test_profile_runtime_switches_describe_incremental_semantics():
    """画像缓存和每次重建开关向用户说明真实运行语义。"""
    config = _read("Config.vue")
    assert 'v-model="form.profile_cache_enabled"' in config
    assert 'v-model="form.rebuild_profile_each_run"' in config
    assert "播放快照未变化时复用当前画像" in config
    assert "按冻结的 Playback Reporting 快照重新生成" in config


def test_discovery_cards_use_non_black_theme_surface():
    """发现页榜单条目常态透明，仅在悬停时显示主题反馈。"""
    app_page = _read("AppPage.vue")
    item_style = next(
        line for line in app_page.splitlines() if line.startswith(".ar-app-page__item {")
    )
    assert "surface-variant" not in item_style
    assert "color-mix" not in item_style
    assert "background: transparent;" in item_style
    assert "color: rgb(var(--v-theme-on-surface));" in item_style
    assert ".ar-app-page__item:hover" in app_page
    assert "background: rgba(var(--v-theme-primary), .07);" in app_page


def test_discovery_page_translates_internal_source_codes():
    """发现页将候选来源内部码转换为用户可读名称。"""
    app_page = _read("AppPage.vue")
    for source, label in (
        ("douban", "豆瓣发现"),
        ("tmdb", "TMDB"),
        ("tmdb_recommend", "TMDB 推荐"),
        ("tmdb_movies", "TMDB 电影"),
        ("tmdb_tv", "TMDB 剧集"),
        ("bangumi", "Bangumi"),
        ("anilist", "AniList"),
    ):
        assert f"{source}: '{label}'" in app_page
    assert "sources.map(source => sourceLabels[source] || '其他来源').join(' · ')" in app_page


def test_all_ranking_surfaces_use_three_button_actions_and_native_subscribe():
    """三处榜单只保留订阅、TMDB、忽略，并优先调用宿主原生订阅。"""
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
    assert "if (result?.success === true || result?.code === 'PERMISSION_DENIED') return" in actions
    assert "VDialog" not in actions
    for name in ("Dashboard.vue", "AppPage.vue", "Page.vue"):
        component = _read(name)
        assert "RecommendationActions" in component
        assert "nativeSubscribe" in component
        assert "置信度" not in component


def test_discovery_settings_open_embedded_config_and_use_core_save_api():
    """发现页设置入口不再依赖宿主未监听的 switch 事件。"""
    app_page = _read("AppPage.vue")
    api = _read("api.js")
    assert '@click="openSettings"' in app_page
    assert "<Config" in app_page
    assert "emit('switch')" not in app_page
    assert "api.put('plugin/AgentRank', payload)" in api


def test_ranking_surfaces_cache_overview_by_stable_profile_id():
    """榜单首屏按稳定 profile_id 聚合缓存并在过期后静默更新。"""
    state = _read("useAgentRankState.js")
    page = _read("Page.vue")
    assert "const cacheByApi = new WeakMap()" in state
    assert "const PROFILE_CACHE_TTL_MS = 60 * 1000" in state
    assert "getPluginApi(api, 'overview', { profile_id: profileId })" in state
    assert "getPluginApi(api, 'board'" not in state
    assert "getPluginApi(api, 'profile'" not in state
    assert "loading.data = !cached" in state
    assert "void fetchProfileData(profileId, entry)" in state
    assert "if (!initialized.value || !value || value === oldValue) return" in page


def test_profile_clear_only_lives_in_advanced_runtime_settings():
    """发现页和详情页不暴露清除入口，危险操作集中在高级运行设置并二次确认。"""
    app_page = _read("AppPage.vue")
    detail_page = _read("Page.vue")
    config = _read("Config.vue")
    for page in (app_page, detail_page):
        assert "清除画像" not in page
        assert "profile/clear" not in page
        assert "mdi-account-remove-outline" not in page
    assert 'v-model="clearProfileSwitch"' in config
    assert '@update:model-value="requestClearProfile"' in config
    assert "postPluginApi(props.api, 'profile/clear'" in config
    assert "profile_id: selectedProfileId.value, confirm: true" in config
    assert 'v-model="clearProfileDialog"' in config
    assert "确认清除" in config


def test_detail_page_focuses_on_four_data_views_without_weights():
    """详情页只展示榜单、画像、归档和历史，不重复承载权重配置。"""
    page = _read("Page.vue")
    for title in ("推荐榜单", "用户画像", "忽略归档", "运行历史"):
        assert title in page
    assert "权重配置" not in page
    assert "weightLabels" not in page
    assert "ar-page__summary-bar" in page
    assert "ar-page__rank-copy" in page


def test_detail_page_uses_transparent_root_and_data_surfaces():
    """详情页根容器、工具栏、统计栏、页签和表格均继承宿主背景。"""
    page = _read("Page.vue")
    root_style = next(line for line in page.splitlines() if line.startswith(".ar-page {"))
    summary_style = next(
        line for line in page.splitlines() if line.startswith(".ar-page__summary-bar {")
    )
    assert "background: transparent;" in root_style
    assert "v-theme-surface" not in root_style
    assert "background: transparent;" in summary_style
    assert ".ar-page__toolbar { flex: 0 0 auto; background: transparent; }" in page
    assert ".ar-page :deep(.v-tabs), .ar-page :deep(.v-table)" in page
    assert ".ar-page__content" in page and "background: transparent;" in page


def test_profile_view_edits_preferences_and_shows_board_matches():
    """画像页支持人工偏好与避雷标签增删，并继续展示本轮命中。"""
    page = _read("Page.vue")
    state = _read("useAgentRankState.js")
    assert "state.profile.value?.negative_tags" in page
    assert "item.match_tags || []" in page
    assert "state.updateProfileTag(kind, 'add', tag)" in page
    assert "state.updateProfileTag(kind, 'remove', tag)" in page
    assert "closable" in page
    for label in ("播放样本", "偏好标签", "避雷标签", "本轮命中"):
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
    """三个榜单页面的海报均按需加载，避免首屏争抢网络。"""
    for name in ("Dashboard.vue", "AppPage.vue", "Page.vue"):
        assert "<VImg" in _read(name)
        assert " eager>" not in _read(name)


def test_mobile_ranking_copy_wraps_and_can_expand():
    """发现页理由和简介使用多行截断并提供展开，不再强制单行省略。"""
    app_page = _read("AppPage.vue")
    page = _read("Page.vue")
    assert "white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" not in next(
        line for line in app_page.splitlines() if line.startswith(".ar-app-page__copy")
    )
    for source in (app_page, page):
        assert "推荐：" in source
        assert "简介：" in source
    assert "ar-app-page__copy-text--reason" in app_page
    assert "-webkit-line-clamp: 2" in app_page
    assert "ar-app-page__copy-text--intro" in app_page
    assert "-webkit-line-clamp: 1" in app_page
    assert "toggleCopy(item, 'reason')" in app_page
    assert "toggleCopy(item, 'summary')" in app_page


def test_mobile_detail_tabs_scroll_without_arrow_controls():
    """详情页移动端使用下载中心同款横向导航且不显示左右箭头。"""
    page = _read("Page.vue")
    assert '<nav class="ar-page__tabs"' in page
    assert "show-arrows" not in page
    assert "overflow-x: auto" in page
    assert "scroll-snap-type: x proximity" in page
    assert '<VList density="compact" nav class="ar-page__tab-list">' in page
    assert '<template #prepend><VIcon :icon="tab.icon"' in page


def test_mobile_detail_hides_idle_runtime_and_wraps_copy_without_toggles():
    """详情页空闲态不挤占页签，移动端理由与简介完整换行。"""
    page = _read("Page.vue")
    assert 'v-if="state.isRunning.value"' in page
    assert "运行就绪" not in page
    assert ">\n        正在生成\n      </VChip>" in page
    assert ".ar-page__rank-copy { grid-template-columns: 34px minmax(0, 1fr); }" in page
    assert ".ar-page__copy-toggle { display: none !important; }" in page
    assert ".ar-page__copy-text--intro," in page
    assert "display: block; overflow: visible; -webkit-line-clamp: initial;" in page


def test_ranking_actions_keep_three_labels_and_wrap_without_container_collapse():
    """三项动作始终保留文字，并通过换行适配狭窄容器。"""
    actions = _read("RecommendationActions.vue")
    assert 'prepend-icon="mdi-bookmark-plus-outline"' in actions
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
        assert f'<span class="ar-actions__label">{label}</span>' in actions
    for name, confidence_class in (
        ("Dashboard.vue", "ar-dashboard__confidence"),
        ("AppPage.vue", "ar-app-page__confidence"),
        ("Page.vue", "ar-page__confidence"),
    ):
        component = _read(name)
        assert "置信度" not in component
        assert "{{ item.confidence }}%" in component
        assert component.index(confidence_class) < component.index("<RecommendationActions")


def test_native_subscribe_payload_keeps_source_id_aliases_without_source_buttons():
    """原生订阅载荷兼容宿主旧字段，但动作栏不再暴露来源按钮。"""
    actions = _read("RecommendationActions.vue")
    for alias in ("tmdb_id", "themoviedb", "doubanid", "bangumiid", "anilistid"):
        assert alias in actions
    assert "mediaid_prefix" in actions
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


def test_runtime_history_uses_chinese_fallbacks_for_unknown_internal_codes():
    """未知阶段、来源和播放状态不再直出内部英文 key。"""
    page = _read("Page.vue")
    config = _read("Config.vue")
    notification = (COMPONENT_DIR.parents[2] / "service" / "notification.py").read_text(encoding="utf-8")
    for label in ("其他阶段", "其他来源", "其他排除原因", "状态未知", "运行异常"):
        assert label in page
    for label in ("播放记录服务", "其他排序", "其他条件", "运行异常"):
        assert label in config
    assert "})[value] || '未评估'" in config
    assert "STATUS_LABELS.get(str(status or ''), '运行异常')" in notification


def test_preview_status_selector_uses_chinese_titles_for_internal_codes():
    """预览夹具展示中文状态标题但保留后端内部状态码。"""
    preview = (COMPONENT_DIR.parent / "PreviewApp.vue").read_text(encoding="utf-8")
    assert "{ title: '画像输出校验失败', value: 'profile_validation_failed' }" in preview
    assert "{ title: '已完成', value: 'success' }" in preview
    assert "generated: '已生成'" in _read("Config.vue")


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


def test_run_history_translates_watched_exclusion_code():
    """运行历史将旧版 watched 排除码转换为中文。"""
    page = _read("Page.vue")
    config = _read("Config.vue")
    assert "watched: '已观看'" in page
    assert "watched: '已观看'" in config


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
        "候选耗时",
        "候选处理",
        "画像缓存",
        "排序校验",
        "保底",
    ):
        assert text in page


def test_profile_filter_aliases_remain_readable_for_legacy_agent_payloads():
    """配置页兼容旧版画像过滤键并把语言值转换为中文。"""
    config = _read("Config.vue")
    for key, label in (
        ("genres", "题材"),
        ("languages", "语言"),
        ("release_year_min", "最早年份"),
        ("release_year_max", "最晚年份"),
    ):
        assert f"{key}: '{label}'" in config
    assert "key === 'original_languages' || key === 'languages'" in config
    assert "languageLabels[item] || item" in config
