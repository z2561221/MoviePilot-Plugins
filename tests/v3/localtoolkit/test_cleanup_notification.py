from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.schemas.message import MessageResponse
from app.schemas.types import MessageType, NotificationChannel
from localtoolkit.adapter.cleanup_notification import (
    CleanupReportNotifier,
    ServiceConfigHelper,
)


def config(name="TG", kind="telegram", *, enabled=True, switchs=None):
    return SimpleNamespace(name=name, type=kind, enabled=enabled,
                           switchs=[MessageType.Plugin.value] if switchs is None else switchs)


def build_notifier(monkeypatch, configs=None, *, action="all", targets=None):
    monkeypatch.setattr(ServiceConfigHelper, "get_notification_switch", lambda _kind: action)
    plugin = SimpleNamespace(post_message=Mock())
    plugin.chain = SimpleNamespace(
        send_direct_message=Mock(side_effect=lambda message: MessageResponse(
            success=True, message_id=f"message-{message.source}", chat_id="chat-42",
            source=message.source, channel=NotificationChannel.Telegram,
        )),
        run_module=Mock(return_value=True),
        data_ports=SimpleNamespace(user=lambda: SimpleNamespace(get_settings=Mock(return_value=targets))),
        runtime_config=SimpleNamespace(superuser="admin"),
    )
    routes = configs if configs is not None else [config()]
    helper = SimpleNamespace(get_configs=lambda: {conf.name: conf for conf in routes})
    return CleanupReportNotifier(plugin, helper), plugin


def test_same_receipt_is_used_for_html_progress_and_final_edit(monkeypatch):
    notifier, plugin = build_notifier(monkeypatch)
    notifier.start("报告", "<b>正在清理</b>")
    notifier.update("报告", "<b>正在复核</b>")
    assert notifier.finish("报告", "<b>删除完毕</b>")
    plugin.chain.send_direct_message.assert_called_once()
    sent = plugin.chain.send_direct_message.call_args.args[0]
    assert sent.parse_mode == "HTML" and sent.channel == NotificationChannel.Telegram
    assert plugin.chain.run_module.call_count == 2
    for call in plugin.chain.run_module.call_args_list:
        assert call.args == ("edit_message",)
        assert call.kwargs["message_id"] == "message-TG" and call.kwargs["chat_id"] == "chat-42"
        assert call.kwargs["source"] == "TG" and call.kwargs["parse_mode"] == "HTML"
    assert plugin.chain.run_module.call_args.kwargs["text"] == "<b>删除完毕</b>"
    plugin.post_message.assert_called_once()
    assert plugin.post_message.call_args.kwargs["channel"] == NotificationChannel.Web


def test_multiple_telegram_sources_keep_separate_receipts_and_other_channels_get_plain_text(monkeypatch):
    notifier, plugin = build_notifier(monkeypatch, [
        config("one"), config("two"), config("飞书", "feishu"),
        config("disabled", enabled=False), config("muted", switchs=[]),
    ])
    notifier.start("报告", "<b>影片 &amp; 配乐</b>")
    assert notifier.finish("报告", "<b>影片 &amp; 配乐</b>")
    assert plugin.chain.send_direct_message.call_count == 2
    assert {call.kwargs["source"] for call in plugin.chain.run_module.call_args_list} == {"one", "two"}
    other_calls = [call.kwargs for call in plugin.post_message.call_args_list if call.kwargs.get("source")]
    assert len(other_calls) == 1
    assert other_calls[0]["source"] == "飞书" and other_calls[0]["text"] == "影片 & 配乐"
    assert other_calls[0]["save_history"] is False


def test_edit_failure_retries_original_message_without_posting_another_telegram_report(monkeypatch):
    monkeypatch.setattr("localtoolkit.adapter.cleanup_notification.time.sleep", lambda _seconds: None)
    notifier, plugin = build_notifier(monkeypatch)
    notifier.start("报告", "开始")
    plugin.chain.run_module.return_value = False
    assert notifier.finish("报告", "结束") is False
    assert plugin.chain.run_module.call_count == 2
    plugin.chain.send_direct_message.assert_called_once()
    assert all(call.kwargs.get("source") != "TG" for call in plugin.post_message.call_args_list)
    assert notifier.to_dict()["updated"] is False


