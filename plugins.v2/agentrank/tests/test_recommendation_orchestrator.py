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
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
subscription_module = importlib.import_module(f"{PACKAGE_NAME}.model.subscription")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
orchestrator_module = importlib.import_module(f"{PACKAGE_NAME}.service.recommendation")

Candidate = candidate_module.Candidate
UserProfile = profile_module.UserProfile
RecommendationBoard = board_module.RecommendationBoard
SubscriptionSample = subscription_module.SubscriptionSample
ProfileInputResult = subscription_module.ProfileInputResult
AgentRankRepository = repository_module.AgentRankRepository
RecommendationOrchestrator = orchestrator_module.RecommendationOrchestrator


class FakePlugin:
    """In-memory plugindata store with one-shot board-save failure."""

    def __init__(self):
        self.data = {}
        self.fail_board_save = False

    def get_data(self, key=None):
        return self.data.get(key)

    def save_data(self, key=None, value=None):
        if self.fail_board_save and key == "recommendation_board:alice":
            self.fail_board_save = False
            raise RuntimeError("board save failed")
        self.data[key] = value

    def del_data(self, key=None):
        self.data.pop(key, None)


class FakeProfileService:
    """Return a deterministic ready profile input."""

    def collect(self, username, **kwargs):
        return ProfileInputResult(
            username=username,
            status="ready",
            minimum_samples=1,
            samples=[
                SubscriptionSample(
                    stable_id="tmdb:999", title="Subscribed", media_type="movie"
                )
            ],
        )


class FakeCandidateService:
    """Return a deterministic frozen candidate result."""

    def __init__(self, count=12):
        self.candidates = [
            Candidate(candidate_id=f"tmdb:{index}", title=f"Title {index}", media_type="movie")
            for index in range(1, count + 1)
        ]

    def collect_and_freeze(self, username, run_id, enabled_sources, candidate_limit):
        return SimpleNamespace(
            username=username,
            run_id=run_id,
            status="ready",
            candidates=self.candidates[:candidate_limit],
            source_errors={},
            rejected_sources=[],
            rejected_count=0,
        )


