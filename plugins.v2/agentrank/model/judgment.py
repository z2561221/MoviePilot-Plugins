"""AgentRank 初赛判断卡与批次检查点领域模型。"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional


JUDGMENT_PROTOCOL_VERSION = 1


@dataclass(frozen=True)
class PreliminaryJudgment:
    """表示一条 Agent 初赛候选判断。"""

    candidate_id: str
    fit_score: int
    positive_evidence: List[Dict[str, str]] = field(default_factory=list)
    counter_evidence: Optional[Dict[str, str]] = None
    advance: bool = False

    def __post_init__(self) -> None:
        """校验候选身份、契合度范围和两项正向证据。"""
        candidate_id = str(self.candidate_id or "").strip()
        if not candidate_id:
            raise ValueError("judgment candidate_id is required")
        if not 0 <= int(self.fit_score) <= 100:
            raise ValueError("judgment fit_score is out of range")
        if len(self.positive_evidence) != 2:
            raise ValueError("judgment requires exactly two positive evidence claims")

    def to_dict(self) -> Dict[str, Any]:
        """转换为可持久化的普通映射。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PreliminaryJudgment":
        """从持久化映射恢复一条初赛判断。"""
        if not isinstance(value, Mapping):
            raise ValueError("judgment must be a mapping")
        return cls(
            candidate_id=str(value.get("candidate_id") or ""),
            fit_score=int(value.get("fit_score") or 0),
            positive_evidence=[
                {str(key): str(item) for key, item in dict(claim).items()}
                for claim in value.get("positive_evidence") or []
                if isinstance(claim, Mapping)
            ],
            counter_evidence=(
                {
                    str(key): str(item)
                    for key, item in dict(value.get("counter_evidence") or {}).items()
                }
                if isinstance(value.get("counter_evidence"), Mapping)
                else None
            ),
            advance=bool(value.get("advance")),
        )


@dataclass(frozen=True)
class JudgmentBatchCheckpoint:
    """按完整输入指纹隔离、可幂等复用的成功初赛批次。"""

    profile_id: str
    batch_id: str
    idempotency_key: str
    profile_fingerprint: str
    retrieval_fingerprint: str
    candidate_fingerprint: str
    judgments: List[PreliminaryJudgment]
    protocol_version: int = JUDGMENT_PROTOCOL_VERSION
    created_at: str = ""

    def __post_init__(self) -> None:
        """校验检查点作用域、协议版本和候选唯一性。"""
        for field_name in (
            "profile_id",
            "batch_id",
            "idempotency_key",
            "profile_fingerprint",
            "retrieval_fingerprint",
            "candidate_fingerprint",
        ):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"checkpoint {field_name} is required")
        if int(self.protocol_version) != JUDGMENT_PROTOCOL_VERSION:
            raise ValueError("checkpoint protocol version is unsupported")
        candidate_ids = [item.candidate_id for item in self.judgments]
        if not candidate_ids or len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("checkpoint judgments must contain unique candidates")
        if not self.created_at:
            object.__setattr__(
                self, "created_at", datetime.now(timezone.utc).isoformat()
            )

    def to_dict(self) -> Dict[str, Any]:
        """转换为插件数据后端可保存的映射。"""
        return {
            "profile_id": self.profile_id,
            "batch_id": self.batch_id,
            "idempotency_key": self.idempotency_key,
            "profile_fingerprint": self.profile_fingerprint,
            "retrieval_fingerprint": self.retrieval_fingerprint,
            "candidate_fingerprint": self.candidate_fingerprint,
            "judgments": [item.to_dict() for item in self.judgments],
            "protocol_version": self.protocol_version,
            "created_at": self.created_at,
        }

    def same_content(self, other: "JudgmentBatchCheckpoint") -> bool:
        """忽略写入时间比较幂等业务内容。"""
        left = self.to_dict()
        right = other.to_dict()
        left.pop("created_at", None)
        right.pop("created_at", None)
        return left == right

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "JudgmentBatchCheckpoint":
        """从插件数据映射恢复批次检查点。"""
        if not isinstance(value, Mapping):
            raise ValueError("checkpoint must be a mapping")
        return cls(
            profile_id=str(value.get("profile_id") or ""),
            batch_id=str(value.get("batch_id") or ""),
            idempotency_key=str(value.get("idempotency_key") or ""),
            profile_fingerprint=str(value.get("profile_fingerprint") or ""),
            retrieval_fingerprint=str(value.get("retrieval_fingerprint") or ""),
            candidate_fingerprint=str(value.get("candidate_fingerprint") or ""),
            judgments=[
                PreliminaryJudgment.from_dict(item)
                for item in value.get("judgments") or []
            ],
            protocol_version=int(value.get("protocol_version") or 0),
            created_at=str(value.get("created_at") or ""),
        )
