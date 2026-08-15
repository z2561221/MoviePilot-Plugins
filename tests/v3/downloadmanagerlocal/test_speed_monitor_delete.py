from __future__ import annotations

import importlib
import os
import sys
import threading
import types
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pytest


PLUGIN_DIR = Path(
    os.environ.get("DOWNLOADMANAGERLOCAL_PLUGIN_DIR")
    or Path(__file__).resolve().parents[1]
)


class NotificationType(Enum):
    """动作卡片测试使用的最小通知分类。"""

    Plugin = "插件"


def _prepare_imports() -> None:
    """安装不执行插件入口的 downloadmanagerlocal 包壳。"""
    for name in list(sys.modules):
        if name == "downloadmanagerlocal" or name.startswith("downloadmanagerlocal."):
            sys.modules.pop(name)
    package = types.ModuleType("downloadmanagerlocal")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["downloadmanagerlocal"] = package


def _load(module_name: str):
    """加载指定下载中心纯 Python 模块。"""
    _prepare_imports()
    return importlib.import_module(f"downloadmanagerlocal.{module_name}")


class FakeDownloader:
    """记录全量删除参数并可模拟失败或并发阻塞。"""

    def __init__(self, *, error=None, started=None, release=None):
        """保存删除行为控制参数。"""
        self.error = error
        self.started = started
        self.release = release
        self.delete_calls = []

    def delete_torrents(self, ids, delete_file):
        """记录删除调用并按测试设置返回或抛错。"""
        self.delete_calls.append((list(ids), delete_file))
        if self.started:
            self.started.set()
        if self.release:
            assert self.release.wait(timeout=2)
        if self.error:
            raise self.error
        return True


class FakePlugin:
    """提供回调动作所需的运行态、下载器和消息接口。"""

    _speed_monitor_notification_type = "Plugin"

    def __init__(self, runtime, downloader, downloader_type="qbittorrent"):
        """绑定速度监控运行态和 fake 下载器。"""
        self._speed_monitor_runtime = runtime
        self.downloader = downloader
        self.downloader_type = downloader_type
        self.data = {}
        self.messages = []

    def service_info(self, name):
        """返回 fake qB/TR 服务。"""
        return SimpleNamespace(
            type=self.downloader_type,
            instance=self.downloader,
        )

    def get_data(self, key):
        """读取内存插件数据。"""
        return self.data.get(key)

    def save_data(self, key, value):
        """保存内存插件数据。"""
        self.data[key] = value

    def post_message(self, **kwargs):
        """记录原消息编辑参数。"""
        self.messages.append(kwargs)


def _runtime(status="notified", downloader_type="qbittorrent"):
    """构造一个已通知且可操作的异常会话。"""
    monitor = _load("service.speed_monitor")
    session = monitor.SpeedMonitorSession(
        downloader_id="qb-main",
        downloader_type=downloader_type,
        torrent_hash="abc123",
        name="Example",
        total_bytes=1000,
        start_downloaded_bytes=100,
        start_remaining_bytes=900,
        last_downloaded_bytes=200,
        first_observed_at=1,
        last_observed_at=10,
        last_effective_at=10,
        last_valid_sample_at=10,
        last_success_poll_at=10,
        effective_seconds=9,
        last_state="active",
        anomaly_epoch=1,
        anomaly_active=True,
        had_anomaly=True,
    )
    alert = {
        "status": status,
        "downloader_id": "qb-main",
        "torrent_hash": "abc123",
        "anomaly_epoch": 1,
        "token": "abc123",
        "telegram_userid": "10001",
        "expires_at": 200,
        "created_at": 10,
        "updated_at": 10,
        "handled_at": 0,
        "decision": {"is_anomalous": True},
    }
    return monitor.SpeedMonitorRuntime(
        sessions={"qb-main:abc123": session},
        alerts={"qb-main:abc123:1": alert},
    )


def _event(action, **overrides):
    """构造当前插件的 Telegram MessageAction 数据。"""
    data = {
        "plugin_id": "FakePlugin",
        "channel": "telegram",
        "userid": "10001",
        "text": f"dmsm:abc123:{action}",
        "source": "telegram-bot",
        "original_message_id": 77,
        "original_chat_id": 88,
    }
    data.update(overrides)
    return data


def _process(actions, plugin, action, now=100, **overrides):
    """以固定通知分类处理一次回调。"""
    return actions.process_speed_message_action(
        plugin,
        _event(action, **overrides),
        now=now,
        notification_type=NotificationType,
    )


