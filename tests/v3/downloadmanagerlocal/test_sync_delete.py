"""同步删除的端到端领域测试；所有下载器、文件和宿主记录均为隔离替身。"""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.model.sync_delete import (
    DEFAULTS,
    JOBS_KEY,
    DeleteRejected,
    event_snapshot,
    mapped_scope,
)
from app.plugins.downloadmanagerlocal.service import cleanup
from app.plugins.downloadmanagerlocal.service import sync_delete as service


class Plugin:
    def __init__(self):
        self._enabled = True
        for key, value in DEFAULTS.items():
            setattr(self, "_" + key, deepcopy(value))
        self._sync_delete_enabled = True
        self._sync_delete_servers = ["Emby"]
        self._sync_delete_cloud_paths = "/emby#/strm#/media"
        self._sync_delete_source_paths = "/downloads"
        self.data = {"QB1-source": {"to_download": "QB2", "to_download_id": "target"},
                     "iyuu_source": [{"downloader": "QB2", "torrents": ["seed"]}]}

    def get_data(self, key=None):
        return deepcopy(self.data if key is None else self.data.get(key))

    def save_data(self, key, value):
        self.data[key] = deepcopy(value)

    def del_data(self, key):
        self.data.pop(key, None)


class Adapter:
    def __init__(self):
        self.calls = []
        self.items = {}
        self.put("local", "/downloads", "dir")
        self.put("local", "/downloads/A.mkv")
        self.put("115网盘Plus", "/media/A.mkv")
        self.records = [{"id": 1, "src": "/downloads/A.mkv", "src_storage": "local",
                         "dest": "/media/A.mkv", "dest_storage": "115网盘Plus",
                         "downloader": "QB1", "download_hash": "source", "mode": "copy"}]
        self.tasks = {}
        for torrent_id in ("target", "seed"):
            self.tasks[("QB2", torrent_id)] = {
                "downloader": "QB2", "id": torrent_id, "hash": torrent_id,
                "save_path": "/downloads", "files": ["/downloads/A.mkv"],
                "identity": [torrent_id, 100, "/downloads"], "state": "uploading"}

    def put(self, storage, path, kind="file"):
        self.items[(storage, path)] = {"storage": storage, "path": path, "type": kind,
                                      "name": path.rsplit("/", 1)[-1], "fileid": path,
                                      "identity": [path, 100], "size": 100}

    def servers(self):
        return ["Emby"]

    def histories(self, search="", source=""):
        return [deepcopy(row) for row in self.records
                if (not source or row["src"] == source) and (not search or search in row["dest"])]

    def lookup(self, storage, path, root):
        return deepcopy(self.items.get((storage, path)))

    def source_root(self, path):
        assert path.startswith("/downloads/")
        return "/downloads"

    def download_files(self, torrent_hash="", path=""):
        return [{"id": 11, "downloader": "QB1", "download_hash": "source", "fullpath": path,
                 "savepath": "/downloads", "state": 1}]

    def children(self, parent):
        return [deepcopy(item) for item in self.items.values() if item["storage"] == parent["storage"]
                and item["path"].rsplit("/", 1)[0] == parent["path"]]

    def torrent(self, downloader, torrent_id):
        return deepcopy(self.tasks.get((downloader, torrent_id)))

    def pause(self, task):
        self.calls.append(("pause", task["id"]))

    def remove(self, task):
        self.calls.append(("remove", task["id"]))
        self.tasks.pop((task["downloader"], task["id"]), None)

    def delete_file(self, target):
        key = (target["storage"], target["path"])
        if key in self.items and self.items[key]["identity"] != target["identity"]:
            raise DeleteRejected("目标身份改变")
        self.calls.append(("file", target["storage"], target["path"]))
        self.items.pop(key, None)

    def mark_source_deleted(self, path):
        self.calls.append(("mark", path))

    def mark_download_record_deleted(self, record):
        self.calls.append(("download_record", record["id"]))

    def delete_record(self, row):
        self.calls.append(("record", row["id"]))
        self.records = [item for item in self.records if item["id"] != row["id"]]


def event(path="/emby/A.strm"):
    return event_snapshot({"event": "deep.delete", "channel": "emby", "server_name": "Emby",
                           "item_path": path, "item_name": "A"})


