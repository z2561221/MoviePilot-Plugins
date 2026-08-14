from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path


PLUGIN_DIR = Path(
    os.environ.get("DOWNLOADMANAGERLOCAL_PLUGIN_DIR")
    or Path(__file__).resolve().parents[1]
)


def _load(module_name: str):
    """加载不执行插件入口的上传限速纯逻辑模块。"""
    for name in list(sys.modules):
        if name == "downloadmanagerlocal" or name.startswith("downloadmanagerlocal."):
            sys.modules.pop(name)
    package = types.ModuleType("downloadmanagerlocal")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["downloadmanagerlocal"] = package
    return importlib.import_module(f"downloadmanagerlocal.{module_name}")


def _pool(model, key, downloader, site, demand=None, task_count=1):
    """构造单个受限站点测试池。"""
    return model.UploadPool(
        key=key,
        downloader_id=downloader,
        site_key=site,
        task_keys=tuple(f"{key}-task-{index}" for index in range(task_count)),
        current_rate_bps=0,
        demand_kib=demand,
    )


def test_site_pools_share_downloader_capacity_equally_without_priority():
    """多个满负载站点不再按优先级偏置，应等权共享下载器额度。"""
    model = _load("model.upload_limit")
    allocator = importlib.import_module("downloadmanagerlocal.service.upload_allocator")
    pools = [
        _pool(model, "a", "qb", "A"),
        _pool(model, "b", "qb", "B"),
        _pool(model, "c", "qb", "C"),
    ]

    result = allocator.allocate_site_pools(
        pools,
        {"qb": 70},
        {"A": 70, "B": 70, "C": 70},
    )

    assert sum(result.values()) == 70
    assert max(result.values()) - min(result.values()) <= 1


def test_site_limit_is_shared_across_downloaders_and_spare_is_reused():
    """同一站点合计上限跨下载器共享，剩余下载器额度可供其他受限站点使用。"""
    model = _load("model.upload_limit")
    allocator = importlib.import_module("downloadmanagerlocal.service.upload_allocator")
    pools = [
        _pool(model, "qb-a", "qb", "A"),
        _pool(model, "qb-b", "qb", "B"),
        _pool(model, "tr-a", "tr", "A"),
        _pool(model, "tr-c", "tr", "C"),
    ]

    result = allocator.allocate_site_pools(
        pools,
        {"qb": 100, "tr": 100},
        {"A": 20, "B": 100, "C": 100},
    )

    assert result["qb-a"] + result["tr-a"] == 20
    assert result["qb-a"] + result["qb-b"] == 100
    assert result["tr-a"] + result["tr-c"] == 100


def test_idle_pool_demand_releases_capacity_to_saturated_pool():
    """需求较小的站点池应把下载器余量让给仍有需求的站点池。"""
    model = _load("model.upload_limit")
    allocator = importlib.import_module("downloadmanagerlocal.service.upload_allocator")
    pools = [
        _pool(model, "idle", "qb", "A", demand=10),
        _pool(model, "busy", "qb", "B", demand=None),
    ]

    result = allocator.allocate_site_pools(
        pools,
        {"qb": 100},
        {"A": 100, "B": 100},
    )

    assert result == {"idle": 10, "busy": 90}


def test_pool_demand_uses_explicit_probe_elasticity():
    """探测池默认只预留目标额度，无真实上传时允许继续借用余量。"""
    allocator = _load("service.upload_allocator")

    assert allocator.aggregate_pool_demand_kib([5, 0], probe_candidates=3) == 29
    assert allocator.aggregate_pool_demand_kib([0], probe_candidates=3) == 24
    assert allocator.aggregate_pool_demand_kib(
        [0], probe_candidates=3, elastic_probes=True
    ) is None
    assert allocator.aggregate_pool_demand_kib([None], probe_candidates=3) is None


def test_initial_auto_probe_count_reserves_fifteen_percent_of_cap():
    """自动探测初值应约占下载器总额度 15%。"""
    allocator = _load("service.upload_allocator")

    assert allocator.initial_auto_probe_count(122, 20) == 2
    assert allocator.initial_auto_probe_count(80, 20) == 2
    assert allocator.initial_auto_probe_count(32, 20) == 1
    assert allocator.initial_auto_probe_count(10_000, 100) == 32
    assert allocator.initial_auto_probe_count(122, 0) == 0


def test_auto_probe_count_changes_one_slot_only_at_batch_boundary():
    """探测数量只在两轮批次边界平滑增减一个。"""
    allocator = _load("service.upload_allocator")

    assert allocator.adjust_auto_probe_count(
        2,
        total_limit_kib=122,
        candidate_count=20,
        upload_rate_bps=40 * 1024,
        low_utilization_cycles=0,
        batch_boundary=False,
    ) == (2, 1)
    assert allocator.adjust_auto_probe_count(
        2,
        total_limit_kib=122,
        candidate_count=20,
        upload_rate_bps=40 * 1024,
        low_utilization_cycles=1,
        batch_boundary=True,
    ) == (3, 0)
    assert allocator.adjust_auto_probe_count(
        3,
        total_limit_kib=122,
        candidate_count=20,
        upload_rate_bps=110 * 1024,
        low_utilization_cycles=0,
        batch_boundary=True,
    ) == (2, 0)


