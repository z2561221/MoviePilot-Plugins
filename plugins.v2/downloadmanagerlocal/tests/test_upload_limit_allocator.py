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


def _pool(model, key, downloader, site, priority, demand=None):
    """构造单个测试站点池。"""
    return model.UploadPool(
        key=key,
        downloader_id=downloader,
        site_key=site,
        priority=priority,
        task_keys=(f"{key}-task",),
        current_rate_bps=0,
        demand_kib=demand,
    )


def test_priority_weights_split_capacity_as_four_two_one():
    """高、中、低优先级满负载时应按 4:2:1 分配。"""
    model = _load("model.upload_limit")
    allocator = importlib.import_module("downloadmanagerlocal.service.upload_allocator")
    pools = [
        _pool(model, "high", "qb", "A", "high"),
        _pool(model, "medium", "qb", "B", "medium"),
        _pool(model, "low", "qb", "C", "low"),
    ]

    result = allocator.allocate_weighted_pools(pools, {"qb": 70}, {})

    assert result == {"high": 40, "medium": 20, "low": 10}


def test_site_hard_cap_is_shared_across_downloaders_and_spare_is_reused():
    """站点硬上限应跨下载器共享，剩余额度由默认组继续使用。"""
    model = _load("model.upload_limit")
    allocator = importlib.import_module("downloadmanagerlocal.service.upload_allocator")
    pools = [
        _pool(model, "qb-site", "qb", "site-a", "high"),
        _pool(model, "qb-default", "qb", model.DEFAULT_SITE_KEY, "medium"),
        _pool(model, "tr-site", "tr", "site-a", "high"),
        _pool(model, "tr-default", "tr", model.DEFAULT_SITE_KEY, "medium"),
    ]

    result = allocator.allocate_weighted_pools(
        pools,
        {"qb": 100, "tr": 100},
        {"site-a": 20},
    )

    assert result["qb-site"] + result["tr-site"] == 20
    assert result["qb-site"] + result["qb-default"] == 100
    assert result["tr-site"] + result["tr-default"] == 100


def test_idle_pool_demand_releases_capacity_to_saturated_pool():
    """未使用完的站点池需求应让饱和池借用剩余额度。"""
    model = _load("model.upload_limit")
    allocator = importlib.import_module("downloadmanagerlocal.service.upload_allocator")
    pools = [
        _pool(model, "idle-high", "qb", "site-a", "high", demand=10),
        _pool(model, "busy-medium", "qb", "site-b", "medium", demand=None),
    ]

    result = allocator.allocate_weighted_pools(pools, {"qb": 100}, {})

    assert result == {"idle-high": 10, "busy-medium": 90}


def test_pool_demand_uses_explicit_probe_elasticity():
    """探测池默认只预留目标额度，仅在下载器无真实上传时保持弹性。"""
    allocator = _load("service.upload_allocator")

    assert allocator.aggregate_pool_demand_kib([5, 0], probe_candidates=3) == 29
    assert allocator.aggregate_pool_demand_kib([0], probe_candidates=3) == 24
    assert allocator.aggregate_pool_demand_kib(
        [0], probe_candidates=3, elastic_probes=True
    ) is None
    assert allocator.aggregate_pool_demand_kib([None], probe_candidates=3) is None


def test_initial_auto_probe_count_reserves_fifteen_percent_of_cap():
    """自动探测初值应约占总额度 15%，并对半数执行向上取整。"""
    allocator = _load("service.upload_allocator")

    assert allocator.initial_auto_probe_count(122, 20) == 2
    assert allocator.initial_auto_probe_count(80, 20) == 2
    assert allocator.initial_auto_probe_count(32, 20) == 1
    assert allocator.initial_auto_probe_count(10_000, 100) == 32
    assert allocator.initial_auto_probe_count(122, 0) == 0


