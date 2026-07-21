"""AgentRank discover-source adapter and candidate snapshot tests."""

import importlib
import sys
from pathlib import Path
from types import ModuleType


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_discovery_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

adapter_module = importlib.import_module(f"{PACKAGE_NAME}.adapter.discovery")
service_module = importlib.import_module(f"{PACKAGE_NAME}.service.candidate")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")

DiscoveryAdapter = adapter_module.DiscoveryAdapter
CandidateCollectionService = service_module.CandidateCollectionService
AgentRankRepository = repository_module.AgentRankRepository


class FakePlugin:
    """In-memory MoviePilot plugindata stand-in."""

    def __init__(self):
        self.data = {}

    def get_data(self, key=None):
        return self.data.get(key)

    def save_data(self, key=None, value=None):
        self.data[key] = value

    def del_data(self, key=None):
        self.data.pop(key, None)


def test_multi_source_candidates_are_deduplicated_and_frozen_before_use():
    """Shared platform IDs merge source evidence into one frozen candidate."""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "douban": lambda count: [
                {
                    "title": "Shared",
                    "type": "电影",
                    "tmdb_id": 100,
                    "douban_id": "db-100",
                    "vote_average": 8.5,
                }
            ],
            "tmdb_movies": lambda count: [
                {
                    "title": "Shared",
                    "media_type": "movie",
                    "tmdb_id": 100,
                    "poster_path": "/poster.jpg",
                },
                {"title": "Only TMDB", "media_type": "movie", "tmdb_id": 101},
            ],
        }
    )
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    service = CandidateCollectionService(adapter, repository)

    result = service.collect_and_freeze(
        profile_id="alice",
        run_id="run-1",
        enabled_sources={"douban": True, "tmdb_movies": True},
        candidate_limit=10,
    )

    assert result.status == "ready"
    assert [candidate.candidate_id for candidate in result.candidates] == [
        "tmdb:100",
        "tmdb:101",
    ]
    assert result.candidates[0].sources == ["douban", "tmdb_movies"]
    assert result.candidates[0].source_ids == {"tmdb": "100", "douban": "db-100"}
    frozen = repository.load_candidate_snapshot("run-1", "alice")
    assert [candidate.candidate_id for candidate in frozen] == ["tmdb:100", "tmdb:101"]


def test_partial_source_failure_preserves_other_candidates_and_error_evidence():
    """One failed source does not discard another source's successful rows."""
    def failed(_count):
        raise RuntimeError("network down")

    adapter = DiscoveryAdapter(
        source_fetchers={
            "douban": failed,
            "bangumi": lambda count: [
                {"title": "Anime", "media_type": "anime", "bangumi_id": 7}
            ],
        }
    )
    service = CandidateCollectionService(adapter, AgentRankRepository(FakePlugin()))

    result = service.collect_and_freeze(
        "alice", "run-2", {"douban": True, "bangumi": True}, 10
    )

    assert result.status == "ready"
    assert [candidate.candidate_id for candidate in result.candidates] == ["bangumi:7"]
    assert result.source_errors == {"douban": "network down"}


