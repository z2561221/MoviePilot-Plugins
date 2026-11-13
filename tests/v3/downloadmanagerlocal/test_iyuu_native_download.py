"""issue #52 的宿主配方、辅种路径、认证隔离和失败缓存回归。"""

import base64
import json
import threading
from copy import deepcopy
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from app.plugins.downloadmanagerlocal.adapter import moviepilot as adapter
from app.plugins.downloadmanagerlocal.service import iyuu
from app.plugins.downloadmanagerlocal.utils.sensitive import mask_sensitive_url


def site(kind):
    """提供不连接网络的站点认证替身。"""
    return {"id": 1, "name": kind, "url": "https://piggo.me/" if kind == "piggo" else "https://www.hxpt.org/",
            "apikey": "test-api-key", "cookie": "test-browser-cookie", "ua": "test-UA", "proxy": False}


def test_piggo_recipe_uses_host_post_protocol_and_does_not_expose_credentials():
    value = adapter.native_iyuu_download_url(site("piggo"), 29664)
    encoded, url = value[1:].split("]", 1)
    recipe = json.loads(base64.b64decode(encoded))
    assert url == "https://api.piggo.me/v1/api/torrents/29664/download-link"
    assert recipe["method"] == "post" and recipe["json"] == {}
    assert recipe["header"]["Authorization"] == "Bearer test-api-key"
    assert recipe["header"]["User-Agent"] == "test-UA"
    assert recipe["cookie"] is False and recipe["allow_redirects"] is False
    assert recipe["protocol"] == "Piggo" and recipe["result"] == "data.url"
    masked = mask_sensitive_url(value)
    assert encoded not in masked and "test-api-key" not in masked
    assert masked == "[下载配方已隐藏]" + url


@pytest.mark.parametrize("apikey,token", [("", "fallback-token"), ("   ", "fallback-token")])
def test_native_sites_use_token_when_api_key_is_empty(apikey, token):
    for kind in ("piggo", "hxpt"):
        value = adapter.native_iyuu_download_url(dict(site(kind), apikey=apikey, token=token), 12)
        if kind == "piggo":
            encoded = value[1:].split("]", 1)[0]
            assert json.loads(base64.b64decode(encoded))["header"]["Authorization"] == "Bearer " + token
        else:
            assert value.endswith("id=12&apikey=" + token)


def test_hxpt_uses_v326_compat_download_builder_and_masks_api_key():
    value = adapter.native_iyuu_download_url(site("hxpt"), "29664")
    assert value == "https://www.hxpt.org/api/v1/compat/nexusphp/download.php?id=29664&apikey=test-api-key"
    assert "apikey=***" in mask_sensitive_url(value) and "test-api-key" not in mask_sensitive_url(value)


@pytest.mark.parametrize("tid", [None, "0", -1, "1&apikey=other", True])
def test_invalid_native_torrent_id_does_not_generate_authenticated_url(tid):
    with pytest.raises(ValueError):
        adapter.native_iyuu_download_url(site("piggo"), tid)


@pytest.mark.parametrize("url", ["https://piggo.me.evil.invalid/", "https://piggo.me@evil.invalid/", "https://example.invalid/"])
def test_native_routing_requires_exact_site_host(url):
    assert adapter.native_iyuu_site({"url": url}) == ""


def test_indirect_content_uses_host_content_stage_and_preserves_failure_reason(monkeypatch):
    calls = []

    def download(torrent):
        """模拟宿主取内容阶段回传具体鉴权失败，不发送消息。"""
        calls.append(torrent)
        return None, "", [], "换票失败：猪猪存取令牌已过期或无效"

    monkeypatch.setattr(adapter, "DownloadChain", lambda: SimpleNamespace(_get_torrent_content=download))
    monkeypatch.setattr(adapter, "TorrentHelper", lambda: pytest.fail("编码配方不能直接进入二进制下载 helper"))
    result = adapter.download_torrent_content("[encoded]https://api.piggo.me/", cookie=None,
                                             ua="test-UA", site_id=1, site_name="猪猪")
    assert result[1] is None and "存取令牌" in result[4]
    assert calls[0].enclosure.startswith("[") and calls[0].site == 1
    assert not calls[0].site_cookie and calls[0].site_ua == "test-UA"


def test_plain_content_keeps_existing_helper_contract(monkeypatch):
    calls = []
    monkeypatch.setattr(adapter, "TorrentHelper", lambda: SimpleNamespace(
        download_torrent=lambda **kwargs: calls.append(kwargs) or (None, b"torrent", "", [], "")))
    assert adapter.download_torrent_content("https://example.invalid/download", cookie="cookie")[1] == b"torrent"
    assert calls == [{"url": "https://example.invalid/download", "cookie": "cookie", "ua": None, "proxy": None}]


