"""MoviePilot recommendation/discovery provider contract tests."""

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_discovery_provider_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

adapter_module = importlib.import_module(f"{PACKAGE_NAME}.adapter.discovery")
retrieval_module = importlib.import_module(f"{PACKAGE_NAME}.model.retrieval")

DiscoveryAdapter = adapter_module.DiscoveryAdapter
MoviePilotProvider = adapter_module.MoviePilotProvider
ProviderRequest = adapter_module.ProviderRequest
RetrievalFilters = retrieval_module.RetrievalFilters
RetrievalPlan = retrieval_module.RetrievalPlan


def _tmdb_request(**overrides):
    """构造一个有效 TMDB 探索请求并允许覆盖单个字段。"""
    values = {
        "request_id": "tmdb_movies",
        "source": "tmdb_movies",
        "provider": "tmdb",
        "mode": "discover",
        "method": "tmdb_discover",
        "media_type": "movie",
        "limit": 20,
        "params": {
            "sort_by": "popularity.desc",
            "with_genres": "878|9648",
            "with_original_language": "ja",
            "with_keywords": "123",
            "with_watch_providers": "",
            "vote_average": 7.5,
            "vote_count": 100,
            "release_date": "2000-01-01",
            "page": 1,
        },
    }
    values.update(overrides)
    return ProviderRequest(**values)


def test_provider_request_rejects_unknown_keys_enums_ids_and_ranges():
    """不在方法白名单内的键和值无法构造 ProviderRequest。"""
    invalid_params = []
    base = dict(_tmdb_request().params)
    invalid_params.append({**base, "free_text": "悬疑"})
    invalid_params.append({**base, "sort_by": "unknown.desc"})
    invalid_params.append({**base, "with_genres": "999999"})
    invalid_params.append({**base, "with_keywords": "1;drop"})
    invalid_params.append({**base, "with_original_language": "xx"})
    invalid_params.append({**base, "with_watch_providers": "secret"})
    invalid_params.append({**base, "vote_average": 11})
    invalid_params.append({**base, "vote_count": -1})
    invalid_params.append({**base, "release_date": "1800-01-01"})
    invalid_params.append({**base, "page": 11})

    for params in invalid_params:
        with pytest.raises(ValueError):
            _tmdb_request(params=params)

    with pytest.raises(ValueError):
        _tmdb_request(method="unknown")
    with pytest.raises(ValueError):
        _tmdb_request(provider="douban")
    with pytest.raises(ValueError):
        _tmdb_request(limit=151)


def test_typed_retrieval_plan_builds_only_whitelisted_tmdb_recipe():
    """检索计划只生成 TmdbChain 支持的白名单参数。"""
    calls = []

    def handler(request):
        calls.append(request)
        return [{"title": "One", "tmdb_id": 1, "media_type": "movie"}]

    plan = RetrievalPlan(
        filters=RetrievalFilters(
            media_types=("movie",),
            genre_ids=(878, 9648),
            keyword_ids=(123,),
            original_languages=("ja",),
            year_min=2000,
            rating_min=7.5,
            vote_count_min=100,
            sort_by="vote_average.desc",
        ),
        ranking_tags=("自由语义不得进入请求",),
    )
    adapter = DiscoveryAdapter(
        provider=MoviePilotProvider({"tmdb_discover": handler})
    )

    result = adapter.fetch(
        {"tmdb_movies": True, "tmdb_tv": True, "douban": False},
        count=50,
        retrieval_plan=plan,
    )

    assert len(calls) == 1
    assert dict(calls[0].params) == {
        "sort_by": "vote_average.desc",
        "with_genres": "878|9648",
        "with_original_language": "ja",
        "with_keywords": "123",
        "with_watch_providers": "",
        "vote_average": 7.5,
        "vote_count": 100,
        "release_date": "2000-01-01",
        "page": 1,
    }
    assert "自由语义不得进入请求" not in str(result.request_recipes)
    assert result.request_recipes[0]["method"] == "tmdb_discover"
    assert result.items[0].source == "tmdb_movies"


