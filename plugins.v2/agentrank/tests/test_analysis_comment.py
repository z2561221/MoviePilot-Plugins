"""逐条 Agent 分析评论、修订谱系、并发与回滚测试。"""

import asyncio
import copy
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_analysis_comment_test"
PROFILE_ID = "emby:home:user-1"
OTHER_PROFILE_ID = "emby:home:user-2"
RUN_ID = "run-analysis-comment"
CANDIDATE_ID = "tmdb:tv:101"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

analysis_module = importlib.import_module(f"{PACKAGE_NAME}.model.analysis")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
snapshot_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate_snapshot")
queue_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback_queue")
support_module = importlib.import_module(f"{PACKAGE_NAME}.model.support")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
comment_module = importlib.import_module(f"{PACKAGE_NAME}.service.analysis_comment")
lifecycle_module = importlib.import_module(f"{PACKAGE_NAME}.service.data_lifecycle")
understanding_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.feedback_understanding"
)

AnalysisEvidence = analysis_module.AnalysisEvidence
RecommendationAnalysis = analysis_module.RecommendationAnalysis
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
Candidate = candidate_module.Candidate
CandidateSnapshot = snapshot_module.CandidateSnapshot
FeedbackQueueJob = queue_module.FeedbackQueueJob
SupportContribution = support_module.SupportContribution
SupportScore = support_module.SupportScore
AgentRankRepository = repository_module.AgentRankRepository
AnalysisCommentError = comment_module.AnalysisCommentError
AnalysisCommentService = comment_module.AnalysisCommentService
DataLifecycleService = lifecycle_module.DataLifecycleService
FeedbackUnderstandingService = understanding_module.FeedbackUnderstandingService
AnalysisCommentParser = understanding_module.AnalysisCommentParser
FeedbackUnderstandingError = understanding_module.FeedbackUnderstandingError


class FakePlugin:
    """提供深复制持久化和一次性写失败注入。"""

    def __init__(self):
        self.data = {}
        self.fail_key_once = ""

    def get_data(self, key=None):
        """返回独立数据副本。"""
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """保存独立副本，并可在指定键模拟一次失败。"""
        if self.fail_key_once and key == self.fail_key_once:
            self.fail_key_once = ""
            raise RuntimeError("injected write failure")
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除测试数据。"""
        self.data.pop(key, None)


class FakeResult(str):
    """携带脱敏模型溯源的字符串结果。"""

    def __new__(cls, value):
        """创建评论 Agent 测试结果。"""
        result = super().__new__(cls, value)
        result.provenance = {
            "provider": "家庭配额",
            "model": "critic-comment-model",
            "source": "agent_tokens",
            "model_call_count": 1,
            "base_url": "https://secret.invalid/v1",
            "authorization": "Bearer must-not-leak",
        }
        return result


class FakeCommentAgent:
    """按顺序返回评论理解 JSON 并记录只读上下文。"""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    async def run_feedback(self, prompt, trusted_context):
        """返回下一条预设输出。"""
        self.calls.append((prompt, trusted_context))
        output = self.outputs.pop(0)
        return FakeResult(json.dumps(output, ensure_ascii=False))


def _agent_output(reason="你偏好快节奏，但本作节奏舒缓。", restatement="你指出既有节奏判断相反"):
    """构造合法的分析评论修订输出。"""
    return {
        "outcome": "understood",
        "restatement": restatement,
        "revised_reason": reason,
        "uncertainties": [],
    }


def _support():
    """构造可精确重算的确定性支持度。"""
    contribution = SupportContribution(
        dimension="theme_weight",
        direction="positive",
        user_value="悬疑",
        candidate_value="悬疑",
        user_refs=("playback:one", "playback:two"),
        candidate_ref=f"candidate:{CANDIDATE_ID}:genres",
        weight_units=8000,
        certainty_units=10000,
        contribution_units=8000,
    )
    return SupportScore.from_contributions("policy-v1", [contribution])


def _seed(profile_id=PROFILE_ID):
    """保存候选、榜单和完整结构化分析。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    support = _support()
    evidence = [
        AnalysisEvidence.from_dict(item.to_dict())
        for item in support.contributions
    ]
    analysis = RecommendationAnalysis(
        analysis_id="analysis-original",
        profile_id=profile_id,
        candidate_id=CANDIDATE_ID,
        run_id=RUN_ID,
        selection_source="agent",
        summary="一场围绕旧案展开的悬疑追查。",
        reason="你偏好悬疑与快节奏，本作同样紧凑。",
        positive_evidence=evidence,
        counter_evidence=[],
        uncertainties=[],
        data_sources=["playback_history", "frozen_candidate"],
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
        profile_id=profile_id,
        username="Alice",
        run_id=RUN_ID,
        status="success",
        recommendations=[item],
    )
    repository.save_candidate_snapshot(
        CandidateSnapshot.create(
            profile_id=profile_id,
            run_id=RUN_ID,
            profile_version={"run_id": RUN_ID, "schema_version": 6},
            retrieval_plan={"media_types": ["tv"]},
            candidates=[
                Candidate(
                    candidate_id=CANDIDATE_ID,
                    title="候选作品",
                    media_type="tv",
                    overview="围绕旧案展开的悬疑追查，叙事节奏较舒缓。",
                    genres=["悬疑"],
                    regions=["中国"],
                )
            ],
            generated_at="2026-07-28T00:00:00+00:00",
        )
    )
    repository.save_board_with_recommendation_analyses(board, [analysis])
    return plugin, repository, analysis


