"""审查停止、重载、任务幂等与跨模块写入的受控回归。"""

import hashlib
import importlib
from copy import deepcopy
from threading import Event, Thread
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.service import (
    lifecycle,
    rename,
    reseed,
    site_tag,
    speed_actions,
    speed_monitor,
    speed_notification,
    tag_completion,
    transfer,
)
from app.plugins.downloadmanagerlocal.service import scheduler as plugin_scheduler
from app.plugins.downloadmanagerlocal.service.coordination import operation_lock
from bencode import bdecode, bencode

from . import (
    test_reseed_runtime as reseed_tests,
)
from . import (
    test_retry_rename as retry_tests,
)
from . import (
    test_site_tag as site_tests,
)
from . import (
    test_transfer_cancellation as transfer_tests,
)
from .test_site_tag import MemoryDownloader
from .test_speed_monitor_delete import FakeDownloader as SpeedFakeDownloader
from .test_speed_monitor_delete import FakePlugin as SpeedFakePlugin
from .test_speed_monitor_delete import NotificationType
from .test_tag_cleanup import FakeTransmission
from .test_tag_completion_async import FakeTagCompletionPlugin, _capture_scheduler

environment = reseed_tests.environment
archived_retry = retry_tests.archived_retry
tag_case = site_tests.tag_case
transfer_case = transfer_tests.transfer_case


def test_old_scan_cannot_replace_the_new_scan_result(tmp_path, monkeypatch):
    """旧请求在重载后才返回时，新任务的结果文件和状态仍须保留。"""
    plugin = FakeTagCompletionPlugin(tmp_path)
    jobs = _capture_scheduler(monkeypatch)
    entered = Event()
    release = Event()

    def scan(_plugin, downloaders, **_options):
        """仅延迟旧扫描，允许新扫描先写入结果。"""
        if downloaders == ["old"]:
            entered.set()
            assert release.wait(3)
        return {"code": 0, "msg": "完成", "downloaders": [{"name": downloaders[0], "tags": []}]}

    monkeypatch.setattr(tag_completion, "scan_tag_completion", scan)
    old_task = tag_completion.submit_tag_completion_scan(plugin, ["old"], "old-request")
    worker = Thread(target=jobs[0][2], kwargs=jobs[0][3])
    worker.start()
    try:
        assert entered.wait(2)
        tag_completion.stop_tag_completion_task(plugin)
        new_task = tag_completion.submit_tag_completion_scan(plugin, ["new"], "new-request")
        jobs[1][2](**jobs[1][3])
        release.set()
        worker.join(2)
        assert not worker.is_alive()
        assert tag_completion.get_tag_completion_status(plugin)["task_id"] == new_task["task_id"]
        result = tag_completion.get_tag_completion_result(plugin, new_task["task_id"])
        assert result["code"] == 0
        assert result["result"]["downloaders"][0]["name"] == "new"
        assert old_task["task_id"] != new_task["task_id"]
    finally:
        release.set()
        worker.join(3)


def test_request_history_retains_the_content_fingerprint(tmp_path, monkeypatch):
    """前一个已完成任务的相同请求可复用，改过内容的请求仍须拒绝。"""
    plugin = FakeTagCompletionPlugin(tmp_path)
    jobs = _capture_scheduler(monkeypatch)
    monkeypatch.setattr(tag_completion, "scan_tag_completion", lambda *_args, **_kwargs: {
        "code": 0, "msg": "完成", "downloaders": [],
    })
    first = tag_completion.submit_tag_completion_scan(plugin, ["QB"], "first-request")
    jobs[0][2](**jobs[0][3])
    tag_completion.submit_tag_completion_scan(plugin, ["QB"], "second-request")
    jobs[1][2](**jobs[1][3])
    repeated = tag_completion.submit_tag_completion_scan(plugin, ["QB"], "first-request")
    assert repeated["code"] == 0
    assert repeated["task_id"] == first["task_id"]
    changed = tag_completion.submit_tag_completion_scan(plugin, ["other"], "first-request")
    assert changed["code"] == 1
    assert len(jobs) == 2


