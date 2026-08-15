from __future__ import annotations

import importlib
import os
import sys
import threading
import types
from pathlib import Path


PLUGIN_DIR = Path(
    os.environ.get("DOWNLOADMANAGERLOCAL_PLUGIN_DIR")
    or Path(__file__).resolve().parents[1]
)


def _load(module_name: str):
    """加载不执行插件入口的上传限速 worker。"""
    for name in list(sys.modules):
        if name == "downloadmanagerlocal" or name.startswith("downloadmanagerlocal."):
            sys.modules.pop(name)
    package = types.ModuleType("downloadmanagerlocal")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["downloadmanagerlocal"] = package
    return importlib.import_module(f"downloadmanagerlocal.{module_name}")


class FakePlugin:
    """提供上传限速 worker 所需的最小插件状态。"""

    _enabled = True
    _upload_limit_enabled = True
    _upload_limit_downloaders = ["QB2"]
    _upload_limit_downloader_limits_kib = {"QB2": 100}

    def __init__(self):
        """初始化 worker 属性与协调次数。"""
        self._upload_limit_thread = None
        self._upload_limit_stop_event = None
        self._upload_limit_wake_event = None
        self._upload_limit_worker_lock = None
        self.calls = 0

    def _coordinate_upload_limits(self):
        """记录一轮协调。"""
        self.calls += 1


def test_worker_starts_once_wakes_and_stop_does_not_call_restore():
    """worker 应单例运行、支持唤醒，并且停止只结束线程不执行恢复。"""
    worker = _load("service.upload_limit_worker")
    plugin = FakePlugin()

    assert worker.start_upload_limit_worker(plugin) is True
    assert worker.start_upload_limit_worker(plugin) is False
    assert worker.is_upload_limit_worker_running(plugin) is True
    assert worker.wake_upload_limit_worker(plugin) is True

    for _ in range(100):
        if plugin.calls >= 2:
            break
        threading.Event().wait(0.005)

    assert plugin.calls >= 1
    assert worker.stop_upload_limit_worker(plugin) is True
    assert worker.is_upload_limit_worker_running(plugin) is False
