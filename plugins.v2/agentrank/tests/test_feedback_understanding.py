"""反馈理解 Agent 的纯忽略、显式评论、敏感边界与幂等测试。"""

import asyncio
import copy
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_feedback_understanding_test"
PROFILE_ID = "emby:home:user-1"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
snapshot_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate_snapshot")
feedback_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback")
memory_module = importlib.import_module(f"{PACKAGE_NAME}.model.memory")
queue_model_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback_queue")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
queue_service_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.feedback_queue"
)
service_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.feedback_understanding"
)
runtime_module = importlib.import_module(f"{PACKAGE_NAME}.service.runtime")

Candidate = candidate_module.Candidate
CandidateSnapshot = snapshot_module.CandidateSnapshot
FeedbackEvent = feedback_module.FeedbackEvent
PreferenceMemoryItem = memory_module.PreferenceMemoryItem
FeedbackQueueJob = queue_model_module.FeedbackQueueJob
AgentRankRepository = repository_module.AgentRankRepository
FeedbackQueueService = queue_service_module.FeedbackQueueService
FeedbackUnderstandingError = service_module.FeedbackUnderstandingError
FeedbackUnderstandingService = service_module.FeedbackUnderstandingService
AgentRankRuntime = runtime_module.AgentRankRuntime


