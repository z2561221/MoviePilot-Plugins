"""额度准备与纯计算；不访问下载器，不修改持久化记录。"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from itertools import chain
from typing import Any

from ..model.upload_limit import UploadPool, UploadTorrentSnapshot, pool_state_key
from ..model.upload_plan import (
    UploadAllocationPlan,
    UploadPoolInputs,
    UploadProbeBudget,
)
from .upload_allocator import (
    adjust_auto_probe_count,
    aggregate_pool_demand_kib,
    allocate_site_pools,
    allocate_task_limits,
    estimate_task_demand_kib,
    initial_auto_probe_count,
    is_task_probe_candidate,
)


def task_upload_rates(
    regular_tasks: Mapping[str, UploadTorrentSnapshot],
    grace_tasks: Mapping[str, UploadTorrentSnapshot],
    selected: Iterable[str],
) -> dict[str, int]:
    """一次遍历两组快照，保持仅所选下载器的原始上传速率口径。"""
    rates = dict.fromkeys(selected, 0)
    for snapshot in chain(regular_tasks.values(), grace_tasks.values()):
        if snapshot.downloader_id in rates:
            rates[snapshot.downloader_id] += int(snapshot.upload_rate_bps or 0)
    return rates


def prepare_pool_inputs(
    regular_tasks: Mapping[str, UploadTorrentSnapshot],
    torrent_state: Mapping[str, dict],
) -> UploadPoolInputs:
    """从只读快照与旧额度准备池；单轮中间结果只保存key与数值。"""
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    demands: dict[str, int | None] = {}
    probe_candidates: set[str] = set()
    candidate_counts: dict[str, int] = defaultdict(int)
    elastic_downloaders: set[str] = set()
    for task_key, snapshot in regular_tasks.items():
        record = torrent_state[task_key]
        site_key = str(record.get("site_key") or "")
        grouped[(snapshot.downloader_id, site_key)].append(task_key)
        previous = record.get("last_allocation_kib")
        previous = None if previous is None else int(previous or 0)
        demands[task_key] = estimate_task_demand_kib(
            snapshot.upload_rate_bps, previous, snapshot.upload_demand_peers,
        )
        if is_task_probe_candidate(snapshot.upload_rate_bps, previous, snapshot.upload_demand_peers):
            probe_candidates.add(task_key)
            candidate_counts[snapshot.downloader_id] += 1
        elif demands[task_key] is None:
            elastic_downloaders.add(snapshot.downloader_id)
    pools = [UploadPool(
        key=pool_state_key(downloader_id, site_key),
        downloader_id=downloader_id,
        site_key=site_key,
        task_keys=tuple(sorted(task_keys)),
        current_rate_bps=sum(int(regular_tasks[key].upload_rate_bps or 0) for key in task_keys),
        demand_kib=0,
    ) for (downloader_id, site_key), task_keys in sorted(grouped.items())]
    return UploadPoolInputs(pools, demands, probe_candidates, candidate_counts, elastic_downloaders)


def next_probe_budget(
    entry: Mapping[str, Any], *, cap_kib: int, candidates: int,
    upload_rate_bps: int, cycle: int,
) -> UploadProbeBudget:
    """只计算计数，保留原利用率阈值与两轮探测边界。"""
    current = int(entry.get("auto_probe_count") or 0)
    batch_boundary = cycle > 1 and (cycle - 1) % 2 == 0
    if current <= 0 and candidates > 0:
        return UploadProbeBudget(initial_auto_probe_count(cap_kib, candidates), 0, False)
    total_limit_kib = int(cap_kib or 0)
    current_rate_bps = int(upload_rate_bps or 0)
    near_cap = total_limit_kib > 0 and current_rate_bps * 100 >= total_limit_kib * 1024 * 90
    reduction_pending = bool(entry.get("probe_reduction_pending") or near_cap)
    current, low_cycles = adjust_auto_probe_count(
        current, total_limit_kib=total_limit_kib, candidate_count=candidates,
        upload_rate_bps=current_rate_bps,
        low_utilization_cycles=int(entry.get("probe_low_utilization_cycles") or 0),
        batch_boundary=batch_boundary, reduction_pending=reduction_pending,
    )
    if batch_boundary and reduction_pending:
        reduction_pending = False
    return UploadProbeBudget(current, low_cycles, reduction_pending)


def resolve_pool_demands(inputs: UploadPoolInputs, probe_keys: set[str]) -> list[UploadPool]:
    """细化本轮拥有的需求表，未入选探测归零；不改任务快照或持久记录。"""
    for task_key in inputs.probe_candidates - probe_keys:
        inputs.demands[task_key] = 0
    result = []
    for pool in inputs.pools:
        selected_count = sum(key in probe_keys for key in pool.task_keys)
        result.append(UploadPool(
            key=pool.key, downloader_id=pool.downloader_id, site_key=pool.site_key,
            task_keys=pool.task_keys, current_rate_bps=pool.current_rate_bps,
            demand_kib=aggregate_pool_demand_kib(
                (inputs.demands[key] for key in pool.task_keys if key not in probe_keys),
                probe_candidates=selected_count,
                elastic_probes=selected_count > 0 and pool.downloader_id not in inputs.elastic_downloaders,
            ),
        ))
    return result


def allocate_upload_plan(
    pools: list[UploadPool], task_demands: dict[str, int | None], probe_keys: set[str],
    caps: dict[str, int], site_rules: Mapping[str, dict], *, cycle: int,
) -> UploadAllocationPlan:
    """使用既有分配器生成额度计划，调用方独立负责写入及检查点。"""
    site_caps = {name: int(rule.get("limit_kib") or 0) for name, rule in site_rules.items()}
    allocations = allocate_site_pools(pools, caps, site_caps)
    desired: dict[str, int] = {}
    for pool in pools:
        desired.update(allocate_task_limits(
            allocations.get(pool.key, 0), {key: task_demands[key] for key in pool.task_keys},
            cycle=cycle, probe_keys=set(pool.task_keys).intersection(probe_keys),
        ))
    probing = {key for key in probe_keys if int(desired.get(key, 0) or 0) > 0}
    return UploadAllocationPlan(allocations, desired, probing)
