"""跨重载锁、停止中的批次及分页取消回归。"""

from copy import deepcopy
from threading import Event, Thread

from app.plugins.localtoolkit.service.cleanup_execution import CleanupExecution
from app.plugins.localtoolkit.service.library_cleanup import LibraryCleanupModule

from .test_cleanup_identity import make_adapter
from .test_cleanup_run import FakeNotifier, FakePlugin, build_module
from .test_cleanup_verification import Response


def test_different_objects_share_os_lock_but_distinct_instances_do_not(tmp_path):
    old = CleanupExecution(tmp_path / "first")
    replacement = CleanupExecution(tmp_path / "first")
    other = CleanupExecution(tmp_path / "second")
    assert old.acquire(False)
    try:
        assert not replacement.acquire(False)
        assert other.acquire(False)
        other.release()
    finally:
        old.release()
    assert old.path.exists()
    assert replacement.acquire(False)
    replacement.release()


def test_cancelled_lock_waiter_exits_without_waiting_for_owner(tmp_path):
    owner, waiter = CleanupExecution(tmp_path), CleanupExecution(tmp_path)
    assert owner.acquire(False)
    result = []
    thread = Thread(target=lambda: result.append(waiter.acquire()))
    thread.start()
    waiter.cancel()
    thread.join(1)
    owner.release()
    assert not thread.is_alive() and result == [False]


def test_reload_cannot_clear_or_duplicate_inflight_batch_and_old_task_stops():
    old, plugin, adapter = build_module({"a": [False], "b": [False]}, auto_delete_delay=300,
                                       cycle_cooldown_minutes=0, cleanup_notify=False)
    old_config = deepcopy(old.config)
    deleting, release_delete = Event(), Event()
    results = []

    def delete(item):
        adapter.deleted.append(item.movie_id)
        deleting.set()
        assert release_delete.wait(3)
        return True

    adapter.delete_item = delete
    thread = Thread(target=lambda: results.append(old.run_once()))
    thread.start()
    try:
        assert deleting.wait(3)
        old.stop()
        replacement_plugin = FakePlugin(plugin.get_data_path())
        replacement_plugin.data = plugin.data
        replacement = LibraryCleanupModule(replacement_plugin, adapter, FakeNotifier)
        replacement.load_config(old_config)
        assert replacement.run_once()["busy"]
        assert replacement.scan_plan()["busy"]
        assert replacement.clear_cleanup_plan()["success"] is False
    finally:
        release_delete.set()
        thread.join(3)
    assert not thread.is_alive()
    assert adapter.deleted == ["a"]
    assert results[0]["stopped"] and results[0]["unprocessed_count"] == 1
    items = {item["movie_id"]: item for item in plugin.data["library_cleanup_plan"]["items"]}
    assert items["a"]["attempts"] == 1 and items["b"]["attempts"] == 0
    assert replacement.clear_cleanup_plan()["success"]
    assert old.run_once()["stopped"] and not plugin.data["library_cleanup_plan"]["items"]


def test_stop_interrupts_long_delete_interval():
    module, _plugin, adapter = build_module({"a": [False], "b": [False]}, auto_delete_delay=300,
                                            cleanup_notify=False)
    first_deleted = Event()
    original = adapter.delete_item

    def delete(item):
        result = original(item)
        first_deleted.set()
        return result

    adapter.delete_item = delete
    results = []
    thread = Thread(target=lambda: results.append(module.run_once()))
    thread.start()
    assert first_deleted.wait(3)
    module.stop()
    thread.join(1)
    assert not thread.is_alive() and adapter.deleted == ["a"]
    assert results[0]["stopped"]


def test_stopped_paginated_scan_preserves_old_plan_without_failure_notice():
    module, plugin, _fake = build_module({"a": [False]}, selected_user="", scan_notify=True)
    original = deepcopy(plugin.data["library_cleanup_plan"])
    adapter, _instance, _calls = make_adapter(Response(200, []))
    adapter.chain.librarys.return_value = [{"Id": "movies"}]
    requests = []

    def get_page(_url, params):
        requests.append(params["StartIndex"])
        module.stop()
        return Response(200, {"Items": [{"Id": "a"}], "TotalRecordCount": 2})

    adapter._request_utils = lambda **_kw: type("HTTP", (), {"get_res": staticmethod(get_page)})()
    module.adapter = adapter
    assert module.scan_plan()["stopped"]
    assert requests == [0]
    assert plugin.data["library_cleanup_plan"] == original and not plugin.notifiers
