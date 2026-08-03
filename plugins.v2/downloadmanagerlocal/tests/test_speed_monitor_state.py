from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace


PLUGIN_DIR = Path(
    os.environ.get("DOWNLOADMANAGERLOCAL_PLUGIN_DIR")
    or Path(__file__).resolve().parents[1]
)


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


class MutableDownloader:
    """提供可切换成功、空列表和错误响应的下载器替身。"""

    def __init__(self, response):
        """保存初始响应。"""
        self.response = response

    def get_torrents(self):
        """返回当前响应。"""
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakePlugin:
    """提供速度监控持久化所需的最小插件接口。"""

    _enabled = True
    _transfer_enabled = False
    _fromdownloader = ""
    _todownloader = ""
    _fromtorrentpath = ""
    _iyuu_enabled = False
    _iyuu_token = ""
    _iyuu_downloaders = []
    _speed_monitor_enabled = True
    _speed_monitor_downloaders = ["qb-main"]

    def __init__(self, downloader=None, data=None):
        """保存 fake 下载器和插件数据副本。"""
        self.downloader = downloader
        self.data = dict(data or {})
        self.saved = []
        self._speed_monitor_runtime = None
        self._speed_monitor_state_error = ""

    def service_info(self, name):
        """按固定名称返回 fake qBittorrent 服务。"""
        if name != "qb-main" or self.downloader is None:
            return None
        return SimpleNamespace(type="qbittorrent", instance=self.downloader)

    def get_data(self, key):
        """读取插件数据。"""
        return self.data.get(key)

    def save_data(self, key, value):
        """保存插件数据并记录写入。"""
        self.data[key] = value
        self.saved.append((key, value))


def _qb_item(downloaded=100, state="downloading"):
    """构造 qBittorrent 任务字典。"""
    return {
        "hash": "ABC",
        "name": "Example",
        "total_size": 1000,
        "downloaded": downloaded,
        "added_on": 1,
        "state": state,
        "dlspeed": 10,
    }


def test_session_persists_and_reload_restores_first_observation_fields():
    """重载应恢复首见字节、剩余预算和有效时长而不创建重复会话。"""
    monitor = _load("service.speed_monitor")
    downloader = MutableDownloader(([_qb_item(100)], None))
    plugin = FakePlugin(downloader)

    monitor.scan_speed_monitor(plugin, now=10)
    downloader.response = ([_qb_item(200)], None)
    monitor.scan_speed_monitor(plugin, now=20)
    saved_data = dict(plugin.data)

    reloaded = FakePlugin(downloader, saved_data)
    runtime = monitor.ensure_speed_monitor_runtime(reloaded)
    session = runtime.sessions["qb-main:abc"]
    result = monitor.scan_speed_monitor(reloaded, now=30)

    assert session.first_observed_at == 10
    assert session.start_downloaded_bytes == 100
    assert session.start_remaining_bytes == 900
    assert session.effective_seconds == 20
    assert result["created_sessions"] == 0
    assert set(runtime.sessions) == {"qb-main:abc"}
    assert reloaded.data["speed_monitor_sessions"]["schema_version"] == 1


def test_success_empty_terminates_once_but_api_error_preserves_session_and_clock():
    """成功空列表只终止一次，API 错误期间会话与有效时钟保持冻结。"""
    monitor = _load("service.speed_monitor")
    downloader = MutableDownloader(([_qb_item(100)], None))
    plugin = FakePlugin(downloader)

    monitor.scan_speed_monitor(plugin, now=10)
    downloader.response = TimeoutError("offline")
    error_result = monitor.scan_speed_monitor(plugin, now=20)
    session = plugin._speed_monitor_runtime.sessions["qb-main:abc"]
    assert session.status == "active"
    assert session.effective_seconds == 0
    assert session.last_success_poll_at == 10
    assert "offline" in error_result["errors"]["qb-main"]

    downloader.response = ([_qb_item(200)], None)
    monitor.scan_speed_monitor(plugin, now=30)
    assert session.effective_seconds == 0
    monitor.scan_speed_monitor(plugin, now=40)
    assert session.effective_seconds == 10

    downloader.response = ([], None)
    monitor.scan_speed_monitor(plugin, now=50)
    terminal_at = session.terminal_at
    monitor.scan_speed_monitor(plugin, now=60)
    assert session.status == "missing"
    assert terminal_at == 50
    assert session.terminal_at == terminal_at
    assert session.last_success_poll_at == 50


