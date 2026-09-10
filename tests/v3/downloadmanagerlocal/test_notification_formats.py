"""下载通知 HTML 路由、动态字段和原消息编辑回归。"""

from html.parser import HTMLParser
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.service import speed_actions, speed_notification


class CardParser(HTMLParser):
    """检查格式标签完整并收集可见正文。"""

    def __init__(self):
        """初始化标签栈和正文。"""
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        """仅允许通知模板使用的标签。"""
        assert tag in {"b", "code"}
        self.tags.append(tag)

    def handle_endtag(self, tag):
        """验证闭合标签没有被长度截断。"""
        assert self.tags.pop() == tag

    def handle_data(self, data):
        """收集解码后的正文。"""
        self.text.append(data)


def test_speed_alert_routes_html_and_keeps_risk_with_long_fields(monkeypatch):
    """长种子名安全截断，Telegram 保留按钮，其余渠道收到完整纯文本语义。"""
    from app.sdk.services import ServiceConfigHelper

    monkeypatch.setattr(ServiceConfigHelper, "get_notification_configs", lambda: [
        SimpleNamespace(name="tg", type="telegram", enabled=True, switchs=["插件"]),
        SimpleNamespace(name="wechat", type="wechat", enabled=True, switchs=["插件"]),
    ])
    messages = []
    plugin = SimpleNamespace(
        _speed_monitor_telegram_userid="1001", _speed_monitor_notification_type="Plugin",
        post_message=lambda **kwargs: messages.append(kwargs),
    )
    session = SimpleNamespace(
        downloader_id="qB <A&B>", name="影片🔬 <标题> & '名称' " * 150,
        torrent_hash="abc123", total_bytes=1024**3,
    )
    alert = {"decision": {"progress": 0.5, "allowed_seconds": 60}}
    assert speed_notification.send_speed_alert(plugin, alert, session, now=100, token_factory=lambda: "token")
    assert len(messages) == 3
    telegram, wechat, history = messages
    assert telegram["source"] == "tg" and telegram["parse_mode"] == "HTML"
    assert "<code>abc123</code>" in telegram["text"]
    assert len(telegram["text"].encode("utf-16-le")) // 2 < 3000
    parser = CardParser()
    parser.feed(telegram["text"])
    parser.close()
    assert not parser.tags
    assert "qB <A&B>" in "".join(parser.text)
    assert "允许时限：1分0秒" in "".join(parser.text)
    assert "不可恢复" in "".join(parser.text)
    assert len(telegram["buttons"][0]) == 2
    assert wechat["parse_mode"] == "plain" and "<b>" not in wechat["text"]
    assert "qB <A&B>" in wechat["text"]
    assert "buttons" not in wechat and "buttons" not in history
    assert telegram["save_history"] is False and wechat["save_history"] is False
    assert history["parse_mode"] == "plain"


@pytest.mark.parametrize("buttons", [None, [[{"text": "确认", "callback_data": "confirm"}]]])
def test_action_edit_passes_html_mode_through_module_dispatch(buttons):
    """有按钮确认卡和无按钮终态均走支持 HTML 的编辑入口。"""
    calls = []
    plugin = SimpleNamespace(
        chain=SimpleNamespace(run_module=lambda method, **kwargs: calls.append((method, kwargs)) or True),
        post_message=lambda **kwargs: pytest.fail("原消息编辑成功后不能另发通知"),
    )
    speed_actions._post_action_card(
        plugin, {"source": "tg", "original_message_id": 7, "original_chat_id": "1001"},
        title="确认 <删除>", text="A & B <任务>", buttons=buttons, telegram_userid="1001",
    )
    method, payload = calls[0]
    assert method == "edit_message"
    assert payload["message_id"] == 7 and payload["chat_id"] == "1001"
    assert payload["parse_mode"] == "HTML"
    assert payload["text"] == "A &amp; B &lt;任务&gt;"
    assert payload["buttons"] == buttons
