"""持续异常的通知去重、发送失败重试与恢复边界。"""

from datetime import datetime, timedelta, timezone

from app.plugins.localtoolkit.service.cleanup_alerts import (
    ALERT_DATA_KEY,
    CleanupAlerts,
)

from .test_cleanup_run import FakePlugin


def test_error_repeats_after_24_hours_and_recovery_notifies_once():
    """未变化的异常不刷屏，恢复提醒不重复。"""
    plugin = FakePlugin()
    calls = []
    alerts = CleanupAlerts(plugin, {}, lambda *args: calls.append(args) or True)
    now = datetime.now(timezone.utc)
    alerts.fail("scan", "timeout", "扫描失败", now)
    alerts.fail("scan", "timeout", "扫描失败", now + timedelta(hours=1))
    assert len(calls) == 1
    alerts.fail("scan", "timeout", "扫描失败", now + timedelta(hours=24))
    assert len(calls) == 2
    alerts.recover("scan")
    alerts.recover("scan")
    assert len(calls) == 3 and calls[-1][1] == "清理计划扫描恢复"
    assert plugin.data[ALERT_DATA_KEY] == {}


def test_send_failure_does_not_start_notification_cooldown():
    """通知失败不会伪装成已送达并压制后续提醒。"""
    plugin = FakePlugin()
    calls = []
    alerts = CleanupAlerts(plugin, {}, lambda *args: calls.append(args) or False)
    now = datetime.now(timezone.utc)
    alerts.fail("scan", "timeout", "扫描失败", now)
    alerts.fail("scan", "timeout", "扫描失败", now + timedelta(minutes=1))
    assert len(calls) == 2
    state = plugin.data[ALERT_DATA_KEY]["scan"]
    assert state["last_notified_at"] == "" and state["notified"] is False
    alerts.recover("scan")
    assert len(calls) == 2


def test_failure_state_survives_reload_and_recovery_is_per_operation():
    """清理恢复不能清除扫描异常，重新加载不重置通知冷却。"""
    plugin = FakePlugin()
    calls = []
    send = lambda *args: calls.append(args) or True
    now = datetime.now(timezone.utc)
    CleanupAlerts(plugin, {}, send).fail("scan", "timeout", "扫描失败", now)
    reloaded = CleanupAlerts(plugin, {}, send)
    reloaded.fail("scan", "timeout", "扫描失败", now + timedelta(minutes=1))
    reloaded.recover("cleanup")
    assert len(calls) == 1 and reloaded.errors() == {"scan": "扫描失败"}


def test_muted_operations_do_not_emit_failure_or_recovery_notifications():
    """关闭通知仍记录异常，但异常和恢复都不对外发送。"""
    plugin = FakePlugin()
    calls = []
    alerts = CleanupAlerts(plugin, {"scan_notify": False}, lambda *args: calls.append(args) or True)
    alerts.fail("scan", "timeout", "扫描失败", datetime.now(timezone.utc))
    assert alerts.errors() == {"scan": "扫描失败"}
    alerts.recover("scan")
    assert not calls
