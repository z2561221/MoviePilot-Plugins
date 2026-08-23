"""豆瓣中心 V3 Vue 联邦静态合同测试。"""

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
COMPONENTS = REPO_ROOT / "plugins.v3" / "doubancenter" / "src" / "components"
DASHBOARD_BACKEND = REPO_ROOT / "plugins.v3" / "doubancenter" / "dashboard.py"
PLUGIN_ROOT = REPO_ROOT / "plugins.v3" / "doubancenter"


def test_api_client_reads_final_v3_envelope_without_double_unwrap():
    """注入客户端响应不得继续按 Axios 双层结构解包。"""
    source = (COMPONENTS / "api.js").read_text(encoding="utf-8")
    assert "response.data.data" not in source
    assert "return response" in source
    assert "response?.data ?? response" in source


def test_page_and_dashboard_forward_media_identity_pair():
    """详情页和仪表盘订阅请求均优先传递来源与媒体 ID。"""
    for filename in ("Page.vue", "Dashboard.vue"):
        source = (COMPONENTS / filename).read_text(encoding="utf-8")
        assert "media_source: item?.media_source" in source
        assert "media_id: item?.media_id" in source
        assert source.count("season: item?.season || ''") >= 2
        assert "merged.media_source" in source
        assert "merged.media_id" in source
    page = (COMPONENTS / "Page.vue").read_text(encoding="utf-8")
    assert "delete_subscribe_history" in page
    assert "media_source: item?.media_source" in page
    assert "media_id: item?.media_id" in page


def test_rank_dialog_resolves_missing_tmdb_identity_before_enabling_link():
    """榜单条目缺少 TMDB ID 时，详情弹窗应自动识别并显示加载状态。"""
    for filename in ("Page.vue", "Dashboard.vue"):
        source = (COMPONENTS / filename).read_text(encoding="utf-8")
        assert "async function showActionDialog" in source
        assert "if (tmdbIdOf(item)) return" in source
        assert "const media = await resolveRankMedia(rk, item)" in source
        assert "dialogItem.value = { rk, item: media }" in source
        assert "dialogResolving" in source
        assert ":loading=\"dialogResolving\"" in source
        assert ":disabled=\"dialogResolving\"" in source
        assert "if (!dialogItem.value || dialogResolving.value) return" in source
        assert "未找到对应的 TMDB 条目" in source


def test_federation_build_retains_previous_hashed_assets():
    """联邦构建应保留上一代 hash 资源，兼容仍缓存旧入口的浏览器标签。"""
    package = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))
    vite_config = (PLUGIN_ROOT / "vite.config.js").read_text(encoding="utf-8")

    assert package["scripts"]["build"] == "vite build"
    assert "emptyOutDir: false" in vite_config


def test_timeline_image_error_has_visible_placeholder():
    """时间线海报代理失败时仍显示明确占位，不留下空洞。"""
    source = (COMPONENTS / "Dashboard.vue").read_text(encoding="utf-8")
    assert "const timelineImageFailed = ref({})" in source
    assert "function markTimelineImageFailed(key)" in source
    assert "!timelineImageFailed[item.key]" in source
    assert '@error="markTimelineImageFailed(item.key)"' in source
    assert 'class="dc-ph"' in source


def test_dashboard_retries_timeline_without_blocking_core_data():
    """时间线瞬时失败应有限重试，配置与榜单仍优先完成渲染。"""
    source = (COMPONENTS / "Dashboard.vue").read_text(encoding="utf-8")

    assert "const TIMELINE_RETRY_DELAYS_MS = [800, 2500]" in source
    assert "const TIMELINE_RETRY_TIMEOUT_MS = 12000" in source
    assert "async function loadFolioData()" in source
    assert "attempt <= TIMELINE_RETRY_DELAYS_MS.length" in source
    assert "TIMELINE_RETRY_DELAYS_MS[attempt - 1]" in source
    assert "attempt === 0 ? INITIAL_LOAD_TIMEOUT_MS : TIMELINE_RETRY_TIMEOUT_MS" in source
    assert "error?.code === 'PLUGIN_API_TIMEOUT' && attempt > 0" in source
    assert source.index("const folioRequest = Promise.allSettled([loadFolioData()])") < source.index(
        "const coreResults = await Promise.allSettled"
    )
    assert source.index("loading.value = false") < source.index("const [folioResult] = await folioRequest")

    refresh_source = source.split("async function refreshDashboard()", 1)[1].split(
        "function showActionDialog", 1
    )[0]
    assert "await postPluginApi(props.api, 'refresh_rss', {})" in refresh_source
    assert "await load()" in refresh_source
    assert refresh_source.index("await load()") < refresh_source.index("await postPluginApi")
    assert '@click="refreshDashboard"' in source


def test_timeline_api_reads_persisted_data_without_history_repair():
    """时间线 API 只读持久化数据，不同步触发依赖 TMDB 缓存的历史修复。"""
    source = DASHBOARD_BACKEND.read_text(encoding="utf-8")
    function_source = source.split("def api_folio_data(self):", 1)[1].split("\ndef ", 1)[0]

    assert "dashboard_folio_service.get_folio_data(self)" in function_source
    assert "repair_folio_history" not in function_source


def test_archive_view_is_paginated_without_forcing_home_page_scroll():
    """详情首页自然伸展，仅详情与发现页的归档状态承载内部滚动。"""
    page = (COMPONENTS / "Page.vue").read_text(encoding="utf-8")
    app_page = (COMPONENTS / "AppPage.vue").read_text(encoding="utf-8")
    base_page_rule = next(line for line in page.splitlines() if line.startswith(".dc-page {"))
    base_flow_rule = next(line for line in page.splitlines() if line.startswith(".dc-flow {"))

    assert "page_size: 10" in page
    assert "function goArchivePage" in page
    assert "archiveData.total_pages > 1" in page
    assert "goArchivePage(archiveData.page - 1)" in page
    assert "goArchivePage(archiveData.page + 1)" in page
    assert "if (archivePage.value) await loadArchive()" in page
    assert "'dc-page--archive': archivePage" in page
    assert ".dc-page--archive { height: clamp(640px, calc(100dvh - 48px), 860px)" in page
    assert ".dc-page--app.dc-page--archive { height: calc(100dvh - 104px)" in page
    assert ".dc-page--archive .dc-flow { flex: 1 1 auto; min-height: 0; overflow-y: auto" in page
    assert "height:" not in base_page_rule
    assert "overflow-y:" not in base_flow_rule
    assert "import Page from './Page.vue'" in app_page
    assert "app-page" in app_page
