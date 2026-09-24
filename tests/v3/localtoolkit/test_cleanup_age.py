"""扫描与删除前复核共用精确时间阈值。"""

from datetime import datetime, timedelta, timezone

import pytest

from app.plugins.localtoolkit.model.library_cleanup import (
    CleanupCandidate, CleanupCondition, evaluate_cleanup_candidate, match_condition,
)


@pytest.mark.parametrize("days", [7, 30])
@pytest.mark.parametrize("offset, expected", [(-1, False), (0, False), (1, True), (82800000000, True)])
@pytest.mark.parametrize("zone", [timezone.utc, timezone(timedelta(hours=8))])
def test_scan_and_precheck_use_exact_elapsed_time(days, offset, expected, zone):
    """覆盖阈值前后微秒、整点、未满下一天及跨时区的等价时刻。"""
    now = datetime(2026, 9, 25, 2, tzinfo=timezone.utc)
    created = (now - timedelta(days=days, microseconds=offset)).astimezone(zone)
    candidate = CleanupCandidate(movie_id="one", date_created=created.isoformat(), played=True, favorite=False)
    condition = CleanupCondition(index=1, days_threshold=days, played="played", favorite="unfav")
    assert match_condition(candidate, condition, now) is expected
    assert evaluate_cleanup_candidate(candidate, [condition], now) is expected


@pytest.mark.parametrize("created", ["", "invalid-date"])
def test_missing_creation_date_stays_unknown(created):
    """无有效日期时既不入队，也不能通过删除前复核。"""
    now = datetime.now(timezone.utc)
    candidate = CleanupCandidate(movie_id="one", date_created=created, played=True, favorite=False)
    condition = CleanupCondition(index=1, days_threshold=7, played="played", favorite="unfav")
    assert match_condition(candidate, condition, now) is False
    assert evaluate_cleanup_candidate(candidate, [condition], now) is None
