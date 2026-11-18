"""全部模块总览的配置门禁、真实执行、错误隔离与只读性质。"""

from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.service.activity import (
    activity_snapshot,
    observed,
)
from app.plugins.downloadmanagerlocal.service.overview import build_module_overview

from tests.v3.downloadmanagerlocal.test_auto_delete import setup_runtime


def overview_fixture(monkeypatch):
    """复用实际运行态，全部插件数据保存在本测试内存中。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    plugin._transfer_enabled = True
    plugin._transfer_active = True
    plugin._iyuu_enabled = True
    plugin._iyuu_token = "fixture"
    plugin._iyuu_downloaders = ["QB"]
    plugin._rename_enabled = True
    plugin._tag_enabled = True
    plugin._upload_limit_enabled = False
    plugin.downloader_helper = SimpleNamespace(get_configs=lambda: {"QB": SimpleNamespace(type="qbittorrent")})
    diagnostics = {"rename_archive": {"active_failed": 0, "archived": 0, "near_archive": 0, "threshold": 3},
                   "downloaders": {"to": {"available": True, "type": "qbittorrent"}}}
    cards = {"transfer": {"enabled": True, "active": True, "fallback_enabled": True,
                           "today_success": 2, "today_fallback": 1, "success_total": 10},
             "iyuu": {"enabled": True, "today_success": 3, "today_fail": 1, "success_total": 20},
             "rename": {"enabled": True, "dirty": 0, "archived": 0}}
    speed = {"enabled": False, "service_status": "disabled", "active_sessions": 0}
    upload = {"active": False, "service_status": "disabled", "errors": [], "downloaders": []}
    return plugin, runtime, adapter, diagnostics, cards, speed, upload


def test_overview_covers_ten_actual_capabilities_without_downloader_poll(monkeypatch):
    """总览覆盖全部能力，读取本轮统计与索引，不触发下载器查询。"""
    plugin, _runtime, adapter, diagnostics, cards, speed, upload = overview_fixture(monkeypatch)
    def no_poll(*args, **kwargs):
        """总览不得主动采样或控制下载器。"""
        pytest.fail("overview polled downloader")
    adapter.poll = no_poll
    modules, auto = build_module_overview(plugin, diagnostics, cards, speed, upload)
    assert {item["key"] for item in modules} == {"transfer", "iyuu", "rename", "tag", "seed", "archive", "sync_delete", "monitor", "upload", "auto_delete"}
    assert all(item["state"] != "running" for item in modules)
    assert next(item for item in modules if item["key"] == "transfer")["metrics"]["截至昨日累计"] == 8
    assert auto["rules"] == 1


def test_total_switch_off_cannot_show_idle_modules_as_running(monkeypatch):
    """各模块虽保留开启意图，总开关关闭后不能显示正在运行。"""
    plugin, _, _, diagnostics, cards, speed, upload = overview_fixture(monkeypatch)
    plugin._enabled = False
    modules, _ = build_module_overview(plugin, diagnostics, cards, speed, upload)
    assert all(item["state"] == "disabled" for item in modules)


def test_real_execution_marker_is_cleared_after_exception(monkeypatch):
    """真正进入业务时可见处理中，异常退出后计数清理。"""
    plugin, _, _, diagnostics, cards, speed, upload = overview_fixture(monkeypatch)
    states = []
    @observed("transfer")
    def operation(owner):
        """操作中使用实际总览观察自身，然后模拟失败。"""
        modules, _ = build_module_overview(owner, diagnostics, cards, speed, upload)
        states.append(next(item["state"] for item in modules if item["key"] == "transfer"))
        raise RuntimeError("fixture operation failed")
    with pytest.raises(RuntimeError):
        operation(plugin)
    assert states == ["running"] and activity_snapshot(plugin) == {}


def test_broken_delete_index_is_visible_without_breaking_other_modules(monkeypatch):
    """删除索引损坏显示对应模块错误，转种与其它模块继续展示。"""
    plugin, _, _, diagnostics, cards, speed, upload = overview_fixture(monkeypatch)
    plugin.data["sync_delete_job_index"] = {"invalid": True}
    modules, _ = build_module_overview(plugin, diagnostics, cards, speed, upload)
    sync = next(item for item in modules if item["key"] == "sync_delete")
    transfer = next(item for item in modules if item["key"] == "transfer")
    assert sync["state"] == "error" and sync["error"]
    assert transfer["state"] == "idle"


def test_disabled_rename_and_missing_iyuu_config_are_reported_separately(monkeypatch):
    """停用与缺少配置不同，IYUU 总览不只看其 enabled 标志。"""
    plugin, _, _, diagnostics, cards, speed, upload = overview_fixture(monkeypatch)
    plugin._iyuu_token = ""
    cards["rename"]["enabled"] = False
    modules, _ = build_module_overview(plugin, diagnostics, cards, speed, upload)
    assert next(item["state"] for item in modules if item["key"] == "iyuu") == "blocked"
    assert next(item["state"] for item in modules if item["key"] == "rename") == "disabled"


def test_other_upload_downloader_error_is_not_hidden(monkeypatch):
    """上传限速单下载器错误也进入总览，不只汇总顶层错误数组。"""
    plugin, _, _, diagnostics, cards, speed, upload = overview_fixture(monkeypatch)
    upload["downloaders"] = [{"id": "TR", "error": "连接失败"}]
    modules, _ = build_module_overview(plugin, diagnostics, cards, speed, upload)
    assert next(item["state"] for item in modules if item["key"] == "upload") == "error"
