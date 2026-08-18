"""豆瓣中心 V3 媒体身份与链参数测试。"""

from types import SimpleNamespace

from app.schemas.types import MediaSource, MediaType

from doubancenter.model.identity import identity_from_media, legacy_identity, recognize_media
from doubancenter.service import dashboard_rank_subscription, subscription


class CaptureMediaChain:
    """记录 V3 媒体链调用参数。"""

    def __init__(self):
        self.kwargs = None

    def recognize_media(self, **kwargs):
        """保存调用参数并返回占位对象。"""
        self.kwargs = kwargs
        return SimpleNamespace(media_source=kwargs.get("media_source"), media_id=kwargs.get("media_id"))


def test_legacy_identity_normalizes_builtin_dynamic_and_invalid_pairs():
    """统一身份优先并支持动态来源，半对和零值必须无效。"""
    assert legacy_identity(tmdb_id=123) == (MediaSource.TMDB, "123")
    assert legacy_identity(media_source="acme.video", media_id="x-9") == (MediaSource("acme.video"), "x-9")
    assert legacy_identity(media_source="douban", media_id="0") == (None, None)
    assert legacy_identity(media_source="douban", media_id=None, tmdb_id=123) == (None, None)


def test_identity_from_media_preserves_dynamic_source():
    """媒体对象中的动态来源身份保持原样。"""
    source, media_id = identity_from_media({"media_source": "vendor_1", "media_id": 88})
    assert source == MediaSource("vendor_1")
    assert media_id == "88"


def test_recognize_media_calls_only_v3_identity_parameters():
    """通用媒体链仅接收 V3 来源与 ID 参数。"""
    chain = CaptureMediaChain()
    recognize_media(chain, meta="meta", mtype="movie", tmdb_id=321)
    assert chain.kwargs["media_source"] == MediaSource.TMDB
    assert chain.kwargs["media_id"] == "321"
    assert "tmdbid" not in chain.kwargs
    assert "doubanid" not in chain.kwargs
    assert "bangumiid" not in chain.kwargs


def test_silent_subscription_calls_v3_subscribe_chain_contract():
    """手动订阅向订阅链传递不可拆分的媒体身份对。"""
    captured = {}

    class SubscribeChain:
        """记录订阅添加参数。"""

        def add(self, **kwargs):
            """保存参数并返回成功。"""
            captured.update(kwargs)
            return 1, ""

    sid, message = dashboard_rank_subscription.add_silent_subscription(
        SubscribeChain(),
        "测试条目",
        "2026",
        "movie",
        media_source="douban",
        media_id=1295644,
    )
    assert sid == 1
    assert message == ""
    assert captured["media_source"] == MediaSource.Douban
    assert captured["media_id"] == "1295644"
    assert "tmdbid" not in captured
    assert "doubanid" not in captured
    assert "bangumiid" not in captured


def test_completed_subscription_check_uses_v3_history_signature():
    """订阅历史去重按来源、ID、季和剧集组查询。"""
    captured = {}
    media = SimpleNamespace(
        media_source=MediaSource.Bangumi,
        media_id="42",
        episode_group="group-a",
    )
    meta = SimpleNamespace(begin_season=2)

    class SubscribeChain:
        """模拟没有活动订阅。"""

        def exists(self, mediainfo, meta):
            """返回无活动订阅。"""
            return False

    class SubscribeOper:
        """记录完成订阅查询参数。"""

        def exist_history(self, **kwargs):
            """保存参数并返回已存在。"""
            captured.update(kwargs)
            return True

    assert subscription.is_existing_media(
        media,
        meta,
        subscribe_chain_cls=SubscribeChain,
        subscribe_oper_cls=SubscribeOper,
    )
    assert captured == {
        "media_source": MediaSource.Bangumi,
        "media_id": "42",
        "season": 2,
        "episode_group": "group-a",
    }


def test_auto_subscription_forwards_season_and_keeps_bangumi_record_title():
    """自动订阅复用 TMDB 身份和季号，历史保留 BGM 来源标题。"""
    captured = {}
    saved = {}
    source_title = "Re:ゼロから始める異世界生活 4th season 奪還編"
    media = SimpleNamespace(
        title="Re：从零开始的异世界生活",
        year="2016",
        type=MediaType.TV,
        media_source=MediaSource.TMDB,
        media_id="65942",
        tmdb_id=65942,
        episode_group=None,
        get_poster_image=lambda: "poster.jpg",
    )
    meta = SimpleNamespace(begin_season=4, org_string=source_title)
    plugin = SimpleNamespace(
        get_data=lambda key: saved.get(key),
        save_data=lambda key, value: saved.update({key: value}),
    )

    class SubscribeChain:
        """记录自动订阅参数。"""

        def exists(self, mediainfo, meta):
            """模拟没有活动订阅。"""
            return False

        def add(self, **kwargs):
            """保存订阅参数并返回成功。"""
            captured.update(kwargs)
            return 1, ""

    class SubscribeOper:
        """模拟没有已完成订阅。"""

        def exist_history(self, **kwargs):
            """返回没有完成历史。"""
            return False

    assert subscription.add_subscription(
        plugin,
        media,
        meta=meta,
        rank_key="bangumi",
        rank_name="BangumiTV",
        record_title=source_title,
        subscribe_chain_cls=SubscribeChain,
        subscribe_oper_cls=SubscribeOper,
    )
    assert captured["media_source"] == MediaSource.TMDB
    assert captured["media_id"] == "65942"
    assert captured["season"] == 4
    assert saved["subscribe_records"][0]["title"] == source_title
    assert saved["subscribe_records"][0]["season"] == 4