def _submit(repository, key="comment-1", comment="这部剧并不紧凑，原判断有误"):
    """提交一条绑定当前分析的评论。"""
    return AnalysisCommentService(repository).submit(
        profile_id=PROFILE_ID,
        candidate_id=CANDIDATE_ID,
        analysis_id="analysis-original",
        comment=comment,
        idempotency_key=key,
        actor_id="7",
        expected_board_revision=1,
        expected_run_id=RUN_ID,
    )


def test_comment_submission_binds_current_analysis_and_is_strictly_idempotent():
    """评论必须绑定当前分析，同请求可重放但幂等键不能换载荷。"""
    _plugin, repository, _analysis = _seed()
    service = AnalysisCommentService(repository)

    first = _submit(repository)
    duplicate = _submit(repository)

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.event.event_id == first.event.event_id
    assert first.to_dict()["event"].get("comment") is None
    with pytest.raises(AnalysisCommentError) as caught:
        _submit(repository, comment="复用幂等键但更换评论")
    assert caught.value.code == "idempotency_conflict"
    with pytest.raises(AnalysisCommentError) as caught:
        service.submit(
            profile_id=PROFILE_ID,
            candidate_id=CANDIDATE_ID,
            analysis_id="analysis-forged",
            comment="伪造分析上下文",
            idempotency_key="forged-1",
            actor_id="7",
        )
    assert caught.value.code == "analysis_context_conflict"
    with pytest.raises(AnalysisCommentError) as caught:
        service.submit(
            profile_id=PROFILE_ID,
            candidate_id=CANDIDATE_ID,
            analysis_id="analysis-original",
            comment="缺少操作者",
            idempotency_key="actor-1",
            actor_id="",
        )
    assert caught.value.status_code == 403


def test_understood_comment_supersedes_analysis_without_changing_support_or_memory():
    """明确评论只修订解释，原分析留档且确定性证据与记忆不变。"""
    _plugin, repository, original = _seed()
    submitted = _submit(repository)
    before_memory = repository.load_preference_memory(PROFILE_ID)
    agent = FakeCommentAgent(_agent_output())

    record = asyncio.run(
        FeedbackUnderstandingService(repository, agent).handle_job(
            FeedbackQueueJob.from_event(submitted.event)
        )
    )

    board = repository.load_board(PROFILE_ID)
    analyses = {
        item.analysis_id: item
        for item in repository.load_recommendation_analyses(PROFILE_ID, RUN_ID)
    }
    revised = analyses[record.analysis_revision_id]
    assert analyses[original.analysis_id].status == "superseded"
    assert revised.status == "active"
    assert revised.supersedes == original.analysis_id
    assert revised.reason == "你偏好快节奏，但本作节奏舒缓。"
    assert revised.positive_evidence == original.positive_evidence
    assert revised.counter_evidence == original.counter_evidence
    assert revised.support_percentage == original.support_percentage
    assert revised.policy_version == original.policy_version
    assert revised.memory_revision == original.memory_revision
    assert board.recommendations[0].analysis_id == revised.analysis_id
    assert board.recommendations[0].reason == revised.reason
    assert board.revision == 2
    assert repository.load_preference_memory(PROFILE_ID) == before_memory
    assert agent.calls[0][1].analysis["analysis_id"] == original.analysis_id
    replayed = _submit(repository)
    assert replayed.created is False
    assert replayed.analysis_status == "revised"
    assert replayed.board_revision == 2
    serialized = json.dumps(record.to_dict(), ensure_ascii=False)
    for forbidden in ("secret.invalid", "authorization", "Bearer", "raw_output"):
        assert forbidden not in serialized


