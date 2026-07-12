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
media_module = importlib.import_module(f"{PACKAGE_NAME}.adapter.media")

Candidate = candidate_module.Candidate
MediaRecognitionAdapter = media_module.MediaRecognitionAdapter


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
