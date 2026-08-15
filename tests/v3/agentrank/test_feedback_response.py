"""待确认提醒、问询回答、幂等恢复与零记忆写入测试。"""

import copy
import importlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"
PACKAGE_NAME = "agentrank_feedback_response_test"
PROFILE_ID = "emby:home:user-1"
FIXED_NOW = datetime(2026, 7, 28, 8, 0, tzinfo=timezone.utc)

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

feedback_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback")
decision_module = importlib.import_module(
    f"{PACKAGE_NAME}.model.feedback_decision"
)
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
response_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.feedback_response"
)
queue_service_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.feedback_queue"
)

FeedbackEvent = feedback_module.FeedbackEvent
MemoryProposal = decision_module.MemoryProposal
MemoryProposalChange = decision_module.MemoryProposalChange
PendingQuestion = decision_module.PendingQuestion
PendingQuestionOption = decision_module.PendingQuestionOption
AgentRankRepository = repository_module.AgentRankRepository
FeedbackDecisionError = response_module.FeedbackDecisionError
FeedbackResponseService = response_module.FeedbackResponseService
FeedbackQueueError = queue_service_module.FeedbackQueueError


class FakePlugin:
    """用线程安全内存字典模拟 MoviePilot 插件数据接口。"""

    def __init__(self):
        """创建空数据空间和可重入锁。"""
        self.data = {}
        self.lock = threading.RLock()

    def get_data(self, key=None):
        """读取指定插件数据的独立副本。"""
        with self.lock:
            return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """保存指定插件数据的独立副本。"""
        with self.lock:
            self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除指定插件数据。"""
        with self.lock:
            self.data.pop(key, None)


class FixedClock:
    """提供测试可推进的 UTC 时钟。"""

    def __init__(self, value=FIXED_NOW):
        """保存初始时间。"""
        self.value = value

    def __call__(self):
        """返回当前测试时间。"""
        return self.value

    def advance(self, **delta):
        """按 timedelta 参数推进测试时间。"""
        self.value += timedelta(**delta)


class FakeQueue:
    """记录回答事件入队并可注入一次失败。"""

    def __init__(self, *, fail_times=0):
        """设置需要失败的前置调用次数。"""
        self.fail_times = int(fail_times)
        self.events = []

    def enqueue_event(self, event):
        """记录事件或模拟持久队列失败。"""
        if self.fail_times > 0:
            self.fail_times -= 1
            raise FeedbackQueueError("反馈理解任务入队失败")
        self.events.append(event)
        return SimpleNamespace(status="queued")


def _event(repository, *, key="original-1", kind="like", candidate_id="tmdb:tv:1"):
    """创建并持久化问询来源反馈事件。"""
    return repository.append_feedback_event(
        FeedbackEvent(
            profile_id=PROFILE_ID,
            kind=kind,
            candidate_id=candidate_id,
            run_id="run-1",
            analysis_id="analysis-1",
            comment="",
            created_by_mp_user_id="mp-user-1",
            idempotency_key=key,
        )
    ).event


def _question(repository, event, *, suffix="1", expires_at=None):
    """创建并持久化一个歧义反馈问询。"""
    question = PendingQuestion(
        question_id=f"question:{suffix}",
        profile_id=PROFILE_ID,
        event_id=event.event_id,
        event_sequence=event.sequence,
        candidate_id=event.candidate_id,
        understanding_record_id=f"understanding:{suffix}",
        question="你喜欢这部作品的哪一点？",
        options=(
            PendingQuestionOption("option_1", "节奏紧凑"),
            PendingQuestionOption("option_2", "人物塑造"),
            PendingQuestionOption("option_3", "世界观设定"),
        ),
        allow_custom_answer=True,
        uncertainties=("需要确认具体匹配点",),
        evidence_refs=(f"event:{event.event_id}",),
        expected_memory_revision=0,
        created_at=FIXED_NOW.isoformat(),
        expires_at=(expires_at or FIXED_NOW + timedelta(days=30)).isoformat(),
    )
    return repository.append_pending_question(question)


def _proposal(repository, event, *, suffix="1", expires_at=None):
    """创建并持久化一个待确认记忆提案。"""
    evidence = (f"event:{event.event_id}",)
    proposal = MemoryProposal(
        proposal_id=f"proposal:{suffix}",
        profile_id=PROFILE_ID,
        event_id=event.event_id,
        event_sequence=event.sequence,
        candidate_id=event.candidate_id,
        understanding_record_id=f"understanding:{suffix}",
        restatement="你明确表示喜欢这部作品的节奏",
        changes=(
            MemoryProposalChange(
                change_id=f"change:{suffix}",
                operation="add",
                category="pacing",
                value="快节奏",
                polarity="positive",
                certainty=0.8,
                evidence_refs=evidence,
                preview="拟新增偏好：喜欢快节奏",
            ),
        ),
        evidence_refs=evidence,
        impact_preview=("后续排序会适度提高快节奏作品",),
        expected_memory_revision=0,
        created_at=FIXED_NOW.isoformat(),
        expires_at=(expires_at or FIXED_NOW + timedelta(days=30)).isoformat(),
    )
    return repository.append_memory_proposal(proposal)


def test_feedback_response_exposes_no_reminder_actions_and_pending_does_not_learn():
    """问询保持待回答且不学习，响应服务不再暴露任何提醒入口。"""
    clock = FixedClock()
    repository = AgentRankRepository(FakePlugin())
    question = _question(repository, _event(repository))
    before = repository.load_preference_memory(PROFILE_ID)
    service = FeedbackResponseService(repository, now_factory=clock)

    clock.advance(days=20)

    assert not hasattr(service, "set_reminder")
    assert not hasattr(service, "claim_due_reminders")
    current = repository.get_pending_question(PROFILE_ID, question.question_id)
    assert current.status == "pending"
    assert current.reminder_policy == "unselected"
    assert current.next_remind_at == ""
    assert repository.load_preference_memory(PROFILE_ID) == before


def test_legacy_reminder_fields_remain_readable_but_have_no_runtime_behavior():
    """旧提醒字段可兼容读取，但不会恢复提醒 API 或改变待处理事实。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    question = _question(repository, _event(repository))
    key = repository._learning_key("pending_questions", PROFILE_ID)
    raw = plugin.get_data(key=key)
    raw[0]["reminder_policy"] = "in_3_days"
    raw[0]["next_remind_at"] = (FIXED_NOW + timedelta(days=3)).isoformat()
    plugin.save_data(key=key, value=raw)
    service = FeedbackResponseService(repository, now_factory=FixedClock())

    loaded = repository.get_pending_question(PROFILE_ID, question.question_id)

    assert loaded.reminder_policy == "in_3_days"
    assert loaded.next_remind_at
    assert loaded.status == "pending"
    assert not hasattr(service, "set_reminder")
    assert not hasattr(service, "claim_due_reminders")


