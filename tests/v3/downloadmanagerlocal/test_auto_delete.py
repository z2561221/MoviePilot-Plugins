"""自动删除真实服务闭环的隔离回归，禁止连接真实下载器。"""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.adapter.auto_delete import (
    AutoDeleteAdapter,
    binding_of,
    normalize_native,
)
from app.plugins.downloadmanagerlocal.adapter import auto_delete as auto_delete_adapter
from app.plugins.downloadmanagerlocal.model.auto_delete import (
    BLOCKS_KEY,
    CONTROL_KEY,
    ActivateRequest,
    Conditions,
    Rule,
    SaveRequest,
    Settings,
    Snapshot,
    Tracker,
    config_values,
)
from app.plugins.downloadmanagerlocal.service import auto_delete, auto_delete_config
from app.plugins.downloadmanagerlocal.service.auto_delete_executor import release_jobs
from app.plugins.downloadmanagerlocal.service.auto_delete_matcher import match_rule
from app.plugins.downloadmanagerlocal.storage.auto_delete_jobs import AutoDeleteStore


class Plugin:
    """克隆配置和持久化数据，模拟独立读写而非共享引用。"""

    def __init__(self, settings):
        """保存仅本测试所有的配置与状态。"""
        self.data = {}
        self.config = {"enabled": True, "other_module": "保留", **config_values(settings)}
        self._enabled = True
        self._event = None
        self._transfer_stop_generation = 0
        self._upload_limit_state = {}

    def get_data(self, key=None):
        """模拟独立持久化读取。"""
        return deepcopy(self.data if key is None else self.data.get(key))

    def save_data(self, key, value):
        """保存数据可由用例替换以模拟故障。"""
        self.data[key] = deepcopy(value)

    def del_data(self, key):
        """仅删除测试内状态。"""
        self.data.pop(key, None)

    def get_config(self):
        """读取测试配置。"""
        return deepcopy(self.config)

    def update_config(self, config):
        """更新测试配置。"""
        self.config = deepcopy(config)


class Adapter:
    """使用内存任务执行暂停/移除，记录每次副作用。"""

    def __init__(self, snapshot):
        """下载器对象只保存用于绑定的公开配置字段。"""
        self.service_info = SimpleNamespace(name="QB", type="qbittorrent", config={"host": "fake", "port": 1})
        snapshot.binding = binding_of(self.service_info)
        self.items = {snapshot.hash: snapshot}
        self.actions = []

    def service(self, name):
        """不创建实际客户端。"""
        return self.service_info

    def poll(self, name, **kwargs):
        """每次返回独立对象，可模拟任务重建。"""
        ids = kwargs.get("ids")
        return [item.model_copy(deep=True) for item in self.items.values()
                if item.downloader == name and (ids is None or item.hash in ids)]

    def current(self, expected):
        """保留原任务身份核验。"""
        current = self.items.get(expected.hash)
        if current and current.identity != expected.identity:
            raise ValueError("任务已重建")
        return current

    def pause(self, expected):
        """记录暂停调用，不删除数据。"""
        current = self.current(expected)
        if current and not current.paused:
            self.actions.append("pause")
            current.state = "stoppedUP"
            current.upload_bps = 0
        return current

    def remove(self, expected):
        """仅模拟移除任务。"""
        self.current(expected)
        self.actions.append("remove")
        self.items.pop(expected.hash, None)

    def restore(self, expected, **kwargs):
        """模拟明确人工恢复。"""
        self.actions.append("restore")
        self.current(expected).state = "uploading"


def snapshot(**changes):
    """生成有可信身份、已完成的原生任务。"""
    return Snapshot(downloader="QB", binding="binding", kind="qbittorrent", hash="a" * 40,
                    name="Example", added_at=1, save_path="/downloads/Movie", total_bytes=1024 ** 3,
                    state="uploading", completed=True, ratio=1, seed_seconds=168 * 3600,
                    upload_bps=5120, tags=["普通"], category="电影", **changes)