def test_corrupt_tag_task_state_is_not_replaced(tmp_path, monkeypatch):
    """任务存储损坏不能当作没有历史，再提交时保留原值。"""
    plugin = FakeTagCompletionPlugin(tmp_path)
    original = ["unreadable-state"]
    plugin.saved[tag_completion.TAG_COMPLETION_TASK_KEY] = original
    jobs = _capture_scheduler(monkeypatch)
    with pytest.raises(ValueError):
        tag_completion.submit_tag_completion_scan(plugin, ["QB"], "request")
    assert plugin.saved[tag_completion.TAG_COMPLETION_TASK_KEY] == original
    assert not jobs


def test_stop_attempts_every_cleanup_after_storage_failure(monkeypatch):
    """一项停止读库失败不应阻断其它任务、调度器和 worker 的退出。"""
    calls = []
    plugin = SimpleNamespace(_event=Event(), _transfer_stop_generation=4)
    plugin._scheduler = SimpleNamespace(
        remove_all_jobs=lambda: calls.append("remove-jobs"),
        running=True,
        shutdown=lambda **options: calls.append(("shutdown", options)),
    )

    def failed_stop(_plugin):
        """模拟标签任务读库失败。"""
        calls.append("tags")
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(lifecycle, "stop_tag_completion_task", failed_stop)
    monkeypatch.setattr(reseed, "stop", lambda _plugin: calls.append("reseed"))
    for name in ("stop_auto_delete", "stop_sync_delete", "clear_transfer_schedule",
                 "stop_seed_recheck_worker", "stop_upload_limit_worker", "stop_speed_monitor_worker",
                 "stop_speed_monitor_runtime"):
        monkeypatch.setattr(lifecycle, name, lambda _plugin, label=name: calls.append(label))
    lifecycle.stop_plugin_service(plugin)
    assert plugin._event.is_set()
    assert plugin._transfer_stop_generation == 5
    assert "reseed" in calls
    assert "stop_speed_monitor_runtime" in calls
    assert ("shutdown", {"wait": False}) in calls
    assert plugin._scheduler is None


@pytest.mark.parametrize("disabled_field", ["_iyuu_enabled", "_iyuu_downloaders"])
def test_reseed_admission_respects_the_iyuu_configuration(environment, disabled_field):
    """关闭 IYUU 或清空下载器后，旧调用不能扩成扫描所有下载器。"""
    case = environment
    setattr(case.plugin, disabled_field, False if disabled_field == "_iyuu_enabled" else [])
    with pytest.raises(ValueError):
        reseed.start(case.plugin, "disabled-request")
    assert not case.jobs
    assert reseed.TASK_KEY not in case.stored


def test_reseed_initialization_failure_releases_worker_ownership(environment):
    """缓存读取失败仍须结束任务并释放线程归属，不永久卡住下一次受理。"""
    case = environment
    case.stored["reseed_metadata_cache"] = ["broken"]
    task = reseed.start(case.plugin, "broken-cache")
    args, options = case.jobs[0]
    args[2](**options["func_kwargs"])
    assert getattr(case.plugin, "_reseed_worker", None) is None
    assert getattr(case.plugin, "_reseed_execution", None) is None
    assert reseed.status(case.plugin)["status"] == "failed"
    assert case.stored["reseed_metadata_cache"] == ["broken"]
    assert reseed.status(case.plugin)["task_id"] == task["task_id"]


def test_reseed_result_read_does_not_mutate_the_stored_page():
    """只读状态投影不能把原始添加回执改写为校验回执。"""
    stored = {
        reseed.TASK_KEY: {"task_id": "task", "status": "completed", "result_count": 1},
        "reseed_result_0": {"task_id": "task", "items": [
            {"state": "added", "message": "等待校验", "downloader": "QB", "target_hash": "hash"},
        ]},
        "reseed_verification": {"QB::hash": {"state": "seeding", "message": "已做种"}},
    }
    plugin = SimpleNamespace(get_data=lambda key: stored.get(key))
    before = deepcopy(stored)
    result = reseed.results(plugin, "task")
    assert result["items"][0]["state"] == "seeding"
    assert stored == before


def test_single_rename_retry_reports_site_tag_failure(archived_retry):
    """标签失败不能报整条补刀完成，但已完成的命名成果仍须保留。"""
    case = archived_retry
    case.plugin._tag_torrent.return_value = False
    result = rename.retry_rename_by_hash(case.plugin, case.service, case.torrent_hash)
    assert result["code"] == 1
    assert "标签" in result["msg"]
    assert case.data[rename.RENAME_RECORDS_KEY][case.torrent_hash]["success"] is True


