from __future__ import annotations

import ast
import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


PLUGIN_DIR = Path(
    os.environ.get("DOWNLOADMANAGERLOCAL_PLUGIN_DIR")
    or Path(__file__).resolve().parents[1]
)


def _load_protocol():
    """按文件路径加载 Telegram 回调协议模块。"""
    path = PLUGIN_DIR / "service" / "speed_notification.py"
    spec = importlib.util.spec_from_file_location("downloadmanagerlocal_speed_notification", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _event(**overrides):
    """构造 MoviePilot MessageAction 事件数据。"""
    data = {
        "plugin_id": "DownloadManagerLocal",
        "channel": "telegram",
        "userid": "10001",
        "text": "dmsm:abc123:close",
        "source": "telegram-bot",
        "original_message_id": 77,
        "original_chat_id": 88,
    }
    data.update(overrides)
    return data


def _validate(protocol, event_data):
    """使用固定会话边界校验测试事件。"""
    return protocol.validate_speed_monitor_callback(
        event_data,
        plugin_id="DownloadManagerLocal",
        telegram_userid="10001",
        token="abc123",
        expires_at=200,
        now=100,
    )


def test_callback_format_is_plugin_scoped_and_within_telegram_limit():
    protocol = _load_protocol()

    callback = protocol.build_speed_monitor_callback(
        "DownloadManagerLocal", "abc123", "delete"
    )

    assert callback == "[PLUGIN]DownloadManagerLocal|dmsm:abc123:delete"
    assert len(callback.encode("utf-8")) <= 64
    with pytest.raises(ValueError, match="64 bytes"):
        protocol.build_speed_monitor_callback(
            "DownloadManagerLocal", "x" * 48, "delete"
        )


@pytest.mark.parametrize(
    ("event_data", "reason"),
    [
        (_event(plugin_id="OtherPlugin"), "foreign_plugin"),
        (_event(channel="slack"), "non_telegram"),
        (_event(text="other:abc123:close"), "foreign_callback"),
        (_event(text="dmsm:wrong:close"), "token_mismatch"),
        (_event(userid="99999"), "unauthorized_user"),
    ],
)
def test_callback_rejects_foreign_or_unauthorized_events(event_data, reason):
    protocol = _load_protocol()

    result = _validate(protocol, event_data)

    assert result.accepted is False
    assert result.reason == reason


def test_callback_rejects_expired_token_and_accepts_target_user():
    protocol = _load_protocol()

    expired = protocol.validate_speed_monitor_callback(
        _event(),
        plugin_id="DownloadManagerLocal",
        telegram_userid="10001",
        token="abc123",
        expires_at=100,
        now=100,
    )
    accepted = _validate(protocol, _event())

    assert expired == protocol.CallbackValidation(False, "expired")
    assert accepted == protocol.CallbackValidation(
        True, "accepted", "abc123", "close"
    )


def test_original_message_fields_are_preserved_for_in_place_collapse():
    protocol = _load_protocol()

    assert protocol.original_message_kwargs(_event()) == {
        "source": "telegram-bot",
        "original_message_id": 77,
        "original_chat_id": 88,
    }
    assert set(protocol.MESSAGE_ACTION_FIELDS) == {
        "plugin_id",
        "channel",
        "userid",
        "text",
        "source",
        "original_message_id",
        "original_chat_id",
    }


def test_entry_registers_message_action_and_has_no_plugin_acl():
    protocol_source = (PLUGIN_DIR / "service" / "speed_notification.py").read_text(encoding="utf-8")
    entry_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    module = ast.parse(entry_source)
    plugin_class = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "DownloadManagerLocal"
    )
    handler = next(
        node
        for node in plugin_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "on_speed_monitor_message_action"
    )

    assert "EventType.MessageAction" in ast.unparse(handler)
    assert "_handle_speed_message_action_event_impl" in ast.unparse(handler)
    assert "dmsm" in protocol_source
    assert "whitelist" not in protocol_source.lower()
    assert "allowed_users" not in protocol_source
    assert "superuser" not in protocol_source.lower()


def test_fake_message_action_routes_only_current_telegram_callback():
    protocol = _load_protocol()

    class DownloadManagerLocal:
        """提供当前插件类名与回调处理器的测试替身。"""

        def __init__(self):
            self.calls = []

        def _speed_monitor_callback_handler(self, event_data):
            """记录当前插件回调并确认已处理。"""
            self.calls.append(event_data)
            return True

    plugin = DownloadManagerLocal()

    assert protocol.handle_speed_message_action_event(
        plugin, SimpleNamespace(event_data=_event())
    ) is True
    assert plugin.calls == [_event()]
    assert protocol.handle_speed_message_action_event(
        plugin, SimpleNamespace(event_data=_event(plugin_id="OtherPlugin"))
    ) is False
    assert protocol.handle_speed_message_action_event(
        plugin, SimpleNamespace(event_data=_event(channel="email"))
    ) is False
