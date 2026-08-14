"""反馈理解 Agent 的纯忽略、显式评论、敏感边界与幂等测试。"""

import asyncio
import copy
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

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
response_service_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.feedback_response"
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
FeedbackResponseService = response_service_module.FeedbackResponseService
FeedbackUnderstandingError = service_module.FeedbackUnderstandingError
FeedbackUnderstandingBudgetError = service_module.FeedbackUnderstandingBudgetError
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
        output = (
            self.output[min(len(self.calls) - 1, len(self.output) - 1)]
            if isinstance(self.output, list)
            else self.output
        )
        return FakeResult(
            json.dumps(output, ensure_ascii=False),
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


def test_feedback_agent_timeout_ends_as_terminal_retryable_budget_failure():
    """反馈 Agent 超过共享总预算后终止，不让队列再开启完整重试周期。"""
    class SlowAgent:
        async def run_feedback(self, _prompt, _trusted_context):
            await asyncio.sleep(2)
            return "{}"

    repository, event = _repository_with_event(_event(key="timeout-like"))
    service = FeedbackUnderstandingService(
        repository,
        SlowAgent(),
        total_timeout_seconds=1,
    )

    with pytest.raises(FeedbackUnderstandingBudgetError) as caught:
        asyncio.run(service.handle_job(_job(event)))
    assert caught.value.terminal_retryable is True
    assert repository.load_feedback_understanding(PROFILE_ID, event.event_id) is None


def test_playback_calibration_without_run_id_reaches_feedback_agent():
    """播放校准回答没有榜单 run_id 时仍可完成理解并持久化记录。"""
    repository = AgentRankRepository(FakePlugin())
    event = repository.append_feedback_event(
        FeedbackEvent(
            profile_id=PROFILE_ID,
            kind="playback_calibration",
            candidate_id="profile:playback",
            comment="都可以",
            idempotency_key="playback-calibration-answer",
            supersedes="initial-calibration-event",
        )
    ).event
    adapter = FakeAgentAdapter(
        {
            "outcome": "ambiguous",
            "restatement": "熟悉体验和新鲜变化都可以",
            "signals": [],
            "uncertainties": ["没有固定探索倾向"],
            "clarification": {
                "question": "看过《候选甲》和《候选乙》后，你更希望下一轮推荐优先保留哪种体验？",
                "options": ["悬疑感更强", "人物关系更细", "换一种完全不同的类型"],
                "allow_custom_answer": True,
                "preference_dimension": "playback_next_direction",
                "exploration_level": 1,
                "confidence_gap": 0.8,
            },
        }
    )

    record = asyncio.run(
        FeedbackUnderstandingService(repository, adapter).handle_job(_job(event))
    )

    assert len(adapter.calls) == 1
    assert record.action == "playback_calibration"
    assert record.outcome == "ambiguous"
    assert record.candidate_id == "profile:playback"
    assert repository.load_feedback_understanding(PROFILE_ID, event.event_id) == record


def test_pending_interview_advances_one_agent_question_at_a_time_and_stops():
    """待办问询按回答逐轮推进，完成后不再调用 Agent 或写入记忆。"""
    repository = AgentRankRepository(FakePlugin())
    event = repository.append_feedback_event(
        FeedbackEvent(
            profile_id=PROFILE_ID,
            kind="playback_calibration",
            candidate_id="profile:playback",
            analysis_id="pending-interview:session123:2",
            comment=(
                "用户明确启动待办问询；近期播放有《命运石之门》和"
                "《来自新世界》，回答只用于本轮测试。"
            ),
            created_by_mp_user_id="7",
            idempotency_key="pending-interview-start",
        )
    ).event
    adapter = FakeAgentAdapter(
        [
            {
                "outcome": "ambiguous",
                "restatement": "先确认下一轮更想延续的体验",
                "signals": [],
                "uncertainties": ["两部作品的吸引点不同"],
                "clarification": {
                    "question": "第1/2题：这两部作品里，你更想延续哪种体验？",
                    "options": ["时间谜题", "陌生世界", "两者都不要"],
                    "allow_custom_answer": True,
                    "preference_dimension": "agent-draft-one",
                    "exploration_level": 1,
                    "confidence_gap": 0.7,
                },
            },
            {
                "outcome": "ambiguous",
                "restatement": "第一题选择了时间谜题，再确认叙事节奏",
                "signals": [],
                "uncertainties": ["尚不清楚慢热铺垫的接受度"],
                "clarification": {
                    "question": "第2/2题：时间谜题类作品，你能接受多长的慢热铺垫？",
                    "options": ["尽快入题", "几集铺垫可以", "节奏不重要"],
                    "allow_custom_answer": True,
                    "preference_dimension": "agent-draft-two",
                    "exploration_level": 2,
                    "confidence_gap": 0.6,
                },
            },
        ]
    )
    service = FeedbackUnderstandingService(repository, adapter)
    response = FeedbackResponseService(repository)
    before = repository.load_preference_memory(PROFILE_ID)

    first_record = asyncio.run(service.handle_job(_job(event)))
    first = repository.load_pending_questions(PROFILE_ID)[0]
    assert first_record.signals == ()
    assert first.question.startswith("第1/2题")
    assert first.preference_dimension == "pending_interview:session123:1:2"

    first_answer = response.answer_question(
        PROFILE_ID,
        first.question_id,
        idempotency_key="pending-interview-answer-1",
        actor_id="7",
        option_id=first.options[0].option_id,
    )
    asyncio.run(service.handle_job(_job(first_answer.event)))
    pending = [
        item
        for item in repository.load_pending_questions(PROFILE_ID)
        if item.status == "pending"
    ]
    assert len(pending) == 1
    second = pending[0]
    assert second.question.startswith("第2/2题")
    assert second.preference_dimension == "pending_interview:session123:2:2"

    second_answer = response.answer_question(
        PROFILE_ID,
        second.question_id,
        idempotency_key="pending-interview-answer-2",
        actor_id="7",
        option_id=second.options[1].option_id,
    )
    final_record = asyncio.run(service.handle_job(_job(second_answer.event)))

    assert final_record.outcome == "exclusion_only"
    assert final_record.model_source == "deterministic"
    assert "共 2 题" in final_record.restatement
    assert len(adapter.calls) == 2
    assert not any(
        item.status == "pending"
        for item in repository.load_pending_questions(PROFILE_ID)
    )
    assert repository.load_preference_memory(PROFILE_ID) == before


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
            "clarification": {
                "question": "你给《候选作品》点赞时，最想让我记住哪一点？",
                "options": ["悬疑推进", "演员表现", "画面氛围"],
                "allow_custom_answer": True,
                "preference_dimension": "candidate_like_reason",
                "exploration_level": 1,
                "confidence_gap": 0.8,
            },
        }
    )

    record = asyncio.run(
        FeedbackUnderstandingService(repository, adapter).handle_job(_job(event))
    )

    assert len(adapter.calls) == 1
    assert record.outcome == "ambiguous"
    assert record.signals == ()
    assert record.uncertainties


