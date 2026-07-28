"""AgentRank recommendation orchestration, refill, lock, and atomic save tests."""

import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_orchestration_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
profile_module = importlib.import_module(f"{PACKAGE_NAME}.model.profile")
preferences_module = importlib.import_module(f"{PACKAGE_NAME}.model.profile_preferences")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
feedback_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback")
memory_module = importlib.import_module(f"{PACKAGE_NAME}.model.memory")
playback_module = importlib.import_module(f"{PACKAGE_NAME}.model.playback")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
orchestrator_module = importlib.import_module(f"{PACKAGE_NAME}.service.recommendation")
archive_service_module = importlib.import_module(f"{PACKAGE_NAME}.service.archive")
keyword_module = importlib.import_module(f"{PACKAGE_NAME}.service.keyword_resolution")
analysis_builder_module = importlib.import_module(f"{PACKAGE_NAME}.service.analysis")

Candidate = candidate_module.Candidate
UserProfile = profile_module.UserProfile
ProfilePreferences = preferences_module.ProfilePreferences
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
FeedbackEvent = feedback_module.FeedbackEvent
PreferenceMemoryItem = memory_module.PreferenceMemoryItem
PlaybackSample = playback_module.PlaybackSample
PlaybackSnapshot = playback_module.PlaybackSnapshot
PlaybackCapability = playback_module.PlaybackCapability
AgentRankRepository = repository_module.AgentRankRepository
RecommendationOrchestrator = orchestrator_module.RecommendationOrchestrator
ArchiveService = archive_service_module.ArchiveService
ControlledRetrievalPlanResolver = keyword_module.ControlledRetrievalPlanResolver
RecommendationAnalysisBuilder = analysis_builder_module.RecommendationAnalysisBuilder

PROFILE_ID = "emby:home:user-1"
IDENTITY_CONFIG = {
    "emby_identities": [
        {
            "server_name": "home",
            "user_id": "user-1",
            "username": "Alice",
            "profile_id": PROFILE_ID,
            "schema_version": 1,
        }
    ],
    "default_profile_id": PROFILE_ID,
}


class FakePlugin:
    """In-memory plugindata store with one-shot board-save failure."""

    def __init__(self):
        self.data = {}
        self.fail_board_save = False

    def get_data(self, key=None):
        return self.data.get(key)

    def save_data(self, key=None, value=None):
        if self.fail_board_save and key == f"recommendation_board:profile:{PROFILE_ID.replace(':', '%3A')}":
            self.fail_board_save = False
            raise RuntimeError("board save failed")
        self.data[key] = value

    def del_data(self, key=None):
        self.data.pop(key, None)


class FakePlaybackService:
    """Return deterministic Playback Reporting evidence."""

    def probe(self, profile_id, config):
        """返回可用的 Playback Reporting 测试能力。"""
        return PlaybackCapability(profile_id, "ready", "mock probe")

    def collect(self, profile_id, config):
        return PlaybackSnapshot(
            profile_id=profile_id,
            username="Alice",
            source="playback_reporting",
            confidence="high",
            status="ready",
            samples=[
                PlaybackSample(
                    f"tmdb:movie:{index}",
                    f"Watched {index}",
                    "movie",
                    tmdb_id=str(index),
                    genres=["悬疑"],
                    completed=True,
                )
                for index in range(1, 6)
            ],
        )


class FakeCandidateService:
    """Return a deterministic frozen candidate result."""

    def __init__(self, count=12):
        self.candidates = [
            Candidate(
                candidate_id=f"tmdb:{index}",
                title=f"Title {index}",
                media_type="movie",
                genres=["悬疑"],
                regions=["中国"],
            )
            for index in range(1, count + 1)
        ]
        self.minimum_frozen_candidates = None

    def collect_and_freeze(
        self,
        profile_id,
        run_id,
        enabled_sources,
        candidate_limit,
        retrieval_plan=None,
        playback_samples=None,
        archived_candidate_ids=None,
        negative_keywords=None,
        profile_version=None,
        disliked_candidate_ids=None,
    ):
        self.retrieval_plan = retrieval_plan
        self.playback_samples = list(playback_samples or [])
        self.archived_candidate_ids = set(archived_candidate_ids or set())
        self.disliked_candidate_ids = set(disliked_candidate_ids or set())
        self.negative_keywords = list(negative_keywords or [])
        self.profile_version = dict(profile_version or {})
        values = dict(
            profile_id=profile_id,
            run_id=run_id,
            status="ready",
            candidates=self.candidates[:candidate_limit],
            source_errors={},
            rejected_sources=[],
            rejected_count=0,
            request_recipes=[],
        )
        if self.minimum_frozen_candidates is not None:
            values["minimum_frozen_candidates"] = self.minimum_frozen_candidates
        return SimpleNamespace(**values)

    def enrich_recommendation_sources(self, recommendations):
        """模拟候选服务为推荐补充来源链接的无副作用步骤。"""
        del recommendations


class FakeAgentAdapter:
    """分别返回画像与排序角色的排队输出或异常。"""

    def __init__(self, outputs, profile_outputs=None):
        self.ranking_outputs = list(outputs)
        self.profile_outputs = (
            None if profile_outputs is None else list(profile_outputs)
        )
        self.calls = []
        self.profile_calls = []
        self.ranking_calls = []

    @staticmethod
    def _result(output):
        """返回测试输出或抛出排队异常。"""
        if isinstance(output, Exception):
            raise output
        return output

    async def run_profile(self, prompt, trusted_context):
        """执行画像角色测试调用。"""
        self.calls.append(("profile", prompt, trusted_context))
        self.profile_calls.append((prompt, trusted_context))
        output = (
            self.profile_outputs.pop(0)
            if self.profile_outputs is not None
            else _profile_output(len(trusted_context.playback["samples"]))
        )
        return self._result(output)

    async def run_ranking(self, prompt, trusted_context):
        """执行排序角色测试调用。"""
        self.calls.append(("ranking", prompt, trusted_context))
        self.ranking_calls.append((prompt, trusted_context))
        return self._result(self.ranking_outputs.pop(0))

    async def run(self, prompt, trusted_context):
        """按受信上下文角色兼容分发测试调用。"""
        if trusted_context.agent_role == "profile":
            return await self.run_profile(prompt, trusted_context)
        return await self.run_ranking(prompt, trusted_context)


class ProvenanceText(str):
    """模拟字符串兼容且携带模型溯源的适配器结果。"""

    def __new__(cls, value, provenance):
        """创建带脱敏 provenance 的字符串结果。"""
        instance = super().__new__(cls, value)
        instance.provenance = dict(provenance)
        return instance


class RetryableAgentError(RuntimeError):
    """Represent a transient Agent completion without final text."""

    retryable = True


def _profile_output(playback_count=5, filters=None, ranking_tags=None):
    return json.dumps(
        {
            "profile": {
                "summary": "偏好高质量悬疑电影",
                "tags": ["悬疑"],
                "negative_tags": [],
                "playback_count": playback_count,
            },
            "filters": filters or {
                "media_types": ["movie"],
                "genre_ids": [80],
                "keyword_ids": [],
                "original_languages": ["zh"],
                "year_min": None,
                "year_max": None,
                "rating_min": 7.0,
                "vote_count_min": 100,
                "sort_by": "popularity.desc",
            },
            "ranking_tags": ranking_tags or ["高质量悬疑"],
        },
        ensure_ascii=False,
    )


def _agent_output(candidate_ids):
    return json.dumps(
        {
            "recommendations": [
                {
                    "candidate_id": candidate_id,
                    "reason": "偏爱悬疑电影，这部中国密室追凶更贴合。",
                    "summary": "悬疑迷局层层牵出尘封往事与真相",
                    "match_tags": ["悬疑", "中国"],
                    "positive_evidence": [
                        {
                            "dimension": "type",
                            "user_value": "movie",
                            "candidate_value": "movie",
                        },
                        {
                            "dimension": "theme",
                            "user_value": "悬疑",
                            "candidate_value": "悬疑",
                        },
                    ],
                    "counter_evidence": [],
                }
                for candidate_id in candidate_ids
            ],
        },
        ensure_ascii=False,
    )


