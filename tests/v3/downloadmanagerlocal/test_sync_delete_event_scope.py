"""其它服务管理的未配置媒体范围不创建下载中心删除任务。"""

import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.service import sync_delete as service

_fixtures = runpy.run_path(str(Path(__file__).with_name("test_sync_delete.py")))
Plugin = _fixtures["Plugin"]


def webhook(path, **extra):
    """构造规范化的神医通知，不连接真实媒体服务。"""
    return SimpleNamespace(event_data={"event": "deep.delete", "channel": "emby",
                                      "server_name": "Emby", "item_path": path, **extra})


@pytest.mark.parametrize("path", ["/media115/strm-9kg/A.strm", "/media115/strm/01.med-other/A.strm", "/elsewhere/A.mkv"])
def test_unmapped_paths_do_not_create_jobs_or_failure_logs(path, monkeypatch):
    """目录边界不同即跳过；无需启动执行器，也不写失败历史或警告。"""
    plugin = Plugin()
    plugin._sync_delete_cloud_paths = "/media115/strm/01.med#/strm#/media#/library"
    before = plugin.get_data()
    warnings = []
    monkeypatch.setattr(service.logger, "warning", warnings.append)
    result = service.receive_webhook(plugin, webhook(path))
    assert result == {"accepted": False, "reason": "path_not_mapped"}
    assert plugin.get_data() == before and not warnings


@pytest.mark.parametrize("kind", ["local", "cloud", "root", "mixed"])
def test_selected_mapping_keeps_original_event_for_normal_safety_checks(kind):
    """已配置路径照常受理；映射根和混合版本仍由完整规划拒绝不安全目标。"""
    plugin = Plugin()
    plugin._sync_delete_local_paths = "/local-emby#/library"
    plugin._sync_delete_cloud_paths = "/media115/strm/01.med#/strm#/media#/library-cloud"
    events = []

    def submit(event):
        events.append(event)
        return "accepted-job"

    plugin._sync_delete_runtime = SimpleNamespace(stop=SimpleNamespace(is_set=lambda: False), submit=submit)
    path = "/local-emby/A.mkv" if kind == "local" else "/media115/strm/01.med/A.strm"
    if kind == "root":
        path = "/media115/strm/01.med"
    extra = {}
    if kind == "mixed":
        extra["json_object"] = {"Description": "Item Path:\n" + path + "\n/media115/strm-9kg/A.strm"}
    result = service.receive_webhook(plugin, webhook(path, **extra))
    assert result == {"accepted": True, "job_id": "accepted-job"}
    assert len(events) == 1
    expected = sorted([path, "/media115/strm-9kg/A.strm"]) if kind == "mixed" else [path]
    assert events[0]["paths"] == expected


def test_removing_a_mapping_stops_future_job_admission():
    """清除纯网盘映射后同一路径不再进入本插件队列。"""
    plugin = Plugin()
    runtime = service.DeleteRuntime(plugin)
    plugin._sync_delete_runtime = runtime
    plugin._sync_delete_cloud_paths = "/media115/strm-9kg#/strm-9kg#/media-9kg/已整理"
    first = service.receive_webhook(plugin, webhook("/media115/strm-9kg/A.strm"))
    assert first["accepted"] is True
    before, pending = runtime.jobs(), runtime.queue.qsize()
    plugin._sync_delete_cloud_paths = ""
    second = service.receive_webhook(plugin, webhook("/media115/strm-9kg/B.strm"))
    assert second == {"accepted": False, "reason": "path_not_mapped"}
    assert runtime.jobs() == before and runtime.queue.qsize() == pending