def test_completed_task_terminates_without_creating_duplicate_or_alert():
    """完成任务应只进入一次终态且不产生告警或新会话。"""
    monitor = _load("service.speed_monitor")
    downloader = MutableDownloader(([_qb_item(100)], None))
    plugin = FakePlugin(downloader)

    monitor.scan_speed_monitor(plugin, now=10)
    downloader.response = ([_qb_item(1000, "uploading")], None)
    monitor.scan_speed_monitor(plugin, now=20)
    session = plugin._speed_monitor_runtime.sessions["qb-main:abc"]
    monitor.scan_speed_monitor(plugin, now=30)

    assert session.status == "completed"
    assert session.terminal_at == 20
    assert plugin._speed_monitor_runtime.alerts == {}
    assert set(plugin._speed_monitor_runtime.sessions) == {"qb-main:abc"}


def test_missing_and_version_zero_states_migrate_to_current_schema():
    """缺失版本和 version 0 状态应显式迁移并回写当前 schema。"""
    state = _load("model.state")
    plugin = FakePlugin(data={
        "speed_monitor_sessions": {"legacy": {"status": "active"}},
        "speed_monitor_alerts": {
            "schema_version": 0,
            "items": {"alert": {"status": "pending"}},
        },
    })

    sessions = state.load_speed_monitor_items(
        plugin, state.SPEED_MONITOR_SESSIONS_KEY, "sessions"
    )
    alerts = state.load_speed_monitor_items(
        plugin, state.SPEED_MONITOR_ALERTS_KEY, "alerts"
    )

    assert sessions == {"legacy": {"status": "active"}}
    assert alerts == {"alert": {"status": "pending"}}
    assert plugin.data["speed_monitor_sessions"]["schema_version"] == 1
    assert plugin.data["speed_monitor_alerts"]["schema_version"] == 1


def test_invalid_migration_disables_monitor_without_overwriting_source_data():
    """不可迁移状态应明确停用监控且不得静默覆盖原数据。"""
    monitor = _load("service.speed_monitor")
    invalid = ["do-not-discard"]
    plugin = FakePlugin(data={"speed_monitor_sessions": invalid})

    runtime = monitor.ensure_speed_monitor_runtime(plugin)

    assert plugin._speed_monitor_enabled is False
    assert runtime.state_error == "sessions state must be a dict"
    assert plugin._speed_monitor_state_error == runtime.state_error
    assert plugin.data["speed_monitor_sessions"] is invalid


def test_retention_keeps_active_sessions_and_caps_terminal_alerts_and_samples():
    """TTL/数量清理只裁剪终态历史，健康样本固定保留最近 20 条。"""
    state = _load("model.state")
    now = 4_000_000
    records = {
        "active-old": {"status": "active", "terminal_at": 1},
        "expired": {
            "status": "completed",
            "terminal_at": now - state.SPEED_MONITOR_TERMINAL_TTL_SECONDS - 1,
        },
    }
    records.update({
        f"terminal-{index}": {
            "status": "completed",
            "terminal_at": now - index,
        }
        for index in range(1002)
    })

    trimmed = state.trim_terminal_records(
        records, now=now, active_statuses=("active",)
    )

    assert "active-old" in trimmed
    assert "expired" not in trimmed
    assert len(trimmed) == 1001
    assert "terminal-0" in trimmed
    assert "terminal-1001" not in trimmed
    assert state.trim_health_samples(list(range(25))) == list(range(5, 25))