def test_auto_probe_count_changes_one_slot_only_at_batch_boundary():
    """探测数只在两轮批次边界变化，低利用命中时保留并发槽。"""
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
        upload_rate_bps=40 * 1024,
        low_utilization_cycles=0,
        batch_boundary=True,
    ) == (3, 1)
    assert allocator.adjust_auto_probe_count(
        3,
        total_limit_kib=122,
        candidate_count=20,
        upload_rate_bps=110 * 1024,
        low_utilization_cycles=0,
        batch_boundary=True,
    ) == (2, 0)


def test_auto_probe_max_uses_four_kib_concurrency_slots():
    """低利用率并发上限应按每 4 KiB/s 一个槽位计算并保留绝对上限。"""
    allocator = _load("service.upload_allocator")

    assert allocator._max_auto_probe_count(122, 100) == 30
    assert allocator._max_auto_probe_count(32, 100) == 8
    assert allocator._max_auto_probe_count(10_000, 100) == 32


def test_task_allocation_uses_globally_selected_probes_without_second_limit():
    """池内分配不得把全局已选的动态探测任务再次截断。"""
    allocator = _load("service.upload_allocator")
    demands = {"a": None, "b": None, "c": None, "d": 0, "idle": 0}
    result = allocator.allocate_task_limits(
        120,
        demands,
        cycle=3,
        probe_keys={"a", "b", "c"},
    )

    assert result == {"a": 40, "b": 40, "c": 40, "d": 0, "idle": 0}


def test_downloader_probe_slots_follow_weighted_site_rotation_and_hold_two_cycles():
    """下载器全局探测槽应按站点 4/2/1 轮换，并稳定保持两个周期。"""
    model = _load("model.upload_limit")
    allocator = importlib.import_module("downloadmanagerlocal.service.upload_allocator")
    pools = [
        model.UploadPool(
            key="high",
            downloader_id="qb",
            site_key="high",
            priority="high",
            task_keys=("high-a", "high-b", "high-c", "high-d"),
            current_rate_bps=0,
            demand_kib=None,
        ),
        model.UploadPool(
            key="medium",
            downloader_id="qb",
            site_key="medium",
            priority="medium",
            task_keys=("medium-a", "medium-b"),
            current_rate_bps=0,
            demand_kib=None,
        ),
        model.UploadPool(
            key="low",
            downloader_id="qb",
            site_key="low",
            priority="low",
            task_keys=("low-a", "low-b"),
            current_rate_bps=0,
            demand_kib=None,
        ),
    ]
    candidates = {
        task_key
        for pool in pools
        for task_key in pool.task_keys
    }

    first = allocator.select_weighted_probe_keys(
        pools, candidates, target_counts={"qb": 2}, cycle=1
    )
    second = allocator.select_weighted_probe_keys(
        pools, candidates, target_counts={"qb": 2}, cycle=2
    )
    third = allocator.select_weighted_probe_keys(
        pools, candidates, target_counts={"qb": 2}, cycle=3
    )
    fifth = allocator.select_weighted_probe_keys(
        pools, candidates, target_counts={"qb": 2}, cycle=5
    )

    assert first == {"high-a", "medium-a"}
    assert second == first
    assert third == {"high-b", "low-a"}
    assert fifth == {"high-c", "medium-b"}
    assert all(len(selected) <= 2 for selected in (first, second, third, fifth))


def test_weighted_probe_rotation_accepts_dynamic_downloader_target():
    """动态探测数量应继续遵守 4/2/1 站点轮换和两轮保持。"""
    model = _load("model.upload_limit")
    allocator = importlib.import_module("downloadmanagerlocal.service.upload_allocator")
    pools = [
        model.UploadPool(
            key=priority,
            downloader_id="qb",
            site_key=priority,
            priority=priority,
            task_keys=tuple(f"{priority}-{index}" for index in range(8)),
            current_rate_bps=0,
            demand_kib=None,
        )
        for priority in ("high", "medium", "low")
    ]
    candidates = {key for pool in pools for key in pool.task_keys}

    first = allocator.select_weighted_probe_keys(
        pools, candidates, cycle=1, target_counts={"qb": 3}
    )
    second = allocator.select_weighted_probe_keys(
        pools, candidates, cycle=2, target_counts={"qb": 3}
    )
    third = allocator.select_weighted_probe_keys(
        pools, candidates, cycle=3, target_counts={"qb": 3}
    )

    assert first == second
    assert len(first) == len(third) == 3
    assert first != third
    assert sum(key.startswith("high-") for key in first | third) >= 3


