"""历史目录迁移兼容：真实路径解析器、适配器查询和领域执行的防误删回归。"""

import runpy
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.adapter import sync_delete as adapters
from app.plugins.downloadmanagerlocal.model.source_paths import SourcePaths
from app.plugins.downloadmanagerlocal.model.sync_delete import (
    DEFAULTS,
    PLAN_VERSION,
    DeleteRejected,
    config_for,
)
from app.plugins.downloadmanagerlocal.service import source_delete
from app.plugins.downloadmanagerlocal.service import sync_delete as service

fixtures = runpy.run_path(str(Path(__file__).with_name("test_sync_delete.py")))
Plugin, Adapter = fixtures["Plugin"], fixtures["Adapter"]


def config(**overrides):
    return {**deepcopy(DEFAULTS), "sync_delete_source_paths": "/downloads\n/seed",
            "sync_delete_source_aliases": "/legacy#/downloads\n/old-seed#/seed", **overrides}


def test_longest_directory_match_and_complete_reverse_lookup():
    paths = SourcePaths(config(sync_delete_source_aliases=(
        "/legacy#/downloads\n/legacy/special#/downloads/other\n/older#/downloads")))
    assert paths.canonical("/legacy/A.mkv") == "/downloads/A.mkv"
    assert paths.canonical("local:/legacy/special/A.mkv") == "/downloads/other/A.mkv"
    assert paths.canonical("/legacy-other/A.mkv") == "/legacy-other/A.mkv"
    assert paths.equivalents("/downloads/A.mkv") == ["/downloads/A.mkv", "/legacy/A.mkv", "/older/A.mkv"]
    assert "/legacy/special/A.mkv" not in paths.equivalents("/downloads/special/A.mkv")


@pytest.mark.parametrize("mapping", [
    "/#/downloads", "/legacy#/", "/downloads#/downloads", "/legacy#/outside",
    "/legacy#/downloads\n/legacy#/seed", "/legacy#/downloads\n/downloads#/seed",
    "/legacy#/downloads\n/downloads/sub#/seed", "/legacy#/downloads#extra",
    "relative#/downloads", "/legacy/../escape#/downloads", "smb:/legacy#/downloads",
])
def test_invalid_or_ambiguous_mapping_is_rejected(mapping):
    with pytest.raises(DeleteRejected):
        SourcePaths(config(sync_delete_source_aliases=mapping))


@pytest.mark.parametrize("excluded", ["/legacy/keep", "/downloads/keep"])
@pytest.mark.parametrize("path", ["/legacy/keep/A.mkv", "/downloads/keep/A.mkv"])
def test_either_name_cannot_bypass_protected_directory(excluded, path):
    with pytest.raises(DeleteRejected, match="保护"):
        SourcePaths(config(sync_delete_exclude_paths=excluded)).checked(path)


def native_adapter(settings=None):
    adapter = object.__new__(adapters.SyncDeleteAdapter)
    adapter.config = settings or config()
    return adapter


def test_existing_distinct_legacy_file_is_not_treated_as_migrated(tmp_path, monkeypatch):
    old, current = tmp_path / "legacy", tmp_path / "downloads"
    old.mkdir(); current.mkdir()
    monkeypatch.setattr(adapters, "Path", lambda value: tmp_path / value.lstrip("/"))
    adapter = native_adapter()
    (old / "A.mkv").write_bytes(b"old")
    with pytest.raises(DeleteRejected, match="仍存在"):
        adapter.source_path("/legacy/A.mkv")
    (current / "A.mkv").write_bytes(b"new")
    with pytest.raises(DeleteRejected, match="不是同一实体"):
        adapter.source_path("/legacy/A.mkv")


def test_missing_current_root_is_not_proof_of_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(adapters, "Path", lambda value: tmp_path / value.lstrip("/"))
    adapter = native_adapter()
    with pytest.raises(DeleteRejected, match="根目录不可访问"):
        adapter.lookup("local", adapter.source_path("/legacy/A.mkv"), "/downloads")


