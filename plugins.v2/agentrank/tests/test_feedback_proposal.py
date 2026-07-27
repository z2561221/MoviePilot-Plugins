"""记忆提案、歧义问询、幂等恢复和零写入边界测试。"""

import asyncio
import copy
import importlib
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_feedback_proposal_test"
PROFILE_ID = "emby:home:user-1"
FIXED_NOW = datetime(2026, 7, 28, 8, 0, tzinfo=timezone.utc)

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

feedback_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback")
decision_module = importlib.import_module(
    f"{PACKAGE_NAME}.model.feedback_decision"
)
understanding_module = importlib.import_module(
    f"{PACKAGE_NAME}.model.feedback_understanding"
)
queue_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback_queue")
memory_module = importlib.import_module(f"{PACKAGE_NAME}.model.memory")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
proposal_service_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.feedback_proposal"
)
understanding_service_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.feedback_understanding"
)
lifecycle_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.data_lifecycle"
)

FeedbackEvent = feedback_module.FeedbackEvent
MemoryProposal = decision_module.MemoryProposal
PendingQuestion = decision_module.PendingQuestion
FeedbackSignal = understanding_module.FeedbackSignal
FeedbackUnderstandingRecord = understanding_module.FeedbackUnderstandingRecord
FeedbackQueueJob = queue_module.FeedbackQueueJob
PreferenceMemoryItem = memory_module.PreferenceMemoryItem
AgentRankRepository = repository_module.AgentRankRepository
FeedbackProposalService = proposal_service_module.FeedbackProposalService
FeedbackUnderstandingService = understanding_service_module.FeedbackUnderstandingService
DataLifecycleService = lifecycle_module.DataLifecycleService