def test_missing_clarification_gets_one_agent_repair_without_template_fallback():
    """Agent 漏交问询时只修复一次，并逐字采用修复后的动态问题。"""
    repository, event = _repository_with_event(_event(key="repair-question"))
    adapter = FakeAgentAdapter(
        [
            {
                "outcome": "ambiguous",
                "restatement": "点赞原因仍不明确",
                "signals": [],
                "uncertainties": ["需要确认具体原因"],
            },
            {
                "outcome": "ambiguous",
                "restatement": "点赞原因仍不明确",
                "signals": [],
                "uncertainties": ["需要确认具体原因"],
                "clarification": {
                    "question": "《候选作品》的悬疑设定里，哪一点促使你点赞？",
                    "options": ["线索埋得巧", "反转有说服力", "氛围压迫感强"],
                    "allow_custom_answer": True,
                    "preference_dimension": "candidate_mystery_reason",
                    "exploration_level": 2,
                    "confidence_gap": 0.7,
                },
            },
        ]
    )

    record = asyncio.run(
        FeedbackUnderstandingService(repository, adapter).handle_job(_job(event))
    )
    question = repository.load_pending_questions(PROFILE_ID)[0]

    assert len(adapter.calls) == 2
    assert "AGENTRANK_CLARIFICATION_REPAIR" in adapter.calls[1][0]
    assert record.model_call_count == 2
    assert question.question == "《候选作品》的悬疑设定里，哪一点促使你点赞？"


def test_invalid_clarification_after_repair_creates_no_fixed_fallback_question():
    """连续两次缺少动态问询时终止处理，不得落回宿主固定题库。"""
    repository, event = _repository_with_event(_event(key="repair-still-invalid"))
    invalid = {
        "outcome": "ambiguous",
        "restatement": "点赞原因仍不明确",
        "signals": [],
        "uncertainties": ["需要确认具体原因"],
    }
    adapter = FakeAgentAdapter([invalid, invalid])

    with pytest.raises(FeedbackUnderstandingError, match="一次修复后仍不符合协议"):
        asyncio.run(
            FeedbackUnderstandingService(repository, adapter).handle_job(_job(event))
        )

    assert len(adapter.calls) == 2
    assert repository.load_feedback_understanding(PROFILE_ID, event.event_id) is None
    assert repository.load_pending_questions(PROFILE_ID) == []


def test_agent_generated_clarification_is_persisted_instead_of_fixed_question_template():
    """歧义反馈的问句和选项来自 Agent 草稿并保持幂等。"""
    repository, event = _repository_with_event(_event(key="agent-question"))
    adapter = FakeAgentAdapter(
        {
            "outcome": "ambiguous",
            "restatement": "喜欢这部作品，但还不能确定最关键的偏好点",
            "signals": [],
            "uncertainties": ["需要区分节奏与人物关系"],
            "clarification": {
                "question": "这部作品让你继续看下去时，最关键的是哪一点？",
                "options": ["双线悬念", "人物关系", "两者都重要"],
                "allow_custom_answer": True,
                "preference_dimension": "candidate_reason",
                "exploration_level": 1,
                "confidence_gap": 0.7,
            },
        }
    )

    record = asyncio.run(
        FeedbackUnderstandingService(repository, adapter).handle_job(
            _job(event)
        )
    )
    questions = repository.load_pending_questions(PROFILE_ID)

    assert record.clarification_question.startswith("这部作品让你")
    assert record.clarification_options == ("双线悬念", "人物关系", "两者都重要")
    assert len(questions) == 1
    assert questions[0].question.endswith("最关键的是哪一点？")
    assert [item.label for item in questions[0].options] == [
        "双线悬念",
        "人物关系",
        "两者都重要",
    ]


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
        conversation_service=SimpleNamespace(),
    )

    assert runtime.feedback_understanding_service is understanding
    assert queue._handler.__self__ is understanding
    assert queue._handler.__func__ is understanding.handle_job.__func__
    assert plugin._feedback_understanding is understanding