def test_active_task_keeps_capacity_while_small_probe_budget_explores_candidates():
    """已有上传任务应保留大部分额度，候选只使用受控探测预算。"""
    allocator = _load("service.upload_allocator")
    demands = {"active": None, "probe-a": None, "probe-b": None, "probe-c": 0}

    result = allocator.allocate_task_limits(
        120,
        demands,
        cycle=1,
        probe_keys={"probe-a", "probe-b"},
    )

    assert result == {
        "active": 104,
        "probe-a": 8,
        "probe-b": 8,
        "probe-c": 0,
    }


def test_finite_active_demand_and_probe_budget_use_the_whole_pool_allocation():
    """有限真实需求满足后，剩余额度应完整交给受控探测任务。"""
    allocator = _load("service.upload_allocator")

    result = allocator.allocate_task_limits(
        53,
        {"active": 5, "probe-a": None, "probe-b": None, "probe-c": 0},
        cycle=1,
        probe_keys={"probe-a", "probe-b"},
    )

    assert result == {
        "active": 5,
        "probe-a": 24,
        "probe-b": 24,
        "probe-c": 0,
    }
    assert sum(result.values()) == 53


def test_task_demand_uses_previous_limit_to_detect_idle_and_saturated_tasks():
    """Peer 需求应区分真正活跃任务与没有上传请求的空闲任务。"""
    allocator = _load("service.upload_allocator")

    assert allocator.estimate_task_demand_kib(0, None, 0) == 0
    assert allocator.estimate_task_demand_kib(0, None, 1) is None
    assert allocator.estimate_task_demand_kib(0, 20, 0) == 0
    assert allocator.estimate_task_demand_kib(0, 20, 1) is None
    assert allocator.is_task_probe_candidate(0, 20, 1) is True
    assert allocator.estimate_task_demand_kib(18 * 1024, 20, 1) is None
    assert allocator.estimate_task_demand_kib(4 * 1024, 20, 1) == 5
    assert allocator.is_task_probe_candidate(4 * 1024, 20, 1) is False


def test_large_idle_fleet_does_not_dilute_one_active_task():
    """大规模空闲种子不应稀释真正有 Peer 需求的任务额度。"""
    allocator = _load("service.upload_allocator")
    demands = {f"idle-{index:04d}": 0 for index in range(3873)}
    demands["active"] = None

    result = allocator.allocate_task_limits(120, demands, cycle=21)

    assert result["active"] == 120
    assert sum(result.values()) == 120
    assert all(
        value == 0 for key, value in result.items() if key != "active"
    )


def test_upload_limit_config_defaults_and_normalization_are_stable():
    """上传限速默认关闭，下载器额度必须为正数，站点规则应收敛。"""
    config = _load("utils.config")

    assert config.UPLOAD_LIMIT_CONFIG_DEFAULTS == {
        "upload_limit_enabled": False,
        "upload_limit_downloaders": [],
        "upload_limit_downloader_limits_kib": {},
        "upload_limit_site_rules": {},
        "upload_limit_grace_minutes": 30,
    }
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
            "NoCap": {"priority": "bad", "limit_kib": -1},
            "": {"priority": "low", "limit_kib": 5},
        },
        "upload_limit_grace_minutes": -5,
    })

    assert normalized == {
        "upload_limit_enabled": True,
        "upload_limit_downloaders": ["QB2", "TR"],
        "upload_limit_downloader_limits_kib": {"QB2": 100},
        "upload_limit_site_rules": {
            "M-Team": {"priority": "high", "limit_kib": 20},
            "NoCap": {"priority": "medium", "limit_kib": 0},
        },
        "upload_limit_grace_minutes": 0,
    }
