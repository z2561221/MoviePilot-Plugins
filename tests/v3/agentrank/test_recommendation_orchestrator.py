"""AgentRank recommendation orchestration, refill, lock, and atomic save tests."""

import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"
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
tournament_module = importlib.import_module(f"{PACKAGE_NAME}.service.tournament")
archive_service_module = importlib.import_module(f"{PACKAGE_NAME}.service.archive")
keyword_module = importlib.import_module(f"{PACKAGE_NAME}.service.keyword_resolution")
analysis_builder_module = importlib.import_module(f"{PACKAGE_NAME}.service.analysis")

Candidate = candidate_module.Candidate
UserProfile = profile_module.UserProfile
PROFILE_SCHEMA_VERSION = profile_module.PROFILE_SCHEMA_VERSION
ProfilePreferences = preferences_module.ProfilePreferences
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
FeedbackEvent = feedback_module.FeedbackEvent
PreferenceMemoryItem = memory_module.PreferenceMemoryItem
PreferenceMemory = memory_module.PreferenceMemory
PlaybackSample = playback_module.PlaybackSample
PlaybackSnapshot = playback_module.PlaybackSnapshot
PlaybackCapability = playback_module.PlaybackCapability
AgentRankRepository = repository_module.AgentRankRepository
RecommendationOrchestrator = orchestrator_module.RecommendationOrchestrator
ensure_default_persona_visibility = orchestrator_module._ensure_default_persona_visibility
DEFAULT_PERSONA_PROMPT = orchestrator_module.DEFAULT_PERSONA_PROMPT
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


def test_default_persona_visibility_fallback_changes_only_two_short_reasons():
    """默认人设缺席时只给两条短理由补语气，不触碰事实字段或自定义人设。"""
    items = [
        RecommendationItem(
            candidate_id=f"tmdb:{index}",
            rank=index,
            reason=f"悬疑动画与复杂人物关系都很贴合{index}",
            summary=f"客观简介{index}",
            selection_source="agent",
        )
        for index in range(1, 6)
    ]

    visible, applied = ensure_default_persona_visibility(
        items, DEFAULT_PERSONA_PROMPT
    )

    assert (visible, applied) == (2, 2)
    assert items[0].reason.startswith("唔，")
    assert items[1].reason.startswith("嘛，")
    assert [item.summary for item in items] == [
        f"客观简介{index}" for index in range(1, 6)
    ]
    custom_items = [
        RecommendationItem(
            candidate_id="tmdb:custom",
            rank=1,
            reason="保持用户自己的表达",
            selection_source="agent",
        )
    ]
    assert ensure_default_persona_visibility(custom_items, "自定义语气") == (0, 0)
    assert custom_items[0].reason == "保持用户自己的表达"


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
        self.processing_counts = {}

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
        previous_board_candidate_ids=None,
        exclude_library_candidates=True,
    ):
        self.retrieval_plan = retrieval_plan
        self.playback_samples = list(playback_samples or [])
        self.archived_candidate_ids = set(archived_candidate_ids or set())
        self.disliked_candidate_ids = set(disliked_candidate_ids or set())
        self.previous_board_candidate_ids = set(
            previous_board_candidate_ids or set()
        )
        self.exclude_library_candidates = bool(exclude_library_candidates)
        self.negative_keywords = list(negative_keywords or [])
        self.profile_version = dict(profile_version or {})
        self.collected_candidate_ids = [
            *getattr(self, "collected_candidate_ids", []),
            [candidate.candidate_id for candidate in self.candidates[:candidate_limit]],
        ]
        values = dict(
            profile_id=profile_id,
            run_id=run_id,
            status="ready",
            candidates=self.candidates[:candidate_limit],
            source_errors={},
            rejected_sources=[],
            rejected_count=0,
            request_recipes=[],
            processing_counts=dict(self.processing_counts),
        )
        if self.minimum_frozen_candidates is not None:
            values["minimum_frozen_candidates"] = self.minimum_frozen_candidates
        return SimpleNamespace(**values)

    def enrich_recommendation_sources(self, recommendations):
        """模拟候选服务为推荐补充来源链接的无副作用步骤。"""
        del recommendations


class FakeAgentAdapter:
    """分别返回画像与排序角色的排队输出或异常。"""

    def __init__(self, outputs, profile_outputs=None, retrieval_outputs=None):
        self.ranking_outputs = list(outputs)
        self.profile_outputs = (
            None if profile_outputs is None else list(profile_outputs)
        )
        self.retrieval_outputs = (
            None if retrieval_outputs is None else list(retrieval_outputs)
        )
        if retrieval_outputs is None:
            self.run_retrieval = None
        self.calls = []
        self.profile_calls = []
        self.ranking_calls = []
        self.retrieval_calls = []

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
            else _profile_output(
                int(
                    trusted_context.playback.get("sample_count")
                    or len(trusted_context.playback["samples"])
                )
            )
        )
        return self._result(output)

    async def run_ranking(self, prompt, trusted_context):
        """执行排序角色测试调用。"""
        self.calls.append(("ranking", prompt, trusted_context))
        self.ranking_calls.append((prompt, trusted_context))
        return self._result(self.ranking_outputs.pop(0))

    async def run_retrieval(self, prompt, trusted_context):
        """执行检索策划角色测试调用。"""
        self.calls.append(("retrieval", prompt, trusted_context))
        self.retrieval_calls.append((prompt, trusted_context))
        return self._result(self.retrieval_outputs.pop(0))

    async def run(self, prompt, trusted_context):
        """按受信上下文角色兼容分发测试调用。"""
        if trusted_context.agent_role == "profile":
            return await self.run_profile(prompt, trusted_context)
        return await self.run_ranking(prompt, trusted_context)