def setup_runtime(monkeypatch, **conditions):
    """将真实运行服务绑定到内存插件及适配器。"""
    rule = Rule(id="rule", name="冷种", enabled=True, downloaders=["QB"], conditions=Conditions(**conditions))
    settings = Settings(enabled=True, rules=[rule])
    plugin = Plugin(settings)
    adapter = Adapter(snapshot())
    runtime = auto_delete.AutoDeleteRuntime(plugin, settings, adapter=adapter, now=1000)
    plugin._auto_delete_runtime = runtime
    runtime.store.write(CONTROL_KEY, {"revision": 1, "approvals": {}, "debug_scans": {}, "config": settings.model_dump(mode="json")})
    monkeypatch.setattr(auto_delete_config, "update_plugin_job", lambda *_: None)
    return plugin, runtime, adapter, rule


@pytest.mark.parametrize("conditions,expected", [
    ({"seed_hours_min": 168}, "match"), ({"seed_hours_min": 169}, "no_match"),
    ({"ratio_min": 1, "ratio_max": 1}, "match"), ({"upload_kib_max": 0}, "no_match"),
    ({"path_include": r"(?:^|/)Movie(?:/|$)"}, "match"),
    ({"tag_exclude": "普通"}, "no_match"), ({"tag_include": "普通"}, "match"),
])
def test_matcher_boundaries(conditions, expected):
    """截图字段按实际原值判断并包含数值边界。"""
    rule = Rule(downloaders=["QB"], conditions=Conditions(**conditions))
    assert match_rule(rule, snapshot(), 1000).status == expected


def test_missing_values_are_unknown_and_tracker_pairing():
    """指定字段缺失或备用 Tracker 故障不能冒充整种失败。"""
    torrent = snapshot()
    torrent.seed_seconds = None
    rule = Rule(downloaders=["QB"], conditions=Conditions(seed_hours_min=0))
    assert match_rule(rule, torrent, 1000).status == "unknown"
    rule.conditions = Conditions(tracker_include="primary", tracker_error="error")
    torrent.trackers = [Tracker(url="https://primary/announce", status="working"),
                        Tracker(url="https://backup/announce", status="error", message="unregistered")]
    assert match_rule(rule, torrent, 1000).status == "no_match"


def test_settings_reject_invalid_regex_and_range():
    """无效正则、反向区间、空白启用规则不能保存。"""
    with pytest.raises(ValueError):
        Conditions(name_include="[")
    with pytest.raises(ValueError):
        Conditions(ratio_min=2, ratio_max=1)
    with pytest.raises(ValueError):
        Rule(enabled=True, downloaders=["QB"])


def test_preview_never_changes_state_or_counter(monkeypatch):
    """连续预览只计算命中，零次暂停和删除。"""
    _, runtime, adapter, _ = setup_runtime(monkeypatch, upload_kib_max=10)
    before = deepcopy(runtime.store.plugin.data)
    for _ in range(3):
        runtime.scan(preview=True, now=1000)
    assert runtime.samples == {} and adapter.actions == []
    assert runtime.store.plugin.data == before


def test_debug_two_samples_and_pause_evidence(monkeypatch):
    """手动连点不计数，间隔到达才暂停，证据保留原速度。"""
    _, runtime, adapter, _ = setup_runtime(monkeypatch, upload_kib_max=10)
    assert runtime.run(now=1000).items == []
    assert runtime.run(now=1001).items == []
    result = runtime.run(now=1300)
    assert adapter.actions == ["pause"]
    assert result.items[0].snapshot.upload_bps == 5120
    assert result.items[0].state == "paused"
    assert runtime.run(now=1600).items == []
    assert adapter.actions == ["pause"]


def test_pause_waits_for_delayed_downloader_confirmation(monkeypatch):
    """暂停回读短暂滞后时等待同一任务的最终状态。"""
    expected = snapshot()
    observed = iter([
        expected.model_copy(deep=True),
        expected.model_copy(deep=True),
        expected.model_copy(update={"state": "stoppedUP"}, deep=True),
    ])
    waits = []
    stop_calls = []
    service = SimpleNamespace(type="qbittorrent", instance=SimpleNamespace(
        stop_torrents=lambda **kwargs: stop_calls.append(kwargs)))
    plugin = SimpleNamespace(service_info=lambda _: service)
    adapter = AutoDeleteAdapter(plugin)
    adapter.current = lambda _: next(observed)
    monkeypatch.setattr(auto_delete_adapter.time, "sleep", waits.append)

    result = adapter.pause(expected)

    assert result.paused
    assert stop_calls == [{"ids": [expected.hash]}]
    assert waits == [0.5]


