"""AgentRank MoviePilot media recognition adapter tests."""

import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_media_recognition_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

adapter_package = sys.modules.setdefault(
    f"{PACKAGE_NAME}.adapter", ModuleType(f"{PACKAGE_NAME}.adapter")
)
adapter_package.__path__ = [str(PLUGIN_DIR / "adapter")]

candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
media_module = importlib.import_module(f"{PACKAGE_NAME}.adapter.media")
poster_module = importlib.import_module(f"{PACKAGE_NAME}.service.poster")

Candidate = candidate_module.Candidate
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
MediaRecognitionAdapter = media_module.MediaRecognitionAdapter
BoardPosterRepairService = poster_module.BoardPosterRepairService
BoardSourceRepairService = poster_module.BoardSourceRepairService
PosterImageService = poster_module.PosterImageService


class FakeMediaType:
    """Expose the minimal MoviePilot media type enum contract."""

    MOVIE = "movie-enum"
    TV = "tv-enum"


class FakeMeta:
    """Capture title, year, and media type passed to MediaChain."""

    def __init__(self, title):
        self.title = title
        self.year = ""
        self.type = None


def test_recognition_prefers_tmdb_id_and_rebuilds_display_fields():
    """A recognized result becomes the sole display identity while source IDs remain."""
    calls = []

    class FakeChain:
        def recognize_media(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                tmdb_id=900,
                title="TMDB 标准标题",
                type=FakeMediaType.MOVIE,
                year="2026",
                original_title="Original",
                overview="Overview",
                poster_path="https://image.example/poster.jpg",
                backdrop_path="https://image.example/backdrop.jpg",
                category="剧情",
                genres=[{"id": 18, "name": "剧情"}],
                genre_ids=[18],
                actors=[{"name": "演员甲"}],
                directors=[{"name": "导演乙"}],
                origin_country=["中国大陆"],
                vote_average=8.6,
                popularity=123.4,
            )

    candidate = Candidate(
        candidate_id="douban:db-9",
        title="来源标题",
        media_type="movie",
        year=2025,
        source_ids={"douban": "db-9", "tmdb": "900"},
    )
    adapter = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType)

    result = adapter.recognize(candidate)

    assert calls[0]["tmdbid"] == "900"
    assert calls[0]["mtype"] == FakeMediaType.MOVIE
    assert result.candidate_id == "tmdb:movie:900"
    assert result.title == "TMDB 标准标题"
    assert result.year == 2026
    assert result.poster_path.endswith("poster.jpg")
    assert result.source_ids == {"douban": "db-9", "tmdb": "900"}
    assert result.media_type == "movie"
    assert result.metadata["mp_media_type"] == "电影"
    assert result.genres == ["剧情"]
    assert result.actors == ["演员甲"]
    assert result.directors == ["导演乙"]
    assert result.regions == ["中国大陆"]
    assert result.rating == 8.6
    assert result.popularity == 123.4
    assert result.metadata["recognized_by"] == "moviepilot"


def test_recognition_uses_actual_type_and_animation_features_not_source_name():
    """Bangumi 也可识别为真人剧，动画电影则保留电影订阅基础类型。"""
    results = [
        SimpleNamespace(
            tmdb_id=901,
            title="Bangumi 真人剧",
            type=FakeMediaType.TV,
            category="剧情",
            genres=[{"id": 18, "name": "剧情"}],
            genre_ids=[18],
        ),
        SimpleNamespace(
            tmdb_id=902,
            title="动画电影",
            type=FakeMediaType.MOVIE,
            category="动画",
            genres=[{"id": 16, "name": "动画"}],
            genre_ids=[16],
        ),
    ]

    class FakeChain:
        def recognize_media(self, **kwargs):
            return results.pop(0)

    adapter = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType)
    bangumi = adapter.recognize(
        Candidate(
            candidate_id="bangumi:1",
            title="Bangumi 真人剧",
            media_type="anime",
            source_ids={"bangumi": "1"},
        )
    )
    animation_movie = adapter.recognize(
        Candidate(
            candidate_id="douban:2",
            title="动画电影",
            media_type="movie",
            source_ids={"douban": "2"},
        )
    )

    assert bangumi.media_type == "tv"
    assert bangumi.metadata["mp_media_type"] == "电视剧"
    assert animation_movie.media_type == "anime"
    assert animation_movie.metadata["mp_media_type"] == "电影"


def test_recognition_rejects_media_without_tmdb_id():
    """A MoviePilot match without TMDB identity is not eligible for Agent ranking."""
    class FakeChain:
        def recognize_media(self, **kwargs):
            return SimpleNamespace(title="Bangumi only", tmdb_id=None)

    candidate = Candidate(
        candidate_id="bangumi:7",
        title="Anime",
        media_type="anime",
        source_ids={"bangumi": "7"},
    )
    adapter = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType)

    assert adapter.recognize(candidate) is None


def test_enrich_cross_source_ids_adds_douban_id_for_tmdb_item():
    """TMDB 榜单条目最终展示前可补齐豆瓣 ID。"""
    calls = []

    class FakeChain:
        def get_doubaninfo_by_tmdbid(self, tmdb_id, mtype=None):
            calls.append((tmdb_id, mtype))
            return {"id": "douban-900"}

    candidate = Candidate(
        candidate_id="tmdb:tv:900",
        title="TMDB剧集",
        media_type="tv",
        source_ids={"tmdb": "900"},
    )
    adapter = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType)

    assert adapter.enrich_cross_source_ids(candidate) is candidate
    assert candidate.source_ids["douban"] == "douban-900"
    assert calls == [(900, FakeMediaType.TV)]