def _agent_output_with_overrides(candidate_ids, overrides):
    """按候选 ID 覆盖模拟推荐字段，构造混合通过与丢弃输出。"""
    payload = json.loads(_agent_output(candidate_ids))
    for recommendation in payload["recommendations"]:
        recommendation.update(overrides.get(recommendation["candidate_id"], {}))
    return json.dumps(payload, ensure_ascii=False)


def _orchestrator(
    plugin,
    outputs,
    candidate_count=12,
    profile_outputs=None,
    retrieval_plan_resolver=None,
):
    repository = AgentRankRepository(plugin)
    return (
        RecommendationOrchestrator(
            repository=repository,
            candidate_service=FakeCandidateService(candidate_count),
            agent_adapter=FakeAgentAdapter(outputs, profile_outputs=profile_outputs),
            run_id_factory=lambda: "run-1",
            playback_service=FakePlaybackService(),
            retrieval_plan_resolver=retrieval_plan_resolver,
        ),
        repository,
    )


def _config():
    return {
        **IDENTITY_CONFIG,
        "candidate_pool_size": 50,
        "discovery_sources": {"douban": True},
        "weights": {"rating_weight": 0.7},
        "media_types": ["movie"],
        "confidence_threshold": 0.6,
        "exclude_keywords": [],
        "profile_cache_enabled": True,
        "rebuild_profile_each_run": False,
    }


def test_success_atomically_saves_profile_board_and_run_history():
    """A complete valid run replaces both current objects and records metrics."""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin, [_agent_output([f"tmdb:{index}" for index in range(1, 6)])]
    )
    config = _config()
    result = asyncio.run(orchestrator.run(PROFILE_ID, config))

    assert result.status == "success"
    assert result.profile_id == PROFILE_ID
    assert result.username == "Alice"
    assert orchestrator.agent_adapter.profile_calls[0][1].username == "Alice"
    assert orchestrator.agent_adapter.profile_calls[0][1].agent_role == "profile"
    assert orchestrator.agent_adapter.profile_calls[0][1].candidates == ()
    assert orchestrator.agent_adapter.ranking_calls[0][1].agent_role == "ranking"
    assert orchestrator.agent_adapter.ranking_calls[0][1].profile["run_id"] == (
        "run-1"
    )
    ranking_weights = orchestrator.agent_adapter.ranking_calls[0][1].weights
    assert ranking_weights["policy_version"].startswith("policy-v1-")
    assert len(ranking_weights["weights"]) == 10
    assert ranking_weights["base_weights"]["rating_weight"] == 0.7
    assert orchestrator._candidate_service.retrieval_plan.filters.genre_ids == (80,)
    assert [item.tmdb_id for item in orchestrator._candidate_service.playback_samples] == [
        "1",
        "2",
        "3",
        "4",
        "5",
    ]
    saved_board = repository.load_board(PROFILE_ID)
    assert len(saved_board.recommendations) == 5
    analyses = repository.load_recommendation_analyses(PROFILE_ID, "run-1")
    assert len(analyses) == 5
    assert {item.analysis_id for item in saved_board.recommendations} == {
        item.analysis_id for item in analyses
    }
    assert all(item.policy_version == ranking_weights["policy_version"] for item in analyses)
    assert all(item.memory_revision == 0 for item in analyses)
    assert repository.load_profile(PROFILE_ID).run_id == "run-1"
    assert repository.load_profile(PROFILE_ID).filters["genre_ids"] == [80]
    assert repository.load_profile(PROFILE_ID).ranking_tags == ["高质量悬疑"]
    history = repository.load_run_history(PROFILE_ID)
    assert history[0].status == "success"
    assert history[0].metrics["policy_version"] == ranking_weights["policy_version"]
    assert history[0].metrics["policy_memory_revision"] == 0
    assert repository.load_policy_snapshot(PROFILE_ID).policy_version == (
        ranking_weights["policy_version"]
    )
    assert history[0].metrics["final_count"] == 5
    assert history[0].metrics["agent_calls"] == 2
    assert history[0].metrics["profile_agent_calls"] == 1
    assert history[0].metrics["ranking_agent_calls"] == 1
    assert history[0].metrics["selection_source_counts"] == {
        "agent": 5,
        "safe_fallback": 0,
    }
    assert history[0].metrics["agent_selected_count"] == 5
    assert history[0].metrics["safe_fallback_selected_count"] == 0
    assert history[0].metrics["recommendation_analysis_count"] == 5
    assert "candidate_source_counts" in history[0].metrics
    assert "candidate_exclusion_counts" in history[0].metrics
    assert "source_errors" in history[0].metrics
    expected_stages = [
        "probe",
        "playback_snapshot",
        "policy",
        "profile",
        "candidate",
        "ranking",
        "save",
    ]
    assert history[0].metrics["stage_order"] == expected_stages
    assert set(history[0].metrics["stage_status"]) == set(expected_stages)
    assert set(history[0].metrics["stage_ms"]) == set(expected_stages)
    assert all(
        history[0].metrics["stage_ms"][stage] >= 0 for stage in expected_stages
    )
    assert history[0].metrics["playback_probe_status"] == "ready"


def test_run_history_aggregates_actual_agent_model_provenance():
    """画像和排序调用分别记录真实模型来源，主模型字段不再承载调用数。"""
    profile_output = ProvenanceText(
        _profile_output(5),
        {
            "provider_id": "provider-7",
            "selected_provider_name": "家庭配额",
            "provider": "openai",
            "model": "gpt-5.1",
            "source": "agent_tokens",
            "model_call_count": 2,
            "base_url": "must-not-persist",
        },
    )
    ranking_output = ProvenanceText(
        _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
        {
            "provider_id": "",
            "selected_provider_name": "",
            "provider": "openai",
            "model": "system-gpt",
            "source": "moviepilot_system",
            "model_call_count": 3,
            "api_key": "must-not-persist",
        },
    )
    orchestrator, repository = _orchestrator(
        FakePlugin(), [ranking_output], profile_outputs=[profile_output]
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    metrics = repository.load_run_history(PROFILE_ID)[0].metrics
    assert metrics["agent_model"] == "gpt-5.1 / system-gpt"
    assert metrics["agent_provider"] == "家庭配额 / openai"
    assert metrics["agent_model_source"] == "mixed"
    assert metrics["model_call_count"] == 5
    assert metrics["profile_model_call_count"] == 2
    assert metrics["ranking_model_call_count"] == 3
    assert [item["role"] for item in metrics["agent_provenance"]] == [
        "profile",
        "ranking",
    ]
    serialized = json.dumps(metrics["agent_provenance"], ensure_ascii=False)
    for forbidden in ("base_url", "api_key", "must-not-persist"):
        assert forbidden not in serialized


def test_main_ranking_uses_three_reserves_but_persists_only_top_five():
    """主排序八条先按确定性净分选前五，不能先截 Agent 前五。"""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            _agent_output_with_overrides(
                [f"tmdb:{index}" for index in range(1, 9)],
                {
                    "tmdb:8": {
                        "reason": "偏爱悬疑电影，这部法国密室追凶更贴合。",
                        "match_tags": ["悬疑", "法国"],
                    }
                },
            )
        ],
    )
    orchestrator._candidate_service.candidates[7].regions = ["法国"]
    repository.save_profile_preferences(
        ProfilePreferences(profile_id=PROFILE_ID, custom_tags=["法国"])
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    board = repository.load_board(PROFILE_ID)
    assert result.status == "success"
    assert result.agent_calls == 2
    assert [item.candidate_id for item in board.recommendations] == [
        "tmdb:8",
        "tmdb:1",
        "tmdb:2",
        "tmdb:3",
        "tmdb:4",
    ]
    assert len(orchestrator.agent_adapter.ranking_calls) == 1
    assert "最多 8 条" in orchestrator.agent_adapter.ranking_calls[0][0]
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["ranking_valid_count"] == 8
    assert history.metrics["ranking_reserve_count"] == 3
    assert history.metrics["refill_attempted"] is False
    assert history.metrics["selection_source_counts"] == {
        "agent": 5,
        "safe_fallback": 0,
    }


def test_fewer_than_twenty_frozen_candidates_skips_ranking_agent():
    """冻结候选低于默认 20 条时保留画像但不调用排序 Agent。"""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [_agent_output([f"tmdb:{index}" for index in range(1, 6)])],
        candidate_count=19,
    )
    orchestrator._candidate_service.minimum_frozen_candidates = 20

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "candidate_insufficient"
    assert len(orchestrator.agent_adapter.profile_calls) == 1
    assert orchestrator.agent_adapter.ranking_calls == []
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["candidate_count"] == 19
    assert history.metrics["minimum_frozen_candidates"] == 20


