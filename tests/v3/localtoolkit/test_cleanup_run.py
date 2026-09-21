from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from app.plugins.localtoolkit.model.library_cleanup import CleanupCandidate
from app.plugins.localtoolkit.service.library_cleanup import LibraryCleanupModule


class FakePlugin:
    def __init__(self, data_path=None):
        self.data = {}
        self.notifiers = []
        self._temporary = TemporaryDirectory(prefix="localtoolkit-test-") if data_path is None else None
        self._data_path = Path(self._temporary.name if self._temporary else data_path)

    def get_data_path(self):
        return self._data_path

    def get_data(self, key):
        return deepcopy(self.data.get(key))

    def save_data(self, key, value):
        self.data[key] = deepcopy(value)


class FakeNotifier:
    def __init__(self, plugin):
        self.calls = []
        plugin.notifiers.append(self)

    def start(self, title, text):
        self.calls.append(("start", title, text))

    def update(self, title, text):
        self.calls.append(("update", title, text))

    def finish(self, title, text):
        self.calls.append(("finish", title, text))
        return True

    def to_dict(self):
        return {"updated": True, "receipts": [{"message_id": 41, "chat_id": 99, "source": "TG"}]}


class FakeMediaServer:
    def user_scope(self, check_cancel=None):
        return nullcontext()

    def __init__(self, states, delete_results=None):
        self.states = deepcopy(states)
        self.delete_results = delete_results or {}
        self.deleted = []
        self.checked = []
        self.scans = 0
        self.prechecked = []
        self.preflight = {}
        created = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        self.inventory = {
            key: CleanupCandidate(movie_id=key, title=f"电影 {key}", server="emby", library_id="movies",
                                  date_created=created, favorite=False, played=True)
            for key in self.states
        }

    def iter_candidates(self, _config):
        self.scans += 1
        return [deepcopy(item) for key, item in self.inventory.items() if key not in self.deleted]

    def refresh_candidate(self, item, user, *, diagnose=False):
        """独立模拟删除前读取，删除后状态由 states 控制。"""
        self.prechecked.append((item.movie_id, user))
        if item.movie_id in self.preflight:
            value = self.preflight[item.movie_id]
            if isinstance(value, Exception):
                raise value
            return value
        return True, deepcopy(self.inventory[item.movie_id])

    def delete_item(self, item):
        self.deleted.append(item.movie_id)
        result = self.delete_results.get(item.movie_id, True)
        if isinstance(result, Exception):
            raise result
        return result

    def item_exists(self, item, user):
        self.checked.append((item.movie_id, user))
        values = self.states[item.movie_id]
        value = values.pop(0) if len(values) > 1 else values[0]
        if isinstance(value, Exception):
            raise value
        return value


def build_module(states, *, delete_results=None, **config):
    plugin = FakePlugin()
    adapter = FakeMediaServer(states, delete_results)
    module = LibraryCleanupModule(plugin, adapter, FakeNotifier)
    module.verification_delay = 0
    module.load_config({
        "auto_delete": True, "auto_delete_delay": 0,
        "selected_user": "viewer", **config,
    })
    plugin.data["library_cleanup_plan"] = {"version": 1, "items": [
        {**item.to_dict(), "queue_key": f"emby:{item.movie_id}", "attempts": 0}
        for item in adapter.inventory.values()
    ]}
    return module, plugin, adapter


def test_deletion_is_verified_before_same_report_gets_final_status():
    module, plugin, adapter = build_module({"a": [False], "b": [False]})
    result = module.run_once()
    assert result["success"] is True
    assert adapter.deleted == ["b", "a"] and adapter.scans == 0
    assert adapter.prechecked == [("b", "viewer"), ("a", "viewer")]
    assert adapter.checked == [("b", "viewer"), ("a", "viewer")]
    assert len(plugin.notifiers) == 1
    calls = plugin.notifiers[0].calls
    assert [call[0] for call in calls] == ["start", "update", "finish"]
    assert "正在清理" in calls[0][2] and "正在复核" in calls[1][2]
    assert "✅ 本轮删除完毕" in calls[2][2]
    assert plugin.data["library_cleanup_result"]["deletion"]["verification"]["removed_count"] == 2
    assert plugin.data["tool_history"][0]["status"] == "success"


def test_api_success_does_not_hide_remaining_or_unknown_items():
    module, plugin, adapter = build_module({"a": [False], "b": [True], "c": [None]})
    result = module.run_once()
    assert result["success"] is False
    assert adapter.deleted == ["c", "b", "a"]
    assert [key for key, _ in adapter.checked] == ["c", "b", "a", "c", "b", "c", "b"]
    verification = plugin.data["library_cleanup_result"]["deletion"]["verification"]
    assert [verification[key] for key in ["removed_count", "remaining_count", "unknown_count"]] == [1, 1, 1]
    assert plugin.data["tool_history"][0]["status"] == "failed"
    assert "✅ 本轮删除完毕" not in plugin.notifiers[0].calls[-1][2]
    assert module.last_error == "本轮清理未全部完成"


