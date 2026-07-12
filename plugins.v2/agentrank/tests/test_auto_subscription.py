"""AgentRank automatic top-N subscription safety and history tests."""

import asyncio
import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_auto_subscription_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
run_module = importlib.import_module(f"{PACKAGE_NAME}.model.run")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
subscription_module = importlib.import_module(f"{PACKAGE_NAME}.service.subscription")
runtime_module = importlib.import_module(f"{PACKAGE_NAME}.service.runtime")

Candidate = candidate_module.Candidate
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
RecommendationRun = run_module.RecommendationRun
AgentRankRepository = repository_module.AgentRankRepository
SubscriptionService = subscription_module.SubscriptionService
AgentRankRuntime = runtime_module.AgentRankRuntime


class FakePlugin:
    """In-memory plugindata store."""

    def __init__(self):
        self.data = {}
        self._repository = None

    def get_data(self, key=None):
        return self.data.get(key)

    def save_data(self, key=None, value=None):
        self.data[key] = value

    def del_data(self, key=None):
        self.data.pop(key, None)


class SequencedChain:
    """Return per-item exists/add results while recording continuation."""

    def __init__(self, exists_results=None, add_results=None):
        self.exists_results = list(exists_results or [])
        self.add_results = list(add_results or [])
        self.exists_calls = []
        self.add_calls = []

    def exists(self, media, meta=None):
        self.exists_calls.append(media)
        return self.exists_results.pop(0) if self.exists_results else False

    def add(self, **kwargs):
        self.add_calls.append(kwargs)
        return self.add_results.pop(0) if self.add_results else (1, "ok")


class FakeMedia:
    """Simple media stand-in."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _seed(repository, count=3):
    items = []
    candidates = []
    for index in range(1, count + 1):
        candidate_id = f"tmdb:{index}"
        items.append(
            RecommendationItem(
                candidate_id=candidate_id,
                rank=index,
                title=f"Title {index}",
                media_type="movie",
                confidence=80,
                source_ids={"tmdb": str(index)},
            )
        )
        candidates.append(
            Candidate(
                candidate_id=candidate_id,
                title=f"Title {index}",
                media_type="movie",
                source_ids={"tmdb": str(index)},
            )
        )
    repository.save_board(
        RecommendationBoard(
            username="alice",
            run_id="run-1",
            status="success",
            recommendations=items,
        )
    )
    repository.save_candidate_snapshot("run-1", "alice", candidates)


def _service(repository, chain):
    return SubscriptionService(repository, chain, FakeMedia, lambda value: value)


def test_top_n_zero_is_disabled_and_over_limit_is_rejected_without_calls():
    """Automatic subscription defaults off and cannot exceed the configured limit."""
    repository = AgentRankRepository(FakePlugin())
    _seed(repository)
    chain = SequencedChain()
    service = _service(repository, chain)

    disabled = service.subscribe_top_n("alice", 0, 3, 0.6)
    over_limit = service.subscribe_top_n("alice", 4, 3, 0.6)

    assert disabled.status == "disabled"
    assert over_limit.status == "invalid_limit"
    assert chain.exists_calls == []
    assert chain.add_calls == []


def test_batch_continues_across_created_existing_and_failed_items():
    """One item failure is recorded while later safe items continue."""
    repository = AgentRankRepository(FakePlugin())
    _seed(repository)
    chain = SequencedChain(
        exists_results=[False, True, False],
        add_results=[(101, "created"), (None, "downstream failed")],
    )
    service = _service(repository, chain)

    result = service.subscribe_top_n("alice", 3, 3, 0.6)

    assert result.status == "subscription_partial_failed"
    assert result.success_count == 2
    assert result.failure_count == 1
    assert [item.code for item in result.items] == [
        "subscription_created",
        "already_subscribed",
        "subscription_failed",
    ]
    assert len(chain.exists_calls) == 3
    assert len(chain.add_calls) == 2
    assert all(call["username"] == "alice" for call in chain.add_calls)


def test_runtime_marks_board_and_latest_history_on_partial_auto_failure():
    """Automatic partial failure is visible on the board and original run record."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    plugin._repository = repository
    _seed(repository)
    repository.append_run(
        RecommendationRun(username="alice", run_id="run-1", status="success")
    )
    chain = SequencedChain(
        exists_results=[False, False],
        add_results=[(1, "ok"), (None, "failed")],
    )
    service = _service(repository, chain)
    board = repository.load_board("alice")

    class Orchestrator:
        async def run(self, username, config):
            return SimpleNamespace(
                status="success",
                board=board,
                run_id="run-1",
                message="ok",
                final_count=3,
            )

    runtime = AgentRankRuntime(
        plugin,
        {
            "enabled": True,
            "users": ["alice"],
            "action_mode": "auto_subscribe",
            "auto_subscribe_top_n": 2,
            "auto_subscribe_limit": 3,
            "confidence_threshold": 0.6,
        },
        Orchestrator(),
        lambda cron: cron,
        subscription_service=service,
    )

    result = asyncio.run(runtime.refresh("alice"))

    assert result.status == "subscription_partial_failed"
    assert repository.load_board("alice").status == "subscription_partial_failed"
    history = repository.load_run_history("alice")[0]
    assert history.status == "subscription_partial_failed"
    assert history.metrics["subscription_failure_count"] == 1
    assert history.errors == ["tmdb:2: failed"]
