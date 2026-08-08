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


def _load_monitor():
    """加载速度监控纯 Python 服务。"""
    _prepare_imports()
    return importlib.import_module("downloadmanagerlocal.service.speed_monitor")


class MutableDownloader:
    """提供可切换任务列表或错误的下载器替身。"""

    def __init__(self, items):
        """保存初始任务列表。"""
        self.response = (items, None)

    def get_torrents(self):
        """返回当前轮询结果或抛出错误。"""
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakePlugin:
    """提供完成统计所需的最小插件和数据接口。"""

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

    def __init__(self, downloader, downloader_type="qbittorrent", downloader_id="qb-main"):
        """保存 fake 下载器并初始化空插件数据。"""
        self.downloader = downloader
        self.downloader_type = downloader_type
        self.downloader_id = downloader_id
        self._speed_monitor_downloaders = [downloader_id]
        self.data = {}
        self._speed_monitor_runtime = None

    def service_info(self, name):
        """返回 fake qBittorrent 服务。"""
        if name != self.downloader_id:
            return None
        return SimpleNamespace(type=self.downloader_type, instance=self.downloader)

    def get_data(self, key):
        """读取插件数据。"""
        return self.data.get(key)

    def save_data(self, key, value):
        """保存插件数据。"""
        self.data[key] = value


def _item(downloaded, state="downloading", total=1000):
    """构造指定进度和状态的 qB 任务。"""
    return {
        "hash": "ABC",
        "name": "Example",
        "total_size": total,
        "downloaded": downloaded,
        "state": state,
        "dlspeed": 10,
    }


def _matrix_item(downloader_type, downloaded, state="downloading", total=1000):
    """构造 qB 字典或 Transmission camelCase 对象。"""
    if downloader_type == "transmission":
        return SimpleNamespace(
            hashString="ABC", name="Example", totalSize=total,
            downloadedEver=downloaded, status=state, rateDownload=10,
        )
    return _item(downloaded, state, total)


def _scan(monitor, plugin, downloader, now, items):
    """切换 fake 任务列表并执行一次扫描。"""
    downloader.response = (items, None)
    return monitor.scan_speed_monitor(plugin, now=now)


def test_partial_download_completion_uses_observed_delta_and_effective_time():
    """部分下载任务只按首次观察后的新增字节和有效时长计算平均速度。"""
    monitor = _load_monitor()
    downloader = MutableDownloader([_item(400)])
    plugin = FakePlugin(downloader)

    monitor.scan_speed_monitor(plugin, now=10)
    _scan(monitor, plugin, downloader, 20, [_item(700)])
    _scan(monitor, plugin, downloader, 30, [_item(1000, "uploading")])
    session = plugin._speed_monitor_runtime.sessions["qb-main:abc"]
    samples = plugin._speed_monitor_runtime.baselines["qb-main"]["samples"]

    assert session.status == "completed"
    assert session.completion_stats["observed_bytes"] == 600
    assert session.completion_stats["effective_seconds"] == 20
    assert session.completion_stats["average_speed_bps"] == 30
    assert session.sample_eligible is True
    assert samples == [session.completion_stats]


def test_paused_and_queued_intervals_do_not_inflate_effective_time():
    """暂停、排队和恢复首个采样区间不得计入有效下载时长。"""
    monitor = _load_monitor()
    downloader = MutableDownloader([_item(100)])
    plugin = FakePlugin(downloader)

    monitor.scan_speed_monitor(plugin, now=10)
    _scan(monitor, plugin, downloader, 20, [_item(100, "pausedDL")])
    _scan(monitor, plugin, downloader, 30, [_item(100, "queuedDL")])
    _scan(monitor, plugin, downloader, 40, [_item(200)])
    _scan(monitor, plugin, downloader, 50, [_item(300)])
    _scan(monitor, plugin, downloader, 60, [_item(1000, "uploading")])
    session = plugin._speed_monitor_runtime.sessions["qb-main:abc"]

    assert session.effective_seconds == 20
    assert session.completion_stats["observed_bytes"] == 900
    assert session.completion_stats["average_speed_bps"] == 45


def test_zero_total_zero_time_and_zero_delta_are_not_health_samples():
    """零体积、零有效时长和零字节增量均不得进入健康样本。"""
    monitor = _load_monitor()

    zero_total_downloader = MutableDownloader([_item(0, total=0)])
    zero_total = FakePlugin(zero_total_downloader)
    monitor.scan_speed_monitor(zero_total, now=10)
    _scan(
        monitor, zero_total, zero_total_downloader, 20,
        [_item(0, "uploading", total=0)],
    )
    zero_total_session = zero_total._speed_monitor_runtime.sessions["qb-main:abc"]
    assert zero_total_session.sample_eligible is False
    assert "zero_total_bytes" in zero_total_session.completion_stats["rejection_reasons"]

    zero_time_downloader = MutableDownloader([_item(100)])
    zero_time = FakePlugin(zero_time_downloader)
    monitor.scan_speed_monitor(zero_time, now=10)
    _scan(monitor, zero_time, zero_time_downloader, 10, [_item(1000, "uploading")])
    zero_time_session = zero_time._speed_monitor_runtime.sessions["qb-main:abc"]
    assert zero_time_session.sample_eligible is False
    assert "no_effective_time" in zero_time_session.completion_stats["rejection_reasons"]

    zero_delta_downloader = MutableDownloader([_item(1000, "downloading", total=2000)])
    zero_delta = FakePlugin(zero_delta_downloader)
    monitor.scan_speed_monitor(zero_delta, now=10)
    _scan(
        monitor, zero_delta, zero_delta_downloader, 20,
        [_item(1000, "uploading", total=2000)],
    )
    zero_delta_session = zero_delta._speed_monitor_runtime.sessions["qb-main:abc"]
    assert zero_delta_session.sample_eligible is False
    assert "no_observed_bytes" in zero_delta_session.completion_stats["rejection_reasons"]


