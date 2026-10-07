"""AgentRank media-library exclusion adapter tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models.mediaserver import MediaServerItem
from app.db.oper.mediaserver import MediaServerOper
from app.schemas.types import MediaSource
from app.plugins.agentrank.model.candidate import Candidate
from app.plugins.agentrank.adapter.library import LibraryAdapter


class RecordingOper:
    """Record exact MediaServerOper.exists lookup arguments."""

    def __init__(self, result=True):
        self.result = result
        self.calls = []

    def exists(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def test_library_lookup_uses_tmdb_id_and_recognized_moviepilot_type():
    """媒体库联合索引需要 TMDB ID 与实际基础类型同时命中。"""
    oper = RecordingOper()
    candidate = Candidate(
        candidate_id="tmdb:tv:42509",
        title="Steins Gate",
        media_type="anime",
        source_ids={"tmdb": "42509"},
        metadata={"mp_media_type": "电视剧"},
    )

    assert LibraryAdapter(oper).exists(candidate) is True
    assert oper.calls == [
        {
            "media_source": MediaSource.TMDB,
            "media_id": "42509",
            "mtype": "电视剧",
            "title": "Steins Gate",
            "year": None,
        }
    ]


def test_animation_movie_library_lookup_uses_movie_type():
    """展示为动漫的电影不能误查电视剧索引。"""
    oper = RecordingOper()
    candidate = Candidate(
        candidate_id="tmdb:movie:16",
        title="Animation Movie",
        media_type="anime",
        source_ids={"tmdb": "16"},
        metadata={"mp_media_type": "电影"},
    )

    LibraryAdapter(oper).exists(candidate)

    assert oper.calls == [
        {
            "media_source": MediaSource.TMDB,
            "media_id": "16",
            "mtype": "电影",
            "title": "Animation Movie",
            "year": None,
        }
    ]


@pytest.mark.parametrize("year, media_type, expected", [(2025, "movie", True), (2024, "movie", False), (2025, "tv", False)])
def test_cross_source_library_uses_host_metadata_fallback(year, media_type, expected):
    """真实宿主查库按标题、年份与类型匹配，不改写候选主身份。"""
    engine = create_engine("sqlite://")
    try:
        MediaServerItem.__table__.create(engine)
        with Session(engine) as session:
            session.add(MediaServerItem(
                server="review-lab", item_id="douban-film", title="Review Film",
                year="2025", item_type="电影", media_source="douban", media_id="987654",
            ))
            session.commit()
            candidate = Candidate(
                candidate_id=f"tmdb:{media_type}:123456", title="Review Film",
                year=year, media_type=media_type, media_source="themoviedb", media_id="123456",
            )
            assert LibraryAdapter(MediaServerOper(session)).exists(candidate) is expected
            assert candidate.media_source == "themoviedb"
            assert candidate.media_id == "123456"
    finally:
        engine.dispose()
