"""宿主先删记录再通知时，关联清理仍按文件和任务身份执行。"""

import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.model.sync_delete import (
    JOBS_KEY,
    DeleteRejected,
    event_key,
)
from app.plugins.downloadmanagerlocal.service import cleanup, source_delete
from app.plugins.downloadmanagerlocal.service import sync_delete as service

_fixtures = runpy.run_path(str(Path(__file__).with_name("test_sync_delete.py")))
Plugin, Adapter = _fixtures["Plugin"], _fixtures["Adapter"]


def case():
    plugin, adapter = Plugin(), Adapter()
    adapter.records = []  # 宿主已经提交整理记录删除，QB1源任务也不再存在。
    adapter.items.pop(("local", "/downloads/A.mkv"))
    event = {"channel": "download", "event": "downloadfile.deleted",
             "paths": ["/downloads/A.mkv"], "source_hash": "source",
             "source_downloader": "", "observed_at": 1000, "timestamp": ""}
    return plugin, adapter, event


def queued(plugin, adapter, event):
    runtime = service.DeleteRuntime(plugin)
    plugin._sync_delete_runtime = runtime
    plan = source_delete.build_source_plan(plugin, event, service.config_for(plugin), adapter)
    job_id = runtime.submit(event, plan=plan)
    return runtime, runtime.jobs()[job_id]


def test_committed_history_deletion_and_missing_qb1_still_remove_qb2_and_seeds():
    plugin, adapter, event = case()
    runtime, job = queued(plugin, adapter, event)
    runtime.execute(job, adapter)
    assert not adapter.tasks
    assert job["state"] == "completed"
    assert job["plan"]["records"] == [] and job["plan"]["cloud_files"] == []
    assert not any(call[0] in {"record", "mark", "file"} for call in adapter.calls)
    assert "QB1-source" not in plugin.data


def test_separate_target_copy_is_deleted_by_exact_file_not_by_whole_pack():
    plugin, adapter, event = case()
    adapter.put("local", "/seed", "dir")
    adapter.put("local", "/seed/A.mkv")
    adapter.source_root = lambda path: "/seed" if path.startswith("/seed/") else "/downloads"
    for task in adapter.tasks.values():
        task.update(save_path="/seed", files=["/seed/A.mkv"], identity=[task["id"], 100, "/seed"])
    runtime, job = queued(plugin, adapter, event)
    runtime.execute(job, adapter)
    assert not adapter.tasks
    assert ("local", "/seed/A.mkv") not in adapter.items
    assert [call for call in adapter.calls if call[0] == "file"] == [("file", "local", "/seed/A.mkv")]


def test_pack_remaining_episode_is_preserved_then_final_episode_can_remove_tasks():
    plugin, adapter, event = case()
    adapter.put("local", "/downloads/B.mkv")
    for task in adapter.tasks.values():
        task["files"].append("/downloads/B.mkv")
    runtime, job = queued(plugin, adapter, event)
    runtime.execute(job, adapter)
    assert len(adapter.tasks) == 2 and all(task["status"] == "paused" for task in job["plan"]["tasks"])
    assert not any(call[0] == "remove" for call in adapter.calls)
    adapter.items.pop(("local", "/downloads/B.mkv"))
    next_event = dict(event, paths=["/downloads/B.mkv"])
    plan = source_delete.build_source_plan(plugin, next_event, service.config_for(plugin), adapter)
    next_job_id = runtime.submit(next_event, plan=plan)
    next_job = runtime.jobs()[next_job_id]
    runtime.execute(next_job, adapter)
    assert not adapter.tasks


@pytest.mark.parametrize("change", ["recreated-task", "changed-files", "new-file", "new-history", "new-relation"])
def test_saved_plan_rejects_replacement_or_new_references_before_actions(change):
    plugin, adapter, event = case()
    runtime, job = queued(plugin, adapter, event)
    if change == "recreated-task":
        adapter.tasks[("QB2", "target")]["identity"][1] = 200
    elif change == "changed-files":
        adapter.tasks[("QB2", "target")]["files"].append("/downloads/C.mkv")
    elif change == "new-file":
        adapter.put("local", "/downloads/A.mkv")
    elif change == "new-history":
        adapter.records.append({"id": 2, "src": "/downloads/A.mkv", "dest": "/new/A.mkv"})
    else:
        plugin.data["QB1-source"]["to_download_id"] = "new-target"
    with pytest.raises(DeleteRejected):
        runtime.execute(job, adapter)
    assert not adapter.calls and len(adapter.tasks) == 2


def test_file_reappearing_after_pause_still_prevents_task_removal():
    plugin, adapter, event = case()
    runtime, job = queued(plugin, adapter, event)
    pause = adapter.pause
    def replace_after_pause(task):
        pause(task)
        adapter.put("local", "/downloads/A.mkv")
    adapter.pause = replace_after_pause
    with pytest.raises(DeleteRejected, match="新文件"):
        runtime.execute(job, adapter)
    assert not any(call[0] == "remove" for call in adapter.calls)


