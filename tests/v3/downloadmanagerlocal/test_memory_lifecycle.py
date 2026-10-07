"""资源回收及停止期间在途限速写入回归。"""

import gc
import importlib
import runpy
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest


def helpers(filename):
    """复用现有纯 Python 测试替身，不连接真实下载器。"""
    return runpy.run_path(str(Path(__file__).with_name(filename)))


def test_expired_sessions_do_not_retain_locks():
    """多批过期会话不能留下按历史任务数量增长的锁表。"""
    module = helpers("test_speed_monitor_lifecycle.py")["_load"]("service.speed_monitor")
    runtime = module.SpeedMonitorRuntime()
    for batch in range(2):
        for number in range(batch * 1000, (batch + 1) * 1000):
            key = f"fake:{number}"
            runtime.sessions[key] = module.SpeedMonitorSession.from_dict({
                "downloader_id": "fake", "torrent_hash": str(number),
            })
            module._finish_session(runtime, key, "completed", 100)
        module._trim_runtime(runtime, 100 + 31 * 86400)
        gc.collect()
        assert not runtime.sessions
        assert not runtime.session_locks


def test_waiting_thread_keeps_same_session_lock_alive():
    """弱引用回收不能使同一会话的持有者与等待者获得不同锁。"""
    module = helpers("test_speed_monitor_lifecycle.py")["_load"]("service.speed_monitor")
    runtime = module.SpeedMonitorRuntime()
    owner = runtime.session_lock("same")
    waiting, done = threading.Event(), threading.Event()
    owner.acquire()

    def wait_for_lock():
        """持有等待锁的强引用，直到临界区结束。"""
        lock = runtime.session_lock("same")
        assert lock is owner
        waiting.set()
        with lock:
            done.set()

    thread = threading.Thread(target=wait_for_lock)
    thread.start()
    try:
        assert waiting.wait(2)
        gc.collect()
        assert runtime.session_lock("same") is owner
        assert not done.is_set()
    finally:
        owner.release()
        thread.join(2)
    assert done.is_set()
    del owner
    gc.collect()
    assert not runtime.session_locks


@pytest.mark.parametrize("restart", [False, True])
def test_stopped_inflight_global_read_never_writes(monkeypatch, restart):
    """读请求在途时停止，返回后不得写限速；重新启用也不能复活旧轮次。"""
    fake = helpers("test_upload_limiter_service.py")
    limiter = fake["_load"]("service.upload_limiter")
    worker = importlib.import_module("downloadmanagerlocal.service.upload_limit_worker")
    instance = fake["FakeTransmissionInstance"]([])
    plugin = fake["FakePlugin"](
        {"TR": SimpleNamespace(type="transmission", instance=instance)}, ["TR"], {"TR": 100},
    )
    plugin._transfer_stop_generation = 0
    entered, release = threading.Event(), threading.Event()
    original = limiter.read_global_upload_settings
    writes, results = [], []
    monkeypatch.setattr(instance.trc, "set_session", lambda **kw: writes.append(kw))

    def blocked_read(*args, **kwargs):
        """模拟已经发出、停止时无法中断的读取。"""
        entered.set()
        assert release.wait(3)
        return original(*args, **kwargs)

    monkeypatch.setattr(limiter, "read_global_upload_settings", blocked_read)
    plugin._coordinate_upload_limits = lambda: results.append(limiter.run_upload_limit_cycle(plugin))
    worker.start_upload_limit_worker(plugin)
    thread = plugin._upload_limit_thread
    try:
        assert entered.wait(2)
        worker.stop_upload_limit_worker(plugin, join_timeout=0)
        plugin._transfer_stop_generation += 1
        if restart:
            plugin._upload_limit_stop_event = threading.Event()
        release.set()
        thread.join(2)
        assert not thread.is_alive()
        assert not writes
        assert results[0]["service_status"] == "stopped"
    finally:
        release.set()
        thread.join(3)


def test_cycle_waiting_for_lock_exits_after_stop():
    """取消等锁轮次，不必等待另一个长时间下载器调用结束。"""
    fake = helpers("test_upload_limiter_service.py")
    limiter = fake["_load"]("service.upload_limiter")
    plugin = fake["FakePlugin"]({}, ["TR"], {"TR": 100})
    plugin._upload_limit_stop_event = threading.Event()
    lock = limiter._cycle_lock(plugin)
    results = []
    lock.acquire()
    thread = threading.Thread(target=lambda: results.append(limiter.run_upload_limit_cycle(plugin)))
    thread.start()
    try:
        plugin._upload_limit_stop_event.set()
        thread.join(2)
        assert not thread.is_alive()
        assert results[0]["service_status"] == "stopped"
    finally:
        lock.release()
        thread.join(2)