def test_candidate_stage_exception_preserves_previous_board_and_records_failure():
    """候选采集异常必须闭锁排序，并留下可审计阶段失败记录。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)

    class FailedCandidateService(FakeCandidateService):
        def collect_and_freeze(self, *args, **kwargs):
            """模拟候选采集阶段抛出不可恢复异常。"""
            raise RuntimeError("provider chain offline")

    agent = FakeAgentAdapter([_agent_output(["tmdb:1"])])
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=FailedCandidateService(),
        agent_adapter=agent,
        run_id_factory=lambda: "run-candidate-failed",
        playback_service=FakePlaybackService(),
    )
    repository.save_board(
        RecommendationBoard(
            profile_id=PROFILE_ID,
            username="Alice",
            run_id="old",
            status="success",
        )
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "candidate_failed"
    assert result.board.run_id == "old"
    assert agent.ranking_calls == []
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.errors == ["candidate: provider chain offline"]
    assert history.metrics["stage_order"] == [
        "probe",
        "playback_snapshot",
        "policy",
        "profile",
        "candidate",
    ]
    assert history.metrics["stage_status"]["candidate"] == "candidate_failed"


def test_ranking_context_prefers_persisted_snapshot_candidates():
    """候选结果与快照分叉时，排序 Agent 必须只读取持久化快照内容。"""
    class SnapshotCandidateService(FakeCandidateService):
        def collect_and_freeze(self, *args, **kwargs):
            result = super().collect_and_freeze(*args, **kwargs)
            persisted = Candidate(
                candidate_id="tmdb:movie:99",
                title="Persisted",
                media_type="movie",
            )
            result.snapshot = SimpleNamespace(
                candidates=[persisted],
                content_hash="snapshot-hash",
                generated_at="2026-07-21T00:00:00+00:00",
            )
            result.minimum_frozen_candidates = 1
            return result

    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    agent = FakeAgentAdapter([_agent_output(["tmdb:movie:99"])])
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=SnapshotCandidateService(),
        agent_adapter=agent,
        run_id_factory=lambda: "run-snapshot-context",
        playback_service=FakePlaybackService(),
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    visible_ids = [
        item["candidate_id"] for item in agent.ranking_calls[0][1].candidates
    ]
    assert visible_ids == ["tmdb:movie:99"]
    assert result.status == "recommendation_incomplete"
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["candidate_snapshot_hash"] == "snapshot-hash"


def test_same_playback_fingerprint_reuses_profile_when_candidates_change():
    """播放事实相同而候选池变化时只重新排序，不改写画像。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    candidates = FakeCandidateService(12)
    agent = FakeAgentAdapter(
        [
            _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
            _agent_output([f"tmdb:{index}" for index in range(20, 25)]),
        ]
    )
    run_ids = iter(["run-profile", "run-ranking-only"])
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=candidates,
        agent_adapter=agent,
        run_id_factory=lambda: next(run_ids),
        playback_service=FakePlaybackService(),
    )

    first = asyncio.run(orchestrator.run(PROFILE_ID, _config()))
    candidates.candidates = [
        Candidate(
            candidate_id=f"tmdb:{index}",
            title=f"Changed {index}",
            media_type="movie",
            genres=["悬疑"],
            regions=["中国"],
        )
        for index in range(20, 32)
    ]
    second = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    profile = repository.load_profile(PROFILE_ID)
    assert first.status == "success"
    assert second.status == "success"
    assert len(agent.profile_calls) == 1
    assert len(agent.ranking_calls) == 2
    assert profile.run_id == "run-profile"
    assert profile.playback_fingerprint
    assert repository.load_board(PROFILE_ID).run_id == "run-ranking-only"
    latest_metrics = repository.load_run_history(PROFILE_ID)[0].metrics
    assert latest_metrics["profile_agent_reused"] is True
    assert latest_metrics.get("profile_agent_calls", 0) == 0
    assert latest_metrics["profile_cache_status"] == "hit"
    assert latest_metrics["profile_cache_miss_reason"] == ""


def test_dislike_excludes_title_across_refresh_without_mutating_long_term_taste():
    """旧轮次点踩在新刷新中只排除作品，不写画像偏好或确认记忆。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    preferences = ProfilePreferences(
        profile_id=PROFILE_ID,
        username="Alice",
        custom_tags=["科幻"],
        custom_negative_tags=["真人秀"],
    )
    repository.save_profile_preferences(preferences)
    before_preferences = repository.load_profile_preferences(PROFILE_ID).to_dict()
    before_memory = repository.load_preference_memory(PROFILE_ID).to_dict()
    repository.append_feedback_event(
        FeedbackEvent(
            profile_id=PROFILE_ID,
            kind="dislike",
            candidate_id="tmdb:1",
            run_id="run-before-refresh",
            created_by_mp_user_id="mp-user-1",
            idempotency_key="dislike-before-refresh",
        )
    )
    candidates = FakeCandidateService(12)
    agent = FakeAgentAdapter(
        [
            _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
            _agent_output(["tmdb:6"]),
        ]
    )
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=candidates,
        agent_adapter=agent,
        run_id_factory=lambda: "run-after-refresh",
        playback_service=FakePlaybackService(),
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert candidates.disliked_candidate_ids == {"tmdb:1"}
    assert [item.candidate_id for item in result.board.recommendations] == [
        "tmdb:2",
        "tmdb:3",
        "tmdb:4",
        "tmdb:5",
        "tmdb:6",
    ]
    assert repository.load_archive(PROFILE_ID).entries == []
    assert repository.load_profile_preferences(PROFILE_ID).to_dict() == before_preferences
    assert repository.load_preference_memory(PROFILE_ID).to_dict() == before_memory
    assert repository.load_profile(PROFILE_ID).negative_tags == []
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["active_disliked_candidate_count"] == 1
    assert len(agent.ranking_calls) == 2


def test_only_profile_prompt_change_invalidates_profile_cache():
    """排序或文案变化复用画像，画像规则变化才按明确原因重建。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    agent = FakeAgentAdapter(
        [
            _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
            _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
            _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
        ]
    )
    run_ids = iter(["run-profile-a", "run-copy-change", "run-profile-b"])
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=FakeCandidateService(12),
        agent_adapter=agent,
        run_id_factory=lambda: next(run_ids),
        playback_service=FakePlaybackService(),
    )
    base_config = {
        **_config(),
        "profile_prompt": "画像规则甲",
        "ranking_prompt": "排序规则甲",
        "copy_prompt": "文案规则甲",
    }

    first = asyncio.run(orchestrator.run(PROFILE_ID, base_config))
    copy_changed = {
        **base_config,
        "ranking_prompt": "排序规则乙",
        "copy_prompt": "文案规则乙",
    }
    second = asyncio.run(orchestrator.run(PROFILE_ID, copy_changed))
    second_metrics = repository.load_run_history(PROFILE_ID)[0].metrics
    profile_changed = {**copy_changed, "profile_prompt": "画像规则乙"}
    third = asyncio.run(orchestrator.run(PROFILE_ID, profile_changed))
    third_metrics = repository.load_run_history(PROFILE_ID)[0].metrics

    assert [first.status, second.status, third.status] == ["success"] * 3
    assert len(agent.profile_calls) == 2
    assert second_metrics["profile_cache_status"] == "hit"
    assert second_metrics["profile_cache_miss_reason"] == ""
    assert third_metrics["profile_cache_status"] == "miss"
    assert third_metrics["profile_cache_miss_reason"] == "profile_prompt_changed"
    assert repository.load_profile(PROFILE_ID).profile_prompt_fingerprint


