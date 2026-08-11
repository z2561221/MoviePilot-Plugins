"""上传额度纯逻辑分配器。"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, Optional

from ..model.upload_limit import UploadPool


_EPSILON = 1e-9


def estimate_task_demand_kib(
    upload_rate_bps: int,
    previous_limit_kib: Optional[int],
) -> Optional[int]:
    """根据上一轮限额与实时上传估算任务需求，None 表示仍可继续借额。"""
    if previous_limit_kib is None:
        return None
    previous = max(0, int(previous_limit_kib))
    current_bps = max(0, int(upload_rate_bps or 0))
    if previous <= 0:
        return 1
    if current_bps >= previous * 1024 * 0.8:
        return None
    return max(1, int(math.ceil(current_bps / 1024 * 1.25)))


def aggregate_pool_demand_kib(values: Iterable[Optional[int]]) -> Optional[int]:
    """聚合任务需求；任一任务仍饱和时整个站点池保持弹性需求。"""
    normalized = list(values)
    if any(value is None for value in normalized):
        return None
    return sum(max(0, int(value or 0)) for value in normalized)


def allocate_weighted_pools(
    pools: Iterable[UploadPool],
    downloader_caps_kib: dict[str, int],
    site_caps_kib: dict[str, int],
) -> dict[str, int]:
    """按下载器总额度、站点共享硬上限与 4/2/1 权重分配站点池。"""
    pool_map = {pool.key: pool for pool in pools}
    if not pool_map:
        return {}
    remaining_downloader = {
        key: float(max(0, int(value or 0)))
        for key, value in downloader_caps_kib.items()
    }
    remaining_site = {
        key: float(max(0, int(value or 0)))
        for key, value in site_caps_kib.items()
        if int(value or 0) > 0
    }
    remaining_demand = {
        key: (None if pool.demand_kib is None else float(max(0, pool.demand_kib)))
        for key, pool in pool_map.items()
    }
    allocations = {key: 0.0 for key in pool_map}
    active = {
        key for key, pool in pool_map.items()
        if remaining_downloader.get(pool.downloader_id, 0.0) > _EPSILON
        and remaining_site.get(pool.site_key, 1.0) > _EPSILON
        and (remaining_demand[key] is None or remaining_demand[key] > _EPSILON)
    }

    for _ in range(max(12, len(pool_map) * 6)):
        if not active:
            break
        by_downloader: dict[str, list[str]] = defaultdict(list)
        for key in active:
            by_downloader[pool_map[key].downloader_id].append(key)
        proposals: dict[str, float] = {}
        for downloader_id, keys in by_downloader.items():
            capacity = remaining_downloader.get(downloader_id, 0.0)
            if capacity <= _EPSILON:
                continue
            total_weight = sum(pool_map[key].weight for key in keys)
            if total_weight <= 0:
                continue
            for key in keys:
                proposals[key] = capacity * pool_map[key].weight / total_weight
        if not proposals or max(proposals.values()) <= _EPSILON:
            break

        site_scales: dict[str, float] = {}
        proposed_by_site: dict[str, float] = defaultdict(float)
        for key, proposal in proposals.items():
            proposed_by_site[pool_map[key].site_key] += proposal
        for site_key, proposal in proposed_by_site.items():
            if site_key not in remaining_site:
                site_scales[site_key] = 1.0
                continue
            site_scales[site_key] = min(
                1.0,
                remaining_site[site_key] / proposal if proposal > _EPSILON else 0.0,
            )

        increments: dict[str, float] = {}
        for key, proposal in proposals.items():
            increment = proposal * site_scales.get(pool_map[key].site_key, 1.0)
            demand = remaining_demand[key]
            if demand is not None:
                increment = min(increment, demand)
            if increment > _EPSILON:
                increments[key] = increment
        if not increments:
            break

        downloader_used: dict[str, float] = defaultdict(float)
        site_used: dict[str, float] = defaultdict(float)
        for key, increment in increments.items():
            allocations[key] += increment
            pool = pool_map[key]
            downloader_used[pool.downloader_id] += increment
            site_used[pool.site_key] += increment
            demand = remaining_demand[key]
            if demand is not None:
                remaining_demand[key] = max(0.0, demand - increment)
        for downloader_id, used in downloader_used.items():
            remaining_downloader[downloader_id] = max(
                0.0, remaining_downloader.get(downloader_id, 0.0) - used
            )
        for site_key, used in site_used.items():
            if site_key in remaining_site:
                remaining_site[site_key] = max(0.0, remaining_site[site_key] - used)

        active = {
            key for key in active
            if remaining_downloader.get(pool_map[key].downloader_id, 0.0) > _EPSILON
            and remaining_site.get(pool_map[key].site_key, 1.0) > _EPSILON
            and (remaining_demand[key] is None or remaining_demand[key] > _EPSILON)
        }

    return _integerize_pool_allocations(
        pool_map,
        allocations,
        downloader_caps_kib,
        site_caps_kib,
    )


def allocate_task_limits(
    total_kib: int,
    demands_kib: dict[str, Optional[int]],
    *,
    cycle: int = 0,
) -> dict[str, int]:
    """在同一站点池内等权分配单种额度，并轮换不足一 KiB/s 的探测槽。"""
    keys = sorted(str(key) for key in demands_kib)
    if not keys:
        return {}
    total = max(0, int(total_kib or 0))
    if total <= 0:
        return {key: 0 for key in keys}
    rotated = _rotate(keys, cycle)
    order = {key: index for index, key in enumerate(rotated)}
    remaining = float(total)
    active = set(keys)
    allocations = {key: 0.0 for key in keys}
    demand_remaining = {
        key: (None if demands_kib[key] is None else float(max(0, demands_kib[key] or 0)))
        for key in keys
    }
    for _ in range(max(8, len(keys) * 3)):
        if not active or remaining <= _EPSILON:
            break
        share = remaining / len(active)
        capped = [
            key for key in active
            if demand_remaining[key] is not None
            and demand_remaining[key] <= share + _EPSILON
        ]
        if not capped:
            for key in active:
                allocations[key] += share
            remaining = 0.0
            break
        used = 0.0
        for key in capped:
            amount = max(0.0, demand_remaining[key] or 0.0)
            allocations[key] += amount
            used += amount
            active.remove(key)
        remaining = max(0.0, remaining - used)

    result = {key: int(math.floor(value + _EPSILON)) for key, value in allocations.items()}
    residual = total - sum(result.values())
    candidates = sorted(
        keys,
        key=lambda key: (
            -(allocations[key] - math.floor(allocations[key])),
            order[key],
        ),
    )
    while residual > 0:
        progressed = False
        for key in candidates:
            demand = demands_kib[key]
            if demand is not None and result[key] >= max(0, int(demand)):
                continue
            result[key] += 1
            residual -= 1
            progressed = True
            if residual <= 0:
                break
        if not progressed:
            break
    return result


def _integerize_pool_allocations(
    pools: dict[str, UploadPool],
    allocations: dict[str, float],
    downloader_caps_kib: dict[str, int],
    site_caps_kib: dict[str, int],
) -> dict[str, int]:
    """把浮点站点池额度收敛为不突破任一硬约束的整数 KiB/s。"""
    result = {
        key: max(0, int(math.floor(value + _EPSILON)))
        for key, value in allocations.items()
    }
    downloader_used: dict[str, int] = defaultdict(int)
    site_used: dict[str, int] = defaultdict(int)
    for key, value in result.items():
        pool = pools[key]
        downloader_used[pool.downloader_id] += value
        site_used[pool.site_key] += value
    candidates = sorted(
        pools,
        key=lambda key: (
            -(allocations[key] - math.floor(allocations[key])),
            -pools[key].weight,
            key,
        ),
    )
    while True:
        progressed = False
        for key in candidates:
            pool = pools[key]
            downloader_cap = max(0, int(downloader_caps_kib.get(pool.downloader_id, 0) or 0))
            if downloader_used[pool.downloader_id] >= downloader_cap:
                continue
            site_cap = max(0, int(site_caps_kib.get(pool.site_key, 0) or 0))
            if site_cap and site_used[pool.site_key] >= site_cap:
                continue
            if pool.demand_kib is not None and result[key] >= max(0, pool.demand_kib):
                continue
            result[key] += 1
            downloader_used[pool.downloader_id] += 1
            site_used[pool.site_key] += 1
            progressed = True
        if not progressed:
            break
    return result


def _rotate(values: list[str], cycle: int) -> list[str]:
    """按协调周期轮换同权任务顺序，避免长期固定饿死尾部任务。"""
    if not values:
        return []
    offset = max(0, int(cycle or 0)) % len(values)
    return values[offset:] + values[:offset]


__all__ = (
    "aggregate_pool_demand_kib",
    "allocate_task_limits",
    "allocate_weighted_pools",
    "estimate_task_demand_kib",
)