def test_pause_timeout_keeps_confirmation_failure(monkeypatch):
    """超过有界确认等待仍未暂停时继续拒绝后续删除。"""
    expected = snapshot()
    observed = iter([expected.model_copy(deep=True)] * 7)
    waits = []
    service = SimpleNamespace(type="qbittorrent", instance=SimpleNamespace(stop_torrents=lambda **_: True))
    plugin = SimpleNamespace(service_info=lambda _: service)
    adapter = AutoDeleteAdapter(plugin)
    adapter.current = lambda _: next(observed)
    monkeypatch.setattr(auto_delete_adapter.time, "sleep", waits.append)

    with pytest.raises(RuntimeError, match="尚未确认暂停"):
        adapter.pause(expected)

    assert waits == [0.5, 1, 2, 3, 3]


def test_pause_confirmation_stops_if_task_identity_changes(monkeypatch):
    """确认等待期间任务身份变化时不再轮询或继续处理。"""
    expected = snapshot()
    changed = expected.model_copy(update={"added_at": 2}, deep=True)
    observed = iter([expected.model_copy(deep=True), changed])
    waits = []
    stop_calls = []
    service = SimpleNamespace(type="qbittorrent", instance=SimpleNamespace(
        stop_torrents=lambda **kwargs: stop_calls.append(kwargs)))
    plugin = SimpleNamespace(service_info=lambda _: service)
    adapter = AutoDeleteAdapter(plugin)
    adapter.poll = lambda *_args, **_kwargs: [next(observed)]
    monkeypatch.setattr(auto_delete_adapter.time, "sleep", waits.append)

    with pytest.raises(ValueError, match="任务已重建"):
        adapter.pause(expected)

    assert stop_calls == [{"ids": [expected.hash]}]
    assert waits == []


def test_activation_does_not_delete_and_explicit_pending_uses_saved_evidence(monkeypatch):
    """批准规则和暂停清单只保存意图，下一轮才移除原任务。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, seed_hours_min=168)
    job = runtime.run(now=1000).items[0]
    monkeypatch.setattr(auto_delete, "AutoDeleteAdapter", lambda *_: adapter)
    request = ActivateRequest(expected_revision=1, rule_id="rule", job_ids=[job.id],
                              evidence_versions={job.id: job.evidence_fingerprint}, accept_history=True)
    auto_delete.activate_rule(plugin, request)
    assert adapter.actions == ["pause"]
    new_runtime = plugin._auto_delete_runtime
    assert new_runtime.run(now=1300).items[0].state == "removed"
    assert adapter.actions == ["pause", "remove"]


def test_forged_delete_is_downgraded_and_other_config_preserved(monkeypatch):
    """配置保存不能自报已确认，也不覆盖其他模块字段。"""
    plugin, runtime, _, _ = setup_runtime(monkeypatch, name_include="Example")
    settings = runtime.settings.model_copy(deep=True)
    settings.rules[0].mode = "delete"
    result = auto_delete.save_settings(plugin, SaveRequest(expected_revision=1, settings=settings))
    assert result.settings.rules[0].mode == "debug"
    assert plugin.config["other_module"] == "保留"


def test_storage_failure_prevents_pause(monkeypatch):
    """意图或索引未确认之前，外部副作用必须为零。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, seed_hours_min=168)
    def fail_save(key, value):
        """模拟写入没有落盘。"""
        return
    plugin.save_data = fail_save
    assert runtime.run(now=1000).state == "error"
    assert adapter.actions == []