class FakeTournamentAgentAdapter(FakeAgentAdapter):
    """模拟支持独立初赛、决赛与批次失败的生产适配器。"""

    def __init__(self, preliminary_failures=None, final_outputs=None):
        """初始化按批次消费的失败队列和可选决赛输出。"""
        super().__init__([])
        self.preliminary_failures = {
            str(batch_id): list(values)
            for batch_id, values in dict(preliminary_failures or {}).items()
        }
        self.final_outputs = list(final_outputs or ())
        self.preliminary_calls = []
        self.final_calls = []
        self.preliminary_active = 0
        self.preliminary_max_active = 0

    @staticmethod
    def _batch_id(trusted_context):
        """从隔离会话 ID 取出稳定的初赛批次 ID。"""
        marker = trusted_context.run_id.rfind("batch-")
        return trusted_context.run_id[marker:] if marker >= 0 else ""

    @staticmethod
    def _preliminary_output(trusted_context):
        """为当前批次生成覆盖全部候选的严格判断卡。"""
        quota = int(trusted_context.submission_constraints["advance_quota"])
        return json.dumps(
            {
                "judgments": [
                    {
                        "candidate_id": item["candidate_id"],
                        "fit_score": 100 - index,
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
                        "counter_evidence": None,
                        "advance": index < quota,
                    }
                    for index, item in enumerate(trusted_context.candidates)
                ]
            },
            ensure_ascii=False,
        )

    async def run_preliminary(self, prompt, trusted_context):
        """记录并发状态，按需让一个批次失败或返回完整判断卡。"""
        batch_id = self._batch_id(trusted_context)
        self.calls.append(("preliminary", prompt, trusted_context))
        self.preliminary_calls.append((batch_id, prompt, trusted_context))
        self.preliminary_active += 1
        self.preliminary_max_active = max(
            self.preliminary_max_active,
            self.preliminary_active,
        )
        try:
            await asyncio.sleep(0.01)
            queue = self.preliminary_failures.get(batch_id) or []
            if queue:
                return self._result(queue.pop(0))
            return self._preliminary_output(trusted_context)
        finally:
            self.preliminary_active -= 1

    async def run_final(self, prompt, trusted_context):
        """按队列返回决赛失败，默认逆序提交以验证 Agent 顺序。"""
        self.calls.append(("final", prompt, trusted_context))
        self.final_calls.append((prompt, trusted_context))
        if self.final_outputs:
            return self._result(self.final_outputs.pop(0))
        candidate_ids = [
            item["candidate_id"] for item in trusted_context.candidates
        ]
        ordered_ids = list(reversed(candidate_ids))
        selected_ids = ordered_ids[:5]
        payload = json.loads(_agent_output(selected_ids))
        options_by_id = {
            str(candidate_id): {
                "positive_evidence_options": [
                    dict(item)
                    for item in options.get("positive_evidence_options") or ()
                ],
                "counter_evidence_options": [
                    dict(item)
                    for item in options.get("counter_evidence_options") or ()
                ],
            }
            for candidate_id, options in trusted_context.submission_constraints[
                "evidence_options"
            ].items()
        }
        for recommendation in payload["recommendations"]:
            options = options_by_id[recommendation["candidate_id"]]
            recommendation["positive_evidence"] = list(
                options["positive_evidence_options"][:2]
            )
            recommendation["counter_evidence"] = list(
                options["counter_evidence_options"][:1]
            )
        return json.dumps(payload, ensure_ascii=False)


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
        },
        ensure_ascii=False,
    )


