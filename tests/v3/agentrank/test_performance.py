"""性能回归验证真实调用数量、分页语义与缓存更新，不连接外部服务。"""

import copy
import importlib
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from app.plugins.agentrank.adapter.playback_reporting import PlaybackReportingAdapter
from app.plugins.agentrank.controller.api import AgentRankApiController
from app.plugins.agentrank.model.board import RecommendationBoard, RecommendationItem
from app.plugins.agentrank.model.feedback import BoardConsumption, FeedbackEvent
from app.plugins.agentrank.model.identity import EmbyIdentity
from app.plugins.agentrank.storage.repository import AgentRankRepository

IDENTITY = EmbyIdentity("review", "user-1", "Review")
PROFILE = IDENTITY.profile_id


class MemoryPlugin:
    """保留实际仓库逻辑，记录插件持久化读取次数。"""

    def __init__(self, *, history_limit=200):
        self.data = {}
        self.reads = Counter()
        self._config = {
            "emby_identities": [IDENTITY.to_dict()],
            "default_profile_id": PROFILE,
            "agent_display_name": "Review",
        }
        self._repository = AgentRankRepository(self, history_limit=history_limit)

    def get_state(self):
        return True

    def get_data(self, key=None):
        self.reads[key] += 1
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        self.data.pop(key, None)


class DetailAccess:
    """返回批量详情，并记录缺项补查及并发峰值。"""

    def __init__(self, details, barrier=None):
        self.details = details
        self.batch_ids = []
        self.lookups = []
        self.active = 0
        self.peak = 0
        self.lock = threading.Lock()
        self.barrier = barrier

    def request(self):
        return self

    def get_res(self, _url, params):
        ids = params["Ids"].split(",")
        self.batch_ids.append(ids)
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"Items": [copy.deepcopy(self.details[key]) for key in ids if key in self.details]},
        )

    def synced_item(self, _server, item_id):
        with self.lock:
            self.lookups.append(item_id)
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            if self.barrier:
                self.barrier.wait(timeout=5)
            return {"tmdbid": item_id, "title": "Recovered"}
        finally:
            with self.lock:
                self.active -= 1


def fetch_details(access, ids):
    return PlaybackReportingAdapter(access)._fetch_details(
        "review", "https://invalid.example/", "fixture", "user-1", ids
    )


def test_complete_playback_batch_deduplicates_ids_and_makes_no_item_queries():
    details = {
        str(i): {"Id": str(i), "Name": "Complete", "ProviderIds": {"Tmdb": str(i)}}
        for i in range(1, 501)
    }
    access = DetailAccess(details)
    result = fetch_details(access, ["1"] * 100 + list(details))
    assert len(result) == 500
    assert len(access.batch_ids) == 1
    assert len(access.batch_ids[0]) == 500
    assert access.lookups == []


def test_playback_backfill_preserves_complete_values_and_library_scope():
    access = DetailAccess({
        "1": {"Id": "1", "Name": "Keep", "ProviderIds": {"Imdb": "tt1"}},
        "2": {"Id": "2", "ProviderIds": {"Tmdb": "keep-id"}},
        "3": {"Id": "3", "Name": "Episode", "ProviderIds": {"Tmdb": "3"}, "SeriesId": "4"},
        "4": {"Id": "4", "Name": "Parent", "ProviderIds": {"Tmdb": "4"}},
    })
    result = fetch_details(access, ["1", "2", "3", "outside-library"])
    assert set(access.lookups) == {"1", "2"}
    assert "outside-library" not in result
    assert result["1"]["Name"] == "Keep"
    assert result["1"]["ProviderIds"] == {"Imdb": "tt1", "Tmdb": "1"}
    assert result["2"]["ProviderIds"]["Tmdb"] == "keep-id"
    assert result["2"]["Name"] == "Recovered"
    assert result["4"]["Name"] == "Parent"