def test_slow_rename_cannot_write_after_stop_and_reinitialization(archived_retry):
    """媒体识别回包再慢，停止代次变化后也不能继续重命名下载器。"""
    case = archived_retry
    case.plugin._event = Event()
    case.plugin._transfer_stop_generation = 2
    media = SimpleNamespace(type=case.plugin.chain.recognize_media.return_value.type)

    def recognize(**_kwargs):
        """在识别回包前模拟停止及新初始化清除退出事件。"""
        case.plugin._event.set()
        case.plugin._transfer_stop_generation += 1
        case.plugin._event.clear()
        return media

    case.plugin.chain.recognize_media.side_effect = recognize
    assert rename.rename_torrent(case.plugin, case.downloader, "qbittorrent", case.torrent_hash,
                                 case.original_name, "/downloads/example") is False
    case.downloader.qbc.torrents_rename.assert_not_called()


def test_slow_transmission_tag_read_cannot_write_after_reload(tag_case):
    """TR 的标签回读跨过停止代次时，不继续覆盖下载器整组标签。"""
    case = tag_case
    downloader = MemoryDownloader("transmission", ["保种"])
    original_read = downloader.get_torrents

    def read(ids):
        """模拟下载器回包时插件已进入新代次。"""
        rows = original_read(ids)
        case.plugin._transfer_stop_generation += 1
        return rows

    downloader.get_torrents = read
    assert site_tag.tag_torrent(case.plugin, downloader, "transmission", "target", ["保种"],
                                ["https://tracker.example/announce"]) is False
    assert not downloader.writes


def test_tag_completion_serializes_each_target_write_with_other_modules(tag_case):
    """补全标签必须避让共享锁，并在取得锁后保留其他模块刚写入的 TR 标签。"""
    case = tag_case
    downloader = MemoryDownloader("transmission", ["保种"])
    case.plugin.service_info = lambda _name: SimpleNamespace(name="target", type="transmission", instance=downloader)
    entered = Event()
    written = Event()
    original_write = downloader.change_torrent

    def write(**options):
        """记录真实替换标签边界。"""
        written.set()
        original_write(**options)

    def execute():
        """调用生产补全执行器，等待共享协调锁。"""
        entered.set()
        site_tag.execute_tag_completion(case.plugin, [
            {"downloader": "target", "kind": "site", "tag": "彩虹岛", "hashes": ["target-hash"]},
        ])

    downloader.change_torrent = write
    worker = Thread(target=execute)
    try:
        with operation_lock(case.plugin):
            worker.start()
            assert entered.wait(2)
            assert not written.wait(0.15)
            downloader.labels.append("并发标签")
        worker.join(2)
        assert not worker.is_alive()
        assert set(downloader.labels) == {"保种", "并发标签", "彩虹岛"}
    finally:
        worker.join(3)


def _speed_runtime():
    """用生产命名空间构造一个已经二次确认的告警。"""
    session = speed_monitor.SpeedMonitorSession(
        downloader_id="qb-main", downloader_type="qbittorrent", torrent_hash="abc123", name="Example",
        total_bytes=1000, start_downloaded_bytes=100, start_remaining_bytes=900,
        last_downloaded_bytes=200, first_observed_at=1, last_observed_at=10,
        last_effective_at=10, last_valid_sample_at=10, last_success_poll_at=10, effective_seconds=9,
        last_state="active", target_identity=[speed_monitor.binding_of(SimpleNamespace(type="qbittorrent")),
                                              12, "/downloads"],
        anomaly_epoch=1, anomaly_active=True, had_anomaly=True,
    )
    alert = {"status": "confirming", "downloader_id": "qb-main", "torrent_hash": "abc123",
             "anomaly_epoch": 1, "target_identity": list(session.target_identity), "token": "abc123",
             "telegram_userid": "10001", "expires_at": 200, "created_at": 10, "updated_at": 10,
             "handled_at": 0, "decision": {"is_anomalous": True}}
    return speed_monitor.SpeedMonitorRuntime(sessions={"qb-main:abc123": session},
                                              alerts={"qb-main:abc123:1": alert})