class FakeAgentAdapter:
    """Return queued outputs or raise a queued exception."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    async def run(self, prompt, trusted_context):
        self.calls.append((prompt, trusted_context))
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


class RetryableAgentError(RuntimeError):
    """Represent a transient Agent completion without final text."""

    retryable = True


def _agent_output(candidate_ids):
    return json.dumps(
        {
            "profile": {
                "summary": "偏好高质量悬疑电影",
                "tags": ["悬疑"],
                "negative_tags": [],
                "subscription_count": 1,
            },
            "recommendations": [
                {
                    "candidate_id": candidate_id,
                    "reason": "这部正好戳中你的笑点",
                    "summary": "悬疑迷局牵出旧日真相",
                    "match_tags": ["悬疑"],
                    "confidence": 80,
                }
                for candidate_id in candidate_ids
            ],
        },
        ensure_ascii=False,
    )


def _orchestrator(plugin, outputs, candidate_count=12):
    repository = AgentRankRepository(plugin)
    return (
        RecommendationOrchestrator(
            repository=repository,
            profile_service=FakeProfileService(),
            candidate_service=FakeCandidateService(candidate_count),
            agent_adapter=FakeAgentAdapter(outputs),
            run_id_factory=lambda: "run-1",
        ),
        repository,
    )


def _config():
    return {
        "profile_scope": "all",
        "subscription_sample_limit": 200,
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

    result = asyncio.run(orchestrator.run("alice", _config()))

    assert result.status == "success"
    assert len(repository.load_board("alice").recommendations) == 10
    assert repository.load_profile("alice").run_id == "run-1"
    history = repository.load_run_history("alice")
    assert history[0].status == "success"
    assert history[0].metrics["final_count"] == 10
    assert history[0].metrics["agent_calls"] == 1


def test_run_uses_configured_agent_prompt():
    """初选调用会收到当前配置中的排序提示词。"""
    plugin = FakePlugin()
    orchestrator, _ = _orchestrator(
        plugin, [_agent_output([f"tmdb:{index}" for index in range(1, 11)])]
    )
    config = _config()
    config["agent_prompt"] = "多推荐冷门科幻并保持俏皮文风"

    asyncio.run(orchestrator.run("alice", config))

    assert "多推荐冷门科幻并保持俏皮文风" in orchestrator.agent_adapter.calls[0][0]


def test_cached_profile_is_passed_as_incremental_context():
    """画像缓存开启且未要求重建时，旧画像会进入只读订阅上下文。"""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin, [_agent_output([f"tmdb:{index}" for index in range(1, 11)])]
    )
    repository.save_profile(
        UserProfile(username="alice", summary="old", tags=["悬疑"], run_id="old")
    )

    result = asyncio.run(orchestrator.run("alice", _config()))

    context = orchestrator.agent_adapter.calls[0][1]
    assert context.previous_profile["summary"] == "old"
    assert context.previous_profile["tags"] == ("悬疑",)
    assert "禁止简单做标签并集" in orchestrator.agent_adapter.calls[0][0]
    history = repository.load_run_history("alice")[0]
    assert history.metrics["profile_mode"] == "incremental"
    assert history.metrics["previous_profile_used"] is True
    assert result.status == "success"


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
            UserProfile(username="alice", summary="old", run_id="old")
        )
        config = _config()
        config.update(overrides)

        result = asyncio.run(orchestrator.run("alice", config))

        assert orchestrator.agent_adapter.calls[0][1].previous_profile is None
        history = repository.load_run_history("alice")[0]
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
        profile_service=FakeProfileService(),
        candidate_service=FakeCandidateService(12),
        agent_adapter=agent,
        run_id_factory=lambda: "run-library",
        library_adapter=LibraryAdapter(),
    )

    result = asyncio.run(orchestrator.run("alice", _config()))

    assert result.status == "success"
    candidate_ids = {
        item["candidate_id"]
        for item in agent.calls[0][1].candidates
    }
    assert "tmdb:1" not in candidate_ids
    assert "tmdb:2" not in candidate_ids
    assert repository.load_run_history("alice")[0].metrics["library_excluded_count"] == 2


def test_agent_failure_preserves_previous_profile_and_board():
    """An Agent exception records agent_failed without replacing old state."""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(plugin, [RuntimeError("llm offline")])
    repository.save_profile(UserProfile(username="alice", summary="old", run_id="old"))
    repository.save_board(RecommendationBoard(username="alice", run_id="old", status="success"))

    result = asyncio.run(orchestrator.run("alice", _config()))

    assert result.status == "agent_failed"
    assert repository.load_profile("alice").run_id == "old"
    assert repository.load_board("alice").run_id == "old"
    assert repository.load_run_history("alice")[0].status == "agent_failed"


def test_retryable_empty_agent_output_retries_once_and_records_both_calls():
    """A transient no-text completion gets one bounded retry with honest metrics."""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            RetryableAgentError("no text"),
            _agent_output([f"tmdb:{index}" for index in range(1, 11)]),
        ],
    )

    result = asyncio.run(orchestrator.run("alice", _config()))

    assert result.status == "success"
    assert result.agent_calls == 2
    assert len(orchestrator.agent_adapter.calls) == 2
    assert repository.load_run_history("alice")[0].metrics["agent_calls"] == 2


def test_retryable_empty_agent_output_fails_after_one_retry():
    """Two no-text completions preserve old data and stop after two calls."""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin,
        [RetryableAgentError("first"), RetryableAgentError("second")],
    )
    repository.save_profile(UserProfile(username="alice", summary="old", run_id="old"))
    repository.save_board(RecommendationBoard(username="alice", run_id="old", status="success"))

    result = asyncio.run(orchestrator.run("alice", _config()))

    assert result.status == "agent_failed"
    assert result.agent_calls == 2
    assert repository.load_profile("alice").run_id == "old"
    assert repository.load_board("alice").run_id == "old"
    assert repository.load_run_history("alice")[0].metrics["agent_calls"] == 2


def test_invalid_json_retries_once_with_stricter_prompt():
    """Invalid JSON is rejected, then one strict retry may succeed."""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            "not-json",
            _agent_output([f"tmdb:{index}" for index in range(1, 11)]),
        ],
    )

    result = asyncio.run(orchestrator.run("alice", _config()))

    assert result.status == "success"
    assert result.agent_calls == 2
    assert "上一次输出未通过严格校验" in orchestrator.agent_adapter.calls[1][0]
    history = repository.load_run_history("alice")[0]
    assert history.metrics["agent_calls"] == 2
    assert history.errors[0].startswith("attempt 1:")


def test_invalid_json_fails_after_one_strict_retry():
    """Two invalid JSON outputs cannot replace the previous board."""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(plugin, ["bad-one", "bad-two"])
    repository.save_board(
        RecommendationBoard(username="alice", run_id="old", status="success")
    )

    result = asyncio.run(orchestrator.run("alice", _config()))

    assert result.status == "validation_failed"
    assert result.agent_calls == 2
    assert repository.load_board("alice").run_id == "old"
    history = repository.load_run_history("alice")[0]
    assert history.metrics["agent_calls"] == 2
    assert len(history.errors) == 2


def test_partial_valid_output_gets_exactly_one_successful_refill():
    """Eight accepted items trigger one refill for the two remaining slots."""
    first = _agent_output([f"tmdb:{index}" for index in range(1, 9)])
    refill = _agent_output(["tmdb:9", "tmdb:10"])
    orchestrator, repository = _orchestrator(FakePlugin(), [first, refill])

    result = asyncio.run(orchestrator.run("alice", _config()))

    assert result.status == "success"
    assert result.agent_calls == 2
    assert len(repository.load_board("alice").recommendations) == 10
    assert "tmdb:1" in orchestrator.agent_adapter.calls[1][0]
    assert "排除" in orchestrator.agent_adapter.calls[1][0]


def test_refill_still_insufficient_saves_actual_count_and_incomplete_state():
    """One refill is final; remaining shortage is visible rather than padded."""
    orchestrator, repository = _orchestrator(
        FakePlugin(),
        [
            _agent_output([f"tmdb:{index}" for index in range(1, 9)]),
            _agent_output(["tmdb:9"]),
        ],
    )

    result = asyncio.run(orchestrator.run("alice", _config()))

    assert result.status == "recommendation_incomplete"
    board = repository.load_board("alice")
    assert board.status == "recommendation_incomplete"
    assert len(board.recommendations) == 9
    assert result.agent_calls == 2


def test_zero_valid_items_preserves_old_board_and_records_validation_failure():
    """A wholly unsafe Agent result cannot replace the previous board."""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(plugin, [_agent_output(["tmdb:404"])])
    repository.save_board(RecommendationBoard(username="alice", run_id="old", status="success"))

    result = asyncio.run(orchestrator.run("alice", _config()))

    assert result.status == "validation_failed"
    assert repository.load_board("alice").run_id == "old"


def test_atomic_save_failure_restores_both_previous_objects():
    """A board write failure rolls the already-written profile back to its old value."""
    plugin = FakePlugin()
    orchestrator, repository = _orchestrator(
        plugin, [_agent_output([f"tmdb:{index}" for index in range(1, 11)])]
    )
    repository.save_profile(UserProfile(username="alice", summary="old", run_id="old"))
    repository.save_board(RecommendationBoard(username="alice", run_id="old", status="success"))
    plugin.fail_board_save = True

    result = asyncio.run(orchestrator.run("alice", _config()))

    assert result.status == "validation_failed"
    assert repository.load_profile("alice").run_id == "old"
    assert repository.load_board("alice").run_id == "old"


def test_concurrent_refresh_returns_running_without_second_agent_call():
    """The same username cannot start two recommendation runs concurrently."""
    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingAgent(FakeAgentAdapter):
        async def run(self, prompt, trusted_context):
            self.calls.append((prompt, trusted_context))
            entered.set()
            await release.wait()
            return self.outputs.pop(0)

    async def scenario():
        plugin = FakePlugin()
        repository = AgentRankRepository(plugin)
        agent = BlockingAgent([_agent_output([f"tmdb:{index}" for index in range(1, 11)])])
        orchestrator = RecommendationOrchestrator(
            repository,
            FakeProfileService(),
            FakeCandidateService(),
            agent,
            run_id_factory=lambda: "run-lock",
        )
        first_task = asyncio.create_task(orchestrator.run("alice", _config()))
        await entered.wait()
        second = await orchestrator.run("alice", _config())
        release.set()
        first = await first_task
        return first, second, agent

    first, second, agent = asyncio.run(scenario())

    assert first.status == "success"
    assert second.status == "running"
    assert len(agent.calls) == 1