class FakePlugin:
    """用独立副本模拟 MoviePilot 插件数据接口。"""

    def __init__(self):
        self.data = {}

    def get_data(self, key=None):
        """读取指定插件数据的独立副本。"""
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """保存指定插件数据的独立副本。"""
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除指定插件数据。"""
        self.data.pop(key, None)


class ExplodingAdapter:
    """确保恢复已存在理解时不会再次调用 Agent。"""

    async def run_feedback(self, _prompt, _trusted_context):
        """任何重复模型调用都使测试失败。"""
        raise AssertionError("existing understanding must not call Agent again")


def _event(
    repository,
    *,
    key="feedback-1",
    kind="like",
    comment="喜欢节奏",
    candidate_id="tmdb:tv:101",
):
    """创建并持久化一条反馈事件。"""
    return repository.append_feedback_event(
        FeedbackEvent(
            profile_id=PROFILE_ID,
            kind=kind,
            candidate_id=candidate_id,
            run_id="run-1",
            analysis_id="analysis-1",
            comment=comment,
            idempotency_key=key,
        )
    ).event


def _signal(event, *, polarity="positive", value="快节奏"):
    """构造绑定当前事件与候选的反馈信号。"""
    return FeedbackSignal(
        category="pacing",
        value=value,
        polarity=polarity,
        certainty=0.8,
        evidence_refs=(
            f"event:{event.event_id}",
            f"candidate:{event.candidate_id}",
        ),
    )


def _understanding(
    event,
    *,
    outcome="understood",
    signals=(),
    conflicts=(),
    uncertainties=(),
    memory_revision=0,
):
    """构造一条已完成且不含模型原文的反馈理解。"""
    return FeedbackUnderstandingRecord(
        record_id=f"feedback-understanding:{event.event_id}",
        profile_id=event.profile_id,
        event_id=event.event_id,
        event_sequence=event.sequence,
        candidate_id=event.candidate_id,
        action=event.kind,
        outcome=outcome,
        restatement="你明确表示喜欢这部作品的快节奏",
        signals=tuple(signals),
        conflicts=tuple(conflicts),
        uncertainties=tuple(uncertainties),
        prompt_fingerprint="fingerprint",
        memory_revision=memory_revision,
        model_source="agent_tokens",
        model="gpt-feedback",
        model_call_count=1,
    )


def _service(repository):
    """构造使用固定时钟的确定性提案服务。"""
    return FeedbackProposalService(
        repository, now_factory=lambda: FIXED_NOW, expiry_days=30
    )


def _seed_memory(repository, *, tombstone=False):
    """用事件序号一投影一条确认偏好或归档墓碑。"""
    source = _event(
        repository,
        key="memory-source",
        comment="已确认慢节奏偏好",
        candidate_id="tmdb:tv:100",
    )
    item = PreferenceMemoryItem(
        item_id="memory-pacing",
        category="pacing",
        value="慢节奏",
        polarity="positive",
        strength=0.8,
        certainty=0.9,
        evidence_refs=(f"event:{source.event_id}",),
        source_event_sequence=source.sequence,
        created_at=FIXED_NOW.isoformat(),
        status="archived" if tombstone else "active",
        tombstone=tombstone,
    )
    result = repository.project_preference_memory(
        PROFILE_ID,
        [item],
        expected_revision=0,
        source_event_sequence=source.sequence,
    )
    assert result.applied is True
    return result.memory


def test_understood_feedback_creates_evidence_linked_add_proposal_without_memory_write():
    """明确反馈生成新增预览，重复物化幂等且长期记忆保持空白。"""
    repository = AgentRankRepository(FakePlugin())
    event = _event(repository)
    before = repository.load_preference_memory(PROFILE_ID)
    record = _understanding(event, signals=(_signal(event),))
    service = _service(repository)

    first = service.materialize(
        record,
        event=event,
        candidate={"candidate_id": event.candidate_id, "title": "候选作品"},
        memory=before,
    )
    second = service.materialize(
        record,
        event=event,
        candidate={"candidate_id": event.candidate_id, "title": "候选作品"},
        memory=before,
    )

    assert isinstance(first, MemoryProposal)
    assert first == second
    assert first.restatement == record.restatement
    assert first.changes[0].operation == "add"
    assert first.changes[0].preview == "拟新增偏好：喜欢“快节奏”"
    assert f"event:{event.event_id}" in first.evidence_refs
    assert first.expected_memory_revision == 0
    assert first.status == "pending_confirmation"
    assert first.expires_at == "2026-08-27T08:00:00+00:00"
    assert len(repository.load_memory_proposals(PROFILE_ID)) == 1
    assert repository.load_pending_questions(PROFILE_ID) == []
    assert repository.load_preference_memory(PROFILE_ID) == before


@pytest.mark.parametrize(
    ("tombstone", "polarity", "expected_operation"),
    [
        (False, "negative", "weaken"),
        (True, "positive", "restore"),
    ],
)
def test_proposal_previews_conflict_or_archived_restore_explicitly(
    tombstone, polarity, expected_operation
):
    """相反偏好显示调整，归档谱系必须显示恢复而不能静默复活。"""
    repository = AgentRankRepository(FakePlugin())
    memory = _seed_memory(repository, tombstone=tombstone)
    event = _event(
        repository,
        key=f"target-{expected_operation}",
        kind="dislike" if polarity == "negative" else "like",
        comment="明确纠正慢节奏偏好",
    )
    signal = _signal(event, polarity=polarity, value="慢节奏")
    conflicts = (
        {
            "memory_item_id": "memory-pacing",
            "category": "pacing",
            "value": "慢节奏",
            "reason": "与已确认偏好方向相反",
        },
    ) if not tombstone else ()
    record = _understanding(
        event,
        signals=(signal,),
        conflicts=conflicts,
        memory_revision=memory.memory_revision,
    )

    proposal = _service(repository).materialize(
        record,
        event=event,
        candidate={"candidate_id": event.candidate_id, "title": "候选作品"},
        memory=memory,
    )

    assert proposal.changes[0].operation == expected_operation
    assert proposal.changes[0].target_memory_item_ids == ("memory-pacing",)
    assert "恢复已归档" in proposal.changes[0].preview if tombstone else "调整" in proposal.changes[0].preview
    assert repository.load_preference_memory(PROFILE_ID) == memory


def test_ambiguous_feedback_creates_three_options_and_custom_answer_only():
    """歧义反馈只生成三选一加自定义问询，不生成记忆提案。"""
    repository = AgentRankRepository(FakePlugin())
    event = _event(repository, comment="")
    before = repository.load_preference_memory(PROFILE_ID)
    record = _understanding(
        event,
        outcome="ambiguous",
        uncertainties=("需要确认具体喜欢的内容特征",),
    )

    question = _service(repository).materialize(
        record,
        event=event,
        candidate={"candidate_id": event.candidate_id, "title": "候选作品"},
        memory=before,
    )

    assert isinstance(question, PendingQuestion)
    assert question.question == "你喜欢《候选作品》的哪一点？"
    assert [item.option_id for item in question.options] == [
        "option_1",
        "option_2",
        "option_3",
    ]
    assert question.allow_custom_answer is True
    assert question.reminder_policy == "unselected"
    assert question.next_remind_at == ""
    assert repository.load_memory_proposals(PROFILE_ID) == []
    assert repository.load_preference_memory(PROFILE_ID) == before


def test_exclusion_only_creates_no_proposal_or_question():
    """无评论忽略已经语义明确，不生成口味提案也不额外追问。"""
    repository = AgentRankRepository(FakePlugin())
    event = _event(repository, kind="ignore", comment="")
    memory = repository.load_preference_memory(PROFILE_ID)
    record = _understanding(event, outcome="exclusion_only")

    decision = _service(repository).materialize(
        record,
        event=event,
        candidate={"candidate_id": event.candidate_id, "title": "候选作品"},
        memory=memory,
    )

    assert decision is None
    assert repository.load_memory_proposals(PROFILE_ID) == []
    assert repository.load_pending_questions(PROFILE_ID) == []


def test_existing_understanding_materializes_missing_question_without_agent_retry():
    """理解已落盘但问询写入中断时，队列重试只补问询而不重调模型。"""
    repository = AgentRankRepository(FakePlugin())
    event = _event(repository, comment="")
    record = _understanding(
        event,
        outcome="ambiguous",
        uncertainties=("需要确认具体原因",),
    )
    repository.append_feedback_understanding(record)
    service = FeedbackUnderstandingService(
        repository,
        ExplodingAdapter(),
        proposal_service=_service(repository),
    )

    restored = asyncio.run(service.handle_job(FeedbackQueueJob.from_event(event)))

    assert restored == record
    assert len(repository.load_pending_questions(PROFILE_ID)) == 1


def test_pending_records_survive_limits_and_safe_export_contains_no_internal_reasoning():
    """未完成项不被数量上限挤掉，导出只含安全提案和问询字段。"""
    repository = AgentRankRepository(FakePlugin())
    service = _service(repository)
    for index in range(1, 4):
        event = _event(repository, key=f"pending-{index}", comment="")
        record = _understanding(
            event,
            outcome="ambiguous",
            uncertainties=("token=secret-value https://secret.invalid/path",),
        )
        question = service.materialize(
            record,
            event=event,
            candidate={"candidate_id": event.candidate_id, "title": f"候选{index}"},
            memory=repository.load_preference_memory(PROFILE_ID),
        )
        if index == 1:
            key = repository._learning_key("pending_questions", PROFILE_ID)
            raw = repository._plugin.get_data(key=key)
            raw[0] = replace(question, status="answered").to_dict()
            repository._plugin.save_data(key=key, value=raw)

    removed = repository.prune_pending_questions(PROFILE_ID, 1)
    retained = repository.load_pending_questions(PROFILE_ID)
    exported = DataLifecycleService(repository).export_profile(PROFILE_ID)
    serialized = json.dumps(exported, ensure_ascii=False)

    assert removed == 1
    assert len(retained) == 2
    assert all(item.status == "pending" for item in retained)
    assert len(exported["pending_questions"]) == 2
    assert "secret.invalid" not in serialized
    assert "secret-value" not in serialized
    for forbidden in ("prompt", "raw_output", "chain_of_thought", "思维链"):
        assert forbidden not in serialized
