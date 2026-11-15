"""单轮额度计算的数值结果，不持有任务快照、服务或插件实例。"""

from dataclasses import dataclass

from .upload_limit import UploadPool


@dataclass(frozen=True, slots=True)
class UploadPoolInputs:
    """本轮自有的池和需求中间值；收敛时原地细化需求，避免复制整张数值表。"""

    pools: list[UploadPool]
    demands: dict[str, int | None]
    probe_candidates: set[str]
    candidate_counts: dict[str, int]
    elastic_downloaders: set[str]


@dataclass(frozen=True, slots=True)
class UploadProbeBudget:
    """一个下载器下一轮探测计数，协调层决定何时写入运行态。"""

    count: int
    low_utilization_cycles: int
    reduction_pending: bool


@dataclass(frozen=True, slots=True)
class UploadAllocationPlan:
    """最终额度与实际探测任务，只含标识和数字，不进入持久状态。"""

    pool_allocations: dict[str, int]
    task_limits: dict[str, int]
    probing_task_keys: set[str]