def test_speed_delete_confirmation_cannot_write_after_stop():
    """删除确认的慢查询回包后，停止或重载必须使原确认失效。"""
    downloader = SpeedFakeDownloader()
    plugin = SpeedFakePlugin(_speed_runtime(), downloader)
    plugin._event = Event()
    plugin._transfer_stop_generation = 5
    original_read = downloader.get_torrents

    def read(ids):
        """模拟停止代次已变化，但新周期已经清除了退出事件。"""
        rows = original_read(ids)
        plugin._transfer_stop_generation += 1
        plugin._event.clear()
        return rows

    downloader.get_torrents = read
    event = {"plugin_id": "FakePlugin", "channel": "telegram", "userid": "10001",
             "text": "dmsm:abc123:confirm", "source": "telegram-bot",
             "original_message_id": 77, "original_chat_id": 88}
    assert speed_actions.process_speed_message_action(plugin, event, now=100,
                                                      notification_type=NotificationType) is True
    assert not downloader.delete_calls


def test_stale_speed_scan_does_not_notify_or_persist_over_a_new_runtime(monkeypatch):
    """旧扫描回包不得通知或用旧状态覆盖新初始化的监控运行态。"""
    old_runtime = speed_monitor.SpeedMonitorRuntime()
    new_runtime = speed_monitor.SpeedMonitorRuntime()
    plugin = SimpleNamespace(_enabled=True, _speed_monitor_enabled=True, _speed_monitor_mode="auto",
                             _speed_monitor_downloaders=["QB"], _speed_monitor_runtime=old_runtime,
                             _transfer_stop_generation=1, _event=Event(),
                             service_info=lambda _name: SimpleNamespace(type="qbittorrent", instance=object()))
    persisted = []
    notifications = []

    def poll(*_args, **_kwargs):
        """让旧轮次查询返回时，当前实例已经拥有新的状态对象。"""
        plugin._transfer_stop_generation += 1
        plugin._speed_monitor_runtime = new_runtime
        return SimpleNamespace(success=False, error="temporary", items=[])

    monkeypatch.setattr(speed_monitor, "poll_downloader", poll)
    monkeypatch.setattr(speed_monitor, "persist_speed_monitor_runtime", lambda *_args: persisted.append(_args[1]))
    monkeypatch.setattr(speed_monitor, "dispatch_pending_speed_alerts", lambda *_args: notifications.append(True))
    speed_monitor.scan_speed_monitor(plugin, now=100)
    assert not persisted
    assert not notifications
    assert plugin._speed_monitor_runtime is new_runtime


class PageOnlyList(list):
    """完整结果不允许深拷贝，但允许按页提取有限切片。"""

    def __deepcopy__(self, _memo):
        """将全量深拷贝明确暴露为性能回归。"""
        raise AssertionError("不能为一页复制完整种子清单")


def test_scan_paging_only_copies_the_requested_associations():
    """结果页只复制当前切片，既不构造全量关联表，也不改原结果。"""
    hashes = PageOnlyList(f"hash-{index}" for index in range(2000))
    result = {"code": 0, "downloaders": [{"name": "QB", "tags": [
        {"kind": "site", "tag": "站点", "hashes": hashes, "samples": ["Example"], "count": len(hashes)},
    ]}]}
    page, total = tag_completion._page_result("scan", result, 500, 200)
    assert total == 2000
    assert page["downloaders"][0]["tags"][0]["hashes"] == list(hashes[500:700])
    page["downloaders"][0]["tags"][0]["samples"].append("Other")
    assert result["downloaders"][0]["tags"][0]["samples"] == ["Example"]
    assert len(hashes) == 2000


def test_execute_paging_only_copies_current_detail_rows():
    """执行结果页不复制所有成功/跳过/失败项，并保留跨列表游标。"""
    added = PageOnlyList({"hash": f"hash-{index}", "tags": ["站点"]} for index in range(1000))
    result = {"code": 0, "added": added, "skipped": [{"hash": "skipped"}], "failed": []}
    page, total = tag_completion._page_result("execute", result, 990, 20)
    assert total == 1001
    assert len(page["added"]) == 10
    assert page["skipped"] == [{"hash": "skipped"}]
    page["added"][0]["tags"].append("Other")
    assert added[990]["tags"] == ["站点"]


