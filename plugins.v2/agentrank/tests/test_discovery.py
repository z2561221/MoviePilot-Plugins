"""AgentRank discover-source adapter and candidate snapshot tests."""

import importlib
import sys
import threading
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_discovery_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

adapter_module = importlib.import_module(f"{PACKAGE_NAME}.adapter.discovery")
service_module = importlib.import_module(f"{PACKAGE_NAME}.service.candidate")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
retrieval_module = importlib.import_module(f"{PACKAGE_NAME}.model.retrieval")

DiscoveryAdapter = adapter_module.DiscoveryAdapter
DiscoveryFetchResult = adapter_module.DiscoveryFetchResult
MoviePilotProvider = adapter_module.MoviePilotProvider
ProviderRequest = adapter_module.ProviderRequest
RawDiscoveredItem = adapter_module.RawDiscoveredItem
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

    assert result.status == "candidate_insufficient"
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


def test_recent_recommendations_remain_eligible_and_are_not_negative_excluded():
    """无操作的旧推荐仍可进入候选池，不被伪装成负向排除。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "tmdb_movies": lambda count: [
                {
                    "title": f"Title {index}",
                    "media_type": "movie",
                    "tmdb_id": index,
                }
                for index in range(1, 13)
            ]
        }
    )
    service = CandidateCollectionService(adapter, AgentRankRepository(FakePlugin()))

    result = service.collect_and_freeze(
        profile_id="alice",
        run_id="run-cooldown",
        enabled_sources={"tmdb_movies": True},
        candidate_limit=10,
    )

    assert result.status == "ready"
    assert [candidate.candidate_id for candidate in result.candidates] == [
        f"tmdb:movie:{index}" for index in range(1, 11)
    ]
    assert "recent_recommendation" not in result.exclusion_counts
    assert "recent_recommendation_fallback_count" not in result.processing_counts


def test_library_and_subscription_states_are_marked_without_hard_exclusion():
    """已入库、已订阅和部分观看候选继续进入冻结池并带状态标记。"""
    class LibraryAdapter:
        def candidate_ids(self, candidates):
            return {item.candidate_id for item in candidates if item.candidate_id.endswith(":1")}

    class SubscriptionAdapter:
        def candidate_ids(self):
            return {"tmdb:movie:2"}

    adapter = DiscoveryAdapter(
        source_fetchers={
            "tmdb_movies": lambda count: [
                {"title": f"State {index}", "media_type": "movie", "tmdb_id": index}
                for index in range(1, 4)
            ]
        }
    )
    service = CandidateCollectionService(
        adapter,
        AgentRankRepository(FakePlugin()),
        library_adapter=LibraryAdapter(),
        subscription_adapter=SubscriptionAdapter(),
    )
    result = service.collect_and_freeze(
        "alice",
        "run-state-markers",
        {"tmdb_movies": True},
        10,
        playback_samples=[
            {
                "stable_id": "tmdb:movie:3",
                "completed": False,
                "play_count": 1,
            }
        ],
        exclude_library_candidates=False,
    )

    assert [item.candidate_id for item in result.candidates] == [
        "tmdb:movie:1",
        "tmdb:movie:2",
        "tmdb:movie:3",
    ]
    states = {item.candidate_id: item.metadata for item in result.candidates}
    assert states["tmdb:movie:1"]["in_library"] is True
    assert states["tmdb:movie:2"]["subscribed"] is True
    assert states["tmdb:movie:3"]["watch_status"] == "partial"


def test_previous_board_candidates_remain_eligible_for_agent_freshness_ranking():
    """上一榜候选不在采集层硬排除，交给后续时近策略处理。"""
    class PagedDiscoveryAdapter(DiscoveryAdapter):
        """按页返回不同候选的分层来源适配器。"""

        def __init__(self):
            """记录分层召回页码。"""
            super().__init__()
            self.pages = []

        def fetch_layered(
            self,
            enabled_sources,
            candidate_limit,
            retrieval_plan=None,
            playback_samples=(),
            raw_limit=None,
            page=1,
        ):
            """返回当前页候选，模拟来源仍可提供后续新内容。"""
            del enabled_sources, candidate_limit, retrieval_plan, playback_samples
            self.pages.append(page)
            start = 1 if page == 1 else 11
            rows = [
                RawDiscoveredItem(
                    source="tmdb_movies",
                    mediaid_prefix="tmdb",
                    payload={
                        "title": f"Movie {index}",
                        "media_type": "movie",
                        "tmdb_id": index,
                    },
                )
                for index in range(start, start + 10)
            ]
            return DiscoveryFetchResult(
                items=rows,
                source_counts={"tmdb_movies": len(rows)},
                request_recipes=[
                    {
                        "request_id": f"tmdb_movies:page{page}",
                        "source": "tmdb_movies",
                        "layer": "exact",
                        "limit": len(rows),
                        "params": {"page": page},
                    }
                ],
                raw_limit=raw_limit or len(rows),
                layer_counts={"exact": len(rows)},
            )

    adapter = PagedDiscoveryAdapter()
    service = CandidateCollectionService(adapter, AgentRankRepository(FakePlugin()))
    result = service.collect_and_freeze(
        "alice",
        "run-previous-board-page",
        {"tmdb_movies": True},
        candidate_limit=10,
        retrieval_plan=RetrievalPlan(
            filters=RetrievalFilters(media_types=("movie",))
        ),
        previous_board_candidate_ids={
            f"tmdb:movie:{index}" for index in range(1, 6)
        },
    )

    assert result.status == "ready"
    assert [candidate.candidate_id for candidate in result.candidates] == [
        f"tmdb:movie:{index}" for index in range(1, 11)
    ]
    assert adapter.pages == [1]
    assert result.exclusion_counts["previous_board"] == 0
    assert result.processing_counts["previous_board_exclusion_count"] == 0
    assert result.processing_counts["supplement_recall_count"] == 0


def test_builtin_source_prefix_is_trusted_when_payload_uses_media_id():
    """内置来源可为不带前缀的 media_id 补上受信来源身份。"""
    candidate = CandidateCollectionService._normalize(
        RawDiscoveredItem(
            source="douban",
            mediaid_prefix="douban",
            payload={"title": "豆瓣条目", "type": "电影", "media_id": "db-1"},
        )
    )

    assert candidate.source_ids == {"douban": "db-1"}
    assert candidate.candidate_id == "douban:db-1"


def test_payload_cannot_override_a_trusted_source_prefix():
    """来源载荷不能把宿主信任的豆瓣前缀改成另一个来源。"""
    with pytest.raises(ValueError, match="mediaid_prefix mismatch"):
        CandidateCollectionService._normalize(
            RawDiscoveredItem(
                source="douban",
                mediaid_prefix="douban",
                payload={
                    "title": "伪造条目",
                    "type": "电影",
                    "media_id": "1",
                    "mediaid_prefix": "anilist",
                },
            )
        )


def test_extension_source_prefix_is_safely_normalized():
    """未知扩展来源只接受安全前缀并保留可追溯的来源身份。"""
    candidate = CandidateCollectionService._normalize(
        RawDiscoveredItem(
            source="future_source",
            payload={
                "title": "扩展来源条目",
                "media_type": "tv",
                "media_id": "abc-1",
                "media_source": "future_source",
            },
        )
    )

    assert candidate.source_ids == {"future_source": "abc-1"}
    assert candidate.candidate_id == "future_source:abc-1"


def test_extension_source_rejects_unsafe_prefix():
    """未知扩展来源不得注入路径、空白或其他不安全前缀。"""
    with pytest.raises(ValueError, match="invalid"):
        CandidateCollectionService._normalize(
            RawDiscoveredItem(
                source="future_source",
                payload={
                    "title": "不安全条目",
                    "media_type": "tv",
                    "media_id": "abc-1",
                    "media_source": "../escape",
                },
            )
        )


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

    assert result.status == "candidate_insufficient"
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


def test_candidate_target_is_clamped_to_supported_minimum():
    """Direct service callers cannot lower the frozen target below ten."""
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

    assert len(result.candidates) == 7
    assert result.status == "candidate_insufficient"
    assert result.minimum_frozen_candidates == 10


def test_enabled_sources_share_the_default_global_raw_fetch_limit():
    """默认 45 条原始上限在来源间无损均分，不按来源重复放大。"""
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
        "douban": 12,
        "tmdb_movies": 11,
        "tmdb_tv": 11,
        "bangumi": 11,
    }
    assert sum(requested.values()) == 45


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
        candidate_limit=10,
    )

    assert [candidate.sources[0] for candidate in result.candidates[:4]] == [
        "douban",
        "tmdb_movies",
        "tmdb_tv",
        "bangumi",
    ]
    assert result.accepted_source_counts == {
        "douban": 3,
        "tmdb_movies": 3,
        "tmdb_tv": 2,
        "bangumi": 2,
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

    assert result.status == "candidate_insufficient"
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


def test_same_source_identity_is_merged_before_media_recognition():
    """同一 TMDB 条目跨召回层重复出现时只执行一次媒体识别。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "tmdb_movies": lambda count: [
                {
                    "title": "Repeated Movie",
                    "media_type": "movie",
                    "tmdb_id": 77,
                    "overview": "第一来源简介",
                },
                {
                    "title": "Repeated Movie",
                    "media_type": "movie",
                    "tmdb_id": 77,
                    "poster_path": "/poster.jpg",
                },
            ]
        }
    )

    class MediaAdapter:
        """记录候选进入真实识别边界的次数。"""

        def __init__(self):
            """初始化识别调用计数。"""
            self.calls = 0

        def recognize(self, candidate):
            """返回带 MoviePilot 基础类型的标准候选。"""
            self.calls += 1
            candidate.metadata["mp_media_type"] = "电影"
            return candidate

    media_adapter = MediaAdapter()
    result = CandidateCollectionService(
        adapter,
        AgentRankRepository(FakePlugin()),
        media_adapter,
    ).collect_and_freeze(
        "alice", "run-pre-dedup", {"tmdb_movies": True}, 10
    )

    assert media_adapter.calls == 1
    assert result.processing_counts["raw"] == 2
    assert result.processing_counts["recognition_input"] == 1
    assert result.processing_counts["pre_recognition_deduplicated"] == 1
    assert result.candidates[0].overview == "第一来源简介"
    assert result.candidates[0].poster_path == "/poster.jpg"
    assert set(result.timings_ms) == {
        "recall",
        "normalize",
        "recognition",
        "filter",
        "snapshot",
    }