def test_ambiguous_comment_creates_question_without_revising_analysis():
    """含义不明的评论进入整体偏好问询，不静默修改分析或长期画像。"""
    _plugin, repository, original = _seed()
    submitted = _submit(repository, comment="这里不对")
    before_memory = repository.load_preference_memory(PROFILE_ID)
    agent = FakeCommentAgent(
        {
            "outcome": "ambiguous",
            "restatement": "你认为当前分析有误，但尚未指出具体位置",
            "revised_reason": "",
            "uncertainties": ["需要说明是作品事实还是偏好判断有误"],
        }
    )

    record = asyncio.run(
        FeedbackUnderstandingService(repository, agent).handle_job(
            FeedbackQueueJob.from_event(submitted.event)
        )
    )

    board = repository.load_board(PROFILE_ID)
    questions = repository.load_pending_questions(PROFILE_ID)
    assert record.outcome == "ambiguous"
    assert record.analysis_revision_id == ""
    assert board.recommendations[0].analysis_id == original.analysis_id
    assert board.revision == 1
    assert len(questions) == 1
    assert questions[0].event_id == submitted.event.event_id
    assert questions[0].question == "平时挑选影视内容时，你通常最先看重什么？"
    assert questions[0].preference_dimension == "selection_basis"
    assert questions[0].exploration_level == 0
    assert repository.load_preference_memory(PROFILE_ID) == before_memory


def test_comment_parser_rejects_hidden_reasoning_and_invalid_short_copy():
    """评论修订拒绝额外思维链字段和不完整的三十字文案。"""
    _plugin, repository, original = _seed()
    event = _submit(repository, key="comment-invalid-output").event
    parser = AnalysisCommentParser()
    analysis = original.to_dict()

    with pytest.raises(FeedbackUnderstandingError):
        parser.parse(
            json.dumps(
                {
                    **_agent_output(),
                    "chain_of_thought": "must-not-persist",
                },
                ensure_ascii=False,
            ),
            event=event,
            analysis=analysis,
        )
    with pytest.raises(FeedbackUnderstandingError):
        parser.parse(
            json.dumps(
                _agent_output(reason="这项推荐依据仍然需要继续结合更多信息以及"),
                ensure_ascii=False,
            ),
            event=event,
            analysis=analysis,
        )


def test_sensitive_comment_output_becomes_ambiguous_without_revision():
    """敏感心理推断只能降级为待澄清，不能进入分析修订。"""
    _plugin, repository, original = _seed()
    submitted = _submit(repository, key="comment-sensitive-output")
    agent = FakeCommentAgent(
        _agent_output(
            reason="你的焦虑决定了你不适合这部作品。",
            restatement="你因为焦虑而否定原判断",
        )
    )

    record = asyncio.run(
        FeedbackUnderstandingService(repository, agent).handle_job(
            FeedbackQueueJob.from_event(submitted.event)
        )
    )

    assert record.outcome == "ambiguous"
    assert record.analysis_revision_id == ""
    assert repository.load_board(PROFILE_ID).recommendations[0].analysis_id == (
        original.analysis_id
    )
    assert "焦虑" not in json.dumps(record.to_dict(), ensure_ascii=False)


