"""CinePilot Agent 对话、待处理命令和安全边界测试。"""

import asyncio
import copy
import importlib
import json
import sys
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_conversation_test"
PROFILE_ID = "emby:home:user-1"
RUN_ID = "run-conversation"
CANDIDATE_ID = "tmdb:tv:101"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

analysis_module = importlib.import_module(f"{PACKAGE_NAME}.model.analysis")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
snapshot_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate_snapshot")
support_module = importlib.import_module(f"{PACKAGE_NAME}.model.support")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
conversation_model = importlib.import_module(f"{PACKAGE_NAME}.model.conversation")
conversation_module = importlib.import_module(f"{PACKAGE_NAME}.service.conversation")
lifecycle_module = importlib.import_module(f"{PACKAGE_NAME}.service.data_lifecycle")

AnalysisEvidence = analysis_module.AnalysisEvidence
RecommendationAnalysis = analysis_module.RecommendationAnalysis
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
Candidate = candidate_module.Candidate
CandidateSnapshot = snapshot_module.CandidateSnapshot
SupportContribution = support_module.SupportContribution
SupportScore = support_module.SupportScore
AgentRankRepository = repository_module.AgentRankRepository
ConversationMessage = conversation_model.ConversationMessage
ConversationThread = conversation_model.ConversationThread
ConversationError = conversation_module.ConversationError
ConversationReplyParser = conversation_module.ConversationReplyParser
ConversationService = conversation_module.ConversationService
DataLifecycleService = lifecycle_module.DataLifecycleService


class FakePlugin:
    """提供深复制存储、配置写入和运行时门面。"""

    def __init__(self):
        self.data = {}
        self.fail_key_once = ""
        self._config = {
            "enabled": False,
            "conversation_message_limit": 20,
            "analysis_record_limit": 50,
            "confidence_threshold": 0.0,
        }
        self._runtime = SimpleNamespace(config=dict(self._config))
        self._feedback_queue = None

    def get_data(self, key=None):
        """返回独立数据副本。"""
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """保存独立副本并支持一次性失败注入。"""
        if self.fail_key_once and key == self.fail_key_once:
            self.fail_key_once = ""
            raise RuntimeError("injected write failure")
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除测试数据。"""
        self.data.pop(key, None)

    def update_config(self, config=None):
        """模拟 MoviePilot 插件配置持久化。"""
        self.data["persisted_config"] = copy.deepcopy(config or {})


class FakeResult(str):
    """携带脱敏模型来源的 Agent 字符串结果。"""

    def __new__(cls, value):
        """创建测试结果并附加允许持久化的来源字段。"""
        result = super().__new__(cls, value)
        result.provenance = {
            "provider": "家庭配额",
            "model": "critic-chat-model",
            "source": "agent_tokens",
            "base_url": "https://secret.invalid/v1",
            "authorization": "Bearer must-not-leak",
        }
        return result


class FakeConversationAgent:
    """按顺序返回对话结果或注入异常。"""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []
        self.call_times = []

    async def run_conversation(self, prompt, trusted_context):
        """记录只读上下文并返回下一项结果。"""
        self.calls.append((prompt, trusted_context))
        self.call_times.append(time.monotonic())
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return FakeResult(json.dumps(output, ensure_ascii=False))


class ControlledConversationAgent:
    """阻塞前两条跨 profile 消息，用于观测并发和同 profile 保序。"""

    def __init__(self):
        self.release = threading.Event()
        self.lock = threading.Lock()
        self.started = []
        self.active = 0
        self.max_active = 0

    async def run_conversation(self, _prompt, trusted_context):
        """记录开始顺序并等待测试释放。"""
        content = trusted_context.conversation["current_message"]["content"]
        with self.lock:
            self.started.append(content)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            while not self.release.is_set():
                await asyncio.sleep(0.005)
            return FakeResult(json.dumps(_agent_output(reply=f"已处理：{content}")))
        finally:
            with self.lock:
                self.active -= 1


class RateLimitError(RuntimeError):
    """携带 429 状态和 Retry-After 的测试异常。"""

    def __init__(self, retry_after=""):
        super().__init__("429 too many requests")
        self.status_code = 429
        self.response = SimpleNamespace(
            status_code=429,
            headers={"Retry-After": str(retry_after)} if retry_after != "" else {},
        )


class SlowConversationAgent:
    """模拟超过后端总预算的异步上游。"""

    async def run_conversation(self, _prompt, _trusted_context):
        await asyncio.sleep(1)
        return FakeResult(json.dumps(_agent_output()))


def _wait_snapshot(service, predicate, *, profile_id=PROFILE_ID, timeout=3.0):
    """在有界时间内等待后台对话状态满足断言。"""
    deadline = time.monotonic() + timeout
    snapshot = service.snapshot(profile_id)
    while time.monotonic() < deadline:
        if predicate(snapshot):
            return snapshot
        time.sleep(0.01)
        snapshot = service.snapshot(profile_id)
    pytest.fail(f"conversation state did not settle: {snapshot}")


def _wait_until(predicate, *, timeout=3.0):
    """有界等待线程观测条件。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    pytest.fail("conversation concurrency condition did not settle")


