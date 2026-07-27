"""受限反馈理解 Agent 的上下文组装、校验与持久化服务。"""

import hashlib
import json
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from ..agent_tools.context import FEEDBACK_AGENT_ROLE, build_trusted_context
from ..model.feedback import FeedbackEvent
from ..model.feedback_queue import FeedbackQueueJob
from ..model.feedback_understanding import (
    FeedbackSignal,
    FeedbackUnderstandingRecord,
)
from ..storage.repository import AgentRankRepository
from .critic_skills import (
    CRITIC_PERSONA_VERSION,
    CRITIC_SKILLS_VERSION,
    compare_conflicts,
    summarize_evidence,
    understand_feedback,
)
from .prompt import build_feedback_understanding_prompt


_OUTPUT_KEYS = frozenset(
    {"outcome", "restatement", "signals", "uncertainties"}
)
_SIGNAL_KEYS = frozenset(
    {"category", "value", "polarity", "certainty", "evidence_refs"}
)
_SENSITIVE_PSYCHOLOGY_TERMS = (
    "人格",
    "焦虑",
    "孤独",
    "疾病",
    "创伤",
    "抑郁",
    "心理诊断",
    "心理障碍",
)


class FeedbackUnderstandingError(RuntimeError):
    """表示反馈理解无法在安全契约内完成。"""

    retryable = True


def _text(value: Any, limit: int = 240) -> str:
    """把不可信标量规范为有界文本。"""
    return str(value or "").strip()[: max(1, int(limit))]


def _safe_list(values: Iterable[Any], limit: int = 16) -> List[str]:
    """返回保持顺序的有界唯一文本列表。"""
    result: List[str] = []
    for value in values or ():
        text = _text(value, 240)
        if text and text not in result:
            result.append(text)
        if len(result) >= max(1, int(limit)):
            break
    return result


class FeedbackUnderstandingParser:
    """把 Agent JSON 收敛为不含思维链的候选理解字段。"""

    @staticmethod
    def _contains_sensitive_text(values: Iterable[Any]) -> bool:
        """判断输出是否包含禁止持久化的敏感心理推断。"""
        text = " ".join(str(value or "") for value in values)
        return any(term in text for term in _SENSITIVE_PSYCHOLOGY_TERMS)

    def parse(
        self,
        raw: Any,
        *,
        event: FeedbackEvent,
        allowed_evidence_refs: Sequence[str],
    ) -> Dict[str, Any]:
        """校验根结构、证据引用和无评论动作边界。"""
        try:
            value = json.loads(str(raw or ""))
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise FeedbackUnderstandingError("反馈理解输出不是合法 JSON") from error
        if not isinstance(value, Mapping) or set(value) != set(_OUTPUT_KEYS):
            raise FeedbackUnderstandingError("反馈理解输出根结构不符合协议")
        outcome = _text(value.get("outcome"), 32).casefold()
        if outcome not in {"understood", "ambiguous"}:
            raise FeedbackUnderstandingError("反馈理解 outcome 不符合协议")
        restatement = _text(value.get("restatement"), 240)
        uncertainties = _safe_list(value.get("uncertainties") or (), 8)
        raw_signals = value.get("signals") or []
        if not isinstance(raw_signals, list) or len(raw_signals) > 8:
            raise FeedbackUnderstandingError("反馈理解 signals 不符合协议")
        allowed_refs = set(allowed_evidence_refs)
        signals: List[FeedbackSignal] = []
        for item in raw_signals:
            if not isinstance(item, Mapping) or set(item) != set(_SIGNAL_KEYS):
                raise FeedbackUnderstandingError("反馈理解 signal 结构不符合协议")
            refs = _safe_list(item.get("evidence_refs") or (), 8)
            if not refs or any(ref not in allowed_refs for ref in refs):
                raise FeedbackUnderstandingError("反馈理解引用了未授权证据")
            if f"event:{event.event_id}" not in refs:
                raise FeedbackUnderstandingError("反馈理解信号缺少当前事件证据")
            try:
                signals.append(
                    FeedbackSignal(
                        category=item.get("category"),
                        value=item.get("value"),
                        polarity=item.get("polarity"),
                        certainty=item.get("certainty") or 0.0,
                        evidence_refs=tuple(refs),
                    )
                )
            except (TypeError, ValueError) as error:
                raise FeedbackUnderstandingError("反馈理解 signal 值不符合协议") from error

        sensitive_values: List[Any] = [restatement, *uncertainties]
        sensitive_values.extend(signal.value for signal in signals)
        if self._contains_sensitive_text(sensitive_values):
            return {
                "outcome": "ambiguous",
                "restatement": "当前反馈不足以形成安全的长期口味判断",
                "signals": [],
                "uncertainties": ["需要用户用内容偏好语言补充具体原因"],
            }
        if not event.comment:
            return {
                "outcome": "ambiguous",
                "restatement": (
                    "已记录喜欢，但具体原因尚不明确"
                    if event.kind == "like"
                    else "已记录不喜欢，但具体原因尚不明确"
                ),
                "signals": [],
                "uncertainties": ["需要确认是题材、节奏、主创还是其他原因"],
            }
        if outcome == "understood" and not signals:
            outcome = "ambiguous"
        return {
            "outcome": outcome,
            "restatement": restatement,
            "signals": signals if outcome == "understood" else [],
            "uncertainties": uncertainties,
        }


