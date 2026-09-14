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
