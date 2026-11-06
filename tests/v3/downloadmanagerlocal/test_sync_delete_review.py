"""审查发现的跨任务、开关及停止边界回归，外部操作全部隔离。"""

import runpy
import threading
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.model.sync_delete import DeleteRejected
from app.plugins.downloadmanagerlocal.service import sync_delete as service

_fixtures = runpy.run_path(str(Path(__file__).with_name("test_sync_delete.py")))
Plugin, Adapter, event, queued = (_fixtures[name] for name in ("Plugin", "Adapter", "event", "queued"))


def test_torrent_removal_switch_works_without_source_file_deletion():
    """只移除种子时仍解析关联，保留下载文件和下载文件状态。"""
    plugin, adapter = Plugin(), Adapter()
    plugin._sync_delete_source = False
    runtime, job = queued(plugin)
    runtime.execute(job, adapter)
    assert not adapter.tasks
    assert ("local", "/downloads/A.mkv") in adapter.items
    assert not any(call[0] == "mark" or call[:2] == ("file", "local") for call in adapter.calls)


def test_relative_names_are_scoped_to_their_related_torrent_group():
    """一次多媒体通知不能把另一下载任务的相对文件名并入本任务。"""
    plugin, adapter = Plugin(), Adapter()
    plugin.data = {}
    adapter.records = []
    adapter.tasks = {}
    adapter.download_files = lambda **_: []
    for index, (folder, name, torrent_id) in enumerate((("one", "A", "a"), ("two", "B", "b")), 1):
        source = f"/downloads/{folder}/{name}.mkv"
        adapter.put("local", source)
        adapter.put("115网盘Plus", f"/media/{name}.mkv")
        adapter.records.append({"id": index, "src": source, "src_storage": "local",
                                "dest": f"/media/{name}.mkv", "dest_storage": "115网盘Plus",
                                "downloader": "QB1", "download_hash": torrent_id})
        adapter.tasks[("QB1", torrent_id)] = {
            "downloader": "QB1", "id": torrent_id, "hash": torrent_id,
            "save_path": f"/downloads/{folder}", "files": [source],
            "identity": [torrent_id, 100, f"/downloads/{folder}"], "state": "uploading"}
    adapter.put("local", "/downloads/one/B.mkv")
    adapter.tasks[("QB1", "a")]["files"].append("/downloads/one/B.mkv")
    snapshot = dict(event(), paths=["/emby/A.strm", "/emby/B.strm"])
    plan = service.build_plan(plugin, snapshot, service.config_for(plugin), adapter)
    assert "/downloads/one/B.mkv" not in {item["path"] for item in plan["source_files"]}
    assert next(task for task in plan["tasks"] if task["id"] == "a")["action"] == "pause"


def test_retry_rejects_recreated_torrent_even_after_old_task_was_removed():
    """记录删除失败后重新下载同 hash，旧任务重试不能继续清理其关联记录。"""
    plugin, adapter = Plugin(), Adapter()
    runtime, job = queued(plugin)
    original = adapter.delete_record
    adapter.delete_record = lambda *_: (_ for _ in ()).throw(DeleteRejected("记录暂不可写"))
    with pytest.raises(DeleteRejected):
        runtime.execute(job, adapter)
    task = deepcopy(job["plan"]["tasks"][0])
    task["identity"][1] = 200
    adapter.tasks[(task["downloader"], task["id"])] = task
    adapter.delete_record = original
    before = list(adapter.calls)
    with pytest.raises(DeleteRejected, match="重建|身份"):
        runtime.execute(job, adapter)
    assert adapter.records and adapter.calls == before


def test_removed_seeds_retire_reverse_iyuu_relations():
    """已移除的辅种不能留下母种反查关系，暂停合集仍保留反查。"""
    plugin, adapter = Plugin(), Adapter()
    plugin.data["iyuu_source_seed"] = "source"
    runtime, job = queued(plugin)
    runtime.execute(job, adapter)
    assert "iyuu_source_seed" not in plugin.data