def test_playback_missing_parent_is_backfilled_and_concurrency_is_bounded():
    details = {str(i): {"Id": str(i)} for i in range(1, 9)}
    access = DetailAccess(details, barrier=threading.Barrier(4))
    result = fetch_details(access, list(details))
    assert access.peak == 4
    assert len(access.lookups) == 8
    assert all(item["Name"] == "Recovered" for item in result.values())
    parent_access = DetailAccess({
        "episode": {"Id": "episode", "Name": "Episode", "ProviderIds": {"Tmdb": "1"}, "SeriesId": "parent"},
        "parent": {"Id": "parent", "Name": "Series"},
    })
    result = fetch_details(parent_access, ["episode"])
    assert parent_access.lookups == ["parent"]
    assert result["parent"]["ProviderIds"]["Tmdb"] == "parent"


def test_light_options_skip_discovery_and_playback_but_preserve_config():
    plugin = MemoryPlugin()
    calls = []
    plugin._emby_access = SimpleNamespace(
        enumerate_identities=lambda: calls.append("users") or [IDENTITY],
        enumerate_libraries=lambda _identity: calls.append("libraries") or [],
    )
    controller = AgentRankApiController(plugin)
    data = controller.endpoint_config_options(discover=False)
    assert calls == []
    assert data["config"] == plugin._config
    assert data["emby_identities"] == [IDENTITY.to_dict()]
    assert data["playback_status"] == {}
    controller.config_options()
    assert calls == ["users", "libraries"]


def seed_history(plugin, count):
    repo = plugin._repository
    boards = [RecommendationBoard(
        profile_id=PROFILE, run_id=f"run-{i}",
        recommendations=[RecommendationItem(candidate_id=f"tmdb:movie:{i+j+1}", rank=j+1) for j in range(5)],
    ) for i in range(count)]
    plugin.data[repo._board_history_key(PROFILE)] = [board.to_dict() for board in boards]
    plugin.data[repo._learning_key("board_consumption", PROFILE)] = [
        BoardConsumption(PROFILE, board.run_id, 1).to_dict() for board in boards
    ]
    return boards


@pytest.mark.parametrize("count", [50, 200])
def test_history_reads_consumption_once_and_serializes_only_requested_page(count):
    plugin = MemoryPlugin()
    seed_history(plugin, count)
    serialized = []
    controller = AgentRankApiController(plugin)
    original = controller._board_snapshot_data
    controller._board_snapshot_data = lambda board: serialized.append(board.run_id) or original(board)
    result = controller.board_history(PROFILE, page=2, page_size=10)["data"]
    assert result["total"] == count
    assert serialized == [f"run-{i}" for i in range(10, 20)]
    assert plugin.reads[plugin._repository._learning_key("board_consumption", PROFILE)] == 1
    assert result["items"][0]["new_count"] == 1
    assert result["items"][0]["overlap_count"] == 4
    assert result["items"][0]["recent_average_overlap_rate"] == 0.8
    assert result["items"][0]["return_count"] == 0
    assert [item["history_state"] for item in result["items"][0]["board"]["recommendations"]] == ["new", "repeat", "repeat", "repeat", "repeat"]


def test_history_previous_run_and_returning_items_cross_page_boundaries():
    plugin = MemoryPlugin()
    boards = seed_history(plugin, 4)
    boards[0].previous_run_id = "run-2"
    boards[0].recommendations = [RecommendationItem("tmdb:movie:2", 1), RecommendationItem("tmdb:movie:4", 2)]
    plugin.data[plugin._repository._board_history_key(PROFILE)] = [board.to_dict() for board in boards]
    controller = AgentRankApiController(plugin)
    first = controller.board_history(PROFILE, page_size=1)["data"]
    assert first["items"][0]["return_count"] == 1
    assert first["items"][0]["previous_overlap_rate"] == 0.5
    last = controller.board_history(PROFILE, page=4, page_size=1)["data"]["items"][0]
    assert last["new_count"] == 5
    assert last["recent_average_overlap_rate"] == 0
    plugin.reads.clear()
    assert controller.board_history(PROFILE, page=100)["data"]["items"] == []
    assert plugin.reads[plugin._repository._learning_key("board_consumption", PROFILE)] == 0