def test_provider_failures_are_isolated_and_all_recipes_are_recorded():
    """一个请求失败不污染其他来源，失败请求仍保留 recipe 证据。"""
    def handler(request):
        if request.media_type == "movie":
            raise RuntimeError("movie source offline")
        return [{"title": "TV", "tmdb_id": 2, "media_type": "tv"}]

    adapter = DiscoveryAdapter(
        provider=MoviePilotProvider({"tmdb_discover": handler})
    )
    movie = _tmdb_request()
    tv = _tmdb_request(
        request_id="tmdb_tv",
        source="tmdb_tv",
        media_type="tv",
    )

    result = adapter.fetch_requests([movie, tv], raw_limit=40)

    assert result.source_errors == {"tmdb_movies": "movie source offline"}
    assert [item.source for item in result.items] == ["tmdb_tv"]
    assert [item["request_id"] for item in result.request_recipes] == [
        "tmdb_movies",
        "tmdb_tv",
    ]


def test_fetch_requests_enforces_one_global_raw_limit():
    """多个 provider 请求的有效配额总和永远不超过 150。"""
    seen_limits = []

    def handler(request):
        seen_limits.append(request.limit)
        return [
            {"title": f"{request.source}-{index}", "tmdb_id": index + 1}
            for index in range(request.limit + 10)
        ]

    adapter = DiscoveryAdapter(
        provider=MoviePilotProvider({"tmdb_discover": handler})
    )
    first = _tmdb_request(limit=100)
    second = _tmdb_request(
        request_id="tmdb_tv",
        source="tmdb_tv",
        media_type="tv",
        limit=100,
    )

    result = adapter.fetch_requests([first, second], raw_limit=150)

    assert seen_limits == [100, 50]
    assert len(result.items) == 150
    assert sum(item["limit"] for item in result.request_recipes) == 150


def test_small_global_limit_skips_sources_without_a_positive_quota():
    """全局上限小于来源数时只执行有正配额的来源。"""
    calls = []

    def handler(request):
        calls.append(request.source)
        return []

    adapter = DiscoveryAdapter(
        provider=MoviePilotProvider(
            {
                "douban_public": handler,
                "tmdb_discover": handler,
                "bangumi_discover": handler,
            }
        ),
    )
    result = adapter.fetch(
        {"tmdb_movies": True, "tmdb_tv": True, "douban": True, "bangumi": True},
        count=1,
        raw_limit=1,
    )

    assert calls == ["douban"]
    assert [recipe["source"] for recipe in result.request_recipes] == ["douban"]
    assert result.raw_limit == 1


def test_recommend_provider_uses_only_valid_typed_playback_seeds():
    """推荐 Provider 只接受电影/剧集正整数 TMDB 播放种子。"""
    calls = []

    def handler(request):
        calls.append(request)
        return [{"title": request.request_id, "tmdb_id": request.params["tmdbid"]}]

    adapter = DiscoveryAdapter(
        provider=MoviePilotProvider({"tmdb_recommend": handler})
    )
    result = adapter.fetch_recommendations(
        [
            {"media_type": "movie", "tmdb_id": "10"},
            {"media_type": "tv", "tmdb_id": 20},
            {"media_type": "anime", "tmdb_id": 30},
            {"media_type": "movie", "tmdb_id": "bad"},
            {"media_type": "movie", "tmdb_id": 10.5},
            {"media_type": "movie", "tmdb_id": "10"},
        ],
        raw_limit=10,
    )

    assert [(item.media_type, item.params["tmdbid"], item.limit) for item in calls] == [
        ("movie", 10, 5),
        ("tv", 20, 5),
    ]
    assert [item.source for item in result.items] == [
        "tmdb_recommend",
        "tmdb_recommend",
    ]
    assert all(recipe["method"] == "tmdb_recommend" for recipe in result.request_recipes)


