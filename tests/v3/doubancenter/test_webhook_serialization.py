"""并发播放事件必须串行处理且异常释放锁。"""

import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter.service import webhook


def test_busy_webhook_waits_and_delivers_distinct_events(monkeypatch):
    """两个不同媒体事件并发到达时，后者等待且最终执行一次。"""
    entered, release, attempted = threading.Event(), threading.Event(), threading.Event()
    calls = []
    plugin = SimpleNamespace(_enabled=True, _folio_enabled=True, _sync_lock=threading.Lock())

    def handler(_plugin, event, **kwargs):
        """让首个事件停在临界区，构造确定性的竞争。"""
        calls.append(event)
        if event == "first":
            entered.set()
            assert release.wait(3)

    def second():
        """第二个请求在首个尚未结束时尝试处理。"""
        attempted.set()
        webhook.handle_sync_log(plugin, SimpleNamespace(event_data="second"), played=True)

    monkeypatch.setattr(webhook.folio, "check_cookie_periodically", lambda p: None)
    monkeypatch.setattr(webhook.folio, "sync_log_handler", handler)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(webhook.handle_sync_log, plugin, SimpleNamespace(event_data="first"))
        try:
            assert entered.wait(3)
            later = executor.submit(second)
            assert attempted.wait(3)
        finally:
            release.set()
        first.result(timeout=3)
        later.result(timeout=3)
    assert calls == ["first", "second"]


def test_webhook_exception_releases_instance_lock(monkeypatch):
    """一次处理失败后后续事件仍可进入实例锁。"""
    plugin = SimpleNamespace(_enabled=True, _folio_enabled=True, _sync_lock=threading.Lock())
    monkeypatch.setattr(webhook.folio, "check_cookie_periodically", lambda p: None)
    def fail(*args, **kwargs):
        """模拟豆瓣处理失败。"""
        raise RuntimeError("offline")
    monkeypatch.setattr(webhook.folio, "sync_log_handler", fail)
    with pytest.raises(RuntimeError):
        webhook.handle_sync_log(plugin, SimpleNamespace(event_data={}))
    assert not plugin._sync_lock.locked()
