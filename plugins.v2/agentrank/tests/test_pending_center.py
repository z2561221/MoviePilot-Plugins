"""统一待确认中心、提醒并发、响应脱敏与零隐式学习测试。"""

import copy
import importlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_pending_center_test"
PROFILE_ID = "emby:home:user-1"
NOW = datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

conversation_model = importlib.import_module(f"{PACKAGE_NAME}.model.conversation")
decision_model = importlib.import_module(f"{PACKAGE_NAME}.model.feedback_decision")
feedback_model = importlib.import_module(f"{PACKAGE_NAME}.model.feedback")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
conversation_module = importlib.import_module(f"{PACKAGE_NAME}.service.conversation")
response_module = importlib.import_module(f"{PACKAGE_NAME}.service.feedback_response")
projection_module = importlib.import_module(f"{PACKAGE_NAME}.service.memory_projection")
pending_module = importlib.import_module(f"{PACKAGE_NAME}.service.pending_center")
lifecycle_module = importlib.import_module(f"{PACKAGE_NAME}.service.data_lifecycle")

ConversationCommand = conversation_model.ConversationCommand
ConversationThread = conversation_model.ConversationThread
MemoryProposal = decision_model.MemoryProposal
MemoryProposalChange = decision_model.MemoryProposalChange
PendingQuestion = decision_model.PendingQuestion
PendingQuestionOption = decision_model.PendingQuestionOption
FeedbackEvent = feedback_model.FeedbackEvent
AgentRankRepository = repository_module.AgentRankRepository
ConversationService = conversation_module.ConversationService
FeedbackResponseService = response_module.FeedbackResponseService
MemoryProjectionService = projection_module.MemoryProjectionService
PendingCenterService = pending_module.PendingCenterService
DataLifecycleService = lifecycle_module.DataLifecycleService


