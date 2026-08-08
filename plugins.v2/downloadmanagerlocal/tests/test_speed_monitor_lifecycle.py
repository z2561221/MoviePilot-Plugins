from __future__ import annotations

import importlib
import os
import sys
import threading
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
        self.data = {}
        self._speed_monitor_runtime = None
        self._speed_monitor_interval_seconds = 30
        self._speed_monitor_thread = None
        self._speed_monitor_stop_event = None
        self._speed_monitor_worker_lock = None

    def service_info(self, name):
        """按名称返回 fake 下载器服务。"""
        return self.services.get(name)

    def get_data(self, key):
        """读取内存插件数据。"""
        return self.data.get(key)

    def save_data(self, key, value):
        """保存内存插件数据。"""
        self.data[key] = value


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


def test_scheduler_and_lifecycle_use_on_demand_monitor_worker():
    """宿主调度器不得常驻轮询，生命周期只恢复活跃会话 worker。"""
    scheduler_source = (PLUGIN_DIR / "service" / "scheduler.py").read_text(encoding="utf-8")
    lifecycle_source = (PLUGIN_DIR / "service" / "lifecycle.py").read_text(encoding="utf-8")
    entry_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")

    assert '"id": "DownloadSpeedMonitor"' not in scheduler_source
    assert '"name": "下载速度异常监控"' not in scheduler_source
    assert "if is_speed_monitor_active(plugin):" in lifecycle_source
    assert "ensure_speed_monitor_runtime(plugin)" in lifecycle_source
    assert "start_speed_monitor_worker_if_needed(plugin, runtime)" in lifecycle_source
    assert "stop_speed_monitor_worker(plugin)" in lifecycle_source
    assert lifecycle_source.index("stop_speed_monitor_worker(plugin)") < lifecycle_source.index(
        "stop_speed_monitor_runtime(plugin)"
    )
    assert "def _scan_download_speed(self):" in entry_source
    assert "EventType.DownloadAdded" in entry_source
    assert "def on_download_added(self, event: Event):" in entry_source
    assert "start_speed_monitor_worker(self)" in entry_source


def test_worker_starts_once_and_plugin_stop_signals_and_joins_it():
    """重复启动只能保留一个 worker，停止时必须唤醒并完成 join。"""
    worker = _load("service.speed_worker")
    plugin = FakePlugin({})
    plugin._speed_monitor_interval_seconds = 300
    plugin._scan_download_speed = lambda: {"active_sessions": 1}

    assert worker.start_speed_monitor_worker(plugin) is True
    first_thread = plugin._speed_monitor_thread
    assert first_thread is not None
    assert worker.is_speed_monitor_worker_running(plugin) is True
    assert worker.start_speed_monitor_worker(plugin) is False
    assert plugin._speed_monitor_thread is first_thread

    assert worker.stop_speed_monitor_worker(plugin) is True
    assert first_thread.is_alive() is False
    assert worker.is_speed_monitor_worker_running(plugin) is False


def test_concurrent_worker_starts_create_only_one_thread():
    """并发下载新增触发也只能创建一个速度监控 worker。"""
    worker = _load("service.speed_worker")
    plugin = FakePlugin({})
    plugin._speed_monitor_interval_seconds = 300
    plugin._scan_download_speed = lambda: {"active_sessions": 1}
    barrier = threading.Barrier(8)
    results = []

    def start_after_barrier():
        """等待并发门闩后尝试启动同一插件 worker。"""
        barrier.wait()
        results.append(worker.start_speed_monitor_worker(plugin))

    starters = [threading.Thread(target=start_after_barrier) for _ in range(8)]
    for starter in starters:
        starter.start()
    for starter in starters:
        starter.join(timeout=2)

    assert results.count(True) == 1
    assert results.count(False) == 7
    assert worker.is_speed_monitor_worker_running(plugin) is True
    worker.stop_speed_monitor_worker(plugin)