def test_speed_notification_dispatch_stops_before_the_next_alert(monkeypatch):
    """第一条通知在停止期间返回后，不继续派发其他旧告警。"""
    runtime = SimpleNamespace(alerts={"first": {"status": "pending", "downloader_id": "QB", "torrent_hash": "first"},
                                     "second": {"status": "pending", "downloader_id": "QB", "torrent_hash": "second"}},
                              sessions={"QB:first": SimpleNamespace(status="active"),
                                        "QB:second": SimpleNamespace(status="active")})
    plugin = SimpleNamespace(_transfer_stop_generation=1, _event=Event(), _speed_monitor_runtime=runtime)
    sent = []

    def send(_plugin, alert, _session, **_options):
        """完成第一条受理后模拟重载。"""
        sent.append(alert["torrent_hash"])
        plugin._transfer_stop_generation += 1
        return True

    monkeypatch.setattr(speed_notification, "send_speed_alert", send)
    assert speed_notification.dispatch_pending_speed_alerts(plugin, runtime, 100) == 1
    assert sent == ["first"]


def test_speed_runtime_detaches_even_if_final_persistence_fails(monkeypatch):
    """停止保存异常不应保留已退出运行态的锁和对象引用。"""
    runtime = speed_monitor.SpeedMonitorRuntime()
    plugin = SimpleNamespace(_speed_monitor_runtime=runtime)

    def persist(*_args):
        """模拟存储不可用，保留异常供生命周期记录。"""
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(speed_monitor, "persist_speed_monitor_runtime", persist)
    with pytest.raises(RuntimeError):
        speed_monitor.stop_speed_monitor_runtime(plugin)
    assert plugin._speed_monitor_runtime is None


def test_cosmetic_tag_coordination_does_not_load_unrelated_delete_state(tag_case):
    """标签共享互斥即可，不按每颗目标反复读取三个删除保护表。"""
    case = tag_case
    reads = []
    downloader = MemoryDownloader("transmission", ["保种"])
    case.plugin.service_info = lambda _name: SimpleNamespace(name="target", type="transmission", instance=downloader)

    def read(key=None):
        """记录不应发生的保护表读取。"""
        reads.append(key)
        return {}

    case.plugin.get_data = read
    result = site_tag.execute_tag_completion(case.plugin, [
        {"downloader": "target", "kind": "site", "tag": "彩虹岛", "hashes": ["target-hash"]},
    ])
    assert result["code"] == 0
    assert reads == []


def test_wrong_transfer_metadata_never_adds_or_removes_the_original_source(transfer_case):
    """路径上的 torrent 内容错误时，不添加目标、更不删除对应源任务。"""
    case = transfer_case
    (case.torrent_path / f'{case.hashes["a"]}.torrent').write_bytes(b"not a torrent")
    transfer.transfer(case.plugin)
    assert case.hashes["a"] not in case.added
    assert case.hashes["a"] not in case.deleted
    assert case.hashes["a"] not in case.registered


def test_unexpected_transfer_target_hash_does_not_delete_source(transfer_case, monkeypatch):
    """添加接口返回不属于本次元数据的目标时，不进入后处理或删源。"""
    case = transfer_case
    monkeypatch.setattr(transfer, "download_torrent", lambda *_args, **_kwargs: "unexpected-hash")
    transfer.transfer(case.plugin)
    assert case.deleted == []
    assert case.processed == []
    assert case.registered == []


def test_manual_tag_cleanup_stops_after_a_slow_read(tag_case):
    """人工清理的 TR 回读跨过重载代次时，不继续移除或覆盖标签。"""
    case = tag_case
    downloader = MemoryDownloader("transmission", ["用户标签", "保种"])
    original_read = downloader.get_torrents

    def read(ids):
        """在标签快照返回前模拟重载。"""
        result = original_read(ids)
        case.plugin._transfer_stop_generation += 1
        return result

    downloader.get_torrents = read
    case.plugin.service_info = lambda _name: SimpleNamespace(name="TR", type="transmission", instance=downloader)
    site_tag.execute_tag_cleanup(case.plugin, [
        {"downloader": "TR", "tag": "用户标签", "hashes": ["target-hash"]},
    ])
    assert not downloader.writes
    assert downloader.labels == ["用户标签", "保种"]


def test_manual_tag_cleanup_cannot_bypass_managed_anchor_protection(tag_case, monkeypatch):
    """后端同样保护宿主及管理锚点，不能靠伪造请求绕过界面保护。"""
    case = tag_case
    monkeypatch.setattr(site_tag, "settings", SimpleNamespace(TORRENT_TAG="HostTag"))
    downloader = MemoryDownloader("transmission", ["HostTag", "保种"])
    case.plugin.service_info = lambda _name: SimpleNamespace(name="TR", type="transmission", instance=downloader)
    result = site_tag.execute_tag_cleanup(case.plugin, [
        {"downloader": "TR", "tag": "HostTag", "hashes": ["target-hash"]},
    ])
    assert result["code"] == 1
    assert not downloader.writes