def test_legacy_profile_schema_is_rebuilt_even_when_playback_fingerprint_matches():
    """旧画像没有检索计划时不能因相同指纹跳过画像 Agent。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    playback = FakePlaybackService()
    snapshot = playback.collect(PROFILE_ID, _config())
    repository.save_profile(
        UserProfile(
            profile_id=PROFILE_ID,
            username="Alice",
            summary="old",
            playback_count=len(snapshot.samples),
            playback_fingerprint=snapshot.fingerprint(),
            schema_version=3,
            run_id="old",
        )
    )
    orchestrator, _ = _orchestrator(
        plugin,
        [_agent_output([f"tmdb:{index}" for index in range(1, 6)])],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert len(orchestrator.agent_adapter.profile_calls) == 1
    assert repository.load_profile(PROFILE_ID).schema_version == 6
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["profile_cache_miss_reason"] == "profile_schema_changed"


def test_preresolution_profile_is_rebuilt_even_when_playback_fingerprint_matches():
    """3.2 画像尚未经过受控解析时必须重建，不能直接复用。"""
    plugin = FakePlugin()
    playback = FakePlaybackService()
    snapshot = playback.collect(PROFILE_ID, _config())
    repository = AgentRankRepository(plugin)
    repository.save_profile(
        UserProfile(
            profile_id=PROFILE_ID,
            username="Alice",
            summary="old",
            playback_count=len(snapshot.samples),
            playback_fingerprint=snapshot.fingerprint(),
            schema_version=6,
            retrieval_resolution_version=0,
            run_id="old",
        )
    )
    orchestrator, _ = _orchestrator(
        plugin,
        [_agent_output([f"tmdb:{index}" for index in range(1, 6)])],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert len(orchestrator.agent_adapter.profile_calls) == 1
    assert repository.load_profile(PROFILE_ID).retrieval_resolution_version == 1
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["profile_cache_miss_reason"] == (
        "retrieval_resolution_changed"
    )


def test_controlled_resolution_is_persisted_and_exposed_to_ranking_context():
    """唯一关键词 ID 写入画像，排序上下文只看到解析后的计划。"""
    resolver = ControlledRetrievalPlanResolver(
        keyword_searcher=lambda term: [{"id": 321, "name": "cyberpunk"}]
    )
    profile_output = _profile_output(ranking_tags=["赛博朋克", "英文"])
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [_agent_output([f"tmdb:{index}" for index in range(1, 6)])],
        profile_outputs=[profile_output],
        retrieval_plan_resolver=resolver,
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    profile = repository.load_profile(PROFILE_ID)
    ranking_profile = orchestrator.agent_adapter.ranking_calls[0][1].profile
    metrics = repository.load_run_history(PROFILE_ID)[0].metrics
    assert result.status == "success"
    assert profile.filters["keyword_ids"] == [321]
    assert profile.filters["original_languages"] == ["zh", "en"]
    assert profile.ranking_tags == []
    assert ranking_profile["filters"]["keyword_ids"] == (321,)
    assert metrics["resolved_keyword_count"] == 1
    assert metrics["resolved_language_count"] == 1


def test_run_uses_three_configured_prompts_in_their_own_stages():
    """画像、排序和文案提示词只进入各自负责的 Agent 阶段。"""
    plugin = FakePlugin()
    orchestrator, _ = _orchestrator(
        plugin, [_agent_output([f"tmdb:{index}" for index in range(1, 6)])]
    )
    config = _config()
    config["profile_prompt"] = "画像只归纳稳定的科幻偏好"
    config["ranking_prompt"] = "排序优先冷门科幻"
    config["copy_prompt"] = "文案俏皮但克制"

    asyncio.run(orchestrator.run(PROFILE_ID, config))

    profile_prompt = orchestrator.agent_adapter.profile_calls[0][0]
    ranking_prompt = orchestrator.agent_adapter.ranking_calls[0][0]
    assert "画像只归纳稳定的科幻偏好" in profile_prompt
    assert "排序优先冷门科幻" not in profile_prompt
    assert "文案俏皮但克制" not in profile_prompt
    assert "排序优先冷门科幻" in ranking_prompt
    assert "文案俏皮但克制" in ranking_prompt
    assert "画像只归纳稳定的科幻偏好" not in ranking_prompt


def test_cached_profile_is_passed_as_incremental_context():
    """画像缓存开启且未要求重建时，旧画像会进入只读播放上下文。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin, [_agent_output([f"tmdb:{index}" for index in range(1, 6)])]
    )
    repository.save_profile(
        UserProfile(
            profile_id=PROFILE_ID,
            username="Alice",
            summary="old",
            tags=["悬疑"],
            run_id="old",
        )
    )
    repository.save_profile_preferences(
        ProfilePreferences(
            profile_id=PROFILE_ID,
            username="Alice",
            custom_tags=["冷门佳作"],
            custom_negative_tags=["过度煽情"],
        )
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    context = orchestrator.agent_adapter.profile_calls[0][1]
    assert context.previous_profile["summary"] == "old"
    assert context.previous_profile["tags"] == ("悬疑",)
    assert context.profile_preferences["custom_tags"] == ("冷门佳作",)
    assert context.profile_preferences["custom_negative_tags"] == ("过度煽情",)
    assert "禁止简单合并标签" in orchestrator.agent_adapter.profile_calls[0][0]
    assert "明确偏好" in orchestrator.agent_adapter.profile_calls[0][0]
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["profile_mode"] == "incremental"
    assert history.metrics["previous_profile_used"] is True
    assert history.metrics["custom_preference_count"] == 2
    for metric in ("playback_collect_ms", "candidate_collect_ms", "library_check_ms", "agent_ms", "save_ms"):
        assert history.metrics[metric] >= 0
    assert result.status == "success"


def test_preference_change_rebuilds_profile_and_scrubs_archived_agent_tags():
    """人工标签变化使缓存失效，归档标签不会写回画像或检索计划。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    candidates = FakeCandidateService()
    agent = FakeAgentAdapter(
        [
            _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
            _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
        ],
        profile_outputs=[
            _profile_output(),
            _profile_output(ranking_tags=["悬疑", "科幻"]),
        ],
    )
    run_ids = iter(("run-before-tags", "run-after-tags"))
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=candidates,
        agent_adapter=agent,
        run_id_factory=lambda: next(run_ids),
        playback_service=FakePlaybackService(),
    )

    first = asyncio.run(orchestrator.run(PROFILE_ID, _config()))
    preferences = ProfilePreferences(
        profile_id=PROFILE_ID,
        custom_tags=["科幻"],
        archived_tags=["悬疑"],
    )
    repository.save_profile_preferences(preferences)
    second = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    profile = repository.load_profile(PROFILE_ID)
    latest = repository.load_run_history(PROFILE_ID)[0]
    ranking_context = agent.ranking_calls[-1][1]
    assert first.status == "success"
    assert second.status == "success"
    assert len(agent.profile_calls) == 2
    assert latest.metrics["profile_cache_miss_reason"] == "preferences_changed"
    assert latest.metrics["custom_preference_count"] == 1
    assert latest.metrics["archived_preference_count"] == 1
    assert profile.tags == []
    assert profile.preferences_fingerprint == preferences.fingerprint()
    assert "悬疑" not in profile.ranking_tags
    assert ranking_context.profile["tags"] == ("科幻",)
    assert ranking_context.profile_preferences["archived_tags"] == ("悬疑",)


def test_incremental_profile_accepts_only_previously_resolved_keyword_ids():
    """增量画像可沿用插件已解析的关键词 ID，不把任意 ID 加入白名单。"""
    plugin = FakePlugin()
    keyword_filters = {
        "media_types": ["movie"],
        "genre_ids": [80],
        "keyword_ids": [304070],
        "original_languages": ["zh"],
        "year_min": None,
        "year_max": None,
        "rating_min": 7.0,
        "vote_count_min": 100,
        "sort_by": "popularity.desc",
    }
    orchestrator, repository = _orchestrator(
        plugin,
        [_agent_output([f"tmdb:{index}" for index in range(1, 6)])],
        profile_outputs=[_profile_output(filters=keyword_filters)],
    )
    repository.save_profile(
        UserProfile(
            profile_id=PROFILE_ID,
            username="Alice",
            summary="old",
            tags=["悬疑"],
            filters=keyword_filters,
            run_id="old",
        )
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert repository.load_profile(PROFILE_ID).filters["keyword_ids"] == [304070]


def test_playback_evidence_is_collected_and_passed_to_restricted_context():
    """播放画像只以规范化快照进入受信上下文，并记录数据源指标。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)

    class PlaybackService(FakePlaybackService):
        def collect(self, profile_id, config):
            return PlaybackSnapshot(
                profile_id=profile_id,
                username="Alice",
                source="playback_reporting",
                confidence="high",
                status="ready",
                samples=[
                    PlaybackSample(
                        "tmdb:movie:99",
                        "Watched",
                        "movie",
                        tmdb_id="99",
                        completed=True,
                        play_count=2,
                        watch_minutes=220,
                    )
                ],
            )

    agent = FakeAgentAdapter(
        [_agent_output([f"tmdb:{index}" for index in range(1, 6)])]
    )
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=FakeCandidateService(),
        agent_adapter=agent,
        run_id_factory=lambda: "run-playback",
        playback_service=PlaybackService(),
    )

    config = _config()
    config["minimum_samples"] = 1
    result = asyncio.run(orchestrator.run(PROFILE_ID, config))

    context = agent.profile_calls[0][1]
    assert context.playback["source"] == "playback_reporting"
    assert context.playback["samples"][0]["completed"] is True
    metrics = repository.load_run_history(PROFILE_ID)[0].metrics
    assert metrics["playback_source"] == "playback_reporting"
    assert metrics["playback_count"] == 1
    assert result.status == "success"


