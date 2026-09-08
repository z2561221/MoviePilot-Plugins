"""通知格式、长文本和宿主图片拆分边界回归。"""

import html
from html.parser import HTMLParser
from types import SimpleNamespace

import pytest
from app.plugins.agentrank.model.board import RecommendationBoard, RecommendationItem
from app.plugins.agentrank.service.notification import NotificationService
from app.plugins.agentrank.service.telegram_interaction import TelegramSelectionService


class CaptionParser(HTMLParser):
    """核对完整标签并收集 Telegram 实际可见文字。"""

    def __init__(self):
        """初始化标签栈和正文。"""
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        """记录本测试支持的 Telegram HTML 标签。"""
        assert tag in {"b", "i", "a", "code"}
        self.tags.append(tag)

    def handle_endtag(self, tag):
        """要求闭合标签与最近的开始标签一致。"""
        assert self.tags.pop() == tag

    def handle_data(self, data):
        """保留解码后的可见文本。"""
        self.text.append(data)


def _caption(message):
    """按已核验的宿主行为组装最终图片说明。"""
    text = f'<b>{html.escape(message["title"])}</b>\n{message["text"]}'
    if message.get("link"):
        text += f'\n<a href="{html.escape(message["link"], quote=True)}">查看详情</a>'
    return text


@pytest.mark.parametrize("field", ["长标题推荐理由", "🔬🌌<&>\"'"])
def test_five_item_caption_and_edit_fit_host_and_telegram_limits(monkeypatch, field):
    """五条长推荐首次发送和带提示编辑均保持单张图片、完整标签和全部按钮。"""
    messages = []
    plugin = SimpleNamespace(post_message=lambda **kwargs: messages.append(kwargs))
    service = object.__new__(TelegramSelectionService)
    service._plugin = plugin
    service._config = {"agent_display_name": field * 20}
    link = "https://moviepilot.example/" + "x" * 80 + "?a=1&b=2"
    monkeypatch.setattr(service, "_selection_detail_link", lambda: link)
    board = RecommendationBoard(
        profile_id="alice", username="alice", run_id="run-long", status="success",
        recommendations=[
            RecommendationItem(
                candidate_id=f"tmdb:{index}", rank=index, title=field * 40,
                reason=field * 120, summary="完整简介" * 180, year=2026,
                source_ids={"tmdb": str(index)}, media_type="movie",
                backdrop_path="https://image.example/backdrop.jpg",
            )
            for index in range(1, 6)
        ],
    )
    session = SimpleNamespace(
        candidate_ids=[item.candidate_id for item in board.recommendations],
        selected_ids=[], token="token", username="alice", telegram_userid="1001",
    )
    service._post(session, board)
    session.selected_ids = session.candidate_ids[:2]
    service._post(session, board, {"original_message_id": 11, "original_chat_id": "1001"}, field * 120)
    for message in messages:
        caption = _caption(message)
        assert len(caption) < 1024
        parser = CaptionParser()
        parser.feed(caption)
        parser.close()
        assert not parser.tags
        assert len("".join(parser.text).encode("utf-16-le")) // 2 <= 1024
        assert message["text"].count("<code>") == 5
        assert message["text"].count("<b>推荐：</b>") == 5
        assert "完整简介完整简介" not in message["text"]
        assert [len(row) for row in message["buttons"]] == [5, 3]
        assert message["image"].endswith("backdrop.jpg")
        assert message["parse_mode"] == "HTML"
    assert messages[1]["original_message_id"] == 11


def test_summary_routes_html_only_to_telegram_and_saves_plain_history(monkeypatch):
    """混合渠道分别获得 HTML 和纯文本，消息中心只记录一次。"""
    from app.sdk.services import ServiceConfigHelper

    monkeypatch.setattr(ServiceConfigHelper, "get_notification_configs", lambda: [
        SimpleNamespace(name="tg", type="telegram", enabled=True, switchs=["插件"]),
        SimpleNamespace(name="wechat", type="wechat", enabled=True, switchs=["插件"]),
        SimpleNamespace(name="off", type="telegram", enabled=False, switchs=["插件"]),
    ])
    messages = []
    plugin = SimpleNamespace(_config={}, post_message=lambda **kwargs: messages.append(kwargs))
    board = RecommendationBoard(
        profile_id="alice", username="alice", run_id="run-summary", status="success",
        recommendations=[RecommendationItem(
            candidate_id="tmdb:1", rank=1, title="A < B & C", reason="值得看 <很好>", summary="完整简介",
        )],
    )
    NotificationService(plugin).send_confirmation("alice", board)
    assert len(messages) == 3
    telegram, wechat, history = messages
    assert telegram["source"] == "tg" and telegram["parse_mode"] == "HTML"
    assert "<b>01. A &lt; B &amp; C</b>" in telegram["text"]
    assert "```" not in telegram["text"]
    assert wechat["source"] == "wechat" and wechat["parse_mode"] == "plain"
    assert "A < B & C" in wechat["text"] and "<b>" not in wechat["text"]
    assert str(getattr(history["channel"], "value", history["channel"])) == "Web"
    assert history["parse_mode"] == "plain"
    assert telegram["save_history"] is False and wechat["save_history"] is False
