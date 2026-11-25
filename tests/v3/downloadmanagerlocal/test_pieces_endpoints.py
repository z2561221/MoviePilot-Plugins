"""站点 Pieces-hash API 路径选择回归。"""

from unittest.mock import Mock

import pytest
from app.plugins.downloadmanagerlocal.adapter import moviepilot as adapter


@pytest.mark.parametrize(("site_url", "expected_path"), [
    ("https://pt.keepfrds.com/", "/api/torrents/pieces-hash"),
    ("https://hhanclub.net/", "/nexusapi/pieces-hash"),
    ("https://hhanclub.top/", "/nexusapi/pieces-hash"),
    ("https://www.qingwapt.com/", "/api/pieces-hash"),
])
def test_pieces_hash_url_selects_site_specific_path(site_url, expected_path):
    """朋友和憨憨走各自路径，其他站点保留通用路径。"""
    assert adapter.pieces_hash_url({"url": site_url}) == site_url.rstrip("/") + expected_path


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