def test_playback_samples_are_the_only_profile_evidence():
    """真实播放样本达到门槛时推荐主链继续执行。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)

    class PlaybackService(FakePlaybackService):
        def collect(self, profile_id, config):
            return PlaybackSnapshot(
                profile_id=profile_id,
                username="Alice",
                source="playback_reporting",
                confidence="high",
                status="ready",
                samples=[
                    PlaybackSample(f"tmdb:movie:{index}", f"Watched {index}", "movie", tmdb_id=str(index))
                    for index in range(1, 6)
                ],
            )

    agent = FakeAgentAdapter([_agent_output([f"tmdb:{index}" for index in range(1, 6)])])
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=FakeCandidateService(),
        agent_adapter=agent,
        run_id_factory=lambda: "run-playback-only",
        playback_service=PlaybackService(),
    )
    config = _config()
    config["minimum_samples"] = 5

    result = asyncio.run(orchestrator.run(PROFILE_ID, config))

    assert result.status == "success"
    assert repository.load_run_history(PROFILE_ID)[0].metrics["profile_evidence_count"] == 5


def test_insufficient_playback_never_calls_agent_or_uses_subscription_fallback():
    """播放样本不足时停止运行，订阅记录不得成为画像兜底。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)

    class InsufficientPlaybackService(FakePlaybackService):
        def collect(self, profile_id, config):
            return PlaybackSnapshot(
                profile_id=profile_id,
                username="Alice",
                source="playback_reporting",
                confidence="high",
                status="ready",
                samples=[
                    PlaybackSample(
                        f"tmdb:movie:{index}",
                        f"Watched {index}",
                        "movie",
                        tmdb_id=str(index),
                    )
                    for index in range(1, 5)
                ],
            )

    agent = FakeAgentAdapter([_agent_output(["tmdb:1"])])
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=FakeCandidateService(),
        agent_adapter=agent,
        run_id_factory=lambda: "run-insufficient-playback",
        playback_service=InsufficientPlaybackService(),
    )
    config = _config()
    config["minimum_samples"] = 5

    result = asyncio.run(orchestrator.run(PROFILE_ID, config))

    assert result.status == "sample_insufficient"
    assert result.agent_calls == 0
    assert agent.calls == []
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["profile_evidence_count"] == 4
    assert "subscription_count" not in history.metrics


def test_rebuild_or_disabled_cache_does_not_read_previous_profile():
    """每次重建或关闭画像缓存时，旧画像不得进入 Agent 上下文。"""
    for overrides, expected_mode in (
        ({"rebuild_profile_each_run": True}, "rebuild"),
        ({"profile_cache_enabled": False}, "stateless"),
    ):
        plugin = FakePlugin()
        orchestrator, repository = _orchestrator(
            plugin, [_agent_output([f"tmdb:{index}" for index in range(1, 6)])]
        )
        repository.save_profile(
            UserProfile(
                profile_id=PROFILE_ID,
                username="Alice",
                summary="old",
                run_id="old",
            )
        )
        config = _config()
        config.update(overrides)

        result = asyncio.run(orchestrator.run(PROFILE_ID, config))

        assert orchestrator.agent_adapter.profile_calls[0][1].previous_profile is None
        history = repository.load_run_history(PROFILE_ID)[0]
        assert history.metrics["profile_mode"] == expected_mode
        assert history.metrics["previous_profile_used"] is False
        assert history.metrics["profile_cache_miss_reason"] == (
            "forced_rebuild" if expected_mode == "rebuild" else "disabled"
        )
        assert result.status == "success"


