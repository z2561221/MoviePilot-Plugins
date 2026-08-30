"""AgentRank V3 媒体身份与宿主适配测试。"""

from types import SimpleNamespace

from app.schemas.types import MediaSource, MediaType

from app.plugins.agentrank.adapter.library import LibraryAdapter
from app.plugins.agentrank.adapter.media import MediaRecognitionAdapter
from app.plugins.agentrank.adapter.subscription import SubscriptionAdapter
from app.plugins.agentrank.model.board import RecommendationItem
from app.plugins.agentrank.model.candidate import Candidate, backfill_media_identity_payload


def test_legacy_candidate_and_board_item_backfill_tmdb_identity():
    """旧 TMDB 候选与榜单条目可幂等补全 V3 主身份。"""
    candidate = Candidate.from_dict(
        {
            "candidate_id": "tmdb:movie:42",
            "title": "Movie",
            "media_type": "movie",
            "source_ids": {"tmdb": "42", "douban": "db-42"},
        }
    )
    item = RecommendationItem.from_dict(
        {
            "candidate_id": "tmdb:movie:42",
            "rank": 1,
            "title": "Movie",
            "media_type": "movie",
            "source_ids": {"tmdb": "42"},
        }
    )

    assert (candidate.media_source, candidate.media_id) == ("themoviedb", "42")
    assert (item.media_source, item.media_id) == ("themoviedb", "42")
    assert candidate.source_ids["douban"] == "db-42"


def test_unresolved_legacy_payload_is_preserved_without_fake_identity():
    """无法证明来源的旧载荷保持原值，且明确报告未解析。"""
    raw = {"candidate_id": "legacy:unknown", "title": "Unknown", "source_ids": {}}

    migrated, changed, unresolved = backfill_media_identity_payload(raw)

    assert migrated == raw
    assert changed is False
    assert unresolved is True


def test_plugin_extension_source_identity_remains_valid():
    """合法的点分插件来源不会被内置来源列表错误过滤。"""
    candidate = Candidate(
        candidate_id="acme.video:subject-42",
        title="Extension",
        media_type="movie",
        source_ids={"acme.video": "subject-42"},
    )

    assert (candidate.media_source, candidate.media_id) == (
        "acme.video",
        "subject-42",
    )


def test_media_recognition_converts_douban_to_tmdb_before_recognizing():
    """跨源候选必须先走统一转换，再以 TMDB 身份识别。"""
    calls = []

    class Chain:
        def convert_media_identity(self, **kwargs):
            calls.append(("convert", kwargs))
            return {"media_source": MediaSource.TMDB, "media_id": "900", "id": 900}

        def recognize_media(self, **kwargs):
            calls.append(("recognize", kwargs))
            return SimpleNamespace(
                media_source=MediaSource.TMDB,
                media_id="900",
                tmdb_id=900,
                title="Recognized",
                type=MediaType.MOVIE,
                year="2024",
                genres=[],
                directors=[],
                actors=[],
            )

    adapter = MediaRecognitionAdapter(
        chain_factory=Chain,
        meta_factory=lambda title: SimpleNamespace(title=title, year="", type=None),
        media_type_cls=MediaType,
    )
    candidate = Candidate(
        candidate_id="douban:db-9",
        title="Raw",
        media_type="movie",
        source_ids={"douban": "db-9"},
    )

    result = adapter.recognize(candidate)

    assert result is candidate
    assert (result.media_source, result.media_id) == ("themoviedb", "900")
    assert result.candidate_id == "tmdb:movie:900"
    assert calls[0][1]["target_source"] == MediaSource.TMDB
    assert calls[0][1]["media_source"] == MediaSource.Douban
    assert calls[1][1]["media_source"] == MediaSource.TMDB
    assert calls[1][1]["media_id"] == "900"
    assert "tmdbid" not in calls[1][1]


def test_library_lookup_uses_media_identity_pair():
    """媒体库查重只调用 V3 的成对主身份参数。"""
    class Oper:
        def __init__(self):
            self.calls = []

        def exists(self, **kwargs):
            self.calls.append(kwargs)
            return object()

    oper = Oper()
    candidate = Candidate(
        candidate_id="tmdb:tv:16",
        title="Series",
        media_type="tv",
        media_source="themoviedb",
        media_id="16",
        metadata={"mp_media_type": "电视剧"},
    )

    assert LibraryAdapter(oper).exists(candidate) is True
    assert oper.calls == [
        {
            "media_source": MediaSource.TMDB,
            "media_id": "16",
            "mtype": "电视剧",
        }
    ]


def test_subscription_rows_use_v3_identity_and_convert_cross_source():
    """全局订阅从 V3 身份对读取，跨源条目经官方转换后参与 TMDB 去重。"""
    class Oper:
        @staticmethod
        def list():
            return [
                {"media_source": "themoviedb", "media_id": "10", "type": "电影"},
                {"media_source": "douban", "media_id": "db-20", "type": "电视剧"},
            ]

    class Chain:
        def convert_media_identity(self, **kwargs):
            assert kwargs["media_source"] == MediaSource.Douban
            return {"media_source": MediaSource.TMDB, "media_id": "20"}

    result = SubscriptionAdapter(Oper(), chain_factory=Chain).candidate_ids()

    assert result == {"tmdb:movie:10", "tmdb:tv:20"}
