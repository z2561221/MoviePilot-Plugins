"""验证转移取消、停止代次和已创建目标的续办边界。"""

import threading
from types import SimpleNamespace

import pytest

from app.plugins.downloadmanagerlocal.model.state import load_transfer_stats
from app.plugins.downloadmanagerlocal.service import lifecycle, transfer


@pytest.fixture
def transfer_case(monkeypatch, tmp_path):
    """仅使用内存下载器和测试种子文件构造两项批次。"""
    data, added, deleted, processed, registered = {}, [], [], [], []
    existing = set()
    event = threading.Event()
    hooks = {"add": None, "probe": None}

    class Source:
        """提供两个已完成的源任务。"""

        def get_completed_torrents(self):
            """返回固定源任务。"""
            return [{"hash": "a"}, {"hash": "b"}]

        def delete_torrents(self, **kwargs):
            """只记录删除请求，绝不访问下载器。"""
            deleted.extend(kwargs["ids"])

    class Target:
        """记录已经创建的目标任务。"""

        def get_torrents(self, ids):
            """允许在只读查询完成前注入停止请求。"""
            if hooks["probe"]:
                hooks["probe"]()
            return ([{"hash": ids[0]}] if ids[0] in existing else []), None

    source = SimpleNamespace(name="source", type="transmission", instance=Source())
    target = SimpleNamespace(name="target", type="transmission", instance=Target())
    plugin = SimpleNamespace(
        _event=event, _scheduler=None, _transfer_stop_generation=0,
        _fromdownloader="source", _todownloader="target", _fromtorrentpath=str(tmp_path),
        _nopaths="", _includecategory="", _nolabels="", _includelabels="",
        _transferemptylabel=True, _deleteduplicate=True, _deletesource=True,
        _frompath="/source", _topath="/target", _notify=False,
        service_info=lambda name: source if name == "source" else target,
        get_hash=lambda torrent, kind: torrent["hash"],
        get_save_path=lambda torrent, kind: "/source",
        get_label=lambda torrent, kind: [], get_category=lambda torrent, kind: "",
        convert_save_path=lambda *args: "/target",
        get_data=lambda key=None: data.get(key),
        save_data=lambda key, value: data.__setitem__(key, value),
        _register_seed_recheck=lambda name, hashes, origin: registered.extend(hashes),
        _retry_failed_renames=lambda service: None,
    )
    for name in ("stop_upload_limit_worker", "stop_speed_monitor_worker", "stop_speed_monitor_runtime"):
        monkeypatch.setattr(lifecycle, name, lambda *args, **kwargs: None)
    for name in ("a", "b"):
        (tmp_path / f"{name}.torrent").write_bytes(b"fixture")

    def add_target(plugin, service, content, save_path, torrent, stop_generation=None):
        """模拟目标任务接收成功后才到达的取消请求。"""
        added.append(torrent["hash"])
        existing.add(torrent["hash"])
        if hooks["add"]:
            hooks["add"]()
        return torrent["hash"]

    monkeypatch.setattr(transfer, "validate_config", lambda plugin: True)
    monkeypatch.setattr(transfer, "download_torrent", add_target)
    monkeypatch.setattr(transfer, "is_downloader_type", lambda *args, **kwargs: False)
    monkeypatch.setattr(transfer, "post_transfer_process", lambda plugin, service, identity, generation=None: processed.append(identity))
    return SimpleNamespace(
        plugin=plugin, hooks=hooks, added=added, deleted=deleted, processed=processed,
        registered=registered, data=data, target=target,
        stop=lambda: lifecycle.stop_plugin_service(plugin),
    )


def test_stop_after_add_preserves_source_and_resumes_without_duplicate_add(transfer_case):
    """停止后保留已添加目标，下一批只续办后处理而不重复添加或过早删除源。"""
    case = transfer_case
    case.hooks["add"] = case.stop
    transfer.transfer(case.plugin)
    assert case.added == ["a"]
    assert case.deleted == case.processed == case.registered == []
    assert case.data["source-a"]["transfer_state"] == "stopped_after_add"
    assert case.data["source-a"]["delete_source"] is False
    assert load_transfer_stats(case.plugin)["success_total"] == 0

    case.hooks["add"] = None
    case.plugin._event.clear()
    transfer.transfer(case.plugin)
    assert case.added == ["a", "b"]
    assert case.processed == case.registered == case.deleted == ["a", "b"]
    assert case.data["source-a"]["transfer_state"] == "completed"
    assert load_transfer_stats(case.plugin)["success_total"] == 2


def test_stop_during_destination_read_prevents_every_write(transfer_case):
    """只读查询期间收到停止请求时，不执行后续添加、删除和后处理。"""
    case = transfer_case
    case.hooks["probe"] = case.stop
    transfer.transfer(case.plugin)
    assert case.added == case.deleted == case.processed == []


def test_reinitialization_cannot_revive_an_old_transfer(transfer_case):
    """新周期清除共享事件后，旧批次仍因代次失效而停止。"""
    case = transfer_case

    def stop_and_clear():
        """模拟重初始化已准备新的运行周期。"""
        case.stop()
        case.plugin._event.clear()

    case.hooks["probe"] = stop_and_clear
    transfer.transfer(case.plugin)
    assert not case.plugin._event.is_set()
    assert case.added == case.deleted == case.processed == []


def test_stop_without_private_scheduler_keeps_cancellation_set(transfer_case):
    """宿主调度的批次也必须收到停止请求，不能依赖插件私有 scheduler。"""
    case = transfer_case
    case.stop()
    case.stop()
    assert case.plugin._event.is_set()
    assert case.plugin._transfer_stop_generation == 2


def test_initialize_stops_old_work_before_changing_configuration(monkeypatch, transfer_case):
    """停止旧批次后才修改配置，新的周期最后清除退出事件。"""
    case = transfer_case
    order = []

    def stop():
        """记录停止顺序并使用真实取消入口。"""
        order.append("stop")
        case.stop()

    def configure(plugin, config):
        """模拟更新后无后台任务的配置。"""
        order.append("configure")
        plugin._transfer_active = False
        plugin._onlyonce = False
        plugin._iyuu_enabled = False
        return {}

    case.plugin.stop_service = stop
    monkeypatch.setattr(lifecycle, "initialize_runtime_config", configure)
    monkeypatch.setattr(lifecycle, "is_speed_monitor_active", lambda plugin: False)
    monkeypatch.setattr(lifecycle, "is_upload_limit_active", lambda plugin: False)
    monkeypatch.setattr(lifecycle, "load_upload_limit_state", lambda plugin: {})
    lifecycle.initialize_plugin(case.plugin, {})
    assert order == ["stop", "configure"]
    assert not case.plugin._event.is_set()
