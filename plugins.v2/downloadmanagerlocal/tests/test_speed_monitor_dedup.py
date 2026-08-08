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
    """提供可切换 qB 任务列表的下载器替身。"""

    def __init__(self, items):
        """保存初始任务列表。"""
        self.items = items

    def get_torrents(self):
        """返回当前任务列表。"""
        return self.items, None


class FakePlugin:
    """提供异常周期去重所需的最小插件接口。"""

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
    _speed_monitor_mode = "manual"
    _speed_monitor_tolerance = 1.5
    _speed_monitor_grace_minutes = 0
    _speed_monitor_consecutive_abnormal_samples = 1
    _speed_monitor_manual_speed_bps = {"qb-main": 100.0}
    _speed_monitor_floor_speed_bps = {}
    _speed_monitor_min_samples = 5

    def __init__(self, downloader, data=None):
        """保存 fake 下载器和可选持久化数据。"""
        self.downloader = downloader
        self.data = dict(data or {})
        self._speed_monitor_runtime = None

    def service_info(self, name):
        """返回 fake qBittorrent 服务。"""
        return SimpleNamespace(type="qbittorrent", instance=self.downloader)

    def get_data(self, key):
        """读取内存插件数据。"""
        return self.data.get(key)

    def save_data(self, key, value):
        """保存内存插件数据。"""
        self.data[key] = value


def _item(downloaded, state="downloading"):
    """构造指定进度和状态的 qB 任务。"""
    return {
        "hash": "ABC",
        "name": "Example",
        "total_size": 1000,
        "downloaded": downloaded,
        "state": state,
        "dlspeed": 0,
    }


def _scan(monitor, plugin, downloader, now, downloaded, state="downloading"):
    """更新 fake 任务并执行一次扫描。"""
    downloader.items = [_item(downloaded, state)]
    return monitor.scan_speed_monitor(plugin, now=now)


def test_same_anomaly_epoch_creates_one_pending_alert_across_reload():
    """同一异常周期在重复采样和插件重载后只能保留一个 pending 告警。"""
    monitor = _load("service.speed_monitor")
    downloader = MutableDownloader([_item(100)])
    plugin = FakePlugin(downloader)

    monitor.scan_speed_monitor(plugin, now=0)
    _scan(monitor, plugin, downloader, 20, 200)
    _scan(monitor, plugin, downloader, 30, 250)
    session = plugin._speed_monitor_runtime.sessions["qb-main:abc"]

    assert session.anomaly_epoch == 1
    assert session.anomaly_active is True
    assert list(plugin._speed_monitor_runtime.alerts) == ["qb-main:abc:1"]
    assert plugin._speed_monitor_runtime.alerts["qb-main:abc:1"]["status"] == "pending"

    reloaded = FakePlugin(downloader, plugin.data)
    _scan(monitor, reloaded, downloader, 40, 300)
    restored = reloaded._speed_monitor_runtime.sessions["qb-main:abc"]
    assert restored.anomaly_epoch == 1
    assert restored.anomaly_active is True
    assert list(reloaded._speed_monitor_runtime.alerts) == ["qb-main:abc:1"]


def test_recovery_closes_epoch_and_later_anomaly_creates_next_epoch():
    """恢复正常应收束当前周期，后续异常才允许创建新 epoch。"""
    monitor = _load("service.speed_monitor")
    downloader = MutableDownloader([_item(100)])
    plugin = FakePlugin(downloader)

    monitor.scan_speed_monitor(plugin, now=0)
    _scan(monitor, plugin, downloader, 20, 200)
    plugin._speed_monitor_manual_speed_bps = {"qb-main": 10.0}
    _scan(monitor, plugin, downloader, 30, 300)
    session = plugin._speed_monitor_runtime.sessions["qb-main:abc"]

    assert session.anomaly_active is False
    assert plugin._speed_monitor_runtime.alerts["qb-main:abc:1"]["status"] == "recovered"
    assert plugin._speed_monitor_runtime.alerts["qb-main:abc:1"]["handled_at"] == 30

    plugin._speed_monitor_manual_speed_bps = {"qb-main": 100.0}
    _scan(monitor, plugin, downloader, 40, 350)
    assert session.anomaly_epoch == 2
    assert session.anomaly_active is True
    assert set(plugin._speed_monitor_runtime.alerts) == {
        "qb-main:abc:1",
        "qb-main:abc:2",
    }


def test_completion_closes_pending_alert_without_new_notification_or_sample():
    """异常任务完成时应收束告警且不得进入健康基准。"""
    monitor = _load("service.speed_monitor")
    downloader = MutableDownloader([_item(100)])
    plugin = FakePlugin(downloader)

    monitor.scan_speed_monitor(plugin, now=0)
    _scan(monitor, plugin, downloader, 20, 200)
    _scan(monitor, plugin, downloader, 30, 1000, "uploading")
    session = plugin._speed_monitor_runtime.sessions["qb-main:abc"]
    alert = plugin._speed_monitor_runtime.alerts["qb-main:abc:1"]

    assert session.status == "completed"
    assert session.anomaly_active is False
    assert session.sample_eligible is False
    assert "session_anomaly" in session.completion_stats["rejection_reasons"]
    assert alert["status"] == "completed"
    assert alert["handled_at"] == 30
    assert plugin._speed_monitor_runtime.baselines == {}


def test_reset_entry_persists_provisional_state():
    """基准重置入口应立刻持久化并重新等待校准样本。"""
    monitor = _load("service.speed_monitor")
    downloader = MutableDownloader([])
    plugin = FakePlugin(downloader)
    runtime = monitor.ensure_speed_monitor_runtime(plugin)
    runtime.baselines["qb-main"] = {
        "samples": [{"average_speed_bps": 100}],
        "status": "trusted",
        "trusted_speed_bps": 100,
    }

    result = monitor.reset_speed_monitor_baseline(
        plugin, "qb-main", now=500
    )

    assert result["success"] is True
    assert result["baseline"]["status"] == "provisional"
    assert result["baseline"]["sample_count"] == 0
    assert result["baseline"]["trusted_speed_bps"] == 0
    stored = plugin.data["speed_monitor_baselines"]["items"]["qb-main"]
    assert stored["reset_at"] == 500
