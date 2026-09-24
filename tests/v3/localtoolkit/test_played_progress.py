"""播放进度替代媒体服务器已观看标记的筛选与实时复核回归。"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.plugins.localtoolkit.adapter.media_server import MediaServerCleanupAdapter
from app.plugins.localtoolkit.model.library_cleanup import (
    CleanupCandidate,
    build_cleanup_conditions,
    candidate_from_media_item,
    evaluate_cleanup_candidate,
    filter_cleanup_candidates,
    played_from_progress,
)
from .test_cleanup_verification import Response


@pytest.mark.parametrize("state, expected", [
    ({"PlayedPercentage": 76.329, "Played": False}, True),
    ({"PlayedPercentage": 73.364, "Played": False}, True),
    ({"PlayedPercentage": 0.001, "Played": False}, True),
    ({"PlayedPercentage": 100}, True),
    ({"PlayedPercentage": 0, "Played": True, "PlayCount": 5}, False),
    ({"percentage": 12.5, "played": False}, True),
    ({"percentage": "0"}, False),
    ({"PlaybackPositionTicks": 100}, True),
    ({"PlaybackPositionTicks": 0, "Played": True}, False),
    ({"Played": True, "PlayCount": 1}, None),
    ({"PlayedPercentage": None}, None),
    ({"PlayedPercentage": "invalid"}, None),
    ({"PlayedPercentage": -1}, None),
    ({"PlayedPercentage": float("nan")}, None),
    ({"PlayedPercentage": float("inf")}, None),
    ({"PlayedPercentage": True}, None),
])
def test_played_state_uses_progress_only(state, expected):
    """覆盖零值、小进度、已完成、缺失、异常及不同宿主字段形态。"""
    assert played_from_progress(state) is expected


def test_reported_examples_match_first_condition_with_progress():
    """两条现场样本均按大于零进度命中条件一，不依赖 Played 标记。"""
    items = [
        {"Id": "75873", "DateCreated": "2026-08-24T15:02:14.0000000Z",
         "UserData": {"PlayedPercentage": 76.329, "Played": False, "IsFavorite": False}},
        {"Id": "75965", "DateCreated": "2026-08-24T15:03:17.0000000Z",
         "UserData": {"PlayedPercentage": 73.364, "Played": False, "IsFavorite": False}},
    ]
    config = {"filter_played": "played", "filter_favorite": "unfav", "days_threshold": 7}
    now = datetime(2026, 9, 24, 14, tzinfo=timezone.utc)
    candidates = [candidate_from_media_item(item, server="media", library_id="library") for item in items]
    result = filter_cleanup_candidates(candidates, config, now)
    assert [item.movie_id for item in result.qualified_movies] == ["75873", "75965"]


@pytest.mark.parametrize("progress, expected", [(73.0, True), (0, False), (None, None)])
def test_delete_precheck_recomputes_progress_from_current_user(progress, expected):
    """删除前从用户详情重算，进度归零或未知时不沿用入队快照。"""
    instance = SimpleNamespace(_host="http://media.invalid/", _apikey="test-only", get_user=lambda _: "viewer")
    service = SimpleNamespace(instance=instance, type="emby")
    adapter = MediaServerCleanupAdapter(helper=SimpleNamespace(get_service=lambda **_: service), chain=SimpleNamespace())
    data = {"Id": "one", "ParentId": "library", "DateCreated": "2026-08-24T15:02:14Z",
            "UserData": {"PlayedPercentage": progress, "Played": True, "IsFavorite": False}}
    adapter._request_utils = lambda **_: SimpleNamespace(get_res=lambda *_args: Response(200, data))
    old = CleanupCandidate(movie_id="one", server="media", library_id="library", played=True, favorite=False)
    exists, fresh = adapter.refresh_candidate(old)
    assert exists is True
    assert fresh.played is expected
    conditions = build_cleanup_conditions({"filter_played": "played", "filter_favorite": "unfav", "days_threshold": 7})
    assert evaluate_cleanup_candidate(fresh, conditions, datetime(2026, 9, 24, tzinfo=timezone.utc)) is expected
