"""先本地整理再上传网盘时，显式路径桥接的删除边界回归。"""

import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.model.sync_delete import DeleteRejected, mapped_scope, mappings
from app.plugins.downloadmanagerlocal.service import sync_delete as service

_fixtures = runpy.run_path(str(Path(__file__).with_name("test_sync_delete.py")))
Plugin, Adapter, event, queued = (_fixtures[name] for name in ("Plugin", "Adapter", "event", "queued"))


def bridge_case():
    """准备相同内容的本地整理副本、下载源和115实体。"""
    plugin, adapter = Plugin(), Adapter()
    plugin._sync_delete_cloud_paths = "/emby#/strm#/media#/library"
    adapter.put("local", "/library", "dir")
    adapter.put("local", "/library/A.mkv")
    adapter.records[0].update(dest="/library/A.mkv", dest_storage="local", dest_fileitem={"size": 100})
    return plugin, adapter


def test_explicit_local_library_mapping_connects_full_deletion_chain():
    """四段映射关联本地整理历史，并只删除精确副本和下载源。"""
    plugin, adapter = bridge_case()
    adapter.put("local", "/library/Other.mkv")
    runtime, job = queued(plugin)
    runtime.execute(job, adapter)
    assert job["state"] == "completed" and job["records_done"] == [1]
    assert len(job["plan"]["cloud_files"]) == 1
    assert {item["path"] for item in job["plan"]["source_files"]} == {"/downloads/A.mkv", "/library/A.mkv"}
    assert ("local", "/library/Other.mkv") in adapter.items
    assert ("local", "/library/A.mkv") not in adapter.items
    assert not adapter.tasks


def test_bridge_does_not_guess_without_explicit_fourth_path():
    """只有片名、季集相同而无路径映射时不能关联本地记录。"""
    plugin, adapter = bridge_case()
    plugin._sync_delete_cloud_paths = "/emby#/strm#/media"
    with pytest.raises(DeleteRejected, match="没有整理记录"):
        service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    assert not adapter.calls


@pytest.mark.parametrize("changed", ["cloud", "local", "historical"])
def test_bridge_requires_matching_cloud_local_and_history_sizes(changed):
    """同名不同内容不能因映射而进入删除计划。"""
    plugin, adapter = bridge_case()
    if changed == "cloud":
        adapter.items[("115网盘Plus", "/media/A.mkv")]["size"] = 200
    elif changed == "local":
        adapter.items[("local", "/library/A.mkv")]["size"] = 200
    else:
        adapter.records[0]["dest_fileitem"]["size"] = 200
    with pytest.raises(DeleteRejected, match="大小|身份"):
        service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    assert not adapter.calls


def test_bridge_respects_source_switch_and_shared_local_references():
    """保留下载源时也保留整理副本；另一保留记录引用副本时拒绝清理。"""
    plugin, adapter = bridge_case()
    plugin._sync_delete_source = False
    runtime, job = queued(plugin)
    runtime.execute(job, adapter)
    assert ("local", "/library/A.mkv") in adapter.items
    assert ("local", "/downloads/A.mkv") in adapter.items
    assert job["plan"]["source_files"] == []
    plugin, adapter = bridge_case()
    adapter.records.append(dict(adapter.records[0], id=2, src="/library/A.mkv", dest="/retained/A.mkv"))
    with pytest.raises(DeleteRejected, match="引用"):
        service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    assert not adapter.calls


def test_bridge_mapping_remains_backward_compatible_and_excludes_paths():
    """空第四段兼容三段配置，第四段仍遵守根目录、相对路径和保护范围。"""
    plugin = Plugin()
    config = service.config_for(plugin)
    before = mapped_scope("/emby/A.strm", config)
    config["sync_delete_cloud_paths"] += "#"
    assert mapped_scope("/emby/A.strm", config) == before
    for invalid in ("/", "relative", "/library/../other"):
        config["sync_delete_cloud_paths"] = "/emby#/strm#/media#" + invalid
        with pytest.raises(DeleteRejected):
            mappings(config)
    config["sync_delete_cloud_paths"] = "/emby#/strm#/media#/library"
    config["sync_delete_exclude_paths"] = "/library"
    with pytest.raises(DeleteRejected, match="排除"):
        mapped_scope("/emby/A.strm", config)


def test_uploaded_move_uses_recorded_size_when_local_copy_is_absent():
    """上传后本地副本已移走时，历史大小和现存下载源仍可验证云端关联。"""
    plugin, adapter = bridge_case()
    adapter.items.pop(("local", "/library/A.mkv"))
    plan = service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    assert len(plan["records"]) == 1 and len(plan["tasks"]) == 2
    assert next(item for item in plan["source_files"] if item["path"] == "/library/A.mkv")["status"] == "absent"
    adapter.records[0]["dest_fileitem"] = {}
    with pytest.raises(DeleteRejected, match="大小"):
        service.build_plan(plugin, event(), service.config_for(plugin), adapter)


def test_cloud_deleted_before_notification_still_cleans_exact_source():
    """实体先被其它同步链删除时，完整历史身份允许幂等续办本集关联。"""
    plugin, adapter = bridge_case()
    adapter.records[0]["src_fileitem"] = {"size": 100}
    adapter.items.pop(("local", "/library/A.mkv"))
    adapter.items.pop(("115网盘Plus", "/media/A.mkv"))
    runtime, job = queued(plugin)
    runtime.execute(job, adapter)
    assert job["state"] == "completed" and not adapter.records
    assert job["plan"]["cloud_files"][0]["status"] == "absent"
    assert ("file", "115网盘Plus", "/media/A.mkv") not in adapter.calls
    assert ("file", "local", "/downloads/A.mkv") in adapter.calls


def test_pause_allows_delayed_downloader_state_without_unbounded_wait():
    """下载器接受暂停后延迟更新状态，有限重查成功后才允许后续删除。"""
    from app.plugins.downloadmanagerlocal.adapter.sync_delete import SyncDeleteAdapter

    task = {"downloader": "QB", "id": "a", "identity": ["a", 1, "/downloads"], "state": "stalledUP"}
    waits, writes, states = [], [], iter(["stalledUP"] * 4 + ["stoppedUP"])
    adapter = object.__new__(SyncDeleteAdapter)
    adapter.plugin = SimpleNamespace(
        _sync_delete_runtime=SimpleNamespace(stop=SimpleNamespace(wait=lambda delay: waits.append(delay) or False)),
        service_info=lambda _: SimpleNamespace(instance=SimpleNamespace(stop_torrents=lambda **_: writes.append(True))),
    )
    adapter.check_write = lambda: None
    adapter.torrent = lambda *_: dict(task, state=next(states))
    adapter.pause(task)
    assert writes == [True] and 1 < sum(waits) <= 10


def test_already_paused_torrent_does_not_send_another_stop():
    """旧任务已确认暂停时继续核验，不再重复发送暂停请求。"""
    from app.plugins.downloadmanagerlocal.adapter.sync_delete import SyncDeleteAdapter

    task = {"downloader": "QB", "id": "a", "identity": ["a", 1, "/downloads"], "state": "stoppedUP"}
    adapter = object.__new__(SyncDeleteAdapter)
    writes = []
    adapter.plugin = SimpleNamespace(service_info=lambda _: SimpleNamespace(instance=SimpleNamespace(stop_torrents=lambda **_: writes.append(True))))
    adapter.torrent = lambda *_: dict(task)
    adapter.check_write = lambda: None
    adapter.pause(task)
    assert writes == []
