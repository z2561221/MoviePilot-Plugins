"""验证结构调整的并发、缓存资源与生命周期边界。"""

import gc
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from app.plugins.agentrank import AgentRank
from app.plugins.agentrank.service.board_history import BoardHistoryService
from app.plugins.agentrank.service.lifecycle import stop_plugin
from app.plugins.agentrank.storage.feedback_projection import FeedbackPolarityCache
from app.plugins.agentrank.storage.locks import RepositoryLocks
from app.plugins.agentrank.storage.repository import AgentRankRepository
from tests.v3.agentrank.test_performance import (
    PROFILE,
    MemoryPlugin,
    append_feedback,
    seed_history,
)


@pytest.mark.parametrize(
    "kind", ["feedback", "board_archive", "telegram_pending", "telegram_retry"]
)
def test_lock_shares_only_with_same_memory_store(kind):
    plugin = MemoryPlugin()
    same_store = AgentRankRepository(plugin)
    different_store = MemoryPlugin()._repository
    first = plugin._repository._locks.lock(kind, "same-profile")
    assert same_store._locks.lock(kind, "same-profile") is first
    assert different_store._locks.lock(kind, "same-profile") is not first
    assert same_store._locks.lock(kind, "other-profile") is not first


def test_native_sdk_instances_share_by_persisted_plugin_id():
    # __new__ 避免调用宿主构造器；这里只检查已核验的原生数据作用域。
    plugin = AgentRank.__new__(AgentRank)
    reloaded = AgentRank.__new__(AgentRank)
    clone_class = type("AgentRankIndependentClone", (AgentRank,), {})
    clone = clone_class.__new__(clone_class)
    first = AgentRankRepository(plugin)._feedback_lock(PROFILE)
    assert AgentRankRepository(reloaded)._feedback_lock(PROFILE) is first
    assert AgentRankRepository(clone)._feedback_lock(PROFILE) is not first


def test_unhashable_data_owner_is_supported_without_merging_namespaces():
    one = SimpleNamespace(get_data=lambda key=None: None)
    two = SimpleNamespace(get_data=lambda key=None: None)
    first = RepositoryLocks(one).lock("feedback", "profile")
    assert RepositoryLocks(one).lock("feedback", "profile") is first
    assert RepositoryLocks(two).lock("feedback", "profile") is not first


def test_ten_thousand_temporary_profiles_leave_no_registry_growth():
    repository = MemoryPlugin()._repository
    gc.collect()
    before = RepositoryLocks.live_lock_count()
    for number in range(10000):
        repository._feedback_lock(f"temporary-{number}")
    gc.collect()
    assert RepositoryLocks.live_lock_count() == before


def test_waiter_keeps_same_lock_after_holder_releases_and_gc_runs():
    plugin = MemoryPlugin()
    one = plugin._repository
    two = AgentRankRepository(plugin)
    obtained = threading.Event()
    enter = threading.Event()
    lock = one._feedback_lock(PROFILE)
    lock.acquire()
    identity = id(lock)

    def waiter():
        waiting_lock = two._feedback_lock(PROFILE)
        obtained.set()
        assert enter.wait(3)
        with waiting_lock:
            return id(waiting_lock)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(waiter)
        assert obtained.wait(3)
        lock.release()
        del lock
        gc.collect()
        replacement = one._feedback_lock(PROFILE)
        assert id(replacement) == identity
        enter.set()
        assert future.result(timeout=3) == identity


def test_feedback_action_keeps_board_then_profile_lock_order():
    repository = MemoryPlugin()._repository
    calls = []

    class Guard:
        def __init__(self, name):
            self.name = name

        def __enter__(self):
            calls.append(("enter", self.name))

        def __exit__(self, *args):
            calls.append(("exit", self.name))

    repository._locks = SimpleNamespace(lock=lambda kind, scope="": Guard(kind))
    with repository.feedback_action_guard(PROFILE):
        pass
    assert calls == [
        ("enter", "board_archive"),
        ("enter", "feedback"),
        ("exit", "feedback"),
        ("exit", "board_archive"),
    ]


def test_eight_runs_share_one_index_and_interleaved_updates_remain_visible():
    plugin = MemoryPlugin()
    repository = plugin._repository
    for number in range(8):
        append_feedback(repository, number, run_id=f"run-{number}")
        assert repository.load_feedback_polarities(PROFILE, f"run-{number}") == {
            "tmdb:movie:1": "like"
        }
    assert len(repository._feedback_projection) == 8
    assert repository._feedback_projection.retained_ledger_count == 1
    append_feedback(repository, 8, "neutral", run_id="run-1")
    repository.load_feedback_polarities(PROFILE, "run-0")
    plugin.reads.clear()
    assert repository.load_feedback_polarities(PROFILE, "run-1") == {}
    assert sum(plugin.reads.values()) == 1
    assert repository._feedback_projection.retained_ledger_count == 1


def test_lru_removes_indices_for_evicted_profiles():
    plugin = MemoryPlugin()
    for number in range(20):
        plugin._repository.load_feedback_polarities(f"profile-{number}", "current")
    cache = plugin._repository._feedback_projection
    assert len(cache) == 8
    assert cache.retained_ledger_count == 8


def test_stop_releases_cache_and_keeps_persisted_reads_available():
    plugin = MemoryPlugin()
    append_feedback(plugin._repository, 1)
    assert plugin._repository.load_feedback_polarities(PROFILE, "current")
    cache = plugin._repository._feedback_projection
    stop_plugin(plugin)
    stop_plugin(plugin)
    assert len(cache) == 0
    assert cache.retained_ledger_count == 0
    assert plugin._repository.load_feedback_polarities(PROFILE, "current") == {
        "tmdb:movie:1": "like"
    }
    assert len(cache) == 0
    assert len(plugin._repository.load_feedback_events(PROFILE)) == 1


def test_closing_cache_during_read_blocks_late_cache_publication():
    plugin = MemoryPlugin()
    append_feedback(plugin._repository, 1)
    index = plugin._repository._load_feedback_index(PROFILE)
    events = plugin._repository.load_feedback_events(PROFILE)
    cache = FeedbackPolarityCache()
    reading = threading.Event()
    finish = threading.Event()

    def loader(cursor):
        reading.set()
        assert finish.wait(3)
        return events

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(cache.project, PROFILE, "current", index, loader)
        assert reading.wait(3)
        cache.close()
        finish.set()
        assert future.result(timeout=3) == {"tmdb:movie:1": "like"}
    assert len(cache) == 0
    assert cache.retained_ledger_count == 0


def test_history_service_has_same_cross_page_summary_without_serializing_boards():
    plugin = MemoryPlugin()
    seed_history(plugin, 50)
    page = BoardHistoryService(plugin._repository).page(PROFILE, page=2, page_size=10)
    assert page.total == 50
    assert len(page.items) == 10
    assert page.items[0].board.run_id == "run-10"
    assert page.items[0].new_count == 1
    assert page.items[0].overlap_count == 4
    assert page.items[0].recent_average_overlap_rate == 0.8
    assert page.items[0].history_state("tmdb:movie:11") == "new"
    assert (
        plugin.reads[plugin._repository._learning_key("board_consumption", PROFILE)]
        == 1
    )
