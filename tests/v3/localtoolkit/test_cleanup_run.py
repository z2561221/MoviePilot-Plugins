from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from localtoolkit.model.library_cleanup import CleanupCandidate
from localtoolkit.service.library_cleanup import LibraryCleanupModule


class FakePlugin:
    def __init__(self):
        self.data = {}
        self.notifiers = []

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
    def __init__(self, states, delete_results=None):
        self.states = deepcopy(states)
        self.delete_results = delete_results or {}
        self.deleted = []
        self.checked = []
        self.scans = 0

    def iter_candidates(self, _config):
        self.scans += 1
        created = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        return [
            CleanupCandidate(movie_id=key, title=f"电影 {key}", server="emby",
                             date_created=created, favorite=False, played=True)
            for key in self.states
        ]

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
        **module.get_default_config(), "auto_delete": True, "auto_delete_delay": 0,
        "selected_user": "viewer", **config,
    })
    return module, plugin, adapter


def test_deletion_is_verified_before_same_report_gets_final_status():
    module, plugin, adapter = build_module({"a": [False], "b": [False]})
    result = module.run_once()
    assert result["success"] is True
    assert adapter.deleted == ["a", "b"] and adapter.scans == 1
    assert adapter.checked == [("a", "viewer"), ("b", "viewer")]
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
    assert adapter.deleted == ["a", "b", "c"]
    assert [key for key, _ in adapter.checked] == ["a", "b", "c", "b", "c", "b", "c"]
    verification = plugin.data["library_cleanup_result"]["deletion"]["verification"]
    assert [verification[key] for key in ["removed_count", "remaining_count", "unknown_count"]] == [1, 1, 1]
    assert plugin.data["tool_history"][0]["status"] == "failed"
    assert "✅ 本轮删除完毕" not in plugin.notifiers[0].calls[-1][2]
    assert module.last_error == "本轮清理未全部完成"


def test_bounded_recheck_handles_media_server_delay_without_redeleting():
    module, plugin, adapter = build_module({"a": [True, False], "b": [False]})
    assert module.run_once()["success"] is True
    assert adapter.deleted == ["a", "b"]
    assert [key for key, _ in adapter.checked] == ["a", "b", "a"]
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
    assert adapter.deleted == ["a", "b"]
    assert plugin.data["library_cleanup_result"]["deletion"]["verification"]["unknown_count"] == 1
    assert plugin.notifiers[0].calls[-1][0] == "finish"


@pytest.mark.parametrize("config", [
    {"auto_delete": False}, {"dry_run": True}, {"auto_delete_max_count": 1},
])
def test_check_dry_run_and_limit_guards_never_delete_or_verify(config):
    module, plugin, adapter = build_module({"a": [False], "b": [False]}, **config)
    module.run_once()
    assert not adapter.deleted and not adapter.checked
    assert [call[0] for call in plugin.notifiers[0].calls] == ["finish"]
    assert "✅ 本轮删除完毕" not in plugin.notifiers[0].calls[0][2]


def test_empty_inventory_sends_one_check_report_without_deletion():
    module, plugin, adapter = build_module({})
    assert module.run_once()["success"] is True
    assert not adapter.deleted and not adapter.checked
    assert len(plugin.notifiers) == 1 and len(plugin.notifiers[0].calls) == 1


def test_notifications_off_does_not_disable_verification():
    module, plugin, adapter = build_module({"a": [False]}, notify=False)
    assert module.run_once()["success"] is True
    assert adapter.checked and not plugin.notifiers


def test_overlapping_run_cannot_delete_twice_or_replace_active_report():
    module, plugin, adapter = build_module({"a": [False]})
    module._run_lock.acquire()
    try:
        assert module.run_once()["success"] is False
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
