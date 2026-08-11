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


def test_task_probe_slots_rotate_when_budget_is_smaller_than_task_count():
    """额度不足以给全部任务 1 KiB/s 时应轮换探测槽，避免固定饿死。"""
    allocator = _load("service.upload_allocator")
    demands = {"a": None, "b": None, "c": None, "d": None}

    first = allocator.allocate_task_limits(2, demands, cycle=0)
    second = allocator.allocate_task_limits(2, demands, cycle=1)

    assert first == {"a": 1, "b": 1, "c": 0, "d": 0}
    assert second == {"a": 0, "b": 1, "c": 1, "d": 0}


def test_task_demand_uses_previous_limit_to_detect_idle_and_saturated_tasks():
    """Peer 需求应区分真正活跃任务与没有上传请求的空闲任务。"""
    allocator = _load("service.upload_allocator")

    assert allocator.estimate_task_demand_kib(0, None, 0) == 0
    assert allocator.estimate_task_demand_kib(0, None, 1) is None
    assert allocator.estimate_task_demand_kib(0, 20, 0) == 0
    assert allocator.estimate_task_demand_kib(0, 20, 1) == 1
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
