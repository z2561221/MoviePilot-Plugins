"""上传额度纯逻辑分配器。"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, Optional

from ..model.upload_limit import UploadPool


_EPSILON = 1e-9
_PROBE_TARGET_KIB = 8
_PROBE_CONCURRENCY_SLOT_KIB = 4
_PROBE_HOLD_CYCLES = 2
_PROBE_INITIAL_PERCENT = 15
_PROBE_LOW_UTILIZATION_PERCENT = 80
_PROBE_NEAR_CAP_PERCENT = 90
_MAX_AUTO_PROBES_PER_DOWNLOADER = 32


def initial_auto_probe_count(total_limit_kib: int, candidate_count: int) -> int:
    """按下载器总额度约 15% 计算初始自动探测数量。"""
    candidates = max(0, int(candidate_count or 0))
    if candidates <= 0:
        return 0
    total = max(0, int(total_limit_kib or 0))
    rounded = (
        total * _PROBE_INITIAL_PERCENT
        + 50 * _PROBE_TARGET_KIB
    ) // (100 * _PROBE_TARGET_KIB)
    return min(
        max(1, int(rounded)),
        _max_auto_probe_count(total, candidates),
    )


def adjust_auto_probe_count(
    current_count: int,
    *,
    total_limit_kib: int,
    candidate_count: int,
    upload_rate_bps: int,
    low_utilization_cycles: int,
    batch_boundary: bool,
    reduction_pending: bool = False,
) -> tuple[int, int]:
    """根据利用率与探测结果平滑调整探测数量，并返回连续低利用轮数。"""
    candidates = max(0, int(candidate_count or 0))
    if candidates <= 0:
        return 0, 0
    total = max(0, int(total_limit_kib or 0))
    maximum = _max_auto_probe_count(total, candidates)
    current = min(max(1, int(current_count or 0)), maximum)
    current_rate = max(0, int(upload_rate_bps or 0))
    capacity_bps = total * 1024
    low_utilization = (
        capacity_bps > 0
        and current_rate * 100 < capacity_bps * _PROBE_LOW_UTILIZATION_PERCENT
    )
    near_cap = (
        capacity_bps > 0
        and current_rate * 100 >= capacity_bps * _PROBE_NEAR_CAP_PERCENT
    )
    low_cycles = (
        max(0, int(low_utilization_cycles or 0)) + 1
        if low_utilization
        else 0
    )
    if not batch_boundary:
        return current, low_cycles
    if near_cap or reduction_pending:
        return max(1, current - 1), 0
    if low_cycles >= _PROBE_HOLD_CYCLES and current < maximum:
        return current + 1, 0
    return current, low_cycles


def is_task_probe_candidate(
    upload_rate_bps: int,
    previous_limit_kib: Optional[int],
    upload_demand_peers: int = 0,
) -> bool:
    """判断任务是否有 Peer 需求但尚未产生实际上传。"""
    del previous_limit_kib
    return (
        max(0, int(upload_rate_bps or 0)) <= 0
        and max(0, int(upload_demand_peers or 0)) > 0
    )


def estimate_task_demand_kib(
    upload_rate_bps: int,
    previous_limit_kib: Optional[int],
    upload_demand_peers: int = 0,
) -> Optional[int]:
    """根据 Peer、上一轮限额与实时上传估算需求，None 表示仍可借额。"""
    current_bps = max(0, int(upload_rate_bps or 0))
    peer_count = max(0, int(upload_demand_peers or 0))
    if current_bps <= 0 and peer_count <= 0:
        return 0
    if previous_limit_kib is None:
        return None
    previous = max(0, int(previous_limit_kib))
    if previous <= 0:
        return None
    if current_bps <= 0:
        return None
    if current_bps >= previous * 1024 * 0.8:
        return None
    return max(1, int(math.ceil(current_bps / 1024 * 1.25)))


def aggregate_pool_demand_kib(
    values: Iterable[Optional[int]],
    *,
    probe_candidates: int = 0,
    elastic_probes: bool = False,
) -> Optional[int]:
    """聚合真实任务与已选探测预算，必要时允许探测任务借用余量。"""
    normalized = list(values)
    if any(value is None for value in normalized):
        return None
    demand = sum(max(0, int(value or 0)) for value in normalized)
    probe_count = max(0, int(probe_candidates or 0))
    if probe_count and elastic_probes:
        return None
    return demand + probe_count * _PROBE_TARGET_KIB


def select_probe_keys(
    pools: Iterable[UploadPool],
    probe_keys: set[str],
    *,
    target_counts: dict[str, int],
    cycle: int = 0,
) -> set[str]:
    """按受限站点和下载器目标数等权选择轮换探测任务。"""
    candidates = {str(key) for key in probe_keys}
    if not candidates:
        return set()
    by_downloader: dict[str, list[UploadPool]] = defaultdict(list)
    for pool in pools:
        if candidates.intersection(pool.task_keys):
            by_downloader[pool.downloader_id].append(pool)
    selected: set[str] = set()
    batch_index = max(0, int(cycle or 0) - 1) // _PROBE_HOLD_CYCLES
    for downloader_id in sorted(by_downloader):
        downloader_pools = sorted(
            by_downloader[downloader_id],
            key=lambda pool: pool.key,
        )
        schedule = downloader_pools
        if not schedule:
            continue
        pool_candidates = {
            pool.key: sorted(candidates.intersection(pool.task_keys))
            for pool in downloader_pools
        }
        total_candidates = sum(len(values) for values in pool_candidates.values())
        configured_target = int(target_counts.get(downloader_id, 0) or 0)
        target_count = min(max(0, configured_target), total_candidates)
        slot = batch_index * max(1, target_count)
        attempts = max(len(schedule), total_candidates * len(schedule))
        downloader_selected: set[str] = set()
        for absolute_slot in range(slot, slot + attempts):
            pool = schedule[absolute_slot % len(schedule)]
            values = pool_candidates.get(pool.key) or []
            if not values:
                continue
            occurrence = _schedule_occurrence_before(
                schedule,
                pool.key,
                absolute_slot,
            )
            downloader_selected.add(values[occurrence % len(values)])
            if len(downloader_selected) >= target_count:
                break
        selected.update(downloader_selected)
    return selected


def allocate_site_pools(
    pools: Iterable[UploadPool],
    downloader_caps_kib: dict[str, int],
    site_caps_kib: dict[str, int],
) -> dict[str, int]:
    """按下载器总额度、站点共享上限与实际需求等权分配站点池。"""
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
            for key in keys:
                proposals[key] = capacity / len(keys)
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
    probe_keys: set[str] | None = None,
) -> dict[str, int]:
    """在站点池内优先分配上传任务，并接收已全局选定的探测任务。"""
    keys = sorted(str(key) for key in demands_kib)
    if not keys:
        return {}
    total = max(0, int(total_kib or 0))
    if total <= 0:
        return {key: 0 for key in keys}
    probes = set(keys).intersection(str(key) for key in (probe_keys or set()))
    if probes:
        selected_probes = sorted(probes)
        normal_demands = {
            key: value for key, value in demands_kib.items()
            if key not in probes and (value is None or int(value or 0) > 0)
        }
        if not normal_demands:
            selected_limits = _allocate_task_limits_core(
                total,
                {key: demands_kib[key] for key in selected_probes},
                cycle=cycle,
            )
            return {
                key: int(selected_limits.get(key, 0))
                for key in keys
            }

        has_elastic_normal = any(value is None for value in normal_demands.values())
        finite_normal_demand = sum(
            max(0, int(value or 0))
            for value in normal_demands.values()
            if value is not None
        )
        if has_elastic_normal:
            probe_budget = min(
                _PROBE_TARGET_KIB * len(selected_probes),
                total // 2,
            )
        else:
            normal_limits = _allocate_task_limits_core(
                min(total, finite_normal_demand),
                normal_demands,
                cycle=cycle,
            )
            probe_limits = _allocate_task_limits_core(
                total - sum(normal_limits.values()),
                {key: None for key in selected_probes},
                cycle=cycle,
            )
            return {
                key: int(probe_limits.get(key, normal_limits.get(key, 0)))
                for key in keys
            }
        probe_limits = _allocate_task_limits_core(
            probe_budget,
            {
                key: _PROBE_TARGET_KIB
                for key in selected_probes
            },
            cycle=cycle,
        )
        normal_limits = _allocate_task_limits_core(
            total - sum(probe_limits.values()),
            normal_demands,
            cycle=cycle,
        )
        return {
            key: int(probe_limits.get(key, normal_limits.get(key, 0)))
            for key in keys
        }
    return _allocate_task_limits_core(total, demands_kib, cycle=cycle)


def _allocate_task_limits_core(
    total_kib: int,
    demands_kib: dict[str, Optional[int]],
    *,
    cycle: int,
) -> dict[str, int]:
    """按等权水位法分配一组任务额度。"""
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


def _max_auto_probe_count(total_limit_kib: int, candidate_count: int) -> int:
    """返回受额度、候选数量和防扩散上限共同约束的最大探测数。"""
    total = max(0, int(total_limit_kib or 0))
    candidates = max(0, int(candidate_count or 0))
    if candidates <= 0:
        return 0
    budget_slots = max(1, total // _PROBE_CONCURRENCY_SLOT_KIB)
    return min(_MAX_AUTO_PROBES_PER_DOWNLOADER, candidates, budget_slots)


def _schedule_occurrence_before(
    schedule: list[UploadPool],
    pool_key: str,
    absolute_slot: int,
) -> int:
    """计算指定绝对槽位前同一站点池已出现的次数。"""
    cycle_count, offset = divmod(max(0, absolute_slot), len(schedule))
    per_cycle = sum(pool.key == pool_key for pool in schedule)
    prefix = sum(pool.key == pool_key for pool in schedule[:offset])
    return cycle_count * per_cycle + prefix


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
    "adjust_auto_probe_count",
    "aggregate_pool_demand_kib",
    "allocate_site_pools",
    "allocate_task_limits",
    "estimate_task_demand_kib",
    "initial_auto_probe_count",
    "is_task_probe_candidate",
    "select_probe_keys",
)