def test_error_disconnect_and_missing_sessions_never_enter_health_samples():
    """任务错误、断连和外部删除终态均不得进入健康样本。"""
    monitor = _load_monitor()

    error_downloader = MutableDownloader([_item(100)])
    error_plugin = FakePlugin(error_downloader)
    monitor.scan_speed_monitor(error_plugin, now=10)
    _scan(monitor, error_plugin, error_downloader, 20, [_item(200, "missingFiles")])
    _scan(monitor, error_plugin, error_downloader, 30, [_item(1000, "uploading")])
    error_session = error_plugin._speed_monitor_runtime.sessions["qb-main:abc"]
    assert error_session.sample_eligible is False
    assert "session_error" in error_session.completion_stats["rejection_reasons"]

    disconnect_downloader = MutableDownloader([_item(100)])
    disconnect_plugin = FakePlugin(disconnect_downloader)
    monitor.scan_speed_monitor(disconnect_plugin, now=10)
    disconnect_downloader.response = TimeoutError("offline")
    monitor.scan_speed_monitor(disconnect_plugin, now=20)
    _scan(
        monitor, disconnect_plugin, disconnect_downloader, 30,
        [_item(1000, "uploading")],
    )
    disconnect_session = disconnect_plugin._speed_monitor_runtime.sessions["qb-main:abc"]
    assert disconnect_session.sample_eligible is False
    assert "session_error" in disconnect_session.completion_stats["rejection_reasons"]

    missing_downloader = MutableDownloader([_item(100)])
    missing_plugin = FakePlugin(missing_downloader)
    monitor.scan_speed_monitor(missing_plugin, now=10)
    _scan(monitor, missing_plugin, missing_downloader, 20, [])
    missing_session = missing_plugin._speed_monitor_runtime.sessions["qb-main:abc"]
    assert missing_session.status == "missing"
    assert missing_plugin._speed_monitor_runtime.baselines == {}


def test_repeated_completed_snapshot_does_not_duplicate_health_sample():
    """同一会话重复出现完成快照时只能保存一条健康样本。"""
    monitor = _load_monitor()
    downloader = MutableDownloader([_item(100)])
    plugin = FakePlugin(downloader)

    monitor.scan_speed_monitor(plugin, now=10)
    _scan(monitor, plugin, downloader, 20, [_item(500)])
    _scan(monitor, plugin, downloader, 30, [_item(1000, "uploading")])
    _scan(monitor, plugin, downloader, 40, [_item(1000, "uploading")])

    assert len(plugin._speed_monitor_runtime.baselines["qb-main"]["samples"]) == 1
    assert plugin._speed_monitor_runtime.sessions["qb-main:abc"].terminal_at == 30


@pytest.mark.parametrize(
    ("downloader_type", "downloader_id", "states"),
    [
        ("qbittorrent", "qb-main", ("pausedDL", "queuedDL", "checkingDL", "uploading")),
        ("transmission", "tr-backup", ("stopped", "queued", "checking", "seeding")),
    ],
)
def test_qb_tr_pause_queue_checking_and_completion_matrix(
    downloader_type, downloader_id, states
):
    """qB/TR 暂停、排队和校验都冻结计时，恢复后均可完成。"""
    monitor = _load_monitor()
    item = lambda downloaded, state="downloading": _matrix_item(
        downloader_type, downloaded, state
    )
    downloader = MutableDownloader([item(100)])
    plugin = FakePlugin(downloader, downloader_type, downloader_id)

    monitor.scan_speed_monitor(plugin, now=10)
    _scan(monitor, plugin, downloader, 20, [item(100, states[0])])
    _scan(monitor, plugin, downloader, 30, [item(100, states[1])])
    _scan(monitor, plugin, downloader, 40, [item(100, states[2])])
    _scan(monitor, plugin, downloader, 50, [item(200)])
    _scan(monitor, plugin, downloader, 60, [item(300)])
    _scan(monitor, plugin, downloader, 70, [item(1000, states[3])])
    session = plugin._speed_monitor_runtime.sessions[f"{downloader_id}:abc"]

    assert session.downloader_type == downloader_type
    assert session.status == "completed"
    assert session.effective_seconds == 20
    assert session.sample_eligible is True