def test_identity_change_prevents_restore(monkeypatch):
    """同 hash 重建后的新任务不能继承旧保护或恢复。"""
    _, runtime, adapter, _ = setup_runtime(monkeypatch, seed_hours_min=168)
    job = runtime.run(now=1000).items[0]
    adapter.items["a" * 40].added_at = 900
    results = release_jobs(runtime, [job.id], restore=True)
    assert results[0]["state"] == "review"
    assert adapter.actions == ["pause"]
    assert job.id in runtime.store.blocks()


def test_native_completion_never_uses_downloaded_ever():
    """累计下载量很高但实际进度不足的任务不能被当成已完成。"""
    raw = {"hash": "hash", "name": "部分下载", "added_on": 10, "save_path": "/downloads",
           "progress": 0.2, "amount_left": 800, "total_size": 1000, "downloaded": 9000,
           "state": "downloading", "seeding_time": 0, "upspeed": 0}
    normalized = normalize_native(raw, "QB", "qbittorrent", "binding")
    assert normalized.completed is False and normalized.seed_seconds == 0


def test_active_protection_is_never_pruned(monkeypatch):
    """历史保留期限不清除活动暂停证据和保护。"""
    plugin, runtime, _, _ = setup_runtime(monkeypatch, seed_hours_min=168)
    job = runtime.run(now=1000).items[0]
    plugin.data["auto_delete_job_index"][job.id]["updated_at"] = 1
    AutoDeleteStore(plugin).prune(1)
    assert job.id in plugin.data[BLOCKS_KEY]
    assert job.id in runtime.store.index()


def test_source_address_change_is_part_of_binding():
    """实际 DownloaderConf 将连接地址放在嵌套 config，必须识别地址变化。"""
    service = SimpleNamespace(name="QB", type="qbittorrent", config=SimpleNamespace(config={"host": "server-a", "port": 1}, path_mapping=[]))
    original = binding_of(service)
    service.config.config["host"] = "server-b"
    assert binding_of(service) != original


@pytest.mark.parametrize("state", ["checkingUP", "checkingDL", "moving", "missingFiles", "error", "unknown"])
def test_nonactionable_states_never_become_completed(state):
    """进度为 100% 仍须跳过校验、移动、文件缺失和未知状态。"""
    raw = {"hash": "hash", "state": state, "progress": 1, "amount_left": 0}
    assert not normalize_native(raw, "QB", "qbittorrent", "binding").completed


def test_transmission_seconds_and_infinite_ratio():
    """TR 原生字段包含真实零秒及无限分享率，JSON 中不输出 Infinity。"""
    raw = {"hashString": "a" * 40, "name": "Example", "addedDate": 1, "downloadDir": "/downloads",
           "status": 6, "percentDone": 1, "leftUntilDone": 0, "secondsSeeding": 0, "uploadRatio": -2,
           "rateUpload": 0, "totalSize": 100, "labels": []}
    native = normalize_native(raw, "TR", "transmission", "binding")
    assert native.completed and native.seed_seconds == 0 and native.ratio_state == "infinite"
    minimum = Rule(downloaders=["TR"], conditions=Conditions(ratio_min=9999))
    maximum = Rule(downloaders=["TR"], conditions=Conditions(ratio_max=9999))
    assert match_rule(minimum, native, 1000).status == "match"
    assert match_rule(maximum, native, 1000).status == "no_match"
    assert "Infinity" not in native.model_dump_json()


