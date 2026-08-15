"""豆瓣中心 V3 Vue 联邦静态合同测试。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
COMPONENTS = REPO_ROOT / "plugins.v3" / "doubancenter" / "src" / "components"


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
        assert "merged.media_source" in source
        assert "merged.media_id" in source
    page = (COMPONENTS / "Page.vue").read_text(encoding="utf-8")
    assert "delete_subscribe_history" in page
    assert "media_source: item?.media_source" in page
    assert "media_id: item?.media_id" in page


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
