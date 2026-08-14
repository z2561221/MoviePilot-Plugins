from __future__ import annotations

import importlib
import os
import sys
import types
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pytest


PLUGIN_DIR = Path(
    os.environ.get("DOWNLOADMANAGERLOCAL_PLUGIN_DIR")
    or Path(__file__).resolve().parents[1]
)


class NotificationType(Enum):
    """测试覆盖的 MoviePilot 通知分类。"""

    Download = "资源下载"
    Organize = "整理入库"
    Subscribe = "订阅"
    SiteMessage = "站点"
    MediaServer = "媒体服务器"
    Manual = "手动处理"
    Plugin = "插件"
    Agent = "智能体"
    Other = "其它"


def _prepare_imports() -> None:
    """安装不执行插件入口的 downloadmanagerlocal 包壳。"""
    for name in list(sys.modules):
        if name == "downloadmanagerlocal" or name.startswith("downloadmanagerlocal."):
            sys.modules.pop(name)
    package = types.ModuleType("downloadmanagerlocal")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["downloadmanagerlocal"] = package


def _load_notification():
    """加载速度通知纯 Python 服务。"""
    _prepare_imports()
    return importlib.import_module("downloadmanagerlocal.service.speed_notification")


class FakePlugin:
    """记录通知调用并允许切换发送失败。"""

    _speed_monitor_notification_type = "Plugin"
    _speed_monitor_telegram_userid = ""

    def __init__(self, *, fail=False):
        """初始化通知记录和失败开关。"""
        self.messages = []
        self.fail = fail

    def post_message(self, **kwargs):
        """记录通知参数或模拟发送异常。"""
        if self.fail:
            raise RuntimeError("send failed")
        self.messages.append(kwargs)


def _session():
    """构造包含通知展示字段的活跃会话。"""
    return SimpleNamespace(
        status="active",
        downloader_id="qb-main",
        torrent_hash="abc123",
        name="Example Torrent",
        total_bytes=2 * 1024**3,
    )


def _decision():
    """构造包含完整异常依据的判定快照。"""
    return {
        "progress": 0.375,
        "current_speed_bps": 128 * 1024,
        "reference_speed_bps": 2 * 1024**2,
        "effective_seconds": 3661,
        "allowed_seconds": 1800,
        "is_anomalous": True,
    }


def _runtime():
    """构造一个 pending 告警运行态。"""
    return SimpleNamespace(
        sessions={"qb-main:abc123": _session()},
        alerts={
            "qb-main:abc123:1": {
                "status": "pending",
                "downloader_id": "qb-main",
                "torrent_hash": "abc123",
                "anomaly_epoch": 1,
                "decision": _decision(),
            }
        },
    )


@pytest.mark.parametrize("member", list(NotificationType))
def test_notification_type_accepts_every_enum_name_and_value(member):
    """每个 MoviePilot 合法分类的枚举名和显示值都应原样解析。"""
    notification = _load_notification()

    assert notification.resolve_notification_type(
        member.name, NotificationType
    ) is member
    assert notification.resolve_notification_type(
        member.value, NotificationType
    ) is member


def test_invalid_notification_type_falls_back_to_plugin():
    """非法或空通知分类必须回退 Plugin。"""
    notification = _load_notification()

    assert notification.resolve_notification_type(
        "invalid", NotificationType
    ) is NotificationType.Plugin
    assert notification.resolve_notification_type(
        "", NotificationType
    ) is NotificationType.Plugin


def test_telegram_target_uses_moviepilot_user_settings():
    """Telegram 交互目标必须读取 MP 用户设置中的 telegram_userid。"""
    _prepare_imports()
    target = importlib.import_module(
        "downloadmanagerlocal.adapter.telegram_target"
    )

    class FakeUserOper:
        """返回固定管理员通知设置。"""

        def get_settings(self, username):
            """按用户名返回测试通知目标。"""
            assert username == "admin"
            return {"telegram_userid": 10001}

    assert target.resolve_admin_telegram_userid(
        FakeUserOper, "admin"
    ) == "10001"


def test_notification_body_contains_decision_fields_and_delete_risk():
    """通知正文必须展示判断依据和删除全量数据风险。"""
    notification = _load_notification()

    text = notification.format_speed_alert_text(_session(), _decision())

    for expected in (
        "下载器：qb-main",
        "任务：Example Torrent",
        "Hash：abc123",
        "体积：2.0 GiB",
        "进度：37.5%",
        "当前速度：128.0 KiB/s",
        "参考速度：2.0 MiB/s",
        "有效时长：1小时1分1秒",
        "允许时限：30分0秒",
        "删除会同时清理该种子的全部数据且不可恢复",
    ):
        assert expected in text


def test_without_telegram_target_sends_plain_mp_notification_once():
    """未配置 Telegram 时仍应发送普通 MP 通知且不挂不可授权按钮。"""
    notification = _load_notification()
    plugin = FakePlugin()
    plugin._speed_monitor_notification_type = "Manual"
    runtime = _runtime()

    assert notification.dispatch_pending_speed_alerts(
        plugin, runtime, 100, notification_type=NotificationType
    ) == 1
    assert len(plugin.messages) == 1
    message = plugin.messages[0]
    assert message["mtype"] is NotificationType.Manual
    assert "buttons" not in message
    assert "targets" not in message
    assert runtime.alerts["qb-main:abc123:1"]["status"] == "notified"
    assert notification.dispatch_pending_speed_alerts(
        plugin, runtime, 110, notification_type=NotificationType
    ) == 0
    assert len(plugin.messages) == 1


def test_telegram_target_gets_short_close_and_delete_callbacks():
    """已配置 Telegram 目标时应生成两个不超过 64 字节的短回调。"""
    notification = _load_notification()
    plugin = FakePlugin()
    plugin._speed_monitor_telegram_userid = "10001"
    runtime = _runtime()

    sent = notification.dispatch_pending_speed_alerts(
        plugin,
        runtime,
        100,
        token_factory=lambda: "abc123",
        notification_type=NotificationType,
    )
    alert = runtime.alerts["qb-main:abc123:1"]
    message = plugin.messages[0]
    callbacks = [button["callback_data"] for button in message["buttons"][0]]

    assert sent == 1
    assert message["targets"] == {"telegram_userid": "10001"}
    assert callbacks == [
        "[PLUGIN]FakePlugin|dmsm:abc123:close",
        "[PLUGIN]FakePlugin|dmsm:abc123:delete",
    ]
    assert all(len(value.encode("utf-8")) <= 64 for value in callbacks)
    assert alert["token"] == "abc123"
    assert alert["telegram_userid"] == "10001"
    assert alert["expires_at"] == 100 + 24 * 60 * 60
    assert alert["status"] == "notified"


def test_send_failure_keeps_pending_alert_for_retry():
    """通知发送异常时告警保持 pending 并记录失败原因。"""
    notification = _load_notification()
    plugin = FakePlugin(fail=True)
    runtime = _runtime()

    assert notification.dispatch_pending_speed_alerts(
        plugin, runtime, 100, notification_type=NotificationType
    ) == 0
    alert = runtime.alerts["qb-main:abc123:1"]
    assert alert["status"] == "pending"
    assert alert["notification_error"] == "send failed"