def _user_message(snapshot, message_id=""):
    """从公开快照读取目标用户消息。"""
    return next(
        item
        for item in snapshot["messages"]
        if item["role"] == "user"
        and (not message_id or item["message_id"] == message_id)
    )


def _agent_output(
    *,
    intent="read_only",
    reply="这条推荐主要依据你已确认的悬疑偏好。",
    evidence_refs=None,
    commands=None,
    uncertainties=None,
):
    """构造严格的 CinePilot Agent JSON 输出。"""
    return {
        "intent": intent,
        "reply": reply,
        "evidence_refs": list(evidence_refs or []),
        "commands": list(commands or []),
        "uncertainties": list(uncertainties or []),
    }


def _support():
    """构造可精确重算的确定性支持度。"""
    contribution = SupportContribution(
        dimension="theme_weight",
        direction="positive",
        user_value="悬疑",
        candidate_value="悬疑",
        user_refs=("memory:pref-one",),
        candidate_ref=f"candidate:{CANDIDATE_ID}:genres",
        weight_units=8000,
        certainty_units=10000,
        contribution_units=8000,
    )
    return SupportScore.from_contributions("policy-v1", [contribution])


def _seed():
    """保存当前榜单、候选与完整结构化分析。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    support = _support()
    evidence = [
        AnalysisEvidence.from_dict(item.to_dict()) for item in support.contributions
    ]
    analysis = RecommendationAnalysis(
        analysis_id="analysis-current",
        profile_id=PROFILE_ID,
        candidate_id=CANDIDATE_ID,
        run_id=RUN_ID,
        selection_source="agent",
        summary="一场围绕旧案展开的悬疑追查。",
        reason="你偏好悬疑，本作同样围绕旧案。",
        positive_evidence=evidence,
        counter_evidence=[],
        uncertainties=[],
        data_sources=["confirmed_memory", "frozen_candidate"],
        support_percentage=support.percentage,
        policy_version=support.policy_version,
        memory_revision=0,
        persona_version="1.0.0",
        skills_version="1.0.0",
        prompt_fingerprint="a" * 64,
        created_at="2026-07-28T00:00:00+00:00",
    )
    item = RecommendationItem(
        candidate_id=CANDIDATE_ID,
        rank=1,
        title="候选作品",
        media_type="tv",
        summary=analysis.summary,
        reason=analysis.reason,
        support=support,
        selection_source="agent",
        analysis_id=analysis.analysis_id,
    )
    board = RecommendationBoard(
        profile_id=PROFILE_ID,
        username="Alice",
        run_id=RUN_ID,
        status="success",
        recommendations=[item],
    )
    repository.save_candidate_snapshot(
        CandidateSnapshot.create(
            profile_id=PROFILE_ID,
            run_id=RUN_ID,
            profile_version={"run_id": RUN_ID, "schema_version": 6},
            retrieval_plan={"media_types": ["tv"]},
            candidates=[
                Candidate(
                    candidate_id=CANDIDATE_ID,
                    title="候选作品",
                    media_type="tv",
                    overview="围绕旧案展开的悬疑追查。",
                    genres=["悬疑"],
                    regions=["中国"],
                )
            ],
            generated_at="2026-07-28T00:00:00+00:00",
        )
    )
    repository.save_board_with_recommendation_analyses(board, [analysis])
    return plugin, repository


def test_parser_rejects_unknown_fields_write_mismatch_and_forged_evidence():
    """解析器拒绝思维链字段、只读夹带写命令和上下文外引用。"""
    valid = _agent_output()
    with pytest.raises(ConversationError):
        ConversationReplyParser.parse(
            json.dumps({**valid, "chain_of_thought": "must-not-persist"}),
            allowed_evidence_refs=(),
        )
    with pytest.raises(ConversationError):
        ConversationReplyParser.parse(
            json.dumps(
                _agent_output(
                    commands=[
                        {
                            "kind": "profile_tag",
                            "payload": {
                                "kind": "positive",
                                "action": "add",
                                "tag": "悬疑",
                            },
                        }
                    ]
                )
            ),
            allowed_evidence_refs=(),
        )
    with pytest.raises(ConversationError) as caught:
        ConversationReplyParser.parse(
            json.dumps(
                _agent_output(evidence_refs=["candidate:outside"]),
                ensure_ascii=False,
            ),
            allowed_evidence_refs={f"candidate:{CANDIDATE_ID}"},
        )
    assert caught.value.code == "invalid_evidence_reference"
    with pytest.raises(ConversationError) as caught:
        ConversationReplyParser.parse(
            json.dumps(_agent_output(reply="完整句。" * 300), ensure_ascii=False),
            allowed_evidence_refs=(),
        )
    assert caught.value.code == "invalid_agent_output"


def test_read_only_turn_uses_minimal_context_and_is_strictly_idempotent():
    """消息立即入队，只读回答不产生命令且重复投递不重复调用模型。"""
    _plugin, repository = _seed()
    agent = FakeConversationAgent(
        _agent_output(
            evidence_refs=[
                f"candidate:{CANDIDATE_ID}",
                "analysis:analysis-current",
            ]
        )
    )
    service = ConversationService(repository, agent, message_limit=20)

    try:
        first = asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="为什么推荐这部？",
                idempotency_key="message-1",
                actor_id="7",
            )
        )
        duplicate = asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="为什么推荐这部？",
                idempotency_key="message-1",
                actor_id="7",
            )
        )

        assert first["created"] is True
        assert len(first["messages"]) == 1
        assert first["messages"][0]["status"] == "queued"
        assert duplicate["created"] is False
        completed = _wait_snapshot(
            service,
            lambda value: len(value["messages"]) == 2
            and _user_message(value)["status"] == "completed",
        )
        assert len(agent.calls) == 1
        assert completed["commands"] == []
        context = agent.calls[0][1]
        assert context.agent_role == "conversation"
        assert len(context.candidates) == 1
        assert context.archive_feedback["entries"] == ()
        assert context.weights == {}
        assert "raw_output" not in json.dumps(completed, ensure_ascii=False)
    finally:
        service.stop()


def test_unread_agent_replies_are_persisted_per_actor_and_profile():
    """Agent 完成回复后增加未读数，读取后清零且新操作者不继承旧未读。"""
    _plugin, repository = _seed()
    agent = FakeConversationAgent(_agent_output(reply="第一条 Agent 回复。"))
    service = ConversationService(repository, agent, message_limit=20)

    try:
        assert service.status(PROFILE_ID, actor_id="7")["unread_count"] == 0
        asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="开始一次异步对话",
                idempotency_key="unread-message-1",
                actor_id="7",
            )
        )
        _wait_snapshot(
            service,
            lambda value: any(
                item["role"] == "assistant" and item["status"] == "completed"
                for item in value["messages"]
            ),
        )

        unread = service.status(PROFILE_ID, actor_id="7")
        assert unread["unread_count"] == 1
        assert unread["has_pending"] is False
        assert unread["latest_assistant_message_id"]
        assert service.status(PROFILE_ID, actor_id="8")["unread_count"] == 0

        read = service.status(PROFILE_ID, actor_id="7", mark_read=True)
        assert read["unread_count"] == 0
        restarted = ConversationService(repository, FakeConversationAgent(), message_limit=20)
        assert restarted.status(PROFILE_ID, actor_id="7")["unread_count"] == 0
    finally:
        service.stop()


def test_feedback_notice_marks_only_new_receipt_unread_for_feedback_actor():
    """后台反馈回执只增加一条未读，不把既有 Agent 历史重新计入角标。"""
    _plugin, repository = _seed()
    created_at = "2026-07-29T00:00:00+00:00"
    thread = ConversationThread(
        thread_id="thread-feedback-notice",
        profile_id=PROFILE_ID,
        created_by_mp_user_id="7",
        created_at=created_at,
        updated_at=created_at,
        last_message_id="assistant-old",
    )
    old_reply = ConversationMessage(
        message_id="assistant-old",
        profile_id=PROFILE_ID,
        thread_id=thread.thread_id,
        role="assistant",
        content="既有回复",
        status="completed",
        created_at=created_at,
        reply_to="user-old",
    )
    repository.save_conversation_state(thread, [old_reply], [])
    service = ConversationService(repository, FakeConversationAgent(), message_limit=20)

    assert service.append_feedback_notice(
        profile_id=PROFILE_ID,
        event_id="event-like-1",
        actor_id="7",
        candidate_id=CANDIDATE_ID,
        content="已完成点赞理解，当前不需要进一步确认。",
    ) is True
    assert service.status(PROFILE_ID, actor_id="7")["unread_count"] == 1
    assert service.status(PROFILE_ID, actor_id="8")["unread_count"] == 0
    assert service.append_feedback_notice(
        profile_id=PROFILE_ID,
        event_id="event-like-1",
        actor_id="7",
        content="重复回执",
    ) is False


def test_profile_tag_write_waits_for_confirmation_and_confirm_is_idempotent():
    """标签请求确认前零副作用，确认后复用人工偏好服务且可重放。"""
    plugin, repository = _seed()
    agent = FakeConversationAgent(
        _agent_output(
            intent="write_request",
            reply="我可以把科幻记录为明确喜欢，确认后才会生效。",
            commands=[
                {
                    "kind": "profile_tag",
                    "payload": {
                        "kind": "positive",
                        "action": "add",
                        "tag": "科幻",
                    },
                }
            ],
        )
    )
    service = ConversationService(repository, agent, plugin=plugin)

    try:
        sent = asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="以后多推荐科幻",
                idempotency_key="tag-message",
                actor_id="7",
            )
        )
        assert _user_message(sent)["status"] == "queued"
        completed = _wait_snapshot(service, lambda value: bool(value["commands"]))
        command = completed["commands"][0]
        assert command["status"] == "pending_confirmation"
        assert repository.load_profile_preferences(PROFILE_ID).custom_tags == []

        confirmed = service.respond_command(
            profile_id=PROFILE_ID,
            command_id=command["command_id"],
            action="confirm",
            actor_id="7",
        )
        replayed = service.respond_command(
            profile_id=PROFILE_ID,
            command_id=command["command_id"],
            action="confirm",
            actor_id="7",
        )
        assert confirmed["command"]["status"] == "confirmed"
        assert replayed["idempotent"] is True
        assert repository.load_profile_preferences(PROFILE_ID).custom_tags == ["科幻"]
    finally:
        service.stop()


def test_weight_command_is_rejected_after_manual_weights_are_retired():
    """Agent 即使返回旧权重命令，也不会建立待确认项或改写配置。"""
    plugin, repository = _seed()
    agent = FakeConversationAgent(
        _agent_output(
            intent="write_request",
            reply="可以调整题材权重。",
            commands=[
                {
                    "kind": "weight",
                    "payload": {"weight_name": "theme_weight", "value": 0.7},
                }
            ],
        )
    )
    service = ConversationService(repository, agent, plugin=plugin)
    try:
        sent = asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="把题材权重调到0.7",
                idempotency_key="retired-weight",
                actor_id="7",
            )
        )
        assert _user_message(sent)["status"] == "queued"
        failed = _wait_snapshot(
            service,
            lambda value: _user_message(value)["status"] == "retryable_failed",
        )
        assert _user_message(failed)["error_code"] == "invalid_agent_command"
        assert failed["commands"] == []
        assert "weights" not in plugin._config
    finally:
        service.stop()


def test_agent_failure_keeps_retryable_draft_and_retry_reuses_message():
    """模型失败保留同一草稿，重试成功后不创建第二条用户消息。"""
    plugin, repository = _seed()
    agent = FakeConversationAgent(
        RuntimeError("upstream unavailable"),
        _agent_output(reply="重试后已恢复回答。"),
    )
    service = ConversationService(repository, agent, plugin=plugin)

    try:
        sent = asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="解释当前榜单",
                idempotency_key="retry-message",
                actor_id="7",
            )
        )
        assert _user_message(sent)["status"] == "queued"
        failed = _wait_snapshot(
            service,
            lambda value: _user_message(value)["status"] == "retryable_failed",
        )
        failed_message = _user_message(failed)
        assert failed_message["error_code"] == "agent_unavailable"
        assert "upstream" not in json.dumps(failed, ensure_ascii=False)

        retried = asyncio.run(
            service.retry(
                profile_id=PROFILE_ID,
                message_id=failed_message["message_id"],
                actor_id="7",
            )
        )
        assert _user_message(retried)["status"] == "queued"
        completed = _wait_snapshot(
            service, lambda value: _user_message(value)["status"] == "completed"
        )
        user_messages = [
            item for item in completed["messages"] if item["role"] == "user"
        ]
        assert len(user_messages) == 1
        assert user_messages[0]["message_id"] == failed_message["message_id"]
        assert len(agent.calls) == 2
    finally:
        service.stop()


def test_stale_write_command_fails_draft_instead_of_sticking_processing():
    """榜单外命令进入可重试失败态，不留下永久 processing 消息。"""
    plugin, repository = _seed()
    agent = FakeConversationAgent(
        _agent_output(
            intent="write_request",
            reply="我会先生成待确认的忽略命令。",
            commands=[
                {"kind": "ignore", "payload": {"candidate_id": "tmdb:tv:999"}}
            ],
        )
    )
    service = ConversationService(repository, agent, plugin=plugin)

    try:
        sent = asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="忽略不存在的候选",
                idempotency_key="stale-command",
                actor_id="7",
            )
        )
        assert _user_message(sent)["status"] == "queued"
        snapshot = _wait_snapshot(
            service,
            lambda value: _user_message(value)["status"] == "retryable_failed",
        )
        user_message = _user_message(snapshot)
        assert user_message["error_code"] == "stale_agent_command"
        assert snapshot["commands"] == []
    finally:
        service.stop()


def test_learning_reset_confirmation_clears_old_messages_and_keeps_idempotent_receipt():
    """对话发起的学习重置清空旧内容，仅保留可重放的确认回执。"""
    plugin, repository = _seed()
    agent = FakeConversationAgent(
        _agent_output(
            intent="write_request",
            reply="可以重置学习数据，确认后才会执行。",
            commands=[{"kind": "reset_learning", "payload": {}}],
        )
    )
    service = ConversationService(repository, agent, plugin=plugin)
    try:
        sent = asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="重置学习数据",
                idempotency_key="reset-learning",
                actor_id="7",
            )
        )
        assert _user_message(sent)["status"] == "queued"
        completed = _wait_snapshot(service, lambda value: bool(value["commands"]))
        command_id = completed["commands"][0]["command_id"]

        confirmed = service.respond_command(
            profile_id=PROFILE_ID,
            command_id=command_id,
            action="confirm",
            actor_id="7",
        )
        replayed = service.respond_command(
            profile_id=PROFILE_ID,
            command_id=command_id,
            action="confirm",
            actor_id="7",
        )
        snapshot = service.snapshot(PROFILE_ID)
        assert confirmed["conversation_cleared"] is True
        assert replayed["idempotent"] is True
        assert snapshot["messages"] == []
        assert [item["status"] for item in snapshot["commands"]] == ["confirmed"]
    finally:
        service.stop()


def test_same_profile_is_serial_and_two_profiles_can_run_concurrently():
    """同 profile 严格保序，跨 profile 最多两个 worker 并发。"""
    _plugin, repository = _seed()
    other_profile = "emby:home:user-2"
    agent = ControlledConversationAgent()
    service = ConversationService(
        repository,
        agent,
        profile_ids=(PROFILE_ID, other_profile),
        max_workers=2,
        poll_seconds=0.01,
    )
    try:
        first = asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="home-1",
                idempotency_key="home-1",
                actor_id="7",
            )
        )
        second = asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="home-2",
                idempotency_key="home-2",
                actor_id="7",
            )
        )
        other = asyncio.run(
            service.send(
                profile_id=other_profile,
                content="other-1",
                idempotency_key="other-1",
                actor_id="8",
            )
        )
        assert _user_message(first)["status"] == "queued"
        assert any(
            item["content"] == "home-2" and item["status"] == "queued"
            for item in second["messages"]
        )
        assert _user_message(other)["status"] == "queued"

        _wait_until(lambda: len(agent.started) == 2)
        assert set(agent.started) == {"home-1", "other-1"}
        assert agent.max_active == 2
        assert "home-2" not in agent.started

        agent.release.set()
        home_completed = _wait_snapshot(
            service,
            lambda value: len(
                [
                    item
                    for item in value["messages"]
                    if item["role"] == "user" and item["status"] == "completed"
                ]
            )
            == 2,
        )
        _wait_snapshot(
            service,
            lambda value: _user_message(value)["status"] == "completed",
            profile_id=other_profile,
        )
        assert agent.started == ["home-1", "other-1", "home-2"]
        assert agent.max_active == 2
        assert len(
            [item for item in home_completed["messages"] if item["role"] == "assistant"]
        ) == 2
    finally:
        agent.release.set()
        service.stop()


def test_reload_recovers_processing_message_without_duplicate_reply():
    """reload 将 processing 恢复入队，并只生成一条稳定回复。"""
    _plugin, repository = _seed()
    created_at = "2026-07-29T00:00:00+00:00"
    thread = ConversationThread(
        thread_id="thread-reload",
        profile_id=PROFILE_ID,
        created_by_mp_user_id="7",
        created_at=created_at,
        updated_at=created_at,
        last_message_id="message-reload",
    )
    message = ConversationMessage(
        message_id="message-reload",
        profile_id=PROFILE_ID,
        thread_id=thread.thread_id,
        role="user",
        content="恢复这条消息",
        status="processing",
        created_at=created_at,
        idempotency_key="reload-key",
        created_by_mp_user_id="7",
    )
    repository.save_conversation_state(thread, [message], [])
    agent = FakeConversationAgent(_agent_output(reply="恢复后完成。"))
    service = ConversationService(
        repository,
        agent,
        profile_ids=(PROFILE_ID,),
        poll_seconds=0.01,
    )
    try:
        service.start()
        completed = _wait_snapshot(
            service, lambda value: _user_message(value)["status"] == "completed"
        )
        assert len(agent.calls) == 1
        assert len(
            [item for item in completed["messages"] if item["role"] == "assistant"]
        ) == 1
        assert completed["messages"][-1]["reply_to"] == message.message_id
    finally:
        service.stop()


def test_429_uses_retry_after_then_exponential_backoff_within_shared_budget():
    """429 读取 Retry-After，后续按指数退避且最终复用同一消息成功。"""
    _plugin, repository = _seed()
    agent = FakeConversationAgent(
        RateLimitError("0.03"),
        RateLimitError(),
        _agent_output(reply="限流解除后完成。"),
    )
    service = ConversationService(
        repository,
        agent,
        total_timeout_seconds=0.3,
        retry_base_seconds=0.02,
        retry_max_seconds=0.04,
        poll_seconds=0.01,
    )
    try:
        sent = asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="限流后继续",
                idempotency_key="rate-limit-retry",
                actor_id="7",
            )
        )
        assert _user_message(sent)["status"] == "queued"
        completed = _wait_snapshot(
            service, lambda value: _user_message(value)["status"] == "completed"
        )
        assert len(agent.calls) == 3
        assert agent.call_times[1] - agent.call_times[0] >= 0.02
        assert agent.call_times[2] - agent.call_times[1] >= 0.03
        assert len(
            [item for item in completed["messages"] if item["role"] == "assistant"]
        ) == 1
    finally:
        service.stop()


def test_429_and_slow_upstream_end_as_retryable_failure_at_total_budget():
    """429 与慢响应都共享单次总预算，并落为可重试失败。"""
    scenarios = (
        (
            FakeConversationAgent(RateLimitError("1")),
            "conversation_rate_limited",
            "rate-limit-budget",
        ),
        (SlowConversationAgent(), "conversation_timeout", "slow-budget"),
    )
    for agent, expected_code, key in scenarios:
        _plugin, repository = _seed()
        service = ConversationService(
            repository,
            agent,
            total_timeout_seconds=0.05,
            retry_base_seconds=0.01,
            retry_max_seconds=0.02,
            poll_seconds=0.01,
        )
        try:
            asyncio.run(
                service.send(
                    profile_id=PROFILE_ID,
                    content=key,
                    idempotency_key=key,
                    actor_id="7",
                )
            )
            failed = _wait_snapshot(
                service,
                lambda value: _user_message(value)["status"]
                == "retryable_failed",
            )
            assert _user_message(failed)["error_code"] == expected_code
            assert len(
                [item for item in failed["messages"] if item["role"] == "assistant"]
            ) == 0
        finally:
            service.stop()


def test_export_and_public_snapshot_do_not_expose_actor_keys_or_agent_raw_output():
    """对话快照与脱敏导出不包含操作者、幂等键、地址或认证值。"""
    plugin, repository = _seed()
    agent = FakeConversationAgent(_agent_output())
    service = ConversationService(repository, agent, plugin=plugin)
    try:
        public = asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="说明一下",
                idempotency_key="secret-idempotency",
                actor_id="private-actor",
            )
        )
        completed = _wait_snapshot(
            service, lambda value: _user_message(value)["status"] == "completed"
        )
        exported = DataLifecycleService(repository, plugin._config).export_profile(
            PROFILE_ID
        )
        serialized = json.dumps(
            {"public": public, "completed": completed, "export": exported},
            ensure_ascii=False,
        )
        for forbidden in (
            "private-actor",
            "secret-idempotency",
            "secret.invalid",
            "Bearer",
            "authorization",
            "raw_output",
            "chain_of_thought",
        ):
            assert forbidden not in serialized
    finally:
        service.stop()


def test_conversation_state_write_failure_rolls_back_thread_and_records():
    """线程或记录保存失败时原子恢复，不留下半个草稿。"""
    plugin, repository = _seed()
    plugin.fail_key_once = repository._learning_key(
        "conversation_messages", PROFILE_ID
    )
    service = ConversationService(
        repository,
        FakeConversationAgent(_agent_output()),
        plugin=plugin,
    )

    with pytest.raises(RuntimeError, match="injected write failure"):
        asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="这次保存会失败",
                idempotency_key="rollback-message",
                actor_id="7",
            )
        )
    assert repository.load_conversation_thread(PROFILE_ID) is None
    assert repository.load_conversation_records(PROFILE_ID) == ([], [])
