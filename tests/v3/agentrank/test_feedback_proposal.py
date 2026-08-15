"""记忆提案、歧义问询、幂等恢复和零写入边界测试。"""

import asyncio
import copy
import importlib
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"
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
playback_module = importlib.import_module(f"{PACKAGE_NAME}.model.playback")
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
PlaybackSample = playback_module.PlaybackSample
PlaybackSnapshot = playback_module.PlaybackSnapshot
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


def test_first_playback_calibration_creates_one_agent_event_from_strong_evidence():
    """首次有效播放同步只创建一条交给 Agent 提问的受信事件。"""
    repository = AgentRankRepository(FakePlugin())
    service = FeedbackProposalService(repository, now_factory=lambda: FIXED_NOW)
    weak = PlaybackSnapshot(
        PROFILE_ID,
        source="playback_reporting",
        confidence="medium",
        status="ready",
        samples=[PlaybackSample("weak-1", "只点开过", "movie", watch_minutes=5)],
    )
    strong = PlaybackSnapshot(
        PROFILE_ID,
        source="playback_reporting",
        confidence="high",
        status="ready",
        samples=[
            PlaybackSample(
                "strong-1",
                "已看作品甲",
                "movie",
                genres=["科幻", "悬疑"],
                completed=True,
                watch_minutes=110,
            ),
            PlaybackSample(
                "strong-2",
                "重复观看乙",
                "tv",
                genres=["剧情"],
                play_count=2,
                completed_episode_count=3,
            ),
        ],
    )

    assert service.create_playback_calibration(PROFILE_ID, weak) == (None, False)
    event, created = service.create_playback_calibration(
        PROFILE_ID, strong, actor_id="mp-user-1"
    )
    duplicate, duplicate_created = service.create_playback_calibration(
        PROFILE_ID, strong, actor_id="mp-user-1"
    )

    assert created is True
    assert event.kind == "playback_calibration"
    assert event.candidate_id == "profile:playback"
    assert "《已看作品甲》《重复观看乙》" in event.comment
    assert "科幻、悬疑、剧情" in event.comment
    assert duplicate.event_id == event.event_id
    assert duplicate_created is False
    assert repository.load_pending_questions(PROFILE_ID) == []


def test_explicit_pending_interview_uses_real_context_and_bypasses_quiet_mode():
    """显式验收可在安静模式创建动态问题，但仍不写长期偏好。"""
    repository = AgentRankRepository(FakePlugin())
    service = FeedbackProposalService(
        repository,
        now_factory=lambda: FIXED_NOW,
        interaction_mode="quiet",
    )
    snapshot = PlaybackSnapshot(
        PROFILE_ID,
        source="playback_reporting",
        status="ready",
        samples=[
            PlaybackSample(
                "sample-1",
                "命运石之门",
                "tv",
                genres=["科幻", "悬疑"],
                completed_episode_count=24,
            )
        ],
    )
    board = SimpleNamespace(
        recommendations=[SimpleNamespace(title="来自新世界")]
    )

    event, created = service.create_pending_interview(
        PROFILE_ID,
        snapshot,
        board,
        actor_id="mp-user-1",
        idempotency_key="pending-interview-start",
        total=2,
    )

    assert created is True
    assert event.analysis_id.startswith("pending-interview:")
    assert event.analysis_id.endswith(":2")
    assert "《命运石之门》" in event.comment
    assert "《来自新世界》" in event.comment
    assert "不写入长期偏好" in event.comment

    record = FeedbackUnderstandingRecord(
        record_id=f"understanding:{event.event_id}",
        profile_id=PROFILE_ID,
        event_id=event.event_id,
        event_sequence=event.sequence,
        candidate_id=event.candidate_id,
        action=event.kind,
        outcome="ambiguous",
        restatement="需要确认下一次推荐方向",
        clarification_question="第1/2题：这两部作品中，你更想延续哪种体验？",
        clarification_options=("时间谜题", "世界观探索", "换种类型"),
        clarification_allow_custom_answer=True,
        clarification_dimension="ignored-by-host",
        created_at=FIXED_NOW.isoformat(),
    )
    question = service.materialize(
        record,
        event=event,
        candidate={"candidate_id": "profile:playback"},
        memory=repository.load_preference_memory(PROFILE_ID),
        question_draft={
            "question": record.clarification_question,
            "options": list(record.clarification_options),
            "allow_custom_answer": True,
            "preference_dimension": "ignored-by-host",
        },
    )

    assert isinstance(question, PendingQuestion)
    assert question.preference_dimension.startswith("pending_interview:")
    assert any("第 1/2 题" in item for item in question.uncertainties)
    assert repository.load_preference_memory(PROFILE_ID).items == ()


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
    clarification_question="关于《候选作品》，你这次点赞主要认可哪一点？",
    clarification_options=("悬念铺陈", "人物关系", "视觉表达"),
    clarification_dimension="candidate_like_reason",
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
        clarification_question=(
            clarification_question if outcome == "ambiguous" else ""
        ),
        clarification_options=(
            tuple(clarification_options) if outcome == "ambiguous" else ()
        ),
        clarification_allow_custom_answer=outcome == "ambiguous",
        clarification_dimension=(
            clarification_dimension if outcome == "ambiguous" else ""
        ),
        clarification_exploration_level=1 if outcome == "ambiguous" else 0,
        clarification_confidence_gap=0.7 if outcome == "ambiguous" else 0.0,
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


