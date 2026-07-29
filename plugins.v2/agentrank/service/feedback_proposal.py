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
from ..model.feedback_understanding import FeedbackSignal, FeedbackUnderstandingRecord
from ..model.memory import PreferenceMemory, PreferenceMemoryItem
from ..storage.repository import AgentRankRepository
from .critic_skills import ask_clarification, propose_memory_change
from .questioning_policy import QuestioningPolicy


FeedbackDecision = Optional[Union[MemoryProposal, PendingQuestion]]


def _text(value: Any, limit: int = 240) -> str:
    """把不可信标量规范为有界文本。"""
    return str(value or "").strip()[: max(1, int(limit))]


class FeedbackProposalService:
    """生成并幂等保存不产生长期记忆写入的反馈后续项。"""

    def __init__(
        self,
        repository: AgentRankRepository,
        *,
        record_limit: int = 500,
        expiry_days: int = 30,
        now_factory: Callable[[], datetime] = None,
    ):
        """绑定仓储、保留上限、过期窗口和可测试时钟。"""
        if not isinstance(repository, AgentRankRepository):
            raise TypeError("repository must be AgentRankRepository")
        self._repository = repository
        self._record_limit = max(1, min(int(record_limit), 100000))
        self._expiry_days = max(1, min(int(expiry_days), 365))
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self._questioning_policy = QuestioningPolicy()

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
    ) -> tuple[Optional[PendingQuestion], bool]:
        """首次有效播放同步后创建一个不直接写画像的整体偏好校准问题。"""
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
            return existing, False
        if any(item.status == "pending" for item in questions):
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
        fingerprint = str(getattr(snapshot, "fingerprint", lambda: "")() or "")
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
        summary = f"有效观看样本 {len(strong_samples)} 项"
        if genres:
            summary += "；常见类型 " + "、".join(genres)
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
        event = appended.event
        created_at, expires_at = self._time_window()
        question = PendingQuestion(
            question_id=self._stable_id("pending-question", event.event_id),
            profile_id=target,
            event_id=event.event_id,
            event_sequence=event.sequence,
            candidate_id="profile:playback",
            understanding_record_id=f"playback-calibration:{fingerprint[:24] or event.event_id}",
            question="根据近期有效观看记录，未来推荐更应该延续熟悉体验，还是主动带来变化？",
            options=(
                PendingQuestionOption(
                    option_id="continue_patterns", label="延续已看作品的共同点"
                ),
                PendingQuestionOption(option_id="either", label="都可以"),
                PendingQuestionOption(option_id="uncertain", label="不确定"),
                PendingQuestionOption(option_id="not_me", label="不是我看的"),
            ),
            allow_custom_answer=True,
            uncertainties=("播放记录只能提出偏好假设，不能直接等同于喜欢",),
            evidence_refs=(
                f"event:{event.event_id}",
                f"playback:{fingerprint[:24]}",
            ),
            expected_memory_revision=self._repository.load_preference_memory(
                target
            ).memory_revision,
            created_at=created_at,
            expires_at=expires_at,
            preference_dimension="playback_calibration",
            exploration_level=0,
            confidence_gap=1.0,
        )
        return (
            self._repository.append_pending_question(
                question, limit=self._record_limit
            ),
            True,
        )

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
    ) -> PendingQuestion:
        """从歧义理解和既有偏好缺口构造动态整体偏好问题。"""
        history = [
            item.to_dict()
            for item in self._repository.load_pending_questions(record.profile_id)
        ]
        draft = ask_clarification(
            record.action,
            self._candidate_title(candidate),
            record.uncertainties,
            question_history=history,
            confirmed_memory=memory.to_dict(),
        )
        options = tuple(
            PendingQuestionOption(option_id=f"option_{index}", label=label)
            for index, label in enumerate(draft.get("options") or (), 1)
        )
        created_at, expires_at = self._time_window()
        evidence_refs = [f"event:{event.event_id}"]
        if event.candidate_id:
            evidence_refs.append(f"candidate:{event.candidate_id}")
        return PendingQuestion(
            question_id=self._stable_id("pending-question", event.event_id),
            profile_id=record.profile_id,
            event_id=record.event_id,
            event_sequence=record.event_sequence,
            candidate_id=record.candidate_id,
            understanding_record_id=record.record_id,
            question=draft.get("question"),
            options=options,
            allow_custom_answer=draft.get("allow_custom_answer") is True,
            uncertainties=tuple(draft.get("uncertainties") or ()),
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
        if not questioning.allow_question:
            return None
        return self._repository.append_pending_question(
            self._question(record, event, candidate, memory), limit=self._record_limit
        )