def queued(plugin):
    runtime = service.DeleteRuntime(plugin)
    job_id = runtime.submit(event())
    return runtime, runtime.jobs()[job_id]


def test_existing_transfer_and_iyuu_records_clean_full_chain():
    plugin, adapter = Plugin(), Adapter()
    runtime, job = queued(plugin)
    runtime.execute(job, adapter)
    assert job["state"] == "completed"
    assert not adapter.tasks and not adapter.records
    assert ("115网盘Plus", "/media/A.mkv") not in adapter.items
    assert ("local", "/downloads/A.mkv") not in adapter.items
    assert adapter.calls[:2] == [("pause", "seed"), ("pause", "target")]
    assert adapter.calls[-1] == ("record", 1)
    assert sum(call[0] == "file" and call[1] == "local" for call in adapter.calls) == 1


def test_episode_in_pack_preserves_other_files_and_pauses_all_relatives():
    plugin, adapter = Plugin(), Adapter()
    adapter.put("local", "/downloads/B.mkv")
    for task in adapter.tasks.values():
        task["files"].append("/downloads/B.mkv")
    runtime, job = queued(plugin)
    runtime.execute(job, adapter)
    assert job["state"] == "completed"
    assert len(adapter.tasks) == 2
    assert ("local", "/downloads/B.mkv") in adapter.items
    assert all(task["status"] == "paused" for task in job["plan"]["tasks"])
    assert not any(call[0] == "remove" for call in adapter.calls)


def test_cloud_failure_keeps_source_tasks_and_history_then_retries_only_pending():
    plugin, adapter = Plugin(), Adapter()
    runtime, job = queued(plugin)
    original = adapter.delete_file
    def fail(target):
        raise DeleteRejected("云端核验失败")
    adapter.delete_file = fail
    with pytest.raises(DeleteRejected):
        runtime.execute(job, adapter)
    assert adapter.records and adapter.tasks
    assert ("local", "/downloads/A.mkv") in adapter.items
    adapter.delete_file = original
    runtime.execute(job, adapter)
    assert job["state"] == "completed"


def test_retry_does_not_delete_replaced_file():
    plugin, adapter = Plugin(), Adapter()
    runtime, job = queued(plugin)
    job["plan"] = service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    adapter.items[("115网盘Plus", "/media/A.mkv")]["identity"] = ["replacement", 200]
    with pytest.raises(DeleteRejected, match="身份"):
        runtime.execute(job, adapter)
    assert adapter.records


def test_shared_source_with_retained_library_record_rejects_before_actions():
    plugin, adapter = Plugin(), Adapter()
    adapter.records.append(dict(adapter.records[0], id=2, dest="/another/A.mkv"))
    with pytest.raises(DeleteRejected, match="引用"):
        service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    assert not adapter.calls


def test_missing_file_list_or_offline_downloader_rejects_before_deletion():
    plugin, adapter = Plugin(), Adapter()
    adapter.torrent = lambda *_: (_ for _ in ()).throw(DeleteRejected("下载器不可用"))
    runtime, job = queued(plugin)
    with pytest.raises(DeleteRejected):
        runtime.execute(job, adapter)
    assert not adapter.calls


def test_exact_directory_boundaries_and_root_protection():
    plugin = Plugin()
    config = service.config_for(plugin)
    config["sync_delete_cloud_paths"] = "/emby/strm#/strm#/media\n/emby/strm-9kg#/strm9#/media9"
    assert mapped_scope("/emby/strm-9kg/A.strm", config)["target_path"] == "/media9/A.strm"
    for path in ("/emby/strm", "/emby/strm/../A.strm", "/unconfigured/A.strm"):
        with pytest.raises(DeleteRejected):
            mapped_scope(path, config)


def test_hash_only_old_entry_no_longer_deletes_whole_pack():
    plugin = Plugin()
    assert cleanup.cleanup_by_hash(plugin, "source")["skipped"] is True
    assert cleanup.handle_sync_delete_by_hash_event(plugin, SimpleNamespace(event_data={"hash": "source"}))["skipped"] is True


