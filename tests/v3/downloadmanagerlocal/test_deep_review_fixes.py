"""验证深审发现的删除返回值、限速停用与并发生命周期问题。"""

import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from app.plugins.downloadmanagerlocal.service import archive, speed_worker

from . import test_speed_monitor_delete as deletion
from . import test_upload_limiter_service as limits


def test_false_delete_preserves_retryable_alert():
    """下载器拒绝删除时保留会话和确认入口，重试成功后才进入终态。"""
    actions = deletion._load("service.speed_actions")
    runtime = deletion._runtime()
    downloader = deletion.FakeDownloader()
    downloader.delete_torrents = lambda **kwargs: False
    plugin = deletion.FakePlugin(runtime, downloader)
    deletion._process(actions, plugin, "delete")
    deletion._process(actions, plugin, "confirm")
    alert = runtime.alerts["qb-main:abc123:1"]
    assert alert["deletion_result"]["success"] is False
    assert alert["status"] == "confirming"
    assert runtime.sessions["qb-main:abc123"].status != "deleted"
    downloader.delete_torrents = lambda **kwargs: True
    deletion._process(actions, plugin, "confirm")
    assert alert["deletion_result"]["success"] is True


def test_queued_cycle_cannot_reapply_after_disable():
    """等待执行锁的旧轮次不得覆盖已经完成的停用恢复。"""
    limiter = limits._load("service.upload_limiter")
    instance = limits.FakeQbInstance([])
    plugin = limits.FakePlugin(
        {"QB2": SimpleNamespace(type="qbittorrent", instance=instance)},
        ["QB2"], {"QB2": 122},
    )
    limiter.run_upload_limit_cycle(plugin, now=1000)
    entered = threading.Event()

    class ObservedLock:
        """观测旧线程准备获取锁，避免用不确定的睡眠制造竞态。"""
        def __init__(self):
            """建立可重入测试锁。"""
            self.lock = threading.RLock()

        def __enter__(self):
            """在真实阻塞前通知测试主线程。"""
            if threading.current_thread().name == "old-cycle":
                entered.set()
            self.lock.acquire()
            return self

        def __exit__(self, *args):
            """释放测试锁。"""
            self.lock.release()

    plugin._upload_limit_cycle_lock = ObservedLock()
    with plugin._upload_limit_cycle_lock:
        worker = threading.Thread(name="old-cycle", target=limiter.run_upload_limit_cycle, args=(plugin,))
        worker.start()
        assert entered.wait(2)
        plugin._upload_limit_enabled = False
        limiter.restore_upload_limits(plugin)
        assert instance.qbc.transfer.upload_limit == 0
    worker.join(3)
    assert not worker.is_alive()
    assert instance.qbc.transfer.upload_limit == 0
    assert not plugin._upload_limit_state["management_active"]


def test_archive_concurrent_writes_keep_all_records_and_counts():
    """并发不同种子和同一种子的失败记录均不得丢失。"""
    data = {}

    def read(key):
        """模拟存储返回独立快照并放大旧的读改写覆盖窗口。"""
        snapshot = copy.deepcopy(data.get(key))
        time.sleep(0.002)
        return snapshot

    plugin = SimpleNamespace(get_data=read, save_data=lambda key, value: data.__setitem__(key, copy.deepcopy(value)))
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda n: archive.record_rename_failure(plugin, str(n % 4), "name"), range(24)))
    result = archive.get_rename_retry_state(plugin)
    assert len(result) == 4
    assert all(item["fail_count"] == 6 and item["archived"] for item in result.values())
    archive.restore_rename_archive(plugin, "0")
    archive.delete_rename_archive(plugin, "1")
    assert archive.get_rename_retry_state(plugin)["0"]["fail_count"] == 0
    assert "1" not in archive.get_rename_retry_state(plugin)


def test_slow_monitor_hands_off_after_stop_timeout(monkeypatch):
    """慢扫描退出后仅接续一个新 worker，再次停用会取消接续请求。"""
    entered, release = threading.Event(), threading.Event()

    class FirstWait:
        """让首轮立即扫描，其余等待遵循真实停止事件。"""
        def __init__(self):
            """保存首轮与停止状态。"""
            self.first = True
            self.event = threading.Event()

        def wait(self, timeout=None):
            """首轮跳过定时等待。"""
            if self.first:
                self.first = False
                return False
            return self.event.wait(timeout)

        def set(self):
            """设置停止信号。"""
            self.event.set()

        def is_set(self):
            """返回停止状态。"""
            return self.event.is_set()

    def scan():
        """模拟尚未返回的下载器请求。"""
        entered.set()
        assert release.wait(3)
        return {"active_sessions": 1}

    stop = FirstWait()
    runtime = SimpleNamespace(sessions={"a": SimpleNamespace(status=speed_worker.SESSION_ACTIVE)})
    plugin = SimpleNamespace(_scan_download_speed=scan, _speed_monitor_runtime=runtime,
                             _speed_monitor_worker_lock=threading.RLock(), _speed_monitor_stop_event=stop)
    monkeypatch.setattr(speed_worker, "is_speed_monitor_active", lambda p: True)
    worker = threading.Thread(target=speed_worker._speed_monitor_loop, args=(plugin, stop))
    plugin._speed_monitor_thread = worker
    worker.start()
    assert entered.wait(2)
    speed_worker.stop_speed_monitor_worker(plugin, join_timeout=0)
    assert not speed_worker.start_speed_monitor_worker_if_needed(plugin, runtime)
    starts = []
    monkeypatch.setattr(speed_worker, "start_speed_monitor_worker", lambda p: starts.append(p))
    release.set()
    worker.join(3)
    assert not worker.is_alive()
    assert starts == [plugin]
    speed_worker.stop_speed_monitor_worker(plugin, join_timeout=0)
    assert plugin._speed_monitor_restart_pending is False
