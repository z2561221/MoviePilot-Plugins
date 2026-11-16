"""对话隔离、单次读取和待办标题复用的定向检查。"""

from collections import Counter
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.plugins.agentrank.controller.api import AgentRankApiController
from app.plugins.agentrank.model.conversation import (
    ConversationCommand, ConversationMessage, ConversationThread,
)
from app.plugins.agentrank.model.feedback import FeedbackEvent
from app.plugins.agentrank.model.feedback_decision import PendingQuestion, PendingQuestionOption
from app.plugins.agentrank.service.conversation import ConversationService
from app.plugins.agentrank.service.pending_center import PendingCenterService
from app.plugins.agentrank.storage.repository import AgentRankRepository


PROFILE = "emby:home:user-1"
NOW = "2026-11-16T00:00:00+00:00"


class MemoryPlugin:
    """只在内存中保存本用例的数据，并记录实际存储访问。"""

    def __init__(self):
        """绑定一个已配置画像和独立仓储。"""
        self.data = {}
        self.reads = Counter()
        self.writes = Counter()
        self._config = {"emby_identities": [{
            "server_name": "home", "user_id": "user-1", "username": "reader",
            "profile_id": PROFILE, "schema_version": 1,
        }]}
        self._runtime = None
        self._repository = AgentRankRepository(self)

    def get_data(self, key=None):
        """读取副本，避免依赖测试替身的共享可变对象。"""
        self.reads[key] += 1
        return deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """记录一次写入。"""
        self.writes[key] += 1
        self.data[key] = deepcopy(value)


def message(profile=PROFILE, message_id="reply-1"):
    """构造一条合法的已完成回复。"""
    return ConversationMessage(
        message_id=message_id, profile_id=profile, thread_id="thread-1",
        role="assistant", content="读取范围内的回复", status="completed", created_at=NOW,
        reply_to="request-1",
    )


@pytest.mark.parametrize("kind", ["message", "command"])
@pytest.mark.parametrize("strict", [False, True])
def test_conversation_rejects_foreign_profile_before_appending(kind, strict):
    """错误画像记录不进入普通结果，严格读取仍拒绝且保留原存储。"""
    plugin = MemoryPlugin()
    repository = plugin._repository
    local = message() if kind == "message" else ConversationCommand(
        command_id="command-1", profile_id=PROFILE, thread_id="thread-1",
        source_message_id="source-1", kind="profile_tag", title="添加标签",
        preview="添加悬疑标签", payload={"kind": "positive", "action": "add", "tag": "悬疑"},
        requested_by_mp_user_id="actor", created_at=NOW,
    )
    foreign = replace(local, profile_id="emby:other:user-2")
    key = repository._learning_key("conversation_messages", PROFILE)
    raw = [foreign.to_dict(), local.to_dict()]
    plugin.data[key] = deepcopy(raw)
    if strict:
        with pytest.raises(ValueError, match="conversation record is corrupt"):
            repository.load_conversation_records(PROFILE, strict=True)
    else:
        messages, commands = repository.load_conversation_records(PROFILE)
        assert messages + commands == [local]
    assert plugin.data[key] == raw


@pytest.mark.parametrize("mark_read", [False, True])
def test_conversation_response_shares_content_and_status_reads(mark_read):
    """对话响应只读一次线程/消息，已读标记仍按操作者处理。"""
    plugin = MemoryPlugin()
    repository = plugin._repository
    thread = ConversationThread(
        thread_id="thread-1", profile_id=PROFILE, created_by_mp_user_id="actor",
        created_at=NOW, updated_at=NOW,
    )
    plugin.data[repository._learning_key("conversation", PROFILE)] = thread.to_dict()
    plugin.data[repository._learning_key("conversation_messages", PROFILE)] = [message().to_dict()]
    repository.save_conversation_read_marker(PROFILE, "actor", "")
    plugin._conversation = ConversationService(repository, object())
    plugin.reads.clear()
    result = AgentRankApiController(plugin).conversation(PROFILE, "actor", mark_read)["data"]
    assert len(result["messages"]) == 1
    assert result["status"]["latest_assistant_message_id"] == "reply-1"
    assert result["status"]["unread_count"] == (0 if mark_read else 1)
    for prefix in ("conversation", "conversation_messages"):
        assert plugin.reads[repository._learning_key(prefix, PROFILE)] == 1
    assert repository.load_conversation_read_marker(PROFILE, "actor") == ("reply-1" if mark_read else "")


