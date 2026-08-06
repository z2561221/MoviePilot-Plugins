"""反馈理解结果及其可审计来源模型。"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


FEEDBACK_UNDERSTANDING_SCHEMA_VERSION = 1
FEEDBACK_UNDERSTANDING_OUTCOMES = frozenset(
    {"exclusion_only", "understood", "ambiguous"}
)
FEEDBACK_SIGNAL_CATEGORIES = frozenset(
    {
        "genre",
        "creator",
        "region",
        "era",
        "style",
        "emotion",
        "cognition",
        "narrative",
        "novelty",
        "pacing",
        "completion",
        "character",
        "other",
    }
)
FEEDBACK_SIGNAL_POLARITIES = frozenset({"positive", "negative"})


def _text(value: Any, limit: int = 240) -> str:
    """把可选文本规范为有界字符串。"""
    return str(value or "").strip()[: max(1, int(limit))]


def _unique_texts(values: Iterable[Any], limit: int = 16) -> Tuple[str, ...]:
    """返回保持顺序的唯一文本元组。"""
    result = []
    for value in values or ():
        text = _text(value, 160)
        if text and text not in result:
            result.append(text)
        if len(result) >= max(1, int(limit)):
            break
    return tuple(result)


def _conflict_entries(
    values: Iterable[Any], limit: int = 16
) -> Tuple[Mapping[str, str], ...]:
    """复制并限制可持久化的记忆冲突字段。"""
    result = []
    for value in values or ():
        if not isinstance(value, Mapping):
            continue
        conflict = {
            "memory_item_id": _text(value.get("memory_item_id"), 128),
            "category": _text(value.get("category"), 64),
            "value": _text(value.get("value"), 120),
            "reason": _text(value.get("reason"), 160),
        }
        if not all(
            conflict[key]
            for key in ("memory_item_id", "category", "value", "reason")
        ):
            continue
        result.append(conflict)
        if len(result) >= max(1, int(limit)):
            break
    return tuple(result)


def _utc_now() -> str:
    """返回当前 UTC ISO 时间。"""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class FeedbackSignal:
    """表示一条尚未投影到长期记忆的候选偏好信号。"""

    category: str
    value: str
    polarity: str
    certainty: float = 0.0
    evidence_refs: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """规范化信号并限制可写入的类别和证据范围。"""
        object.__setattr__(self, "category", _text(self.category, 32).casefold())
        object.__setattr__(self, "value", _text(self.value, 120))
        object.__setattr__(self, "polarity", _text(self.polarity, 16).casefold())
        object.__setattr__(self, "certainty", max(0.0, min(float(self.certainty), 1.0)))
        object.__setattr__(self, "evidence_refs", _unique_texts(self.evidence_refs))
        if self.category not in FEEDBACK_SIGNAL_CATEGORIES:
            raise ValueError("feedback signal category is unsupported")
        if not self.value or self.polarity not in FEEDBACK_SIGNAL_POLARITIES:
            raise ValueError("feedback signal identity is invalid")
        if not self.evidence_refs:
            raise ValueError("feedback signal requires evidence references")

    def to_dict(self) -> Dict[str, Any]:
        """返回可审计信号字典。"""
        return {
            "category": self.category,
            "value": self.value,
            "polarity": self.polarity,
            "certainty": self.certainty,
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FeedbackSignal":
        """从结构化 Agent 输出恢复信号。"""
        if not isinstance(value, Mapping):
            raise ValueError("feedback signal must be a mapping")
        return cls(
            category=value.get("category"),
            value=value.get("value"),
            polarity=value.get("polarity"),
            certainty=value.get("certainty") or 0.0,
            evidence_refs=tuple(value.get("evidence_refs") or ()),
        )


@dataclass(frozen=True)
class FeedbackUnderstandingRecord:
    """保存一次反馈理解的结构化结果，但不保存提示词或思维链。"""

    record_id: str
    profile_id: str
    event_id: str
    event_sequence: int
    candidate_id: str
    action: str
    outcome: str
    restatement: str = ""
    signals: Tuple[FeedbackSignal, ...] = ()
    conflicts: Tuple[Mapping[str, Any], ...] = ()
    uncertainties: Tuple[str, ...] = ()
    persona_version: str = "1.0.0"
    skills_version: str = "1.0.0"
    prompt_fingerprint: str = ""
    memory_revision: int = 0
    provider: str = ""
    model: str = ""
    model_source: str = ""
    model_call_count: int = 0
    analysis_revision_id: str = ""
    analysis_revision_reason: str = ""
    analysis_revision_note: str = ""
    created_at: str = ""
    status: str = "analyzed"
    schema_version: int = FEEDBACK_UNDERSTANDING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """校验结果身份、动作边界和脱敏来源字段。"""
        for field_name in (
            "record_id",
            "profile_id",
            "event_id",
            "candidate_id",
            "action",
            "outcome",
            "restatement",
            "persona_version",
            "skills_version",
            "prompt_fingerprint",
            "provider",
            "model",
            "model_source",
            "analysis_revision_id",
            "analysis_revision_reason",
            "analysis_revision_note",
            "created_at",
            "status",
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), 240))
        object.__setattr__(self, "event_sequence", int(self.event_sequence))
        object.__setattr__(self, "memory_revision", max(0, int(self.memory_revision)))
        object.__setattr__(self, "model_call_count", max(0, int(self.model_call_count)))
        object.__setattr__(self, "signals", tuple(self.signals or ()))
        object.__setattr__(self, "conflicts", _conflict_entries(self.conflicts))
        object.__setattr__(self, "uncertainties", _unique_texts(self.uncertainties))
        object.__setattr__(self, "schema_version", int(self.schema_version))
        if not self.record_id or not self.profile_id or not self.event_id:
            raise ValueError("feedback understanding identity is incomplete")
        if self.event_sequence <= 0:
            raise ValueError("feedback understanding sequence must be positive")
        if self.action not in {
            "like",
            "dislike",
            "ignore",
            "analysis_comment",
            "playback_calibration",
        }:
            raise ValueError("feedback understanding action is invalid")
        if self.outcome not in FEEDBACK_UNDERSTANDING_OUTCOMES:
            raise ValueError("feedback understanding outcome is invalid")
        if any(not isinstance(item, FeedbackSignal) for item in self.signals):
            raise ValueError("feedback understanding contains invalid signals")
        if self.outcome == "exclusion_only" and self.signals:
            raise ValueError("exclusion_only understanding cannot contain signals")
        revision_fields = (
            self.analysis_revision_id,
            self.analysis_revision_reason,
            self.analysis_revision_note,
        )
        if self.action == "analysis_comment":
            if self.outcome not in {"understood", "ambiguous"}:
                raise ValueError("analysis comment outcome is invalid")
            if self.signals:
                raise ValueError("analysis comment cannot contain taste signals")
            if self.outcome == "understood" and not all(revision_fields):
                raise ValueError("understood analysis comment requires a revision")
            if self.outcome != "understood" and any(revision_fields):
                raise ValueError("ambiguous analysis comment cannot contain a revision")
        elif any(revision_fields):
            raise ValueError("non-comment understanding cannot contain a revision")
        if not self.created_at:
            object.__setattr__(self, "created_at", _utc_now())
        if self.schema_version != FEEDBACK_UNDERSTANDING_SCHEMA_VERSION:
            raise ValueError("feedback understanding schema_version is unsupported")

    def to_dict(self) -> Dict[str, Any]:
        """返回不含原始提示词和思维链的持久化字典。"""
        return {
            "record_type": "feedback_understanding",
            "record_id": self.record_id,
            "profile_id": self.profile_id,
            "event_id": self.event_id,
            "event_sequence": self.event_sequence,
            "candidate_id": self.candidate_id,
            "action": self.action,
            "outcome": self.outcome,
            "restatement": self.restatement,
            "signals": [item.to_dict() for item in self.signals],
            "conflicts": [dict(item) for item in self.conflicts],
            "uncertainties": list(self.uncertainties),
            "persona_version": self.persona_version,
            "skills_version": self.skills_version,
            "prompt_fingerprint": self.prompt_fingerprint,
            "memory_revision": self.memory_revision,
            "provider": self.provider,
            "model": self.model,
            "model_source": self.model_source,
            "model_call_count": self.model_call_count,
            "analysis_revision_id": self.analysis_revision_id,
            "analysis_revision_reason": self.analysis_revision_reason,
            "analysis_revision_note": self.analysis_revision_note,
            "created_at": self.created_at,
            "status": self.status,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FeedbackUnderstandingRecord":
        """从持久化字典恢复理解记录。"""
        if not isinstance(value, Mapping):
            raise ValueError("feedback understanding record must be a mapping")
        return cls(
            record_id=value.get("record_id"),
            profile_id=value.get("profile_id"),
            event_id=value.get("event_id"),
            event_sequence=value.get("event_sequence") or 0,
            candidate_id=value.get("candidate_id"),
            action=value.get("action"),
            outcome=value.get("outcome"),
            restatement=value.get("restatement"),
            signals=tuple(
                FeedbackSignal.from_dict(item)
                for item in value.get("signals") or []
            ),
            conflicts=tuple(
                dict(item) for item in value.get("conflicts") or [] if isinstance(item, Mapping)
            ),
            uncertainties=tuple(value.get("uncertainties") or ()),
            persona_version=value.get("persona_version") or "1.0.0",
            skills_version=value.get("skills_version") or "1.0.0",
            prompt_fingerprint=value.get("prompt_fingerprint"),
            memory_revision=value.get("memory_revision") or 0,
            provider=value.get("provider"),
            model=value.get("model"),
            model_source=value.get("model_source"),
            model_call_count=value.get("model_call_count") or 0,
            analysis_revision_id=value.get("analysis_revision_id"),
            analysis_revision_reason=value.get("analysis_revision_reason"),
            analysis_revision_note=value.get("analysis_revision_note"),
            created_at=value.get("created_at"),
            status=value.get("status") or "analyzed",
            schema_version=value.get("schema_version") or 0,
        )
