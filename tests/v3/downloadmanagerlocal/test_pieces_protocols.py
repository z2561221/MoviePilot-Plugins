"""青蛙助手协议覆盖与凭据边界的隔离回归，不访问真实站点。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.plugins.downloadmanagerlocal.adapter import moviepilot as adapter
from app.plugins.downloadmanagerlocal.service import pieces


@pytest.mark.parametrize("name", ["青蛙", "AGSVPT", "红豆饭", "麒麟", "UBits", "聆音", "通用站点"])
def test_standard_sites_share_the_frog_passkey_protocol(name):
    """通用适配不限制站名，不为每个站点复制一套查询链路。"""
    site = {"name": name, "url": "https://tracker.example/", "passkey": "test-key"}
    assert adapter.is_flux_site(site) is False
    with pytest.raises(ValueError, match="查询路径"):
        adapter.pieces_hash_url(site)


def test_hhan_exact_name_does_not_override_query_path():
    """憨憨不再按站名选路径，改路径不需要插件内置新规则。"""
    site = {"name": "憨憨", "url": "https://configured.example:8443/", "passkey": "test-key"}
    site["query_path"] = "/private-api/match"
    assert adapter.pieces_hash_url(site) == "https://configured.example:8443/private-api/match"


@pytest.mark.parametrize(("name", "credential"), [
    ("FluxTorrent", "fxo_test"), ("好学", "fxo_test"), ("自定义站点", "fxo_test"),
])
def test_flux_sites_use_native_endpoints_and_header_authentication(monkeypatch, name, credential):
    """Flux 令牌只进入认证头，查询体只含原始 pieces 指纹。"""
    client = Mock()
    factory = Mock(return_value=client)
    monkeypatch.setattr(adapter, "RequestUtils", factory)
    site = {"name": name, "url": "https://configured.example:8443/", "passkey": credential,
            "ua": "test-agent", "proxy": False}
    site["query_path"] = "/custom/token-lookup"
    fingerprints = ["a" * 40]

    adapter.request_pieces_res(site, fingerprints)

    assert adapter.is_flux_site(site) is True
    options = factory.call_args.kwargs
    assert options["headers"]["Authorization"] == "Token " + credential
    assert options["headers"]["User-Agent"] == "test-agent"
    assert options["headers"]["Content-Type"] == "application/json"
    assert options["verify"] is True
    assert "cookies" not in options
    client.post_res.assert_called_once_with(
        "https://configured.example:8443/custom/token-lookup",
        json={"pieces_sha1": fingerprints}, allow_redirects=False,
    )
    client.close.assert_called_once_with()


def test_flux_results_keep_every_candidate_and_deduplicate_repeated_ids(monkeypatch):
    """query 是原指纹，match 是类型；同指纹多个种子编号不能互相覆盖。"""
    fingerprint = "a" * 40
    payload = {"code": 0, "data": {"results": [
        {"query": fingerprint, "match": "pieces_sha1", "torrent_id": 11,
         "download_url": "https://untrusted.example/ignored"},
        {"query": fingerprint, "match": "pieces_sha1", "torrent_id": "12"},
        {"query": fingerprint, "match": "pieces_sha1", "torrent_id": 11},
    ]}}
    response = SimpleNamespace(status_code=200, json=lambda: payload)
    monkeypatch.setattr(pieces, "request_pieces_res", lambda *_: response)

    matches, cooldown, error = pieces.query_site({"name": "任意站", "passkey": "fxo_" + "fixture"}, [fingerprint])

    assert matches == {fingerprint: ["11", "12"]}
    assert cooldown == 0
    assert error == ""


@pytest.mark.parametrize("data", [
    {"results": None}, {"results": {}},
    {"results": [{"query": "b" * 40, "match": "pieces_sha1", "torrent_id": 1}]},
    {"results": [{"query": "a" * 40, "match": "info_hash_v1", "torrent_id": 1}]},
    {"results": [{"query": "a" * 40, "match": "pieces_sha1", "torrent_id": True}]},
    {"results": [{"query": "a" * 40, "match": "pieces_sha1", "torrent_id": "../fxo_test"}]},
])
def test_flux_malformed_results_fail_without_becoming_empty_success(monkeypatch, data):
    """未知指纹、类型和编号都拒绝，不在错误里带出回包正文。"""
    response = SimpleNamespace(status_code=200, json=lambda: {"code": 0, "data": data})
    monkeypatch.setattr(pieces, "request_pieces_res", lambda *_: response)

    matches, cooldown, error = pieces.query_site({"name": "任意站", "passkey": "fxo_" + "fixture"}, ["a" * 40])

    assert matches == {}
    assert cooldown > 0
    assert "格式" in error
    assert "fxo_test" not in error


def test_flux_empty_results_are_normal_empty_matches(monkeypatch):
    """已成功处理的空候选列表不应被判断为站点故障。"""
    response = SimpleNamespace(status_code=200, json=lambda: {"code": 0, "data": {"results": []}})
    monkeypatch.setattr(pieces, "request_pieces_res", lambda *_: response)
    assert pieces.query_site({"name": "任意站", "passkey": "fxo_" + "fixture"}, ["a" * 40]) == ({}, 0, "")


def test_flux_download_follows_same_origin_temporary_redirect_without_passkey_query(monkeypatch):
    """跟随原站点临时下载跳转，不把开放令牌放进 URL 或 Cookie。"""
    redirected = SimpleNamespace(status_code=302, headers={"Location": "/download/11?ticket=temporary"}, close=Mock())
    downloaded = SimpleNamespace(status_code=200, headers={}, content=b"torrent-test", close=Mock())
    client = Mock()
    client.get_res.side_effect = [redirected, downloaded]
    factory = Mock(return_value=client)
    monkeypatch.setattr(adapter, "RequestUtils", factory)
    site = {"name": "好学", "url": "https://configured.example/", "passkey": "fxo_test", "ua": "test-agent"}

    content = adapter.request_pieces_torrent(site, "11")

    assert content == b"torrent-test"
    options = factory.call_args.kwargs
    assert options["headers"]["Authorization"] == "Token fxo_test"
    assert options["verify"] is True
    assert "cookies" not in options
    requests = client.get_res.call_args_list
    assert requests[0].args == ("https://configured.example/api/v1/crossseed/dl/11",)
    assert requests[1].args == ("https://configured.example/download/11?ticket=temporary",)
    assert all(call.kwargs == {"allow_redirects": False} for call in requests)
    redirected.close.assert_called_once_with()
    downloaded.close.assert_called_once_with()
    client.close.assert_called_once_with()


@pytest.mark.parametrize("location", [
    "https://other.example/download/11?ticket=private", "http://configured.example/download/11",
    "https://configured.example:8443/download/11", "https://user@configured.example/download/11",
])
def test_flux_download_does_not_forward_credentials_outside_the_configured_origin(monkeypatch, location):
    """跨域、降级、换端口与 URL 用户信息均不能接走 Token。"""
    response = SimpleNamespace(status_code=302, headers={"Location": location}, close=Mock())
    client = Mock()
    client.get_res.return_value = response
    monkeypatch.setattr(adapter, "RequestUtils", Mock(return_value=client))
    site = {"name": "FluxTorrent", "url": "https://configured.example/", "passkey": "fxo_test"}

    with pytest.raises(adapter.SiteDownloadError, match="超出站点范围") as caught:
        adapter.request_pieces_torrent(site, "11")

    assert "private" not in str(caught.value)
    assert "fxo_test" not in str(caught.value)
    client.get_res.assert_called_once()
    response.close.assert_called_once_with()
    client.close.assert_called_once_with()


def test_flux_redirect_limit_is_bounded_and_every_response_is_closed(monkeypatch):
    """循环跳转停止在固定次数，不无限重试下载端点。"""
    responses = [SimpleNamespace(status_code=302, headers={"Location": "/repeat"}, close=Mock()) for _index in range(4)]
    client = Mock()
    client.get_res.side_effect = responses
    monkeypatch.setattr(adapter, "RequestUtils", Mock(return_value=client))

    with pytest.raises(adapter.SiteDownloadError, match="次数超限"):
        adapter.request_pieces_torrent({"name": "FluxTorrent", "url": "https://configured.example/", "passkey": "fxo_test"}, "11")

    assert client.get_res.call_count == 4
    for response in responses:
        response.close.assert_called_once_with()
    client.close.assert_called_once_with()