def test_cosmetic_save_keeps_schedule_and_sample(monkeypatch):
    """改名称保留原周期与一次已取得的有效采样。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, upload_kib_max=10)
    runtime.run(now=1000)
    next_due = runtime.next_due
    settings = runtime.settings.model_copy(deep=True)
    settings.rules[0].name = "冷种新名字"
    auto_delete.save_settings(plugin, SaveRequest(expected_revision=1, settings=settings))
    current = plugin._auto_delete_runtime
    assert current.next_due == next_due
    assert current.run(now=1300).items[0].state == "paused"
    assert adapter.actions == ["pause"]


def test_stale_config_revision_cannot_overwrite_saved_rule(monkeypatch):
    """宿主整体配置的旧页面不能把独立规则编辑器的新设置覆盖掉。"""
    plugin, runtime, _, _ = setup_runtime(monkeypatch, name_include="Example")
    old_config = deepcopy(plugin.config)
    old_config["auto_delete_config_revision"] = 1
    settings = runtime.settings.model_copy(deep=True)
    settings.rules[0].name = "已保存的新名字"
    auto_delete.save_settings(plugin, SaveRequest(expected_revision=1, settings=settings))
    plugin.config = old_config
    auto_delete.initialize_runtime(plugin, old_config)
    assert plugin._auto_delete_runtime.settings.rules[0].name == "已保存的新名字"
    assert plugin.config["other_module"] == "保留"


def test_key_change_increments_rule_revision_and_requires_retest(monkeypatch):
    """条件变化清除旧调试回执与正式批准，不自报新修订。"""
    plugin, runtime, _, _ = setup_runtime(monkeypatch, name_include="Example")
    runtime.run(now=1000)
    auto_delete.activate_rule(plugin, ActivateRequest(expected_revision=1, rule_id="rule"))
    settings = plugin._auto_delete_runtime.settings.model_copy(deep=True)
    settings.rules[0].conditions.name_include = "Other"
    result = auto_delete.save_settings(plugin, SaveRequest(expected_revision=2, settings=settings))
    assert result.settings.rules[0].revision == 2 and result.settings.rules[0].mode == "debug"
    assert "rule" not in result.debug_scans and "rule" not in result.approvals


def test_selected_pause_requires_the_displayed_evidence_version(monkeypatch):
    """确认具体暂停清单不能只交一个 ID，须绑定用户实际看到的证据。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    job = runtime.run(now=1000).items[0]
    request = ActivateRequest(expected_revision=1, rule_id="rule", job_ids=[job.id], accept_history=True)
    with pytest.raises(ValueError, match="证据"):
        auto_delete.activate_rule(plugin, request)
    assert adapter.actions == ["pause"]


def test_read_failure_is_not_successful_zero_match_debug(monkeypatch):
    """下载器查询失败没有成功调试回执，不能据此正式启用。"""
    _plugin, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    def failed_poll(*args, **kwargs):
        """模拟离线下载器。"""
        raise RuntimeError("QB 查询失败")
    adapter.poll = failed_poll
    result = runtime.run(now=1000)
    assert result.state == "degraded" and result.errors
    assert runtime.store.control()["debug_scans"] == {}
    assert adapter.actions == []


def test_zero_match_successful_debug_is_reported_honestly(monkeypatch):
    """完整成功查询得到零命中允许用户确认规则，但不冒充实际暂停样本。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="DoesNotMatch")
    result = runtime.run(now=1000)
    assert result.summary.matched == 0 and not result.items
    receipt = runtime.store.control()["debug_scans"]["rule"]
    assert receipt["matched"] == 0 and receipt["paused"] == 0
    auto_delete.activate_rule(plugin, ActivateRequest(expected_revision=1, rule_id="rule"))
    assert adapter.actions == []


def test_stop_after_pause_does_not_remove_task(monkeypatch):
    """已经暂停但尚未发删除时，一键停止阻断后续删除。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    job = runtime.run(now=1000).items[0]
    auto_delete.activate_rule(plugin, ActivateRequest(expected_revision=1, rule_id="rule", job_ids=[job.id],
                                                     evidence_versions={job.id: job.evidence_fingerprint}, accept_history=True))
    current = plugin._auto_delete_runtime
    original_pause = adapter.pause
    def stopped_pause(expected):
        """模拟暂停回包期间收到停止信号。"""
        result = original_pause(expected)
        current.stop.set()
        return result
    adapter.pause = stopped_pause
    current.run(now=1300)
    assert "remove" not in adapter.actions
    assert current.store.get(job.id)["state"] == "review"


