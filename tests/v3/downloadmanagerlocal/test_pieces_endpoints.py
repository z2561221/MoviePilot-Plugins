"""站点 Pieces-hash API 路径选择回归。"""

from unittest.mock import Mock

import pytest
from app.plugins.downloadmanagerlocal.adapter import moviepilot as adapter
from app.plugins.downloadmanagerlocal.service import pieces


@pytest.mark.parametrize(("site_url", "expected_path"), [
    ("https://pt.keepfrds.com/", "/api/torrents/pieces-hash"),
    ("https://hhanclub.net/", "/nexusapi/pieces-hash"),
    ("https://hhanclub.top/", "/nexusapi/pieces-hash"),
    ("https://www.qingwapt.com/", "/api/pieces-hash"),
])
def test_pieces_hash_url_selects_site_specific_path(site_url, expected_path):
    """路径来自当前配置，而非根据域名预选；同一站点可更换入口。"""
    for path in (expected_path, "/my-site/v2/find"):
        assert adapter.pieces_hash_url({"url": site_url, "query_path": path}) == site_url.rstrip("/") + path


@pytest.mark.parametrize(("site_url", "expected_path"), [
    ("https://pt.keepfrds.com/", "/api/torrents/pieces-hash"),
    ("https://hhanclub.net:8443/", "/nexusapi/pieces-hash"),
])
def test_pieces_request_preserves_configured_origin_and_disables_redirects(monkeypatch, site_url, expected_path):
    """凭据只随 JSON 发给绑定站点，保留域名端口且不转发重定向。"""
    client = Mock()
    factory = Mock(return_value=client)
    monkeypatch.setattr(adapter, "RequestUtils", factory)
    fingerprint = "a" * 40
    site = {"url": site_url, "passkey": "test-passkey", "ua": "site-test-agent", "proxy": False}

    site["query_path"] = expected_path
    response = adapter.request_pieces_res(site, [fingerprint])

    assert response is client.post_res.return_value
    factory.assert_called_once_with(
        timeout=25, ua="site-test-agent", proxies=None, verify=True,
        content_type="application/json", accept_type="application/json",
    )
    client.post_res.assert_called_once_with(
        site_url.rstrip("/") + expected_path,
        json={"passkey": "test-passkey", "pieces_hash": [fingerprint]},
        allow_redirects=False,
    )
    client.close.assert_called_once_with()


@pytest.mark.parametrize("path", ["", "https://another.invalid/api", "//another.invalid/api", "/a/../b",
                                  "/a/%2F%2Fevil", "/a?ticket=private", "/a#fragment", "/a\\b", "/a//b"])
def test_invalid_paths_never_leave_the_parser(path):
    """错误不包含可疑路径或原始凭据，也不能回退到任何预置端点。"""
    with pytest.raises(ValueError) as error:
        pieces.parse_site_keys(f"青蛙:{path},private-credential", [{"name": "青蛙", "id": 11, "url": "https://site.test"}])
    assert "第 1 行" in str(error.value) and "private" not in str(error.value)
    with pytest.raises(ValueError):
        adapter.pieces_hash_url({"name": "青蛙", "url": "https://site.test"})


@pytest.mark.parametrize("url", ["http://site.test", "https://user@site.test", "https://site.test/?token=private",
                                 "https://site.test:invalid", "https://user@site.test:8443/base"])
def test_unsafe_mp_site_url_is_rejected_without_echoing_input(url):
    """只容许已绑定的 HTTPS 源，不把站点认证数据或错误值写到提示中。"""
    with pytest.raises(ValueError) as error:
        pieces.parse_site_keys("站名:/custom/query,private", [{"name": "站名", "id": 7, "url": url}])
    assert "第 1 行" in str(error.value) and "private" not in str(error.value)


def test_composed_query_uses_origin_and_preserves_credential(monkeypatch):
    """站点管理地址带路径也只取源，凭据只交给本站 JSON，不拼入 URL。"""
    site = {"url": "https://mp.test:8443/portal/", "id": 1, "name": "新站", "ua": "ua"}
    config = "新站:/custom/lookup,key-demo"
    resolved = pieces.parse_site_keys(config + "\n" + config, [site])
    assert len(resolved) == 1 and resolved[0]["interval"] == 1
    client = Mock()
    monkeypatch.setattr(adapter, "RequestUtils", Mock(return_value=client))
    fingerprint = "a" * 40
    adapter.request_pieces_res(resolved[0], [fingerprint])
    client.post_res.assert_called_once_with("https://mp.test:8443/custom/lookup",
        json={"passkey": "key-demo", "pieces_hash": [fingerprint]}, allow_redirects=False)