def test_bounded_recheck_handles_media_server_delay_without_redeleting():
    module, plugin, adapter = build_module({"a": [True, False], "b": [False]})
    assert module.run_once()["success"] is True
    assert adapter.deleted == ["b", "a"]
    assert [key for key, _ in adapter.checked] == ["b", "a", "a"]
    assert plugin.data["library_cleanup_result"]["deletion"]["verification"]["complete"]


def test_request_failure_can_still_be_confirmed_removed_by_readback():
    module, plugin, adapter = build_module({"a": [False]}, delete_results={"a": False})
    assert module.run_once()["success"] is True
    deletion = plugin.data["library_cleanup_result"]["deletion"]
    assert deletion["fail_count"] == 1 and deletion["verification"]["removed_count"] == 1
    assert adapter.deleted == ["a"]


def test_delete_and_check_exceptions_do_not_skip_final_report_or_later_items():
    module, plugin, adapter = build_module(
        {"a": [TimeoutError("check failed")], "b": [False]},
        delete_results={"a": RuntimeError("delete failed")},
    )
    assert module.run_once()["success"] is False
    assert adapter.deleted == ["b", "a"]
    assert plugin.data["library_cleanup_result"]["deletion"]["verification"]["unknown_count"] == 1
    assert plugin.notifiers[0].calls[-1][0] == "finish"


@pytest.mark.parametrize("config", [
    {"auto_delete": False}, {"dry_run": True},
])
def test_check_dry_run_and_limit_guards_never_delete_or_verify(config):
    module, plugin, adapter = build_module({"a": [False], "b": [False]}, **config)
    module.run_once()
    assert not adapter.deleted and not adapter.checked
    assert not adapter.prechecked and not adapter.scans and not plugin.notifiers


def test_cleanup_plan_processes_configured_quantity_first_and_respects_cooldown():
    states = {str(index): [False] for index in range(15)}
    module, plugin, adapter = build_module(states, auto_delete_max_count=12)

    first = module.run_once()

    assert first["success"] is True
    assert adapter.deleted == [str(index) for index in range(14, 2, -1)]
    assert [item["movie_id"] for item in plugin.data["library_cleanup_plan"]["items"]] == ["0", "1", "2"]

    second = module.run_once()

    assert second["success"] is True
    assert second["cooldown"] is True
    assert adapter.deleted == [str(index) for index in range(14, 2, -1)]
    assert not adapter.scans and len(adapter.prechecked) == 12


def test_cleanup_plan_retains_failed_items_with_attempt_metadata():
    states = {"a": [True], "b": [True]}
    module, plugin, adapter = build_module(states, delete_results={"a": False, "b": False}, cycle_cooldown_minutes=0)

    result = module.run_once()

    assert result["success"] is False
    assert adapter.deleted == ["b", "a"]
    plan_items = plugin.data["library_cleanup_plan"]["items"]
    assert [item["movie_id"] for item in plan_items] == ["a", "b"]
    assert [item["attempts"] for item in plan_items] == [1, 1]
    assert all(item["last_error"] for item in plan_items)


def test_empty_plan_is_quiet_without_scanning_or_deletion():
    module, plugin, adapter = build_module({})
    assert module.run_once()["success"] is True
    assert not adapter.deleted and not adapter.checked
    assert not plugin.notifiers and not adapter.scans and not adapter.prechecked


def test_notifications_off_does_not_disable_verification():
    module, plugin, adapter = build_module({"a": [False]}, notify=False)
    assert module.run_once()["success"] is True
    assert adapter.checked and not plugin.notifiers


def test_overlapping_run_cannot_delete_twice_or_replace_active_report():
    module, plugin, adapter = build_module({"a": [False]})
    module._run_lock.acquire()
    try:
        assert module.run_once()["busy"] is True
        assert not adapter.deleted and not plugin.notifiers and not adapter.scans
    finally:
        module._run_lock.release()
    assert module.run_once()["success"] is True


def test_report_update_failure_is_recorded_separately_from_verified_deletion():
    class FailingNotifier(FakeNotifier):
        def finish(self, title, text):
            super().finish(title, text)
            return False

        def to_dict(self):
            return {"updated": False}

    module, plugin, _adapter = build_module({"a": [False]})
    module._notifier_factory = FailingNotifier
    result = module.run_once()
    assert result["success"] is True and "清理报告更新失败" in result["summary"]
    assert module.last_error == "清理报告更新失败"
    assert plugin.data["library_cleanup_result"]["report"]["updated"] is False
    assert plugin.data["library_cleanup_result"]["deletion"]["verification"]["complete"] is True