def test_reloaded_pending_list_is_not_automatically_replayed(monkeypatch):
    """已批准但未执行的清单重载后转待复核，不自动重放。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    job = runtime.run(now=1000).items[0]
    auto_delete.activate_rule(plugin, ActivateRequest(expected_revision=1, rule_id="rule", job_ids=[job.id],
                                                     evidence_versions={job.id: job.evidence_fingerprint}, accept_history=True))
    auto_delete.initialize_runtime(plugin, plugin.config)
    assert AutoDeleteStore(plugin).get(job.id)["state"] == "review"
    assert adapter.actions == ["pause"]


def test_same_hash_new_identity_does_not_inherit_pause(monkeypatch):
    """后来重新添加的任务不被旧暂停身份封锁，也不能用旧确认删除。"""
    _, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    first = runtime.run(now=1000).items[0]
    adapter.items[first.torrent_hash].added_at = 1500
    adapter.items[first.torrent_hash].state = "uploading"
    second = runtime.run(now=1600).items[0]
    assert second.id != first.id and second.identity != first.identity
    assert adapter.actions == ["pause", "pause"]


def test_change_between_scan_and_pause_is_detected(monkeypatch):
    """名字或标签在扫描后变化，执行器重新核对后保持待复核。"""
    _, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    original = adapter.poll
    def changed_poll(name, **kwargs):
        """定向操作前返回外部修改后的名称。"""
        if kwargs.get("ids"):
            adapter.items["a" * 40].name = "Changed"
        return original(name, **kwargs)
    adapter.poll = changed_poll
    result = runtime.run(now=1000)
    assert result.items[0].state == "review" and adapter.actions == []


def test_restore_is_available_after_module_stop(monkeypatch):
    """停止自动模块后，明确恢复原状态仍可完成。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    job = runtime.run(now=1000).items[0]
    auto_delete.stop_module(plugin)
    result = release_jobs(plugin._auto_delete_runtime, [job.id], restore=True)
    assert result[0]["state"] == "released" and adapter.actions == ["pause", "restore"]


def test_limit_written_by_this_plugin_is_not_cold_seed_evidence(monkeypatch):
    """自身限速造成低吞吐时不增加低速计数或暂停。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, upload_kib_max=10)
    adapter.items["a" * 40].upload_limit_bps = 1024
    plugin._upload_limit_state = {"torrents": {"QB:" + "a" * 40: {"last_written_settings": {"enabled": True, "limit_bps": 1024}}}}
    runtime.run(now=1000)
    runtime.run(now=1300)
    assert runtime.samples == {} and adapter.actions == []


def test_two_debug_rules_cannot_be_bypassed_by_one_confirmation(monkeypatch):
    """同一任务命中两条调试规则，一条正式确认不能撤销另一条保护。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    settings = runtime.settings.model_copy(deep=True)
    other = settings.rules[0].model_copy(update={"id": "other", "name": "另一条"}, deep=True)
    settings.rules.append(other)
    auto_delete.save_settings(plugin, SaveRequest(expected_revision=1, settings=settings))
    current = plugin._auto_delete_runtime
    job = current.run(now=1000).items[0]
    auto_delete.activate_rule(plugin, ActivateRequest(expected_revision=2, rule_id="rule", job_ids=[job.id],
                                                     evidence_versions={job.id: job.evidence_fingerprint}, accept_history=True))
    result = plugin._auto_delete_runtime.run(now=1300)
    assert result.items[0].state == "review" and adapter.actions == ["pause"]


def test_fair_cap_scans_all_candidates_and_leaves_oldest_waiting(monkeypatch):
    """处理上限限制副作用，不限制基础扫描，后面的候选不会长期饥饿。"""
    _, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    runtime.settings.max_tasks = 1
    runtime.plugin.config["auto_delete_max_tasks"] = 1
    for digit in ("b", "c"):
        item = adapter.items["a" * 40].model_copy(update={"hash": digit * 40}, deep=True)
        adapter.items[item.hash] = item
    first = runtime.run(now=1000)
    second = runtime.run(now=1300)
    third = runtime.run(now=1600)
    assert first.summary.scanned == 3
    assert len(first.items) == len(second.items) == len(third.items) == 1
    assert len({first.items[0].torrent_hash, second.items[0].torrent_hash, third.items[0].torrent_hash}) == 3