def test_automatic_tag_cleanup_stops_after_its_scan_read(tag_case):
    """自动临时标签清理也不能在旧扫描回包后继续写入。"""
    case = tag_case
    tag = site_tag.TEMP_TAG_PREFIX + "A" * 10
    downloader = MemoryDownloader("transmission", [tag, "保种"])
    original_read = downloader.get_torrents

    def read(ids=None):
        """返回快照时换代，仍保留目标任务。"""
        result = original_read(ids or ["target-hash"])
        case.plugin._transfer_stop_generation += 1
        return result

    downloader.get_torrents = read
    case.plugin.service_info = lambda _name: SimpleNamespace(name="TR", type="transmission", instance=downloader)
    result = site_tag.scan_and_clean_tags(case.plugin, ["TR"])
    assert result["code"] == 2
    assert not downloader.writes


def test_transmission_cleanup_builds_the_identity_set_only_once(tag_case, monkeypatch):
    """每个种子不能重新建立全量关联集合，大小写归一的操作数保持线性。"""
    calls = []

    class CountedHash(str):
        """记录种子身份归一次数。"""

        def lower(self):
            """把重复集合构造暴露为可计数回归。"""
            calls.append(str(self))
            return super().lower()

    hashes = [CountedHash(f"hash-{index}") for index in range(200)]
    rows = [SimpleNamespace(hashString=identity, name="Example", labels=["清理标签", "保种"])
            for identity in hashes]
    downloader = FakeTransmission(rows)
    case = tag_case
    case.plugin.service_info = lambda _name: SimpleNamespace(name="TR", type="transmission", instance=downloader)
    monkeypatch.setattr(site_tag, "get_hash", lambda row, _kind: row.hashString)
    result = site_tag.execute_tag_cleanup(case.plugin, [
        {"downloader": "TR", "tag": "清理标签", "hashes": hashes},
    ])
    assert result["code"] == 0
    assert len(calls) < 20 * len(hashes)
    assert all(row.labels == ["保种"] for row in rows)


@pytest.mark.parametrize("kind", ["v1", "v2", "hybrid"])
def test_transfer_metadata_preserves_each_supported_hash_identity(kind):
    """BT 元数据身份不依赖重新编码，v2 与混合种子不会被缩窄成 v1。"""
    info = {b"name": b"Example", b"piece length": 16384}
    if kind != "v1":
        info.update({b"meta version": 2, b"file tree": {b"Example": {b"": {b"length": 1}}}})
    if kind != "v2":
        info.update({b"length": 1, b"pieces": b"a" * 20})
    raw = bencode(info)
    content = bencode({b"info": info})
    source_hash = hashlib.sha1(raw).hexdigest() if kind != "v2" else hashlib.sha256(raw).hexdigest()[:40]
    metadata, hashes = transfer._validated_transfer_metadata(content, source_hash)
    assert source_hash in hashes
    assert metadata["info"]["name"] == "Example"
    with pytest.raises(ValueError):
        transfer._validated_transfer_metadata(content, "0" * 40)


def test_transfer_tracker_supplement_preserves_noncanonical_raw_info(transfer_case, monkeypatch):
    """补 Tracker 不能重编码 info，也不能借共享临时文件读取另一实例内容。"""
    case = transfer_case
    raw = b"d4:name1:a6:lengthi1e12:piece lengthi16e6:pieces20:" + b"a" * 20 + b"e"
    identity = hashlib.sha1(raw).hexdigest()
    content = b"d4:info" + raw + b"e"
    (case.torrent_path / f"{identity}.torrent").write_bytes(content)
    (case.torrent_path / f"{identity}.fastresume").write_bytes(bencode({"trackers": [["https://first.invalid/announce"]]}))
    source = case.plugin.service_info("source")
    source.type = "qbittorrent"
    source.instance.get_completed_torrents = lambda: [{"hash": identity}]
    captured = []

    class SharedTemporary:
        """模拟同 hash 临时文件被别的实例覆盖。"""

        def __truediv__(self, _name):
            """旧路径会把组装后的元数据写入共享位置。"""
            return self

        def write_bytes(self, _content):
            """不向磁盘写入，只模拟另一执行方接管文件。"""

        def read_bytes(self):
            """旧实现读回别的 Tracker，暴露文件级冲突。"""
            return bencode({"announce": "https://other.invalid/announce", "info": bdecode(raw)})

    monkeypatch.setattr(transfer, "settings", SimpleNamespace(TEMP_PATH=SharedTemporary()), raising=False)
    monkeypatch.setattr(transfer, "is_downloader_type", lambda kind, service: kind == service.type)
    monkeypatch.setattr(transfer, "download_torrent", lambda _plugin, **options: captured.append(options["content"]) or identity)
    transfer.transfer(case.plugin)
    assert len(captured) == 1
    assert bdecode(captured[0])["announce"] == "https://first.invalid/announce"
    assert transfer._raw_info(captured[0]) == raw