def test_paused_or_concurrently_reassociated_seed_keeps_reverse_relation():
    """共享 hash 的另一下载器或并发新增关联仍需保留母种反查。"""
    plugin, adapter = Plugin(), Adapter()
    plugin.data["iyuu_source_seed"] = "source"
    plan = service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    for task in plan["tasks"]:
        task["status"] = "removed"
    plugin.data["iyuu_source"].append({"downloader": "QB3", "torrents": ["seed"]})
    service.retire_relations(plugin, plan)
    assert plugin.data["iyuu_source_seed"] == "source"
    plugin, adapter = Plugin(), Adapter()
    plugin.data["iyuu_source_seed"] = "source"
    adapter.put("local", "/downloads/B.mkv")
    for task in adapter.tasks.values():
        task["files"].append("/downloads/B.mkv")
    runtime, job = queued(plugin)
    runtime.execute(job, adapter)
    assert plugin.data["iyuu_source_seed"] == "source"


@pytest.mark.parametrize("restart", [False, True])
def test_waiting_operation_is_cancelled_without_running_in_new_generation(restart):
    """等锁期间取消须及时退出，重新启用也不能复活旧回调。"""
    plugin = Plugin()
    plugin._transfer_stop_generation = 0
    plugin._event = threading.Event()
    entered = threading.Event()
    lock = threading.RLock()

    class ObservedLock:
        """用事件确定回调已经开始等锁，避免依赖随机调度延迟。"""

        def acquire(self, *args, **kwargs):
            """记录等待阶段并委托真实锁。"""
            entered.set()
            return lock.acquire(*args, **kwargs)

        def release(self):
            """释放真实锁。"""
            lock.release()

        def __enter__(self):
            """兼容旧实现的上下文锁。"""
            self.acquire()

        def __exit__(self, *_):
            """退出上下文。"""
            self.release()

    plugin._sync_delete_operation_lock = ObservedLock()
    calls = []

    @service.coordinated
    def operation(current):
        """记录不可在停止后发生的业务动作。"""
        calls.append(current)

    lock.acquire()
    thread = threading.Thread(target=operation, args=(plugin,))
    thread.start()
    try:
        assert entered.wait(2)
        plugin._transfer_stop_generation += 1
        plugin._event.set()
        if restart:
            plugin._event.clear()
        thread.join(1)
        assert not thread.is_alive()
    finally:
        lock.release()
        thread.join(2)
    assert calls == []


@pytest.mark.parametrize("mode", ["queue", "sweep", "legacy"])
def test_recheck_read_returning_after_reinitialize_cannot_start_torrent(mode):
    """校验查询在途时重载，旧响应不能启动新周期的任务。"""
    from app.plugins.downloadmanagerlocal.service import recheck

    started = []
    plugin = SimpleNamespace(
        _event=threading.Event(), _transfer_stop_generation=0, _seed_autostart=True,
        _seed_max_wait_minutes=120, _recheck_torrents={"QB": {"a": "转移做种"}},
        _iyuu_labelsafterseed="", _torrent_tags=["转移做种"],
        get_data=lambda *_: {}, get_hash=lambda torrent, _: torrent["hash"],
        get_label=lambda torrent, _: ["转移做种"],
    )

    def probe(**_):
        """模拟停止并重新初始化后才返回的下载器响应。"""
        plugin._transfer_stop_generation += 1
        plugin._event.clear()
        return [{"hash": "a", "state": "pausedUP", "progress": 1, "tags": "转移做种"}], None

    downloader = SimpleNamespace(get_torrents=probe, start_torrents=lambda **_: started.append(True))
    target = SimpleNamespace(name="QB", type="qbittorrent", instance=downloader)
    plugin.service_info = lambda _: target
    if mode == "queue":
        from time import time

        recheck.process_seed_recheck_once(plugin, {"QB::a": {"hash": "a", "downloader": "QB", "created_at": time()}})
    elif mode == "sweep":
        recheck.sweep_paused_seed_tasks(plugin, [target])
    else:
        recheck._process_legacy_recheck_queue(plugin, [target])
    assert started == []


