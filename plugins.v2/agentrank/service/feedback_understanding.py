"""受限反馈理解 Agent 的上下文组装、校验与持久化服务。"""

import asyncio
import hashlib
import json
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from ..agent_tools.context import FEEDBACK_AGENT_ROLE, build_trusted_context
from ..model.analysis import RecommendationAnalysis
from ..model.constants import INTERACTION_MODE_DEFAULT
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
from .analysis_comment import ANALYSIS_COMMENT_KIND, AnalysisCommentService
from .prompt import (
    DEFAULT_CRITIC_PROMPT,
    DEFAULT_PERSONA_PROMPT,
    build_analysis_comment_prompt,
    build_feedback_understanding_prompt,
)
from .feedback_proposal import FeedbackProposalService
from .validation import is_complete_recommendation_copy


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


class FeedbackUnderstandingBudgetError(FeedbackUnderstandingError):
    """表示本次反馈理解已耗尽总预算，可由用户稍后重试。"""

    terminal_retryable = True


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


class AnalysisCommentParser:
    """把逐条评论输出收敛为安全的用户可读分析修订。"""

    _output_keys = frozenset(
        {"outcome", "restatement", "revised_reason", "uncertainties"}
    )

    def parse(
        self,
        raw: Any,
        *,
        event: FeedbackEvent,
        analysis: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """校验评论修订结构、敏感边界和三十字完整短句。"""
        try:
            value = json.loads(str(raw or ""))
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise FeedbackUnderstandingError("分析评论输出不是合法 JSON") from error
        if not isinstance(value, Mapping) or set(value) != set(self._output_keys):
            raise FeedbackUnderstandingError("分析评论输出根结构不符合协议")
        outcome = _text(value.get("outcome"), 32).casefold()
        if outcome not in {"understood", "ambiguous"}:
            raise FeedbackUnderstandingError("分析评论 outcome 不符合协议")
        restatement = _text(value.get("restatement"), 240)
        revised_reason = " ".join(
            str(value.get("revised_reason") or "").split()
        ).strip()
        uncertainties = _safe_list(value.get("uncertainties") or (), 8)
        sensitive_values = [restatement, revised_reason, *uncertainties]
        if FeedbackUnderstandingParser._contains_sensitive_text(sensitive_values):
            return {
                "outcome": "ambiguous",
                "restatement": "当前评论不足以形成安全的分析修订",
                "revised_reason": "",
                "uncertainties": ["请使用具体作品内容或推荐证据说明错误"],
            }
        if event.kind != ANALYSIS_COMMENT_KIND or not event.comment:
            raise FeedbackUnderstandingError("分析评论事件缺少纠正内容")
        if str(analysis.get("analysis_id") or "") != event.analysis_id:
            raise FeedbackUnderstandingError("分析评论与结构化分析引用不一致")
        if outcome == "ambiguous":
            return {
                "outcome": outcome,
                "restatement": restatement,
                "revised_reason": "",
                "uncertainties": uncertainties
                or ["需要说明既有推荐依据中哪项判断有误"],
            }
        if not restatement or not is_complete_recommendation_copy(revised_reason):
            raise FeedbackUnderstandingError("分析评论修订文案不完整")
        if revised_reason == str(analysis.get("summary") or "").strip():
            raise FeedbackUnderstandingError("分析评论把作品简介误作推荐依据")
        return {
            "outcome": outcome,
            "restatement": restatement,
            "revised_reason": revised_reason,
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
        comment_parser: Optional[AnalysisCommentParser] = None,
        analysis_limit: int = 500,
        proposal_service: Any = None,
        analysis_comment_service: Any = None,
        critic_prompt: str = DEFAULT_CRITIC_PROMPT,
        persona_prompt: str = DEFAULT_PERSONA_PROMPT,
        interaction_mode: str = INTERACTION_MODE_DEFAULT,
        total_timeout_seconds: float = 90.0,
        retry_base_seconds: float = 1.0,
        retry_max_seconds: float = 12.0,
    ):
        """绑定仓储、受限 Agent、解析器和确定性提案服务。"""
        if not isinstance(repository, AgentRankRepository):
            raise TypeError("repository must be AgentRankRepository")
        self._repository = repository
        self._agent_adapter = agent_adapter
        self._parser = parser or FeedbackUnderstandingParser()
        self._comment_parser = comment_parser or AnalysisCommentParser()
        self._analysis_limit = max(1, min(int(analysis_limit), 100000))
        self._critic_prompt = str(critic_prompt or DEFAULT_CRITIC_PROMPT).strip()
        self._persona_prompt = str(persona_prompt or DEFAULT_PERSONA_PROMPT).strip()
        self._total_timeout_seconds = max(1.0, float(total_timeout_seconds))
        self._retry_base_seconds = max(0.05, float(retry_base_seconds))
        self._retry_max_seconds = max(
            self._retry_base_seconds, float(retry_max_seconds)
        )
        self._proposal_service = proposal_service or FeedbackProposalService(
            repository,
            record_limit=self._analysis_limit,
            persona_prompt=self._persona_prompt,
            interaction_mode=interaction_mode,
        )
        self._analysis_comment_service = (
            analysis_comment_service
            or AnalysisCommentService(
                repository, analysis_limit=self._analysis_limit
            )
        )

    @staticmethod
    def _rate_limited(error: BaseException) -> bool:
        """判断异常链是否为供应商 429。"""
        current: Optional[BaseException] = error
        seen: set[int] = set()
        for _ in range(6):
            if current is None or id(current) in seen:
                break
            seen.add(id(current))
            response = getattr(current, "response", None)
            status = getattr(current, "status_code", None) or getattr(
                response, "status_code", None
            )
            code = str(getattr(current, "code", "") or "").casefold()
            text = str(current or "").casefold()
            if status == 429 or code in {"429", "rate_limit", "rate_limit_exceeded"}:
                return True
            if "429" in text or "rate limit" in text or "too many requests" in text:
                return True
            current = getattr(current, "__cause__", None) or getattr(
                current, "__context__", None
            )
        return False

    @staticmethod
    def _retry_after_seconds(error: BaseException) -> float:
        """读取供应商 Retry-After 秒数。"""
        response = getattr(error, "response", None)
        headers = getattr(response, "headers", None) or getattr(error, "headers", None)
        value = ""
        if isinstance(headers, Mapping):
            value = headers.get("retry-after") or headers.get("Retry-After") or ""
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0

    async def _call_agent_with_budget(
        self, method: Any, prompt: str, context: Any
    ) -> Any:
        """在一个总预算内执行反馈 Agent，并仅对 429 退避重试。"""
        deadline = time.monotonic() + self._total_timeout_seconds
        attempt = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FeedbackUnderstandingBudgetError(
                    "反馈理解超时，已保留原始反馈，可稍后重试"
                )
            try:
                result = method(prompt, context)
                if hasattr(result, "__await__"):
                    return await asyncio.wait_for(result, timeout=remaining)
                return result
            except asyncio.TimeoutError as error:
                raise FeedbackUnderstandingBudgetError(
                    "反馈理解超时，已保留原始反馈，可稍后重试"
                ) from error
            except Exception as error:
                if not self._rate_limited(error):
                    raise
                attempt += 1
                delay = self._retry_after_seconds(error) or min(
                    self._retry_max_seconds,
                    self._retry_base_seconds * (2 ** max(0, attempt - 1)),
                )
                remaining = deadline - time.monotonic()
                if remaining <= delay:
                    raise FeedbackUnderstandingBudgetError(
                        "反馈理解请求受限且已超过处理时限，已保留反馈，可稍后重试"
                    ) from error
                await asyncio.sleep(delay)

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
        if not event.run_id:
            return {"candidate_id": event.candidate_id}
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

    def _analysis_context(self, event: FeedbackEvent) -> Dict[str, Any]:
        """读取事件绑定分析并投影为不含隐藏推理的白名单。"""
        if not event.analysis_id:
            return {}
        analysis = next(
            (
                item
                for item in self._repository.load_recommendation_analyses(
                    event.profile_id, event.run_id
                )
                if item.analysis_id == event.analysis_id
            ),
            None,
        )
        if analysis is None:
            if event.kind == ANALYSIS_COMMENT_KIND:
                raise FeedbackUnderstandingError("评论绑定的 Agent 分析已不可读取")
            return {}
        if (
            not isinstance(analysis, RecommendationAnalysis)
            or analysis.profile_id != event.profile_id
            or analysis.candidate_id != event.candidate_id
            or analysis.run_id != event.run_id
        ):
            raise FeedbackUnderstandingError("反馈事件与 Agent 分析作用域不一致")
        return {
            "analysis_id": analysis.analysis_id,
            "candidate_id": analysis.candidate_id,
            "run_id": analysis.run_id,
            "selection_source": analysis.selection_source,
            "summary": _text(analysis.summary, 240),
            "reason": _text(analysis.reason, 240),
            "positive_evidence": [
                item.to_dict() for item in analysis.positive_evidence
            ],
            "counter_evidence": [
                item.to_dict() for item in analysis.counter_evidence
            ],
            "uncertainties": _safe_list(analysis.uncertainties, 16),
            "data_sources": _safe_list(analysis.data_sources, 8),
            "support_percentage": analysis.support_percentage,
            "policy_version": analysis.policy_version,
            "memory_revision": analysis.memory_revision,
            "supersedes": analysis.supersedes,
            "status": analysis.status,
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
        analysis_revision_id: str = "",
        analysis_revision_reason: str = "",
        analysis_revision_note: str = "",
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
            analysis_revision_id=analysis_revision_id,
            analysis_revision_reason=analysis_revision_reason,
            analysis_revision_note=analysis_revision_note,
        )
        return self._repository.append_feedback_understanding(
            record,
            limit=self._analysis_limit,
            mandatory_analysis_ids=(event.analysis_id,) if event.analysis_id else (),
        )

    async def handle_job(self, job: FeedbackQueueJob) -> FeedbackUnderstandingRecord:
        """处理一个持久队列任务；纯忽略固定为 exclusion_only。"""
        if not isinstance(job, FeedbackQueueJob):
            raise TypeError("job must be FeedbackQueueJob")
        event = self._event_for_job(job)
        if event.kind in {"like", "dislike"}:
            from .feedback_action import FeedbackActionService

            actions = FeedbackActionService(
                self._repository, analysis_limit=self._analysis_limit
            )
            if not actions.is_current_polarity(event):
                return None
            actions.finalize_deferred_polarity(event)
        candidate = self._candidate_context(event)
        memory_model = self._repository.load_preference_memory(event.profile_id)
        memory = memory_model.to_dict()
        existing = self._repository.load_feedback_understanding(
            job.profile_id, job.event_id
        )
        if existing is not None:
            if (
                existing.action == ANALYSIS_COMMENT_KIND
                and existing.outcome == "understood"
            ):
                self._analysis_comment_service.apply_revision(event, existing)
            else:
                self._proposal_service.materialize(
                    existing,
                    event=event,
                    candidate=candidate,
                    memory=memory_model,
                )
            return existing
        analysis = self._analysis_context(event)
        evidence = summarize_evidence(
            self._event_context(event), candidate, memory
        )
        guard = understand_feedback(evidence)
        if event.kind == ANALYSIS_COMMENT_KIND and not guard.get(
            "may_revise_analysis"
        ):
            raise FeedbackUnderstandingError("分析评论缺少可修订的用户内容")
        prompt = (
            build_analysis_comment_prompt(
                self._critic_prompt, self._persona_prompt
            )
            if event.kind == ANALYSIS_COMMENT_KIND
            else build_feedback_understanding_prompt(
                self._critic_prompt, self._persona_prompt
            )
        )
        fingerprint = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if guard["required_outcome"] == "exclusion_only":
            record = self._record(
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
            self._proposal_service.materialize(
                record,
                event=event,
                candidate=candidate,
                memory=memory_model,
            )
            return record

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
            analysis=analysis,
            pending_context={},
        )
        method = getattr(self._agent_adapter, "run_feedback", None)
        raw = await self._call_agent_with_budget(
            method if callable(method) else self._agent_adapter.run,
            prompt,
            context,
        )
        if event.kind == ANALYSIS_COMMENT_KIND:
            parsed = self._comment_parser.parse(
                raw,
                event=event,
                analysis=analysis,
            )
            revision_id = (
                self._analysis_comment_service.revision_id(event)
                if parsed["outcome"] == "understood"
                else ""
            )
            record = self._record(
                event=event,
                outcome=parsed["outcome"],
                restatement=parsed["restatement"],
                uncertainties=tuple(parsed["uncertainties"]),
                prompt_fingerprint=fingerprint,
                memory_revision=int(memory.get("memory_revision") or 0),
                provenance=self._safe_provenance(raw),
                analysis_revision_id=revision_id,
                analysis_revision_reason=parsed["revised_reason"],
                analysis_revision_note=(
                    parsed["restatement"]
                    if parsed["outcome"] == "understood"
                    else ""
                ),
            )
            if record.outcome == "understood":
                self._analysis_comment_service.apply_revision(event, record)
            else:
                self._proposal_service.materialize(
                    record,
                    event=event,
                    candidate=candidate,
                    memory=memory_model,
                )
            return record

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
        record = self._record(
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
        self._proposal_service.materialize(
            record,
            event=event,
            candidate=candidate,
            memory=memory_model,
        )
        return record