def test_concurrent_comments_form_one_monotonic_supersedes_chain():
    """同一分析处理前收到两条评论时按事件顺序串成修订链。"""
    _plugin, repository, original = _seed()
    first = _submit(repository, key="comment-concurrent-1", comment="节奏判断不对")
    second = _submit(repository, key="comment-concurrent-2", comment="题材判断也不准确")
    agent = FakeCommentAgent(
        _agent_output(
            reason="你偏好快节奏，但本作节奏舒缓。",
            restatement="你指出节奏判断相反",
        ),
        _agent_output(
            reason="本作仅含悬疑外壳，题材匹配有限。",
            restatement="你指出题材匹配也被高估",
        ),
    )
    service = FeedbackUnderstandingService(repository, agent)

    first_record = asyncio.run(service.handle_job(FeedbackQueueJob.from_event(first.event)))
    second_record = asyncio.run(service.handle_job(FeedbackQueueJob.from_event(second.event)))

    analyses = {
        item.analysis_id: item
        for item in repository.load_recommendation_analyses(PROFILE_ID, RUN_ID)
    }
    assert analyses[first_record.analysis_revision_id].supersedes == original.analysis_id
    assert analyses[first_record.analysis_revision_id].status == "superseded"
    assert (
        analyses[second_record.analysis_revision_id].supersedes
        == first_record.analysis_revision_id
    )
    assert repository.load_board(PROFILE_ID).recommendations[0].analysis_id == (
        second_record.analysis_revision_id
    )


def test_revision_write_failure_rolls_back_and_retry_reuses_understanding():
    """榜单写失败时分析同步回滚，队列重试复用理解并最终收敛。"""
    plugin, repository, original = _seed()
    submitted = _submit(repository)
    agent = FakeCommentAgent(_agent_output())
    service = FeedbackUnderstandingService(repository, agent)
    job = FeedbackQueueJob.from_event(submitted.event)
    plugin.fail_key_once = repository._profile_key("recommendation_board", PROFILE_ID)

    with pytest.raises(RuntimeError, match="injected write failure"):
        asyncio.run(service.handle_job(job))

    board = repository.load_board(PROFILE_ID)
    analyses = repository.load_recommendation_analyses(PROFILE_ID, RUN_ID)
    assert board.recommendations[0].analysis_id == original.analysis_id
    assert {item.analysis_id for item in analyses} == {original.analysis_id}
    assert analyses[0].status == "active"
    assert repository.load_feedback_understanding(
        PROFILE_ID, submitted.event.event_id
    ) is not None

    record = asyncio.run(service.handle_job(job))
    assert len(agent.calls) == 1
    assert repository.load_board(PROFILE_ID).recommendations[0].analysis_id == (
        record.analysis_revision_id
    )
    assert repository.load_feedback_understanding(
        PROFILE_ID, submitted.event.event_id
    ) == record


def test_full_analysis_retention_keeps_source_until_comment_revision_finishes():
    """分析列表满额时仍保留评论来源，避免队列因裁剪永久重试。"""
    plugin, repository, _original = _seed()
    analysis_key = repository._learning_key("agent_analysis", PROFILE_ID)
    plugin.data[analysis_key].extend(
        {"record_type": "bounded_noise", "index": index}
        for index in range(10)
    )
    submitted = _submit(repository, key="comment-full-retention")

    record = asyncio.run(
        FeedbackUnderstandingService(
            repository,
            FakeCommentAgent(_agent_output()),
            analysis_limit=2,
        ).handle_job(FeedbackQueueJob.from_event(submitted.event))
    )

    analyses = repository.load_recommendation_analyses(PROFILE_ID, RUN_ID)
    assert {item.analysis_id for item in analyses} == {
        "analysis-original",
        record.analysis_revision_id,
    }
    assert repository.load_board(PROFILE_ID).recommendations[0].analysis_id == (
        record.analysis_revision_id
    )
    assert repository.load_feedback_understanding(
        PROFILE_ID, submitted.event.event_id
    ) == record


def test_export_keeps_auditable_revision_but_redacts_comment_secrets():
    """脱敏导出保留修订谱系，不包含评论中的地址或模型密钥来源。"""
    _plugin, repository, _original = _seed()
    submitted = _submit(
        repository,
        comment="推荐依据不对，参考 https://private.invalid token=secret-value",
    )
    record = asyncio.run(
        FeedbackUnderstandingService(
            repository, FakeCommentAgent(_agent_output())
        ).handle_job(FeedbackQueueJob.from_event(submitted.event))
    )

    exported = DataLifecycleService(repository).export_profile(PROFILE_ID)
    serialized = json.dumps(exported, ensure_ascii=False)
    assert record.analysis_revision_id in serialized
    assert "analysis-original" in serialized
    assert "https://private.invalid" not in serialized
    assert "secret-value" not in serialized
    assert "secret.invalid" not in serialized