def test_graph_transferred_seed_and_cycle_are_visited_once():
    records = {"QB1-a": {"to_download": "QB2", "to_download_id": "b"},
               "iyuu_b": [{"downloader": "QB2", "torrents": ["c"]}],
               "iyuu_c": [{"downloader": "QB1", "torrents": ["a"]}]}
    assert service.related_nodes(records, {("QB1", "a")}) == {("QB1", "a"), ("QB2", "b"), ("QB2", "c")}


def test_dedup_is_path_scoped_and_instance_isolated():
    first, second = Plugin(), Plugin()
    left, right = service.DeleteRuntime(first), service.DeleteRuntime(second)
    a = left.submit(event())
    assert left.submit(event()) == a
    assert left.submit(event("/emby/B.strm")) != a
    assert right.submit(event()) != a
    assert len(first.get_data(JOBS_KEY)) == 2
    assert len(second.get_data(JOBS_KEY)) == 1


def test_disabled_or_stopped_runtime_cannot_submit_or_continue():
    plugin, adapter = Plugin(), Adapter()
    runtime, job = queued(plugin)
    runtime.stop.set()
    with pytest.raises(DeleteRejected):
        runtime.execute(job, adapter)
    assert not adapter.calls
    plugin._sync_delete_enabled = False
    assert service.receive_webhook(plugin, SimpleNamespace(event_data={"event": "deep.delete"}))["accepted"] is False


def test_preview_is_readonly_and_can_inspect_existing_media():
    plugin, adapter = Plugin(), Adapter()
    adapter.put("local", "/strm/A.strm")
    before = deepcopy(plugin.data)
    with pytest.raises(DeleteRejected, match="尚未删除"):
        service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    plan = service.build_plan(plugin, event(), service.config_for(plugin), adapter, preview=True)
    assert len(plan["tasks"]) == 2 and not adapter.calls and plugin.data == before


def test_config_change_invalidates_persisted_plan():
    plugin, adapter = Plugin(), Adapter()
    runtime, job = queued(plugin)
    job["plan"] = service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    plugin._sync_delete_source = False
    with pytest.raises(DeleteRejected, match="配置"):
        runtime.execute(job, adapter)
    assert not adapter.calls


def test_lost_persistence_prevents_queue_admission():
    plugin = Plugin()
    plugin.save_data = lambda *_: None
    runtime = service.DeleteRuntime(plugin)
    with pytest.raises(DeleteRejected, match="保存"):
        runtime.submit(event())
    assert runtime.queue.empty()


def test_description_multiline_paths_replace_parent_scope():
    payload = {"event": "deep.delete", "channel": "emby", "item_path": "/emby/Series",
               "json_object": {"Description": "Item Path: /emby/Series/A.strm\n/emby/Series/B.strm\nMount Paths:\n/unsafe"}}
    assert event_snapshot(payload)["paths"] == ["/emby/Series/A.strm", "/emby/Series/B.strm"]


def test_missing_downloader_recovers_existing_transfer_record():
    plugin, adapter = Plugin(), Adapter()
    adapter.records[0]["downloader"] = None
    adapter.download_files = lambda **_: []
    plan = service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    assert {task["id"] for task in plan["tasks"]} == {"target", "seed"}


def test_completed_relations_retire_but_partial_pack_relations_remain():
    plugin, adapter = Plugin(), Adapter()
    runtime, job = queued(plugin)
    runtime.execute(job, adapter)
    assert "QB1-source" not in plugin.data and "iyuu_source" not in plugin.data
    plugin, adapter = Plugin(), Adapter()
    adapter.put("local", "/downloads/B.mkv")
    for task in adapter.tasks.values():
        task["files"].append("/downloads/B.mkv")
    runtime, job = queued(plugin)
    runtime.execute(job, adapter)
    assert plugin.get_data("QB1-source") and plugin.get_data("iyuu_source")


def test_finished_file_reappearing_blocks_old_retry():
    plugin, adapter = Plugin(), Adapter()
    runtime, job = queued(plugin)
    original = adapter.delete_record
    adapter.delete_record = lambda *_: (_ for _ in ()).throw(DeleteRejected("记录更新失败"))
    with pytest.raises(DeleteRejected):
        runtime.execute(job, adapter)
    adapter.put("local", "/downloads/A.mkv")
    adapter.delete_record = original
    with pytest.raises(DeleteRejected, match="新文件"):
        runtime.execute(job, adapter)
    assert adapter.records