def test_download_rows_merge_by_id_and_keep_raw_fields(monkeypatch):
    old = {"id": 11, "fullpath": "/legacy/A.mkv", "download_hash": "old", "state": 1}
    new = {"id": 12, "fullpath": "/downloads/A.mkv", "download_hash": "new", "state": 1}
    queries = []
    def get(path):
        queries.append(path)
        return [deepcopy(old)] if path.startswith("/legacy/") else [deepcopy(new)]
    monkeypatch.setattr(adapters, "DownloadHistoryOper", lambda: SimpleNamespace(get_files_by_fullpath=get))
    rows = native_adapter().download_files(path="/legacy/A.mkv")
    assert set(queries) == {"/legacy/A.mkv", "/downloads/A.mkv"}
    assert {row["id"] for row in rows} == {11, 12}
    assert next(row for row in rows if row["id"] == 11)["fullpath"] == "/legacy/A.mkv"


def test_transfer_references_include_both_path_names():
    adapter = native_adapter()
    queries = []
    def read(*, search="", source=""):
        queries.append(source)
        return [{"id": 1 if source.startswith("/legacy/") else 2, "src": source}]
    adapter._histories = read
    assert {row["id"] for row in adapter.histories(source="/downloads/A.mkv")} == {1, 2}
    assert set(queries) == {"/legacy/A.mkv", "/downloads/A.mkv"}


def test_torrent_files_normalize_after_provider_mapping():
    adapter = native_adapter()
    adapter.plugin = SimpleNamespace(service_info=lambda _: SimpleNamespace(
        type="qbittorrent", config=SimpleNamespace(path_mapping=[["local:/legacy", "/qb"]]),
        instance=SimpleNamespace(get_torrents=lambda **_: ([{
            "hash": "old", "name": "A", "added_on": 100, "save_path": "/qb", "state": "stoppedUP"}], False),
            get_files=lambda _: [{"name": "A.mkv"}])))
    task = adapter.torrent("QB2", "old")
    assert task["save_path"] == "/downloads" and task["files"] == ["/downloads/A.mkv"]
    assert task["identity"] == ["old", 100, "/downloads"]


def test_old_row_update_uses_original_id_and_raw_path_only(monkeypatch):
    record = {"id": 11, "downloader": "QB1", "download_hash": "old", "fullpath": "/legacy/A.mkv",
              "savepath": "/legacy", "state": 1}
    replacement = dict(record, id=12, download_hash="new")
    queries, writes = [], []
    def get(path):
        queries.append(path)
        return [record, replacement]
    def update(row, changes):
        writes.append(row["id"])
        row.update(changes)
    monkeypatch.setattr(adapters, "DownloadHistoryOper", lambda: SimpleNamespace(
        get_files_by_fullpath=get, _stage_update=update))
    adapter = native_adapter()
    adapter.check_write = lambda: None
    adapter.mark_download_record_deleted(deepcopy(record))
    assert writes == [11] and replacement["state"] == 1
    assert queries == ["/legacy/A.mkv", "/legacy/A.mkv"]


class HistoricalAdapter(Adapter):
    def __init__(self, settings):
        super().__init__()
        self.paths = SourcePaths(settings)
        self.download_rows = [{"id": 11, "downloader": "QB1", "download_hash": "source",
                               "fullpath": "/legacy/A.mkv", "savepath": "/legacy", "state": 1}]

    def download_files(self, torrent_hash="", path=""):
        return [deepcopy(row) for row in self.download_rows
                if (not torrent_hash or row["download_hash"] == torrent_hash)
                and (not path or self.paths.canonical(row["fullpath"]) == self.paths.canonical(path))]

    def histories(self, search="", source=""):
        return [deepcopy(row) for row in self.records
                if (not source or self.paths.canonical(row["src"]) == self.paths.canonical(source))
                and (not search or search in row["dest"])]


def historical_case():
    plugin = Plugin()
    plugin._sync_delete_source_aliases = "/legacy#/downloads\n/old-seed#/seed"
    plugin._sync_delete_source_paths = "/downloads\n/seed"
    adapter = HistoricalAdapter(config_for(plugin))
    adapter.records[0]["src"] = "/legacy/A.mkv"
    return plugin, adapter


