"""独立扫描与计划清理的行为回归，外部操作全部由替身记录。"""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event, Thread

import pytest
from app.plugins.localtoolkit.model.cleanup_config import normalize_cleanup_config
from app.plugins.localtoolkit.service.library_cleanup import LibraryCleanupModule
from app.plugins.localtoolkit.service.lifecycle import (
    build_services,
    initialize_plugin,
    stop_plugin_service,
)

from .test_cleanup_run import FakePlugin, build_module


def test_legacy_configuration_preserves_cadence_and_disabled_notifications():
    """已有实例迁移后两个周期独立，但不自动提高删除频率。"""
    config = normalize_cleanup_config({"enabled": True, "cron": "9 1 * * *", "notify": False})
    for prefix in ("scan", "cleanup"):
        assert config[f"{prefix}_enabled"] is True
        assert config[f"{prefix}_cron"] == "9 1 * * *"
        assert config[f"{prefix}_notify"] is False
    explicit = normalize_cleanup_config({**config, "notify": True, "cleanup_enabled": False, "scan_cron": ""})
    assert explicit["scan_notify"] is False and explicit["cleanup_enabled"] is False
    assert explicit["scan_cron"] == ""


def test_schedulers_are_independent_and_invalid_scan_cron_does_not_disable_cleanup():
    """两个服务使用独立 ID、回调与周期，重复读取不重复注册。"""
    module, _plugin, _adapter = build_module({}, scan_enabled=True, cleanup_enabled=True)
    services = module.get_service()
    assert len(services) == 2 and len({item["id"] for item in services}) == 2
    assert [item["func"].__name__ for item in services] == ["scan_plan", "run_once"]
    assert all(item["func_kwargs"] == {"scheduled": True} for item in services)
    assert [item["id"] for item in module.get_service()] == [item["id"] for item in services]
    module.config["scan_cron"] = "not a cron"
    assert [item["func"].__name__ for item in module.get_service()] == ["run_once"]
    module.config["cleanup_enabled"] = False
    assert module.get_service() == []


def test_scan_only_adds_plan_and_changed_report_then_cleanup_never_rescans():
    """生成计划不删除，随后清理只访问本批条目。"""
    module, plugin, adapter = build_module({"a": [False], "b": [False]})
    plugin.data["library_cleanup_plan"]["items"] = []
    scan = module.scan_plan()
    assert scan["queued_added"] == 2 and scan["scanned_count"] == 2
    assert not adapter.deleted and not adapter.checked and not adapter.prechecked
    assert len(plugin.notifiers) == 1
    assert plugin.notifiers[0].calls[0][1] == "清理计划更新"
    assert "<b>清理计划更新</b>" not in plugin.notifiers[0].calls[0][2]
    assert "当前待清理：2 部" in plugin.notifiers[0].calls[0][2]
    assert module.run_once()["success_count"] == 2
    assert adapter.scans == 1


def test_unchanged_scan_is_quiet_and_does_not_change_cleanup_cooldown():
    """快照日期更新不会刷通知，扫描不会重置清理冷却。"""
    module, plugin, adapter = build_module({"a": [False]})
    previous = datetime.now(timezone.utc).isoformat()
    plugin.data["library_cleanup_plan"]["last_cycle_at"] = previous
    result = module.scan_plan()
    assert result["queued_added"] == result["queued_removed"] == 0
    assert adapter.scans == 1 and not adapter.deleted and not plugin.notifiers
    assert plugin.data["library_cleanup_plan"]["last_cycle_at"] == previous
    assert module.run_once()["cooldown"] is True
    assert not adapter.prechecked


def test_scan_removes_now_ineligible_items_but_keeps_unknown_snapshots():
    """收藏后移出计划，缺失筛选字段的旧条目保留待后续复核。"""
    module, plugin, adapter = build_module({"a": [False], "b": [False]})
    adapter.inventory["a"].favorite = True
    adapter.inventory["b"].favorite = None
    result = module.scan_plan()
    assert result["queued_removed"] == 1
    assert [item["movie_id"] for item in plugin.data["library_cleanup_plan"]["items"]] == ["b"]
    assert not adapter.deleted