def append_feedback(repo, number, kind="like", run_id="current"):
    return repo.append_feedback_event(FeedbackEvent(
        profile_id=PROFILE, kind=kind, candidate_id="tmdb:movie:1",
        run_id=run_id, idempotency_key=f"key-{number}",
    ))


def test_feedback_cache_observes_other_repository_writes_and_only_reads_new_segment():
    plugin = MemoryPlugin()
    reader = plugin._repository
    writer = AgentRankRepository(plugin, feedback_segment_size=2)
    for number in range(1, 7):
        append_feedback(writer, number, run_id="old" if number < 6 else "current")
    assert reader.load_feedback_polarities(PROFILE, "current") == {"tmdb:movie:1": "like"}
    plugin.reads.clear()
    result = reader.load_feedback_polarities(PROFILE, "current")
    assert sum(plugin.reads.values()) == 1
    result.clear()
    assert reader.load_feedback_polarities(PROFILE, "current")
    append_feedback(writer, 7, "neutral")
    plugin.reads.clear()
    assert reader.load_feedback_polarities(PROFILE, "current") == {}
    assert plugin.reads[reader._feedback_segment_key(PROFILE, 4)] == 1
    assert not any(plugin.reads[reader._feedback_segment_key(PROFILE, i)] for i in range(1, 4))
    append_feedback(writer, 8, "dislike")
    assert reader.load_feedback_polarities(PROFILE, "current") == {"tmdb:movie:1": "dislike"}


def test_feedback_cache_rebuilds_after_retention_reset_and_raw_restore():
    plugin = MemoryPlugin()
    repo = plugin._repository
    append_feedback(repo, 1)
    before = copy.deepcopy(plugin.data)
    assert repo.load_feedback_polarities(PROFILE, "current")
    append_feedback(repo, 2, run_id="other")
    repo.prune_feedback_events(PROFILE, 1)
    assert repo.load_feedback_polarities(PROFILE, "current") == {}
    plugin.data = before
    assert repo.load_feedback_polarities(PROFILE, "current") == {"tmdb:movie:1": "like"}
    repo.reset_learning_data(PROFILE)
    assert repo.load_feedback_polarities(PROFILE, "current") == {}
    append_feedback(repo, 3, "dislike")
    assert repo.load_feedback_polarities(PROFILE, "current") == {"tmdb:movie:1": "dislike"}


def test_feedback_cache_is_instance_scoped_bounded_and_thread_safe():
    plugin = MemoryPlugin()
    append_feedback(plugin._repository, 1)
    other = MemoryPlugin()
    append_feedback(other._repository, 2, "dislike")
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: plugin._repository.load_feedback_polarities(PROFILE, "current"), range(20)))
    assert all(value == {"tmdb:movie:1": "like"} for value in results)
    assert other._repository.load_feedback_polarities(PROFILE, "current") == {"tmdb:movie:1": "dislike"}
    for number in range(20):
        plugin._repository.load_feedback_polarities(PROFILE, f"run-{number}")
    assert len(plugin._repository._polarity_cache) == 8


def test_feedback_cache_rechecks_segments_after_deadline_and_recovers_without_poisoning(monkeypatch):
    plugin = MemoryPlugin()
    repo = plugin._repository
    clock = [0.0]
    repository_module = importlib.import_module("app.plugins.agentrank.storage.repository")
    monkeypatch.setattr(
        repository_module, "time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    append_feedback(repo, 1)
    assert repo.load_feedback_polarities(PROFILE, "current") == {"tmdb:movie:1": "like"}
    clock[0] = 50.0
    append_feedback(repo, 2, run_id="other")
    assert repo.load_feedback_polarities(PROFILE, "current") == {"tmdb:movie:1": "like"}
    segment_key = repo._feedback_segment_key(PROFILE, 1)
    valid_segment = copy.deepcopy(plugin.data[segment_key])
    plugin.data[segment_key] = None
    clock[0] = 61.0
    assert repo.load_feedback_polarities(PROFILE, "current") == {}
    plugin.data[segment_key] = valid_segment
    assert repo.load_feedback_polarities(PROFILE, "current") == {"tmdb:movie:1": "like"}