def test_enrich_cross_source_ids_relaxes_year_when_exact_tmdb_match_is_empty():
    """严格 TMDB 映射为空时按标题执行一次无年份豆瓣匹配。"""
    calls = []

    class FakeChain:
        """记录严格与降级匹配参数。"""

        def get_doubaninfo_by_tmdbid(self, tmdb_id, mtype=None):
            """模拟严格年份匹配失败。"""
            calls.append(("exact", tmdb_id, mtype))
            return {}

        def match_doubaninfo(self, name, mtype=None, year=None):
            """模拟无年份匹配成功。"""
            calls.append(("relaxed", name, mtype, year))
            return {"id": "douban-901"}

    candidate = Candidate(
        candidate_id="tmdb:movie:901",
        title="年份漂移新片",
        media_type="movie",
        source_ids={"tmdb": "901"},
    )
    adapter = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType)

    adapter.enrich_cross_source_ids(candidate)

    assert candidate.source_ids["douban"] == "douban-901"
    assert calls == [
        ("exact", 901, FakeMediaType.MOVIE),
        ("relaxed", "年份漂移新片", FakeMediaType.MOVIE, None),
    ]


def test_legacy_board_repair_replaces_only_broken_poster_urls():
    """Poster migration preserves ranking identity and skips already valid images."""
    assert BoardPosterRepairService._needs_repair(
        "data:image/jpeg;base64,legacy"
    )
    board = RecommendationBoard(
        profile_id="alice",
        username="alice",
        run_id="old-run",
        status="success",
        recommendations=[
            RecommendationItem(
                candidate_id="douban:7",
                rank=1,
                title="Legacy",
                media_type="tv",
                year=2026,
                source_ids={"douban": "7"},
                poster_path="https://img1.doubanio.com/legacy.webp",
                summary="Keep summary",
            ),
            RecommendationItem(
                candidate_id="tmdb:8",
                rank=2,
                title="Current",
                poster_path="https://image.tmdb.org/current.jpg",
            ),
        ],
    )

    class Repository:
        def __init__(self):
            self.saved = None

        def load_board(self, username):
            return board if username == "alice" else None

        def save_board(self, value):
            self.saved = value

    class MediaAdapter:
        def recognize(self, candidate):
            candidate.poster_path = "https://image.tmdb.org/repaired.jpg"
            return candidate

    repository = Repository()
    result = BoardPosterRepairService(repository, MediaAdapter()).repair_profiles(
        ["alice"]
    )

    assert result == {"alice": 1}
    assert repository.saved is board
    assert board.recommendations[0].candidate_id == "douban:7"
    assert board.recommendations[0].summary == "Keep summary"
    assert board.recommendations[0].poster_path.endswith("repaired.jpg")
    assert board.recommendations[1].poster_path.endswith("current.jpg")


def test_legacy_board_source_repair_persists_douban_id():
    """旧榜单中的 TMDB 条目应在重载修复时补齐豆瓣 ID。"""
    item = RecommendationItem(
        candidate_id="tmdb:movie:99",
        rank=1,
        title="Existing",
        media_type="movie",
        source_ids={"tmdb": "99"},
    )
    board = RecommendationBoard(
        profile_id="alice",
        run_id="old-run",
        recommendations=[item],
    )

    class Repository:
        """提供最小榜单读写桩。"""

        def __init__(self):
            self.saved = None

        def load_board(self, profile_id):
            """返回指定画像的榜单。"""
            return board if profile_id == "alice" else None

        def save_board(self, value):
            """记录榜单保存。"""
            self.saved = value

    class MediaAdapter:
        """提供最小跨源补链桩。"""

        def enrich_cross_source_ids(self, value):
            """写入豆瓣 ID。"""
            value.source_ids["douban"] = "db-99"
            return value

    repository = Repository()
    result = BoardSourceRepairService(repository, MediaAdapter()).repair_profiles(
        ["alice"]
    )

    assert result == {"alice": 1}
    assert repository.saved is board
    assert item.source_ids["douban"] == "db-99"


def test_poster_image_service_returns_bounded_tmdb_thumbnail_url():
    """TMDB 原图被收敛为 w200 URL，榜单响应不再内嵌 Base64。"""
    service = PosterImageService()
    board = {
        "recommendations": [
            {
                "poster_path": (
                    "https://image.tmdb.org/t/p/original/example.jpg"
                )
            },
            {"poster_path": "https://image.example/poster.jpg"},
            {"poster_path": "data:image/jpeg;base64,oversized"},
        ]
    }

    result = service.enrich_board(board)

    assert result["recommendations"][0]["poster_path"] == (
        "https://image.tmdb.org/t/p/w200/example.jpg"
    )
    assert result["recommendations"][1]["poster_path"] == (
        "https://image.example/poster.jpg"
    )
    assert result["recommendations"][2]["poster_path"] == ""
    assert PosterImageService.thumbnail_url.cache_parameters()["maxsize"] == 512
