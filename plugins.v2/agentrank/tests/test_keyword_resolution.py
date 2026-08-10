"""Controlled retrieval-plan keyword resolution tests."""

import importlib
import sys
from pathlib import Path
from types import ModuleType


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_keyword_resolution_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

retrieval_module = importlib.import_module(f"{PACKAGE_NAME}.model.retrieval")
adapter_module = importlib.import_module(f"{PACKAGE_NAME}.adapter.tmdb_keyword")
service_module = importlib.import_module(f"{PACKAGE_NAME}.service.keyword_resolution")

RetrievalFilters = retrieval_module.RetrievalFilters
RetrievalPlan = retrieval_module.RetrievalPlan
TmdbKeywordAdapter = adapter_module.TmdbKeywordAdapter
TmdbKeywordProviderError = adapter_module.TmdbKeywordProviderError
ControlledRetrievalPlanResolver = service_module.ControlledRetrievalPlanResolver


def _plan(*tags):
    """构造仅含自由标签的测试检索计划。"""
    return RetrievalPlan(
        filters=RetrievalFilters(media_types=("movie",)),
        ranking_tags=tuple(tags),
    )


def test_fixed_genre_exact_and_language_alias_enter_structured_filters():
    """固定题材精确名与语言别名无需外部查询即可安全解析。"""
    result = ControlledRetrievalPlanResolver().resolve(
        _plan("科幻", "英文", "复杂人物关系")
    )

    assert result.plan.filters.genre_ids == (878,)
    assert result.plan.filters.original_languages == ("en",)
    assert result.plan.ranking_tags == ("复杂人物关系",)
    assert [(item.kind, item.status, item.match_type) for item in result.outcomes] == [
        ("genre", "resolved", "exact"),
        ("language", "resolved", "alias"),
        ("keyword", "unavailable", ""),
    ]


def test_tmdb_keyword_exact_name_requires_one_unique_id():
    """TMDB 精确名称只有一个 ID 时才进入 keyword_ids。"""
    calls = []

    def search(term):
        calls.append(term)
        return [{"id": 123, "name": "Cyberpunk"}]

    result = ControlledRetrievalPlanResolver(keyword_searcher=search).resolve(
        _plan("cyberpunk")
    )

    assert calls == ["cyberpunk"]
    assert result.plan.filters.keyword_ids == (123,)
    assert result.plan.ranking_tags == ()
    assert result.outcomes[0].match_type == "exact"


def test_tmdb_keyword_query_alias_is_verified_against_canonical_result():
    """受控别名先转规范查询词，再以唯一同名结果确认 ID。"""
    calls = []

    def search(term):
        calls.append(term)
        return [{"id": 456, "name": "cyberpunk"}]

    result = ControlledRetrievalPlanResolver(keyword_searcher=search).resolve(
        _plan("赛博朋克")
    )

    assert calls == ["cyberpunk"]
    assert result.plan.filters.keyword_ids == (456,)
    assert result.outcomes[0].match_type == "alias"


def test_trusted_direct_keyword_alias_does_not_call_provider():
    """宿主显式配置的正整数别名可直接解析，且不触发外部搜索。"""
    calls = []
    resolver = ControlledRetrievalPlanResolver(
        keyword_searcher=lambda term: calls.append(term) or [],
        keyword_aliases={"时间循环": {"id": 789, "name": "time loop"}},
    )

    result = resolver.resolve(_plan("时间循环"))

    assert calls == []
    assert result.plan.filters.keyword_ids == (789,)
    assert result.outcomes[0].match_type == "alias"


def test_ambiguous_exact_keyword_results_fall_back_to_ranking_tag():
    """同名但不同 ID 的关键词属于歧义，不能进入结构化过滤。"""
    result = ControlledRetrievalPlanResolver(
        keyword_searcher=lambda term: [
            {"id": 1, "name": term},
            {"id": 2, "name": term},
        ]
    ).resolve(_plan("identity"))

    assert result.plan.filters.keyword_ids == ()
    assert result.plan.ranking_tags == ("identity",)
    assert result.outcomes[0].status == "ambiguous"


def test_empty_or_only_fuzzy_keyword_results_fall_back_to_ranking_tags():
    """空结果和仅模糊结果都按无精确匹配降级。"""
    responses = {
        "no result": [],
        "space": [{"id": 8, "name": "space opera"}],
    }
    result = ControlledRetrievalPlanResolver(
        keyword_searcher=lambda term: responses[term]
    ).resolve(_plan("no result", "space"))

    assert result.plan.filters.keyword_ids == ()
    assert result.plan.ranking_tags == ("no result", "space")
    assert [item.status for item in result.outcomes] == ["not_found", "not_found"]


def test_provider_failure_and_lookup_limit_preserve_all_unresolved_tags():
    """服务异常或达到查询上限时只降级，不中断画像生成。"""
    calls = []

    def fail(term):
        calls.append(term)
        raise RuntimeError("offline")

    result = ControlledRetrievalPlanResolver(
        keyword_searcher=fail,
        max_keyword_lookups=1,
    ).resolve(_plan("first", "second"))

    assert calls == ["first"]
    assert result.plan.ranking_tags == ("first", "second")
    assert [item.status for item in result.outcomes] == ["unavailable", "unavailable"]


def test_adapter_drops_invalid_rows_and_deduplicates_ids():
    """TMDB 适配器只返回正整数 ID、非空名称和唯一 ID。"""
    adapter = TmdbKeywordAdapter(
        lambda term: {
            "results": [
                {"id": 1, "name": term},
                {"id": "1", "name": "duplicate"},
                {"id": 0, "name": "invalid"},
                {"id": True, "name": "invalid"},
                {"id": 2, "name": ""},
            ]
        }
    )

    assert [(item.keyword_id, item.name) for item in adapter.search("safe")] == [
        (1, "safe")
    ]


def test_adapter_wraps_provider_exceptions_without_exposing_payloads():
    """宿主查询异常被收敛为可降级的 provider 错误。"""
    def fail(term):
        raise RuntimeError("offline")

    try:
        TmdbKeywordAdapter(fail).search("safe")
    except TmdbKeywordProviderError as error:
        assert str(error) == "offline"
    else:
        raise AssertionError("provider error was not raised")


def test_resolution_metrics_distinguish_success_ambiguity_and_fallback():
    """运行指标分别统计结构化解析与安全降级。"""
    def search(term):
        if term == "exact":
            return [{"id": 10, "name": "exact"}]
        if term == "ambiguous":
            return [
                {"id": 11, "name": "ambiguous"},
                {"id": 12, "name": "ambiguous"},
            ]
        return []

    result = ControlledRetrievalPlanResolver(keyword_searcher=search).resolve(
        _plan("动作", "英文", "exact", "ambiguous", "missing")
    )

    assert result.metrics() == {
        "resolved_genre_count": 1,
        "resolved_language_count": 1,
        "resolved_keyword_count": 1,
        "ranking_tag_fallback_count": 2,
        "ambiguous_keyword_count": 1,
        "keyword_not_found_count": 1,
        "keyword_unavailable_count": 0,
    }
