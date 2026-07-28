"""用户可读且不包含原始思维链的推荐分析模型。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping

from .support import SupportContribution


ANALYSIS_SCHEMA_VERSION = 1
ANALYSIS_RECORD_TYPE = "recommendation_analysis"
ANALYSIS_SELECTION_SOURCES = frozenset({"agent", "safe_fallback"})
ANALYSIS_STATUSES = frozenset({"active", "superseded"})


def _text(value: Any, limit: int = 240) -> str:
    """返回去除首尾空白的有界文本。"""
    return str(value or "").strip()[: max(1, int(limit))]


def _unique(values: Iterable[Any], limit: int = 32) -> List[str]:
    """返回保持顺序的有界唯一文本。"""
    result: List[str] = []
    for value in values or ():
        current = _text(value, 240)
        if current and current not in result:
            result.append(current)
        if len(result) >= max(1, int(limit)):
            break
    return result


@dataclass(frozen=True)
class AnalysisEvidence:
    """保存一项可由支持度贡献重算的用户可读证据。"""

    direction: str
    dimension: str
    user_value: str
    candidate_value: str
    user_refs: List[str]
    candidate_ref: str
    weight_units: int
    certainty_units: int
    contribution_units: int

    def __post_init__(self) -> None:
        """规范字段并复用支持度模型验证贡献可重算性。"""
        contribution = SupportContribution(
            direction=self.direction,
            dimension=self.dimension,
            user_value=self.user_value,
            candidate_value=self.candidate_value,
            user_refs=tuple(self.user_refs or ()),
            candidate_ref=self.candidate_ref,
            weight_units=self.weight_units,
            certainty_units=self.certainty_units,
            contribution_units=self.contribution_units,
        )
        object.__setattr__(self, "direction", contribution.direction)
        object.__setattr__(self, "dimension", contribution.dimension)
        object.__setattr__(self, "user_value", contribution.user_value)
        object.__setattr__(self, "candidate_value", contribution.candidate_value)
        object.__setattr__(self, "user_refs", list(contribution.user_refs))
        object.__setattr__(self, "candidate_ref", contribution.candidate_ref)
        object.__setattr__(self, "weight_units", contribution.weight_units)
        object.__setattr__(self, "certainty_units", contribution.certainty_units)
        object.__setattr__(self, "contribution_units", contribution.contribution_units)

    def to_dict(self) -> Dict[str, Any]:
        """返回不含隐藏推理的结构化证据字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AnalysisEvidence":
        """从持久化字典恢复并严格校验证据。"""
        if not isinstance(value, Mapping):
            raise ValueError("analysis evidence must be a mapping")
        return cls(
            direction=value.get("direction"),
            dimension=value.get("dimension"),
            user_value=value.get("user_value"),
            candidate_value=value.get("candidate_value"),
            user_refs=list(value.get("user_refs") or ()),
            candidate_ref=value.get("candidate_ref"),
            weight_units=value.get("weight_units") or 0,
            certainty_units=value.get("certainty_units") or 0,
            contribution_units=value.get("contribution_units") or 0,
        )


@dataclass
class RecommendationAnalysis:
    """保存一条推荐的可纠正分析及其版本化来源。"""

    analysis_id: str
    profile_id: str
    candidate_id: str
    run_id: str
    selection_source: str
    summary: str
    reason: str
    positive_evidence: List[AnalysisEvidence]
    counter_evidence: List[AnalysisEvidence]
    uncertainties: List[str]
    data_sources: List[str]
    support_percentage: int
    policy_version: str
    memory_revision: int
    persona_version: str
    skills_version: str
    prompt_fingerprint: str
    supersedes: str = ""
    status: str = "active"
    created_at: str = ""
    record_type: str = ANALYSIS_RECORD_TYPE
    schema_version: int = ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范分析边界并拒绝不完整或不可审计记录。"""
        for name, limit in (
            ("analysis_id", 128),
            ("profile_id", 160),
            ("candidate_id", 160),
            ("run_id", 128),
            ("summary", 240),
            ("reason", 240),
            ("policy_version", 160),
            ("persona_version", 32),
            ("skills_version", 32),
            ("prompt_fingerprint", 128),
            ("supersedes", 128),
            ("status", 32),
            ("created_at", 64),
            ("record_type", 64),
        ):
            setattr(self, name, _text(getattr(self, name), limit))
        self.selection_source = _text(self.selection_source, 32)
        self.support_percentage = int(self.support_percentage)
        self.memory_revision = max(0, int(self.memory_revision))
        self.schema_version = int(self.schema_version)
        self.positive_evidence = [
            item if isinstance(item, AnalysisEvidence) else AnalysisEvidence.from_dict(item)
            for item in self.positive_evidence or ()
        ]
        self.counter_evidence = [
            item if isinstance(item, AnalysisEvidence) else AnalysisEvidence.from_dict(item)
            for item in self.counter_evidence or ()
        ]
        self.uncertainties = _unique(self.uncertainties, 16)
        self.data_sources = _unique(self.data_sources, 8)
        if not all(
            (self.analysis_id, self.profile_id, self.candidate_id, self.run_id)
        ):
            raise ValueError("recommendation analysis identity is incomplete")
        if self.selection_source not in ANALYSIS_SELECTION_SOURCES:
            raise ValueError("recommendation analysis selection_source is invalid")
        if self.status not in ANALYSIS_STATUSES:
            raise ValueError("recommendation analysis status is invalid")
        if not 0 <= self.support_percentage <= 100:
            raise ValueError("recommendation analysis support is out of range")
        if not self.policy_version or not self.prompt_fingerprint:
            raise ValueError("recommendation analysis provenance is incomplete")
        if self.record_type != ANALYSIS_RECORD_TYPE:
            raise ValueError("recommendation analysis record_type is invalid")
        if self.schema_version != ANALYSIS_SCHEMA_VERSION:
            raise ValueError("recommendation analysis schema is unsupported")

    def to_dict(self) -> Dict[str, Any]:
        """返回不含提示词、工具过程、token 或原始思维链的字典。"""
        return {
            **asdict(self),
            "positive_evidence": [item.to_dict() for item in self.positive_evidence],
            "counter_evidence": [item.to_dict() for item in self.counter_evidence],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RecommendationAnalysis":
        """从持久化字典恢复结构化推荐分析。"""
        if not isinstance(value, Mapping):
            raise ValueError("recommendation analysis must be a mapping")
        return cls(
            analysis_id=value.get("analysis_id"),
            profile_id=value.get("profile_id"),
            candidate_id=value.get("candidate_id"),
            run_id=value.get("run_id"),
            selection_source=value.get("selection_source"),
            summary=value.get("summary"),
            reason=value.get("reason"),
            positive_evidence=list(value.get("positive_evidence") or ()),
            counter_evidence=list(value.get("counter_evidence") or ()),
            uncertainties=list(value.get("uncertainties") or ()),
            data_sources=list(value.get("data_sources") or ()),
            support_percentage=value.get("support_percentage") or 0,
            policy_version=value.get("policy_version"),
            memory_revision=value.get("memory_revision") or 0,
            persona_version=value.get("persona_version"),
            skills_version=value.get("skills_version"),
            prompt_fingerprint=value.get("prompt_fingerprint"),
            supersedes=value.get("supersedes") or "",
            status=value.get("status") or "active",
            created_at=value.get("created_at") or "",
            record_type=value.get("record_type") or "",
            schema_version=value.get("schema_version") or 0,
        )
