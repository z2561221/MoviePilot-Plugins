"""AgentRank 全局订阅硬过滤适配器测试。"""

import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest


subscription_module = importlib.import_module(
    "app.plugins.agentrank.adapter.subscription"
)
SubscriptionAdapter = subscription_module.SubscriptionAdapter
MediaSource = subscription_module.MediaSource
V3MediaType = subscription_module.MediaType


@pytest.fixture(name="query_sdk")
def query_sdk_fixture(monkeypatch):
    """仅在查询测试期间安装 SDK 替身，保留宿主模块的导入路径。"""
    queries = ModuleType("app.sdk.queries")
    queries.QueryPageRequest = SimpleNamespace
    queries.QuerySort = SimpleNamespace
    queries.QuerySortField = SimpleNamespace(ID="id")
    queries.QuerySortDirection = SimpleNamespace(ASC="asc")
    queries.MAX_QUERY_PAGE_SIZE = 200
    queries.list_subscriptions = lambda **kwargs: SimpleNamespace(items=[], has_next=False)
    monkeypatch.setitem(sys.modules, "app.sdk.queries", queries)
    monkeypatch.setattr(importlib.import_module("app.sdk"), "queries", queries, raising=False)
    return queries


class RecordingOper:
    """记录全局订阅读取次数并禁止按用户名查询。"""

    def __init__(self):
        """准备跨多个用户名的订阅测试数据。"""
        self.calls = 0

    def list(self):
        """返回不同用户名、类型和无效身份的混合订阅。"""
        self.calls += 1
        return [
            {
                "username": "alice",
                "media_source": MediaSource.TMDB,
                "media_id": "10",
                "type": "电影",
            },
            SimpleNamespace(
                username="bob",
                media_source=MediaSource.TMDB,
                media_id="10",
                type="电视剧",
            ),
            {
                "username": "carol",
                "media_source": MediaSource.TMDB,
                "media_id": None,
                "type": "电影",
            },
        ]

    def list_by_username(self, **kwargs):
        """若生产代码回退到 MP 用户链路则立即失败。"""
        raise AssertionError("username-scoped subscription lookup is forbidden")


def test_all_user_subscriptions_become_type_safe_candidate_ids():
    """所有用户名下的有效订阅必须统一进入硬过滤集合。"""
    oper = RecordingOper()

    result = SubscriptionAdapter(oper).candidate_ids()

    assert result == {"tmdb:movie:10", "tmdb:tv:10"}
    assert oper.calls == 1


@pytest.mark.parametrize(
    ("raw_type", "expected_type"),
    [
        ("电影", V3MediaType.MOVIE),
        ("movie", V3MediaType.MOVIE),
        ("电视剧", V3MediaType.TV),
        ("tv", V3MediaType.TV),
    ],
)
def test_cross_source_conversion_receives_media_type_enum(raw_type, expected_type):
    """跨源订阅转换必须收到 MediaType 枚举而不是裸字符串。"""
    calls = []

    class ConversionChain:
        """记录转换参数并模拟返回 TMDB 身份。"""

        def convert_media_identity(self, **kwargs):
            """校验类型枚举可被 TMDB 日志读取。"""
            calls.append(kwargs)
            assert kwargs["mtype"].value == expected_type.value
            return {
                "media_source": MediaSource.TMDB,
                "media_id": "12",
            }

    class DoubanOper:
        """返回一条需要跨源转换的订阅。"""

        def list(self):
            """返回豆瓣订阅记录。"""
            return [
                {
                    "media_source": MediaSource.Douban,
                    "media_id": "37508847",
                    "type": raw_type,
                }
            ]

    result = SubscriptionAdapter(
        DoubanOper(), chain_factory=lambda: ConversionChain()
    ).candidate_ids()

    assert result == {"tmdb:movie:12" if expected_type is V3MediaType.MOVIE else "tmdb:tv:12"}
    assert len(calls) == 1


def test_query_sdk_reads_all_pages(query_sdk):
    """超过单页上限的订阅必须全部进入过滤集合，并使用稳定排序。"""
    calls = []

    def list_subscriptions(filters, page):
        """按请求页号返回共 201 条订阅，末页只有一条电视剧。"""
        calls.append((filters, page))
        return SimpleNamespace(
            items=[
                {
                    "media_source": MediaSource.TMDB,
                    "media_id": str(media_id),
                    "type": "电影" if page.page == 1 else "电视剧",
                }
                for media_id in (range(1, 201) if page.page == 1 else [201])
            ],
            has_next=page.page == 1,
        )

    query_sdk.list_subscriptions = list_subscriptions
    result = SubscriptionAdapter(query_api=query_sdk).candidate_ids()

    assert result == {f"tmdb:movie:{media_id}" for media_id in range(1, 201)} | {"tmdb:tv:201"}
    assert [page.page for _, page in calls] == [1, 2]
    for filters, page in calls:
        assert filters == {"media_types": (V3MediaType.MOVIE, V3MediaType.TV)}
        assert page.count == 200
        assert page.sort.field == "id"
        assert page.sort.direction == "asc"


def test_default_adapter_uses_v3_query_sdk(query_sdk):
    """默认适配器应从 V3 稳定查询门面读取订阅。"""
    record = {"media_source": MediaSource.TMDB, "media_id": "12", "type": "电影"}
    query_sdk.list_subscriptions = lambda **kwargs: SimpleNamespace(items=[record], has_next=False)

    assert SubscriptionAdapter().candidate_ids() == {"tmdb:movie:12"}


@pytest.mark.parametrize("music_type", ["music", "音乐", V3MediaType.MUSIC])
def test_music_subscriptions_are_skipped_before_identity_conversion(music_type):
    """音乐原生 ID 不得转换成影视身份或阻断影视订阅过滤。"""
    records = [
        {"media_source": MediaSource("musicbrainz"), "media_id": "album-id", "type": music_type},
        {"media_source": MediaSource.TMDB, "media_id": "10", "type": "电影"},
    ]

    def unexpected_conversion():
        """任何音乐身份转换调用都使测试失败。"""
        raise AssertionError("music subscriptions must not enter identity conversion")

    adapter = SubscriptionAdapter(
        oper=SimpleNamespace(list=lambda: records), chain_factory=unexpected_conversion
    )
    assert adapter.candidate_ids() == {"tmdb:movie:10"}


def test_subscription_with_tmdb_id_but_unknown_type_fails_closed():
    """已有 TMDB ID 却无法判定类型时不得静默漏过重复订阅。"""
    class AmbiguousOper:
        def list(self):
            return [
                {
                    "username": "alice",
                    "media_source": MediaSource.TMDB,
                    "media_id": "11",
                    "type": "unknown",
                }
            ]

    with pytest.raises(ValueError, match="movie or tv"):
        SubscriptionAdapter(AmbiguousOper()).candidate_ids()
