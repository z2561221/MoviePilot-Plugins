"""缓存释放审查只使用内存依赖，不访问真实媒体库或业务队列。"""

import ast
import inspect
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter import DoubanCenter
from app.plugins.doubancenter.adapter import folio_library
from app.plugins.doubancenter.service import lifecycle


@pytest.mark.parametrize("stop_during_read", [False, True])
def test_season_cache_publication_respects_the_started_generation(monkeypatch, stop_during_read):
    plugin = object.__new__(DoubanCenter)
    lifecycle.start(plugin)
    service = SimpleNamespace(name="test", config=SimpleNamespace(config={"host": "http://library.invalid/"}))
    monkeypatch.setattr(folio_library, "MediaServerHelper", lambda: SimpleNamespace(get_services=lambda **kwargs: {"test": service}))

    def find(*args):
        if stop_during_read:
            lifecycle.start(plugin)
        return service, {"Id": "series"}

    monkeypatch.setattr(folio_library, "_find_series", find)
    monkeypatch.setattr(folio_library, "_get_json", lambda *args: {
        "Items": [{"Id": "season", "Type": "Season", "SeriesId": "series", "IndexNumber": 2}], "TotalRecordCount": 1,
    })
    monkeypatch.setattr(folio_library, "_season_episodes", lambda *args: [
        {"IndexNumber": 1, "PremiereDate": "2026-01-01"},
    ])
    result = folio_library.load_season(plugin, {"media_source": "themoviedb", "media_id": "123", "season": 2})
    assert result["season"] == 2
    assert len(plugin._folio_library_season_cache) == (0 if stop_during_read else 1)


def _reader(monkeypatch, plugin, kind, io_hook=lambda: None):
    service = SimpleNamespace(name="test", config=SimpleNamespace(config={"host": "http://library.invalid/"}))
    monkeypatch.setattr(folio_library, "MediaServerHelper", lambda: SimpleNamespace(get_services=lambda **kwargs: {"test": service}))
    if kind == "season":
        def find(*args):
            io_hook()
            return service, {"Id": "series"}
        monkeypatch.setattr(folio_library, "_find_series", find)
        monkeypatch.setattr(folio_library, "_get_json", lambda *args: {
            "Items": [{"Id": "season", "Type": "Season", "SeriesId": "series", "IndexNumber": 2}], "TotalRecordCount": 1,
        })
        monkeypatch.setattr(folio_library, "_season_episodes", lambda *args: [{"IndexNumber": 1, "PremiereDate": "2026-01-01"}])
        return lambda: folio_library.load_season(plugin, {"media_source": "themoviedb", "media_id": "123", "season": 2})

    def lookup(*args):
        io_hook()
        return {"url": "http://library.invalid/poster", "reference": {"item_id": "movie"}}
    monkeypatch.setattr(folio_library, "_lookup_poster", lookup)
    monkeypatch.setattr(folio_library.SecurityUtils, "sign_url", lambda url: url)
    return lambda: folio_library.project_posters(plugin, {
        "movie": {"type": "movie", "media_source": "douban", "media_id": "1", "poster_path": "fallback"},
    })


def _publication_site(kind):
    """定位真实赋值行；兼容修复前后的实现，用普通线程trace确定性交错。"""
    publish = getattr(lifecycle, "publish_cache", None)
    if publish is not None:
        function = publish
        source, first = inspect.getsourcelines(function)
        tree = ast.parse("".join(source))
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "setattr")
    else:
        function = folio_library.load_season if kind == "season" else folio_library._project_posters
        source, first = inspect.getsourcelines(function)
        tree = ast.parse("".join(source))
        name = f"_folio_library_{kind}_cache"
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                    and any(isinstance(target, ast.Attribute) and target.attr == name for target in n.targets))
    return function.__code__, first + node.lineno - 1


@pytest.mark.parametrize("kind", ["season", "poster"])
def test_restart_at_final_cache_assignment_cannot_resurrect_old_container(monkeypatch, kind):
    plugin = object.__new__(DoubanCenter)
    lifecycle.start(plugin)
    old_event = plugin._run_stop
    read = _reader(monkeypatch, plugin, kind)
    code, line = _publication_site(kind)
    paused, release, restart_entered, restart_done = Event(), Event(), Event(), Event()

    def trace(frame, event, arg):
        if event == "line" and frame.f_code is code and frame.f_lineno == line:
            paused.set()
            assert release.wait(5)
        return trace

    def run_reader():
        sys.settrace(trace)
        try:
            return read()
        finally:
            sys.settrace(None)

    def restart():
        restart_entered.set()
        lifecycle.start(plugin)
        restart_done.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        reader = pool.submit(run_reader)
        try:
            assert paused.wait(5)
            reloader = pool.submit(restart)
            assert restart_entered.wait(5)
            if hasattr(lifecycle, "publish_cache"):
                # 发布检查已通过且持有短锁；另一线程不能先清空然后被旧赋值覆盖。
                acquired = plugin._lifecycle_lock.acquire(blocking=False)
                if acquired:
                    plugin._lifecycle_lock.release()
                assert not acquired
                assert not restart_done.is_set()
            else:
                # 原实现无共同临界区：强制stop/start在最终赋值之前完整结束。
                assert restart_done.wait(5)
                assert getattr(plugin, f"_folio_library_{kind}_cache") == {}
        finally:
            release.set()
        reader.result(5)
        reloader.result(5)
    assert old_event.is_set()
    assert not plugin._run_stop.is_set()
    assert getattr(plugin, f"_folio_library_{kind}_cache") == {}


@pytest.mark.parametrize("kind", ["season", "poster"])
def test_restart_completes_while_media_io_is_still_pending(monkeypatch, kind):
    plugin = object.__new__(DoubanCenter)
    lifecycle.start(plugin)
    entered, release, restarted = Event(), Event(), Event()

    def pending_io():
        entered.set()
        assert release.wait(5)

    read = _reader(monkeypatch, plugin, kind, pending_io)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reader = pool.submit(read)
        try:
            assert entered.wait(5)
            def restart():
                lifecycle.start(plugin)
                restarted.set()
            reloader = pool.submit(restart)
            assert restarted.wait(5)
        finally:
            release.set()
        reader.result(5)
        reloader.result(5)
    assert getattr(plugin, f"_folio_library_{kind}_cache") == {}


@pytest.mark.parametrize("kind", ["season", "poster"])
def test_old_reader_cannot_replace_a_new_generation_cache(monkeypatch, kind):
    plugin = object.__new__(DoubanCenter)
    lifecycle.start(plugin)
    entered, release = Event(), Event()

    def pending_io():
        entered.set()
        assert release.wait(5)

    read = _reader(monkeypatch, plugin, kind, pending_io)
    field = f"_folio_library_{kind}_cache"
    fresh = {"new_generation": ("new", {})}
    with ThreadPoolExecutor(max_workers=1) as pool:
        reader = pool.submit(read)
        try:
            assert entered.wait(5)
            lifecycle.start(plugin)
            assert lifecycle.publish_cache(plugin, plugin._run_stop, field, fresh)
        finally:
            release.set()
        reader.result(5)
    assert getattr(plugin, field) is fresh