def test_source_name_never_overrides_payload_media_type():
    """Bangumi、豆瓣和 TMDB 分区都不能被硬编码成固定展示类型。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "bangumi": lambda count: [
                {"title": "Live Action", "type": "电视剧", "bangumi_id": 1}
            ],
            "douban": lambda count: [
                {"title": "Movie", "type": "电影", "douban_id": 2}
            ],
            "tmdb_tv": lambda count: [
                {"title": "Animation", "media_type": "anime", "tmdb_id": 3}
            ],
        }
    )
    service = CandidateCollectionService(adapter, AgentRankRepository(FakePlugin()))

    result = service.collect_and_freeze(
        "alice",
        "run-source-types",
        {"bangumi": True, "douban": True, "tmdb_tv": True},
        10,
    )

    assert {item.sources[0]: item.media_type for item in result.candidates} == {
        "bangumi": "tv",
        "douban": "movie",
        "tmdb_tv": "anime",
    }


def test_all_sources_empty_returns_candidate_insufficient_and_empty_snapshot():
    """No valid candidate produces an explicit pre-Agent insufficient state."""
    adapter = DiscoveryAdapter(source_fetchers={"douban": lambda count: []})
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    service = CandidateCollectionService(adapter, repository)

    result = service.collect_and_freeze("alice", "run-3", {"douban": True}, 10)

    assert result.status == "candidate_insufficient"
    assert result.candidates == []
    assert repository.load_candidate_snapshot("run-3", "alice") == []


def test_unknown_source_keys_are_ignored_without_extension_execution():
    """Unknown persisted keys cannot register or execute additional discovery sources."""
    adapter = DiscoveryAdapter(source_fetchers={})

    result = adapter.fetch({"extensions": True, "unknown": True}, 10)

    assert result.items == []
    assert result.source_errors == {}
    assert result.rejected_sources == []


def test_discovery_adapter_has_no_extension_event_or_token_fetch_path():
    """Risky extension discovery and local token forwarding are absent from source."""
    source = (PLUGIN_DIR / "adapter" / "discovery.py").read_text(encoding="utf-8")
    forbidden = {
        "DiscoverSource",
        "extra_sources",
        "API_TOKEN",
        "extension_sources_provider",
        "extension_fetcher",
    }
    assert [name for name in sorted(forbidden) if name in source] == []


def test_candidate_limit_is_applied_after_normalization_and_deduplication():
    """The frozen candidate pool never exceeds its configured safety bound."""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "tmdb_movies": lambda count: [
                {"title": f"Movie {index}", "tmdb_id": index, "media_type": "movie"}
                for index in range(1, 8)
            ]
        }
    )
    service = CandidateCollectionService(adapter, AgentRankRepository(FakePlugin()))

    result = service.collect_and_freeze(
        "alice", "run-5", {"tmdb_movies": True}, candidate_limit=3
    )

    assert len(result.candidates) == 3


def test_enabled_sources_share_the_default_global_raw_fetch_limit():
    """默认 150 条原始上限在来源间无损均分，不按来源重复放大。"""
    requested = {}

    def fetcher(name):
        def fetch(count):
            requested[name] = count
            return []

        return fetch

    adapter = DiscoveryAdapter(
        source_fetchers={name: fetcher(name) for name in ("douban", "tmdb_movies", "tmdb_tv", "bangumi")}
    )
    adapter.fetch(
        {"douban": True, "tmdb_movies": True, "tmdb_tv": True, "bangumi": True},
        50,
    )

    assert requested == {
        "douban": 38,
        "tmdb_movies": 38,
        "tmdb_tv": 37,
        "bangumi": 37,
    }
    assert sum(requested.values()) == 150


def test_candidate_limit_round_robins_sources_before_global_cutoff():
    """固定上限下各来源轮询入池，豆瓣不能再独占前排候选。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            source: lambda count, source=source: [
                {
                    "title": f"{source}-{index}",
                    "tmdb_id": f"{source}-{index}",
                    "media_type": "movie",
                }
                for index in range(4)
            ]
            for source in ("douban", "tmdb_movies", "tmdb_tv", "bangumi")
        }
    )
    service = CandidateCollectionService(adapter, AgentRankRepository(FakePlugin()))

    result = service.collect_and_freeze(
        "alice",
        "run-balanced",
        {"douban": True, "tmdb_movies": True, "tmdb_tv": True, "bangumi": True},
        candidate_limit=4,
    )

    assert [candidate.sources[0] for candidate in result.candidates] == [
        "douban",
        "tmdb_movies",
        "tmdb_tv",
        "bangumi",
    ]
    assert result.accepted_source_counts == {
        "douban": 1,
        "tmdb_movies": 1,
        "tmdb_tv": 1,
        "bangumi": 1,
    }


def test_media_recognition_gate_rebuilds_source_item_as_tmdb_candidate():
    """Source identity is retained only as trace data after TMDB recognition."""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "douban": lambda count: [
                {"title": "Source Title", "douban_id": "db-9", "type": "电影"}
            ]
        }
    )

    class MediaAdapter:
        def recognize(self, candidate):
            candidate.candidate_id = "tmdb:900"
            candidate.source_ids["tmdb"] = "900"
            candidate.title = "TMDB Title"
            candidate.poster_path = "https://image.example/poster.jpg"
            return candidate

    service = CandidateCollectionService(
        adapter, AgentRankRepository(FakePlugin()), MediaAdapter()
    )

    result = service.collect_and_freeze(
        "alice", "run-tmdb", {"douban": True}, 10
    )

    assert [candidate.candidate_id for candidate in result.candidates] == ["tmdb:900"]
    assert result.candidates[0].title == "TMDB Title"
    assert result.candidates[0].source_ids == {"douban": "db-9", "tmdb": "900"}


def test_media_recognition_gate_rejects_items_without_tmdb_identity():
    """Unrecognized source rows never enter the frozen Agent candidate pool."""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "bangumi": lambda count: [
                {"title": "Unknown Anime", "bangumi_id": 7, "media_type": "anime"}
            ]
        }
    )

    class MediaAdapter:
        def recognize(self, candidate):
            return None

    service = CandidateCollectionService(
        adapter, AgentRankRepository(FakePlugin()), MediaAdapter()
    )

    result = service.collect_and_freeze(
        "alice", "run-rejected", {"bangumi": True}, 10
    )

    assert result.status == "candidate_insufficient"
    assert result.candidates == []
    assert result.rejected_count == 1
