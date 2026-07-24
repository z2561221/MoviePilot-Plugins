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
retrieval_module = importlib.import_module(f"{PACKAGE_NAME}.model.retrieval")

DiscoveryAdapter = adapter_module.DiscoveryAdapter
CandidateCollectionService = service_module.CandidateCollectionService
AgentRankRepository = repository_module.AgentRankRepository
RetrievalFilters = retrieval_module.RetrievalFilters
RetrievalPlan = retrieval_module.RetrievalPlan


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
        "tmdb:movie:100",
        "tmdb:movie:101",
    ]
    assert result.candidates[0].sources == ["douban", "tmdb_movies"]
    assert result.candidates[0].source_ids == {"tmdb": "100", "douban": "db-100"}
    frozen = repository.load_candidate_snapshot("run-1", "alice")
    assert [candidate.candidate_id for candidate in frozen] == [
        "tmdb:movie:100",
        "tmdb:movie:101",
    ]


def test_partial_source_failure_preserves_other_candidates_and_error_evidence():
    """One failed source does not discard another source's successful rows."""
    def failed(_count):
        raise RuntimeError("network down")

    adapter = DiscoveryAdapter(
        source_fetchers={
            "douban": failed,
            "bangumi": lambda count: [
                {
                    "title": "Anime",
                    "media_type": "tv",
                    "tmdb_id": 7,
                    "bangumi_id": 7,
                }
            ],
        }
    )
    service = CandidateCollectionService(adapter, AgentRankRepository(FakePlugin()))

    result = service.collect_and_freeze(
        "alice", "run-2", {"douban": True, "bangumi": True}, 10
    )

    assert result.status == "ready"
    assert [candidate.candidate_id for candidate in result.candidates] == [
        "tmdb:tv:7"
    ]
    assert result.source_errors == {"douban": "network down"}


def test_source_name_never_overrides_payload_media_type():
    """Bangumi、豆瓣和 TMDB 分区都不能被硬编码成固定展示类型。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "bangumi": lambda count: [
                {
                    "title": "Live Action",
                    "type": "电视剧",
                    "tmdb_id": 1,
                    "bangumi_id": 1,
                }
            ],
            "douban": lambda count: [
                {
                    "title": "Movie",
                    "type": "电影",
                    "tmdb_id": 2,
                    "douban_id": 2,
                }
            ],
            "tmdb_tv": lambda count: [
                {"title": "Series", "tmdb_id": 3}
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
        "tmdb_tv": "tv",
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
                    "tmdb_id": 1000 * (
                        ("douban", "tmdb_movies", "tmdb_tv", "bangumi").index(source)
                        + 1
                    )
                    + index
                    + 1,
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


def test_layered_recall_preserves_source_round_robin_order():
    """分层结果进入候选池时仍先轮询来源，单一来源不能抢占前排。"""
    source_order = ("douban", "tmdb_movies", "tmdb_tv", "bangumi")
    adapter = DiscoveryAdapter(
        source_fetchers={
            source: lambda count, source=source: [
                {
                    "title": f"{source}-{index}",
                    "tmdb_id": 1000 * (source_order.index(source) + 1) + index + 1,
                    "media_type": "movie",
                }
                for index in range(count)
            ]
            for source in source_order
        }
    )
    service = CandidateCollectionService(adapter, AgentRankRepository(FakePlugin()))
    plan = RetrievalPlan(
        filters=RetrievalFilters(media_types=("movie",), genre_ids=(878,))
    )

    result = service.collect_and_freeze(
        "alice",
        "run-layered-balanced",
        {source: True for source in source_order},
        candidate_limit=50,
        retrieval_plan=plan,
    )

    assert [candidate.sources[0] for candidate in result.candidates[:4]] == list(
        source_order
    )
    assert {recipe["layer"] for recipe in result.request_recipes} >= {
        "exact",
        "relaxed",
        "adjacent",
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

    assert [candidate.candidate_id for candidate in result.candidates] == [
        "tmdb:movie:900"
    ]
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


def test_anilist_candidate_is_recognized_to_typed_tmdb_identity():
    """AniList 原生 ID 经 MoviePilot 识别后进入统一 TMDB 动漫候选池。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "anilist": lambda count: [
                {"title": "AniList 动画", "anilist_id": 321}
            ]
        }
    )

    class MediaAdapter:
        def recognize(self, candidate):
            assert candidate.media_type == "anime"
            assert candidate.source_ids == {"anilist": "321"}
            candidate.source_ids["tmdb"] = "654"
            candidate.metadata["mp_media_type"] = "电视剧"
            candidate.candidate_id = "tmdb:tv:654"
            return candidate

    result = CandidateCollectionService(
        adapter,
        AgentRankRepository(FakePlugin()),
        MediaAdapter(),
    ).collect_and_freeze(
        "alice", "run-anilist", {"anilist": True}, 10
    )

    assert result.status == "ready"
    assert result.candidates[0].candidate_id == "tmdb:tv:654"
    assert result.candidates[0].source_ids == {"anilist": "321", "tmdb": "654"}


