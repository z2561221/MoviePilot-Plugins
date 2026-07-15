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
    assert "参考上一版画像持续演进" in config


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


def test_ranking_surfaces_use_one_cached_overview_request():
    """榜单首屏聚合读取、内存缓存并在过期后静默更新。"""
    state = _read("useAgentRankState.js")
    page = _read("Page.vue")
    assert "const cacheByApi = new WeakMap()" in state
    assert "const USER_CACHE_TTL_MS = 60 * 1000" in state
    assert "getPluginApi(api, 'overview', { username })" in state
    assert "getPluginApi(api, 'board'" not in state
    assert "getPluginApi(api, 'profile'" not in state
    assert "loading.data = !cached" in state
    assert "void fetchUserData(username, entry)" in state
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
    assert "username: clearProfileUser.value, confirm: true" in config
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


def test_ranking_posters_do_not_force_eager_loading():
    """三个榜单页面的海报均按需加载，避免首屏争抢网络。"""
    for name in ("Dashboard.vue", "AppPage.vue", "Page.vue"):
        assert "<VImg" in _read(name)
        assert " eager>" not in _read(name)