@pytest.mark.parametrize("response", [None, {"success": True, "message_id": 1},
    {"success": True, "message_id": 1, "chat_id": 2, "source": "foreign"}])
def test_missing_or_foreign_receipt_never_edits_arbitrary_message_or_resends(monkeypatch, response):
    notifier, plugin = build_notifier(monkeypatch)
    plugin.chain.send_direct_message.side_effect = None
    plugin.chain.send_direct_message.return_value = response
    notifier.start("报告", "开始")
    assert notifier.finish("报告", "结束") is False
    plugin.chain.run_module.assert_not_called()
    plugin.chain.send_direct_message.assert_called_once()
    assert all(call.kwargs.get("source") != "TG" for call in plugin.post_message.call_args_list)


def test_admin_routing_is_preserved_without_bypassing_notification_type_switch(monkeypatch):
    notifier, plugin = build_notifier(monkeypatch, action="admin", targets={"telegram_userid": "admin-chat"})
    notifier.start("报告", "开始")
    sent = plugin.chain.send_direct_message.call_args.args[0]
    assert sent.targets == {"telegram_userid": "admin-chat"}
    assert sent.userid is None and sent.mtype == MessageType.Plugin


def test_admin_without_telegram_target_does_not_fall_back_to_default_chat(monkeypatch):
    notifier, plugin = build_notifier(monkeypatch, action="admin", targets={"wechat_userid": "admin"})
    notifier.start("报告", "开始")
    assert notifier.finish("报告", "结束")
    plugin.chain.send_direct_message.assert_not_called()
    assert all(call.kwargs.get("source") != "TG" for call in plugin.post_message.call_args_list)


def test_host_without_receipt_capability_sends_only_one_final_report(monkeypatch):
    notifier, plugin = build_notifier(monkeypatch)
    plugin.chain.send_direct_message = None
    notifier.start("报告", "开始")
    assert notifier.finish("报告", "结束")
    telegram_calls = [call for call in plugin.post_message.call_args_list if call.kwargs.get("source") == "TG"]
    assert len(telegram_calls) == 1
    assert telegram_calls[0].kwargs["text"] == "结束" and telegram_calls[0].kwargs["parse_mode"] == "HTML"


def test_transient_progress_edit_failure_can_recover_on_final_update(monkeypatch):
    notifier, plugin = build_notifier(monkeypatch)
    notifier.start("报告", "开始")
    plugin.chain.run_module.return_value = False
    notifier.update("报告", "复核")
    plugin.chain.run_module.return_value = True
    assert notifier.finish("报告", "结束")
    assert notifier.to_dict()["updated"]


def test_real_host_telegram_module_preserves_html_and_original_message_identity(monkeypatch):
    from app.modules.telegram.module import TelegramModule

    notifier, plugin = build_notifier(monkeypatch)
    client = SimpleNamespace(
        send_msg=Mock(return_value={"success": True, "message_id": 712, "chat_id": "chat-9"}),
        edit_msg=Mock(return_value=True),
    )
    module = object.__new__(TelegramModule)
    module._channel = NotificationChannel.Telegram
    route = config()
    monkeypatch.setattr(module, "get_configs", lambda: {"TG": route})
    monkeypatch.setattr(module, "get_config", lambda _name: route)
    monkeypatch.setattr(module, "get_instance", lambda _name: client)
    plugin.chain.send_direct_message = module.send_direct_message
    plugin.chain.run_module = lambda name, **kwargs: getattr(module, name)(**kwargs)

    notifier.start("清理库存检查报告", "<b>正在清理</b>")
    notifier.update("清理库存检查报告", "<b>正在复核</b>")
    assert notifier.finish("清理库存检查报告", "<b>确认移除：2 部</b>\n✅ 本轮删除完毕")
    client.send_msg.assert_called_once()
    assert client.send_msg.call_args.kwargs["parse_mode"] == "HTML"
    assert client.edit_msg.call_count == 2
    for call in client.edit_msg.call_args_list:
        assert call.kwargs["message_id"] == 712 and call.kwargs["chat_id"] == "chat-9"
        assert call.kwargs["parse_mode"] == "HTML"
    assert client.edit_msg.call_args.kwargs["text"].endswith("✅ 本轮删除完毕")
