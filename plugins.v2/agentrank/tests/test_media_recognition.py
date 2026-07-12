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
                year="2026",
                original_title="Original",
                overview="Overview",
                poster_path="https://image.example/poster.jpg",
                backdrop_path="https://image.example/backdrop.jpg",
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
    assert result.candidate_id == "tmdb:900"
    assert result.title == "TMDB 标准标题"
    assert result.year == 2026
    assert result.poster_path.endswith("poster.jpg")
    assert result.source_ids == {"douban": "db-9", "tmdb": "900"}
    assert result.metadata["recognized_by"] == "moviepilot"


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


def test_legacy_board_repair_replaces_only_broken_poster_urls():
    """Poster migration preserves ranking identity and skips already valid images."""
    board = RecommendationBoard(
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
    result = BoardPosterRepairService(repository, MediaAdapter()).repair_users(
        ["alice"]
    )

    assert result == {"alice": 1}
    assert repository.saved is board
    assert board.recommendations[0].candidate_id == "douban:7"
    assert board.recommendations[0].summary == "Keep summary"
    assert board.recommendations[0].poster_path.endswith("repaired.jpg")
    assert board.recommendations[1].poster_path.endswith("current.jpg")


def test_poster_image_service_returns_cached_data_url():
    """外部图片被转换为可直接渲染的 data URL 并命中内存缓存。"""
    calls = []

    def fetcher(url):
        calls.append(url)
        return b"\x89PNG\r\n\x1a\nimage"

    service = PosterImageService(fetcher)
    first = service.data_url("https://image.tmdb.org/poster.jpg")
    second = service.data_url("https://image.tmdb.org/poster.jpg")
    assert first.startswith("data:image/png;base64,")
    assert second == first
    assert calls == ["https://image.tmdb.org/poster.jpg"]