@pytest.mark.parametrize("downloader_type", ["qbittorrent", "transmission"])
def test_close_and_cancel_never_call_downloader_delete(downloader_type):
    """关闭与取消删除只收束卡片，不能改变下载器任务。"""
    actions = _load("service.speed_actions")

    close_runtime = _runtime(downloader_type=downloader_type)
    close_downloader = FakeDownloader()
    close_plugin = FakePlugin(close_runtime, close_downloader, downloader_type)
    assert _process(actions, close_plugin, "close") is True
    close_session = close_runtime.sessions["qb-main:abc123"]
    assert close_downloader.delete_calls == []
    assert close_session.status == "active"
    assert close_session.anomaly_active is True
    assert close_runtime.alerts["qb-main:abc123:1"]["status"] == "closed"
    assert close_plugin.messages[-1]["buttons"] is None

    cancel_runtime = _runtime(downloader_type=downloader_type)
    cancel_downloader = FakeDownloader()
    cancel_plugin = FakePlugin(cancel_runtime, cancel_downloader, downloader_type)
    _process(actions, cancel_plugin, "delete")
    assert cancel_runtime.alerts["qb-main:abc123:1"]["status"] == "confirming"
    assert cancel_downloader.delete_calls == []
    confirm_callbacks = [
        button["callback_data"]
        for button in cancel_plugin.messages[-1]["buttons"][0]
    ]
    assert all(
        len(callback.encode("utf-8")) <= 64
        for callback in confirm_callbacks
    )
    _process(actions, cancel_plugin, "cancel")
    assert cancel_downloader.delete_calls == []
    assert cancel_runtime.sessions["qb-main:abc123"].status == "active"
    assert cancel_runtime.alerts["qb-main:abc123:1"]["status"] == "notified"


@pytest.mark.parametrize("downloader_type", ["qbittorrent", "transmission"])
def test_confirm_delete_calls_qb_and_tr_with_delete_file_true(downloader_type):
    """qB/TR 确认删除都必须固定传 delete_file=True 并进入删除终态。"""
    actions = _load("service.speed_actions")
    runtime = _runtime()
    downloader = FakeDownloader()
    plugin = FakePlugin(runtime, downloader, downloader_type)

    _process(actions, plugin, "delete")
    assert downloader.delete_calls == []
    _process(actions, plugin, "confirm")
    session = runtime.sessions["qb-main:abc123"]
    alert = runtime.alerts["qb-main:abc123:1"]

    assert downloader.delete_calls == [(["abc123"], True)]
    assert session.status == "deleted"
    assert session.sample_eligible is False
    assert alert["status"] == "deleted"
    assert alert["deletion_result"] == {
        "success": True,
        "delete_file": True,
        "completed_at": 100,
    }
    assert plugin.data["speed_monitor_sessions"]["items"]["qb-main:abc123"]["status"] == "deleted"


def test_unauthorized_expired_terminal_and_repeated_callbacks_are_idempotent():
    """越权、过期、终态和重复点击均不得调用删除器。"""
    actions = _load("service.speed_actions")
    runtime = _runtime()
    downloader = FakeDownloader()
    plugin = FakePlugin(runtime, downloader)

    _process(actions, plugin, "delete", userid="99999")
    _process(actions, plugin, "delete", now=200)
    assert runtime.alerts["qb-main:abc123:1"]["status"] == "notified"
    assert downloader.delete_calls == []

    runtime.sessions["qb-main:abc123"].status = "completed"
    _process(actions, plugin, "delete")
    _process(actions, plugin, "confirm")
    assert downloader.delete_calls == []

    deleted_runtime = _runtime("confirming")
    deleted_downloader = FakeDownloader()
    deleted_plugin = FakePlugin(deleted_runtime, deleted_downloader)
    _process(actions, deleted_plugin, "confirm")
    _process(actions, deleted_plugin, "confirm")
    assert deleted_downloader.delete_calls == [(["abc123"], True)]


def test_delete_failure_is_persisted_and_can_be_cancelled_without_second_call():
    """删除失败应保持确认态并持久化失败，取消后不自动重试。"""
    actions = _load("service.speed_actions")
    runtime = _runtime("confirming")
    downloader = FakeDownloader(error=RuntimeError("offline"))
    plugin = FakePlugin(runtime, downloader)

    _process(actions, plugin, "confirm")
    alert = runtime.alerts["qb-main:abc123:1"]
    assert alert["status"] == "confirming"
    assert alert["deletion_result"]["success"] is False
    assert alert["deletion_result"]["error"] == "offline"
    assert plugin.data["speed_monitor_alerts"]["items"]["qb-main:abc123:1"]["deletion_result"]["error"] == "offline"

    _process(actions, plugin, "cancel")
    assert downloader.delete_calls == [(["abc123"], True)]
    assert runtime.alerts["qb-main:abc123:1"]["status"] == "notified"


def test_completion_and_delete_share_session_lock_and_only_one_terminal_wins():
    """删除进行中遇到完成扫描时只能有一个终态动作获胜。"""
    actions = _load("service.speed_actions")
    monitor = importlib.import_module("downloadmanagerlocal.service.speed_monitor")
    runtime = _runtime("confirming")
    delete_started = threading.Event()
    allow_delete = threading.Event()
    downloader = FakeDownloader(started=delete_started, release=allow_delete)
    plugin = FakePlugin(runtime, downloader)

    with ThreadPoolExecutor(max_workers=2) as executor:
        delete_future = executor.submit(
            _process, actions, plugin, "confirm", 100
        )
        assert delete_started.wait(timeout=2)
        completion_future = executor.submit(
            monitor._finish_session,
            runtime,
            "qb-main:abc123",
            "completed",
            101,
        )
        allow_delete.set()
        assert delete_future.result(timeout=2) is True
        assert completion_future.result(timeout=2) is False

    assert downloader.delete_calls == [(["abc123"], True)]
    assert runtime.sessions["qb-main:abc123"].status == "deleted"
    assert len(runtime.alerts) == 1