def test_missing_host_content_stage_returns_retryable_error(monkeypatch):
    """不支持该内容接口的宿主不能把编码地址交回旧 GET helper。"""
    monkeypatch.setattr(adapter, "DownloadChain", lambda: SimpleNamespace())
    monkeypatch.setattr(adapter, "TorrentHelper", lambda: pytest.fail("不能回退到旧 helper"))
    result = adapter.download_torrent_content("[encoded]https://api.piggo.me/", cookie=None)
    assert result[1] is None and result[4].startswith("换票失败：")


def runtime_case(monkeypatch, kind, error=""):
    """执行真实辅种方法，替换站点 HTTP 和目标提交边界。"""
    data, downloads, additions = {}, [], []
    config = site(kind)
    plugin = SimpleNamespace(
        _event=threading.Event(), _transfer_stop_generation=0, _iyuu_sites=[],
        _iyuu_total=0, _iyuu_realtotal=0, _iyuu_fail=0, _iyuu_cached=0, _iyuu_exist=0,
        _iyuu_error_caches=[], _iyuu_permanent_error_caches=[],
        iyuu_helper=SimpleNamespace(get_torrent_url=lambda _: (config["url"], "download.php?id={}&passkey={passkey}")),
        get_data=lambda key=None: deepcopy(data.get(key)),
        save_data=lambda key, value: data.__setitem__(key, deepcopy(value)),
    )
    service = SimpleNamespace(name="TR", type="transmission", instance=SimpleNamespace(get_torrents=lambda **_: ([], None)))

    def content(**kwargs):
        """只记录下载请求，测试不进行真实取种。"""
        downloads.append(kwargs)
        return None, None if error else b"torrent", "", [], error

    monkeypatch.setattr(iyuu, "check_site", lambda _: (False, ""))
    monkeypatch.setattr(iyuu, "get_url_domain", lambda url: urlsplit(url).hostname)
    monkeypatch.setattr(iyuu, "download_torrent_content", content)
    monkeypatch.setattr(iyuu, "is_torrent_content", lambda _: True)
    monkeypatch.setattr(iyuu, "request_get_res", lambda *_, **__: pytest.fail("API 站点不能回退 details.php"))
    monkeypatch.setattr(iyuu, "iyuu_download", lambda *_, **kwargs: additions.append(kwargs) or "child")
    monkeypatch.setattr(iyuu, "_finish_iyuu_pending", lambda *_: True)
    return plugin, service, config, downloads, additions


@pytest.mark.parametrize("kind", ["piggo", "hxpt"])
def test_native_seeding_downloads_once_without_cookie_or_https_suffix(monkeypatch, kind):
    plugin, service, config, downloads, additions = runtime_case(monkeypatch, kind)
    assert iyuu.iyuu_download_torrent(plugin, {"sid": 1, "torrent_id": 29664, "info_hash": "child"},
                                    service, "/seed", "", source_hash="mother", site_info=config)
    assert len(downloads) == len(additions) == 1
    assert downloads[0]["cookie"] is None and downloads[0]["site_id"] == 1
    assert "https=1" not in downloads[0]["url"]
    assert not plugin._iyuu_error_caches and not plugin._iyuu_permanent_error_caches


@pytest.mark.parametrize("error", ["下载种子出错，状态码：403", "换票失败：猪猪存取令牌已过期或无效",
                                  "站点限流：HTTP 429", "换票失败：有未读必读公告，请到网页端阅读后重试"])
def test_native_auth_and_rate_errors_remain_retryable_without_html_fallback(monkeypatch, error):
    plugin, service, config, downloads, additions = runtime_case(monkeypatch, "piggo", error)
    assert not iyuu.iyuu_download_torrent(plugin, {"sid": 1, "torrent_id": 29664, "info_hash": "child"},
                                        service, "/seed", "", source_hash="mother", site_info=config)
    assert plugin._iyuu_error_caches == ["child"] and not plugin._iyuu_permanent_error_caches
    assert len(downloads) == 1 and not additions


def test_force_page_cannot_send_native_site_to_legacy_details(monkeypatch):
    monkeypatch.setattr(iyuu, "request_get_res", lambda *_, **__: pytest.fail("不能请求网页"))
    for kind in ("piggo", "hxpt"):
        expected = iyuu.iyuu_get_download_url(None, {"torrent_id": 5}, site(kind), "obsolete/{}")
        assert iyuu.iyuu_get_download_url(None, {"torrent_id": 5}, site(kind), "obsolete/{}", force_page=True) == expected