def test_reject_and_expire_are_terminal_without_memory_projection():
    """拒绝、关闭和到期只结束待确认状态，不修改长期记忆。"""
    clock = FixedClock()
    repository = AgentRankRepository(FakePlugin())
    question = _question(repository, _event(repository, key="dismiss-event"))
    proposal = _proposal(
        repository,
        _event(repository, key="expire-event", candidate_id="tmdb:tv:2"),
        expires_at=FIXED_NOW + timedelta(hours=1),
    )
    before = repository.load_preference_memory(PROFILE_ID)
    service = FeedbackResponseService(repository, now_factory=clock)

    dismissed = service.reject(PROFILE_ID, "question", question.question_id)
    clock.advance(hours=2)
    expired = service.expire_due(PROFILE_ID)

    assert dismissed.status == "dismissed"
    assert [item.proposal_id for item in expired] == [proposal.proposal_id]
    assert repository.get_memory_proposal(PROFILE_ID, proposal.proposal_id).status == "expired"
    assert repository.load_preference_memory(PROFILE_ID) == before


@pytest.mark.parametrize(
    ("option_id", "custom_answer", "expected_text"),
    [
        ("option_2", "", "人物塑造"),
        ("", "我喜欢配乐与场景共同制造的沉浸感", "我喜欢配乐与场景共同制造的沉浸感"),
    ],
)
def test_question_answers_create_superseding_events_and_queue_them(
    option_id, custom_answer, expected_text
):
    """选项和自定义回答均形成可审计的新事件并重新进入理解队列。"""
    repository = AgentRankRepository(FakePlugin())
    original = _event(repository)
    question = _question(repository, original)
    queue = FakeQueue()
    before = repository.load_preference_memory(PROFILE_ID)
    service = FeedbackResponseService(
        repository, feedback_queue=queue, now_factory=FixedClock()
    )

    result = service.answer_question(
        PROFILE_ID,
        question.question_id,
        idempotency_key="answer-1",
        actor_id="mp-user-1",
        option_id=option_id,
        custom_answer=custom_answer,
    )

    assert result.question.status == "answered"
    assert result.question.selected_option_id == option_id
    assert result.question.answer_text == expected_text
    assert result.question.answered_by_mp_user_id == "mp-user-1"
    assert result.event.kind == original.kind
    assert result.event.comment == expected_text
    assert result.event.supersedes == original.event_id
    assert result.event.analysis_id == original.analysis_id
    assert result.queue_status == "queued"
    assert queue.events == [result.event]
    assert repository.load_preference_memory(PROFILE_ID) == before


