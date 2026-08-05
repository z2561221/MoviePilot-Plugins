from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path


PLUGIN_DIR = Path(
    os.environ.get("DOWNLOADMANAGERLOCAL_PLUGIN_DIR")
    or Path(__file__).resolve().parents[1]
)


def _prepare_imports() -> None:
    """安装不执行插件入口和宿主依赖的 downloadmanagerlocal 包壳。"""
    for name in list(sys.modules):
        if name == "downloadmanagerlocal" or name.startswith("downloadmanagerlocal."):
            sys.modules.pop(name)
    package = types.ModuleType("downloadmanagerlocal")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["downloadmanagerlocal"] = package

    app = types.ModuleType("app")
    app_log = types.ModuleType("app.log")
    app_log.logger = types.SimpleNamespace(error=lambda *_args, **_kwargs: None)
    sys.modules.update({"app": app, "app.log": app_log})

    adapter = types.ModuleType("downloadmanagerlocal.adapter.moviepilot")
    adapter.get_downloader_config = lambda *_args, **_kwargs: None
    adapter.list_builtin_sites = lambda *_args, **_kwargs: []
    sys.modules[adapter.__name__] = adapter

    site_tag = types.ModuleType("downloadmanagerlocal.service.site_tag")
    site_tag.execute_tag_cleanup = lambda *_args, **_kwargs: None
    site_tag.scan_and_clean_tags = lambda *_args, **_kwargs: None
    sys.modules[site_tag.__name__] = site_tag


class SharedDataPlugin:
    """模拟共享持久层但运行态彼此隔离的 MoviePilot worker。"""

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
    _speed_monitor_mode = "auto"
    _speed_monitor_manual_speed_bps = {}
    _speed_monitor_floor_speed_bps = {}
    _speed_monitor_min_samples = 5

    def __init__(self, shared_data: dict) -> None:
        """绑定共享数据仓并初始化当前 worker 的空运行态。"""
        self.shared_data = shared_data
        self._speed_monitor_runtime = None
        self._speed_monitor_state_error = ""

    def get_data(self, key):
        """从共享持久层读取插件数据。"""
        return self.shared_data.get(key)

    def save_data(self, key, value):
        """把插件数据写入共享持久层。"""
        self.shared_data[key] = value


def _sample(speed: float, index: int) -> dict:
    """构造一个已完成下载的健康速度样本。"""
    return {
        "downloader_id": "qb-main",
        "torrent_hash": f"hash-{index}",
        "average_speed_bps": speed,
        "eligible": True,
    }


def _active_session(monitor):
    """构造一个由扫描 worker 持久化的活跃会话。"""
    return monitor.SpeedMonitorSession(
        downloader_id="qb-main",
        downloader_type="qbittorrent",
        torrent_hash="abc",
        name="Example",
        total_bytes=1_000,
        start_downloaded_bytes=100,
        start_remaining_bytes=900,
        last_downloaded_bytes=200,
        first_observed_at=10,
        last_observed_at=20,
        last_effective_at=20,
        last_valid_sample_at=20,
        last_success_poll_at=20,
        effective_seconds=10,
        last_state="active",
    )


