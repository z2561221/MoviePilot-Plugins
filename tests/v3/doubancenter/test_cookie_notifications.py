"""CK 请求失败的强制告警与常规通知开关回归。"""

from types import SimpleNamespace

import pytest
from app.plugins.doubancenter.adapter import douban_account
from app.plugins.doubancenter.service import folio


def _plugin(post_message):
    return SimpleNamespace(
        _notify=False, _folio_notify=False, _wish_notify=False, _folio_cookie="dbcl2=test-cookie",
        plugin_name="豆瓣中心", post_message=post_message,
    )


def _mock_homepage(monkeypatch, response):
    monkeypatch.setattr(
        douban_account.DoubanApi, "_request_utils",
        staticmethod(lambda **_: SimpleNamespace(get_res=lambda _url: response)),
    )


@pytest.mark.parametrize("response", [
    None,
    SimpleNamespace(headers={}),
    SimpleNamespace(headers={"Set-Cookie": 'ck="deleted"; Path=/'}),
])
def test_ck_failure_notifies_with_all_plugin_notification_switches_off(monkeypatch, response):
    """真实 CK 获取分支无响应、无令牌或令牌删除时均强制通知。"""
    messages = []
    plugin = _plugin(lambda **message: messages.append(message))
    _mock_homepage(monkeypatch, response)
    client = folio._create_douban_api(plugin)
    assert not client.ck
    assert len(messages) == 1
    assert messages[0]["title"] == "豆瓣 CK 请求失败"
    assert messages[0]["parse_mode"] == "plain"
    assert "test-cookie" not in messages[0]["text"]
    assert plugin._notify is plugin._folio_notify is plugin._wish_notify is False


def test_ck_success_is_silent_and_ordinary_failure_still_respects_switch(monkeypatch):
    """强制告警只覆盖 CK 故障，普通想看失败仍尊重原开关。"""
    messages = []
    plugin = _plugin(lambda **message: messages.append(message))
    _mock_homepage(monkeypatch, SimpleNamespace(headers={"Set-Cookie": "ck=valid; Path=/"}))
    assert folio._create_douban_api(plugin).ck == "valid"
    folio._send_wish_notification(plugin, "普通想看失败")
    assert messages == []


def test_repeated_ck_failure_keeps_existing_throttle(monkeypatch):
    """一次业务中的重复建连失败只通知一次，且不修改通知配置。"""
    messages = []
    plugin = _plugin(lambda **message: messages.append(message))
    _mock_homepage(monkeypatch, None)
    folio._create_douban_api(plugin)
    folio._create_douban_api(plugin)
    assert len(messages) == 1


def test_delivery_exception_does_not_consume_ck_alert_throttle(monkeypatch):
    """通知发送失败后，下次 CK 故障仍有机会发出告警。"""
    attempts = []

    def post_message(**message):
        attempts.append(message)
        if len(attempts) == 1:
            raise RuntimeError("notification transport unavailable")

    plugin = _plugin(post_message)
    _mock_homepage(monkeypatch, None)
    folio._create_douban_api(plugin)
    folio._create_douban_api(plugin)
    assert len(attempts) == 2
    assert plugin._wish_notification_last_times["cookie_invalid"] > 0


@pytest.mark.parametrize("response,expected", [
    (None, "network_error"),
    (SimpleNamespace(status_code=503), "http_error"),
    (SimpleNamespace(status_code=403), "blocked"),
    (SimpleNamespace(status_code=429), "blocked"),
    (SimpleNamespace(status_code=401), "login_required"),
    (SimpleNamespace(status_code=200, text="验证码"), "blocked"),
    (SimpleNamespace(status_code=200, text="", url="https://sec.douban.com/"), "blocked"),
    (SimpleNamespace(status_code=200, text="", url="https://accounts.douban.com/passport/login"), "login_required"),
    (SimpleNamespace(status_code=200, text='<form action="https://accounts.douban.com/login"></form>'), "login_required"),
    (SimpleNamespace(status_code=200, text='<a href="/accounts/logout?ck=secret">退出</a>'), "valid"),
    (SimpleNamespace(status_code=200, text='<a href="https://accounts.douban.com/passport/login">登录</a>'), "unknown"),
    (SimpleNamespace(status_code=200, text='<div class="title">肖申克的救赎</div>'), "unknown"),
    (SimpleNamespace(status_code=200, text='<a href="https://example.com/accounts/logout">退出</a>'), "unknown"),
])
def test_login_status_requires_account_evidence(response, expected):
    """区分网络、风控和账号证据，普通登录链接与搜索结果不证明登录状态。"""
    client = object.__new__(douban_account.DoubanApi)
    client._account_response = response
    status, reason = client.get_login_status()
    assert status == expected
    assert reason
    assert "secret" not in reason


@pytest.mark.parametrize("status", ["valid", "network_error", "http_error", "blocked", "unknown"])
def test_cookie_probe_does_not_send_false_sync_alert(monkeypatch, status):
    """健康探测不搜索影片，不安装 CK 告警回调，并按小时节流。"""
    messages, calls = [], []
    plugin = _plugin(lambda **message: messages.append(message))
    plugin._folio_notify = plugin._wish_notify = True

    def client(**kwargs):
        """只暴露登录探测，旧搜索路径调用会使测试失败。"""
        calls.append(kwargs)
        return SimpleNamespace(get_login_status=lambda: (status, "测试响应"))

    monkeypatch.setattr(folio, "DoubanApi", client)
    folio.check_cookie_periodically(plugin)
    folio.check_cookie_periodically(plugin)
    assert calls == [{"user_cookie": "dbcl2=test-cookie"}]
    assert messages == []


@pytest.mark.parametrize("enabled", [True, False])
def test_confirmed_login_alert_uses_folio_switch_and_own_title(monkeypatch, enabled):
    """登录异常使用观影开关与独立标题，不冒充想看同步失败。"""
    messages = []
    plugin = _plugin(lambda **message: messages.append(message))
    plugin._folio_notify = enabled
    monkeypatch.setattr(folio, "DoubanApi", lambda **_: SimpleNamespace(
        get_login_status=lambda: ("login_required", "HTTP 401")))
    folio.check_cookie_periodically(plugin)
    plugin._last_cookie_check_time = 0
    folio.check_cookie_periodically(plugin)
    assert len(messages) == int(enabled)
    if enabled:
        assert messages[0]["title"] == "豆瓣登录状态异常"
        assert "想看" not in messages[0]["text"]


def test_probe_exception_is_unknown_and_does_not_leak_secret(monkeypatch):
    """探测异常不发失效通知，日志不输出可能包含凭据的异常正文。"""
    messages, logs = [], []
    plugin = _plugin(lambda **message: messages.append(message))
    plugin._folio_notify = plugin._wish_notify = True

    def fail(**kwargs):
        """模拟包含敏感正文的网络异常。"""
        raise RuntimeError("sensitive-cookie")

    monkeypatch.setattr(folio, "DoubanApi", fail)
    monkeypatch.setattr(folio, "logger", SimpleNamespace(warning=logs.append))
    folio.check_cookie_periodically(plugin)
    assert messages == []
    assert len(logs) == 1 and "RuntimeError" in logs[0]
    assert "sensitive-cookie" not in logs[0]