def test_recognition_cache_metrics_cover_all_inputs_without_persisting_temp_flag():
    """宿主缓存命中统计覆盖全部识别输入，临时标志不得进入冻结快照。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "tmdb_movies": lambda count: [
                {
                    "title": f"Cache Movie {index}",
                    "media_type": "movie",
                    "tmdb_id": index,
                }
                for index in range(1, 3)
            ]
        }
    )

    class MediaAdapter:
        """模拟一个宿主缓存命中和一个未命中。"""

        @staticmethod
        def recognize_many(candidates):
            values = list(candidates)
            for index, candidate in enumerate(values):
                candidate.metadata["mp_media_type"] = "电影"
                candidate.metadata["_recognize_cache_hit"] = index == 0
            return values

    result = CandidateCollectionService(
        adapter,
        AgentRankRepository(FakePlugin()),
        MediaAdapter(),
    ).collect_and_freeze(
        "alice", "run-cache-metrics", {"tmdb_movies": True}, 10
    )

    counts = result.processing_counts
    assert counts["recognition_input"] == 2
    assert counts["candidate_recognition_cache_hit_count"] == 1
    assert counts["candidate_recognition_cache_miss_count"] == 1
    assert (
        counts["candidate_recognition_cache_hit_count"]
        + counts["candidate_recognition_cache_miss_count"]
        == counts["recognition_input"]
    )
    assert all(
        "_recognize_cache_hit" not in candidate.metadata
        for candidate in result.candidates
    )
    assert all(
        "_recognize_cache_hit" not in candidate.metadata
        for candidate in result.snapshot.candidates
    )


def test_serial_media_adapter_failure_only_rejects_the_failed_candidate():
    """兼容适配器单条识别异常时继续冻结其余候选。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "tmdb_movies": lambda count: [
                {
                    "title": f"Movie {index}",
                    "media_type": "movie",
                    "tmdb_id": index,
                }
                for index in range(1, 3)
            ]
        }
    )

    class MediaAdapter:
        """模拟未实现批量识别的兼容适配器。"""

        @staticmethod
        def recognize(candidate):
            """让第一条候选失败并返回第二条候选。"""
            if candidate.source_ids["tmdb"] == "1":
                raise ValueError("single candidate failed")
            candidate.metadata["mp_media_type"] = "电影"
            return candidate

    result = CandidateCollectionService(
        adapter,
        AgentRankRepository(FakePlugin()),
        MediaAdapter(),
    ).collect_and_freeze("alice", "run-partial-recognition", {"tmdb_movies": True}, 10)

    assert [candidate.source_ids["tmdb"] for candidate in result.candidates] == ["2"]
    assert result.exclusion_counts["invalid_or_unrecognized"] == 1


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
    """已看、入库、订阅、点踩、归档和负向词均不得进入冻结快照。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "tmdb_movies": lambda count: [
                {
                    "title": f"Movie {index}",
                    "media_type": "movie",
                    "tmdb_id": index,
                    "overview": "包含真人秀桥段" if index == 5 else "安全剧情",
                }
                for index in range(1, 8)
            ]
        }
    )

    class LibraryAdapter:
        def __init__(self):
            self.batch_sizes = []

        def candidate_ids(self, candidates):
            values = list(candidates)
            self.batch_sizes.append(len(values))
            return {"tmdb:movie:2"}

    class SubscriptionAdapter:
        def candidate_ids(self):
            return {"tmdb:movie:3"}

    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    library_adapter = LibraryAdapter()
    service = CandidateCollectionService(
        adapter,
        repository,
        library_adapter=library_adapter,
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
        disliked_candidate_ids={"tmdb:movie:6"},
        negative_keywords=["真人秀"],
    )

    assert [item.candidate_id for item in result.candidates] == [
        "tmdb:movie:3",
        "tmdb:movie:7",
    ]
    assert result.candidates[0].metadata["subscribed"] is True
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
        "cheap_media_type": 0,
        "cheap_year": 0,
        "previous_board": 0,
        "watched_completed": 1,
        "library": 1,
            "subscribed": 0,
        "disliked": 1,
        "archived": 1,
        "negative_keyword": 1,
    }
    assert library_adapter.batch_sizes == [6]
    assert [item.candidate_id for item in repository.load_candidate_snapshot(
        "run-hard-filter", "alice"
    )] == ["tmdb:movie:3", "tmdb:movie:7"]


def test_dynamic_recall_freezes_fifteen_and_stops_recognition_by_batch():
    """默认目标十五，首批预算三十，并在第三个六条批次内提前停止。"""
    requested = []

    def fetch(count):
        requested.append(count)
        return [
            {
                "title": f"Movie {index}",
                "media_type": "movie",
                "tmdb_id": index,
            }
            for index in range(1, count + 1)
        ]

    result = CandidateCollectionService(
        DiscoveryAdapter(source_fetchers={"tmdb_movies": fetch}),
        AgentRankRepository(FakePlugin()),
    ).collect_and_freeze(
        "alice", "run-dynamic-target", {"tmdb_movies": True}, 15
    )

    assert result.status == "ready"
    assert len(result.candidates) == 15
    assert requested == [30]
    assert result.processing_counts["initial_recall_budget"] == 30
    assert result.processing_counts["recognition_batch_count"] == 3
    assert result.processing_counts["recognition_input"] == 18
    assert result.processing_counts["early_stop"] == 1


def test_exhausted_sources_allow_ten_to_fourteen_candidates_to_proceed():
    """来源耗尽后只要冻结候选达到十条便允许进入 Agent 阶段。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "tmdb_movies": lambda count: [
                {
                    "title": f"Movie {index}",
                    "media_type": "movie",
                    "tmdb_id": index,
                }
                for index in range(1, 13)
            ]
        }
    )

    result = CandidateCollectionService(
        adapter, AgentRankRepository(FakePlugin())
    ).collect_and_freeze(
        "alice", "run-minimum-ready", {"tmdb_movies": True}, 15
    )

    assert result.status == "ready"
    assert len(result.candidates) == 12
    assert result.processing_counts["recall_round_count"] == 1


