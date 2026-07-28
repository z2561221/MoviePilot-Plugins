"""专属影评师对话、待确认命令和安全边界测试。"""

import asyncio
import copy
import importlib
import json
import sys
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
            "weights": {"theme_weight": 0.8},
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

    async def run_conversation(self, prompt, trusted_context):
        """记录只读上下文并返回下一项结果。"""
        self.calls.append((prompt, trusted_context))
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return FakeResult(json.dumps(output, ensure_ascii=False))


def _agent_output(
    *,
    intent="read_only",
    reply="这条推荐主要依据你已确认的悬疑偏好。",
    evidence_refs=None,
    commands=None,
    uncertainties=None,
):
    """构造严格的专属影评师 JSON 输出。"""
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
    """只读回答不产生命令，同幂等消息不重复调用模型。"""
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
    assert duplicate["created"] is False
    assert len(agent.calls) == 1
    assert len(first["messages"]) == 2
    assert first["commands"] == []
    context = agent.calls[0][1]
    assert context.agent_role == "conversation"
    assert len(context.candidates) == 1
    assert context.archive_feedback["entries"] == ()
    assert context.weights == {}
    assert "raw_output" not in json.dumps(first, ensure_ascii=False)


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

    sent = asyncio.run(
        service.send(
            profile_id=PROFILE_ID,
            content="以后多推荐科幻",
            idempotency_key="tag-message",
            actor_id="7",
        )
    )
    command = sent["commands"][0]
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


def test_weight_command_requires_superuser_and_newer_command_supersedes_old():
    """全局权重仅管理员可确认，同目标新命令替代旧待确认项。"""
    plugin, repository = _seed()
    agent = FakeConversationAgent(
        _agent_output(
            intent="write_request",
            reply="可以调整题材权重，需管理员确认。",
            commands=[
                {
                    "kind": "weight",
                    "payload": {"weight_name": "theme_weight", "value": 0.7},
                }
            ],
        ),
        _agent_output(
            intent="write_request",
            reply="已更新为新的待确认值。",
            commands=[
                {
                    "kind": "weight",
                    "payload": {"weight_name": "theme_weight", "value": 0.9},
                }
            ],
        ),
    )
    service = ConversationService(repository, agent, plugin=plugin)
    first = asyncio.run(
        service.send(
            profile_id=PROFILE_ID,
            content="把题材权重调到0.7",
            idempotency_key="weight-1",
            actor_id="7",
        )
    )
    second = asyncio.run(
        service.send(
            profile_id=PROFILE_ID,
            content="改成0.9",
            idempotency_key="weight-2",
            actor_id="7",
        )
    )
    commands = {item["command_id"]: item for item in second["commands"]}
    first_id = first["commands"][0]["command_id"]
    second_id = next(
        item["command_id"]
        for item in second["commands"]
        if item["status"] == "pending_confirmation"
    )
    assert commands[first_id]["status"] == "superseded"
    assert commands[second_id]["supersedes"] == first_id
    with pytest.raises(ConversationError) as caught:
        service.respond_command(
            profile_id=PROFILE_ID,
            command_id=second_id,
            action="confirm",
            actor_id="7",
            is_superuser=False,
        )
    assert caught.value.code == "superuser_required"
    assert plugin._config["weights"]["theme_weight"] == 0.8

    result = service.respond_command(
        profile_id=PROFILE_ID,
        command_id=second_id,
        action="confirm",
        actor_id="admin",
        is_superuser=True,
    )
    assert result["command"]["status"] == "confirmed"
    assert plugin._config["weights"]["theme_weight"] == 0.9


def test_agent_failure_keeps_retryable_draft_and_retry_reuses_message():
    """模型失败保留同一草稿，重试成功后不创建第二条用户消息。"""
    plugin, repository = _seed()
    agent = FakeConversationAgent(
        RuntimeError("upstream unavailable"),
        _agent_output(reply="重试后已恢复回答。"),
    )
    service = ConversationService(repository, agent, plugin=plugin)

    with pytest.raises(ConversationError) as caught:
        asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="解释当前榜单",
                idempotency_key="retry-message",
                actor_id="7",
            )
        )
    assert caught.value.code == "conversation_failed"
    failed = service.snapshot(PROFILE_ID)
    failed_message = next(
        item for item in failed["messages"] if item["role"] == "user"
    )
    assert failed_message["status"] == "failed"
    assert "upstream" not in json.dumps(failed, ensure_ascii=False)

    retried = asyncio.run(
        service.retry(
            profile_id=PROFILE_ID,
            message_id=failed_message["message_id"],
            actor_id="7",
        )
    )
    user_messages = [item for item in retried["messages"] if item["role"] == "user"]
    assert len(user_messages) == 1
    assert user_messages[0]["message_id"] == failed_message["message_id"]
    assert user_messages[0]["status"] == "completed"
    assert len(agent.calls) == 2


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

    with pytest.raises(ConversationError) as caught:
        asyncio.run(
            service.send(
                profile_id=PROFILE_ID,
                content="忽略不存在的候选",
                idempotency_key="stale-command",
                actor_id="7",
            )
        )
    assert caught.value.code == "stale_agent_command"
    snapshot = service.snapshot(PROFILE_ID)
    user_message = next(
        item for item in snapshot["messages"] if item["role"] == "user"
    )
    assert user_message["status"] == "failed"
    assert user_message["error_code"] == "stale_agent_command"
    assert snapshot["commands"] == []


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
    sent = asyncio.run(
        service.send(
            profile_id=PROFILE_ID,
            content="重置学习数据",
            idempotency_key="reset-learning",
            actor_id="7",
        )
    )
    command_id = sent["commands"][0]["command_id"]

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


def test_export_and_public_snapshot_do_not_expose_actor_keys_or_agent_raw_output():
    """对话快照与脱敏导出不包含操作者、幂等键、地址或认证值。"""
    plugin, repository = _seed()
    agent = FakeConversationAgent(_agent_output())
    service = ConversationService(repository, agent, plugin=plugin)
    public = asyncio.run(
        service.send(
            profile_id=PROFILE_ID,
            content="说明一下",
            idempotency_key="secret-idempotency",
            actor_id="private-actor",
        )
    )
    exported = DataLifecycleService(repository, plugin._config).export_profile(
        PROFILE_ID
    )
    serialized = json.dumps({"public": public, "export": exported}, ensure_ascii=False)
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
