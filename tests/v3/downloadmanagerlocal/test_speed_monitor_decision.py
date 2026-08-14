from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


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
    """提供可切换任务列表或异常的下载器替身。"""

    def __init__(self, response):
        """保存初始轮询响应。"""
        self.response = response

    def get_torrents(self):
        """返回当前轮询响应或抛出异常。"""
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakePlugin:
    """提供异常判定所需的最小插件配置与数据接口。"""

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
    _speed_monitor_grace_minutes = 10 / 60
    _speed_monitor_consecutive_abnormal_samples = 2
    _speed_monitor_manual_speed_bps = {"qb-main": 100.0}
    _speed_monitor_floor_speed_bps = {}

    def __init__(self, downloader, downloader_type="qbittorrent", downloader_id="qb-main"):
        """保存 fake 下载器并初始化空持久化数据。"""
        self.downloader = downloader
        self.downloader_type = downloader_type
        self.downloader_id = downloader_id
        self._speed_monitor_downloaders = [downloader_id]
        self._speed_monitor_manual_speed_bps = {downloader_id: 100.0}
        self.data = {}
        self._speed_monitor_runtime = None

    def service_info(self, name):
        """返回 fake qBittorrent 服务。"""
        return SimpleNamespace(type=self.downloader_type, instance=self.downloader)

    def get_data(self, key):
        """读取内存插件数据。"""
        return self.data.get(key)

    def save_data(self, key, value):
        """保存内存插件数据。"""
        self.data[key] = value


def _item(downloaded, *, state="downloading", speed=10, total=1000, downloader_type="qbittorrent"):
    """构造指定进度、状态和瞬时速度的 qB 任务。"""
    if downloader_type == "transmission":
        return SimpleNamespace(
            hashString="ABC", name="Example", totalSize=total,
            downloadedEver=downloaded, status=state, rateDownload=speed,
        )
    return {
        "hash": "ABC",
        "name": "Example",
        "total_size": total,
        "downloaded": downloaded,
        "state": state,
        "dlspeed": speed,
    }


def _scan(monitor, plugin, downloader, now, items):
    """切换 fake 任务列表并执行一次扫描。"""
    downloader.response = (items, None)
    return monitor.scan_speed_monitor(plugin, now=now)


def test_reference_speed_and_tolerance_formula_cover_floor_boundaries():
    """自动参考速度、保护下限和容忍倍数应产生可复现的时限。"""
    decision = _load("service.speed_decision")
    baseline = {"trusted_speed_bps": 100.0}

    plain, plain_source = decision.resolve_reference_speed(
        mode="auto",
        downloader_id="qb-main",
        baseline=baseline,
        manual_speeds={},
        floor_speeds={},
    )
    protected, protected_source = decision.resolve_reference_speed(
        mode="auto",
        downloader_id="qb-main",
        baseline=baseline,
        manual_speeds={},
        floor_speeds={"qb-main": 200.0},
    )
    accepted = decision.evaluate_speed_anomaly(
        start_remaining_bytes=900,
        total_bytes=1000,
        downloaded_bytes=100,
        current_speed_bps=0,
        effective_seconds=0,
        reference_speed_bps=plain,
        reference_source=plain_source,
        tolerance=1.5,
        grace_seconds=0,
        required_samples=2,
        previous_abnormal_samples=0,
    )
    rejected = decision.evaluate_speed_anomaly(
        start_remaining_bytes=900,
        total_bytes=1000,
        downloaded_bytes=100,
        current_speed_bps=0,
        effective_seconds=0,
        reference_speed_bps=protected,
        reference_source=protected_source,
        tolerance=1.0,
        grace_seconds=0,
        required_samples=2,
        previous_abnormal_samples=0,
    )

    assert (plain, plain_source) == (100.0, "trusted_baseline")
    assert (protected, protected_source) == (
        200.0,
        "trusted_baseline_with_floor",
    )
    assert accepted["expected_seconds"] == 9
    assert accepted["allowed_seconds"] == 13.5
    assert rejected["status"] == "unready"
    assert rejected["reason"] == "invalid_tolerance"