def test_default_layered_recall_uses_25_10_5_10_quotas():
    """默认 50 候选按精确、放宽、相邻和公共推荐四层分配。"""
    calls = []

    def handler(request):
        calls.append(request)
        base = (len(calls) + 1) * 1000
        return [
            {
                "title": f"{request.layer}-{index}",
                "tmdb_id": base + index,
                "media_type": request.media_type,
            }
            for index in range(request.limit)
        ]

    plan = RetrievalPlan(
        filters=RetrievalFilters(
            media_types=("movie",),
            genre_ids=(878,),
            keyword_ids=(123,),
            rating_min=7.0,
            vote_count_min=100,
            year_min=2000,
        )
    )
    adapter = DiscoveryAdapter(
        provider=MoviePilotProvider(
            {"tmdb_discover": handler, "tmdb_recommend": handler}
        )
    )

    result = adapter.fetch_layered(
        {"tmdb_movies": True},
        candidate_limit=50,
        retrieval_plan=plan,
        playback_samples=[{"media_type": "movie", "tmdb_id": "10"}],
    )

    initial_totals = {}
    for recipe in result.request_recipes:
        if recipe["recall_pass"] == "initial":
            initial_totals[recipe["layer"]] = (
                initial_totals.get(recipe["layer"], 0) + recipe["limit"]
            )
    assert initial_totals == {
        "exact": 25,
        "relaxed": 10,
        "adjacent": 5,
        "public_recommend": 10,
    }
    request_ids = [item["request_id"] for item in result.request_recipes]
    assert len(request_ids) == len(set(request_ids))
    assert len(result.items) == 50
    relaxed = next(item for item in calls if item.layer == "relaxed")
    assert dict(relaxed.params) == {
        "sort_by": "popularity.desc",
        "with_genres": "",
        "with_original_language": "",
        "with_keywords": "",
        "with_watch_providers": "",
        "vote_average": 0.0,
        "vote_count": 0,
        "release_date": "",
        "page": 1,
    }
    adjacent = next(item for item in calls if item.layer == "adjacent")
    assert adjacent.params["with_genres"] == "12|14|28|9648"


def test_layer_shortfall_is_refilled_from_other_valid_layers():
    """精确层不足时由其余有效层按稳定轮询配额补足。"""
    call_index = 0

    def handler(request):
        nonlocal call_index
        call_index += 1
        if request.layer == "exact" and ":fallback" not in request.request_id:
            return []
        return [
            {
                "title": f"{request.request_id}-{index}",
                "tmdb_id": call_index * 1000 + index,
                "media_type": request.media_type,
            }
            for index in range(request.limit)
        ]

    adapter = DiscoveryAdapter(
        provider=MoviePilotProvider(
            {"tmdb_discover": handler, "tmdb_recommend": handler}
        )
    )
    plan = RetrievalPlan(
        filters=RetrievalFilters(media_types=("movie",), genre_ids=(878,))
    )

    result = adapter.fetch_layered(
        {"tmdb_movies": True},
        candidate_limit=50,
        retrieval_plan=plan,
        playback_samples=[{"media_type": "movie", "tmdb_id": "10"}],
    )

    fallback = [
        item for item in result.request_recipes if item["recall_pass"] == "fallback"
    ]
    assert len(result.items) == 50
    assert sum(item["limit"] for item in fallback) == 25
    assert sum(item["limit"] for item in result.request_recipes) <= 150
    assert {item["layer"] for item in fallback} == {
        "relaxed",
        "adjacent",
        "public_recommend",
    }


def test_discovery_adapter_contains_no_frontend_scraping_path():
    """Provider 只能调用 MoviePilot chain，不得抓取发现页 HTML。"""
    source = (PLUGIN_DIR / "adapter" / "discovery.py").read_text(encoding="utf-8")
    for forbidden in (
        "BeautifulSoup",
        "selenium",
        "playwright",
        "frontend_url",
        "requests.get",
        "httpx",
    ):
        assert forbidden not in source
    for chain_name in ("DoubanChain", "TmdbChain", "BangumiChain"):
        assert chain_name in source
