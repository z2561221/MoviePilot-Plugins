"""AgentRank Telegram 旧宿主消息终态兼容测试。"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "adapter" / "telegram_compat.py"
SPEC = importlib.util.spec_from_file_location("agentrank_telegram_compat_test", MODULE_PATH)
telegram_compat = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(telegram_compat)


class MissingMessageBot:
    """模拟 Telegram 对已不存在消息返回精确 400。"""

    def delete_message(self, **kwargs):
        """模拟删除目标消息不存在。"""
        raise RuntimeError("Bad Request: message to delete not found")

    def edit_message_text(self, **kwargs):
        """模拟编辑文本消息不存在。"""
        raise RuntimeError("Bad Request: message to edit not found")

    def edit_message_caption(self, **kwargs):
        """模拟编辑说明消息不存在。"""
        raise RuntimeError("Bad Request: message to edit not found")

    def edit_message_media(self, **kwargs):
        """模拟编辑媒体消息不存在。"""
        raise RuntimeError("Bad Request: message to edit not found")


class FailingBot(MissingMessageBot):
    """模拟不应被兼容层吞掉的 Telegram 异常。"""

    def delete_message(self, **kwargs):
        """模拟普通权限错误。"""
        raise RuntimeError("Bad Request: message can't be deleted")

    def edit_message_text(self, **kwargs):
        """模拟普通编辑权限错误。"""
        raise RuntimeError("Forbidden: bot was blocked by the user")


def _module_manager_factory(bot):
    """构造只暴露一个 Telegram 客户端的模块管理器工厂。"""
    telegram_module = SimpleNamespace(
        get_instances=lambda: {"Telegram": SimpleNamespace(_bot=bot)}
    )
    manager = SimpleNamespace(
        get_running_module=lambda module_id: (
            telegram_module if module_id == "TelegramModule" else None
        )
    )
    return lambda: manager


def test_guard_treats_exact_delete_and_edit_not_found_as_success():
    """精确的删除和编辑消息不存在错误均视为终态成功。"""
    bot = MissingMessageBot()

    with telegram_compat.telegram_message_not_found_guard(
        _module_manager_factory(bot)
    ):
        assert bot.delete_message(message_id=1) is True
        assert bot.edit_message_text(message_id=1) is True
        assert bot.edit_message_caption(message_id=1) is True
        assert bot.edit_message_media(message_id=1) is True


def test_guard_preserves_other_telegram_errors():
    """非目标 Telegram 异常必须继续抛出，避免隐藏真实故障。"""
    bot = FailingBot()

    with telegram_compat.telegram_message_not_found_guard(
        _module_manager_factory(bot)
    ):
        with pytest.raises(RuntimeError, match="can't be deleted"):
            bot.delete_message(message_id=1)
        with pytest.raises(RuntimeError, match="blocked by the user"):
            bot.edit_message_text(message_id=1)


def test_guard_restores_original_bot_methods_after_call_window():
    """兼容调用窗口结束后恢复 bot 原方法，不留下常驻补丁。"""
    bot = MissingMessageBot()
    original_delete = bot.delete_message

    with telegram_compat.telegram_message_not_found_guard(
        _module_manager_factory(bot)
    ):
        assert bot.delete_message(message_id=1) is True

    assert "delete_message" not in vars(bot)
    assert bot.delete_message.__func__ is original_delete.__func__
    with pytest.raises(RuntimeError, match="message to delete not found"):
        bot.delete_message(message_id=1)


def test_guard_is_noop_when_telegram_module_is_unavailable():
    """Telegram 模块不可用时兼容层应安全退化为无操作上下文。"""
    manager = SimpleNamespace(get_running_module=lambda module_id: None)

    with telegram_compat.telegram_message_not_found_guard(lambda: manager):
        assert True
