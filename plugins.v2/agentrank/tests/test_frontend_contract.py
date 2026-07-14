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


def test_discovery_cards_use_non_black_theme_surface():
    """发现页榜单条目使用主题灰面而不是黑色 surface。"""
    app_page = _read("AppPage.vue")
    item_style = next(
        line for line in app_page.splitlines() if line.startswith(".ar-app-page__item {")
    )
    assert "surface-variant" in item_style
    assert "background: rgb(var(--v-theme-surface));" not in item_style


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