def _seed_mature_memory(repository):
    """投影五个覆盖维度的确认偏好，构造低打扰画像。"""
    source = _event(
        repository,
        key="mature-memory-source",
        comment="已确认多维整体偏好",
        candidate_id="tmdb:tv:99",
    )
    items = [
        PreferenceMemoryItem(
            item_id=f"memory-{category}",
            category=category,
            value=value,
            polarity="positive",
            strength=0.8,
            certainty=0.9,
            evidence_refs=(f"event:{source.event_id}",),
            source_event_sequence=source.sequence,
            created_at=FIXED_NOW.isoformat(),
        )
        for category, value in (
            ("genre", "悬疑"),
            ("creator", "导演风格"),
            ("pacing", "紧凑"),
            ("character", "群像"),
            ("novelty", "熟悉框架有新意"),
        )
    ]
    result = repository.project_preference_memory(
        PROFILE_ID,
        items,
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


def test_ambiguous_feedback_uses_agent_question_and_clear_candidate_context():
    """歧义反馈逐字采用 Agent 草稿，并明确展示当前作品与触发原因。"""
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
    assert question.question == "关于《候选作品》，你这次点赞主要认可哪一点？"
    assert question.uncertainties == (
        "提问背景：你刚刚对《候选作品》点了赞，但 Agent 还缺少一个会影响后续推荐的关键信息。",
    )
    assert len(question.options) == 3
    assert [item.option_id for item in question.options] == [
        "option_1", "option_2", "option_3"
    ]
    assert [item.label for item in question.options] == [
        "悬念铺陈", "人物关系", "视觉表达"
    ]
    assert question.preference_dimension == "candidate_like_reason"
    assert question.exploration_level == 1
    assert 0.0 < question.confidence_gap <= 1.0
    assert question.allow_custom_answer is True
    assert question.reminder_policy == "unselected"
    assert question.next_remind_at == ""
    assert repository.load_memory_proposals(PROFILE_ID) == []
    assert repository.load_preference_memory(PROFILE_ID) == before


def test_ambiguous_feedback_without_agent_question_has_no_template_fallback():
    """理解记录没有合格 Agent 草稿时，不创建任何宿主固定问询。"""
    repository = AgentRankRepository(FakePlugin())
    event = _event(repository, comment="")
    record = replace(
        _understanding(
            event,
            outcome="ambiguous",
            uncertainties=("需要确认具体喜欢的内容特征",),
        ),
        clarification_question="",
        clarification_options=(),
    )

    decision = _service(repository).materialize(
        record,
        event=event,
        candidate={"candidate_id": event.candidate_id, "title": "候选作品"},
        memory=repository.load_preference_memory(PROFILE_ID),
    )

    assert decision is None
    assert repository.load_pending_questions(PROFILE_ID) == []


@pytest.mark.parametrize(
    ("interaction_mode", "expected_question"),
    [("auto", False), ("normal", True), ("quiet", False)],
)
def test_interaction_mode_controls_routine_question_frequency(
    interaction_mode, expected_question
):
    """三档模式控制成熟画像的日常问询频率。"""
    repository = AgentRankRepository(FakePlugin())
    memory = _seed_mature_memory(repository)
    event = _event(repository, key=f"mode-{interaction_mode}", comment="")
    record = _understanding(
        event,
        outcome="ambiguous",
        uncertainties=("仍可补充细节",),
        memory_revision=memory.memory_revision,
    )

    decision = FeedbackProposalService(
        repository,
        now_factory=lambda: FIXED_NOW,
        interaction_mode=interaction_mode,
    ).materialize(
        record,
        event=event,
        candidate={"candidate_id": event.candidate_id, "title": "候选作品"},
        memory=memory,
    )

    assert isinstance(decision, PendingQuestion) is expected_question


def test_quiet_mode_still_questions_on_preference_conflict():
    """安静模式只压制日常问询，明显偏好冲突仍需要确认。"""
    repository = AgentRankRepository(FakePlugin())
    memory = _seed_mature_memory(repository)
    event = _event(repository, key="quiet-conflict", kind="dislike", comment="")
    record = _understanding(
        event,
        outcome="ambiguous",
        conflicts=(
            {
                "memory_item_id": "memory-pacing",
                "category": "pacing",
                "value": "紧凑",
                "reason": "当前反馈与已确认偏好冲突",
            },
        ),
        uncertainties=("需要确认是否口味变化",),
        memory_revision=memory.memory_revision,
    )

    decision = FeedbackProposalService(
        repository,
        now_factory=lambda: FIXED_NOW,
        interaction_mode="quiet",
    ).materialize(
        record,
        event=event,
        candidate={"candidate_id": event.candidate_id, "title": "候选作品"},
        memory=memory,
    )

    assert isinstance(decision, PendingQuestion)


def test_quiet_mode_skips_first_playback_calibration():
    """安静模式不自动创建首次播放校准问题。"""
    repository = AgentRankRepository(FakePlugin())
    snapshot = PlaybackSnapshot(
        PROFILE_ID,
        source="playback_reporting",
        confidence="high",
        status="ready",
        samples=[
            PlaybackSample(
                "quiet-strong-1",
                "已看作品",
                "movie",
                genres=["科幻"],
                completed=True,
                watch_minutes=100,
            )
        ],
    )

    decision = FeedbackProposalService(
        repository,
        now_factory=lambda: FIXED_NOW,
        interaction_mode="quiet",
    ).create_playback_calibration(PROFILE_ID, snapshot)

    assert decision == (None, False)
    assert repository.load_pending_questions(PROFILE_ID) == []


def test_only_one_pending_global_question_is_active_per_profile():
    """新的歧义事件复用当前待问询，避免连续弹出标准化问题。"""
    repository = AgentRankRepository(FakePlugin())
    service = _service(repository)
    first_event = _event(repository, key="question-first", comment="")
    second_event = _event(
        repository,
        key="question-second",
        candidate_id="tmdb:tv:2",
        comment="",
    )
    first = service.materialize(
        _understanding(first_event, outcome="ambiguous", uncertainties=("信息不足",)),
        event=first_event,
        candidate={"candidate_id": first_event.candidate_id, "title": "作品一"},
        memory=repository.load_preference_memory(PROFILE_ID),
    )
    second = service.materialize(
        _understanding(second_event, outcome="ambiguous", uncertainties=("仍需了解",)),
        event=second_event,
        candidate={"candidate_id": second_event.candidate_id, "title": "作品二"},
        memory=repository.load_preference_memory(PROFILE_ID),
    )

    assert second.question_id == first.question_id
    assert len(repository.load_pending_questions(PROFILE_ID)) == 1


def test_mature_profile_suppresses_routine_question_but_conflict_restores_it():
    """低打扰画像不再常规追问，明显冲突仍恢复必要问询。"""
    repository = AgentRankRepository(FakePlugin())
    memory = _seed_mature_memory(repository)
    service = _service(repository)
    routine_event = _event(repository, key="mature-routine", comment="")
    routine_record = _understanding(
        routine_event,
        outcome="ambiguous",
        uncertainties=("仍可补充细节",),
        memory_revision=memory.memory_revision,
    )

    assert service.questioning_state(PROFILE_ID, memory=memory) == "low_interruption"
    assert service.materialize(
        routine_record,
        event=routine_event,
        candidate={"candidate_id": routine_event.candidate_id, "title": "候选作品"},
        memory=memory,
    ) is None

    conflict_event = _event(
        repository,
        key="mature-conflict",
        kind="dislike",
        comment="",
        candidate_id="tmdb:tv:102",
    )
    conflict_record = _understanding(
        conflict_event,
        outcome="ambiguous",
        conflicts=(
            {
                "memory_item_id": "memory-pacing",
                "category": "pacing",
                "value": "紧凑",
                "reason": "当前反馈与已确认偏好冲突",
            },
        ),
        uncertainties=("需要确认是否口味变化",),
        memory_revision=memory.memory_revision,
    )
    question = service.materialize(
        conflict_record,
        event=conflict_event,
        candidate={"candidate_id": conflict_event.candidate_id, "title": "候选作品"},
        memory=memory,
    )

    assert isinstance(question, PendingQuestion)


def test_dismissed_question_raises_interruption_cost_without_negative_memory():
    """关闭问询提高打扰成本并抑制连续追问，但不写任何负向偏好。"""
    repository = AgentRankRepository(FakePlugin())
    service = _service(repository)
    first_event = _event(repository, key="dismiss-cost-first", comment="")
    first = service.materialize(
        _understanding(first_event, outcome="ambiguous", uncertainties=("信息不足",)),
        event=first_event,
        candidate={"candidate_id": first_event.candidate_id, "title": "作品一"},
        memory=repository.load_preference_memory(PROFILE_ID),
    )
    dismissed = replace(first, status="dismissed", resolved_at=FIXED_NOW.isoformat())
    assert repository.replace_pending_question(dismissed, expected_status="pending") is True
    before = repository.load_preference_memory(PROFILE_ID)
    second_event = _event(
        repository,
        key="dismiss-cost-second",
        comment="",
        candidate_id="tmdb:tv:103",
    )

    second = service.materialize(
        _understanding(second_event, outcome="ambiguous", uncertainties=("仍可询问",)),
        event=second_event,
        candidate={"candidate_id": second_event.candidate_id, "title": "作品二"},
        memory=before,
    )

    assert second is None
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


def test_single_pending_record_survives_limits_and_safe_export_is_sanitized():
    """唯一未完成问询不被裁剪，导出只含安全提案和问询字段。"""
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
            raw[0] = replace(
                question,
                status="answered",
                answer_text="已回答",
                answer_event_id="event:answered",
                answered_by_mp_user_id="mp-user-1",
                resolved_at=FIXED_NOW.isoformat(),
            ).to_dict()
            repository._plugin.save_data(key=key, value=raw)

    removed = repository.prune_pending_questions(PROFILE_ID, 1)
    retained = repository.load_pending_questions(PROFILE_ID)
    exported = DataLifecycleService(repository).export_profile(PROFILE_ID)
    serialized = json.dumps(exported, ensure_ascii=False)

    assert removed == 1
    assert len(retained) == 1
    assert all(item.status == "pending" for item in retained)
    assert len(exported["pending_questions"]) == 1
    assert "secret.invalid" not in serialized
    assert "secret-value" not in serialized
    for forbidden in ("prompt", "raw_output", "chain_of_thought", "思维链"):
        assert forbidden not in serialized