@pytest.mark.parametrize(
    ("downloader_type", "downloader_id"),
    [("qbittorrent", "qb-main"), ("transmission", "tr-backup")],
)
def test_partial_remaining_grace_zero_speed_and_consecutive_samples(
    downloader_type, downloader_id
):
    """部分下载预算应在宽限后把零速超时连续采样提升为异常。"""
    monitor = _load("service.speed_monitor")
    item = lambda downloaded: _item(
        downloaded, speed=0, downloader_type=downloader_type
    )
    downloader = MutableDownloader(([item(400)], None))
    plugin = FakePlugin(downloader, downloader_type, downloader_id)

    monitor.scan_speed_monitor(plugin, now=0)
    _scan(monitor, plugin, downloader, 5, [item(450)])
    session = plugin._speed_monitor_runtime.sessions[f"{downloader_id}:abc"]
    assert session.start_remaining_bytes == 600
    assert session.decision["status"] == "grace"

    _scan(monitor, plugin, downloader, 10, [item(500)])
    assert session.decision["expected_seconds"] == 6
    assert session.decision["allowed_seconds"] == 9
    assert session.decision["status"] == "suspected"
    assert session.consecutive_abnormal_samples == 1

    _scan(monitor, plugin, downloader, 15, [item(500)])
    assert session.decision["status"] == "anomalous"
    assert session.decision["current_speed_bps"] == 0
    assert session.consecutive_abnormal_samples == 2
    assert session.had_anomaly is True


def test_disconnect_freezes_effective_timeout_and_abnormal_counter():
    """下载器断连期间不得推进有效时限或连续异常次数。"""
    monitor = _load("service.speed_monitor")
    downloader = MutableDownloader(([_item(400)], None))
    plugin = FakePlugin(downloader)

    monitor.scan_speed_monitor(plugin, now=0)
    downloader.response = TimeoutError("offline")
    monitor.scan_speed_monitor(plugin, now=20)
    session = plugin._speed_monitor_runtime.sessions["qb-main:abc"]
    assert session.effective_seconds == 0
    assert session.consecutive_abnormal_samples == 0

    _scan(monitor, plugin, downloader, 100, [_item(500)])
    assert session.effective_seconds == 0
    assert session.decision["status"] == "grace"
    _scan(monitor, plugin, downloader, 110, [_item(550)])
    assert session.effective_seconds == 10
    assert session.decision["status"] == "suspected"


def test_completed_and_zero_byte_tasks_never_become_anomalous():
    """首次已完成、完成切换和零体积任务均不得生成异常状态。"""
    monitor = _load("service.speed_monitor")

    complete_downloader = MutableDownloader(([_item(1000, state="uploading")], None))
    complete_plugin = FakePlugin(complete_downloader)
    monitor.scan_speed_monitor(complete_plugin, now=0)
    assert complete_plugin._speed_monitor_runtime.sessions == {}

    active_downloader = MutableDownloader(([_item(100)], None))
    active_plugin = FakePlugin(active_downloader)
    monitor.scan_speed_monitor(active_plugin, now=0)
    _scan(
        monitor,
        active_plugin,
        active_downloader,
        20,
        [_item(1000, state="uploading")],
    )
    completed = active_plugin._speed_monitor_runtime.sessions["qb-main:abc"]
    assert completed.status == "completed"
    assert completed.had_anomaly is False

    zero_downloader = MutableDownloader(([_item(0, total=0, speed=0)], None))
    zero_plugin = FakePlugin(zero_downloader)
    monitor.scan_speed_monitor(zero_plugin, now=0)
    _scan(monitor, zero_plugin, zero_downloader, 100, [_item(0, total=0, speed=0)])
    zero = zero_plugin._speed_monitor_runtime.sessions["qb-main:abc"]
    assert zero.decision["status"] == "unready"
    assert zero.decision["reason"] == "no_remaining_bytes"
    assert zero.had_anomaly is False