def test_shutdown_and_reinitialize_preserve_pending_without_replay():
    plugin = Plugin()
    service.start_runtime(plugin)
    first = plugin._sync_delete_runtime
    service.stop_runtime(plugin)
    assert first.stop.is_set() and not first.thread.is_alive()
    plugin.data[JOBS_KEY] = {"old": {"id": "old", "state": "running", "updated_at": 1}}
    plugin._sync_delete_enabled = False
    service.start_runtime(plugin)
    second = plugin._sync_delete_runtime
    assert second is not first and second.thread is None
    assert second.jobs()["old"]["state"] == "failed"
    service.stop_runtime(plugin)


def test_api_preview_and_retry_require_admin_and_reject_unknown_job():
    from app.plugins.downloadmanagerlocal.controller import sync_delete as controller
    from fastapi import HTTPException
    plugin = Plugin()
    with pytest.raises(HTTPException) as denied:
        controller.preview(plugin, controller.PreviewRequest(path="/emby/A.strm"), SimpleNamespace(super_user=False))
    assert denied.value.status_code == 403
    plugin._sync_delete_runtime = service.DeleteRuntime(plugin)
    response = controller.retry(plugin, controller.RetryRequest(job_id="unknown"), SimpleNamespace(super_user=True))
    assert response.success is False and plugin._sync_delete_runtime.queue.empty()


@pytest.mark.parametrize("kind", ["qbittorrent", "transmission"])
def test_adapter_deletes_task_without_data_and_verifies_removal(kind):
    from app.plugins.downloadmanagerlocal.adapter.sync_delete import SyncDeleteAdapter
    calls = []
    source = {"hash": "abc", "name": "A", "added_on": 100, "save_path": "/downloads", "state": "stoppedUP"}
    if kind == "transmission":
        source = SimpleNamespace(hash_string="abc", name="A", added_date=100, download_dir="/downloads", status="stopped")
    tasks = [source]
    def delete(**kwargs):
        calls.append(kwargs)
        tasks.clear()
        return True
    instance = SimpleNamespace(get_torrents=lambda **_: (list(tasks), False),
                               get_files=lambda _: [{"name": "A.mkv"}], delete_torrents=delete)
    plugin = SimpleNamespace(service_info=lambda _: SimpleNamespace(type=kind, instance=instance))
    adapter = object.__new__(SyncDeleteAdapter)
    adapter.plugin = plugin
    task = adapter.torrent("DL", "abc")
    adapter.remove(task)
    assert calls == [{"ids": ["abc"], "delete_file": False}]


def test_cloud_listing_failure_is_not_absence_and_foreign_child_is_rejected():
    from app.plugins.downloadmanagerlocal.adapter.sync_delete import SyncDeleteAdapter
    adapter = object.__new__(SyncDeleteAdapter)
    parent = {"storage": "115网盘Plus", "path": "/media", "type": "dir", "fileid": "1"}
    adapter.chain = SimpleNamespace(list_files=lambda *a, **k: None)
    with pytest.raises(DeleteRejected, match="查询失败"):
        adapter.children(parent)
    adapter.chain.list_files = lambda *a, **k: [{"storage": "115网盘Plus", "path": "/outside/A.mkv", "name": "A.mkv", "type": "file"}]
    with pytest.raises(DeleteRejected, match="越界"):
        adapter.children(parent)


def test_relation_snapshot_does_not_store_unrelated_iyuu_caches():
    plugin = Plugin()
    plugin.data["iyuu_success_caches"] = ["secret-looking-unrelated-value"]
    snapshot = service.relation_records(plugin)
    assert "iyuu_success_caches" not in snapshot