def test_worker_scans_every_configured_seconds_and_exits_after_last_session():
    """worker 应按秒级间隔扫描，并在最后活跃会话结束后自行退出。"""
    worker = _load("service.speed_worker")
    plugin = FakePlugin({})
    waits = []
    scans = iter(({"active_sessions": 1}, {"active_sessions": 0}))

    class ControlledEvent:
        """记录等待间隔且不阻塞测试线程。"""

        def wait(self, timeout):
            """记录本轮等待秒数并允许继续扫描。"""
            waits.append(timeout)
            return False

        def is_set(self):
            """测试期间不触发外部停止。"""
            return False

        def set(self):
            """兼容停止事件接口。"""
            return None

    stop_event = ControlledEvent()
    plugin._speed_monitor_worker_lock = threading.RLock()
    plugin._speed_monitor_stop_event = stop_event
    plugin._speed_monitor_thread = threading.current_thread()
    plugin._scan_download_speed = lambda: next(scans)

    worker._speed_monitor_loop(plugin, stop_event)

    assert waits == [30, 30]
    assert plugin._speed_monitor_thread is None
    assert plugin._speed_monitor_stop_event is None


def test_worker_retries_after_unexpected_scan_exception():
    """单轮扫描异常不得杀死 worker，应在下一间隔继续扫描。"""
    worker = _load("service.speed_worker")
    plugin = FakePlugin({})
    waits = []
    scan_calls = 0

    class ControlledEvent:
        """提供无阻塞等待的停止事件替身。"""

        def wait(self, timeout):
            """记录等待秒数并允许继续扫描。"""
            waits.append(timeout)
            return False

        def is_set(self):
            """测试期间不触发外部停止。"""
            return False

    def scan_once_failed():
        """首轮抛错，第二轮返回无活跃会话。"""
        nonlocal scan_calls
        scan_calls += 1
        if scan_calls == 1:
            raise RuntimeError("temporary failure")
        return {"active_sessions": 0}

    stop_event = ControlledEvent()
    plugin._speed_monitor_worker_lock = threading.RLock()
    plugin._speed_monitor_stop_event = stop_event
    plugin._speed_monitor_thread = threading.current_thread()
    plugin._scan_download_speed = scan_once_failed

    worker._speed_monitor_loop(plugin, stop_event)

    assert scan_calls == 2
    assert waits == [30, 30]


def test_reload_resumes_worker_only_for_persisted_active_sessions():
    """重载时只有持久化活跃会话存在才恢复监控 worker。"""
    worker = _load("service.speed_worker")
    plugin = FakePlugin({})
    plugin._speed_monitor_interval_seconds = 300
    plugin._scan_download_speed = lambda: {"active_sessions": 1}
    idle_runtime = SimpleNamespace(sessions={})

    assert worker.start_speed_monitor_worker_if_needed(plugin, idle_runtime) is False
    assert worker.is_speed_monitor_worker_running(plugin) is False

    active_runtime = SimpleNamespace(
        sessions={"qb-main:abc": SimpleNamespace(status="active")}
    )
    assert worker.start_speed_monitor_worker_if_needed(plugin, active_runtime) is True
    assert worker.is_speed_monitor_worker_running(plugin) is True
    worker.stop_speed_monitor_worker(plugin)


def test_download_added_event_starts_session_before_interval_scan():
    """下载新增事件应立即建会话，短任务不能等下一轮五分钟扫描。"""
    monitor = _load("service.speed_monitor")
    downloader = FakeDownloader(([{
        "hash": "QB-HASH",
        "name": "Short QB Task",
        "total_size": 1000,
        "downloaded": 200,
        "added_on": 1,
        "state": "downloading",
        "dlspeed": 40,
    }], None))
    plugin = FakePlugin({
        "qb-main": SimpleNamespace(type="qbittorrent", instance=downloader),
    })
    plugin._speed_monitor_downloaders = ["qb-main"]
    event = SimpleNamespace(event_data={"hash": "QB-HASH", "downloader": "qb-main"})

    started = monitor.handle_download_added_event(plugin, event, now=500)

    assert started["handled"] is True
    assert started["created_sessions"] == 1
    session = plugin._speed_monitor_runtime.sessions["qb-main:qb-hash"]
    assert session.first_observed_at == 500
    assert session.status == "active"

    downloader.response = ([{
        "hash": "QB-HASH",
        "name": "Short QB Task",
        "total_size": 1000,
        "downloaded": 1000,
        "added_on": 1,
        "state": "uploading",
        "dlspeed": 0,
    }], None)
    monitor.scan_speed_monitor(plugin, now=520)

    assert session.status == "completed"