def test_orphan_detail_is_preserved_and_not_admitted(monkeypatch):
    """详情保存成功但索引失败，保留现场且不放行暂停或删除。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    original = plugin.save_data
    def failed_index(key, value):
        """模拟索引没有成功发布。"""
        if key != "auto_delete_job_index":
            original(key, value)
    plugin.save_data = failed_index
    runtime.run(now=1000)
    assert adapter.actions == [] and runtime.stop.is_set()
    assert any(key.startswith("auto_delete_job_") and key != "auto_delete_job_index" for key in plugin.data)
    assert runtime.store.index() == {}


def test_retirement_protects_old_source_but_accepts_new_source(monkeypatch):
    """主动移除的辅种不被旧母种自动补回，新母种仍按新身份判断。"""
    from app.plugins.downloadmanagerlocal.service.auto_delete_relations import (
        target_retired,
    )

    plugin, runtime, _adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    source = "b" * 40
    plugin.data["iyuu_" + source] = [{"downloader": "QB", "torrents": ["a" * 40]}, {"downloader": "OTHER", "torrents": ["c" * 40]}]
    job = runtime.run(now=1000).items[0]
    assert target_retired(plugin, "QB", "a" * 40, source, 1)
    auto_delete.activate_rule(plugin, ActivateRequest(expected_revision=1, rule_id="rule", job_ids=[job.id],
                                                     evidence_versions={job.id: job.evidence_fingerprint}, accept_history=True))
    assert plugin._auto_delete_runtime.run(now=1300).items[0].state == "removed"
    assert plugin.data["iyuu_" + source] == [{"downloader": "OTHER", "torrents": ["c" * 40]}]
    assert target_retired(plugin, "QB", "a" * 40, source, 1)
    assert not target_retired(plugin, "QB", "a" * 40, source, 1500)


def test_remove_timeout_is_never_automatically_repeated(monkeypatch):
    """发送后超时即便任务实际消失，旧操作也不能在后续扫描重放。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    job = runtime.run(now=1000).items[0]
    auto_delete.activate_rule(plugin, ActivateRequest(expected_revision=1, rule_id="rule", job_ids=[job.id],
                                                     evidence_versions={job.id: job.evidence_fingerprint}, accept_history=True))
    def timed_out(expected):
        """模拟下载器已接受移除但回复超时。"""
        adapter.actions.append("remove")
        adapter.items.pop(expected.hash, None)
        raise RuntimeError("移除请求结果未知")
    adapter.remove = timed_out
    current = plugin._auto_delete_runtime
    current.run(now=1300)
    current.run(now=1600)
    assert adapter.actions.count("remove") == 1 and current.store.get(job.id)["state"] == "review"


def test_fixed_interval_keeps_anchor_and_manual_sample_does_not_move_it(monkeypatch):
    """固定周期从启用起算，手动运行不改变下次自动时间。"""
    _, runtime, _, _ = setup_runtime(monkeypatch, name_include="DoesNotMatch")
    assert runtime.next_due == 1300
    runtime.run(now=1100)
    assert runtime.next_due == 1300
    runtime.run(now=1302, automatic=True)
    assert runtime.next_due == 1600


def test_cron_daily_two_samples_mean_two_days(monkeypatch):
    """每日 Cron 不私自增加后台采样，两个运行点确实相隔一天。"""
    from datetime import datetime

    _, runtime, _, _ = setup_runtime(monkeypatch, upload_kib_max=10)
    runtime.settings.schedule_type = "cron"
    runtime.settings.cron = "0 3 * * *"
    at = datetime(2026, 11, 17, 2, 0, tzinfo=auto_delete.TZ).timestamp()
    first = runtime.compute_due(at)
    second = runtime.compute_due(first)
    assert first - at == 3600 and second - first == 86400


def test_sdk_once_rejection_is_not_reported_as_task_accepted(monkeypatch):
    """宿主未运行或未受理的一次性任务不会留下假运行状态。"""
    plugin, runtime, _, _ = setup_runtime(monkeypatch, name_include="Example")
    plugin._scan_auto_delete = lambda **_: None
    monkeypatch.setattr(auto_delete, "add_plugin_once_job", lambda *_, **__: False)
    with pytest.raises(ValueError, match="未受理"):
        auto_delete.request_run(plugin)
    assert not runtime.once_pending


