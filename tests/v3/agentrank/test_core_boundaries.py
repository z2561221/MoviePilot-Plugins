"""Exercise the new phase and storage boundaries without external services."""

import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from app.plugins.agentrank.model.telegram_retry import TelegramRetrySession
from app.plugins.agentrank.service.recommendation_input import RecommendationRunContext
from app.plugins.agentrank.storage.data import PluginDataStore
from app.plugins.agentrank.storage.locks import RepositoryLocks
from app.plugins.agentrank.storage.telegram import TelegramSessionStore
from tests.v3.agentrank import test_recommendation_orchestrator as helpers


class TracePlugin:
    """Record writes and expose a single recoverable storage failure."""

    def __init__(self):
        self.data = {"one": {"old": 1}, "two": {"old": 2}}
        self.writes = []
        self.fail_once = ""

    def get_data(self, key=None):
        return copy.deepcopy(self.data if key is None else self.data.get(key))

    def save_data(self, key=None, value=None):
        self.writes.append(("save", key))
        if key == self.fail_once:
            self.fail_once = ""
            raise RuntimeError("injected storage failure")
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        self.writes.append(("delete", key))
        self.data.pop(key, None)


def test_shared_data_facility_restores_each_touched_key_in_reverse_order():
    plugin = TracePlugin()
    data = PluginDataStore(plugin, "recovery")
    plugin.fail_once = "two"
    with pytest.raises(RuntimeError, match="injected storage failure"):
        data.atomic_update(
            updates={"one": {"new": 1}, "two": {"new": 2}},
            delete_keys=["absent"],
            recovery_key="transaction",
            action="failed",
        )
    assert plugin.data["one"] == {"old": 1}
    assert plugin.data["two"] == {"old": 2}
    assert plugin.writes == [
        ("save", "one"),
        ("save", "two"),
        ("delete", "absent"),
        ("save", "two"),
        ("save", "one"),
        ("save", "recovery"),
    ]
    assert plugin.data["recovery"][0]["action"] == "failed"


def test_leaf_retry_store_uses_shared_data_namespace_for_compare_and_set():
    plugin = TracePlugin()
    one = TelegramSessionStore(
        PluginDataStore(plugin, "recovery"), RepositoryLocks(plugin)
    )
    two = TelegramSessionStore(
        PluginDataStore(plugin, "recovery"), RepositoryLocks(plugin)
    )
    session = TelegramRetrySession(
        token="token123",
        profile_id="profile",
        username="User",
        telegram_userid="42",
        run_id="run",
        message="retry",
        created_at="2026-11-16T00:00:00+08:00",
        expires_at="2050-01-01T00:00:00+00:00",
    )
    assert one.save_telegram_retry_session(session)
    submitted = replace(session, status="submitted", attempt=1)

    def compare_and_set(store):
        return store.save_telegram_retry_session(
            submitted, expected_status="open", expected_attempt=0
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(compare_and_set, [one, two]))
    assert sorted(results) == [False, True]
    assert two.load_telegram_retry_session(session.token).status == "submitted"


def test_input_phase_returns_the_original_snapshot_and_shared_run_diagnostics():
    plugin = helpers.FakePlugin()
    orchestrator, repository = helpers._orchestrator(plugin, [])

    class Playback(helpers.FakePlaybackService):
        def collect(self, profile_id, config):
            self.last_snapshot = super().collect(profile_id, config)
            return self.last_snapshot

    playback = Playback()
    orchestrator._playback_service = playback
    metrics = {"agent_calls": 0, "_profile_id": helpers.PROFILE_ID, "_run_id": "run-1"}
    errors = []
    context = RecommendationRunContext(
        helpers.PROFILE_ID,
        "Alice",
        "run-1",
        "2026-11-16T00:00:00+08:00",
        0.0,
        metrics,
        errors,
    )
    inputs = asyncio.run(orchestrator._run_input_stage(context, helpers._config()))
    assert inputs.playback_snapshot is playback.last_snapshot
    assert context.metrics is metrics
    assert context.errors is errors
    assert metrics["agent_calls"] == 1
    assert metrics["stage_order"] == ["probe", "playback_snapshot", "policy", "profile"]
    assert (
        inputs.current_profile.to_dict()
        == repository.load_profile(helpers.PROFILE_ID).to_dict()
    )
    assert not orchestrator.agent_adapter.ranking_calls
