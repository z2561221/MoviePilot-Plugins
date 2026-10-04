"""停止、重载和等锁期间的任务不得继续产生副作用。"""

import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter import DoubanCenter
from app.plugins.doubancenter.service import lifecycle, rank_pipeline, subscription, webhook
from app.plugins.doubancenter.storage import records
from app.schemas.types import MediaSource, MediaType


def make_plugin():
    """只创建内存运行状态，不启动宿主链和真实调度器。"""
    plugin = object.__new__(DoubanCenter)
    plugin._enabled = True
    plugin._folio_enabled = True
    plugin._scheduler = None
    plugin._sync_lock = threading.Lock()
    lifecycle.start(plugin)
    return plugin


@pytest.mark.parametrize("restart", [False, True])
def test_refresh_in_flight_cannot_subscribe_after_stop(monkeypatch, restart):
    """RSS 在途时停止，旧快照返回后禁止进入订阅；重启也不能复活旧任务。"""
    plugin = make_plugin()
    entered, release = threading.Event(), threading.Event()
    calls = []

    def refresh(*args, **kwargs):
        """构造已经发出但尚未返回的外部读取。"""
        entered.set()
        assert release.wait(3)
        return {}, {}

    monkeypatch.setattr(rank_pipeline, "_subscription_limit_by_rank", lambda p: {})
    monkeypatch.setattr(rank_pipeline, "refresh_rank_data", refresh)
    monkeypatch.setattr(rank_pipeline, "subscribe_to_rank_snapshots", lambda *a: calls.append("submit"))
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(rank_pipeline.run_scheduled, plugin)
        try:
            assert entered.wait(3)
            plugin.stop_service()
            plugin.stop_service()
            if restart:
                lifecycle.start(plugin)
        finally:
            release.set()
        future.result(timeout=3)
    assert calls == []


def test_old_registered_job_and_storage_are_invalid_after_restart():
    """停止既作废排队回调，也禁止旧代次覆盖新存储，实例之间互不影响。"""
    plugin, other = make_plugin(), make_plugin()
    writes = []
    plugin.save_data = lambda *args: writes.append(args)
    old_job = lifecycle.bind(plugin, lambda: writes.append("old"))
    with lifecycle.scope(plugin):
        plugin.stop_service()
        lifecycle.start(plugin)
        with pytest.raises(lifecycle.RunStopped):
            records.write_dict(plugin, "data", {"old": True})
        lifecycle.checkpoint(other)
    old_job()
    records.write_dict(plugin, "data", {"new": True})
    assert writes == [("data", {"new": True})]


def test_stopped_webhook_leaves_busy_lock_without_waiting_for_holder(monkeypatch):
    """已经排队的事件及时响应停止，不等旧网络任务完成，也不处理事件。"""
    plugin = make_plugin()
    entered = threading.Event()
    calls = []
    original_checkpoint = lifecycle.checkpoint

    def checkpoint(current):
        """观测工作线程已经绑定旧运行代次。"""
        if threading.current_thread() is not threading.main_thread():
            entered.set()
        return original_checkpoint(current)

    monkeypatch.setattr(lifecycle, "checkpoint", checkpoint)
    monkeypatch.setattr(webhook.folio, "check_cookie_periodically", lambda p: calls.append("cookie"))
    monkeypatch.setattr(webhook.folio, "sync_log_handler", lambda *a, **kw: calls.append("write"))
    plugin._sync_lock.acquire()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(webhook.handle_sync_log, plugin, SimpleNamespace(event_data={}))
            assert entered.wait(3)
            plugin.stop_service()
            future.result(timeout=1)
    finally:
        plugin._sync_lock.release()
    assert calls == []


def test_stop_during_subscription_lookup_prevents_add(monkeypatch):
    """查重返回之前停止并重建代次，不允许旧任务继续创建订阅。"""
    plugin = make_plugin()
    calls = []
    media = SimpleNamespace(title="停止测试", year="2026", type=MediaType.TV,
                            media_source=MediaSource.TMDB, media_id="1", tmdb_id=1)

    def lookup(*args, **kwargs):
        """模拟查重等待期间发生重载。"""
        plugin.stop_service()
        lifecycle.start(plugin)
        return False

    monkeypatch.setattr(subscription, "is_existing_media", lookup)
    with pytest.raises(lifecycle.RunStopped):
        subscription.add_subscription(plugin, media, subscribe_chain_cls=lambda: SimpleNamespace(
            add=lambda **kw: calls.append(kw)))
    assert calls == []
