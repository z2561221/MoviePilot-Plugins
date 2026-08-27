"""AgentRank 全局订阅硬过滤适配器测试。"""

import importlib
import sys
from enum import Enum
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"
PACKAGE_NAME = "agentrank_subscription_filter_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

app_module = sys.modules.setdefault("app", ModuleType("app"))
schemas_module = sys.modules.setdefault("app.schemas", ModuleType("app.schemas"))
types_module = sys.modules.setdefault("app.schemas.types", ModuleType("app.schemas.types"))


class V3MediaSource(str):
    """测试使用的可扩展 V3 媒体来源值。"""

    def __new__(cls, value):
        instance = str.__new__(cls, value)
        instance.value = value
        return instance


V3MediaSource.TMDB = V3MediaSource("themoviedb")
V3MediaSource.Douban = V3MediaSource("douban")


class V3MediaType(Enum):
    """测试使用的 MoviePilot 媒体类型枚举。"""

    MOVIE = "电影"
    TV = "电视剧"


app_module.schemas = schemas_module
schemas_module.types = types_module
types_module.MediaSource = V3MediaSource
types_module.MediaType = V3MediaType

subscription_module = importlib.import_module(
    f"{PACKAGE_NAME}.adapter.subscription"
)
SubscriptionAdapter = subscription_module.SubscriptionAdapter
MediaSource = subscription_module.MediaSource


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


def test_default_adapter_uses_v3_subscription_oper(monkeypatch):
    """默认适配器应从 V3 公开订阅操作路径创建读取器。"""
    oper_module = importlib.import_module("app.db.oper.subscribe")

    class FakeOper:
        """避免默认构造测试触碰真实数据库。"""

        def list(self):
            """返回空订阅列表。"""
            return []

    monkeypatch.setattr(oper_module, "SubscribeOper", FakeOper)

    adapter = SubscriptionAdapter()

    assert isinstance(adapter._oper, FakeOper)


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
