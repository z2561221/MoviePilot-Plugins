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


class FakeDownloader:
    """提供可重复轮询结果的下载器替身。"""

    def __init__(self, response):
        """保存预设下载器响应。"""
        self.response = response

    def get_torrents(self):
        """返回预设下载器响应。"""
        return self.response


class FakePlugin:
    """提供多下载器监控所需最小插件接口。"""

    _enabled = True
    _transfer_enabled = False
    _fromdownloader = ""
    _todownloader = ""
    _fromtorrentpath = ""
    _iyuu_enabled = False
    _iyuu_token = ""
    _iyuu_downloaders = []
    _speed_monitor_enabled = True
    _speed_monitor_downloaders = ["qb-main", "tr-backup"]

    def __init__(self, services):
        """保存按名称索引的 fake 下载器服务。"""
        self.services = services
        self._speed_monitor_runtime = None

    def service_info(self, name):
        """按名称返回 fake 下载器服务。"""
        return self.services.get(name)


def test_speed_monitor_is_independent_from_transfer_and_iyuu_state():
    """转移与 IYUU 全关闭时速度监控仍能独立启用插件。"""
    config = _load("utils.config")
    plugin = FakePlugin({})

    assert config.is_speed_monitor_active(plugin) is True
    assert config.is_plugin_active(plugin) is True

    plugin._speed_monitor_enabled = False
    assert config.is_speed_monitor_active(plugin) is False
    assert config.is_plugin_active(plugin) is False

    plugin._speed_monitor_enabled = True
    plugin._speed_monitor_downloaders = []
    assert config.is_speed_monitor_active(plugin) is False
    assert config.is_plugin_active(plugin) is False


def test_qb_tr_multi_downloader_scan_creates_sessions_from_first_observation():
    """qB/TR 多下载器首次扫描应按实例建会话且不回填历史时长。"""
    monitor = _load("service.speed_monitor")
    services = {
        "qb-main": SimpleNamespace(
            type="qbittorrent",
            instance=FakeDownloader(([{
                "hash": "QB-HASH",
                "name": "QB Task",
                "total_size": 1000,
                "downloaded": 200,
                "added_on": 1,
                "state": "downloading",
                "dlspeed": 10,
            }], None)),
        ),
        "tr-backup": SimpleNamespace(
            type="transmission",
            instance=FakeDownloader(([SimpleNamespace(
                hashString="TR-HASH",
                name="TR Task",
                totalSize=2000,
                downloadedEver=500,
                dateAdded=2,
                status="downloading",
                rateDownload=20,
            )], None)),
        ),
    }
    plugin = FakePlugin(services)

    first = monitor.scan_speed_monitor(plugin, now=500)
    second = monitor.scan_speed_monitor(plugin, now=600)
    runtime = plugin._speed_monitor_runtime

    assert first == {
        "scanned_downloaders": 2,
        "created_sessions": 2,
        "active_sessions": 2,
        "errors": {},
    }
    assert second["created_sessions"] == 0
    assert set(runtime.downloader_locks) == {"qb-main", "tr-backup"}
    assert set(runtime.sessions) == {"qb-main:qb-hash", "tr-backup:tr-hash"}
    qb_session = runtime.sessions["qb-main:qb-hash"]
    tr_session = runtime.sessions["tr-backup:tr-hash"]
    assert qb_session.first_observed_at == 500
    assert qb_session.last_observed_at == 600
    assert qb_session.start_downloaded_bytes == 200
    assert qb_session.start_remaining_bytes == 800
    assert tr_session.first_observed_at == 500
    assert tr_session.start_downloaded_bytes == 500
    assert tr_session.start_remaining_bytes == 1500
    assert set(runtime.session_locks) == set(runtime.sessions)


def test_disabled_monitor_does_not_poll_or_create_runtime():
    """监控关闭时不得轮询下载器或创建运行态。"""
    monitor = _load("service.speed_monitor")
    plugin = FakePlugin({})
    plugin._speed_monitor_enabled = False

    assert monitor.scan_speed_monitor(plugin, now=500) == {
        "scanned_downloaders": 0,
        "created_sessions": 0,
        "active_sessions": 0,
        "errors": {},
    }
    assert plugin._speed_monitor_runtime is None


def test_scheduler_and_lifecycle_register_monitor_without_transfer_dependency():
    """调度器和生命周期应按独立速度监控门禁接入。"""
    scheduler_source = (PLUGIN_DIR / "service" / "scheduler.py").read_text(encoding="utf-8")
    lifecycle_source = (PLUGIN_DIR / "service" / "lifecycle.py").read_text(encoding="utf-8")
    entry_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")

    assert '"id": "DownloadSpeedMonitor"' in scheduler_source
    assert '"name": "下载速度异常监控"' in scheduler_source
    assert '"trigger": "interval"' in scheduler_source
    assert '"func": plugin._scan_download_speed' in scheduler_source
    assert '"minutes": plugin._speed_monitor_interval_minutes' in scheduler_source
    assert "if is_speed_monitor_active(plugin):" in lifecycle_source
    assert "ensure_speed_monitor_runtime(plugin)" in lifecycle_source
    assert "def _scan_download_speed(self):" in entry_source
