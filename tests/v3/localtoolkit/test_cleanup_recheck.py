"""只读核验的四种去向、身份、批次与生命周期边界。"""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app import schemas
from app.plugins.localtoolkit import LocalToolkit
from app.plugins.localtoolkit.model.api import ToolkitRecheckData, ToolkitRecheckRequest
from app.plugins.localtoolkit.model.cleanup_recheck import CleanupReadError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from .test_cleanup_identity import make_adapter
from .test_cleanup_run import build_module
from .test_cleanup_verification import Response


def mark_errors(plugin):
    for item in plugin.data["library_cleanup_plan"]["items"]:
        item.update(last_error="媒体条目状态无法核验", attempts=2, last_attempt_at="previous-attempt", queued_at="")


def test_recheck_four_outcomes_without_deletion_scan_notifications_or_cooldown_change():
    module, plugin, adapter = build_module({key: [False] for key in ["ready", "absent", "changed", "unknown", "untouched"]})
    mark_errors(plugin)
    plan = plugin.data["library_cleanup_plan"]
    plan["items"][-1]["last_error"] = ""
    plan.update(last_cycle_at="2026-09-21T01:00:00+08:00", pending_cycle_at="pending", last_cycle={"success_count": 10})
    before = deepcopy(plan)
    adapter.preflight["absent"] = (False, None)
    adapter.inventory["changed"].favorite = True
    adapter.preflight["unknown"] = CleanupReadError("access_denied", "访问被拒绝", "检查用户权限")
    result = module.recheck_plan()
    assert result["success"] is False
    assert [result[k] for k in ("processed_count", "restored_count", "removed_count", "unknown_count")] == [4, 1, 2, 1]
    assert len(result["results"]) == 4
    after = plugin.data["library_cleanup_plan"]
    assert [item["movie_id"] for item in after["items"]] == ["ready", "unknown", "untouched"]
    assert after["items"][0]["last_error"] == ""
    assert after["items"][1]["recovery_hint"] == "检查用户权限"
    assert after["items"][1]["error_code"] == "access_denied"
    assert after["items"][-1] == before["items"][-1]
    for key in ("last_cycle_at", "pending_cycle_at", "last_cycle"):
        assert after[key] == before[key]
    assert all(item["attempts"] == 2 and item["last_attempt_at"] == "previous-attempt" for item in after["items"])
    assert not adapter.deleted and not adapter.checked and not adapter.scans and not plugin.notifiers
    assert module.get_cleanup_plan()["error_count"] == 1


def test_single_item_and_missing_key_never_expand_to_batch():
    module, plugin, adapter = build_module({"a": [False], "b": [False]})
    mark_errors(plugin)
    assert module.recheck_plan("emby:missing")["success"] is False
    assert not adapter.prechecked
    assert module.recheck_plan("emby:b")["restored_count"] == 1
    assert adapter.prechecked == [("b", "viewer")]
    assert plugin.data["library_cleanup_plan"]["items"][0]["last_error"]


@pytest.mark.parametrize("mode", ["fields", "identity", "network", "unknown"])
def test_unknown_states_keep_item_and_action(mode):
    module, plugin, adapter = build_module({"a": [False]})
    mark_errors(plugin)
    if mode == "fields":
        adapter.inventory["a"].favorite = None
    elif mode == "identity":
        adapter.preflight["a"] = (True, replace(adapter.inventory["a"], server="another-server"))
    elif mode == "network":
        adapter.preflight["a"] = TimeoutError("secret-raw-detail")
    else:
        adapter.preflight["a"] = (None, None)
    result = module.recheck_plan()
    assert result["unknown_count"] == 1
    assert result["results"][0]["action"]
    assert "secret-raw-detail" not in str(result)
    assert len(plugin.data["library_cleanup_plan"]["items"]) == 1
    assert not adapter.deleted


def test_batch_limit_rotates_errors_and_preserves_unchecked_entries():
    module, plugin, adapter = build_module({str(i): [False] for i in range(12)})
    mark_errors(plugin)
    adapter.preflight = dict.fromkeys(adapter.inventory, (None, None))
    assert module.recheck_plan()["pending_count"] == 2
    assert len(adapter.prechecked) == 10
    adapter.prechecked.clear()
    module.recheck_plan()
    assert [key for key, _ in adapter.prechecked[:2]] == ["10", "11"]