def test_missing_thread_keeps_empty_snapshot_and_existing_status_semantics():
    """无主线程时不展示孤立消息，状态查询的首次标记行为仍保留。"""
    plugin = MemoryPlugin()
    repository = plugin._repository
    plugin.data[repository._learning_key("conversation_messages", PROFILE)] = [message().to_dict()]
    service = ConversationService(repository, object())
    result = service.snapshot(PROFILE, actor_id="actor")
    assert result["thread"] is None and result["messages"] == []
    assert result["status"]["latest_assistant_message_id"] == "reply-1"
    assert result["status"]["unread_count"] == 0
    assert plugin.reads[repository._learning_key("conversation_messages", PROFILE)] == 1


@pytest.mark.parametrize("missing", [False, True])
def test_pending_titles_share_one_snapshot_only_within_the_request(monkeypatch, missing):
    """同轮问题只加载一次快照，缺失也复用；下一请求重新取最新标题。"""
    plugin = MemoryPlugin()
    repository = plugin._repository
    for index in range(2):
        event = repository.append_feedback_event(FeedbackEvent(
            profile_id=PROFILE, kind="like", candidate_id=f"tmdb:{index}", run_id="run-1",
            analysis_id="analysis-1", comment="", created_by_mp_user_id="actor",
            idempotency_key=f"event-{index}",
        )).event
        repository.append_pending_question(PendingQuestion(
            question_id=f"question-{index}", profile_id=PROFILE, event_id=event.event_id,
            event_sequence=event.sequence, candidate_id=event.candidate_id,
            understanding_record_id=f"understanding-{index}", question="更喜欢哪一点？",
            options=(PendingQuestionOption("pace", "节奏"), PendingQuestionOption("story", "剧情")),
            allow_custom_answer=True, uncertainties=("需确认偏好",),
            evidence_refs=(f"event:{event.event_id}",), expected_memory_revision=0,
            created_at=NOW, expires_at="2030-01-01T00:00:00+00:00",
        ))
    calls = []
    titles = [] if missing else [SimpleNamespace(candidate_id=f"tmdb:{i}", title=f"作品{i}") for i in range(2)]

    def load_snapshot(run_id, profile_id):
        """只替换与本次改动相关的候选快照读取。"""
        calls.append((profile_id, run_id))
        return titles

    monkeypatch.setattr(repository, "load_candidate_snapshot", load_snapshot)
    center = PendingCenterService(
        repository, feedback_response=SimpleNamespace(expire_due=lambda _: None),
        memory_projection=None, conversation=None,
    )
    first = center.list_pending(PROFILE)
    assert len(first["items"]) == 2 and calls == [(PROFILE, "run-1")]
    if not missing:
        assert {item["title"] for item in first["items"]} == {"关于《作品0》的一次确认", "关于《作品1》的一次确认"}
    titles[:] = [SimpleNamespace(candidate_id=f"tmdb:{i}", title=f"新版{i}") for i in range(2)]
    second = center.list_pending(PROFILE)
    assert len(calls) == 2
    assert {item["title"] for item in second["items"]} == {"关于《新版0》的一次确认", "关于《新版1》的一次确认"}


def test_health_endpoint_calculates_without_persisting():
    """独立健康查询保留原摘要，业务保存入口仍可单独调用。"""
    plugin = MemoryPlugin()
    key = plugin._repository._learning_key("learning_health", PROFILE)
    plugin.data[key] = {"previous": True}
    result = AgentRankApiController(plugin).learning_health(PROFILE)["data"]
    assert result["profile_id"] == PROFILE
    assert plugin.data[key] == {"previous": True} and plugin.writes[key] == 0