def test_supplement_recall_continues_past_forty_five_until_target_is_met():
    """前四十五条均被过滤时继续分页补充，直到冻结十五条候选。"""
    class PagingAdapter:
        def __init__(self):
            self.budgets = []
            self.next_id = 1

        def fetch(self, enabled_sources, count, retrieval_plan=None, raw_limit=None):
            del enabled_sources, count, retrieval_plan
            budget = int(raw_limit)
            self.budgets.append(budget)
            rows = [
                RawDiscoveredItem(
                    source="tmdb_movies",
                    payload={
                        "title": f"Blocked {index}",
                        "media_type": "movie",
                        "tmdb_id": index,
                        "overview": (
                            "blocked-topic" if index <= 45 else "available-topic"
                        ),
                    },
                )
                for index in range(self.next_id, self.next_id + budget)
            ]
            self.next_id += budget
            return DiscoveryFetchResult(
                items=rows,
                source_counts={"tmdb_movies": budget},
                raw_limit=budget,
            )

    adapter = PagingAdapter()
    result = CandidateCollectionService(
        adapter, AgentRankRepository(FakePlugin())
    ).collect_and_freeze(
        "alice",
        "run-recall-cap",
        {"tmdb_movies": True},
        15,
        negative_keywords=["blocked-topic"],
    )

    assert result.status == "ready"
    assert adapter.budgets == [30, 10, 10, 10]
    assert result.processing_counts["raw"] == 60
    assert result.processing_counts["supplement_recall_count"] == 30
    assert result.processing_counts["recognition_input"] == 15