def test_unterminated_recipe_is_hidden_even_when_url_parsing_fails():
    assert mask_sensitive_url("[test-private-recipe") == "[下载配方已隐藏]"


def test_nonsecret_query_is_preserved_and_malformed_address_cannot_echo_api_key():
    """脱敏不能把正常地址替换成末尾查询值，也不能回显无法解析地址中的凭据。"""
    value = "https://example.invalid/download.php?id=5&https=1"
    assert mask_sensitive_url(value) == value
    assert mask_sensitive_url("[test-private-recipe]" + value) == "[下载配方已隐藏]" + value
    assert "test-api-key" not in mask_sensitive_url("[test-private-recipe]https://[bad?apikey=test-api-key")


@pytest.mark.parametrize("status", [200, 401])
def test_host_chain_redeems_piggo_recipe_and_never_forwards_bearer_to_final_get(monkeypatch, status):
    """运行真实 v3.2.6 DownloadChain，只替换 HTTP、额度等待和二进制下载端口。"""
    from app.chain.download import submission
    from app.modules.indexer.spider.piggo import PiggoSpider

    calls, closed, notifications = [], [], []
    recipe = adapter.native_iyuu_download_url(site("piggo"), 29664)
    final_url = "https://download.piggo.me/29664.torrent?token=test-ticket"
    response = SimpleNamespace(
        status_code=status, headers={"Content-Type": "application/json"},
        text=json.dumps({"code": "0" if status == 200 else "401", "data": {"url": final_url}}),
        content=json.dumps({"code": "0" if status == 200 else "401", "data": {"url": final_url}}).encode(),
        url="https://api.piggo.me/v1/api/torrents/29664/download-link",
        json=lambda: {"code": "0" if status == 200 else "401", "data": {"url": final_url}},
        close=lambda: closed.append(True),
    )

    def post(url, **kwargs):
        """保存换票参数并返回隔离 JSON 响应。"""
        calls.append(("POST", url, kwargs))
        return response

    def binary(**kwargs):
        """保存最终下载参数，提供替身种子内容。"""
        calls.append(("GET", kwargs["url"], kwargs))
        return None, b"test-torrent", "folder", ["A.mkv"], ""

    def parse(_method, **kwargs):
        """保持真实 Piggo 响应验证，替换宿主模块派发边界。"""
        return PiggoSpider.parse_download_response(
            status_code=kwargs["status_code"], payload=kwargs["payload"], request_params=kwargs["request_params"])

    chain = object.__new__(adapter.DownloadChain)
    monkeypatch.setattr(chain, "run_module", parse)
    monkeypatch.setattr(chain, "post_message", lambda value: notifications.append(value))
    monkeypatch.setattr(adapter, "DownloadChain", lambda: chain)
    monkeypatch.setattr(submission, "_download_ports_snapshot", lambda: (SimpleNamespace(post=post), None))
    monkeypatch.setattr(submission, "site_request_config", lambda *_: {"domain": "piggo.me"})
    monkeypatch.setattr(submission, "wait_for_site_request", lambda _: None)
    monkeypatch.setattr(submission, "get_chain_runtime_config_snapshot", lambda: SimpleNamespace(proxy={}))
    monkeypatch.setattr(submission, "is_expiring_download_url", lambda _: False)
    monkeypatch.setattr(submission, "torrent_resource_identity", lambda _: None)
    monkeypatch.setattr(submission, "TorrentHelper", lambda: SimpleNamespace(is_invalid=lambda _: False, download_torrent=binary))
    result = adapter.download_torrent_content(recipe, cookie=None, ua="test-UA", site_name="猪猪")
    assert calls[0][0:2] == ("POST", "https://api.piggo.me/v1/api/torrents/29664/download-link")
    assert calls[0][2]["headers"]["Authorization"] == "Bearer test-api-key"
    assert calls[0][2]["cookies"] is None and calls[0][2]["json_body"] == {}
    assert calls[0][2]["allow_redirects"] is False and closed == [True]
    assert not notifications
    if status == 200:
        assert result[1] == b"test-torrent" and len(calls) == 2
        assert calls[1][0:2] == ("GET", final_url)
        assert calls[1][2]["cookie"] is None and "headers" not in calls[1][2]
    else:
        assert result[1] is None and len(calls) == 1
        assert "存取令牌" in result[4] and "test-api-key" not in result[4]