class FeedbackUnderstandingService:
    """读取最小受信上下文并异步生成幂等反馈理解记录。"""

    def __init__(
        self,
        repository: AgentRankRepository,
        agent_adapter: Any,
        *,
        parser: Optional[FeedbackUnderstandingParser] = None,
        analysis_limit: int = 500,
    ):
        """绑定仓储、受限 Agent 适配器和有界记录上限。"""
        if not isinstance(repository, AgentRankRepository):
            raise TypeError("repository must be AgentRankRepository")
        self._repository = repository
        self._agent_adapter = agent_adapter
        self._parser = parser or FeedbackUnderstandingParser()
        self._analysis_limit = max(1, min(int(analysis_limit), 100000))

    def _event_for_job(self, job: FeedbackQueueJob) -> FeedbackEvent:
        """按持久序号读取当前任务引用的不可变反馈事实。"""
        events = self._repository.load_feedback_events(
            job.profile_id,
            after_sequence=job.event_sequence - 1,
            limit=1,
        )
        if not events:
            raise FeedbackUnderstandingError("反馈事实已不可读取")
        event = events[0]
        if event.sequence != job.event_sequence or event.event_id != job.event_id:
            raise FeedbackUnderstandingError("反馈任务与事件引用不一致")
        if event.status != "recorded":
            raise FeedbackUnderstandingError("反馈事实状态不允许理解")
        return event

    @staticmethod
    def _event_context(event: FeedbackEvent) -> Dict[str, Any]:
        """返回不含操作者和幂等键的最小事件切片。"""
        return {
            "event_id": event.event_id,
            "sequence": event.sequence,
            "kind": event.kind,
            "candidate_id": event.candidate_id,
            "run_id": event.run_id,
            "analysis_id": event.analysis_id,
            "comment": event.comment,
            "created_at": event.created_at,
            "supersedes": event.supersedes,
        }

    def _candidate_context(self, event: FeedbackEvent) -> Dict[str, Any]:
        """从冻结候选快照读取作品事实白名单。"""
        candidate = next(
            (
                item
                for item in self._repository.load_candidate_snapshot(
                    event.run_id, event.profile_id
                )
                if item.candidate_id == event.candidate_id
            ),
            None,
        )
        if candidate is None:
            return {"candidate_id": event.candidate_id}
        return {
            "candidate_id": candidate.candidate_id,
            "title": _text(candidate.title, 160),
            "media_type": _text(candidate.media_type, 24),
            "year": candidate.year,
            "overview": _text(candidate.overview, 1000),
            "genres": _safe_list(candidate.genres, 16),
            "regions": _safe_list(candidate.regions, 16),
            "actors": _safe_list(candidate.actors, 12),
            "directors": _safe_list(candidate.directors, 8),
        }

    @staticmethod
    def _safe_provenance(raw: Any) -> Dict[str, Any]:
        """只保留 Agent 适配器允许持久化的模型来源字段。"""
        value = getattr(raw, "provenance", None)
        if not isinstance(value, Mapping):
            value = {}
        try:
            calls = max(0, int(value.get("model_call_count") or 0))
        except (TypeError, ValueError):
            calls = 0
        return {
            "provider": _text(
                value.get("selected_provider_name") or value.get("provider"), 160
            ),
            "model": _text(value.get("model"), 160) or "unknown",
            "model_source": _text(value.get("source"), 64)
            or "moviepilot_system",
            "model_call_count": calls,
        }

    @staticmethod
    def _allowed_evidence_refs(
        event: FeedbackEvent,
        candidate: Mapping[str, Any],
        memory: Mapping[str, Any],
    ) -> List[str]:
        """列出模型可以引用的事件、候选和已确认记忆标识。"""
        refs = [f"event:{event.event_id}"]
        candidate_id = _text(candidate.get("candidate_id"), 128)
        if candidate_id:
            refs.append(f"candidate:{candidate_id}")
        for item in memory.get("items") or []:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("status") or "") != "active" or bool(
                item.get("tombstone")
            ):
                continue
            item_id = _text(item.get("item_id"), 128)
            if item_id:
                refs.append(f"memory:{item_id}")
        return refs

    def _record(
        self,
        *,
        event: FeedbackEvent,
        outcome: str,
        restatement: str,
        signals: Sequence[FeedbackSignal] = (),
        conflicts: Sequence[Mapping[str, Any]] = (),
        uncertainties: Sequence[str] = (),
        prompt_fingerprint: str,
        memory_revision: int,
        provenance: Mapping[str, Any],
    ) -> FeedbackUnderstandingRecord:
        """构造并幂等保存不含原始 Agent 输出的理解记录。"""
        record = FeedbackUnderstandingRecord(
            record_id=f"feedback-understanding:{event.event_id}",
            profile_id=event.profile_id,
            event_id=event.event_id,
            event_sequence=event.sequence,
            candidate_id=event.candidate_id,
            action=event.kind,
            outcome=outcome,
            restatement=restatement,
            signals=tuple(signals),
            conflicts=tuple(dict(item) for item in conflicts),
            uncertainties=tuple(uncertainties),
            persona_version=CRITIC_PERSONA_VERSION,
            skills_version=CRITIC_SKILLS_VERSION,
            prompt_fingerprint=prompt_fingerprint,
            memory_revision=memory_revision,
            provider=_text(provenance.get("provider"), 160),
            model=_text(provenance.get("model"), 160),
            model_source=_text(provenance.get("model_source"), 64),
            model_call_count=max(0, int(provenance.get("model_call_count") or 0)),
        )
        return self._repository.append_feedback_understanding(
            record, limit=self._analysis_limit
        )

    async def handle_job(self, job: FeedbackQueueJob) -> FeedbackUnderstandingRecord:
        """处理一个持久队列任务；纯忽略固定为 exclusion_only。"""
        if not isinstance(job, FeedbackQueueJob):
            raise TypeError("job must be FeedbackQueueJob")
        existing = self._repository.load_feedback_understanding(
            job.profile_id, job.event_id
        )
        if existing is not None:
            return existing
        event = self._event_for_job(job)
        candidate = self._candidate_context(event)
        memory = self._repository.load_preference_memory(event.profile_id).to_dict()
        evidence = summarize_evidence(
            self._event_context(event), candidate, memory
        )
        guard = understand_feedback(evidence)
        prompt = build_feedback_understanding_prompt()
        fingerprint = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if guard["required_outcome"] == "exclusion_only":
            return self._record(
                event=event,
                outcome="exclusion_only",
                restatement="仅排除这部作品，不改变长期口味判断",
                uncertainties=(),
                prompt_fingerprint=fingerprint,
                memory_revision=int(memory.get("memory_revision") or 0),
                provenance={
                    "provider": "",
                    "model": "",
                    "model_source": "deterministic",
                    "model_call_count": 0,
                },
            )

        context = build_trusted_context(
            username=(
                "profile_"
                + hashlib.sha256(event.profile_id.encode("utf-8")).hexdigest()[:16]
            ),
            run_id=f"feedback_{event.event_id}",
            candidates=[],
            archive_feedback={"entries": []},
            weights={},
            playback={},
            profile=None,
            agent_role=FEEDBACK_AGENT_ROLE,
            feedback_event=self._event_context(event),
            feedback_candidate=candidate,
            confirmed_memory=memory,
            analysis={},
            pending_context={},
        )
        method = getattr(self._agent_adapter, "run_feedback", None)
        raw = (
            await method(prompt, context)
            if callable(method)
            else await self._agent_adapter.run(prompt, context)
        )
        parsed = self._parser.parse(
            raw,
            event=event,
            allowed_evidence_refs=self._allowed_evidence_refs(
                event, candidate, memory
            ),
        )
        signals = tuple(parsed["signals"])
        conflicts = compare_conflicts(
            [signal.to_dict() for signal in signals],
            memory,
        )
        return self._record(
            event=event,
            outcome=parsed["outcome"],
            restatement=parsed["restatement"],
            signals=signals,
            conflicts=conflicts,
            uncertainties=tuple(parsed["uncertainties"]),
            prompt_fingerprint=fingerprint,
            memory_revision=int(memory.get("memory_revision") or 0),
            provenance=self._safe_provenance(raw),
        )