def test_duplicate_answer_is_idempotent_and_conflicting_key_is_rejected():
    """同一回答可安全重试，复用他人幂等键则明确冲突。"""
    repository = AgentRankRepository(FakePlugin())
    original = _event(repository)
    question = _question(repository, original)
    service = FeedbackResponseService(repository, now_factory=FixedClock())

    first = service.answer_question(
        PROFILE_ID,
        question.question_id,
        idempotency_key="answer-1",
        actor_id="mp-user-1",
        option_id="option_1",
    )
    duplicate = service.answer_question(
        PROFILE_ID,
        question.question_id,
        idempotency_key="answer-1",
        actor_id="mp-user-1",
        option_id="option_1",
    )

    assert first.event_created is True
    assert duplicate.event_created is False
    assert duplicate.event == first.event
    assert len(repository.load_feedback_events(PROFILE_ID)) == 2

    second_original = _event(
        repository, key="original-2", candidate_id="tmdb:tv:2"
    )
    second_question = _question(repository, second_original, suffix="2")
    with pytest.raises(FeedbackDecisionError) as caught:
        service.answer_question(
            PROFILE_ID,
            second_question.question_id,
            idempotency_key="answer-1",
            actor_id="mp-user-1",
            option_id="option_1",
        )
    assert caught.value.code == "idempotency_conflict"


def test_answer_can_be_revised_and_reopened_without_rewriting_old_events():
    """已回答问询可追加修订事实，也可清空展示答案后重新进入待办。"""
    repository = AgentRankRepository(FakePlugin())
    original = _event(repository)
    question = _question(repository, original)
    queue = FakeQueue()
    service = FeedbackResponseService(
        repository, feedback_queue=queue, now_factory=FixedClock()
    )

    first = service.answer_question(
        PROFILE_ID,
        question.question_id,
        idempotency_key="answer-first",
        actor_id="mp-user-1",
        option_id="option_1",
    )
    revised = service.answer_question(
        PROFILE_ID,
        question.question_id,
        idempotency_key="answer-revised",
        actor_id="mp-user-1",
        custom_answer="其实更看重角色关系是否可信",
    )
    reopened = service.reopen_question(PROFILE_ID, question.question_id)

    assert revised.event.supersedes == first.event.event_id
    assert revised.question.answer_text == "其实更看重角色关系是否可信"
    assert [item.event_id for item in repository.load_feedback_events(PROFILE_ID)] == [
        original.event_id,
        first.event.event_id,
        revised.event.event_id,
    ]
    assert reopened.status == "pending"
    assert reopened.answer_text == ""
    assert reopened.answer_event_id == ""
    assert queue.events == [first.event, revised.event]