def test_auto_probe_max_uses_four_kib_concurrency_slots():
    """探测并发上限按每 4 KiB/s 一个槽位并保留绝对上限。"""
    allocator = _load("service.upload_allocator")

    assert allocator._max_auto_probe_count(122, 100) == 30
    assert allocator._max_auto_probe_count(32, 100) == 8
    assert allocator._max_auto_probe_count(10_000, 100) == 32


def test_probe_slots_rotate_equally_across_limited_sites_and_hold_two_cycles():
    """探测槽应在受限站点间等权轮换，并稳定保持两个周期。"""
    model = _load("model.upload_limit")
    allocator = importlib.import_module("downloadmanagerlocal.service.upload_allocator")
    pools = [
        _pool(model, "A", "qb", "A", task_count=4),
        _pool(model, "B", "qb", "B", task_count=4),
        _pool(model, "C", "qb", "C", task_count=4),
    ]
    candidates = {key for pool in pools for key in pool.task_keys}

    first = allocator.select_probe_keys(
        pools, candidates, target_counts={"qb": 2}, cycle=1
    )
    second = allocator.select_probe_keys(
        pools, candidates, target_counts={"qb": 2}, cycle=2
    )
    third = allocator.select_probe_keys(
        pools, candidates, target_counts={"qb": 2}, cycle=3
    )

    assert first == second
    assert len(first) == len(third) == 2
    assert first != third
    assert {key.split("-", 1)[0] for key in first} == {"A", "B"}
    assert {key.split("-", 1)[0] for key in third} == {"A", "C"}


def test_task_allocation_preserves_active_capacity_and_probe_budget():
    """已有上传任务保留主要额度，候选任务只使用受控探测预算。"""
    allocator = _load("service.upload_allocator")
    result = allocator.allocate_task_limits(
        120,
        {"active": None, "probe-a": None, "probe-b": None, "idle": 0},
        cycle=1,
        probe_keys={"probe-a", "probe-b"},
    )

    assert result == {
        "active": 104,
        "probe-a": 8,
        "probe-b": 8,
        "idle": 0,
    }


def test_finite_active_demand_and_probes_use_whole_pool_allocation():
    """有限真实需求满足后，余量应完整交给已选探测任务。"""
    allocator = _load("service.upload_allocator")
    result = allocator.allocate_task_limits(
        53,
        {"active": 5, "probe-a": None, "probe-b": None, "idle": 0},
        cycle=1,
        probe_keys={"probe-a", "probe-b"},
    )

    assert result == {
        "active": 5,
        "probe-a": 24,
        "probe-b": 24,
        "idle": 0,
    }


def test_task_demand_distinguishes_idle_and_saturated_tasks():
    """Peer 需求应区分真实活跃任务和无上传请求的空闲任务。"""
    allocator = _load("service.upload_allocator")

    assert allocator.estimate_task_demand_kib(0, None, 0) == 0
    assert allocator.estimate_task_demand_kib(0, None, 1) is None
    assert allocator.estimate_task_demand_kib(0, 20, 0) == 0
    assert allocator.estimate_task_demand_kib(0, 20, 1) is None
    assert allocator.is_task_probe_candidate(0, 20, 1) is True
    assert allocator.estimate_task_demand_kib(18 * 1024, 20, 1) is None
    assert allocator.estimate_task_demand_kib(4 * 1024, 20, 1) == 5


def test_large_idle_fleet_does_not_dilute_one_active_task():
    """大规模空闲种子不应稀释真正有 Peer 需求的任务额度。"""
    allocator = _load("service.upload_allocator")
    demands = {f"idle-{index:04d}": 0 for index in range(3873)}
    demands["active"] = None

    result = allocator.allocate_task_limits(120, demands, cycle=21)

    assert result["active"] == 120
    assert sum(result.values()) == 120


def test_upload_limit_config_removes_priority_and_preserves_empty_site_limits():
    """旧优先级字段应被移除，零值站点继续保留为已扫描但不限速。"""
    config = _load("utils.config")
    normalized = config.normalize_upload_limit_config({
        "upload_limit_enabled": 1,
        "upload_limit_downloaders": ["QB2", "", "QB2", 1, "TR"],
        "upload_limit_downloader_limits_kib": {
            "QB2": "100",
            "TR": 0,
            "bad": "fast",
        },
        "upload_limit_site_rules": {
            " M-Team ": {"priority": "HIGH", "limit_kib": "20"},
            "NoCap": {"priority": "low", "limit_kib": 0},
            "": {"limit_kib": 5},
        },
        "upload_limit_grace_minutes": -5,
    })

    assert normalized == {
        "upload_limit_enabled": True,
        "upload_limit_downloaders": ["QB2", "TR"],
        "upload_limit_downloader_limits_kib": {"QB2": 100},
        "upload_limit_site_rules": {
            "M-Team": {"limit_kib": 20},
            "NoCap": {"limit_kib": 0},
        },
        "upload_limit_grace_minutes": 0,
    }
