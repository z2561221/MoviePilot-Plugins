"""使用宿主真实 Telegram 模块和客户端验证原消息编辑，不连接网络。"""

from types import SimpleNamespace

import pytest
from app.modules.telegram.module import TelegramModule
from app.modules.telegram.telegram import Telegram
from app.schemas.types import NotificationChannel

from tests.v3.agentrank import test_telegram_retry as retry_cases

setup_retry = retry_cases.setup_retry


class RecordingBot:
    """替换 Telegram 网络边界，同时记录发送与编辑这两种实际操作。"""

    def __init__(self, original_kind):
        """指定原消息类型，或模拟服务器已删除该消息。"""
        self.original_kind = original_kind
        self.sent = []
        self.text_edits = []
        self.caption_edits = []

    def send_message(self, **kwargs):
        """记录新消息创建。"""
        self.sent.append(kwargs)

    def edit_message_text(self, **kwargs):
        """记录真正的文本编辑，并模拟 Telegram 对原消息的响应。"""
        self.text_edits.append(kwargs)
        if self.original_kind == "missing":
            raise RuntimeError("Bad Request: message to edit not found")
        if self.original_kind == "caption":
            raise RuntimeError("Bad Request: there is no text in the message to edit")

    def edit_message_caption(self, **kwargs):
        """原消息为媒体时仅编辑说明文字。"""
        self.caption_edits.append(kwargs)


@pytest.mark.parametrize("original_kind", ["text", "caption", "missing"])
def test_real_host_edit_path_never_creates_followup_message(setup_retry, original_kind):
    """经过真实宿主分发与客户端，即使按钮清空或编辑失败也只发送一次。"""
    plugin, _, service, calls = setup_retry
    bot = RecordingBot(original_kind)
    client = Telegram.__new__(Telegram)
    client._bot = bot
    module = SimpleNamespace(
        _channel=NotificationChannel.Telegram,
        get_configs=lambda: {"Telegram": SimpleNamespace(name="Telegram")},
        get_instance=lambda source: client,
    )

    def dispatch(method, **kwargs):
        """使用真实宿主编辑实现，而非仅记录编辑参数的替身。"""
        assert method == "edit_message"
        return TelegramModule.edit_message(module, **kwargs)

    original_post = plugin.post_message

    def post(**kwargs):
        """将普通通知作为一次网络发送记录，以识别回退或重复发送。"""
        original_post(**kwargs)
        bot.send_message(
            chat_id="1001", text=kwargs.get("text"), buttons=kwargs.get("buttons")
        )

    plugin.chain = SimpleNamespace(run_module=dispatch)
    plugin.post_message = post
    event = retry_cases._notice(service)
    service.handle_callback(event)
    key = service.active_key(retry_cases.PROFILE)
    assert calls == [retry_cases.PROFILE]
    assert bot.text_edits[0]["reply_markup"] is None
    assert bot.text_edits[0]["message_id"] == 42
    service.update_progress(
        retry_cases.PROFILE,
        key,
        {
            "active": True,
            "run_id": "retry-run",
            "message": "正在分析 <候选>&结果",
        },
    )
    updated = service.finish(
        retry_cases.PROFILE,
        key,
        SimpleNamespace(
            status="ranking_agent_failed",
            run_id="retry-run",
            message="排序校验失败",
            board=None,
        ),
    )
    assert updated is (original_kind != "missing")
    assert len(bot.sent) == len(plugin.messages) == 1
    assert {edit["message_id"] for edit in bot.text_edits} == {42}
    assert {edit["chat_id"] for edit in bot.text_edits} == {"1001"}
    assert {edit["parse_mode"] for edit in bot.text_edits} == {"HTML"}
    assert "&lt;候选&gt;&amp;结果" in bot.text_edits[1]["text"]
    if original_kind == "caption":
        assert len(bot.caption_edits) == len(bot.text_edits)
    if original_kind != "missing":
        edits = bot.caption_edits or bot.text_edits
        assert edits[-1]["reply_markup"] is not None