def test_overview_reloads_persisted_state_without_overwriting_worker_runtime():
    """总览应看到其他 worker 新样本，且不得覆盖本 worker 的可写缓存。"""
    _prepare_imports()
    monitor = importlib.import_module("downloadmanagerlocal.service.speed_monitor")
    baseline_service = importlib.import_module(
        "downloadmanagerlocal.service.speed_baseline"
    )
    handlers = importlib.import_module("downloadmanagerlocal.controller.handlers")
    shared_data = {}
    viewer = SharedDataPlugin(shared_data)
    writer = SharedDataPlugin(shared_data)

    viewer_runtime = monitor.ensure_speed_monitor_runtime(viewer)
    assert viewer_runtime.baselines == {}

    writer_runtime = monitor.ensure_speed_monitor_runtime(writer)
    baseline = None
    for index, speed in enumerate((10_760_000, 4_580_000)):
        baseline, accepted, reason = baseline_service.record_health_sample(
            baseline,
            _sample(speed, index),
            min_samples=5,
        )
        assert accepted is True
        assert reason == ""
    writer_runtime.baselines["qb-main"] = baseline
    monitor.persist_speed_monitor_runtime(writer, writer_runtime, now=100)

    overview = handlers._speed_monitor_overview(viewer)

    assert overview["baselines"][0]["sample_count"] == 2
    assert overview["active_sessions"] == 0
    assert overview["active"] is False
    assert overview["service_status"] == "idle"
    assert viewer._speed_monitor_runtime is viewer_runtime
    assert viewer_runtime.baselines == {}


def test_overview_reports_running_only_while_an_active_session_exists():
    """总览只在持久化活跃会话存在时显示监控中。"""
    _prepare_imports()
    monitor = importlib.import_module("downloadmanagerlocal.service.speed_monitor")
    handlers = importlib.import_module("downloadmanagerlocal.controller.handlers")
    shared_data = {}
    writer = SharedDataPlugin(shared_data)
    runtime = monitor.ensure_speed_monitor_runtime(writer)
    runtime.sessions["qb-main:abc"] = _active_session(monitor)
    monitor.persist_speed_monitor_runtime(writer, runtime, now=20)

    overview = handlers._speed_monitor_overview(SharedDataPlugin(shared_data))

    assert overview["active_sessions"] == 1
    assert overview["active"] is True
    assert overview["service_status"] == "running"


def test_overview_distinguishes_disabled_and_state_error():
    """总览应分别暴露未启用和持久化状态异常。"""
    _prepare_imports()
    handlers = importlib.import_module("downloadmanagerlocal.controller.handlers")
    disabled = SharedDataPlugin({})
    disabled._speed_monitor_enabled = False

    disabled_overview = handlers._speed_monitor_overview(disabled)

    assert disabled_overview["active"] is False
    assert disabled_overview["service_status"] == "disabled"

    invalid_state = {
        "speed_monitor_sessions": {"schema_version": 99, "items": {}},
    }
    error_overview = handlers._speed_monitor_overview(SharedDataPlugin(invalid_state))

    assert error_overview["active"] is False
    assert error_overview["service_status"] == "error"
    assert "unsupported sessions schema version" in error_overview["state_error"]


def test_overview_drops_active_session_completed_by_another_worker():
    """其他 worker 已完成会话后，总览不得继续显示缓存中的活跃会话。"""
    _prepare_imports()
    monitor = importlib.import_module("downloadmanagerlocal.service.speed_monitor")
    handlers = importlib.import_module("downloadmanagerlocal.controller.handlers")
    shared_data = {}
    seed = SharedDataPlugin(shared_data)
    seed_runtime = monitor.ensure_speed_monitor_runtime(seed)
    seed_runtime.sessions["qb-main:abc"] = _active_session(monitor)
    monitor.persist_speed_monitor_runtime(seed, seed_runtime, now=20)

    viewer = SharedDataPlugin(shared_data)
    writer = SharedDataPlugin(shared_data)
    viewer_runtime = monitor.ensure_speed_monitor_runtime(viewer)
    writer_runtime = monitor.ensure_speed_monitor_runtime(writer)
    writer_runtime.sessions["qb-main:abc"].status = "completed"
    writer_runtime.sessions["qb-main:abc"].terminal_at = 30
    monitor.persist_speed_monitor_runtime(writer, writer_runtime, now=30)

    overview = handlers._speed_monitor_overview(viewer)

    assert overview["active_sessions"] == 0
    assert overview["active"] is False
    assert overview["service_status"] == "idle"
    assert viewer._speed_monitor_runtime is viewer_runtime
    assert viewer_runtime.sessions["qb-main:abc"].status == "active"
