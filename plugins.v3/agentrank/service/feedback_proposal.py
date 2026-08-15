"""把结构化反馈理解确定性转换为待确认提案或歧义问询。"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Mapping, Optional, Union

from ..model.feedback import FeedbackEvent
from ..model.feedback_decision import (
    MemoryProposal,
    MemoryProposalChange,
    PendingQuestion,
    PendingQuestionOption,
)
from ..model.constants import INTERACTION_MODE_DEFAULT
from ..model.feedback_understanding import FeedbackSignal, FeedbackUnderstandingRecord
from ..model.memory import PreferenceMemory, PreferenceMemoryItem
from ..storage.repository import AgentRankRepository
from .critic_skills import (
    propose_memory_change,
)
from .questioning_policy import QuestioningPolicy


FeedbackDecision = Optional[Union[MemoryProposal, PendingQuestion]]
PENDING_INTERVIEW_PREFIX = "pending-interview"


def _text(value: Any, limit: int = 240) -> str:
    """把不可信标量规范为有界文本。"""
    return str(value or "").strip()[: max(1, int(limit))]


def parse_pending_interview_id(value: Any) -> Optional[tuple[str, int]]:
    """解析宿主签发的待办问询会话标识。"""
    parts = str(value or "").strip().split(":")
    if len(parts) != 3 or parts[0] != PENDING_INTERVIEW_PREFIX:
        return None
    session_id = parts[1]
    try:
        total = int(parts[2])
    except (TypeError, ValueError):
        return None
    if not session_id or not 1 <= total <= 10:
        return None
    return session_id, total


class FeedbackProposalService:
    """生成并幂等保存不产生长期记忆写入的反馈后续项。"""

    def __init__(
        self,
        repository: AgentRankRepository,
        *,
        record_limit: int = 500,
        expiry_days: int = 30,
        now_factory: Callable[[], datetime] = None,
        persona_prompt: str = "",
        interaction_mode: str = INTERACTION_MODE_DEFAULT,
    ):
        """绑定仓储、保留上限、过期窗口和可测试时钟。"""
        if not isinstance(repository, AgentRankRepository):
            raise TypeError("repository must be AgentRankRepository")
        self._repository = repository
        self._record_limit = max(1, min(int(record_limit), 100000))
        self._expiry_days = max(1, min(int(expiry_days), 365))
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self._persona_prompt = str(persona_prompt or "").strip()
        self._questioning_policy = QuestioningPolicy(interaction_mode)

    def questioning_state(
        self, profile_id: str, *, memory: PreferenceMemory = None
    ) -> str:
        """返回画像当前的用户可见问询状态。"""
        target_memory = memory or self._repository.load_preference_memory(profile_id)
        decision = self._questioning_policy.evaluate(
            target_memory, self._repository.load_pending_questions(profile_id)
        )
        return decision.state

    def _time_window(self) -> tuple[str, str]:
        """返回当前创建时间和固定过期时间。"""
        now = self._now_factory()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.isoformat(), (now + timedelta(days=self._expiry_days)).isoformat()

    def create_playback_calibration(
        self,
        profile_id: str,
        snapshot: Any,
        *,
        actor_id: str = "",
    ) -> tuple[Optional[FeedbackEvent], bool]:
        """首次有效播放同步后创建一条交给 Agent 理解的校准事件。"""
        target = str(profile_id or "").strip()
        if not target or snapshot is None:
            return None, False
        questions = self._repository.load_pending_questions(target)
        existing = next(
            (
                item
                for item in questions
                if item.preference_dimension == "playback_calibration"
            ),
            None,
        )
        if existing is not None:
            return None, False
        if any(item.status == "pending" for item in questions):
            return None, False
        if not self._questioning_policy.allows_playback_calibration():
            return None, False
        if str(getattr(snapshot, "status", "") or "") not in {"ready", "cached"}:
            return None, False
        strong_samples = [
            item
            for item in getattr(snapshot, "samples", ()) or ()
            if bool(getattr(item, "completed", False))
            or int(getattr(item, "play_count", 0) or 0) >= 2
            or int(getattr(item, "completed_episode_count", 0) or 0) >= 2
            or int(getattr(item, "watch_minutes", 0) or 0) >= 60
        ]
        if not strong_samples:
            return None, False
        genres = []
        for sample in strong_samples:
            for genre in getattr(sample, "genres", ()) or ():
                label = _text(genre, 20)
                if label and label not in genres:
                    genres.append(label)
                if len(genres) >= 3:
                    break
            if len(genres) >= 3:
                break
        sample_titles = []
        for sample in strong_samples:
            title = _text(getattr(sample, "title", ""), 48)
            if title and title not in sample_titles:
                sample_titles.append(title)
            if len(sample_titles) >= 4:
                break
        summary = f"近期有 {len(strong_samples)} 项有效观看样本"
        if sample_titles:
            summary += "，包括《" + "》《".join(sample_titles) + "》"
        if genres:
            summary += "；其中常见类型为" + "、".join(genres)
        summary += "。这些记录只能用于提出问题，不能直接等同于喜欢。"
        appended = self._repository.append_feedback_event(
            FeedbackEvent(
                profile_id=target,
                kind="playback_calibration",
                candidate_id="profile:playback",
                comment=summary,
                created_by_mp_user_id=str(actor_id or "").strip()[:128],
                idempotency_key=f"playback-calibration:{target}",
            )
        )
        return appended.event, appended.created

    def create_pending_interview(
        self,
        profile_id: str,
        snapshot: Any,
        board: Any,
        *,
        actor_id: str,
        idempotency_key: str,
        total: int = 10,
    ) -> tuple[Optional[FeedbackEvent], bool]:
        """创建一条只用于待办中心逐轮验收的 Agent 问询事件。"""
        target = str(profile_id or "").strip()
        actor = str(actor_id or "").strip()[:128]
        request_key = str(idempotency_key or "").strip()
        count = max(1, min(int(total or 10), 10))
        if not target or not actor or not request_key or snapshot is None:
            return None, False
        existing_event = self._repository.load_feedback_event(target, request_key)
        if existing_event is not None:
            return existing_event, False
        if any(
            item.status == "pending"
            for item in self._repository.load_pending_questions(target)
        ):
            return None, False

        samples = list(getattr(snapshot, "samples", ()) or ())
        sample_titles = []
        genres = []
        for sample in samples:
            title = _text(getattr(sample, "title", ""), 48)
            if title and title not in sample_titles:
                sample_titles.append(title)
            for genre in getattr(sample, "genres", ()) or ():
                label = _text(genre, 20)
                if label and label not in genres:
                    genres.append(label)
            if len(sample_titles) >= 6 and len(genres) >= 5:
                break
        board_titles = []
        for item in getattr(board, "recommendations", ()) or ():
            title = _text(getattr(item, "title", ""), 48)
            if title and title not in board_titles:
                board_titles.append(title)
            if len(board_titles) >= 5:
                break

        summary = "用户明确启动了待办中心动态问询验收"
        if sample_titles:
            summary += "。近期播放事实包括《" + "》《".join(sample_titles) + "》"
        if genres:
            summary += "，可见类型有" + "、".join(genres[:5])
        if board_titles:
            summary += "。当前榜单包括《" + "》《".join(board_titles) + "》"
        summary += "。这些事实只用于生成具体问题，不能直接等同于喜欢；本轮回答不写入长期偏好。"
        digest = hashlib.sha256(
            f"{target}:{request_key}".encode("utf-8")
        ).hexdigest()[:24]
        appended = self._repository.append_feedback_event(
            FeedbackEvent(
                profile_id=target,
                kind="playback_calibration",
                candidate_id="profile:playback",
                analysis_id=f"{PENDING_INTERVIEW_PREFIX}:{digest}:{count}",
                comment=summary,
                created_by_mp_user_id=actor,
                idempotency_key=request_key,
            )
        )
        return appended.event, appended.created

    def pending_interview_state(
        self, event: FeedbackEvent
    ) -> Optional[Dict[str, Any]]:
        """返回当前验收会话的轮次、历史问答与显示维度。"""
        parsed = parse_pending_interview_id(event.analysis_id)
        if parsed is None:
            return None
        session_id, total = parsed
        events = {
            item.event_id: item
            for item in self._repository.load_feedback_events(event.profile_id)
            if item.analysis_id == event.analysis_id
        }
        questions = [
            item
            for item in self._repository.load_pending_questions(event.profile_id)
            if (
                item.event_id in events
                and events[item.event_id].analysis_id == event.analysis_id
            )
        ]
        questions.sort(key=lambda item: (item.event_sequence, item.question_id))
        history = [
            {
                "round": index,
                "question": item.question,
                "answer": item.answer_text,
                "status": item.status,
            }
            for index, item in enumerate(questions, 1)
        ]
        source_event = min(
            events.values(), key=lambda item: (item.sequence, item.event_id)
        )
        round_number = len(questions) + 1
        return {
            "session_id": session_id,
            "total": total,
            "round": round_number,
            "history": history[-10:],
            "source_context": source_event.comment,
            "dimension": (
                f"pending_interview:{session_id}:{round_number}:{total}"
            ),
        }

    @staticmethod
    def _stable_id(prefix: str, event_id: str, suffix: str = "") -> str:
        """根据事件身份生成重试稳定且不泄露原文的记录 ID。"""
        digest = hashlib.sha256(
            f"{prefix}:{event_id}:{suffix}".encode("utf-8")
        ).hexdigest()[:24]
        return f"{prefix}:{digest}"

    @staticmethod
    def _candidate_title(candidate: Mapping[str, Any]) -> str:
        """返回用于问询的安全作品标题。"""
        return _text(dict(candidate or {}).get("title"), 120) or "这部作品"

    @staticmethod
    def _conflict_targets(
        record: FeedbackUnderstandingRecord, signal: FeedbackSignal
    ) -> tuple[str, ...]:
        """读取与当前信号严格同类别同值的已确认冲突目标。"""
        result = []
        for conflict in record.conflicts:
            value = dict(conflict or {})
            if _text(value.get("category"), 64).casefold() != signal.category:
                continue
            if _text(value.get("value"), 120).casefold() != signal.value.casefold():
                continue
            item_id = _text(value.get("memory_item_id"), 128)
            if item_id and item_id not in result:
                result.append(item_id)
        return tuple(result)

    @staticmethod
    def _operation(
        signal: FeedbackSignal,
        latest: Optional[PreferenceMemoryItem],
        conflict_targets: tuple[str, ...],
    ) -> tuple[str, tuple[str, ...]]:
        """根据确认态谱系确定新增、强化、削弱或显式恢复操作。"""
        if latest is not None and latest.tombstone:
            return "restore", (latest.item_id,)
        if latest is not None and latest.polarity == signal.polarity:
            return "reinforce", (latest.item_id,)
        if latest is not None:
            return "weaken", (latest.item_id,)
        if conflict_targets:
            return "weaken", conflict_targets
        return "add", ()

    @staticmethod
    def _preview(operation: str, signal: FeedbackSignal) -> str:
        """生成不含心理术语的用户可读变化预览。"""
        direction = "喜欢" if signal.polarity == "positive" else "不喜欢"
        prefixes = {
            "add": "拟新增偏好",
            "reinforce": "拟强化已确认偏好",
            "weaken": "拟调整已确认偏好方向",
            "restore": "拟恢复已归档偏好",
            "archive": "拟归档偏好",
        }
        return f"{prefixes[operation]}：{direction}“{signal.value}”"

    def _proposal(
        self,
        record: FeedbackUnderstandingRecord,
        event: FeedbackEvent,
        memory: PreferenceMemory,
    ) -> MemoryProposal:
        """从明确理解构造证据绑定且尚未应用的记忆提案。"""
        draft = propose_memory_change(record.to_dict())
        if draft.get("status") != "pending_confirmation" or not record.signals:
            raise ValueError("understood feedback must produce a pending proposal")
        memory_matches = memory.memory_revision == record.memory_revision
        changes = []
        evidence_refs = []
        previews = []
        for index, signal in enumerate(record.signals, 1):
            latest = (
                memory.latest_item(signal.category, signal.value)
                if memory_matches
                else None
            )
            conflict_targets = self._conflict_targets(record, signal)
            operation, target_ids = self._operation(
                signal, latest, conflict_targets
            )
            preview = self._preview(operation, signal)
            change = MemoryProposalChange(
                change_id=self._stable_id(
                    "memory-change", event.event_id, f"{index}:{signal.category}:{signal.value}"
                ),
                operation=operation,
                category=signal.category,
                value=signal.value,
                polarity=signal.polarity,
                certainty=signal.certainty,
                evidence_refs=signal.evidence_refs,
                preview=preview,
                target_memory_item_ids=target_ids,
            )
            changes.append(change)
            previews.append(preview)
            for ref in signal.evidence_refs:
                if ref not in evidence_refs:
                    evidence_refs.append(ref)
        created_at, expires_at = self._time_window()
        return MemoryProposal(
            proposal_id=self._stable_id("memory-proposal", event.event_id),
            profile_id=record.profile_id,
            event_id=record.event_id,
            event_sequence=record.event_sequence,
            candidate_id=record.candidate_id,
            understanding_record_id=record.record_id,
            restatement=_text(draft.get("restatement"), 240),
            changes=tuple(changes),
            evidence_refs=tuple(evidence_refs),
            impact_preview=tuple(previews),
            expected_memory_revision=record.memory_revision,
            created_at=created_at,
            expires_at=expires_at,
        )

    def _question(
        self,
        record: FeedbackUnderstandingRecord,
        event: FeedbackEvent,
        candidate: Mapping[str, Any],
        memory: PreferenceMemory,
        question_draft: Mapping[str, Any] = None,
    ) -> Optional[PendingQuestion]:
        """仅从 Agent 已校验草稿构造问题，缺失时不做模板兜底。"""
        draft = dict(question_draft or {})
        if not draft and record.clarification_question:
            draft = {
                "question": record.clarification_question,
                "options": list(record.clarification_options),
                "allow_custom_answer": record.clarification_allow_custom_answer,
                "preference_dimension": record.clarification_dimension,
                "exploration_level": record.clarification_exploration_level,
                "confidence_gap": record.clarification_confidence_gap,
            }
        interview = self.pending_interview_state(event)
        if interview is not None:
            draft["preference_dimension"] = interview["dimension"]
        question_text = _text(draft.get("question"), 220)
        option_labels = []
        for value in draft.get("options") or ():
            label = _text(value, 120)
            if label and label not in option_labels:
                option_labels.append(label)
        if (
            not question_text
            or not 2 <= len(option_labels) <= 5
            or draft.get("allow_custom_answer") is not True
        ):
            return None
        options = tuple(
            PendingQuestionOption(option_id=f"option_{index}", label=label)
            for index, label in enumerate(option_labels, 1)
        )
        created_at, expires_at = self._time_window()
        evidence_refs = [f"event:{event.event_id}"]
        if event.candidate_id:
            evidence_refs.append(f"candidate:{event.candidate_id}")
        candidate_title = self._candidate_title(candidate)
        action_label = {
            "like": "点了赞",
            "dislike": "点了踩",
            "playback_calibration": "产生了一组有效观看记录",
        }.get(record.action, "留下了反馈")
        if interview is not None:
            context_line = (
                f"提问背景：这是待办中心动态问询验收的第 "
                f"{interview['round']}/{interview['total']} 题；回答仅推进本次验收，"
                "不会直接写入长期偏好。"
            )
        elif record.action == "playback_calibration":
            context_line = "提问背景：近期观看记录只能提供线索，不能直接代表你的喜好。"
        else:
            context_line = (
                f"提问背景：你刚刚对《{candidate_title}》{action_label}，"
                "但 Agent 还缺少一个会影响后续推荐的关键信息。"
            )
        return PendingQuestion(
            question_id=self._stable_id("pending-question", event.event_id),
            profile_id=record.profile_id,
            event_id=record.event_id,
            event_sequence=record.event_sequence,
            candidate_id=record.candidate_id,
            understanding_record_id=record.record_id,
            question=question_text,
            options=options,
            allow_custom_answer=draft.get("allow_custom_answer") is True,
            uncertainties=(context_line,),
            evidence_refs=tuple(evidence_refs),
            expected_memory_revision=record.memory_revision,
            created_at=created_at,
            expires_at=expires_at,
            preference_dimension=draft.get("preference_dimension"),
            exploration_level=draft.get("exploration_level") or 0,
            confidence_gap=draft.get("confidence_gap") or 0.0,
        )

    def materialize(
        self,
        record: FeedbackUnderstandingRecord,
        *,
        event: FeedbackEvent,
        candidate: Mapping[str, Any],
        memory: PreferenceMemory,
        question_draft: Mapping[str, Any] = None,
    ) -> FeedbackDecision:
        """幂等生成提案或问询；纯排除不产生额外打扰。"""
        if not isinstance(record, FeedbackUnderstandingRecord):
            raise TypeError("record must be FeedbackUnderstandingRecord")
        if not isinstance(event, FeedbackEvent) or event.event_id != record.event_id:
            raise ValueError("feedback decision event mismatch")
        if not isinstance(memory, PreferenceMemory) or memory.profile_id != record.profile_id:
            raise ValueError("feedback decision memory mismatch")
        if record.outcome == "exclusion_only":
            return None
        if record.action == "analysis_comment" and record.outcome == "understood":
            return None
        if record.outcome == "understood":
            existing = self._repository.load_memory_proposal(
                record.profile_id, record.event_id
            )
            if existing is not None:
                return existing
            return self._repository.append_memory_proposal(
                self._proposal(record, event, memory), limit=self._record_limit
            )
        existing = self._repository.load_pending_question(
            record.profile_id, record.event_id
        )
        if existing is not None:
            return existing
        pending = next(
            (
                item
                for item in self._repository.load_pending_questions(record.profile_id)
                if item.status == "pending"
            ),
            None,
        )
        if pending is not None:
            return pending
        questioning = self._questioning_policy.evaluate(
            memory,
            self._repository.load_pending_questions(record.profile_id),
            conflict_count=len(record.conflicts),
            uncertainty_count=len(record.uncertainties),
        )
        if self.pending_interview_state(event) is None and not questioning.allow_question:
            return None
        question = self._question(
            record,
            event,
            candidate,
            memory,
            question_draft=question_draft,
        )
        if question is None:
            return None
        return self._repository.append_pending_question(
            question, limit=self._record_limit
        )
