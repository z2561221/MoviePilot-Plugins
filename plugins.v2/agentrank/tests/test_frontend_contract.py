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


def test_runtime_settings_exposes_discovery_page_switch_and_fifty_default():
    """运行设置可独立关闭发现页入口，候选池前端默认值为五十。"""
    config = _read("Config.vue")
    assert 'discovery_page_enabled: true' in config
    assert 'v-model="form.discovery_page_enabled"' in config
    assert 'label="开启发现页"' in config
    assert 'candidate_pool_size: 50' in config


def test_basic_settings_selects_stable_emby_identities_for_run_once():
    """基础设置以稳定 Emby identity 取代 MoviePilot 用户和用户名映射。"""
    config = _read("Config.vue")
    assert 'onlyonce: false' in config
    assert 'emby_identities: []' in config
    assert "default_profile_id: ''" in config
    assert 'v-model="selectedProfileIds"' in config
    assert 'v-model="form.default_profile_id"' in config
    assert 'v-model="form.onlyonce"' in config
    assert 'label="立即运行一次"' in config
    assert "!form.emby_identities.length" in config
    assert "立即运行触发后会自动关闭" in config
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


def test_extension_discovery_source_is_absent_from_config_ui():
    """配置页只允许选择四个 MoviePilot 内置发现来源。"""
    config = _read("Config.vue")
    assert "扩展来源" not in config
    assert "extensions: true" not in config
    assert "选择 MoviePilot 内置发现来源" in config


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


def test_all_ranking_surfaces_use_direct_four_button_actions():
    """三处榜单统一直显四按钮，不使用操作弹窗。"""
    actions = _read("RecommendationActions.vue")
    for label in ("订阅", "TMDB", "豆瓣", "Bgm", "忽略"):
        assert label in actions
    assert "VDialog" not in actions
    for name in ("Dashboard.vue", "AppPage.vue", "Page.vue"):
        component = _read(name)
        assert "RecommendationActions" in component


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
    assert "-webkit-line-clamp: 3" in app_page
    assert "ar-app-page__copy-text--intro" in app_page
    assert "-webkit-line-clamp: 4" in app_page
    assert "toggleCopy(item, 'reason')" in app_page
    assert "toggleCopy(item, 'summary')" in app_page


def test_mobile_detail_tabs_scroll_without_arrow_controls():
    """详情页移动端页签使用原生横向滚动，不为左右箭头牺牲文字空间。"""
    page = _read("Page.vue")
    assert '<nav class="ar-page__tabs"' in page
    assert "show-arrows" not in page
    assert "overflow-x: auto" in page
    assert "scroll-snap-type: x proximity" in page
    assert "ar-page__tab-icon { display: none; }" in page


def test_compact_actions_keep_primary_commands_and_tooltip_links():
    """移动端保留订阅和忽略文字命令，外链收为带提示的图标按钮。"""
    actions = _read("RecommendationActions.vue")
    assert 'prepend-icon="mdi-bookmark-plus-outline"' in actions
    assert 'prepend-icon="mdi-eye-off-outline"' in actions
    assert '<VTooltip text="打开 TMDB"' in actions
    assert 'icon="mdi-movie-open-outline"' in actions
    assert 'icon="mdi-open-in-new"' in actions