def test_dismissed_question_can_be_reopened_but_expired_question_cannot():
    """关闭问询可重新打开，过期事实保持终态。"""
    clock = FixedClock()
    repository = AgentRankRepository(FakePlugin())
    dismissed = _question(repository, _event(repository, key="dismiss-reopen"))
    expired = _question(
        repository,
        _event(repository, key="expired-reopen", candidate_id="tmdb:tv:2"),
        suffix="expired",
        expires_at=FIXED_NOW + timedelta(hours=1),
    )
    service = FeedbackResponseService(repository, now_factory=clock)

    service.reject(PROFILE_ID, "question", dismissed.question_id)
    reopened = service.reopen_question(PROFILE_ID, dismissed.question_id)
    clock.advance(hours=2)
    service.expire_due(PROFILE_ID)

    assert reopened.status == "pending"
    with pytest.raises(FeedbackDecisionError) as caught:
        service.reopen_question(PROFILE_ID, expired.question_id)
    assert caught.value.code == "question_cannot_reopen"


def test_queue_failure_keeps_answer_audited_and_retry_recovers_enqueue():
    """入队失败后回答状态与事件保留，同一请求重试可恢复队列。"""
    repository = AgentRankRepository(FakePlugin())
    original = _event(repository)
    question = _question(repository, original)
    queue = FakeQueue(fail_times=1)
    service = FeedbackResponseService(
        repository, feedback_queue=queue, now_factory=FixedClock()
    )

    with pytest.raises(FeedbackQueueError):
        service.answer_question(
            PROFILE_ID,
            question.question_id,
            idempotency_key="answer-retry",
            actor_id="mp-user-1",
            option_id="option_3",
        )

    stored = repository.get_pending_question(PROFILE_ID, question.question_id)
    assert stored.status == "answered"
    assert stored.answer_event_id
    retry = service.answer_question(
        PROFILE_ID,
        question.question_id,
        idempotency_key="answer-retry",
        actor_id="mp-user-1",
        option_id="option_3",
    )
    assert retry.event_created is False
    assert retry.queue_status == "queued"
    assert queue.events == [retry.event]
    assert len(repository.load_feedback_events(PROFILE_ID)) == 2


def test_concurrent_answer_and_dismiss_have_one_terminal_winner():
    """回答与关闭并发时仅一种终态生效，不产生矛盾学习事实。"""
    repository = AgentRankRepository(FakePlugin())
    question = _question(repository, _event(repository))
    service = FeedbackResponseService(repository, now_factory=FixedClock())
    barrier = threading.Barrier(2)

    def answer():
        """等待并发起回答。"""
        barrier.wait()
        return service.answer_question(
            PROFILE_ID,
            question.question_id,
            idempotency_key="answer-race",
            actor_id="mp-user-1",
            option_id="option_1",
        )

    def dismiss():
        """等待并发起关闭。"""
        barrier.wait()
        return service.reject(PROFILE_ID, "question", question.question_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(answer), executor.submit(dismiss)]
        results = []
        errors = []
        for future in futures:
            try:
                results.append(future.result())
            except FeedbackDecisionError as error:
                errors.append(error)

    stored = repository.get_pending_question(PROFILE_ID, question.question_id)
    assert len(results) == 1
    assert len(errors) == 1
    assert errors[0].code == "decision_already_resolved"
    if stored.status == "answered":
        assert len(repository.load_feedback_events(PROFILE_ID)) == 2
        assert stored.answer_event_id
    else:
        assert stored.status == "dismissed"
        assert len(repository.load_feedback_events(PROFILE_ID)) == 1


def test_answer_requires_auditable_actor_identity():
    """缺少 MP 用户身份时不得生成回答事件。"""
    repository = AgentRankRepository(FakePlugin())
    question = _question(repository, _event(repository))
    service = FeedbackResponseService(repository, now_factory=FixedClock())

    with pytest.raises(FeedbackDecisionError) as caught:
        service.answer_question(
            PROFILE_ID,
            question.question_id,
            idempotency_key="answer-no-actor",
            actor_id="",
            option_id="option_1",
        )

    assert caught.value.code == "actor_id_invalid"
    assert repository.get_pending_question(PROFILE_ID, question.question_id).status == "pending"
    assert len(repository.load_feedback_events(PROFILE_ID)) == 1
