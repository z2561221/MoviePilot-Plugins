"""短期信号重试保持原始时间、真实冲突和画像内并发幂等。"""

import copy
import importlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest


PACKAGE_NAME = "app.plugins.agentrank"
feedback_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
ShortTermSignal = feedback_module.ShortTermSignal
AgentRankRepository = repository_module.AgentRankRepository
PROFILE_ID = "emby:home:user-1"
FIRST_OBSERVED_AT = "2026-11-15T18:03:35+00:00"
RETRY_OBSERVED_AT = "2026-11-15T18:27:00+00:00"


class FakePlugin:
    """模拟宿主按值保存，并记录实际写入次数。"""

    def __init__(self):
        self.data = {}
        self.saves = []

    def get_data(self, key=None):
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        self.data[key] = copy.deepcopy(value)
        self.saves.append(key)


def _signal(kind="detail_opened", **changes):
    signal = ShortTermSignal(
        profile_id=PROFILE_ID,
        kind=kind,
        idempotency_key="same-business-event",
        candidate_id="" if kind == "rotation" else "tmdb:tv:100",
        run_id="run-1",
        board_revision=3,
        strength=0.3,
        decay_days=30,
        observed_at=FIRST_OBSERVED_AT,
        source="agentrank_detail",
    )
    return replace(signal, **changes)


@pytest.mark.parametrize("kind", sorted(feedback_module.SHORT_TERM_SIGNAL_KINDS))
def test_same_intent_retry_preserves_first_time_and_does_not_write(kind):
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    first, created = repository.append_short_term_signal(_signal(kind))
    before = copy.deepcopy(plugin.data)

    replayed, replay_created = repository.append_short_term_signal(
        _signal(kind, observed_at=RETRY_OBSERVED_AT)
    )

    assert created is True
    assert replay_created is False
    assert replayed == first
    assert replayed.observed_at == FIRST_OBSERVED_AT
    assert replayed.decayed_strength(RETRY_OBSERVED_AT) == first.decayed_strength(
        RETRY_OBSERVED_AT
    )
    assert plugin.data == before
    assert len(plugin.saves) == 1
    assert repository.load_short_term_signals(PROFILE_ID) == [first]


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "like"},
        {"candidate_id": "tmdb:tv:101"},
        {"run_id": "run-2"},
        {"board_revision": 4},
        {"strength": 0.8},
        {"decay_days": 90},
        {"source": "different_source"},
        {"metadata": {"reason": "different_intent"}},
    ],
    ids=["kind", "candidate", "run", "revision", "strength", "decay", "source", "metadata"],
)
def test_same_key_with_changed_business_payload_still_conflicts(changes):
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    first, _ = repository.append_short_term_signal(_signal())
    before = copy.deepcopy(plugin.data)

    with pytest.raises(ValueError, match="short-term signal idempotency conflict"):
        repository.append_short_term_signal(
            _signal(observed_at=RETRY_OBSERVED_AT, **changes)
        )

    assert plugin.data == before
    assert len(plugin.saves) == 1
    assert repository.load_short_term_signals(PROFILE_ID) == [first]


def test_concurrent_different_time_retries_share_one_persisted_signal():
    plugin = FakePlugin()
    repositories = [AgentRankRepository(plugin) for _ in range(4)]
    started = datetime(2026, 11, 15, 18, 3, 35, tzinfo=timezone.utc)

    def append(index):
        return repositories[index % len(repositories)].append_short_term_signal(
            _signal(observed_at=(started + timedelta(seconds=index)).isoformat())
        )

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(append, range(48)))

    persisted = repositories[0].load_short_term_signals(PROFILE_ID)
    assert len(persisted) == 1
    assert sum(created for _, created in results) == 1
    assert all(signal == persisted[0] for signal, _ in results)
    assert len(plugin.saves) == 1


def test_identical_key_is_scoped_to_each_profile():
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    first, first_created = repository.append_short_term_signal(_signal())
    other, other_created = repository.append_short_term_signal(
        _signal(profile_id="emby:home:user-2", observed_at=RETRY_OBSERVED_AT)
    )

    assert first_created is True and other_created is True
    assert repository.load_short_term_signals(PROFILE_ID) == [first]
    assert repository.load_short_term_signals(other.profile_id) == [other]
    assert len(plugin.saves) == 2