def test_movie_and_tv_with_same_tmdb_number_do_not_collide():
    """相同数字 TMDB ID 的电影和剧集必须保留为两个候选。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "tmdb_movies": lambda count: [
                {"title": "Shared Number Movie", "media_type": "movie", "tmdb_id": 42}
            ],
            "tmdb_tv": lambda count: [
                {"title": "Shared Number TV", "media_type": "tv", "tmdb_id": 42}
            ],
        }
    )
    result = CandidateCollectionService(
        adapter, AgentRankRepository(FakePlugin())
    ).collect_and_freeze(
        "alice",
        "run-type-safe",
        {"tmdb_movies": True, "tmdb_tv": True},
        10,
    )

    assert [item.candidate_id for item in result.candidates] == [
        "tmdb:movie:42",
        "tmdb:tv:42",
    ]


def test_same_title_with_different_tmdb_ids_is_never_merged():
    """标题相同但 TMDB 身份不同的作品不得使用标题兜底合并。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "tmdb_movies": lambda count: [
                {"title": "The Same Title", "media_type": "movie", "tmdb_id": 51},
                {"title": "The Same Title", "media_type": "movie", "tmdb_id": 52},
            ]
        }
    )
    result = CandidateCollectionService(
        adapter, AgentRankRepository(FakePlugin())
    ).collect_and_freeze(
        "alice", "run-no-title-dedup", {"tmdb_movies": True}, 10
    )

    assert [item.candidate_id for item in result.candidates] == [
        "tmdb:movie:51",
        "tmdb:movie:52",
    ]


def test_hard_filters_run_after_deduplication_and_before_snapshot():
    """已看、入库、订阅、归档和负向词候选均不得进入冻结快照。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "tmdb_movies": lambda count: [
                {
                    "title": f"Movie {index}",
                    "media_type": "movie",
                    "tmdb_id": index,
                    "overview": "包含真人秀桥段" if index == 5 else "安全剧情",
                }
                for index in range(1, 7)
            ]
        }
    )

    class LibraryAdapter:
        def exists(self, candidate):
            return candidate.candidate_id == "tmdb:movie:2"

    class SubscriptionAdapter:
        def candidate_ids(self):
            return {"tmdb:movie:3"}

    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    service = CandidateCollectionService(
        adapter,
        repository,
        library_adapter=LibraryAdapter(),
        subscription_adapter=SubscriptionAdapter(),
    )

    result = service.collect_and_freeze(
        "alice",
        "run-hard-filter",
        {"tmdb_movies": True},
        50,
        playback_samples=[
            {
                "stable_id": "tmdb:movie:1",
                "tmdb_id": "1",
                "media_type": "movie",
                "completed": True,
            }
        ],
        archived_candidate_ids={"tmdb:movie:4"},
        negative_keywords=["真人秀"],
    )

    assert [item.candidate_id for item in result.candidates] == ["tmdb:movie:6"]
    assert result.snapshot is not None
    assert result.snapshot.content_hash
    assert result.snapshot.to_dict() == plugin.data[
        "candidate_snapshot:profile:alice:run:run-hard-filter"
    ]
    assert [item.to_dict() for item in result.candidates] == [
        item.to_dict() for item in result.snapshot.candidates
    ]
    assert result.exclusion_counts == {
        "invalid_or_unrecognized": 0,
        "watched_completed": 1,
        "library": 1,
        "subscribed": 1,
        "archived": 1,
        "negative_keyword": 1,
    }
    assert [item.candidate_id for item in repository.load_candidate_snapshot(
        "run-hard-filter", "alice"
    )] == ["tmdb:movie:6"]


def test_subscription_filter_failure_stops_before_snapshot():
    """全局订阅无法读取时必须闭锁候选池，不能带风险继续排序。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "tmdb_movies": lambda count: [
                {"title": "Movie", "media_type": "movie", "tmdb_id": 70}
            ]
        }
    )

    class BrokenSubscriptionAdapter:
        def candidate_ids(self):
            raise RuntimeError("database unavailable")

    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    result = CandidateCollectionService(
        adapter,
        repository,
        subscription_adapter=BrokenSubscriptionAdapter(),
    ).collect_and_freeze(
        "alice", "run-filter-failed", {"tmdb_movies": True}, 10
    )

    assert result.status == "candidate_filter_failed"
    assert result.candidates == []
    assert result.filter_errors == {"subscriptions": "database unavailable"}
    assert repository.load_candidate_snapshot("run-filter-failed", "alice") == []