def test_supplement_recall_stops_after_three_rounds_without_new_ids():
    """来源持续返回同一批 ID 时以连续无新增身份熔断。"""
    class RepeatingAdapter:
        def __init__(self):
            self.budgets = []

        def fetch(self, enabled_sources, count, retrieval_plan=None, raw_limit=None):
            del enabled_sources, count, retrieval_plan
            budget = int(raw_limit)
            self.budgets.append(budget)
            return DiscoveryFetchResult(
                items=[
                    RawDiscoveredItem(
                        source="tmdb_movies",
                        payload={
                            "title": "Repeated",
                            "media_type": "movie",
                            "tmdb_id": 1,
                        },
                    )
                    for _ in range(budget)
                ],
                source_counts={"tmdb_movies": budget},
                raw_limit=budget,
            )

    adapter = RepeatingAdapter()
    result = CandidateCollectionService(
        adapter, AgentRankRepository(FakePlugin())
    ).collect_and_freeze(
        "alice", "run-recall-stalled", {"tmdb_movies": True}, 15
    )

    assert result.status == "candidate_insufficient"
    assert adapter.budgets == [30, 10, 10, 10]
    assert result.processing_counts["no_new_identity_rounds"] == 3
    assert result.processing_counts["raw"] == 60


def test_media_type_year_and_negative_keyword_filters_run_before_recognition():
    """只依赖来源字段的类型、年份和负向词过滤不得消耗识别调用。"""
    adapter = DiscoveryAdapter(
        source_fetchers={
            "tmdb_movies": lambda count: [
                {"title": "Wrong type", "media_type": "tv", "tmdb_id": 1},
                {"title": "Too old", "media_type": "movie", "tmdb_id": 2, "year": 1999},
                {
                    "title": "Blocked",
                    "media_type": "movie",
                    "tmdb_id": 3,
                    "year": 2024,
                    "overview": "skip-this",
                },
                {"title": "Accepted", "media_type": "movie", "tmdb_id": 4, "year": 2024},
            ]
        }
    )

    class MediaAdapter:
        def __init__(self):
            self.inputs = []

        def recognize_many(self, candidates):
            self.inputs.extend(candidate.candidate_id for candidate in candidates)
            return list(candidates)

    media_adapter = MediaAdapter()
    result = CandidateCollectionService(
        adapter,
        AgentRankRepository(FakePlugin()),
        media_adapter,
    ).collect_and_freeze(
        "alice",
        "run-cheap-filter",
        {"tmdb_movies": True},
        10,
        retrieval_plan=RetrievalPlan(
            filters=RetrievalFilters(media_types=("movie",), year_min=2020)
        ),
        negative_keywords=["skip-this"],
    )

    assert media_adapter.inputs == ["tmdb:movie:4"]
    assert result.exclusion_counts["cheap_media_type"] == 1
    assert result.exclusion_counts["cheap_year"] == 1
    assert result.exclusion_counts["negative_keyword"] == 1