def test_library_items_are_removed_before_agent_context_is_built():
    """已入库 TMDB 候选不会进入 Agent 可见候选快照。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)

    class LibraryAdapter:
        def exists(self, candidate):
            return candidate.candidate_id in {"tmdb:1", "tmdb:2"}

    agent = FakeAgentAdapter(
        [_agent_output([f"tmdb:{index}" for index in range(3, 8)])]
    )
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=FakeCandidateService(12),
        agent_adapter=agent,
        run_id_factory=lambda: "run-library",
        library_adapter=LibraryAdapter(),
        playback_service=FakePlaybackService(),
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    candidate_ids = {
        item["candidate_id"]
        for item in agent.ranking_calls[0][1].candidates
    }
    assert "tmdb:1" not in candidate_ids
    assert "tmdb:2" not in candidate_ids
    assert repository.load_run_history(PROFILE_ID)[0].metrics["library_excluded_count"] == 2


def test_ranking_failure_uses_frozen_candidates_to_build_five_item_board():
    """排序异常保留新画像，并从冻结候选池安全补齐五条。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(plugin, [RuntimeError("llm offline")])
    repository.save_profile(UserProfile(profile_id=PROFILE_ID, username="Alice", summary="old", run_id="old"))
    repository.save_board(RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success"))

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 2
    assert repository.load_profile(PROFILE_ID).run_id == "run-1"
    board = repository.load_board(PROFILE_ID)
    assert board.run_id == "run-1"
    assert len(board.recommendations) == 5
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.status == "success"
    assert history.errors == []
    assert history.metrics["ranking_fallback_count"] == 5
    assert history.metrics["ranking_fallback_reason"] == "ranking_agent_failed"
    assert all(item.support is not None for item in board.recommendations)
    assert all(
        item.selection_source == "safe_fallback"
        for item in board.recommendations
    )
    assert history.metrics["selection_source_counts"] == {
        "agent": 0,
        "safe_fallback": 5,
    }
    analyses = repository.load_recommendation_analyses(PROFILE_ID, "run-1")
    assert len(analyses) == 5
    assert all(item.selection_source == "safe_fallback" for item in analyses)
    assert all(item.uncertainties for item in analyses)


def test_profile_failure_preserves_previous_profile_and_skips_ranking():
    """画像异常保留旧画像与旧榜单，并且排序 Agent 完全不启动。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin,
        [_agent_output(["tmdb:1"])],
        profile_outputs=[RuntimeError("profile offline")],
    )
    repository.save_profile(
        UserProfile(
            profile_id=PROFILE_ID, username="Alice", summary="old", run_id="old"
        )
    )
    repository.save_board(
        RecommendationBoard(
            profile_id=PROFILE_ID,
            username="Alice",
            run_id="old",
            status="success",
        )
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "profile_agent_failed"
    assert repository.load_profile(PROFILE_ID).run_id == "old"
    assert repository.load_board(PROFILE_ID).run_id == "old"
    assert orchestrator.agent_adapter.ranking_calls == []


def test_transient_playback_failure_preserves_previous_profile_and_board():
    """运行中 Playback Reporting 瞬时故障不得覆盖旧画像与旧榜单。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)

    class TransientPlaybackService(FakePlaybackService):
        def collect(self, profile_id, config):
            return PlaybackSnapshot(
                profile_id=profile_id,
                username="Alice",
                source="playback_reporting",
                confidence="high",
                status="transient_error",
                message="Playback Reporting 暂时不可用",
            )

    agent = FakeAgentAdapter([_agent_output(["tmdb:1"])])
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=FakeCandidateService(),
        agent_adapter=agent,
        run_id_factory=lambda: "run-transient-playback",
        playback_service=TransientPlaybackService(),
    )
    repository.save_profile(
        UserProfile(
            profile_id=PROFILE_ID, username="Alice", summary="old", run_id="old"
        )
    )
    repository.save_board(
        RecommendationBoard(
            profile_id=PROFILE_ID,
            username="Alice",
            run_id="old",
            status="success",
        )
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "playback_unavailable"
    assert result.board.run_id == "old"
    assert repository.load_profile(PROFILE_ID).run_id == "old"
    assert repository.load_board(PROFILE_ID).run_id == "old"
    assert repository.load_run_history(PROFILE_ID)[0].metrics["playback_status"] == (
        "transient_error"
    )
    assert agent.calls == []


def test_non_ready_probe_stops_before_collection_and_preserves_old_data():
    """运行前探测未就绪时不得采集、调用 Agent 或覆盖旧数据。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)

    class BlockedPlaybackService:
        def __init__(self):
            """初始化采集调用计数。"""
            self.collect_calls = 0

        def probe(self, profile_id, config):
            """返回权限不足的探测结果。"""
            return PlaybackCapability(profile_id, "permission_error", "无权访问")

        def collect(self, profile_id, config):
            """拒绝在失败探测之后执行播放采集。"""
            self.collect_calls += 1
            raise AssertionError("collect must not run after a blocked probe")

    playback_service = BlockedPlaybackService()
    agent = FakeAgentAdapter([_agent_output(["tmdb:1"])])
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=FakeCandidateService(),
        agent_adapter=agent,
        run_id_factory=lambda: "run-probe-blocked",
        playback_service=playback_service,
    )
    repository.save_profile(
        UserProfile(profile_id=PROFILE_ID, username="Alice", summary="old", run_id="old")
    )
    repository.save_board(
        RecommendationBoard(
            profile_id=PROFILE_ID,
            username="Alice",
            run_id="old",
            status="success",
        )
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "playback_unavailable"
    assert result.board.run_id == "old"
    assert repository.load_profile(PROFILE_ID).run_id == "old"
    assert repository.load_board(PROFILE_ID).run_id == "old"
    assert playback_service.collect_calls == 0
    assert agent.calls == []
    metrics = repository.load_run_history(PROFILE_ID)[0].metrics
    assert metrics["stage_order"] == ["probe"]
    assert metrics["stage_status"] == {"probe": "playback_unavailable"}
    assert metrics["playback_probe_status"] == "permission_error"


def test_retryable_empty_agent_output_retries_once_and_records_both_calls():
    """A transient no-text completion gets one bounded retry with honest metrics."""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            RetryableAgentError("no text"),
            _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
        ],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    assert len(orchestrator.agent_adapter.ranking_calls) == 2
    assert repository.load_run_history(PROFILE_ID)[0].metrics["agent_calls"] == 3


def test_retryable_empty_agent_output_falls_back_after_one_retry():
    """连续两次无文本结果后停止调用，并从冻结候选池补齐五条。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin,
        [RetryableAgentError("first"), RetryableAgentError("second")],
    )
    repository.save_profile(UserProfile(profile_id=PROFILE_ID, username="Alice", summary="old", run_id="old"))
    repository.save_board(RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success"))

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    assert repository.load_profile(PROFILE_ID).run_id == "run-1"
    board = repository.load_board(PROFILE_ID)
    assert board.run_id == "run-1"
    assert len(board.recommendations) == 5
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.errors == []
    assert history.metrics["agent_calls"] == 3
    assert history.metrics["ranking_fallback_count"] == 5
    assert history.metrics["ranking_fallback_reason"] == "ranking_agent_failed"


def test_invalid_json_retries_once_with_stricter_prompt():
    """Invalid JSON is rejected, then one strict retry may succeed."""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            "not-json",
            _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
        ],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    assert "上一次输出未通过严格校验" in orchestrator.agent_adapter.ranking_calls[1][0]
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["agent_calls"] == 3
    assert history.errors == []
    assert history.metrics["ranking_retry_count"] == 1
    assert history.metrics["retry_events"][0]["stage"] == "ranking"


def test_invalid_profile_json_retries_once_with_stricter_prompt():
    """画像输出无效时第二次调用必须追加 JSON 纠错指令。"""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [_agent_output([f"tmdb:{index}" for index in range(1, 6)])],
        profile_outputs=["not-json", _profile_output()],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert len(orchestrator.agent_adapter.profile_calls) == 2
    assert "上一次输出未通过严格校验" in orchestrator.agent_adapter.profile_calls[1][0]
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["profile_agent_calls"] == 2
    assert history.errors == []
    assert history.metrics["profile_retry_count"] == 1
    assert history.metrics["retry_events"][0]["stage"] == "profile"