def test_fastapi_registers_sync_routes_and_validates_retry_body():
    from app import schemas
    from app.plugins.downloadmanagerlocal.controller.sync_delete import routes
    from app.sdk.security import verify_token
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    plugin = Plugin()
    plugin._sync_delete_runtime = service.DeleteRuntime(plugin)
    app = FastAPI()
    for route in routes(plugin):
        app.add_api_route(route["path"], route["endpoint"], methods=route["methods"], response_model=route["response_model"])
    app.dependency_overrides[verify_token] = lambda: schemas.TokenPayload(super_user=False)
    with TestClient(app) as client:
        assert client.post('/sync_delete/retry', json={'job_id': 'missing'}).status_code == 403
        app.dependency_overrides[verify_token] = lambda: schemas.TokenPayload(super_user=True)
        assert client.post('/sync_delete/retry', json={'job_id': 'missing', 'files': ['/unsafe']}).status_code == 422
        assert client.post('/sync_delete/retry', json={'job_id': 'missing'}).json()['success'] is False
        result = client.get('/sync_delete/history').json()
        assert result['total'] == 0 and result['worker_running'] is False


def test_series_scope_requires_matching_media_identity():
    plugin, adapter = Plugin(), Adapter()
    adapter.records[0].update(dest='/media/Series/A.mkv', media_source='themoviedb', media_id='1')
    adapter.put('115网盘Plus', '/media/Series/A.mkv')
    snapshot = event_snapshot({'event': 'deep.delete', 'channel': 'emby', 'server_name': 'Emby',
                               'item_path': '/emby/Series', 'media_type': 'Series',
                               'media_source': 'themoviedb', 'media_id': '2'})
    with pytest.raises(DeleteRejected, match='没有整理记录'):
        service.build_plan(plugin, snapshot, service.config_for(plugin), adapter)


def test_multiple_cloud_versions_are_not_guessed():
    from app.plugins.downloadmanagerlocal.adapter.sync_delete import SyncDeleteAdapter
    adapter = object.__new__(SyncDeleteAdapter)
    adapter.lookup = lambda *a: {'storage': '115网盘Plus', 'path': '/media', 'type': 'dir'}
    adapter.children = lambda *_: [
        {'storage': '115网盘Plus', 'path': '/media/A.mkv', 'name': 'A.mkv', 'type': 'file'},
        {'storage': '115网盘Plus', 'path': '/media/A.mp4', 'name': 'A.mp4', 'type': 'file'},
    ]
    with pytest.raises(DeleteRejected, match='多个网盘版本'):
        adapter.media_targets('115网盘Plus', '/media/A.strm', '/media', strm=True)


def test_cloud_absence_requires_mapping_root_and_uses_uncached_root_walk():
    from app.plugins.downloadmanagerlocal.adapter.sync_delete import SyncDeleteAdapter
    adapter = object.__new__(SyncDeleteAdapter)
    adapter.config = deepcopy(DEFAULTS)
    calls = []
    def children(parent):
        calls.append(parent['path'])
        if parent['path'] == '/':
            return [{'storage': '115网盘Plus', 'path': '/media', 'type': 'dir', 'name': 'media', 'fileid': '123'}]
        return []
    adapter.children = children
    assert adapter.lookup('115网盘Plus', '/media/missing.mkv', '/media') is None
    assert calls == ['/', '/media']
    adapter.children = lambda *_: []
    with pytest.raises(DeleteRejected, match='根目录'):
        adapter.lookup('115网盘Plus', '/media/missing.mkv', '/media')


def test_stop_during_file_lookup_prevents_following_delete():
    from app.plugins.downloadmanagerlocal.adapter.sync_delete import SyncDeleteAdapter
    plugin = Plugin()
    runtime = service.DeleteRuntime(plugin)
    plugin._sync_delete_runtime = runtime
    adapter = object.__new__(SyncDeleteAdapter)
    adapter.plugin, adapter.config = plugin, service.config_for(plugin)
    target = {'storage': '115网盘Plus', 'path': '/media/A.mkv', 'root': '/media', 'type': 'file', 'identity': ['a', 1]}
    def lookup(*_):
        runtime.stop.set()
        return dict(target)
    adapter.lookup = lookup
    calls = []
    adapter.chain = SimpleNamespace(delete_file=lambda *_: calls.append('delete'))
    with pytest.raises(DeleteRejected, match='停止'):
        adapter.delete_file(target)
    assert calls == []