def test_scan_failure_after_partial_results_preserves_the_entire_original_plan():
    """网络中断时不把已读的一页当成完整媒体库。"""
    module, plugin, adapter = build_module({"a": [False], "b": [False]})
    previous = deepcopy(plugin.data["library_cleanup_plan"])

    def incomplete_scan(_config):
        yield adapter.inventory["a"]
        raise TimeoutError("second page unavailable")

    adapter.iter_candidates = incomplete_scan
    assert module.scan_plan()["success"] is False
    assert plugin.data["library_cleanup_plan"] == previous
    assert len(plugin.notifiers) == 1
    assert module.scan_plan()["success"] is False
    assert len(plugin.notifiers) == 1


def test_scan_preserves_same_item_id_on_different_servers():
    """候选去重与计划身份都必须包含服务器。"""
    module, plugin, adapter = build_module({"a": [False]})
    first = adapter.inventory["a"]
    second = replace(first, server="second-server")
    adapter.iter_candidates = lambda _config: [first, second]
    result = module.scan_plan()
    assert result["qualified_count"] == 2 and result["queue_count"] == 2
    assert {item["server"] for item in plugin.data["library_cleanup_plan"]["items"]} == {"emby", "second-server"}


@pytest.mark.parametrize("condition", ["favorite", "scope", "absent", "unknown", "fields"])
def test_precheck_prevents_stale_plan_deletion(condition):
    """旧计划不具备删除资格，必须以当前范围和本次实时状态判定。"""
    module, plugin, adapter = build_module({"a": [False]})
    if condition == "favorite":
        adapter.inventory["a"].favorite = True
    elif condition == "scope":
        module.config["selected_library"] = "another-library"
    elif condition == "absent":
        adapter.preflight["a"] = (False, None)
    elif condition == "unknown":
        adapter.preflight["a"] = TimeoutError("read unavailable")
    else:
        adapter.inventory["a"].favorite = None
    result = module.run_once()
    assert not adapter.deleted and not adapter.checked and not adapter.scans
    retained = condition in ("unknown", "fields")
    assert len(plugin.data["library_cleanup_plan"]["items"]) == int(retained)
    assert result["success"] is not retained
    if retained:
        assert plugin.data["library_cleanup_plan"]["items"][0]["attempts"] == 1
        assert result["unknown_count"] == 1
    elif condition == "absent":
        assert result["already_absent_count"] == 1 and result["success_count"] == 0
    else:
        assert result["skipped_count"] == 1


def test_precheck_skips_do_not_expand_this_cycle_beyond_configured_batch():
    """本批有失效项时也不越过已选择的数量继续扫整份队列。"""
    module, plugin, adapter = build_module({str(i): [False] for i in range(5)}, auto_delete_max_count=2)
    adapter.inventory["4"].favorite = True
    result = module.run_once()
    assert [item for item, _user in adapter.prechecked] == ["4", "3"]
    assert adapter.deleted == ["3"] and result["processed_count"] == 2
    assert len(plugin.data["library_cleanup_plan"]["items"]) == 3


def test_notifications_are_independent_and_unknown_state_is_deduplicated_until_recovery():
    """连续无法核验时不刷屏，恢复后发一次恢复及本批结果。"""
    module, plugin, adapter = build_module({"a": [False]}, cycle_cooldown_minutes=0)
    adapter.preflight["a"] = (None, None)
    assert module.run_once()["success"] is False
    assert module.run_once()["success"] is False
    assert len(plugin.notifiers) == 1
    adapter.preflight.clear()
    assert module.run_once()["success"] is True
    titles = [call[1] for notifier in plugin.notifiers for call in notifier.calls]
    assert titles.count("周期清理异常") == 1 and titles.count("周期清理恢复") == 1


