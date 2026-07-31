"""AgentRank 初赛分批、指纹和批次结果 DTO。"""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Iterable, List

from ..model.judgment import JUDGMENT_PROTOCOL_VERSION, PreliminaryJudgment


@dataclass(frozen=True)
class PreliminaryBatch:
    """一个最多五条候选的确定性初赛批次。"""

    batch_id: str
    index: int
    candidates: List[Any]
    advance_quota: int
    weights_fingerprint: str
    candidate_fingerprint: str
    idempotency_key: str


@dataclass
class PreliminaryBatchResult:
    """表示一个初赛批次的 Agent、缓存或失败结果。"""

    batch: PreliminaryBatch
    status: str
    judgments: List[PreliminaryJudgment] = field(default_factory=list)
    error: str = ""


def _fingerprint(value: Any) -> str:
    """对规范化 JSON 输入计算稳定 SHA-256 指纹。"""
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def retrieval_fingerprint(profile: Any) -> str:
    """对冻结画像中的检索策略计算稳定指纹。"""
    return _fingerprint(
        {
            "filters": dict(getattr(profile, "filters", {}) or {}),
            "ranking_tags": list(getattr(profile, "ranking_tags", []) or []),
        }
    )


def judgment_weights_fingerprint(weights: Any) -> str:
    """对影响 Agent 判断的权重、策略版本和证据目录计算指纹。"""
    return _fingerprint(dict(weights or {}))


def partition_preliminary_batches(
    candidates: Iterable[Any],
    profile_fingerprint: str,
    retrieval_plan_fingerprint: str,
    weights_fingerprint: str = "",
) -> List[PreliminaryBatch]:
    """把 10-15 条冻结候选无重叠地分成两组或三组。"""
    values = list(candidates or ())
    count = len(values)
    if not 10 <= count <= 15:
        raise ValueError("preliminary tournament requires 10 to 15 candidates")
    batch_count = 2 if count == 10 else 3
    advance_quota = 3 if count == 10 else 2
    base_size, remainder = divmod(count, batch_count)
    sizes = [base_size + int(index < remainder) for index in range(batch_count)]
    if any(size < 1 or size > 5 for size in sizes) or sum(sizes) != count:
        raise RuntimeError("preliminary batch partition is invalid")
    batches: List[PreliminaryBatch] = []
    offset = 0
    for index, size in enumerate(sizes):
        items = values[offset : offset + size]
        offset += size
        candidate_payload = [
            item.to_dict() if hasattr(item, "to_dict") else dict(item)
            for item in items
        ]
        candidate_fingerprint = _fingerprint(candidate_payload)
        idempotency_key = _fingerprint(
            {
                "profile_fingerprint": str(profile_fingerprint),
                "retrieval_fingerprint": str(retrieval_plan_fingerprint),
                "weights_fingerprint": str(weights_fingerprint),
                "candidate_fingerprint": candidate_fingerprint,
                "protocol_version": JUDGMENT_PROTOCOL_VERSION,
            }
        )
        batches.append(
            PreliminaryBatch(
                batch_id=f"batch-{index + 1}",
                index=index,
                candidates=items,
                advance_quota=advance_quota,
                weights_fingerprint=str(weights_fingerprint),
                candidate_fingerprint=candidate_fingerprint,
                idempotency_key=idempotency_key,
            )
        )
    candidate_ids = [
        str(getattr(item, "candidate_id", "") or "")
        for batch in batches
        for item in batch.candidates
    ]
    if len(candidate_ids) != count or len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("preliminary candidates must be unique across batches")
    return batches