def test_provider_requests_preserve_requested_media_type_for_filtering():
    """类型化 Provider 请求会把请求媒体类型传给候选过滤层。"""
    provider = MoviePilotProvider(
        handlers={
            "bangumi_discover": lambda request: [
                {"title": "Bangumi Anime", "bangumi_id": "bgm-1"}
            ]
        }
    )
    adapter = DiscoveryAdapter(provider=provider)

    result = adapter.fetch_requests(
        [
            ProviderRequest(
                request_id="bangumi",
                source="bangumi",
                provider="bangumi",
                mode="discover",
                method="bangumi_discover",
                media_type="anime",
                limit=1,
                params={
                    "type": 2,
                    "cat": None,
                    "sort": "rank",
                    "year": None,
                    "offset": 0,
                },
            )
        ],
        raw_limit=1,
    )

    assert result.items[0].requested_media_type == "anime"


def test_anime_filter_waits_for_recognition_when_animation_hints_exist():
    """anime 过滤可放行动画线索候选，但识别后仍拒绝真人剧集。"""

    class Adapter:
        def fetch(self, enabled_sources, count, retrieval_plan=None, raw_limit=None):
            del enabled_sources, count, retrieval_plan, raw_limit
            return DiscoveryFetchResult(
                items=[
                    RawDiscoveredItem(
                        source="tmdb_tv",
                        payload={
                            "title": "Animated Series",
                            "media_type": "tv",
                            "tmdb_id": 101,
                            "genre_ids": [16],
                        },
                        mediaid_prefix="themoviedb",
                        requested_media_type="tv",
                    ),
                    RawDiscoveredItem(
                        source="bangumi",
                        payload={"title": "Bangumi Anime", "bangumi_id": "bgm-2"},
                        mediaid_prefix="bangumi",
                        requested_media_type="anime",
                    ),
                    RawDiscoveredItem(
                        source="bangumi",
                        payload={"title": "Live Action", "bangumi_id": "bgm-3"},
                        mediaid_prefix="bangumi",
                        requested_media_type="anime",
                    ),
                    RawDiscoveredItem(
                        source="tmdb_tv",
                        payload={
                            "title": "Plain Series",
                            "media_type": "tv",
                            "tmdb_id": 104,
                            "genres": ["Drama"],
                        },
                        mediaid_prefix="themoviedb",
                        requested_media_type="tv",
                    ),
                ],
                raw_limit=4,
                source_counts={"tmdb_tv": 2, "bangumi": 2},
            )

    class MediaAdapter:
        def __init__(self):
            self.inputs = []

        def recognize_many(self, candidates):
            self.inputs.extend(candidate.title for candidate in candidates)
            recognized = []
            for candidate in candidates:
                if candidate.title == "Bangumi Anime":
                    candidate.source_ids["tmdb"] = "102"
                    candidate.media_type = "anime"
                elif candidate.title == "Live Action":
                    candidate.source_ids["tmdb"] = "103"
                    candidate.media_type = "tv"
                else:
                    candidate.media_type = "anime"
                candidate.metadata["mp_media_type"] = "电视剧"
                recognized.append(candidate)
            return recognized

    media_adapter = MediaAdapter()
    result = CandidateCollectionService(
        Adapter(),
        AgentRankRepository(FakePlugin()),
        media_adapter,
    ).collect_and_freeze(
        "alice",
        "run-anime-filter",
        {"tmdb_tv": True, "bangumi": True},
        10,
        retrieval_plan=RetrievalPlan(
            filters=RetrievalFilters(media_types=("anime",))
        ),
    )

    assert media_adapter.inputs == [
        "Animated Series",
        "Bangumi Anime",
        "Live Action",
    ]
    assert [candidate.candidate_id for candidate in result.candidates] == [
        "tmdb:tv:101",
        "tmdb:tv:102",
    ]
    assert {candidate.media_type for candidate in result.candidates} == {"anime"}
    assert all(
        "requested_media_type" not in candidate.metadata
        for candidate in result.candidates
    )
    assert result.exclusion_counts["cheap_media_type"] == 2


def test_legacy_sources_execute_concurrently_and_isolate_failures():
    """多个来源必须并发开始，且单来源失败仍保留其余候选。"""
    barrier = threading.Barrier(2)

    def successful(count):
        barrier.wait(timeout=1)
        return [{"title": "Movie", "media_type": "movie", "tmdb_id": 1}]

    def failed(count):
        barrier.wait(timeout=1)
        raise RuntimeError("network down")

    result = DiscoveryAdapter(
        source_fetchers={"douban": failed, "tmdb_movies": successful}
    ).fetch(
        {"douban": True, "tmdb_movies": True},
        count=2,
        raw_limit=2,
    )

    assert [item.source for item in result.items] == ["tmdb_movies"]
    assert result.source_errors == {"douban": "network down"}


def test_subscription_state_failure_does_not_block_candidate_snapshot():
    """全局订阅读取失败时保留候选，只记录状态读取错误。"""
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

    assert result.status == "candidate_insufficient"
    assert result.candidates
    assert result.filter_errors == {}
    assert result.source_errors["subscriptions"] == "database unavailable"
    assert repository.load_candidate_snapshot("run-filter-failed", "alice")