def _retrieval_output(*, tool="tmdb_movies", ranking_tags=None, media_types=None):
    """构造独立于稳定画像的单轮检索计划。"""
    return json.dumps(
        {
            "goal": "寻找新的悬疑候选",
            "actions": [{"tool": tool, "purpose": "related"}],
            "filters": {
                "media_types": media_types or ["movie"],
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
            "hard_constraints": ["排除已观看媒体"],
            "soft_signals": ["悬疑"],
            "relaxation_order": ["热度"],
        },
        ensure_ascii=False,
    )


def _agent_output(candidate_ids):
    return json.dumps(
        {
            "recommendations": [
                {
                    "candidate_id": candidate_id,
                    "fit_score": 80,
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


def _agent_output_with_counter_evidence(candidate_ids, *, include_counter):
    """构造保留或遗漏已存在反证的决赛输出。"""
    payload = json.loads(_agent_output(candidate_ids))
    for recommendation in payload["recommendations"]:
        recommendation["counter_evidence"] = (
            [
                {
                    "dimension": "region",
                    "user_value": "中国",
                    "candidate_value": "中国",
                }
            ]
            if include_counter
            else []
        )
    return json.dumps(payload, ensure_ascii=False)


def _orchestrator(
    plugin,
    outputs,
    candidate_count=12,
    profile_outputs=None,
    retrieval_plan_resolver=None,
    progress_callback=None,
    retrieval_outputs=None,
):
    repository = AgentRankRepository(plugin)
    return (
        RecommendationOrchestrator(
            repository=repository,
            candidate_service=FakeCandidateService(candidate_count),
            agent_adapter=FakeAgentAdapter(
                outputs,
                profile_outputs=profile_outputs,
                retrieval_outputs=retrieval_outputs,
            ),
            run_id_factory=lambda: "run-1",
            playback_service=FakePlaybackService(),
            retrieval_plan_resolver=retrieval_plan_resolver,
            progress_callback=progress_callback,
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


def _tournament_orchestrator(
    plugin,
    *,
    candidate_count=15,
    agent=None,
    run_id_factory=None,
):
    """构建启用初赛和决赛协议的测试编排器。"""
    repository = AgentRankRepository(plugin)
    candidate_service = FakeCandidateService(candidate_count)
    tournament_agent = agent or FakeTournamentAgentAdapter()
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=candidate_service,
        agent_adapter=tournament_agent,
        run_id_factory=run_id_factory or (lambda: "run-tournament"),
        playback_service=FakePlaybackService(),
    )
    return orchestrator, repository, candidate_service, tournament_agent


def test_exposed_board_without_action_creates_one_rotation_signal():
    """已曝光但无操作的榜单只产生一条幂等轮换信号。"""
    orchestrator, repository = _orchestrator(FakePlugin(), [])
    board = RecommendationBoard(
        profile_id=PROFILE_ID,
        username="Alice",
        run_id="run-exposed",
        revision=4,
    )
    repository.save_board(board)
    repository.record_board_exposure(
        PROFILE_ID,
        board.run_id,
        board.revision,
        ["tmdb:1"],
        "2026-08-05T00:00:00+00:00",
    )

    metrics = {}
    orchestrator._record_rotation_signal_if_needed(PROFILE_ID, board, metrics)
    assert metrics["rotation_signal_created"] is True
    signals = repository.load_short_term_signals(PROFILE_ID)
    assert len(signals) == 1
    assert signals[0].kind == "rotation"
    assert signals[0].idempotency_key == "rotation:run-exposed:4"

    second_metrics = {}
    orchestrator._record_rotation_signal_if_needed(PROFILE_ID, board, second_metrics)
    assert second_metrics["rotation_signal_created"] is False
    assert len(repository.load_short_term_signals(PROFILE_ID)) == 1


def test_neutral_feedback_changes_adaptive_preference_fingerprint():
    """中立纠正虽不新增短期信号，也必须使自适应门控看到偏好变化。"""
    orchestrator, _ = _orchestrator(FakePlugin(), [])
    profile = UserProfile(
        profile_id=PROFILE_ID,
        username="Alice",
        profile_input_fingerprint="profile-input",
    )
    preferences = ProfilePreferences(profile_id=PROFILE_ID)
    memory = PreferenceMemory.empty(PROFILE_ID)

    liked = orchestrator._adaptive_preference_fingerprint(
        PROFILE_ID,
        profile,
        preferences,
        memory,
        {"tmdb:movie:1": "like"},
    )
    neutral = orchestrator._adaptive_preference_fingerprint(
        PROFILE_ID,
        profile,
        preferences,
        memory,
        {"tmdb:movie:1": "neutral"},
    )

    assert liked != neutral


def test_success_atomically_saves_profile_board_and_run_history():
    """A complete valid run replaces both current objects and records metrics."""
    plugin = FakePlugin()
    progress_events = []
    orchestrator, repository = _orchestrator(
        plugin,
        [_agent_output([f"tmdb:{index}" for index in range(1, 6)])],
        progress_callback=progress_events.append,
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
    assert "confidence_threshold" not in ranking_weights
    assert "media_types" not in ranking_weights
    assert "exclude_keywords" not in ranking_weights
    assert ranking_weights["base_weights"]["rating_weight"] == 0.9
    assert {
        (item["dimension"], item["value"], item["evidence_count"])
        for item in ranking_weights["evidence_catalog"]
    } >= {("type", "movie", 5), ("theme", "悬疑", 5)}
    assert orchestrator._candidate_service.retrieval_plan.filters.media_types == ()
    assert orchestrator._candidate_service.retrieval_plan.filters.genre_ids == (9648,)
    assert "悬疑" in orchestrator._candidate_service.retrieval_plan.soft_signals
    assert "retrieval_plan" in orchestrator.agent_adapter.ranking_calls[0][1].profile
    assert repository.load_run_history(PROFILE_ID)[0].metrics[
        "softened_profile_media_types"
    ] == []
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
    saved_profile = repository.load_profile(PROFILE_ID)
    assert not hasattr(saved_profile, "filters")
    assert not hasattr(saved_profile, "ranking_tags")
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
            "retrieval",
            "candidate",
        "ranking",
        "save",
    ]
    assert history[0].metrics["stage_order"] == expected_stages
    observed_stages = []
    for event in progress_events:
        if not observed_stages or observed_stages[-1] != event["stage"]:
            observed_stages.append(event["stage"])
    assert observed_stages == expected_stages
    assert all(event["profile_id"] == PROFILE_ID for event in progress_events)
    assert all(event["run_id"] == "run-1" for event in progress_events)
    assert all(set(event) <= {"profile_id", "run_id", "stage", "message"} for event in progress_events)
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
            "repair_count": 1,
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
            "repair_count": 2,
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
    assert metrics["agent_repair_count"] == 3
    assert metrics["profile_repair_count"] == 1
    assert metrics["ranking_repair_count"] == 2
    assert [item["role"] for item in metrics["agent_provenance"]] == [
        "profile",
        "ranking",
    ]
    assert [item["stage"] for item in metrics["agent_provenance"]] == [
        "profile",
        "ranking",
    ]
    assert [item["attempt"] for item in metrics["agent_provenance"]] == [1, 1]
    assert all(
        item["duration_ms"] >= 0 for item in metrics["agent_provenance"]
    )
    assert all(
        item["status"] == "completed" for item in metrics["agent_provenance"]
    )
    assert all(
        item["failure_reason"] == "" for item in metrics["agent_provenance"]
    )
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
    orchestrator._candidate_service.processing_counts = {
        "recognition_input": 12,
        "candidate_recognition_cache_hit_count": 3,
        "candidate_recognition_cache_miss_count": 9,
    }
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
    assert history.metrics["candidate_recognition_cache_hit_count"] == 3
    assert history.metrics["candidate_recognition_cache_miss_count"] == 9
    assert history.metrics["candidate_processing_counts"]["recognition_input"] == 12


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
        "retrieval",
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
    assert result.status == "recommendation_degraded"
    assert result.board is None
    assert repository.load_board(PROFILE_ID) is None
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
        ],
        retrieval_outputs=[
            _retrieval_output(media_types=["movie"]),
            _retrieval_output(media_types=["anime"]),
        ],
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
    assert len(agent.retrieval_calls) == 2
    assert len(agent.ranking_calls) == 2
    assert profile.run_id == "run-profile"
    assert profile.playback_fingerprint
    assert repository.load_board(PROFILE_ID).run_id == "run-ranking-only"
    latest_metrics = repository.load_run_history(PROFILE_ID)[0].metrics
    assert latest_metrics["profile_agent_reused"] is True
    assert latest_metrics.get("profile_agent_calls", 0) == 0
    assert latest_metrics["profile_cache_status"] == "hit"
    assert latest_metrics["profile_cache_miss_reason"] == ""
    assert latest_metrics["softened_profile_media_types"] == ["anime"]
    assert candidates.retrieval_plan.filters.media_types == ()
    assert "动画" in candidates.retrieval_plan.ranking_tags
    assert agent.ranking_calls[1][1].profile["retrieval_plan"]["filters"][
        "media_types"
    ] == ()


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
    assert repository.load_profile(PROFILE_ID).schema_version == PROFILE_SCHEMA_VERSION
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["profile_cache_miss_reason"] == "profile_schema_changed"


def test_legacy_retrieval_profile_is_rebuilt_even_when_playback_matches():
    """旧版画像 schema 必须重建，检索字段不再进入稳定画像。"""
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
            schema_version=PROFILE_SCHEMA_VERSION - 1,
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
    profile = repository.load_profile(PROFILE_ID)
    assert not hasattr(profile, "filters")
    assert not hasattr(profile, "ranking_tags")
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["profile_cache_miss_reason"] == "profile_schema_changed"


def test_changed_playback_fact_triggers_one_incremental_profile_update():
    """新增播放事实只触发一次增量画像，随后相同输入再次命中缓存。"""
    class MutablePlaybackService(FakePlaybackService):
        def __init__(self):
            self.extra_sample = False

        def collect(self, profile_id, config):
            snapshot = super().collect(profile_id, config)
            if self.extra_sample:
                snapshot.samples.append(
                    PlaybackSample(
                        "tmdb:movie:6",
                        "Watched 6",
                        "movie",
                        tmdb_id="6",
                        genres=["科幻"],
                        completed=True,
                    )
                )
                snapshot.mapped_count = len(snapshot.samples)
            return snapshot

    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    playback = MutablePlaybackService()
    agent = FakeAgentAdapter(
        [
            _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
            _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
            _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
        ]
    )
    run_ids = iter(("run-initial", "run-incremental", "run-reused"))
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=FakeCandidateService(12),
        agent_adapter=agent,
        run_id_factory=lambda: next(run_ids),
        playback_service=playback,
    )

    first = asyncio.run(orchestrator.run(PROFILE_ID, _config()))
    playback.extra_sample = True
    second = asyncio.run(orchestrator.run(PROFILE_ID, _config()))
    second_metrics = repository.load_run_history(PROFILE_ID)[0].metrics
    third = asyncio.run(orchestrator.run(PROFILE_ID, _config()))
    third_metrics = repository.load_run_history(PROFILE_ID)[0].metrics

    assert [first.status, second.status, third.status] == ["success"] * 3
    assert len(agent.profile_calls) == 2
    incremental_context = agent.profile_calls[1][1]
    assert incremental_context.previous_profile["run_id"] == "run-initial"
    assert incremental_context.playback["incremental"] is True
    assert incremental_context.playback["sample_count"] == 6
    assert incremental_context.playback["full_sample_count"] == 6
    assert [
        item["stable_id"] for item in incremental_context.playback["samples"]
    ] == ["tmdb:movie:6"]
    assert second_metrics["profile_cache_miss_reason"] == "playback_changed"
    assert second_metrics["profile_incremental_sample_count"] == 1
    assert third_metrics["profile_cache_status"] == "hit"


def test_controlled_resolution_is_transient_and_exposed_to_ranking_context():
    """唯一关键词 ID 只进入本轮检索计划，不再写入稳定画像。"""
    resolver = ControlledRetrievalPlanResolver(
        keyword_searcher=lambda term: [{"id": 321, "name": "cyberpunk"}]
    )
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [_agent_output([f"tmdb:{index}" for index in range(1, 6)])],
        retrieval_outputs=[
            _retrieval_output(ranking_tags=["赛博朋克", "英文"])
        ],
        retrieval_plan_resolver=resolver,
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    profile = repository.load_profile(PROFILE_ID)
    ranking_profile = orchestrator.agent_adapter.ranking_calls[0][1].profile
    metrics = repository.load_run_history(PROFILE_ID)[0].metrics
    assert result.status == "success"
    assert not hasattr(profile, "filters")
    assert not hasattr(profile, "ranking_tags")
    assert ranking_profile["retrieval_plan"]["filters"]["keyword_ids"] == (321,)
    assert ranking_profile["retrieval_plan"]["filters"][
        "original_languages"
    ] == ("zh", "en")
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
    assert not hasattr(profile, "ranking_tags")
    assert "悬疑" not in str(ranking_context.profile["retrieval_plan"])
    assert ranking_context.profile["tags"] == ("科幻",)
    assert ranking_context.profile_preferences["archived_tags"] == ("悬疑",)


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
    assert result.status == "recommendation_degraded"


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

    assert result.status == "recommendation_degraded"
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


def test_library_items_remain_available_and_are_marked_for_agent_context():
    """已入库候选不再被硬排除，宿主改为传递状态标记。"""
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
    assert "tmdb:1" in candidate_ids
    assert "tmdb:2" in candidate_ids
    assert orchestrator._candidate_service.exclude_library_candidates is False
    assert repository.load_run_history(PROFILE_ID)[0].metrics["library_excluded_count"] == 0


def test_ranking_failure_keeps_previous_board_and_records_fallback_diagnostics():
    """排序异常保留新画像与旧榜单，补位只记录失败诊断。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(plugin, [RuntimeError("llm offline")])
    repository.save_profile(UserProfile(profile_id=PROFILE_ID, username="Alice", summary="old", run_id="old"))
    repository.save_board(RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success"))

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "recommendation_degraded"
    assert result.agent_calls == 2
    assert repository.load_profile(PROFILE_ID).run_id == "run-1"
    board = repository.load_board(PROFILE_ID)
    assert result.board.run_id == "old"
    assert board.run_id == "old"
    assert board.recommendations == []
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.status == "recommendation_degraded"
    assert history.errors
    assert history.metrics["ranking_fallback_count"] == 5
    assert history.metrics["ranking_fallback_reason"] == "ranking_agent_failed"
    assert history.metrics["agent_selected_count"] == 0
    assert history.metrics["safe_fallback_selected_count"] == 5
    analyses = repository.load_recommendation_analyses(PROFILE_ID, "run-1")
    assert analyses == []


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


def test_transient_probe_degrades_and_uses_snapshot_fallback():
    """探测瞬时失败时继续采集快照，不应误阻断本轮推荐。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)

    class TransientProbePlaybackService(FakePlaybackService):
        def __init__(self):
            """初始化快照采集计数。"""
            self.collect_calls = 0

        def probe(self, profile_id, config):
            """模拟一次可恢复的探测异常。"""
            raise TimeoutError("Playback Reporting probe timeout")

        def collect(self, profile_id, config):
            """记录并继续返回可用的播放快照。"""
            self.collect_calls += 1
            return super().collect(profile_id, config)

    playback_service = TransientProbePlaybackService()
    orchestrator = RecommendationOrchestrator(
        repository=repository,
        candidate_service=FakeCandidateService(),
        agent_adapter=FakeAgentAdapter(
            [_agent_output([f"tmdb:{index}" for index in range(1, 6)])]
        ),
        run_id_factory=lambda: "run-transient-probe",
        playback_service=playback_service,
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert playback_service.collect_calls == 1
    metrics = repository.load_run_history(PROFILE_ID)[0].metrics
    assert metrics["playback_probe_status"] == "transient_error"
    assert metrics["stage_status"]["probe"] == "degraded"


def test_retryable_empty_agent_output_retries_once_and_records_both_calls():
    """A transient no-text completion gets one bounded retry with honest metrics."""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            RetryableAgentError(
                "token=hidden https://private.invalid 192.0.2.11:8443 upstream unavailable"
            ),
            _agent_output([f"tmdb:{index}" for index in range(1, 6)]),
        ],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    assert len(orchestrator.agent_adapter.ranking_calls) == 2
    metrics = repository.load_run_history(PROFILE_ID)[0].metrics
    assert metrics["agent_calls"] == 3
    ranking_calls = [
        item for item in metrics["agent_provenance"] if item["stage"] == "ranking"
    ]
    assert [item["status"] for item in ranking_calls] == ["failed", "completed"]
    assert [item["attempt"] for item in ranking_calls] == [1, 2]
    assert "hidden" not in ranking_calls[0]["failure_reason"]
    assert "private.invalid" not in ranking_calls[0]["failure_reason"]
    assert "192.0.2.11" not in ranking_calls[0]["failure_reason"]
    assert "[已脱敏凭据]" in ranking_calls[0]["failure_reason"]


def test_retryable_empty_agent_output_keeps_previous_board_after_one_retry():
    """连续两次无文本结果后停止调用并保留旧榜单。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin,
        [RetryableAgentError("first"), RetryableAgentError("second")],
    )
    repository.save_profile(UserProfile(profile_id=PROFILE_ID, username="Alice", summary="old", run_id="old"))
    repository.save_board(RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success"))

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "recommendation_degraded"
    assert result.agent_calls == 3
    assert repository.load_profile(PROFILE_ID).run_id == "run-1"
    board = repository.load_board(PROFILE_ID)
    assert result.board.run_id == "old"
    assert board.run_id == "old"
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.errors == ["attempt 1: first", "attempt 2: second"]
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
    ranking_calls = [
        item
        for item in history.metrics["agent_provenance"]
        if item["stage"] == "ranking"
    ]
    assert [item["status"] for item in ranking_calls] == [
        "validation_failed",
        "completed",
    ]
    assert ranking_calls[0]["failure_reason"]


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


def test_invalid_json_keeps_previous_board_after_one_strict_retry():
    """连续两次非法 JSON 后停止调用并保留旧榜单。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(plugin, ["bad-one", "bad-two"])
    repository.save_board(
        RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success")
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "recommendation_degraded"
    assert result.agent_calls == 3
    board = repository.load_board(PROFILE_ID)
    assert result.board.run_id == "old"
    assert board.run_id == "old"
    history = repository.load_run_history(PROFILE_ID)[0]
    assert len(history.errors) == 2
    assert all("Agent output must be one JSON object" in item for item in history.errors)
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


def test_failed_copy_rewrite_does_not_save_template_fallback():
    """唯一重写仍是残句时记录模板补位诊断，但不保存新榜单。"""
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

    assert result.status == "recommendation_degraded"
    assert result.agent_calls == 3
    assert len(orchestrator.agent_adapter.ranking_calls) == 2
    assert result.board is None
    assert repository.load_board(PROFILE_ID) is None
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


def test_single_refill_drop_stops_without_saving_fallback_board():
    """唯一补选被安全门丢弃时不再启动第二轮，也不保存补位榜单。"""
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

    assert result.status == "recommendation_degraded"
    assert result.agent_calls == 3
    assert result.board is None
    assert repository.load_board(PROFILE_ID) is None
    assert len(orchestrator.agent_adapter.ranking_calls) == 2
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.errors == []
    assert history.metrics["refill_agent_calls"] == 1
    assert history.metrics["refill_drops"] == ["invalid_reason"]
    assert history.metrics["ranking_fallback_count"] == 1
    assert history.metrics["ranking_fallback_reason"] == "refill_insufficient"


def test_refill_still_insufficient_does_not_save_local_fallback_item():
    """唯一补选仍不足时记录一条补位诊断，但不保存新榜单。"""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            _agent_output([f"tmdb:{index}" for index in range(1, 5)]),
            _agent_output([]),
            _agent_output([]),
        ],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "recommendation_degraded"
    assert result.board is None
    assert repository.load_board(PROFILE_ID) is None
    assert result.agent_calls == 3
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.errors == []
    assert history.metrics["ranking_fallback_count"] == 1
    assert history.metrics["ranking_fallback_reason"] == "refill_insufficient"


def test_incomplete_agent_board_is_not_saved_when_no_fallback_is_available():
    """补位也不可用时，四条 Agent 推荐仍不得保存为不完整榜单。"""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            _agent_output([f"tmdb:{index}" for index in range(1, 5)]),
            _agent_output([]),
        ],
    )
    orchestrator._validator.build_fallback_items = lambda *args, **kwargs: []

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "recommendation_incomplete"
    assert result.board is None
    assert repository.load_board(PROFILE_ID) is None
    assert repository.load_recommendation_analyses(PROFILE_ID, result.run_id) == []
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["ranking_fallback_count"] == 0
    assert history.metrics["agent_selected_count"] == 4
    assert history.metrics["safe_fallback_selected_count"] == 0


def test_refill_invalid_json_stops_without_saving_fallback_board():
    """唯一补选返回非 JSON 时不再扩大模型往返，也不保存补位榜单。"""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            _agent_output([f"tmdb:{index}" for index in range(1, 5)]),
            "not-json",
            _agent_output(["tmdb:5"]),
        ],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "recommendation_degraded"
    assert result.agent_calls == 3
    assert result.board is None
    assert repository.load_board(PROFILE_ID) is None
    history = repository.load_run_history(PROFILE_ID)[0]
    assert len(history.errors) == 1
    assert "Agent output must be one JSON object" in history.errors[0]
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


