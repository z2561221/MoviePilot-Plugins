"""网盘交由外部服务时，本地清理不能访问云端或绕过身份保护。"""

import runpy
from copy import deepcopy
from pathlib import Path

import pytest
from app.plugins.downloadmanagerlocal.model.sync_delete import (
    BLOCKS_KEY,
    DeleteRejected,
)
from app.plugins.downloadmanagerlocal.service import sync_delete as service

_fixtures = runpy.run_path(str(Path(__file__).with_name("test_sync_delete_local_bridge.py")))
Plugin, Adapter, event, queued, bridge_case = (
    _fixtures[name] for name in ("Plugin", "Adapter", "event", "queued", "bridge_case")
)


def forbid_cloud_io(adapter):
    """所有云端读写都拒绝，确保开关隔离真实调用而非只跳过删除。"""
    lookup, children, delete = adapter.lookup, adapter.children, adapter.delete_file

    def local_lookup(storage, path, root):
        """只允许本地文件身份核验。"""
        assert storage == "local", "关闭网盘处理后不应查询网盘"
        return lookup(storage, path, root)

    def local_children(parent):
        """只允许枚举本地附件。"""
        assert parent["storage"] == "local", "关闭网盘处理后不应枚举网盘"
        return children(parent)

    def local_delete(target):
        """只允许精确清理本地目标。"""
        assert target["storage"] == "local", "关闭网盘处理后不应删除网盘"
        return delete(target)

    def unexpected_targets(*_, **__):
        """无记录的云端回退也不能绕过关闭开关。"""
        raise AssertionError("关闭网盘处理后不应展开网盘目标")

    adapter.lookup, adapter.children, adapter.delete_file = local_lookup, local_children, local_delete
    adapter.media_targets = unexpected_targets


@pytest.mark.parametrize("layout", ["cloud_history", "local_bridge", "local_copy_moved", "partial_pack"])
def test_cloud_disabled_keeps_local_cleanup_independent(layout):
    """三段、四段及部分合集在零云端读写时仍完成对应本地动作。"""
    plugin, adapter = (Plugin(), Adapter()) if layout == "cloud_history" else bridge_case()
    plugin._sync_delete_cloud = False
    if layout == "local_copy_moved":
        adapter.items.pop(("local", "/library/A.mkv"))
        adapter.records[0]["src_fileitem"] = {"size": 100}
    if layout == "partial_pack":
        adapter.put("local", "/downloads/B.mkv")
        for task in adapter.tasks.values():
            task["files"].append("/downloads/B.mkv")
    cloud_before = deepcopy(adapter.items[("115网盘Plus", "/media/A.mkv")])
    forbid_cloud_io(adapter)
    runtime, job = queued(plugin)
    runtime.execute(job, adapter)
    assert job["state"] == "completed" and job["records_done"] == [1]
    assert job["plan"]["cloud_files"] == [] and not adapter.records
    assert ("local", "/downloads/A.mkv") not in adapter.items
    assert adapter.items[("115网盘Plus", "/media/A.mkv")] == cloud_before
    if layout == "partial_pack":
        assert ("local", "/downloads/B.mkv") in adapter.items
        assert len(adapter.tasks) == 2 and plugin.get_data(BLOCKS_KEY)
        assert all(task["status"] == "paused" for task in job["plan"]["tasks"])
    else:
        assert not adapter.tasks


@pytest.mark.parametrize("changed", ["local_copy", "download_source"])
def test_cloud_disabled_still_rejects_local_identity_changes(changed):
    """关闭网盘处理不放宽本地文件与历史大小的身份要求。"""
    plugin, adapter = bridge_case()
    plugin._sync_delete_cloud = False
    adapter.records[0]["src_fileitem"] = {"size": 100}
    path = "/library/A.mkv" if changed == "local_copy" else "/downloads/A.mkv"
    adapter.items[("local", path)]["size"] = 200
    forbid_cloud_io(adapter)
    with pytest.raises(DeleteRejected, match="大小"):
        service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    assert not adapter.calls


def test_cloud_disabled_does_not_guess_when_no_transfer_record_exists():
    """强制云端回退开关不能使本地模式猜测下载源或种子。"""
    plugin, adapter = Plugin(), Adapter()
    plugin._sync_delete_cloud = False
    plugin._sync_delete_force_cloud = True
    adapter.records = []
    forbid_cloud_io(adapter)
    with pytest.raises(DeleteRejected, match="没有对应的整理记录"):
        service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    assert not adapter.calls


def test_cloud_toggle_change_rejects_old_delete_plan_without_io():
    """关闭网盘后不能重放含云端清单的旧计划。"""
    plugin, adapter = bridge_case()
    runtime, job = queued(plugin)
    job["plan"] = service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    plugin._sync_delete_cloud = False
    forbid_cloud_io(adapter)
    with pytest.raises(DeleteRejected, match="配置"):
        runtime.execute(job, adapter)
    assert not adapter.calls


def test_cloud_disabled_keeps_new_reference_protection_on_retry():
    """本地模式重试仍保护新出现的保留媒体引用。"""
    plugin, adapter = bridge_case()
    plugin._sync_delete_cloud = False
    forbid_cloud_io(adapter)
    runtime, job = queued(plugin)
    job["plan"] = service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    adapter.records.append(dict(adapter.records[0], id=2, dest="/other/A.mkv"))
    with pytest.raises(DeleteRejected, match="引用"):
        runtime.execute(job, adapter)
    assert not adapter.calls