class FakePlugin:
    """提供线程安全且深复制的插件数据接口。"""

    def __init__(self):
        """创建空数据空间和最小配置。"""
        self.data = {}
        self.lock = threading.RLock()
        self._config = {"enabled": True, "weights": {}}
        self._runtime = None
        self._feedback_queue = None

    def get_data(self, key=None):
        """读取数据副本。"""
        with self.lock:
            return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """保存数据副本。"""
        with self.lock:
            self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除指定数据。"""
        with self.lock:
            self.data.pop(key, None)

    def update_config(self, config=None):
        """记录配置更新。"""
        self._config = copy.deepcopy(config or {})


class Clock:
    """提供可推进的 UTC 测试时钟。"""

    def __init__(self):
        """从固定时间开始。"""
        self.value = NOW

    def __call__(self):
        """返回当前时间。"""
        return self.value

    def advance(self, **kwargs):
        """推进当前时间。"""
        self.value += timedelta(**kwargs)


class Queue:
    """记录问询回答进入异步理解队列。"""

    def __init__(self):
        """创建空事件列表。"""
        self.events = []

    def enqueue_event(self, event):
        """记录反馈事件并返回队列状态。"""
        self.events.append(event)
        return type("Queued", (), {"status": "queued"})()


def _event(repository, key, candidate_id):
    """创建带审计用户的反馈来源事件。"""
    return repository.append_feedback_event(
        FeedbackEvent(
            profile_id=PROFILE_ID,
            kind="like",
            candidate_id=candidate_id,
            run_id="run-1",
            analysis_id="analysis-1",
            comment="",
            created_by_mp_user_id="mp-user-1",
            idempotency_key=key,
        )
    ).event


def _proposal(repository, event):
    """创建一个待确认记忆提案。"""
    evidence = (f"event:{event.event_id}",)
    return repository.append_memory_proposal(
        MemoryProposal(
            proposal_id="proposal-1",
            profile_id=PROFILE_ID,
            event_id=event.event_id,
            event_sequence=event.sequence,
            candidate_id=event.candidate_id,
            understanding_record_id="understanding-1",
            restatement="你可能明确偏好节奏紧凑的叙事",
            changes=(
                MemoryProposalChange(
                    change_id="change-1",
                    operation="add",
                    category="pacing",
                    value="节奏紧凑",
                    polarity="positive",
                    certainty=0.8,
                    evidence_refs=evidence,
                    preview="拟新增偏好：节奏紧凑",
                ),
            ),
            evidence_refs=evidence,
            impact_preview=("后续排序适度提高节奏紧凑作品",),
            expected_memory_revision=0,
            created_at=NOW.isoformat(),
            expires_at=(NOW + timedelta(days=30)).isoformat(),
        )
    )


def _question(repository, event):
    """创建一个带三个选项的待回答问询。"""
    return repository.append_pending_question(
        PendingQuestion(
            question_id="question-1",
            profile_id=PROFILE_ID,
            event_id=event.event_id,
            event_sequence=event.sequence,
            candidate_id=event.candidate_id,
            understanding_record_id="understanding-2",
            question="你更喜欢这部作品的节奏、人物还是世界观？",
            options=(
                PendingQuestionOption("pace", "节奏"),
                PendingQuestionOption("character", "人物"),
                PendingQuestionOption("world", "世界观"),
            ),
            allow_custom_answer=True,
            uncertainties=("需要确认具体匹配点",),
            evidence_refs=(f"event:{event.event_id}",),
            expected_memory_revision=0,
            created_at=NOW.isoformat(),
            expires_at=(NOW + timedelta(days=30)).isoformat(),
        )
    )


def _command(repository):
    """创建一个仅请求者可操作的待确认对话命令。"""
    thread = ConversationThread(
        thread_id="thread-1",
        profile_id=PROFILE_ID,
        created_by_mp_user_id="mp-user-1",
        created_at=NOW.isoformat(),
        updated_at=NOW.isoformat(),
        pending_command_ids=("command-1",),
    )
    command = ConversationCommand(
        command_id="command-1",
        profile_id=PROFILE_ID,
        thread_id=thread.thread_id,
        source_message_id="message-1",
        kind="profile_tag",
        title="更新明确偏好标签",
        preview="添加喜欢标签：悬疑",
        payload={"kind": "positive", "action": "add", "tag": "悬疑"},
        requested_by_mp_user_id="mp-user-1",
        created_at=NOW.isoformat(),
    )
    repository.save_conversation_state(thread, [], [command])
    return command


def _services():
    """创建共享仓储、时钟和统一中心。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    clock = Clock()
    queue = Queue()
    response = FeedbackResponseService(
        repository, feedback_queue=queue, now_factory=clock
    )
    conversation = ConversationService(
        repository, object(), plugin=plugin, now_factory=clock
    )
    projection = MemoryProjectionService(repository, now_factory=clock)
    center = PendingCenterService(
        repository,
        feedback_response=response,
        memory_projection=projection,
        conversation=conversation,
    )
    return plugin, repository, clock, queue, center


def test_center_aggregates_three_types_without_actor_or_evidence_leak():
    """统一列表聚合三类项目且不公开身份、证据引用和命令载荷。"""
    _, repository, _, _, center = _services()
    proposal = _proposal(repository, _event(repository, "p-event", "tmdb:1"))
    question = _question(repository, _event(repository, "q-event", "tmdb:2"))
    command = _command(repository)

    data = center.list_pending(PROFILE_ID, actor_id="mp-user-1")
    rendered = str(data)

    assert data["counts"] == {"proposal": 1, "question": 1, "command": 1}
    assert {item["item_id"] for item in data["items"]} == {
        proposal.proposal_id,
        question.question_id,
        command.command_id,
    }
    assert "requested_by_mp_user_id" not in rendered
    assert "created_by_mp_user_id" not in rendered
    assert "evidence_refs" not in rendered
    assert "payload" not in rendered
    assert center.list_pending(PROFILE_ID, actor_id="other")["counts"]["command"] == 0


