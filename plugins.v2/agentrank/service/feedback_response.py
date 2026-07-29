"""待确认提案与问询的回答、关闭、拒绝和过期状态机。"""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Union

from ..model.feedback import FeedbackEvent
from ..model.feedback_decision import MemoryProposal, PendingQuestion
from ..storage.repository import AgentRankRepository


DecisionRecord = Union[MemoryProposal, PendingQuestion]
class FeedbackDecisionError(RuntimeError):
    """表示待确认状态转换无法安全完成。"""

    def __init__(self, code: str, message: str, status_code: int = 409):
        """保存稳定错误码、用户文案和 HTTP 状态码。"""
        self.code = str(code)
        self.message = str(message)
        self.status_code = int(status_code)
        super().__init__(self.message)


@dataclass(frozen=True)
class QuestionAnswerResult:
    """描述回答问询后生成的新反馈事实及队列状态。"""

    question: PendingQuestion
    event: FeedbackEvent
    event_created: bool
    queue_status: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """返回不含内部提示和模型原文的回答结果。"""
        return {
            "question": self.question.to_dict(),
            "event": self.event.to_dict(),
            "event_status": "created" if self.event_created else "duplicate",
            "queue_status": self.queue_status,
            "memory_delta": {},
        }


class FeedbackResponseService:
    """协调待确认项的用户响应，且从不投影 PreferenceMemory。"""

    def __init__(
        self,
        repository: AgentRankRepository,
        *,
        feedback_queue: Any = None,
        now_factory: Callable[[], datetime] = None,
    ):
        """绑定仓储、可选反馈队列和可测试时钟。"""
        if not isinstance(repository, AgentRankRepository):
            raise TypeError("repository must be AgentRankRepository")
        self._repository = repository
        self._feedback_queue = feedback_queue
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        """返回带时区的当前时间。"""
        current = self._now_factory()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)

    @staticmethod
    def _profile_id(value: str) -> str:
        """校验并返回服务层稳定的 profile 身份。"""
        target = str(value or "").strip()
        if not target:
            raise FeedbackDecisionError(
                "decision_identity_required", "必须指定待确认记录", 422
            )
        return target

    @staticmethod
    def _parse_time(value: str) -> datetime:
        """解析模型已经校验过的带时区 ISO 时间。"""
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(
            timezone.utc
        )

    def _is_expired(self, record: DecisionRecord) -> bool:
        """判断待确认记录是否已到过期时间。"""
        return self._parse_time(record.expires_at) <= self._now()

    def _load_decision(
        self, profile_id: str, decision_type: str, decision_id: str
    ) -> DecisionRecord:
        """按 profile 和类型读取待确认记录。"""
        target = str(profile_id or "").strip()
        target_type = str(decision_type or "").strip().casefold()
        target_id = str(decision_id or "").strip()
        if not target or not target_id:
            raise FeedbackDecisionError(
                "decision_identity_required", "必须指定待确认记录", 422
            )
        if target_type == "proposal":
            record = self._repository.get_memory_proposal(target, target_id)
        elif target_type == "question":
            record = self._repository.get_pending_question(target, target_id)
        else:
            raise FeedbackDecisionError(
                "decision_type_invalid", "待确认类型不受支持", 422
            )
        if record is None:
            raise FeedbackDecisionError(
                "decision_not_found", "待确认记录不存在或已清理", 404
            )
        return record

    def _replace(
        self, record: DecisionRecord, *, expected_status: str
    ) -> bool:
        """按记录类型执行状态条件替换。"""
        if isinstance(record, MemoryProposal):
            return self._repository.replace_memory_proposal(
                record, expected_status=expected_status
            )
        return self._repository.replace_pending_question(
            record, expected_status=expected_status
        )

    @staticmethod
    def _pending_status(record: DecisionRecord) -> str:
        """返回指定待确认类型的未完成状态。"""
        return "pending_confirmation" if isinstance(record, MemoryProposal) else "pending"

    @staticmethod
    def _decision_id(record: DecisionRecord) -> str:
        """返回指定记录的稳定显示身份。"""
        return (
            record.proposal_id
            if isinstance(record, MemoryProposal)
            else record.question_id
        )

    def _ensure_pending(self, record: DecisionRecord) -> str:
        """确认记录仍待处理且尚未过期。"""
        pending_status = self._pending_status(record)
        if record.status != pending_status:
            raise FeedbackDecisionError(
                "decision_already_resolved", "该待确认项已经处理", 409
            )
        if self._is_expired(record):
            self._expire_record(record)
            raise FeedbackDecisionError(
                "decision_expired", "该待确认项已过期", 409
            )
        return pending_status

    def _expire_record(self, record: DecisionRecord) -> DecisionRecord:
        """把一个仍未完成且已到期的记录标记为过期。"""
        pending_status = self._pending_status(record)
        if record.status != pending_status:
            return record
        updated = replace(
            record,
            status="expired",
            reminder_policy="unselected",
            next_remind_at="",
            resolved_at=self._now().isoformat(),
        )
        if self._replace(updated, expected_status=pending_status):
            return updated
        return self._load_decision(
            record.profile_id,
            "proposal" if isinstance(record, MemoryProposal) else "question",
            self._decision_id(record),
        )

    def reject(
        self, profile_id: str, decision_type: str, decision_id: str
    ) -> DecisionRecord:
        """拒绝提案或关闭问询，不生成反馈事件或记忆变化。"""
        target = self._profile_id(profile_id)
        with self._repository.profile_data_guard(target):
            return self._reject_locked(target, decision_type, decision_id)

    def _reject_locked(
        self, profile_id: str, decision_type: str, decision_id: str
    ) -> DecisionRecord:
        """在 profile 写锁内拒绝或关闭待确认项。"""
        record = self._load_decision(profile_id, decision_type, decision_id)
        pending_status = self._ensure_pending(record)
        updated = replace(
            record,
            status="rejected" if isinstance(record, MemoryProposal) else "dismissed",
            reminder_policy="unselected",
            next_remind_at="",
            resolved_at=self._now().isoformat(),
        )
        if not self._replace(updated, expected_status=pending_status):
            raise FeedbackDecisionError(
                "decision_state_conflict", "待确认状态已变化，请刷新后重试", 409
            )
        return updated

    def expire_due(self, profile_id: str) -> List[DecisionRecord]:
        """标记指定 profile 中已经超时的提案和问询。"""
        target = self._profile_id(profile_id)
        with self._repository.profile_data_guard(target):
            return self._expire_due_locked(target)

    def _expire_due_locked(self, profile_id: str) -> List[DecisionRecord]:
        """在 profile 写锁内批量标记超时待确认项。"""
        expired: List[DecisionRecord] = []
        records: List[DecisionRecord] = [
            *self._repository.load_memory_proposals(profile_id),
            *self._repository.load_pending_questions(profile_id),
        ]
        for record in records:
            if record.status != self._pending_status(record):
                continue
            if not self._is_expired(record):
                continue
            updated = self._expire_record(record)
            if updated.status == "expired":
                expired.append(updated)
        return expired

    def _original_event(self, question: PendingQuestion) -> FeedbackEvent:
        """读取问询来源的原始反馈事实。"""
        event = next(
            (
                item
                for item in self._repository.load_feedback_events(question.profile_id)
                if item.event_id == question.event_id
            ),
            None,
        )
        if event is None:
            raise FeedbackDecisionError(
                "feedback_event_unavailable", "原始反馈事实已不可读取", 409
            )
        return event

    @staticmethod
    def _answer_text(
        question: PendingQuestion,
        *,
        option_id: str,
        custom_answer: str,
    ) -> tuple[str, str]:
        """校验选项或自定义回答并返回选项身份与实际文本。"""
        selected = str(option_id or "").strip()
        custom = str(custom_answer or "").strip()
        if bool(selected) == bool(custom):
            raise FeedbackDecisionError(
                "answer_invalid", "请选择一个选项或填写自定义回答", 422
            )
        if selected:
            option = next(
                (item for item in question.options if item.option_id == selected),
                None,
            )
            if option is None:
                raise FeedbackDecisionError(
                    "answer_option_invalid", "所选回答不存在", 422
                )
            return selected, option.label
        if not question.allow_custom_answer:
            raise FeedbackDecisionError(
                "custom_answer_forbidden", "该问题不接受自定义回答", 422
            )
        if len(custom) > 1000:
            raise FeedbackDecisionError(
                "custom_answer_too_long", "自定义回答不能超过一千字", 422
            )
        return "", custom

    @staticmethod
    def _same_answer_event(
        event: FeedbackEvent,
        *,
        original: FeedbackEvent,
        answer_text: str,
        actor_id: str,
    ) -> bool:
        """判断幂等键命中的事件是否属于同一问询回答。"""
        return all(
            (
                event.profile_id == original.profile_id,
                event.kind == original.kind,
                event.candidate_id == original.candidate_id,
                event.run_id == original.run_id,
                event.comment == answer_text,
                event.created_by_mp_user_id == actor_id,
                event.supersedes == original.event_id,
                event.status == "recorded",
            )
        )

    def answer_question(
        self,
        profile_id: str,
        question_id: str,
        *,
        idempotency_key: str,
        actor_id: str,
        option_id: str = "",
        custom_answer: str = "",
    ) -> QuestionAnswerResult:
        """回答问询并生成 supersedes 原反馈的新事件，再异步入队理解。"""
        target = self._profile_id(profile_id)
        with self._repository.profile_data_guard(target):
            return self._answer_question_locked(
                target,
                question_id,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
                option_id=option_id,
                custom_answer=custom_answer,
            )

    def _answer_question_locked(
        self,
        profile_id: str,
        question_id: str,
        *,
        idempotency_key: str,
        actor_id: str,
        option_id: str = "",
        custom_answer: str = "",
    ) -> QuestionAnswerResult:
        """在 profile 写锁内持久化问询回答并触发重新理解。"""
        question = self._load_decision(profile_id, "question", question_id)
        if not isinstance(question, PendingQuestion):
            raise FeedbackDecisionError(
                "question_not_found", "待回答问题不存在", 404
            )
        request_key = str(idempotency_key or "").strip()
        actor = str(actor_id or "").strip()
        if not request_key or len(request_key) > 256:
            raise FeedbackDecisionError(
                "idempotency_key_invalid", "回答请求缺少有效幂等标识", 422
            )
        if not actor or len(actor) > 128:
            raise FeedbackDecisionError(
                "actor_id_invalid", "回答请求缺少有效用户身份", 422
            )
        selected_option, answer_text = self._answer_text(
            question, option_id=option_id, custom_answer=custom_answer
        )
        original = self._original_event(question)
        existing_event = self._repository.load_feedback_event(
            question.profile_id, request_key
        )
        if question.status == "answered":
            if (
                existing_event is None
                or existing_event.event_id != question.answer_event_id
                or not self._same_answer_event(
                    existing_event,
                    original=original,
                    answer_text=answer_text,
                    actor_id=actor,
                )
            ):
                raise FeedbackDecisionError(
                    "question_already_answered", "该问题已经回答", 409
                )
            queue_status = ""
            if self._feedback_queue is not None:
                queue_status = self._feedback_queue.enqueue_event(existing_event).status
            return QuestionAnswerResult(
                question=question,
                event=existing_event,
                event_created=False,
                queue_status=queue_status,
            )
        pending_status = self._ensure_pending(question)
        if existing_event is not None:
            if not self._same_answer_event(
                existing_event,
                original=original,
                answer_text=answer_text,
                actor_id=actor,
            ):
                raise FeedbackDecisionError(
                    "idempotency_conflict", "幂等标识已被其他回答使用", 409
                )
            event = existing_event
            event_created = False
        else:
            appended = self._repository.append_feedback_event(
                FeedbackEvent(
                    profile_id=original.profile_id,
                    kind=original.kind,
                    candidate_id=original.candidate_id,
                    run_id=original.run_id,
                    analysis_id=original.analysis_id,
                    comment=answer_text,
                    created_by_mp_user_id=actor,
                    idempotency_key=request_key,
                    supersedes=original.event_id,
                )
            )
            event = appended.event
            event_created = appended.created
        updated = replace(
            question,
            status="answered",
            reminder_policy="unselected",
            next_remind_at="",
            selected_option_id=selected_option,
            answer_text=answer_text,
            answer_event_id=event.event_id,
            answered_by_mp_user_id=actor,
            resolved_at=self._now().isoformat(),
        )
        if not self._replace(updated, expected_status=pending_status):
            current = self._load_decision(
                profile_id, "question", question.question_id
            )
            if not (
                isinstance(current, PendingQuestion)
                and current.status == "answered"
                and current.answer_event_id == event.event_id
            ):
                raise FeedbackDecisionError(
                    "decision_state_conflict", "问题状态已变化，请刷新后重试", 409
                )
            updated = current
        queue_status = ""
        if self._feedback_queue is not None:
            queue_status = self._feedback_queue.enqueue_event(event).status
        return QuestionAnswerResult(
            question=updated,
            event=event,
            event_created=event_created,
            queue_status=queue_status,
        )
