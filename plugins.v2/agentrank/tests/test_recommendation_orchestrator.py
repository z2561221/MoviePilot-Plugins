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
playback_module = importlib.import_module(f"{PACKAGE_NAME}.model.playback")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
orchestrator_module = importlib.import_module(f"{PACKAGE_NAME}.service.recommendation")
keyword_module = importlib.import_module(f"{PACKAGE_NAME}.service.keyword_resolution")

Candidate = candidate_module.Candidate
UserProfile = profile_module.UserProfile
ProfilePreferences = preferences_module.ProfilePreferences
RecommendationBoard = board_module.RecommendationBoard
PlaybackSample = playback_module.PlaybackSample
PlaybackSnapshot = playback_module.PlaybackSnapshot
PlaybackCapability = playback_module.PlaybackCapability
AgentRankRepository = repository_module.AgentRankRepository
RecommendationOrchestrator = orchestrator_module.RecommendationOrchestrator
ControlledRetrievalPlanResolver = keyword_module.ControlledRetrievalPlanResolver

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
                    completed=True,
                )
                for index in range(1, 6)
            ],
        )


class FakeCandidateService:
    """Return a deterministic frozen candidate result."""

    def __init__(self, count=12):
        self.candidates = [
            Candidate(candidate_id=f"tmdb:{index}", title=f"Title {index}", media_type="movie")
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
    ):
        self.retrieval_plan = retrieval_plan
        self.playback_samples = list(playback_samples or [])
        self.archived_candidate_ids = set(archived_candidate_ids or set())
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
                    "reason": "你持续订阅悬疑电影，这部以密室追凶和双线叙事延续相同兴趣。",
                    "summary": "悬疑迷局层层牵出尘封往事与真相",
                    "match_tags": ["悬疑电影", "双线叙事"],
                    "confidence": 80,
                }
                for candidate_id in candidate_ids
            ],
        },
        ensure_ascii=False,
    )


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
        plugin, [_agent_output([f"tmdb:{index}" for index in range(1, 11)])]
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
    assert orchestrator._candidate_service.retrieval_plan.filters.genre_ids == (80,)
    assert [item.tmdb_id for item in orchestrator._candidate_service.playback_samples] == [
        "1",
        "2",
        "3",
        "4",
        "5",
    ]
    assert len(repository.load_board(PROFILE_ID).recommendations) == 10
    assert repository.load_profile(PROFILE_ID).run_id == "run-1"
    assert repository.load_profile(PROFILE_ID).filters["genre_ids"] == [80]
    assert repository.load_profile(PROFILE_ID).ranking_tags == ["高质量悬疑"]
    history = repository.load_run_history(PROFILE_ID)
    assert history[0].status == "success"
    assert history[0].metrics["final_count"] == 10
    assert history[0].metrics["agent_calls"] == 2
    assert history[0].metrics["profile_agent_calls"] == 1
    assert history[0].metrics["ranking_agent_calls"] == 1
    expected_stages = [
        "probe",
        "playback_snapshot",
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


def test_fewer_than_twenty_frozen_candidates_skips_ranking_agent():
    """冻结候选低于默认 20 条时保留画像但不调用排序 Agent。"""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [_agent_output([f"tmdb:{index}" for index in range(1, 11)])],
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
    assert history.metrics["stage_order"] == [
        "probe",
        "playback_snapshot",
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
            _agent_output([f"tmdb:{index}" for index in range(1, 11)]),
            _agent_output([f"tmdb:{index}" for index in range(20, 30)]),
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
        [_agent_output([f"tmdb:{index}" for index in range(1, 11)])],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert len(orchestrator.agent_adapter.profile_calls) == 1
    assert repository.load_profile(PROFILE_ID).schema_version == 4


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
            schema_version=4,
            retrieval_resolution_version=0,
            run_id="old",
        )
    )
    orchestrator, _ = _orchestrator(
        plugin,
        [_agent_output([f"tmdb:{index}" for index in range(1, 11)])],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert len(orchestrator.agent_adapter.profile_calls) == 1
    assert repository.load_profile(PROFILE_ID).retrieval_resolution_version == 1


def test_controlled_resolution_is_persisted_and_exposed_to_ranking_context():
    """唯一关键词 ID 写入画像，排序上下文只看到解析后的计划。"""
    resolver = ControlledRetrievalPlanResolver(
        keyword_searcher=lambda term: [{"id": 321, "name": "cyberpunk"}]
    )
    profile_output = _profile_output(ranking_tags=["赛博朋克", "英文"])
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [_agent_output([f"tmdb:{index}" for index in range(1, 11)])],
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


def test_run_uses_configured_agent_prompt():
    """初选调用会收到当前配置中的排序提示词。"""
    plugin = FakePlugin()
    orchestrator, _ = _orchestrator(
        plugin, [_agent_output([f"tmdb:{index}" for index in range(1, 11)])]
    )
    config = _config()
    config["agent_prompt"] = "多推荐冷门科幻并保持俏皮文风"

    asyncio.run(orchestrator.run(PROFILE_ID, config))

    assert "多推荐冷门科幻并保持俏皮文风" in (
        orchestrator.agent_adapter.profile_calls[0][0]
    )


def test_cached_profile_is_passed_as_incremental_context():
    """画像缓存开启且未要求重建时，旧画像会进入只读播放上下文。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin, [_agent_output([f"tmdb:{index}" for index in range(1, 11)])]
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
        [_agent_output([f"tmdb:{index}" for index in range(1, 11)])]
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

    agent = FakeAgentAdapter([_agent_output([f"tmdb:{index}" for index in range(1, 11)])])
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
            plugin, [_agent_output([f"tmdb:{index}" for index in range(1, 11)])]
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
        assert result.status == "success"


def test_library_items_are_removed_before_agent_context_is_built():
    """已入库 TMDB 候选不会进入 Agent 可见候选快照。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)

    class LibraryAdapter:
        def exists(self, candidate):
            return candidate.candidate_id in {"tmdb:1", "tmdb:2"}

    agent = FakeAgentAdapter(
        [_agent_output([f"tmdb:{index}" for index in range(3, 13)])]
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


def test_ranking_failure_keeps_generated_profile_and_previous_board():
    """排序异常不回滚独立画像，也不覆盖旧榜单。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(plugin, [RuntimeError("llm offline")])
    repository.save_profile(UserProfile(profile_id=PROFILE_ID, username="Alice", summary="old", run_id="old"))
    repository.save_board(RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success"))

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "ranking_agent_failed"
    assert repository.load_profile(PROFILE_ID).run_id == "run-1"
    assert repository.load_board(PROFILE_ID).run_id == "old"
    assert repository.load_run_history(PROFILE_ID)[0].status == "ranking_agent_failed"


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
            _agent_output([f"tmdb:{index}" for index in range(1, 11)]),
        ],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    assert len(orchestrator.agent_adapter.ranking_calls) == 2
    assert repository.load_run_history(PROFILE_ID)[0].metrics["agent_calls"] == 3


def test_retryable_empty_agent_output_fails_after_one_retry():
    """Two no-text completions preserve old data and stop after two calls."""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin,
        [RetryableAgentError("first"), RetryableAgentError("second")],
    )
    repository.save_profile(UserProfile(profile_id=PROFILE_ID, username="Alice", summary="old", run_id="old"))
    repository.save_board(RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success"))

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "ranking_agent_failed"
    assert result.agent_calls == 3
    assert repository.load_profile(PROFILE_ID).run_id == "run-1"
    assert repository.load_board(PROFILE_ID).run_id == "old"
    assert repository.load_run_history(PROFILE_ID)[0].metrics["agent_calls"] == 3


def test_invalid_json_retries_once_with_stricter_prompt():
    """Invalid JSON is rejected, then one strict retry may succeed."""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            "not-json",
            _agent_output([f"tmdb:{index}" for index in range(1, 11)]),
        ],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    assert "上一次输出未通过严格校验" in orchestrator.agent_adapter.ranking_calls[1][0]
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["agent_calls"] == 3
    assert history.errors[0].startswith("attempt 1:")


def test_invalid_json_fails_after_one_strict_retry():
    """Two invalid JSON outputs cannot replace the previous board."""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(plugin, ["bad-one", "bad-two"])
    repository.save_board(
        RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success")
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "ranking_validation_failed"
    assert result.agent_calls == 3
    assert repository.load_board(PROFILE_ID).run_id == "old"
    history = repository.load_run_history(PROFILE_ID)[0]
    assert history.metrics["agent_calls"] == 3
    assert len(history.errors) == 2


def test_partial_valid_output_gets_exactly_one_successful_refill():
    """Eight accepted items trigger one refill for the two remaining slots."""
    first = _agent_output([f"tmdb:{index}" for index in range(1, 9)])
    refill = _agent_output(["tmdb:9", "tmdb:10"])
    orchestrator, repository = _orchestrator(FakePlugin(), [first, refill])

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "success"
    assert result.agent_calls == 3
    assert len(repository.load_board(PROFILE_ID).recommendations) == 10
    assert "tmdb:1" in orchestrator.agent_adapter.ranking_calls[1][0]
    assert "排除" in orchestrator.agent_adapter.ranking_calls[1][0]


def test_refill_still_insufficient_saves_actual_count_and_incomplete_state():
    """One refill is final; remaining shortage is visible rather than padded."""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            _agent_output([f"tmdb:{index}" for index in range(1, 9)]),
            _agent_output(["tmdb:9"]),
        ],
    )

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "recommendation_incomplete"
    board = repository.load_board(PROFILE_ID)
    assert board.status == "recommendation_incomplete"
    assert len(board.recommendations) == 9
    assert result.agent_calls == 3


def test_zero_valid_items_preserves_old_board_and_records_validation_failure():
    """A wholly unsafe Agent result cannot replace the previous board."""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(plugin, [_agent_output(["tmdb:404"])])
    repository.save_board(RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success"))

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "ranking_validation_failed"
    assert repository.load_board(PROFILE_ID).run_id == "old"


def test_board_save_failure_keeps_new_profile_and_previous_board():
    """排序榜单写入失败不回滚已经独立保存的画像。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin, [_agent_output([f"tmdb:{index}" for index in range(1, 11)])]
    )
    repository.save_profile(UserProfile(profile_id=PROFILE_ID, username="Alice", summary="old", run_id="old"))
    repository.save_board(RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success"))
    plugin.fail_board_save = True

    result = asyncio.run(orchestrator.run(PROFILE_ID, _config()))

    assert result.status == "ranking_save_failed"
    assert repository.load_profile(PROFILE_ID).run_id == "run-1"
    assert repository.load_board(PROFILE_ID).run_id == "old"


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
        agent = BlockingAgent([_agent_output([f"tmdb:{index}" for index in range(1, 11)])])
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
                _agent_output([f"tmdb:{index}" for index in range(1, 11)]),
                _agent_output([f"tmdb:{index}" for index in range(1, 11)]),
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