def test_new_task_added_after_event_is_not_selected_on_later_retry():
    plugin, adapter, event = case()
    adapter.tasks[("QB2", "target")]["identity"][1] = 1000
    with pytest.raises(DeleteRejected, match="新任务"):
        source_delete.build_source_plan(plugin, event, service.config_for(plugin), adapter)
    assert not adapter.calls


def test_real_event_entry_enqueues_snapshot_without_looking_up_deleted_destination(monkeypatch):
    plugin, adapter, _ = case()
    runtime = service.DeleteRuntime(plugin)
    plugin._sync_delete_runtime = runtime
    monkeypatch.setattr(source_delete, "SyncDeleteAdapter", lambda *_: adapter)
    notification = SimpleNamespace(event_data={"src": "/downloads/A.mkv", "hash": "source"})
    first = cleanup.handle_sync_delete_by_hash_event(plugin, notification)
    second = cleanup.handle_sync_delete_by_hash_event(plugin, notification)
    assert first["accepted"] and first == second
    assert len(plugin.data[JOBS_KEY]) == 1
    job = runtime.jobs()[first["job_id"]]
    assert job["plan"]["tasks"] and job["plan"]["channel"] == "download"
    runtime.execute(job, adapter)
    assert not adapter.tasks


def test_unrelated_source_event_does_not_fill_failure_queue(monkeypatch):
    plugin, adapter, _ = case()
    plugin.data = {}
    plugin._sync_delete_runtime = service.DeleteRuntime(plugin)
    monkeypatch.setattr(source_delete, "SyncDeleteAdapter", lambda *_: adapter)
    result = cleanup.handle_sync_delete_by_hash_event(
        plugin, SimpleNamespace(event_data={"src": "/downloads/A.mkv", "hash": "other"}))
    assert result["skipped"] and not plugin._sync_delete_runtime.jobs()


def test_duplicate_path_with_different_hash_is_not_deduplicated():
    _, _, event = case()
    assert event_key(event) != event_key(dict(event, source_hash="replacement"))


def test_source_plan_enforces_shared_file_limit_before_actions(monkeypatch):
    plugin, adapter, event = case()
    for task in adapter.tasks.values():
        task["files"].append("/downloads/B.mkv")
    monkeypatch.setattr(source_delete, "MAX_TARGETS", 1)
    with pytest.raises(DeleteRejected, match="单次上限"):
        source_delete.build_source_plan(plugin, event, service.config_for(plugin), adapter)
    assert not adapter.calls


def test_existing_new_library_reference_blocks_target_copy_deletion():
    plugin, adapter, event = case()
    adapter.records.append({"id": 2, "src": "/downloads/A.mkv", "dest": "/new/A.mkv"})
    with pytest.raises(DeleteRejected, match="整理记录"):
        source_delete.build_source_plan(plugin, event, service.config_for(plugin), adapter)
    assert not adapter.calls


@pytest.mark.parametrize("stage", ["planning", "after-pause"])
def test_file_claimed_by_new_download_is_preserved_even_before_transfer_history(stage):
    plugin, adapter, event = case()
    original = adapter.download_files
    claimed = stage == "planning"
    def download_files(torrent_hash="", path=""):
        rows = original(torrent_hash, path)
        if claimed:
            rows.append({"downloader": "QB1", "download_hash": "new-download", "fullpath": path})
        return rows
    adapter.download_files = download_files
    if stage == "planning":
        with pytest.raises(DeleteRejected, match="其它下载"):
            source_delete.build_source_plan(plugin, event, service.config_for(plugin), adapter)
        assert not adapter.calls
    else:
        runtime, job = queued(plugin, adapter, event)
        pause = adapter.pause
        def claim_after_pause(task):
            nonlocal claimed
            pause(task)
            claimed = True
        adapter.pause = claim_after_pause
        with pytest.raises(DeleteRejected, match="其它下载"):
            runtime.execute(job, adapter)
        assert not any(call[0] in {"file", "remove"} for call in adapter.calls)


@pytest.mark.parametrize("flag", ["sync_delete_torrents", "sync_delete_source"])
def test_disabled_cleanup_option_preserves_task_or_target_file(flag):
    plugin, adapter, event = case()
    setattr(plugin, "_" + flag, False)
    if flag == "sync_delete_source":
        adapter.put("local", "/seed", "dir")
        adapter.put("local", "/seed/A.mkv")
        adapter.source_root = lambda path: "/seed" if path.startswith("/seed/") else "/downloads"
        for task in adapter.tasks.values():
            task.update(save_path="/seed", files=["/seed/A.mkv"], identity=[task["id"], 100, "/seed"])
    runtime, job = queued(plugin, adapter, event)
    runtime.execute(job, adapter)
    assert len(adapter.tasks) == 2 and not any(call[0] == "remove" for call in adapter.calls)
