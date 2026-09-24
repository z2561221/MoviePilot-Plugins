"""AgentRank media-library exclusion adapter tests."""

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
        }
    ]