def test_question_answer_and_reminders_never_return_raw_event_or_implicitly_learn():
    """稍后、不提醒和回答仅改变待确认事实，不隐式写入长期记忆。"""
    _, repository, _, queue, center = _services()
    question = _question(repository, _event(repository, "q-event", "tmdb:2"))
    before = repository.load_preference_memory(PROFILE_ID)

    reminded = center.respond(
        profile_id=PROFILE_ID,
        item_type="question",
        item_id=question.question_id,
        action="remind",
        reminder_policy="in_3_days",
        actor_id="mp-user-1",
    )
    answered = center.respond(
        profile_id=PROFILE_ID,
        item_type="question",
        item_id=question.question_id,
        action="answer",
        option_id="character",
        idempotency_key="answer-question-1",
        actor_id="mp-user-1",
    )

    assert reminded["item"]["reminder_policy"] == "in_3_days"
    assert answered["item"]["status"] == "answered"
    assert answered["queue_status"] == "queued"
    assert "event" not in answered
    rendered = str(answered)
    assert "created_by_mp_user_id" not in rendered
    assert "answer_text" not in rendered
    assert "event_id" not in rendered
    assert queue.events[0].supersedes
    assert repository.load_preference_memory(PROFILE_ID) == before


def test_proposal_confirmation_is_explicit_and_rejection_writes_no_memory():
    """只有确认提案才投影记忆，拒绝另一提案不产生学习。"""
    _, repository, _, _, center = _services()
    proposal = _proposal(repository, _event(repository, "p-event", "tmdb:1"))

    confirmed = center.respond(
        profile_id=PROFILE_ID,
        item_type="proposal",
        item_id=proposal.proposal_id,
        action="confirm",
        actor_id="mp-user-1",
    )

    assert confirmed["item"]["status"] == "confirmed"
    assert confirmed["memory_revision"] == 1
    assert repository.load_preference_memory(PROFILE_ID).memory_revision == 1


def test_three_types_due_reminders_are_claimed_once_under_concurrency():
    """提案、问询和命令提醒在并发领取时各自最多出现一次。"""
    _, repository, clock, _, center = _services()
    proposal = _proposal(repository, _event(repository, "p-event", "tmdb:1"))
    question = _question(repository, _event(repository, "q-event", "tmdb:2"))
    command = _command(repository)
    for item_type, item_id in (
        ("proposal", proposal.proposal_id),
        ("question", question.question_id),
        ("command", command.command_id),
    ):
        center.respond(
            profile_id=PROFILE_ID,
            item_type=item_type,
            item_id=item_id,
            action="remind",
            reminder_policy="in_1_day",
            actor_id="mp-user-1",
        )
    clock.advance(days=1)

    with ThreadPoolExecutor(max_workers=8) as executor:
        batches = list(executor.map(lambda _: center.claim_due_notices(PROFILE_ID), range(8)))
    notices = [item for batch in batches for item in batch]

    assert {(item.item.item_type, item.item.item_id) for item in notices} == {
        ("proposal", proposal.proposal_id),
        ("question", question.question_id),
        ("command", command.command_id),
    }
    assert len(notices) == 3
    assert center.claim_due_notices(PROFILE_ID) == []
    assert repository.load_preference_memory(PROFILE_ID).memory_revision == 0


def test_export_keeps_command_reminder_audit_without_requester_identity():
    """脱敏导出保留提醒策略，但不导出命令请求者或 Telegram 会话。"""
    plugin, repository, _, _, center = _services()
    command = _command(repository)
    center.respond(
        profile_id=PROFILE_ID,
        item_type="command",
        item_id=command.command_id,
        action="remind",
        reminder_policy="in_7_days",
        actor_id="mp-user-1",
    )

    exported = DataLifecycleService(repository, plugin._config).export_profile(
        PROFILE_ID
    )
    rendered = str(exported)
    exported_command = exported["conversation"]["commands"][0]

    assert exported_command["reminder_policy"] == "in_7_days"
    assert exported_command["next_remind_at"]
    assert "requested_by_mp_user_id" not in rendered
    assert "telegram_pending_sessions" not in rendered