def test_disabling_cleanup_notifications_does_not_disable_scan_notifications():
    """两个通知开关互不影响实际扫描、删除与复核。"""
    module, plugin, adapter = build_module({"a": [False]}, scan_notify=True, cleanup_notify=False)
    plugin.data["library_cleanup_plan"]["items"] = []
    module.scan_plan()
    module.run_once()
    assert adapter.deleted == ["a"] and adapter.checked
    assert len(plugin.notifiers) == 1
    assert plugin.notifiers[0].calls[0][1] == "清理计划更新"


def test_scan_and_cleanup_share_lock_and_disabled_scheduled_callbacks_are_noops():
    """独立调度不代表可以同时读写计划，关闭后遗留回调也不能执行。"""
    module, plugin, adapter = build_module({"a": [False]})
    module._run_lock.acquire()
    try:
        assert module.scan_plan()["busy"] is True
        assert module.run_once()["busy"] is True
    finally:
        module._run_lock.release()
    module.scan_plan(scheduled=True)
    module.run_once(scheduled=True)
    assert not adapter.scans and not adapter.deleted and not adapter.prechecked and not plugin.notifiers


def test_new_module_instance_reuses_persisted_cleanup_cooldown():
    """重新加载模块后仍受上次清理时间约束。"""
    module, plugin, adapter = build_module({"a": [False]})
    plugin.data["library_cleanup_plan"]["last_cycle_at"] = datetime.now(timezone.utc).isoformat()
    reloaded = LibraryCleanupModule(plugin, adapter)
    reloaded.load_config(module.config)
    assert reloaded.run_once()["cooldown"] is True
    assert not adapter.deleted and not adapter.scans
    plugin.data["library_cleanup_plan"]["last_cycle_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    assert reloaded.get_cleanup_plan()["next_cycle_at"] == ""


def test_scheduled_cooldown_creates_one_persisted_retry_trigger():
    """周期冷却只登记一次 DateTrigger，手动跳过不登记。"""
    module, plugin, _adapter = build_module({"a": [False]}, cleanup_enabled=True,
                                           cycle_cooldown_minutes=60, cleanup_notify=False)
    plugin.data["library_cleanup_plan"]["last_cycle_at"] = datetime.now(timezone.utc).isoformat()
    manual = module.run_once()
    assert manual["cooldown"] and "pending_cycle_at" not in plugin.data["library_cleanup_plan"]
    scheduled = module.run_once(scheduled=True)
    assert scheduled["retry_scheduled"]
    pending = plugin.data["library_cleanup_plan"]["pending_cycle_at"]
    services = module.get_service()
    retry = [item for item in services if item["id"].endswith("cooldown_retry")]
    assert len(retry) == 1 and retry[0]["func_kwargs"] == {"scheduled": True, "retry": True}
    module.run_once(scheduled=True)
    assert plugin.data["library_cleanup_plan"]["pending_cycle_at"] == pending
    assert not _adapter.deleted


def test_retry_consumes_pending_intent_and_clear_cancels_it():
    """补跑执行后消费意图，清空计划撤销意图。"""
    module, plugin, _adapter = build_module({"a": [False]}, cleanup_enabled=True,
                                           cycle_cooldown_minutes=1, cleanup_notify=False)
    plugin.data["library_cleanup_plan"]["pending_cycle_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    plugin.data["library_cleanup_plan"]["last_cycle_at"] = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    result = module.run_once(scheduled=True, retry=True)
    assert result["success"] and not plugin.data["library_cleanup_plan"]["pending_cycle_at"]
    plugin.data["library_cleanup_plan"]["pending_cycle_at"] = datetime.now(timezone.utc).isoformat()
    module.clear_cleanup_plan()
    assert not plugin.data["library_cleanup_plan"]["pending_cycle_at"]


def test_reinitialization_migrates_saved_config_and_keeps_inflight_batch_lock():
    """配置保存及重复初始化不会放开正在运行的清理锁。"""
    plugin = FakePlugin()
    saved = []
    plugin.update_config = lambda value: saved.append(deepcopy(value))
    initialize_plugin(plugin, {"enabled": True, "migration_done": True,
                               "library_cleanup": {"enabled": True, "cron": "9 1 * * *", "notify": False}})
    assert len(saved) == 1 and saved[0]["library_cleanup"]["scan_notify"] is False
    first = plugin.library_cleanup
    first._run_lock.acquire()
    try:
        initialize_plugin(plugin, deepcopy(plugin._config))
        assert first.config["scan_enabled"] is False
        assert plugin.library_cleanup.run_once()["busy"] is True
        assert len(build_services(plugin)) == 2
    finally:
        first._run_lock.release()
    stop_plugin_service(plugin)
    stop_plugin_service(plugin)
    assert build_services(plugin) == []
    plugin._enabled = False
    assert build_services(plugin) == []


def test_fresh_candidate_with_changed_id_is_retained_without_deletion():
    """外部适配器返回身份错误时也不能操作另一个条目。"""
    module, plugin, adapter = build_module({"a": [False]})
    adapter.preflight["a"] = (True, replace(adapter.inventory["a"], movie_id="other"))
    assert module.run_once()["unknown_count"] == 1
    assert not adapter.deleted
    assert plugin.data["library_cleanup_plan"]["items"][0]["last_error"] == "删除前条目身份不一致"


def test_unknown_then_eligible_later_item_is_not_starved():
    """失败项放回队首，倒序清理下轮能够继续处理其余计划。"""
    module, _plugin, adapter = build_module({"a": [False], "b": [False]}, auto_delete_max_count=1,
                                         cycle_cooldown_minutes=0, cleanup_notify=False)
    adapter.preflight["b"] = (None, None)
    assert module.run_once()["success"] is False
    assert module.run_once()["success"] is True
    assert adapter.deleted == ["a"]


@pytest.mark.parametrize("disable_while_waiting", [False, True])
def test_simultaneous_schedules_wait_in_sequence_instead_of_starving_cleanup(disable_while_waiting):
    """旧周期相同时，清理等待扫描结束后执行，不能每次被跳过。"""
    module, plugin, adapter = build_module({"a": [False]}, scan_enabled=True, cleanup_enabled=True,
                                         scan_notify=False, cleanup_notify=False)
    plugin.data["library_cleanup_plan"]["items"] = []
    scanning = Event()
    release_scan = Event()
    entered_cleanup = Event()
    cleanup_finished = Event()
    results = {}
    original_scan = adapter.iter_candidates

    def scan_candidates(config):
        scanning.set()
        assert release_scan.wait(3)
        return original_scan(config)

    def cleanup():
        entered_cleanup.set()
        try:
            results["cleanup"] = module.run_once(scheduled=True)
        finally:
            cleanup_finished.set()

    adapter.iter_candidates = scan_candidates
    scan_thread = Thread(target=lambda: results.update(scan=module.scan_plan(scheduled=True)))
    cleanup_thread = Thread(target=cleanup)
    scan_thread.start()
    try:
        assert scanning.wait(3)
        cleanup_thread.start()
        assert entered_cleanup.wait(3)
        assert not cleanup_finished.wait(0.1)
        if disable_while_waiting:
            module.config["cleanup_enabled"] = False
    finally:
        release_scan.set()
        scan_thread.join(3)
        if cleanup_thread.ident is not None:
            cleanup_thread.join(3)
    assert not scan_thread.is_alive() and not cleanup_thread.is_alive()
    assert results["scan"]["success"] is True and results["cleanup"]["success"] is True
    assert adapter.scans == 1
    assert adapter.deleted == ([] if disable_while_waiting else ["a"])