def test_invalid_json_falls_back_after_one_strict_retry():
    """连续两次非法 JSON 后停止调用，并从冻结候选池补齐五条。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(plugin, ["bad-one", "bad-two"])
    repository.save_board(
        RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success")
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    board = repository.load_board(PROFILE_ID)
    assert board.run_id == "run-1"
    assert len(board.recommendations) == 5
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.errors == []
    assert history.metrics["agent_calls"] == 3
    assert history.metrics["ranking_fallback_count"] == 5
    assert history.metrics["ranking_fallback_reason"] == "ranking_validation_failed"


def test_partial_valid_output_gets_exactly_one_successful_refill():
    """Four accepted items trigger one refill for the remaining slot."""
    first = _agent_output([f"tmdb:{index}" for index in range(1, 5)])
    refill = _agent_output(["tmdb:5"])
    orchestrator, repository = _orchestrator(FakePlugin(), [first, refill])

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    assert len(repository.load_board(PROFILE_ID).recommendations) == 5
    assert "tmdb:1" in orchestrator.agent_adapter.ranking_calls[1][0]
    assert "排除" in orchestrator.agent_adapter.ranking_calls[1][0]


def test_overlong_copy_gets_one_directed_rewrite_and_preserves_complete_result():
    """超长简介只触发一次定向重写，成功后原样保存完整短句。"""
    first = _agent_output_with_overrides(
        [f"tmdb:{index}" for index in range(1, 6)],
        {
            "tmdb:5": {
                "summary": "一名侦探追查多年未解旧案，并在封闭小镇逐步发现家族隐藏已久的秘密。"
            }
        },
    )
    rewritten = _agent_output_with_overrides(
        ["tmdb:5"],
        {"tmdb:5": {"summary": "密室旧案牵出尘封真相。"}},
    )
    orchestrator, repository = _orchestrator(FakePlugin(), [first, rewritten])

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert len(orchestrator.agent_adapter.ranking_calls) == 2
    board = repository.load_board(PROFILE_ID)
    rewritten_item = next(
        item for item in board.recommendations if item.candidate_id == "tmdb:5"
    )
    assert rewritten_item.summary == "密室旧案牵出尘封真相。"
    rewrite_prompt = orchestrator.agent_adapter.ranking_calls[1][0]
    assert '"candidate_id":"tmdb:5","reason":"summary_too_long"' in rewrite_prompt
    assert "一名侦探追查多年未解旧案" not in rewrite_prompt
    analysis = next(
        item
        for item in repository.load_recommendation_analyses(PROFILE_ID, "run-1")
        if item.candidate_id == "tmdb:5"
    )
    assert analysis.prompt_fingerprint == RecommendationAnalysisBuilder.prompt_fingerprint(
        orchestrator.agent_adapter.ranking_calls[0][0],
        rewrite_prompt,
    )
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["copy_rewrite_attempted"] is True
    assert history.metrics["copy_rewrite_candidate_count"] == 1
    assert history.metrics["copy_rewrite_success_count"] == 1
    assert history.metrics["copy_template_fallback_count"] == 0


def test_failed_copy_rewrite_uses_complete_template_without_prefix_truncation():
    """唯一重写仍是残句时改用模板，绝不保存原文前缀。"""
    overlong = "一名侦探追查多年未解旧案，并在封闭小镇逐步发现家族隐藏已久的秘密。"
    first = _agent_output_with_overrides(
        [f"tmdb:{index}" for index in range(1, 6)],
        {"tmdb:5": {"summary": overlong}},
    )
    incomplete = _agent_output_with_overrides(
        ["tmdb:5"],
        {"tmdb:5": {"summary": "侦探继续追查旧案并"}},
    )
    orchestrator, repository = _orchestrator(FakePlugin(), [first, incomplete])

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    assert len(orchestrator.agent_adapter.ranking_calls) == 2
    board = repository.load_board(PROFILE_ID)
    fallback_item = next(
        item for item in board.recommendations if item.candidate_id == "tmdb:5"
    )
    assert fallback_item.selection_source == "safe_fallback"
    assert fallback_item.summary == "围绕悬疑题材展开的完整故事。"
    assert fallback_item.summary != overlong[:30]
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["copy_rewrite_candidate_count"] == 1
    assert history.metrics["copy_rewrite_success_count"] == 0
    assert history.metrics["copy_template_fallback_count"] == 1


def test_refill_ignores_extra_fields_without_discarding_the_batch():
    """补选中的无关字段只记告警，不得让整批推荐进入安全补位。"""
    refill = _agent_output_with_overrides(
        [f"tmdb:{index}" for index in range(2, 6)],
        {"tmdb:3": {"completed_episode_count": 2}},
    )
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [_agent_output(["tmdb:1"]), refill],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    assert len(orchestrator.agent_adapter.ranking_calls) == 2
    board = repository.load_board(PROFILE_ID)
    assert [item.candidate_id for item in board.recommendations] == [
        "tmdb:1",
        "tmdb:2",
        "tmdb:3",
        "tmdb:4",
        "tmdb:5",
    ]
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["ranking_fallback_count"] == 0
    assert history.metrics["ranking_fallback_reason"] == ""
    assert any(
        "completed_episode_count" in warning
        for warning in history.metrics["refill_parse_warnings"]
    )


def test_initial_domain_drops_are_explained_to_refill():
    """首轮已知候选的安全丢弃原因必须进入补选提示并允许改写。"""
    first = _agent_output_with_overrides(
        [f"tmdb:{index}" for index in range(1, 6)],
        {
            "tmdb:4": {
                "reason": "你偏爱悬疑题材，这部经典作品不容错过。",
                },
                "tmdb:5": {
                    "positive_evidence": [
                        {
                            "dimension": "type",
                            "user_value": "movie",
                            "candidate_value": "movie",
                        }
                    ],
                },
        },
    )
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [first, _agent_output(["tmdb:4", "tmdb:5"])],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert len(repository.load_board(PROFILE_ID).recommendations) == 5
    refill_prompt = orchestrator.agent_adapter.ranking_calls[1][0]
    assert '"candidate_id":"tmdb:4","reason":"invalid_reason"' in refill_prompt
    assert (
            '"candidate_id":"tmdb:5","reason":"insufficient_verified_evidence"'
        in refill_prompt
    )


def test_single_refill_drop_stops_without_starting_a_second_agent_call():
    """唯一补选被安全门丢弃时由本地补齐五条，不再启动第二轮。"""
    rejected_refill = _agent_output_with_overrides(
        ["tmdb:5"],
        {
            "tmdb:5": {
                "reason": "你偏爱悬疑题材，这部经典作品不容错过。",
            }
        },
    )
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            _agent_output([f"tmdb:{index}" for index in range(1, 5)]),
            rejected_refill,
            _agent_output(["tmdb:5"]),
        ],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    board = repository.load_board(PROFILE_ID)
    assert board.run_id == "run-1"
    assert len(board.recommendations) == 5
    assert len(orchestrator.agent_adapter.ranking_calls) == 2
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.errors == []
    assert history.metrics["refill_agent_calls"] == 1
    assert history.metrics["refill_drops"] == ["invalid_reason"]
    assert history.metrics["ranking_fallback_count"] == 1
    assert history.metrics["ranking_fallback_reason"] == "refill_insufficient"


def test_refill_still_insufficient_uses_one_local_fallback_item():
    """唯一补选仍不足时从冻结候选池补一条，保持榜单五条。"""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            _agent_output([f"tmdb:{index}" for index in range(1, 5)]),
            _agent_output([]),
            _agent_output([]),
        ],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    board = repository.load_board(PROFILE_ID)
    assert board.run_id == "run-1"
    assert board.status == "success"
    assert len(board.recommendations) == 5
    assert result.agent_calls == 3
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.errors == []
    assert history.metrics["ranking_fallback_count"] == 1
    assert history.metrics["ranking_fallback_reason"] == "refill_insufficient"


def test_refill_invalid_json_stops_after_the_single_bounded_call():
    """唯一补选返回非 JSON 时本地补齐五条，不再扩大模型往返。"""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            _agent_output([f"tmdb:{index}" for index in range(1, 5)]),
            "not-json",
            _agent_output(["tmdb:5"]),
        ],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    board = repository.load_board(PROFILE_ID)
    assert board.run_id == "run-1"
    assert len(board.recommendations) == 5
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.errors == []
    assert history.metrics["ranking_fallback_count"] == 1
    assert history.metrics["ranking_fallback_reason"] == "refill_validation_failed"
    assert len(orchestrator.agent_adapter.ranking_calls) == 2


def test_memory_revision_change_during_ranking_discards_old_policy_board():
    """排序期间确认记忆更新时旧策略结果不得保存。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)

    class MemoryChangingCandidateService(FakeCandidateService):
        """在来源补全阶段模拟另一请求确认了新偏好。"""

        def __init__(self):
            """初始化候选池和一次性投影标记。"""
            super().__init__(12)
            self.changed = False

        def enrich_recommendation_sources(self, recommendations):
            """在最终提交锁之前推进确认记忆 revision。"""
            del recommendations
            if self.changed:
                return
            self.changed = True
            result = repository.project_preference_memory(
                PROFILE_ID,
                [
                    PreferenceMemoryItem(
                        item_id="memory-during-ranking",
                        category="genre",
                        value="悬疑",
                        polarity="positive",
                        strength=1.0,
                        certainty=1.0,
                        evidence_refs=("feedback:1",),
                        source_event_sequence=1,
                        created_at="2026-07-28T12:00:00+00:00",
                    )
                ],
                expected_revision=0,
                source_event_sequence=1,
            )
            assert result.applied is True

    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=MemoryChangingCandidateService(),
        agent_adapter=FakeAgentAdapter(
            [_agent_output([f"tmdb:{index}" for index in range(1, 6)])]
        ),
        run_id_factory=lambda: "run-policy-superseded",
        playback_service=FakePlaybackService(),
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "policy_superseded"
    assert result.board is None
    assert repository.load_board(PROFILE_ID) is None
    assert repository.load_preference_memory(PROFILE_ID).memory_revision == 1
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.status == "policy_superseded"
    assert history.metrics["policy_memory_revision"] == 0