class FakePlugin:
    """提供独立副本的最小插件数据接口。"""

    def __init__(self):
        self.data = {}

    def get_data(self, key=None):
        """读取数据独立副本。"""
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """写入数据独立副本。"""
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除数据。"""
        self.data.pop(key, None)


class FakeResult(str):
    """携带安全模型来源的字符串结果。"""

    def __new__(cls, value, provenance=None):
        """创建测试用模型结果。"""
        result = super().__new__(cls, value)
        result.provenance = dict(provenance or {})
        return result


class FakeAgentAdapter:
    """返回预设 JSON 并记录反馈理解调用。"""

    def __init__(self, output):
        self.output = output
        self.calls = []

    async def run_feedback(self, prompt, trusted_context):
        """记录最小提示上下文并返回预设结果。"""
        self.calls.append((prompt, trusted_context))
        return FakeResult(
            json.dumps(self.output, ensure_ascii=False),
            {
                "provider": "家庭配额",
                "model": "gpt-feedback",
                "source": "agent_tokens",
                "model_call_count": 1,
                "base_url": "https://secret.invalid/v1",
            },
        )


def _event(kind="like", *, comment="", key="event-key", index=1):
    """构造测试反馈事件。"""
    return FeedbackEvent(
        profile_id=PROFILE_ID,
        kind=kind,
        candidate_id="tmdb:tv:101",
        run_id=f"run-{index}",
        analysis_id=f"analysis-{index}",
        comment=comment,
        idempotency_key=key,
    )


def _repository_with_event(event):
    """保存事件、候选快照并返回仓储与持久化事件。"""
    repository = AgentRankRepository(FakePlugin())
    stored = repository.append_feedback_event(event).event
    repository.save_candidate_snapshot(
        CandidateSnapshot.create(
            profile_id=PROFILE_ID,
            run_id=stored.run_id,
            profile_version={"run_id": stored.run_id, "schema_version": 6},
            retrieval_plan={"media_types": ["tv"]},
            candidates=[
                Candidate(
                    candidate_id="tmdb:tv:101",
                    title="候选作品",
                    media_type="tv",
                    overview="一部节奏鲜明的悬疑剧",
                    genres=["悬疑"],
                    regions=["中国"],
                    actors=["演员甲"],
                    directors=["导演乙"],
                )
            ],
            generated_at="2026-07-28T00:00:00+00:00",
        )
    )
    return repository, stored


def _job(event):
    """从持久化事件构造队列任务引用。"""
    return FeedbackQueueJob.from_event(event)


def test_pure_ignore_is_deterministic_exclusion_only_without_llm_or_memory_write():
    """无评论忽略不调用 Agent，不生成信号，也不改变确认记忆。"""
    repository, event = _repository_with_event(
        _event(kind="ignore", key="ignore-1")
    )
    adapter = FakeAgentAdapter(
        {
            "outcome": "understood",
            "restatement": "应该讨厌悬疑",
            "signals": [],
            "uncertainties": [],
        }
    )
    before = repository.load_preference_memory(PROFILE_ID)
    service = FeedbackUnderstandingService(repository, adapter)

    record = asyncio.run(service.handle_job(_job(event)))

    assert record.outcome == "exclusion_only"
    assert record.signals == ()
    assert record.model_source == "deterministic"
    assert record.model_call_count == 0
    assert adapter.calls == []
    assert repository.load_preference_memory(PROFILE_ID) == before
    assert repository.load_feedback_understanding(PROFILE_ID, event.event_id) == record


def test_uncommented_like_calls_agent_but_forces_ambiguous_without_stable_signal():
    """无评论喜欢仍异步理解，但模型不能凭单一动作制造长期偏好。"""
    repository, event = _repository_with_event(_event(key="like-1"))
    adapter = FakeAgentAdapter(
        {
            "outcome": "understood",
            "restatement": "你喜欢悬疑",
            "signals": [
                {
                    "category": "genre",
                    "value": "悬疑",
                    "polarity": "positive",
                    "certainty": 1,
                    "evidence_refs": [
                        f"event:{event.event_id}",
                        "candidate:tmdb:tv:101",
                    ],
                }
            ],
            "uncertainties": [],
        }
    )

    record = asyncio.run(
        FeedbackUnderstandingService(repository, adapter).handle_job(_job(event))
    )

    assert len(adapter.calls) == 1
    assert record.outcome == "ambiguous"
    assert record.signals == ()
    assert record.uncertainties


def test_explicit_comment_produces_pending_signal_and_deterministic_conflict():
    """明确评论可以形成待确认信号，且与旧记忆冲突会被结构化记录。"""
    repository, event = _repository_with_event(
        _event(
            kind="dislike",
            comment="我不喜欢这部剧的慢节奏",
            key="dislike-comment-1",
        )
    )
    repository.project_preference_memory(
        PROFILE_ID,
        [
            PreferenceMemoryItem(
                item_id="memory-pacing",
                category="pacing",
                value="慢节奏",
                polarity="positive",
                strength=0.8,
                certainty=0.9,
                evidence_refs=("feedback:1",),
                source_event_sequence=1,
                created_at="2026-07-28T00:00:00+00:00",
            )
        ],
        expected_revision=0,
        source_event_sequence=1,
    )
    adapter = FakeAgentAdapter(
        {
            "outcome": "understood",
            "restatement": "你不喜欢慢节奏",
            "signals": [
                {
                    "category": "pacing",
                    "value": "慢节奏",
                    "polarity": "negative",
                    "certainty": 0.8,
                    "evidence_refs": [
                        f"event:{event.event_id}",
                        "candidate:tmdb:tv:101",
                    ],
                }
            ],
            "uncertainties": [],
        }
    )

    record = asyncio.run(
        FeedbackUnderstandingService(repository, adapter).handle_job(_job(event))
    )

    assert record.outcome == "understood"
    assert record.signals[0].category == "pacing"
    assert record.conflicts[0]["memory_item_id"] == "memory-pacing"
    assert record.memory_revision == 1
    serialized = json.dumps(record.to_dict(), ensure_ascii=False)
    for forbidden in ("secret.invalid", "base_url", "思维链", "raw_output"):
        assert forbidden not in serialized


def test_sensitive_psychology_output_is_reduced_to_safe_ambiguous_result():
    """模型输出敏感心理推断时只保留安全的不确定结果。"""
    repository, event = _repository_with_event(
        _event(comment="我不喜欢这部作品", key="sensitive-1")
    )
    adapter = FakeAgentAdapter(
        {
            "outcome": "understood",
            "restatement": "你因为焦虑和孤独而不喜欢",
            "signals": [
                {
                    "category": "other",
                    "value": "焦虑",
                    "polarity": "negative",
                    "certainty": 1,
                    "evidence_refs": [f"event:{event.event_id}"],
                }
            ],
            "uncertainties": [],
        }
    )

    record = asyncio.run(
        FeedbackUnderstandingService(repository, adapter).handle_job(_job(event))
    )

    assert record.outcome == "ambiguous"
    assert record.signals == ()
    assert "焦虑" not in json.dumps(record.to_dict(), ensure_ascii=False)


def test_duplicate_consumption_returns_existing_record_without_second_agent_call():
    """重复消费同一事件只保留第一条理解记录。"""
    repository, event = _repository_with_event(
        _event(comment="喜欢节奏", key="duplicate-1")
    )
    output = {
        "outcome": "understood",
        "restatement": "你喜欢节奏",
        "signals": [
            {
                "category": "pacing",
                "value": "快节奏",
                "polarity": "positive",
                "certainty": 0.7,
                "evidence_refs": [f"event:{event.event_id}"],
            }
        ],
        "uncertainties": [],
    }
    adapter = FakeAgentAdapter(output)
    service = FeedbackUnderstandingService(repository, adapter)

    first = asyncio.run(service.handle_job(_job(event)))
    second = asyncio.run(service.handle_job(_job(event)))

    assert first == second
    assert len(adapter.calls) == 1
    assert len(repository.load_feedback_understandings(PROFILE_ID)) == 1


def test_parser_rejects_untrusted_evidence_reference_and_extra_root_key():
    """非法引用和额外根字段不能进入理解记录。"""
    repository, event = _repository_with_event(
        _event(comment="喜欢", key="invalid-output-1")
    )
    service = FeedbackUnderstandingService(repository, FakeAgentAdapter({}))
    parser = service._parser

    with pytest.raises(FeedbackUnderstandingError):
        parser.parse(
            json.dumps(
                {
                    "outcome": "understood",
                    "restatement": "喜欢",
                    "signals": [
                        {
                            "category": "genre",
                            "value": "悬疑",
                            "polarity": "positive",
                            "certainty": 0.8,
                            "evidence_refs": ["event:other"],
                        }
                    ],
                    "uncertainties": [],
                    "chain_of_thought": "must not persist",
                },
                ensure_ascii=False,
            ),
            event=event,
            allowed_evidence_refs=[f"event:{event.event_id}"],
        )


def test_runtime_injects_feedback_understanding_handler_into_queue():
    """运行时把受限理解服务的 handle_job 绑定为队列处理器。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    plugin._repository = repository
    adapter = FakeAgentAdapter(
        {
            "outcome": "ambiguous",
            "restatement": "仍需确认具体原因",
            "signals": [],
            "uncertainties": ["需要补充具体内容偏好"],
        }
    )
    understanding = FeedbackUnderstandingService(repository, adapter)
    queue = FeedbackQueueService(repository, profile_ids=[PROFILE_ID])

    runtime = AgentRankRuntime(
        plugin,
        {},
        orchestrator=object(),
        feedback_queue=queue,
        feedback_understanding_service=understanding,
    )

    assert runtime.feedback_understanding_service is understanding
    assert queue._handler.__self__ is understanding
    assert queue._handler.__func__ is understanding.handle_job.__func__
    assert plugin._feedback_understanding is understanding
