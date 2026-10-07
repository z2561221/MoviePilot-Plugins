"""父级剧集缓存的容量、过期、引用释放和停止边界。"""

import gc
import weakref
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter import DoubanCenter
from app.plugins.doubancenter.service import folio, lifecycle
from app.schemas.types import MediaSource


@pytest.fixture
def cache_case(monkeypatch):
    """创建可控时钟和无网络媒体库替身。"""
    plugin = object.__new__(DoubanCenter)
    plugin._scheduler = None
    lifecycle.start(plugin)
    clock, calls, refs = [100.0], [], []

    class Media:
        """可弱引用的模拟媒体对象。"""

    def iteminfo(server, item_id):
        """记录查询并返回仅测试所需的父级资料。"""
        calls.append((server, item_id))
        item = Media()
        item.title, item.year = "合成剧集", "2026"
        item.media_source, item.media_id = MediaSource.TMDB, item_id
        refs.append(weakref.ref(item))
        return item

    monkeypatch.setattr(folio, "MediaServerChain", lambda: SimpleNamespace(iteminfo=iteminfo))
    monkeypatch.setattr(folio, "MediaServerHelper", lambda: SimpleNamespace(get_services=lambda: {}))
    monkeypatch.setattr(folio, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    return plugin, clock, calls, refs


def event(number):
    """创建不含真实媒体资料的播放事件。"""
    return SimpleNamespace(item_id=str(number), server_name="Fake", item_path="", json_object={})


def test_series_cache_is_bounded_and_releases_media_objects(cache_case):
    """缓存只保留精简字段，不能持有完整媒体对象或无限增长。"""
    plugin, _, _, refs = cache_case
    for number in range(1, 1001):
        assert folio._series_context(plugin, event(number))["media_id"] == str(number)
    gc.collect()
    assert len(plugin._folio_series_cache) == folio.FOLIO_SERIES_CACHE_LIMIT
    assert all(ref() is None for ref in refs)
    plugin.stop_service()
    assert not plugin._folio_series_cache


def test_series_cache_expires_and_reuses_live_entry(cache_case):
    """过期前复用同一身份，过期后重新查询且清除旧条目。"""
    plugin, clock, calls, _ = cache_case
    folio._series_context(plugin, event(1))
    folio._series_context(plugin, event(1))
    assert len(calls) == 1
    clock[0] += folio.FOLIO_SERIES_CACHE_SECONDS + 1
    folio._series_context(plugin, event(2))
    assert len(plugin._folio_series_cache) == 1
    folio._series_context(plugin, event(1))
    assert len(calls) == 3


def test_inflight_series_read_cannot_restore_cache_after_stop(cache_case, monkeypatch):
    """停用和重建代次后，旧查询不得重新挂接结果缓存。"""
    plugin, _, _, _ = cache_case

    def stop_during_read(**kwargs):
        """模拟网络等待期间发生停止及重新初始化。"""
        plugin.stop_service()
        lifecycle.start(plugin)
        return SimpleNamespace(title="旧结果", year="2026")

    monkeypatch.setattr(folio, "MediaServerChain", lambda: SimpleNamespace(iteminfo=stop_during_read))
    with pytest.raises(lifecycle.RunStopped):
        folio._series_context(plugin, event(1))
    assert not plugin._folio_series_cache
