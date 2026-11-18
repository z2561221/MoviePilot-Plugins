"""忽略仅修改未开始的记录；权限、并发及失败证据均保留。"""

from copy import deepcopy
from threading import Event, Thread
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.controller import sync_delete as controller
from app.plugins.downloadmanagerlocal.model.sync_delete import (
    BLOCKS_KEY,
    JOBS_KEY,
    DeleteRejected,
)
from app.plugins.downloadmanagerlocal.model.sync_delete_review import review_revision
from app.plugins.downloadmanagerlocal.service.coordination import operation_lock
from app.plugins.downloadmanagerlocal.storage.sync_delete_jobs import DeleteJobStore
from app.sdk.security import verify_token
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.v3.downloadmanagerlocal.test_sync_delete import Plugin


def failed_job(job_id="old"):
    """模拟无当前执行快照的旧事件，不能据错误文案宣称已成功删除。"""
    return {"id": job_id, "state": "failed", "event_key": job_id,
            "event": {"name": "旧媒体", "paths": ["/emby/old.strm"]},
            "plan": None, "error": "关联任务已不存在，无需删除", "updated_at": 1,
            "records_done": [], "sources_marked": []}


def fixture(job=None, *, admin=True):
    """调用真实HTTP处理函数，存储与下载器隔离。"""
    plugin = Plugin()
    plugin.data[JOBS_KEY] = {"old": deepcopy(job or failed_job())}
    app = FastAPI()
    routes = controller.routes(plugin)
    app.dependency_overrides[verify_token] = lambda: SimpleNamespace(super_user=admin, username="测试管理员")
    for route in routes:
        app.add_api_route(**{key: value for key, value in route.items() if key != "auth"})
    return plugin, TestClient(app)


def test_history_can_filter_before_paging_and_never_writes_old_records():
    """大量已完成项不能挤掉待处理筛选，读取不写回review投影。"""
    plugin = Plugin()
    jobs = {str(index): {**failed_job(str(index)), "updated_at": index + 2, "state": "completed"}
            for index in range(40)}
    jobs["old"] = failed_job()
    jobs["closed"] = {**failed_job("closed"), "state": "dismissed"}
    plugin.data[JOBS_KEY] = jobs
    before = deepcopy(plugin.data)
    result = controller.history(plugin, page=1, page_size=1, pending_only=True)
    assert result.total == 1 and result.items[0]["id"] == "old"
    review = result.items[0]["review"]
    assert review["dismiss_allowed"] and not review["retry_allowed"]
    assert review["retry_reason"] and review["revision"] == review_revision(jobs["old"])
    assert plugin.data == before


@pytest.mark.parametrize("custom_reason", [None, "已核实，放弃旧清理"])
def test_admin_can_ignore_without_reason_and_legacy_request_keeps_custom_reason(custom_reason):
    """直接忽略默认记录说明，旧请求兼容；原错误、历史及其它保护保留。"""
    plugin, client = fixture()
    plugin._enabled = False
    plugin.data[BLOCKS_KEY] = {"other": {"job_id": "other-job", "identity": ["hash", 1, "/downloads"]}}
    original = deepcopy(plugin.data)
    with client:
        row = client.get("/sync_delete/history?pending_only=true").json()["items"][0]
        payload = {"job_id": "old", "expected_revision": row["review"]["revision"]}
        if custom_reason is not None:
            payload["reason"] = custom_reason
        result = client.post("/sync_delete/dismiss", json=payload)
        assert result.json()["success"] is True
        assert result.json()["data"] == {"job_id": "old", "state": "dismissed"}
        assert client.get("/sync_delete/history?pending_only=true").json()["total"] == 0
        completed = client.get("/sync_delete/history").json()["items"][0]
    assert completed["error"] == original[JOBS_KEY]["old"]["error"]
    assert completed["resolution"]["reason"] == (custom_reason or "用户忽略")
    assert completed["resolution"]["actor"] == "测试管理员"
    assert completed["plan"] is None and completed["records_done"] == []
    assert not completed["review"]["dismiss_allowed"]
    assert plugin.data[BLOCKS_KEY] == original[BLOCKS_KEY]
    assert plugin.data[JOBS_KEY] == original[JOBS_KEY]
    assert plugin.data["QB1-source"] == original["QB1-source"]


@pytest.mark.parametrize("change", [
    {"state": "running"}, {"state": "queued"}, {"state": "completed"},
    {"plan": {}}, {"records_done": [1]}, {"sources_marked": ["/downloads/old"]},
    {"download_records_done": [2]}, {"entities_complete": True},
])
def test_running_planned_or_partially_executed_job_cannot_be_dismissed(change):
    plugin = Plugin()
    job = {**failed_job(), **change}
    plugin.data[JOBS_KEY] = {"old": job}
    before = deepcopy(plugin.data)
    with pytest.raises(DeleteRejected):
        DeleteJobStore(plugin).dismiss("old", review_revision(job), "放弃", "管理员")
    assert plugin.data == before


@pytest.mark.parametrize("blocks", [{"own": {"job_id": "old"}}, {"bad": "invalid"}, []])
def test_protected_or_unreadable_protection_job_cannot_be_dismissed(blocks):
    plugin, client = fixture()
    plugin.data[BLOCKS_KEY] = blocks
    before = deepcopy(plugin.data)
    with client:
        result = client.post("/sync_delete/dismiss", json={"job_id": "old",
            "expected_revision": review_revision(failed_job()), "reason": "结束"})
    assert result.json()["success"] is False
    assert plugin.data == before


def test_ordinary_user_cannot_end_a_record_and_revision_drift_requires_reconfirmation():
    plugin, client = fixture(admin=False)
    before = deepcopy(plugin.data)
    payload = {"job_id": "old", "expected_revision": review_revision(failed_job()), "reason": "结束"}
    with client:
        assert client.post("/sync_delete/dismiss", json=payload).status_code == 403
    assert plugin.data == before
    plugin, client = fixture()
    plugin.data[JOBS_KEY]["old"]["error"] = "状态已变化"
    before = deepcopy(plugin.data)
    with client:
        result = client.post("/sync_delete/dismiss", json=payload).json()
    assert result["success"] is False and "已变化" in result["message"]
    assert plugin.data == before


def test_busy_operation_and_unconfirmed_storage_do_not_report_success():
    plugin, client = fixture()
    lock = operation_lock(plugin)
    acquired, release = Event(), Event()
    def hold():
        with lock:
            acquired.set()
            release.wait(5)
    thread = Thread(target=hold)
    thread.start()
    assert acquired.wait(2)
    payload = {"job_id": "old", "expected_revision": review_revision(failed_job()), "reason": "结束"}
    before = deepcopy(plugin.data)
    try:
        with client:
            result = client.post("/sync_delete/dismiss", json=payload).json()
        assert result["success"] is False and "正在处理" in result["message"]
        assert plugin.data == before
    finally:
        release.set()
        thread.join(2)
    original_save = plugin.save_data
    def discard_detail(key, value):
        if not key.startswith("sync_delete_job_record_"):
            original_save(key, value)
    plugin.save_data = discard_detail
    with client:
        result = client.post("/sync_delete/dismiss", json=payload).json()
    assert result["success"] is False and "保存未确认" in result["message"]