def test_duplicate_once_request_reuses_existing_run_id(monkeypatch):
    """重复手动请求只受理一个调度任务，反馈相同真实批次标识。"""
    plugin, runtime, _, _ = setup_runtime(monkeypatch, name_include="Example")
    plugin._scan_auto_delete = lambda **_: None
    accepted = []
    def add_once(*args, **kwargs):
        """只记录宿主受理，不执行任务。"""
        accepted.append(kwargs)
        return True
    monkeypatch.setattr(auto_delete, "add_plugin_once_job", add_once)
    first = auto_delete.request_run(plugin)
    second = auto_delete.request_run(plugin)
    assert first.state == "accepted" and second.state == "running"
    assert first.run_id == second.run_id and len(accepted) == 1
    assert accepted[0]["func_kwargs"]["runtime_token"] == runtime.token


def test_terminal_record_with_unreleased_protection_is_visible_for_manual_review(monkeypatch):
    """终态之后保护写入结果未知，重载不静默丢失人工处理入口。"""
    plugin, runtime, _, _ = setup_runtime(monkeypatch, name_include="Example")
    job = runtime.run(now=1000).items[0]
    stored = runtime.store.get(job.id)
    stored.update(state="removed", stage="finished", task_removed=True)
    runtime.store.save(stored)
    auto_delete_config.mark_pending_review(runtime.store)
    assert runtime.store.get(job.id)["state"] == "review"
    assert job.id in plugin.data[BLOCKS_KEY]


def test_scan_reads_only_details_required_by_surviving_rules(monkeypatch):
    _, runtime, adapter, rule = setup_runtime(monkeypatch, name_include="^Example")
    calls = []
    adapter.enrich = lambda row, **fields: calls.append(fields)
    item = next(iter(adapter.items.values()))
    item.seed_seconds = None
    runtime.scan(preview=True, now=1000)
    assert not calls
    rule.conditions.name_include = "^Wrong"
    rule.conditions.seed_hours_min = 1
    runtime.scan(preview=True, now=1000)
    assert not calls
    rule.conditions.name_include = "^Example"
    entries, _, _ = runtime.scan(preview=True, now=1000)
    assert calls == [{"need_trackers": False, "need_seed_time": True}]
    assert entries[0].rules[0].status == "unknown"


@pytest.mark.parametrize("change, retained", [("name", True), ("condition", False), ("interval", False),
                                              ("disable", False), ("running", False)])
def test_host_config_save_retains_only_compatible_idle_samples(monkeypatch, change, retained):
    from app.plugins.downloadmanagerlocal.service import lifecycle

    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, upload_kib_max=10)
    runtime.run(now=1000)
    assert len(runtime.samples) == 1
    plugin.stop_service = lambda: auto_delete.stop_runtime(plugin)
    plugin._transfer_active = plugin._onlyonce = plugin._iyuu_enabled = False
    monkeypatch.setattr(lifecycle, "initialize_runtime_config", lambda plugin, config: config)
    monkeypatch.setattr(lifecycle, "is_speed_monitor_active", lambda _: False)
    monkeypatch.setattr(lifecycle, "is_upload_limit_active", lambda _: False)
    monkeypatch.setattr(lifecycle, "load_upload_limit_state", lambda _: {})
    monkeypatch.setattr(lifecycle, "load_seed_recheck_queue", lambda _: [])
    monkeypatch.setattr(lifecycle, "start_sync_delete", lambda _: None)
    config = plugin.get_config()
    settings = runtime.settings.model_copy(deep=True)
    settings.rules[0].name = "改名"
    if change == "condition":
        settings.rules[0].conditions.upload_kib_max = 8
    elif change == "interval":
        settings.sample_minutes += 1
    elif change == "disable":
        settings.enabled = False
    elif change == "running":
        runtime.run_lock.acquire()
    config.update(config_values(settings, 1))
    plugin.config = config
    try:
        lifecycle.initialize_plugin(plugin, config)
    finally:
        if change == "running":
            runtime.run_lock.release()
    assert not plugin._auto_delete_error
    assert bool(plugin._auto_delete_runtime.samples) == retained
    assert adapter.actions == []