def test_old_source_event_keeps_original_snapshot_and_retires_only_old_rows(monkeypatch):
    plugin, adapter = historical_case()
    adapter.records = []
    adapter.items.pop(("local", "/downloads/A.mkv"))
    runtime = service.DeleteRuntime(plugin)
    plugin._sync_delete_runtime = runtime
    monkeypatch.setattr(source_delete, "SyncDeleteAdapter", lambda *_: adapter)
    result = source_delete.receive_source_deleted(plugin, SimpleNamespace(
        event_data={"src": "/legacy/A.mkv", "hash": "source"}), "downloadfile.deleted")
    assert result["accepted"]
    job = runtime.jobs()[result["job_id"]]
    assert job["event"]["paths"] == ["/downloads/A.mkv"]
    assert job["event"]["original_paths"] == ["/legacy/A.mkv"]
    assert job["plan"]["download_records"][0]["fullpath"] == "/legacy/A.mkv"
    runtime.execute(job, adapter)
    assert job["state"] == "completed" and not adapter.tasks
    assert ("download_record", 11) in adapter.calls


def test_existing_current_file_blocks_historical_delete_event(monkeypatch):
    plugin, adapter = historical_case()
    adapter.records = []
    adapter.download_rows.append(dict(adapter.download_rows[0], id=12, download_hash="new-pack",
                                      fullpath="/downloads/A.mkv"))
    runtime = service.DeleteRuntime(plugin)
    plugin._sync_delete_runtime = runtime
    monkeypatch.setattr(source_delete, "SyncDeleteAdapter", lambda *_: adapter)
    result = source_delete.receive_source_deleted(plugin, SimpleNamespace(
        event_data={"src": "/legacy/A.mkv", "hash": "source"}))
    job = runtime.jobs()[result["job_id"]]
    with pytest.raises(DeleteRejected, match="仍存在|新下载"):
        runtime.execute(job, adapter)
    assert not adapter.calls


def test_emby_plan_normalizes_old_record_but_preserves_raw_identity():
    plugin, adapter = historical_case()
    event = fixtures["event"]()
    runtime = service.DeleteRuntime(plugin)
    job_id = runtime.submit(event)
    job = runtime.jobs()[job_id]
    runtime.execute(job, adapter)
    assert job["state"] == "completed" and not adapter.tasks
    assert job["plan"]["records"][0]["src"] == "/legacy/A.mkv"
    assert job["plan"]["source_files"][0]["path"] == "/downloads/A.mkv"
    assert ("download_record", 11) in adapter.calls


@pytest.mark.parametrize("claim_path", ["/legacy/A.mkv", "/downloads/A.mkv"])
def test_new_download_reference_is_not_absorbed_into_emby_deletion(claim_path):
    plugin, adapter = historical_case()
    adapter.download_rows.append(dict(adapter.download_rows[0], id=12, download_hash="new-pack",
                                      fullpath=claim_path))
    with pytest.raises(DeleteRejected, match="其它下载"):
        service.build_plan(plugin, fixtures["event"](), config_for(plugin), adapter)
    assert not adapter.calls


@pytest.mark.parametrize("change", ["mapping", "old-event", "old-plan"])
def test_retry_requires_same_mapping_and_current_version(change):
    plugin, adapter = historical_case()
    runtime = service.DeleteRuntime(plugin)
    job_id = runtime.submit(fixtures["event"]())
    job = runtime.jobs()[job_id]
    job["state"] = "failed"
    if change == "old-event":
        job["event"].pop("plan_version")
    elif change == "old-plan":
        job["plan"] = {"version": PLAN_VERSION - 1}
    else:
        plugin._sync_delete_source_aliases = "/different#/downloads"
    runtime.save(job)
    with pytest.raises(DeleteRejected, match="旧|配置"):
        runtime.submit(None, job_id=job_id)
    assert not adapter.calls