def test_zero_valid_agent_items_builds_five_item_fallback_board():
    """Agent 没有安全推荐时从冻结候选池构建五条保底榜单。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin,
        [_agent_output(["tmdb:404"]), _agent_output([]), _agent_output([])],
    )
    repository.save_board(RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success"))

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    board = repository.load_board(PROFILE_ID)
    assert board.run_id == "run-1"
    assert len(board.recommendations) == 5
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.errors == []
    assert history.metrics["ranking_fallback_count"] == 5
    assert history.metrics["ranking_fallback_reason"] == "refill_insufficient"
    assert all(item.support is not None for item in board.recommendations)
    assert all(
        item.selection_source == "safe_fallback"
        for item in board.recommendations
    )


def test_board_save_failure_keeps_new_profile_and_previous_board():
    """排序榜单写入失败不回滚已经独立保存的画像。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin, [_agent_output([f"tmdb:{index}" for index in range(1, 6)])]
    )
    repository.save_profile(UserProfile(profile_id=PROFILE_ID, username="Alice", summary="old", run_id="old"))
    repository.save_board(RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success"))
    plugin.fail_board_save = True

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "ranking_save_failed"
    assert repository.load_profile(PROFILE_ID).run_id == "run-1"
    assert repository.load_board(PROFILE_ID).run_id == "old"


def test_ignore_during_run_is_rechecked_and_refilled_before_board_commit():
    """运行期间新增的忽略反馈在最终提交时生效并安全补足五条。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(
        RecommendationBoard(
            profile_id=PROFILE_ID,
            username="Alice",
            run_id="old",
            status="success",
            recommendations=[
                RecommendationItem(
                    candidate_id="tmdb:movie:2",
                    rank=2,
                    title="Title 2",
                    media_type="movie",
                    source_ids={"tmdb": "2"},
                )
            ],
        )
    )

    class IgnoringCandidateService(FakeCandidateService):
        """在排序完成后模拟用户忽略仍位于旧榜单中的条目。"""

        def __init__(self):
            """初始化候选池与一次性忽略标记。"""
            super().__init__(12)
            self.candidates = [
                    Candidate(
                        candidate_id=f"tmdb:movie:{index}",
                        title=f"Title {index}",
                        media_type="movie",
                        genres=["悬疑"],
                        regions=["中国"],
                        source_ids={"tmdb": str(index)},
                    )
                for index in range(1, 13)
            ]
            self.ignored = False

        def enrich_recommendation_sources(self, recommendations):
            """首次来源补全时写入运行期间新增的忽略反馈。"""
            del recommendations
            if self.ignored:
                return
            self.ignored = True
            result = ArchiveService(repository).ignore(PROFILE_ID, "tmdb:movie:2")
            assert result.changed is True

    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=IgnoringCandidateService(),
        agent_adapter=FakeAgentAdapter(
            [_agent_output([f"tmdb:movie:{index}" for index in range(1, 6)])]
        ),
        run_id_factory=lambda: "run-ignore-race",
        playback_service=FakePlaybackService(),
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    board = repository.load_board(PROFILE_ID)
    assert [item.candidate_id for item in board.recommendations] == [
        "tmdb:movie:1",
        "tmdb:movie:3",
        "tmdb:movie:4",
        "tmdb:movie:5",
        "tmdb:movie:6",
    ]
    assert [item.rank for item in board.recommendations] == [1, 2, 3, 4, 5]
    assert [entry.candidate_id for entry in repository.load_archive(PROFILE_ID).entries] == [
        "tmdb:movie:2"
    ]
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["archive_commit_excluded_count"] == 1
    assert history.metrics["ranking_fallback_count"] == 1
    assert history.metrics["ranking_fallback_reason"] == "archive_updated_during_run"


def test_dislike_during_run_is_rechecked_and_refilled_before_board_commit():
    """运行期间新增点踩在提交前生效，且不借用忽略归档语义。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)

    class DislikingCandidateService(FakeCandidateService):
        """在排序结束后模拟另一请求写入作品级点踩。"""

        def __init__(self):
            """初始化使用类型化 TMDB 身份的候选池。"""
            super().__init__(12)
            self.candidates = [
                    Candidate(
                        candidate_id=f"tmdb:movie:{index}",
                        title=f"Title {index}",
                        media_type="movie",
                        genres=["悬疑"],
                        regions=["中国"],
                        source_ids={"tmdb": str(index)},
                    )
                for index in range(1, 13)
            ]
            self.disliked = False

        def enrich_recommendation_sources(self, recommendations):
            """首次来源补全时追加一条并发点踩事件。"""
            del recommendations
            if self.disliked:
                return
            self.disliked = True
            repository.append_feedback_event(
                FeedbackEvent(
                    profile_id=PROFILE_ID,
                    kind="dislike",
                    candidate_id="tmdb:movie:2",
                    run_id="run-old-board",
                    created_by_mp_user_id="mp-user-1",
                    idempotency_key="dislike-during-run",
                )
            )

    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=DislikingCandidateService(),
        agent_adapter=FakeAgentAdapter(
            [_agent_output([f"tmdb:movie:{index}" for index in range(1, 6)])]
        ),
        run_id_factory=lambda: "run-dislike-race",
        playback_service=FakePlaybackService(),
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert [item.candidate_id for item in result.board.recommendations] == [
        "tmdb:movie:1",
        "tmdb:movie:3",
        "tmdb:movie:4",
        "tmdb:movie:5",
        "tmdb:movie:6",
    ]
    assert repository.load_archive(PROFILE_ID).entries == []
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["archive_commit_excluded_count"] == 0
    assert history.metrics["dislike_commit_excluded_count"] == 1
    assert history.metrics["ranking_fallback_count"] == 1
    assert history.metrics["ranking_fallback_reason"] == "dislike_updated_during_run"


def test_concurrent_refresh_returns_running_without_second_agent_call():
    """The same profile identity cannot start two recommendation runs concurrently."""
    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingAgent(FakeAgentAdapter):
        async def run_profile(self, prompt, trusted_context):
            self.calls.append(("profile", prompt, trusted_context))
            self.profile_calls.append((prompt, trusted_context))
            entered.set()
            await release.wait()
            return _profile_output(len(trusted_context.playback["samples"]))

    async def scenario():
        plugin = FakePlugin()
        repository = AgentRankRepository(plugin)
        agent = BlockingAgent([_agent_output([f"tmdb:{index}" for index in range(1, 6)])])
        orchestrator = RecommendationOrchestrator(
            repository,
            FakeCandidateService(),
            agent,
            run_id_factory=lambda: "run-lock",
            playback_service=FakePlaybackService(),
        )
        first_task = asyncio.create_task(orchestrator.run(PROFILE_ID, _config()))
        await entered.wait()
        second = await orchestrator.run(PROFILE_ID, _config())
        release.set()
        first = await first_task
        return first, second, agent

    first, second, agent = asyncio.run(scenario())

    assert first.status == "success"
    assert second.status == "running"
    assert len(agent.profile_calls) == 1


def test_different_profiles_can_enter_profile_stage_concurrently():
    """不同画像身份使用独立互斥键，可同时进入画像 Agent 阶段。"""
    other_profile_id = "emby:home:user-2"
    entered = {PROFILE_ID: asyncio.Event(), other_profile_id: asyncio.Event()}
    release = asyncio.Event()

    class ConcurrentAgent(FakeAgentAdapter):
        async def run_profile(self, prompt, trusted_context):
            """等待两个画像同时进入后再释放 Agent 输出。"""
            self.calls.append(("profile", prompt, trusted_context))
            self.profile_calls.append((prompt, trusted_context))
            profile_id = trusted_context.playback["profile_id"]
            entered[profile_id].set()
            await asyncio.wait_for(
                asyncio.gather(*(event.wait() for event in entered.values())),
                timeout=1,
            )
            await release.wait()
            return _profile_output(len(trusted_context.playback["samples"]))

    async def scenario():
        """并发运行两个不同 profile_id 的完整推荐任务。"""
        plugin = FakePlugin()
        repository = AgentRankRepository(plugin)
        agent = ConcurrentAgent(
            [
                _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
                _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
            ]
        )
        run_ids = iter(("run-profile-1", "run-profile-2"))
        orchestrator = RecommendationOrchestrator(
            repository,
            FakeCandidateService(),
            agent,
            run_id_factory=lambda: next(run_ids),
            playback_service=FakePlaybackService(),
        )
        config = _config()
        config["emby_identities"] = [
            *config["emby_identities"],
            {
                "server_name": "home",
                "user_id": "user-2",
                "username": "Bob",
                "profile_id": other_profile_id,
                "schema_version": 1,
            },
        ]
        tasks = [
            asyncio.create_task(orchestrator.run(PROFILE_ID, config)),
            asyncio.create_task(orchestrator.run(other_profile_id, config)),
        ]
        await asyncio.wait_for(
            asyncio.gather(*(event.wait() for event in entered.values())),
            timeout=1,
        )
        release.set()
        return await asyncio.gather(*tasks), agent

    results, agent = asyncio.run(scenario())

    assert [result.status for result in results] == ["success", "success"]
    assert len(agent.profile_calls) == 2
