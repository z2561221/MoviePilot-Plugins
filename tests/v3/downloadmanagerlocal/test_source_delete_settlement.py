"""源删除正常结束、旧记录身份和真实宿主精确写入回归。"""

import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.db.oper.downloadhistory import DownloadHistoryOper
from app.plugins.downloadmanagerlocal.adapter.sync_delete import (
    SyncDeleteAdapter,
    plain,
)
from app.plugins.downloadmanagerlocal.model.sync_delete import DeleteRejected
from app.plugins.downloadmanagerlocal.service import source_delete
from app.plugins.downloadmanagerlocal.service import sync_delete as service

_source = runpy.run_path(str(Path(__file__).with_name("test_source_delete.py")))
_logs = runpy.run_path(str(Path(__file__).with_name("test_sync_delete_logging.py")))
case, queued = _source["case"], _source["queued"]


def snapshot_case():
    plugin, adapter, event = case()
    event["source_records"] = source_delete.source_record_snapshot(adapter, "/downloads/A.mkv", "source")
    return plugin, adapter, event


def test_no_targets_finishes_normally_and_does_not_consume_pending_capacity(monkeypatch):
    plugin, adapter, event = snapshot_case()
    adapter.tasks.clear()
    runtime, job = queued(plugin, adapter, event)
    _logs["run_one_job"](monkeypatch, runtime, adapter)
    saved = runtime.jobs()[job["id"]]
    assert saved["state"] == "skipped" and saved["error"] == ""
    assert saved["download_records_done"] == [11]
    assert adapter.calls == [("download_record", 11)]
    runtime.stop.clear()
    with pytest.raises(DeleteRejected, match="不能重试"):
        runtime.submit(None, job_id=job["id"])
    assert runtime.submit(event) == job["id"]
    monkeypatch.setattr(service, "MAX_PENDING", 1)
    runtime.submit(dict(event, paths=["/downloads/B.mkv"]))


def test_legacy_event_does_not_capture_later_same_hash_records():
    plugin, adapter, event = case()
    adapter.tasks.clear()
    runtime, job = queued(plugin, adapter, event)
    runtime.execute(job, adapter)
    assert job["state"] == "skipped" and job["plan"]["download_records"] == []
    assert not adapter.calls


def test_recreated_file_still_blocks_no_target_plan():
    plugin, adapter, event = snapshot_case()
    adapter.tasks.clear()
    runtime, job = queued(plugin, adapter, event)
    adapter.put("local", "/downloads/A.mkv")
    with pytest.raises(DeleteRejected, match="新文件"):
        runtime.execute(job, adapter)
    assert not adapter.calls


def test_snapshot_query_error_is_a_real_failed_job(monkeypatch):
    plugin, adapter, _ = case()
    plugin._sync_delete_runtime = runtime = service.DeleteRuntime(plugin)
    adapter.download_files = lambda **_: (_ for _ in ()).throw(OSError("private endpoint"))
    monkeypatch.setattr(source_delete, "SyncDeleteAdapter", lambda *_: adapter)
    result = source_delete.receive_source_deleted(
        plugin, SimpleNamespace(event_data={"src": "/downloads/A.mkv", "hash": "source"}))
    assert result["accepted"]
    _logs["run_one_job"](monkeypatch, runtime, adapter)
    job = runtime.jobs()[result["job_id"]]
    assert job["state"] == "failed" and "快照读取失败：OSError" in job["error"]
    assert "private endpoint" not in job["error"] and not adapter.calls


def test_failure_updating_record_keeps_retry_stage_and_snapshot():
    plugin, adapter, event = snapshot_case()
    runtime, job = queued(plugin, adapter, event)
    mark = adapter.mark_download_record_deleted
    adapter.mark_download_record_deleted = lambda _: (_ for _ in ()).throw(DeleteRejected("记录暂不可写"))
    with pytest.raises(DeleteRejected, match="暂不可写"):
        runtime.execute(job, adapter)
    assert job["download_records_done"] == [] and not adapter.tasks
    adapter.mark_download_record_deleted = mark
    runtime.execute(job, adapter)
    assert job["state"] == "completed" and job["download_records_done"] == [11]
    assert len([call for call in adapter.calls if call[0] == "remove"]) == 2


def test_only_receipt_time_ids_are_updated_after_new_same_path_row_appears():
    plugin, adapter, event = snapshot_case()
    runtime, job = queued(plugin, adapter, event)
    original = adapter.download_files
    adapter.download_files = lambda **kwargs: original(**kwargs) + [
        {"id": 12, "fullpath": "/downloads/A.mkv", "download_hash": "source", "downloader": "QB1", "state": 1}]
    runtime.execute(job, adapter)
    assert job["download_records_done"] == [11]
    assert [call for call in adapter.calls if call[0] == "download_record"] == [("download_record", 11)]


def test_real_oper_updates_old_id_and_preserves_new_same_hash_path():
    path = "/downloads/settlement-test/A.mkv"
    oper = DownloadHistoryOper()
    payload = {"fullpath": path, "download_hash": "same-hash", "downloader": "QB", "savepath": "/downloads", "state": 1}
    oper.add_files([dict(payload)])
    old = plain(oper.get_files_by_fullpath(path)[0])
    oper.add_files([dict(payload)])
    adapter = object.__new__(SyncDeleteAdapter)
    adapter.check_write = lambda: None
    adapter.mark_download_record_deleted(old)
    rows = [plain(row) for row in oper.get_files_by_fullpath(path)]
    assert {row["id"]: row["state"] for row in rows} == {old["id"]: 0, max(row["id"] for row in rows): 1}
    adapter.mark_download_record_deleted(old)
    assert [plain(row)["state"] for row in oper.get_files_by_fullpath(path)].count(1) == 1


def test_real_oper_rejects_changed_record_identity_before_write():
    path = "/downloads/settlement-test/changed.mkv"
    oper = DownloadHistoryOper()
    oper.add_files([{"fullpath": path, "download_hash": "new-hash", "downloader": "QB", "state": 1}])
    old = plain(oper.get_files_by_fullpath(path)[0])
    old["download_hash"] = "old-hash"
    adapter = object.__new__(SyncDeleteAdapter)
    adapter.check_write = lambda: None
    with pytest.raises(DeleteRejected, match="身份"):
        adapter.mark_download_record_deleted(old)
    assert plain(oper.get_files_by_fullpath(path)[0])["state"] == 1