def test_busy_or_stopped_module_never_queries_or_changes_plan():
    module, plugin, adapter = build_module({"a": [False]})
    mark_errors(plugin)
    before = deepcopy(plugin.data)
    assert module._run_lock.acquire(blocking=False)
    try:
        assert module.recheck_plan()["busy"] is True
    finally:
        module._run_lock.release()
    module.stop()
    assert module.recheck_plan()["stopped"] is True
    assert plugin.data == before and not adapter.prechecked


def test_cancel_during_read_keeps_pending_item_and_commits_completed_item():
    module, plugin, adapter = build_module({"a": [False], "b": [False]})
    mark_errors(plugin)
    original = adapter.refresh_candidate

    def cancel_second(item, user, **kwargs):
        if item.movie_id == "b":
            module.stop()
        return original(item, user, **kwargs)

    adapter.refresh_candidate = cancel_second
    result = module.recheck_plan()
    assert result["stopped"] is True and result["processed_count"] == 1
    assert result["pending_count"] == 1
    assert not plugin.data["library_cleanup_plan"]["items"][0]["last_error"]
    assert plugin.data["library_cleanup_plan"]["items"][1]["last_error"]
    assert not adapter.deleted


def test_recheck_only_resolves_matching_read_alerts_without_notification():
    module, plugin, _adapter = build_module({"a": [False], "b": [False]})
    mark_errors(plugin)
    plugin.data["library_cleanup_alerts"] = {
        "cleanup": {"category": "precheck_unavailable", "active": True, "notified": True,
                    "message": "读取异常", "identities": ["emby:a", "emby:b"]},
        "scan": {"category": "network", "active": True, "message": "扫描失败"},
    }
    module.recheck_plan("emby:a")
    assert plugin.data["library_cleanup_alerts"]["cleanup"]["identities"] == ["emby:b"]
    module.recheck_plan("emby:b")
    assert set(plugin.data["library_cleanup_alerts"]) == {"scan"}
    plugin.data["library_cleanup_alerts"]["cleanup"] = {"category": "delete_failed", "active": True}
    module.recheck_plan("emby:b")
    assert plugin.data["library_cleanup_alerts"]["cleanup"]["active"] is True
    assert not plugin.notifiers


@pytest.mark.parametrize("status,code", [(401, "access_denied"), (403, "access_denied"), (500, "http_error")])
def test_http_diagnostics_keep_status_and_hide_response_credentials(status, code):
    module, plugin, _fake = build_module({"a": [False]}, selected_user="")
    mark_errors(plugin)
    adapter, _instance, _calls = make_adapter(Response(200, []))
    adapter._request_utils = lambda **_kw: SimpleNamespace(get_res=Mock(return_value=Response(status)))
    module.adapter = adapter
    result = module.recheck_plan()
    row = result["results"][0]
    assert row["error_code"] == code and str(status) in row["reason"]
    assert "test-only" not in str(result)
    adapter.delete_item.assert_not_called()


def test_invalid_selected_user_does_not_fallback_to_admin_in_recheck():
    module, plugin, _fake = build_module({"a": [False]}, selected_user="viewer")
    mark_errors(plugin)
    adapter, instance, calls = make_adapter(Response(200, [{"Name": "renamed", "Id": "admin-id"}]))
    module.adapter = adapter
    assert module.recheck_plan()["results"][0]["error_code"] == "connection_or_user"
    instance.get_user.assert_not_called()
    adapter.delete_item.assert_not_called()
    assert all(url.endswith("/Users") for url in calls)


def test_real_route_preserves_partial_failure_and_rejects_malformed_scope():
    module, plugin, adapter = build_module({"a": [False], "b": [False]})
    mark_errors(plugin)
    adapter.preflight["b"] = (None, None)
    instance = object.__new__(LocalToolkit)
    instance.library_cleanup = module
    app = FastAPI()
    route = next(route for route in instance.get_api() if route["path"].endswith("/recheck"))
    assert route["response_model"] == schemas.Response[ToolkitRecheckData]
    app.add_api_route("/recheck", route["endpoint"], methods=["POST"], response_model=route["response_model"])
    client = TestClient(app)
    for body in ({"queue_key": ""}, {"queue_key": " "}, {"queue_keey": "emby:a"}, {"queue_key": []}):
        assert client.post("/recheck", json=body).status_code == 422
    assert not adapter.prechecked
    response = client.post("/recheck", json={}).json()
    assert set(response) == {"success", "message", "data"}
    assert response["success"] is False and response["data"]["restored_count"] == 1
    assert len(response["data"]["results"]) == 2
    assert ToolkitRecheckRequest(queue_key="emby:a").queue_key == "emby:a"