@pytest.mark.parametrize("kind", ["transfer", "iyuu"])
def test_queued_one_shot_does_not_run_after_the_generation_changes(monkeypatch, kind):
    """调度器已取出的旧一次性回调，也不能在重初始化后启动新批次。"""
    entry = importlib.import_module("app.plugins.downloadmanagerlocal")
    plugin = object.__new__(entry.DownloadManagerLocal)
    plugin._event = Event()
    jobs = []
    called = []
    plugin._scheduler = SimpleNamespace(add_job=lambda function, *_args, **options: jobs.append((function, options)))
    plugin._transfer_stop_generation = 7
    plugin._onlyonce = plugin._iyuu_onlyonce = True
    plugin.update_config = lambda **_options: None
    if kind == "transfer":
        monkeypatch.setattr(entry, "_transfer_impl", lambda *_args, **_kwargs: called.append(True))
        lifecycle._schedule_transfer_once(plugin, {})
    else:
        monkeypatch.setattr(reseed, "start", lambda *_args, **_kwargs: called.append(True))
        lifecycle._schedule_iyuu_once(plugin, {})
    plugin._transfer_stop_generation += 1
    plugin._event.clear()
    function, options = jobs[0]
    function(**options.get("kwargs", {}))
    assert called == []


def test_initialization_failure_cleans_up_already_started_workers(monkeypatch):
    """最后一个模块启动失败时，先前启动的监控和限速也必须收口。"""
    alive = {"speed": False, "upload": False}
    calls = []
    plugin = SimpleNamespace(_event=Event(), _scheduler=None, _transfer_active=False, _onlyonce=False,
                             _iyuu_token="", _enabled=True)

    def stop():
        """模拟统一停止入口释放本轮的两个 worker。"""
        calls.append("stop")
        plugin._event.set()
        alive.update(speed=False, upload=False)

    def failure(_plugin):
        """模拟最后一步同步删除初始化失败。"""
        raise RuntimeError("invalid sync configuration")

    plugin.stop_service = stop
    monkeypatch.setattr(lifecycle, "initialize_runtime_config", lambda _plugin, config: deepcopy(config))
    monkeypatch.setattr(lifecycle, "recover_tag_completion_task", lambda _plugin: None)
    monkeypatch.setattr(reseed, "recover", lambda _plugin: None)
    monkeypatch.setattr(lifecycle, "initialize_auto_delete", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(lifecycle, "is_speed_monitor_active", lambda _plugin: True)
    monkeypatch.setattr(lifecycle, "ensure_speed_monitor_runtime", lambda _plugin: object())
    monkeypatch.setattr(lifecycle, "start_speed_monitor_worker_if_needed", lambda *_args: alive.update(speed=True))
    monkeypatch.setattr(lifecycle, "load_upload_limit_state", lambda _plugin: {})
    monkeypatch.setattr(lifecycle, "is_upload_limit_active", lambda _plugin: True)
    monkeypatch.setattr(lifecycle, "start_upload_limit_worker", lambda _plugin: alive.update(upload=True))
    monkeypatch.setattr(lifecycle, "is_iyuu_active", lambda _plugin: False)
    monkeypatch.setattr(lifecycle, "load_seed_recheck_queue", lambda _plugin: {})
    monkeypatch.setattr(lifecycle, "start_sync_delete", failure)
    with pytest.raises(RuntimeError):
        lifecycle.initialize_plugin(plugin, {})
    assert alive == {"speed": False, "upload": False}
    assert calls == ["stop", "stop"]
    assert plugin._event.is_set()


def test_invalid_iyuu_cron_does_not_remove_other_module_services(monkeypatch):
    """一个无效执行周期不能让自动删除和转种兜底一起失去注册。"""
    plugin = SimpleNamespace(_enabled=True, _iyuu_enabled=True, _iyuu_token="fixture",
                             _iyuu_downloaders=["QB"], _iyuu_cron="invalid cron", _transfer_active=True,
                             _transfer_fallback_enabled=True, _transfer_fallback_interval_minutes=60,
                             _fallback_transfer=lambda: None, iyuu_auto_seed=lambda: None)
    monkeypatch.setattr(plugin_scheduler, "service_declaration", lambda _plugin: [{"id": "AutoDelete"}])
    services = plugin_scheduler.build_plugin_services(plugin)
    assert {service["id"] for service in services} == {"AutoDelete", "TorrentTransferFallback"}
    assert getattr(plugin, "_iyuu_schedule_error", "")


def test_old_request_does_not_claim_an_overwritten_result_is_available(tmp_path, monkeypatch):
    """请求幂等记录保留，但被后续扫描取代的大结果不能继续声称可取。"""
    plugin = FakeTagCompletionPlugin(tmp_path)
    jobs = _capture_scheduler(monkeypatch)
    monkeypatch.setattr(tag_completion, "scan_tag_completion", lambda *_args, **_kwargs: {"code": 0, "msg": "完成"})
    first = tag_completion.submit_tag_completion_scan(plugin, ["QB"], "old")
    jobs[0][2](**jobs[0][3])
    tag_completion.submit_tag_completion_scan(plugin, ["QB"], "new")
    jobs[1][2](**jobs[1][3])
    status = tag_completion.get_tag_completion_status(plugin, task_id=first["task_id"])
    assert status["result_available"] is False
    repeated = tag_completion.submit_tag_completion_scan(plugin, ["QB"], "old")
    assert repeated["code"] == 0
    assert repeated["result_available"] is False


@pytest.mark.parametrize("state", [
    {"current_task": ["broken"], "requests": []},
    {"current_task": None, "requests": "broken"},
    {"current_task": {"status": False}, "requests": []},
])
def test_corrupt_task_fields_are_preserved_instead_of_replaced(tmp_path, monkeypatch, state):
    """外层是字典也不代表内部任务和去重记录有效。"""
    plugin = FakeTagCompletionPlugin(tmp_path)
    original = deepcopy(state)
    plugin.saved[tag_completion.TAG_COMPLETION_TASK_KEY] = state
    _capture_scheduler(monkeypatch)
    with pytest.raises(ValueError):
        tag_completion.submit_tag_completion_scan(plugin, ["QB"], "request")
    assert plugin.saved[tag_completion.TAG_COMPLETION_TASK_KEY] == original


def test_reused_iyuu_name_prefix_does_not_write_after_a_stale_history_read(archived_retry):
    """复用母种前缀的捷径也必须执行停止代次复验。"""
    case = archived_retry
    case.plugin._event = Event()
    case.plugin._transfer_stop_generation = 1
    original_read = case.plugin.get_data

    def read(key):
        """历史查询返回时换代，不影响其它持久化键。"""
        records = original_read(key) or {}
        if key == rename.RENAME_RECORDS_KEY:
            records["mother"] = {"success": True, "after_name": "[Example (2026)] - source"}
            case.plugin._transfer_stop_generation += 1
        return records

    case.plugin.get_data = read
    result = rename.rename_iyuu_torrent_by_source_record(case.plugin, case.downloader, "qbittorrent",
                                                        case.torrent_hash, case.original_name, "mother")
    assert result is None
    case.downloader.qbc.torrents_rename.assert_not_called()


def test_single_retry_cannot_restart_suboperations_after_a_stale_target_read(archived_retry):
    """补刀入口本身也固定代次，不能借新代次的子函数复活旧请求。"""
    case = archived_retry
    case.plugin._event = Event()
    case.plugin._transfer_stop_generation = 1
    response = case.downloader.get_torrents.return_value

    def read(**_options):
        """目标查询结束时模拟重载及退出事件清除。"""
        case.plugin._transfer_stop_generation += 1
        case.plugin._event.clear()
        return response

    case.downloader.get_torrents.side_effect = read
    result = rename.retry_rename_by_hash(case.plugin, case.service, case.torrent_hash)
    assert result["code"] != 0
    case.downloader.qbc.torrents_rename.assert_not_called()
    case.plugin._tag_torrent.assert_not_called()
