"""额度阶段的只读边界、探测迟滞与摘要各层口径。"""

import gc
import weakref
from copy import deepcopy

import pytest
from app.plugins.downloadmanagerlocal.model.upload_limit import (
    TorrentUploadSettings,
    UploadTorrentSnapshot,
)
from app.plugins.downloadmanagerlocal.model.upload_scan import UploadDownloaderContext
from app.plugins.downloadmanagerlocal.service.upload_limit_plan import (
    allocate_upload_plan,
    next_probe_budget,
    prepare_pool_inputs,
    resolve_pool_demands,
    task_upload_rates,
)
from app.plugins.downloadmanagerlocal.service.upload_limit_summary import (
    build_downloader_only_summary,
    build_site_summary,
)


def snapshot(key, *, rate=0, peers=1):
    """只创建领域快照，不连接下载器。"""
    return UploadTorrentSnapshot(
        "A", "qbittorrent", key, key, ("🏠Site",), "uploading", True, 1, 2,
        rate, peers, TorrentUploadSettings(0, False),
    )


def test_plan_keeps_elastic_upload_and_probe_budget_without_changing_records():
    """有上传需求的任务与探测按既有预算共享额度，输入状态保持只读。"""
    tasks = {key: snapshot(key, rate=8192 if key == "upload" else 0, peers=0 if key == "idle" else 1)
             for key in ["upload", "probe", "idle"]}
    records = {key: {"site_key": "Site", "last_allocation_kib": 10} for key in tasks}
    before = deepcopy(records)
    inputs = prepare_pool_inputs(tasks, records)
    pools = resolve_pool_demands(inputs, {"probe"})
    plan = allocate_upload_plan(pools, inputs.demands, {"probe"}, {"A": 24},
                                {"Site": {"limit_kib": 20}}, cycle=1)
    assert plan.task_limits == {"upload": 12, "probe": 8, "idle": 0}
    assert plan.probing_task_keys == {"probe"}
    assert sum(plan.pool_allocations.values()) == 20 and records == before


@pytest.mark.parametrize("entry,rate,cycle,expected", [
    ({}, 0, 1, (2, 0, False)),
    ({"auto_probe_count": 3, "probe_low_utilization_cycles": 1}, 0, 2, (3, 2, False)),
    ({"auto_probe_count": 3, "probe_low_utilization_cycles": 1}, 0, 3, (4, 0, False)),
    ({"auto_probe_count": 3}, 128 * 1024, 2, (3, 0, True)),
    ({"auto_probe_count": 3, "probe_reduction_pending": True}, 0, 3, (2, 0, False)),
])
def test_probe_budget_preserves_two_cycle_hysteresis_and_does_not_write(entry, rate, cycle, expected):
    """利用率变化只计算下一计数，写入时间由协调层决定。"""
    before = deepcopy(entry)
    result = next_probe_budget(entry, cap_kib=128, candidates=5, upload_rate_bps=rate, cycle=cycle)
    assert (result.count, result.low_utilization_cycles, result.reduction_pending) == expected
    assert entry == before


class NoServiceAccess:
    """投影若越过扫描边界读取服务立即失败。"""

    def __getattribute__(self, name):
        """所有服务访问都不属于纯投影。"""
        raise AssertionError("summary accessed service: " + name)


def test_summary_preserves_separate_global_downloader_and_site_metrics():
    """宽限、未受限及残留记录按不同口径汇总，不把分配计划当写入成功。"""
    active, grace, untagged = snapshot("active", rate=1024), snapshot("grace", rate=2048), snapshot("free", rate=4096)
    context = UploadDownloaderContext("A", NoServiceAccess(), "qbittorrent", {},
                                      {"active": active, "grace": grace, "free": untagged}, False)
    state = {"last_run_at": 1000, "cycle": 3, "downloaders": {
        "A": {"auto_probe_count": 2}, "B": {"downloader_type": "transmission"}}, "torrents": {
        "active": {"downloader_id": "A", "site_key": "Site", "last_allocation_kib": 2},
        "old": {"downloader_id": "A", "last_allocation_kib": 7},
        "grace": {"downloader_id": "A", "last_allocation_kib": 6, "grace_until": 2000},
        "bad": [], "foreign": {"downloader_id": ["invalid"], "last_allocation_kib": 100},
    }}
    before = deepcopy(state)
    result = build_site_summary(state=state, selected=["B", "A"], caps={"A": 20, "B": 10},
                                contexts={"A": context}, regular_tasks={"active": active},
                                grace_tasks={"grace": grace}, pool_allocations={"pool": 12},
                                site_rules={"Site": {"limit_kib": 20}}, probing_task_keys={"active"},
                                errors={"B": ["offline"]}, reason="test")
    assert result["service_status"] == "degraded" and result["errors"] == ["B: offline"]
    assert (result["managed_torrents"], result["grace_torrents"], result["uploading_torrents"]) == (1, 1, 2)
    assert result["upload_rate_bps"] == 7168 and result["allocated_kib"] == 12
    b, a = result["downloaders"]
    assert b["id"] == "B" and b["allocated_kib"] == 0 and b["type"] == "transmission"
    assert a["allocated_kib"] == 9 and a["uploading_torrents"] == 3 and a["auto_probe_count"] == 2
    assert result["sites"][0]["allocated_kib"] == 2 and state == before


def test_downloader_only_projection_uses_snapshots_without_service_reads():
    """没有站点策略时总额度只对成功扫描的下载器记分配值。"""
    task = snapshot("one", rate=1024)
    context = UploadDownloaderContext("A", NoServiceAccess(), "qbittorrent", {}, {"one": task}, False)
    result = build_downloader_only_summary(state={}, selected=["B", "A"], caps={"A": 20, "B": 10},
                                          contexts={"A": context}, errors={"B": ["offline"]}, reason="test")
    assert result["allocated_kib"] == 20 and result["managed_torrents"] == 1
    assert result["downloaders"][0]["allocated_kib"] == 0 and result["mode"] == "downloader_only"


def test_numeric_phase_results_do_not_keep_snapshot_or_service_graph_alive():
    """阶段结果仅保留key/数字，删除输入后快照可立即回收。"""
    task = snapshot("one", rate=1024)
    reference = weakref.ref(task)
    tasks = {"one": task}
    inputs = prepare_pool_inputs(tasks, {"one": {"site_key": "Site"}})
    pools = resolve_pool_demands(inputs, set())
    plan = allocate_upload_plan(pools, inputs.demands, set(), {"A": 20}, {"Site": {"limit_kib": 20}}, cycle=1)
    assert task_upload_rates(tasks, {}, ["A", "B"]) == {"A": 1024, "B": 0}
    del task, tasks
    gc.collect()
    assert reference() is None and plan.task_limits["one"] == 20