def test_zero_valid_agent_items_keep_previous_board():
    """Agent 没有安全推荐时只记录补位诊断并保留旧榜单。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin,
        [_agent_output(["tmdb:404"]), _agent_output([]), _agent_output([])],
    )
    repository.save_board(RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success"))

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "recommendation_degraded"
    assert result.agent_calls == 3
    board = repository.load_board(PROFILE_ID)
    assert result.board.run_id == "old"
    assert board.run_id == "old"
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.errors == []
    assert history.metrics["ranking_fallback_count"] == 5
    assert history.metrics["ranking_fallback_reason"] == "refill_insufficient"
    assert repository.load_recommendation_analyses(PROFILE_ID, "run-1") == []


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


def test_ignore_during_run_is_rechecked_without_saving_fallback_board():
    """运行期间新增忽略在提交时生效，但不以补位覆盖旧榜单。"""
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

    assert result.status == "recommendation_degraded"
    board = repository.load_board(PROFILE_ID)
    assert result.board.run_id == "old"
    assert board.run_id == "old"
    assert board.recommendations == []
    assert [entry.candidate_id for entry in repository.load_archive(PROFILE_ID).entries] == [
        "tmdb:movie:2"
    ]
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["archive_commit_excluded_count"] == 1
    assert history.metrics["ranking_fallback_count"] == 1
    assert history.metrics["ranking_fallback_reason"] == "archive_updated_during_run"


def test_dislike_during_run_is_rechecked_without_saving_fallback_board():
    """运行期间新增点踩在提交前生效，但不保存补位榜单。"""
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

    assert result.status == "recommendation_degraded"
    assert result.board is None
    assert repository.load_board(PROFILE_ID) is None
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


def test_preliminary_partition_covers_ten_to_fifteen_candidates_once():
    """10 条分两组，11-15 条分三组，且每条候选只出现一次。"""
    expected = {
        10: ([5, 5], [3, 3]),
        11: ([4, 4, 3], [2, 2, 2]),
        12: ([4, 4, 4], [2, 2, 2]),
        13: ([5, 4, 4], [2, 2, 2]),
        14: ([5, 5, 4], [2, 2, 2]),
        15: ([5, 5, 5], [2, 2, 2]),
    }
    for count, (sizes, quotas) in expected.items():
        candidates = FakeCandidateService(count).candidates
        batches = orchestrator_module.partition_preliminary_batches(
            candidates,
            "a" * 64,
            "b" * 64,
        )
        processed_ids = [
            candidate.candidate_id
            for batch in batches
            for candidate in batch.candidates
        ]
        assert [len(batch.candidates) for batch in batches] == sizes
        assert [batch.advance_quota for batch in batches] == quotas
        assert len(processed_ids) == len(set(processed_ids)) == count
        assert set(processed_ids) == {
            candidate.candidate_id for candidate in candidates
        }


def test_judgment_cache_key_invalidates_every_judgment_input_dimension():
    """画像、候选、策略、权重或协议变化都会生成新的判断卡键。"""
    candidates = FakeCandidateService(15).candidates

    def keys(
        values,
        profile_fingerprint="profile-v1",
        retrieval_fingerprint="retrieval-v1",
        weights_fingerprint="weights-v1",
    ):
        """返回当前输入生成的三个批次幂等键。"""
        return tuple(
            batch.idempotency_key
            for batch in tournament_module.partition_preliminary_batches(
                values,
                profile_fingerprint,
                retrieval_fingerprint,
                weights_fingerprint,
            )
        )

    baseline = keys(candidates)
    changed_candidates = FakeCandidateService(15).candidates
    changed_candidates[0].title = "Changed title"
    assert keys(candidates, profile_fingerprint="profile-v2") != baseline
    assert keys(changed_candidates) != baseline
    assert keys(candidates, retrieval_fingerprint="retrieval-v2") != baseline
    assert keys(candidates, weights_fingerprint="weights-v2") != baseline

    protocol_version = tournament_module.JUDGMENT_PROTOCOL_VERSION
    try:
        tournament_module.JUDGMENT_PROTOCOL_VERSION = protocol_version + 1
        assert keys(candidates) != baseline
    finally:
        tournament_module.JUDGMENT_PROTOCOL_VERSION = protocol_version


def test_fifteen_candidate_tournament_is_parallel_and_preserves_final_order():
    """15 条并行初赛汇入六人决赛，最终 Top 5 严格保留 Agent 顺序。"""
    orchestrator, repository, _, agent = _tournament_orchestrator(FakePlugin())

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert [
        len(call[2].candidates) for call in agent.preliminary_calls
    ] == [5, 5, 5]
    assert [
        call[2].submission_constraints["advance_quota"]
        for call in agent.preliminary_calls
    ] == [2, 2, 2]
    assert agent.preliminary_max_active == 3
    final_context = agent.final_calls[0][1]
    assert len(final_context.candidates) == 6
    assert {
        (item["dimension"], item["value"], item["polarity"])
        for item in final_context.weights["evidence_catalog"]
    } >= {
        ("type", "movie", "positive"),
        ("theme", "悬疑", "positive"),
    }
    assert list(
        final_context.submission_constraints["allowed_candidate_ids"]
    ) == [item["candidate_id"] for item in final_context.candidates]
    assert all(
        len(
            final_context.submission_constraints["evidence_options"][
                item["candidate_id"]
            ]["positive_evidence_options"]
        )
        >= 2
        for item in final_context.candidates
    )
    expected_order = [
        item["candidate_id"]
        for item in reversed(final_context.candidates)
    ][:5]
    board = repository.load_board(PROFILE_ID)
    assert [item.candidate_id for item in board.recommendations] == expected_order
    assert [item.rank for item in board.recommendations] == [1, 2, 3, 4, 5]
    assert [item.fit_score for item in board.recommendations] == [80] * 5
    history = repository.load_run_history(PROFILE_ID)[0]
    assert len(history.metrics["candidate_preliminary_status"]) == 15
    assert history.metrics["preliminary_candidate_count"] == 15
    assert history.metrics["finalist_count"] == 6
    assert history.metrics["final_fit_score_count"] == 5
    assert history.metrics["final_status"] == "success"


def test_final_ranking_uses_fit_score_and_keeps_agent_order_for_ties():
    """最终榜单按匹配分降序，同分保留 Agent 顺序且不再二次微调。"""
    orchestrator, _ = _orchestrator(
        FakePlugin(),
        [_agent_output([f"tmdb:{index}" for index in range(1, 6)])],
    )
    items = [
        RecommendationItem(
            candidate_id=f"tmdb:{index}",
            rank=index,
            fit_score=fit_score,
            selection_source="agent",
        )
        for index, fit_score in enumerate((92, 84, 88, 84), start=1)
    ]

    ranked = orchestrator._rank_final_items(
        items,
        [],
        {item.candidate_id: index for index, item in enumerate(items)},
        preserve_agent_order=True,
        short_term_scores={"tmdb:2": 1.0, "tmdb:4": 1.0},
    )

    assert [item.candidate_id for item in ranked] == [
        "tmdb:1",
        "tmdb:3",
        "tmdb:2",
        "tmdb:4",
    ]
    assert [item.rank for item in ranked] == [1, 2, 3, 4]


def test_failed_batch_uses_safe_fill_then_only_that_batch_retries_next_run():
    """成功批次继续命中缓存，只有上轮失败的批次在下一轮重试。"""
    plugin = FakePlugin()
    agent = FakeTournamentAgentAdapter(
        preliminary_failures={"batch-2": [RuntimeError("batch offline")]}
    )
    run_ids = iter(("run-tournament-1", "run-tournament-2"))
    orchestrator, repository, _, _ = _tournament_orchestrator(
        plugin,
        agent=agent,
        run_id_factory=lambda: next(run_ids),
    )

    first = asyncio.run(orchestrator.run(PROFILE_ID, _config()))
    first_metrics = repository.load_run_history(PROFILE_ID)[0].metrics
    first_board = repository.load_board(PROFILE_ID)
    second = asyncio.run(orchestrator.run(PROFILE_ID, _config()))
    second_metrics = repository.load_run_history(PROFILE_ID)[0].metrics

    assert first.status == "success"
    assert first_metrics["preliminary_failed_count"] == 1
    assert first_metrics["preliminary_safe_fill_count"] == 2
    assert first_metrics["finalist_count"] == 6
    safe_fill_ids = {
        candidate_id
        for candidate_id, status in first_metrics["candidate_preliminary_status"].items()
        if status["status"] == "failed" and status["selected"]
    }
    assert safe_fill_ids & {item.candidate_id for item in first_board.recommendations}
    assert all(
        item.fit_score == 80
        for item in first_board.recommendations
        if item.candidate_id in safe_fill_ids
    )
    assert first_metrics["final_fit_score_count"] == 5
    assert second.status == "success"
    assert [call[0] for call in agent.preliminary_calls] == [
        "batch-1",
        "batch-2",
        "batch-3",
        "batch-2",
    ]
    assert second_metrics["preliminary_cache_hit_count"] == 2
    assert second_metrics["preliminary_failed_count"] == 0
    assert second_metrics["preliminary_safe_fill_count"] == 0
    assert [item["status"] for item in second_metrics["preliminary_batch_statuses"]] == [
        "cache_hit",
        "agent",
        "cache_hit",
    ]


def test_final_pool_replaces_candidates_without_two_verified_evidence_options():
    """证据不足的初赛晋级项由合格候选补席，最终排序仍交给 Agent。"""
    plugin = FakePlugin()
    orchestrator, repository, _, agent = _tournament_orchestrator(plugin)
    real_scorer = orchestrator._support_scorer

    class EvidenceGateScorer:
        """仅覆写指定候选的公开证据选项，其余确定性评分保持真实。"""

        def verified_evidence_options(self, candidate, *args):
            """让两个初赛晋级候选只暴露一项正向证据。"""
            options = real_scorer.verified_evidence_options(candidate, *args)
            if candidate.candidate_id in {"tmdb:1", "tmdb:6"}:
                options["positive_evidence_options"] = options[
                    "positive_evidence_options"
                ][:1]
            return options

        def score_candidate(self, *args, **kwargs):
            """委托真实评分器完成后续支持度校验。"""
            return real_scorer.score_candidate(*args, **kwargs)

    orchestrator._support_scorer = EvidenceGateScorer()

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    final_context = agent.final_calls[0][1]
    final_ids = [item["candidate_id"] for item in final_context.candidates]
    assert len(final_ids) == 6
    assert not {"tmdb:1", "tmdb:6"} & set(final_ids)
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["evidence_ineligible_candidate_count"] == 2
    assert history.metrics["final_evidence_fill_count"] == 2


def test_judgment_checkpoints_never_cross_profile_scope():
    """相同候选和策略在不同画像下仍分别调用初赛 Agent。"""
    other_profile_id = "emby:home:user-2"
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
    agent = FakeTournamentAgentAdapter()
    run_ids = iter(("run-profile-1", "run-profile-2"))
    orchestrator, _, _, _ = _tournament_orchestrator(
        FakePlugin(),
        agent=agent,
        run_id_factory=lambda: next(run_ids),
    )

    first = asyncio.run(orchestrator.run(PROFILE_ID, config))
    second = asyncio.run(orchestrator.run(other_profile_id, config))

    assert [first.status, second.status] == ["success", "success"]
    assert len(agent.preliminary_calls) == 6


def test_cached_judgments_keep_facts_but_refresh_finalists_against_previous_board():
    """无操作不改变候选语义，成功初赛判断可继续复用且榜单仍保持新鲜。"""
    plugin = FakePlugin()
    agent = FakeTournamentAgentAdapter()
    run_ids = iter(("run-cache-1", "run-cache-2"))
    orchestrator, repository, _, _ = _tournament_orchestrator(
        plugin,
        agent=agent,
        run_id_factory=lambda: next(run_ids),
    )

    first = asyncio.run(orchestrator.run(PROFILE_ID, _config()))
    second = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert [first.status, second.status] == ["success", "success"]
    assert len(agent.preliminary_calls) == 3
    assert len(agent.final_calls) == 2
    first_ids = {item.candidate_id for item in first.board.recommendations}
    second_ids = {item.candidate_id for item in second.board.recommendations}
    assert not first_ids & second_ids
    assert len(second_ids - first_ids) == 5
    assert agent.final_calls[0][1].candidates != agent.final_calls[1][1].candidates
    assert agent.final_calls[1][1].submission_constraints["minimum_new_items"] == 5
    histories = repository.load_run_history(PROFILE_ID)
    current_metrics = histories[0].metrics
    previous_metrics = histories[1].metrics
    assert current_metrics["judgment_card_cache_hit_count"] == 3
    assert current_metrics["final_input_source"] == "cached_judgments"
    assert current_metrics["final_input_fingerprint"] != previous_metrics["final_input_fingerprint"]
    assert current_metrics["freshness_status"] == "applied"
    assert current_metrics["freshness_minimum_new_items"] == 5
    assert "recommendation_cooldown_status" not in current_metrics
    assert current_metrics["final_agent_calls"] == 1


def test_board_recency_weight_decay_skips_the_current_board_history_entry():
    """榜单新鲜度从上一榜之后的历史轮次开始衰减。"""
    orchestrator, _, _, _ = _tournament_orchestrator(FakePlugin())
    history = [
        SimpleNamespace(
            metrics={"recommendation_candidate_ids": ["tmdb:current"]}
        ),
        SimpleNamespace(
            metrics={"recommendation_candidate_ids": ["tmdb:two-rounds"]}
        ),
        SimpleNamespace(
            metrics={"recommendation_candidate_ids": ["tmdb:three-rounds"]}
        ),
        SimpleNamespace(
            metrics={"recommendation_candidate_ids": ["tmdb:old"]}
        ),
    ]
    orchestrator._repository.load_run_history = lambda profile_id: history

    weights = orchestrator._board_recency_weights(
        PROFILE_ID, ["tmdb:current"]
    )

    assert weights == {
        "tmdb:current": 0.0,
        "tmdb:two-rounds": 0.35,
        "tmdb:three-rounds": 0.7,
        "tmdb:old": 1.0,
    }


def test_unacted_recommendations_are_not_cooled_before_final_agent_selection():
    """无操作榜单仍保留在候选池，只有上一榜单新鲜度约束继续生效。"""
    plugin = FakePlugin()
    agent = FakeTournamentAgentAdapter()
    run_ids = iter(("run-no-cooldown-1", "run-no-cooldown-2"))
    orchestrator, repository, candidate_service, _ = _tournament_orchestrator(
        plugin,
        agent=agent,
        run_id_factory=lambda: next(run_ids),
    )

    results = [
        asyncio.run(orchestrator.run(PROFILE_ID, _config()))
        for _ in range(2)
    ]

    assert [result.status for result in results] == [
        "success",
        "success",
    ]
    first_board_ids = {
        item.candidate_id for item in results[0].board.recommendations
    }
    assert first_board_ids <= set(candidate_service.collected_candidate_ids[1])
    second_context = agent.final_calls[1][1]
    assert "recent_recommendation_candidate_ids" not in second_context.submission_constraints
    latest_metrics = repository.load_run_history(PROFILE_ID)[0].metrics
    assert "recommendation_cooldown_status" not in latest_metrics


def test_final_retry_preserves_submission_error_code_field_and_candidate_map():
    """外层决赛重试必须反馈真实提交错误，不得统一伪装成校验失败。"""
    class SubmissionError(RuntimeError):
        """模拟适配器返回带稳定 code/field 的提交失败。"""

        code = "candidate_out_of_pool"
        field = "candidate_id"

    agent = FakeTournamentAgentAdapter(
        final_outputs=[SubmissionError("first"), SubmissionError("second")]
    )
    orchestrator, repository, _, _ = _tournament_orchestrator(
        FakePlugin(),
        agent=agent,
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "recommendation_degraded"
    retry_prompt = agent.final_calls[1][0]
    assert "code=candidate_out_of_pool field=candidate_id" in retry_prompt
    assert "candidate_ref_map={" in retry_prompt
    assert "code=final_validation_failed" not in retry_prompt
    history = repository.load_run_history(PROFILE_ID)[0]
    assert "candidate_out_of_pool (candidate_id)" in history.errors[0]


def test_final_rejects_missing_counter_evidence_when_counter_signal_exists():
    """决赛遗漏反证且所有晋级项均命中反证时保留旧榜。"""
    plugin = FakePlugin()
    ordered_ids = ["tmdb:12", "tmdb:11", "tmdb:7", "tmdb:6", "tmdb:2"]
    missing_counter = _agent_output_with_counter_evidence(
        ordered_ids,
        include_counter=False,
    )
    agent = FakeTournamentAgentAdapter(
        final_outputs=[missing_counter, missing_counter]
    )
    orchestrator, repository, _, _ = _tournament_orchestrator(
        plugin,
        agent=agent,
    )
    repository.save_profile_preferences(
        ProfilePreferences(
            profile_id=PROFILE_ID,
            custom_negative_tags=["中国"],
        )
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "ranking_validation_failed"
    assert result.board is None
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["final_status"] == "failed"
    assert history.metrics["ranking_fallback_count"] == 0
    assert history.metrics["validation_drops"] == [
        "missing_counter_evidence"
    ] * 10


def test_final_accepts_verified_counter_evidence_when_counter_signal_exists():
    """决赛提交可验证反证后仍保留 Agent Top 5 顺序并正常完成。"""
    plugin = FakePlugin()
    ordered_ids = ["tmdb:12", "tmdb:11", "tmdb:7", "tmdb:6", "tmdb:2"]
    agent = FakeTournamentAgentAdapter(
        final_outputs=[
            _agent_output_with_counter_evidence(
                ordered_ids,
                include_counter=True,
            )
        ]
    )
    orchestrator, repository, _, _ = _tournament_orchestrator(
        plugin,
        agent=agent,
    )
    repository.save_profile_preferences(
        ProfilePreferences(
            profile_id=PROFILE_ID,
            custom_negative_tags=["中国"],
        )
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert [item.candidate_id for item in result.board.recommendations] == ordered_ids


def test_final_validation_failure_persists_drops_without_saving_fallback():
    """决赛字段失败反馈到重试并留痕，但不保存补位榜单。"""
    finalist_ids = ["tmdb:12", "tmdb:11", "tmdb:7", "tmdb:6", "tmdb:2"]
    overlong = _agent_output_with_overrides(
        finalist_ids,
        {
            candidate_id: {"reason": "过长理由" * 8 + "。"}
            for candidate_id in finalist_ids
        },
    )
    agent = FakeTournamentAgentAdapter(final_outputs=[overlong, overlong])
    orchestrator, repository, _, _ = _tournament_orchestrator(
        FakePlugin(),
        agent=agent,
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "recommendation_degraded"
    assert len(agent.final_calls) == 2
    retry_prompt = agent.final_calls[1][0]
    assert '"candidate_id":"tmdb:12","reason":"reason_too_long"' in retry_prompt
    assert "禁止新增、替换或重排" in retry_prompt
    retry_context = agent.final_calls[1][1]
    assert list(retry_context.submission_constraints["allowed_candidate_ids"]) == [
        "tmdb:12",
        "tmdb:11",
        "tmdb:7",
        "tmdb:6",
        "tmdb:2",
    ]
    assert {
        item["candidate_id"] for item in retry_context.candidates
    } == {
        "tmdb:12",
        "tmdb:11",
        "tmdb:7",
        "tmdb:6",
        "tmdb:2",
    }
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["validation_drops"] == ["reason_too_long"] * 10
    assert history.metrics["validation_drop_details"][0] == {
        "attempt": 1,
        "candidate_id": "tmdb:12",
        "reason": "reason_too_long",
    }
    assert all("reason_too_long" in error for error in history.errors)
    assert result.board is None
    assert repository.load_board(PROFILE_ID) is None
    assert repository.load_recommendation_analyses(PROFILE_ID, result.run_id) == []


def test_final_validation_failure_does_not_save_safe_nonfinalists():
    """晋级候选被反证淘汰后只记录补位诊断，不保存非晋级候选。"""
    finalist_ids = {"tmdb:1", "tmdb:2", "tmdb:6", "tmdb:7", "tmdb:11", "tmdb:12"}
    overlong = _agent_output_with_overrides(
        ["tmdb:12", "tmdb:11", "tmdb:7", "tmdb:6", "tmdb:2"],
        {
            candidate_id: {"reason": "过长理由" * 8 + "。"}
            for candidate_id in finalist_ids
        },
    )
    agent = FakeTournamentAgentAdapter(final_outputs=[overlong, overlong])
    orchestrator, repository, candidate_service, _ = _tournament_orchestrator(
        FakePlugin(),
        agent=agent,
    )
    for candidate in candidate_service.candidates:
        candidate.regions = ["中国" if candidate.candidate_id in finalist_ids else "美国"]
    repository.save_profile_preferences(
        ProfilePreferences(
            profile_id=PROFILE_ID,
            custom_negative_tags=["中国"],
        )
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "recommendation_degraded"
    assert result.board is None
    assert repository.load_board(PROFILE_ID) is None
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["safe_fallback_selected_count"] == 5


def test_final_failure_retries_only_final_and_does_not_save_safe_board():
    """决赛连续失败只重试决赛，不重建前序阶段或保存补位榜单。"""
    agent = FakeTournamentAgentAdapter(
        final_outputs=[RuntimeError("final offline"), RuntimeError("final offline")]
    )
    orchestrator, repository, candidate_service, _ = _tournament_orchestrator(
        FakePlugin(),
        agent=agent,
    )
    collect_calls = 0
    original_collect = candidate_service.collect_and_freeze

    def counted_collect(*args, **kwargs):
        """统计候选冻结调用，验证决赛重试不回退整轮。"""
        nonlocal collect_calls
        collect_calls += 1
        return original_collect(*args, **kwargs)

    candidate_service.collect_and_freeze = counted_collect

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "recommendation_degraded"
    assert collect_calls == 1
    assert len(agent.profile_calls) == 1
    assert len(agent.preliminary_calls) == 3
    assert len(agent.final_calls) == 2
    assert result.board is None
    assert repository.load_board(PROFILE_ID) is None
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["final_retry_count"] == 1
    assert history.metrics["final_status"] == "failed"
    assert history.metrics["ranking_fallback_reason"] == "final_agent_failed"