def test_invalid_transfer_config_does_not_disable_independent_capabilities(monkeypatch):
    """转移配置无效只停转移，不关闭同步删除及其它已启用能力。"""
    from app.plugins.downloadmanagerlocal.service import lifecycle

    plugin, calls, saved = Plugin(), [], []
    plugin._transfer_active = True
    plugin._onlyonce = True
    plugin._iyuu_enabled = False
    plugin._scheduler = None
    plugin.stop_service = lambda: None
    plugin.update_config = lambda **kwargs: saved.append(kwargs["config"])
    config = {"enabled": True, "transfer_enabled": True, "sync_delete_enabled": True, "onlyonce": True}
    monkeypatch.setattr(lifecycle, "initialize_runtime_config", lambda *_: config)
    monkeypatch.setattr(lifecycle, "is_speed_monitor_active", lambda *_: False)
    monkeypatch.setattr(lifecycle, "is_upload_limit_active", lambda *_: False)
    monkeypatch.setattr(lifecycle, "load_upload_limit_state", lambda *_: {})
    monkeypatch.setattr(lifecycle, "load_seed_recheck_queue", lambda *_: {})
    monkeypatch.setattr(lifecycle, "validate_config", lambda *_: False)
    monkeypatch.setattr(lifecycle, "start_sync_delete", lambda *_: calls.append("sync-delete"))
    lifecycle.initialize_plugin(plugin, config)
    assert calls == ["sync-delete"]
    assert plugin._enabled is True and saved[0]["enabled"] is True
    assert saved[0]["transfer_enabled"] is False and saved[0]["onlyonce"] is False


def test_retry_does_not_delete_source_newly_referenced_by_retained_media():
    """失败重试前出现新的整理引用时，不能沿用旧规划删除共享源。"""
    plugin, adapter = Plugin(), Adapter()
    runtime, job = queued(plugin)
    job["plan"] = service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    adapter.records.append(dict(adapter.records[0], id=2, dest="/media/Retained/A.mkv"))
    with pytest.raises(DeleteRejected, match="引用"):
        runtime.execute(job, adapter)
    assert not adapter.calls


def test_failed_legacy_recheck_query_preserves_pending_queue():
    """下载器查询失败不能当成任务消失并清空校验队列。"""
    from app.plugins.downloadmanagerlocal.service import recheck

    plugin = SimpleNamespace(_seed_autostart=True, _recheck_torrents={"QB": {"a": "转种"}})
    target = SimpleNamespace(name="QB", instance=SimpleNamespace(get_torrents=lambda **_: ([], "offline")))
    recheck._process_legacy_recheck_queue(plugin, [target])
    assert plugin._recheck_torrents == {"QB": {"a": "转种"}}


@pytest.mark.parametrize("empty", [None, {}])
def test_empty_configuration_clears_previous_enablement(monkeypatch, empty):
    """清空配置后所有功能回到默认关闭，不能沿用上一轮的认证和开关。"""
    from app.plugins.downloadmanagerlocal import DownloadManagerLocal
    from app.plugins.downloadmanagerlocal.service import config

    monkeypatch.setattr(DownloadManagerLocal.__mro__[1], "__init__", lambda _: None)
    monkeypatch.setattr(config, "create_downloader_helper", lambda: None)
    plugin = DownloadManagerLocal()
    plugin._enabled = True
    plugin._iyuu_enabled = True
    plugin._iyuu_token = "old-config"
    plugin._fromdownloader = "QB1"
    config.initialize_runtime_config(plugin, empty)
    assert plugin._enabled is False and plugin._iyuu_enabled is False
    assert not plugin._iyuu_token and not plugin._fromdownloader


def test_old_persisted_plan_cannot_bypass_new_matching_rules():
    """升级前已保存的清单不自动改写或重放，保留原始进度供核验。"""
    plugin, adapter = Plugin(), Adapter()
    runtime, job = queued(plugin)
    job["plan"] = service.build_plan(plugin, event(), service.config_for(plugin), adapter)
    job["plan"].pop("version")
    job["state"] = "failed"
    runtime.save(job)
    with pytest.raises(DeleteRejected, match="旧版本"):
        runtime.submit(None, job_id=job["id"])
    with pytest.raises(DeleteRejected, match="旧版本"):
        runtime.execute(job, adapter)
    assert not adapter.calls
