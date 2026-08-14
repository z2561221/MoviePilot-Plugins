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
