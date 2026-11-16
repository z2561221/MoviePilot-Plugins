"""性能边界采用请求/存储计数，外部依赖隔离，恢复语义与旧算法对照。"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event, RLock
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter.adapter import folio_library
from app.plugins.doubancenter.service import (
    archive,
    dashboard,
    dashboard_folio,
    lifecycle,
    subscription,
)
from app.plugins.doubancenter.service.dashboard_subscribe_history import same_record


class MemoryPlugin:
    def __init__(self, data=None):
        self.data = deepcopy(data or {})
        self.reads = Counter()
        self.writes = Counter()
        self.fail_key = None
        self._rank_lock = RLock()
        self._folio_poster_lock = RLock()
        self._custom_ranks = []
        lifecycle.start(self)

    def get_data(self, key, **kwargs):
        self.reads[key] += 1
        return deepcopy(self.data.get(key))

    def save_data(self, key, value):
        if self.fail_key == key:
            raise OSError("injected save failure")
        self.writes[key] += 1
        self.data[key] = deepcopy(value)


@pytest.fixture
def poster_lookup(monkeypatch):
    service = SimpleNamespace(name="test", config=SimpleNamespace(config={"host": "http://library.invalid/"}))
    monkeypatch.setattr(folio_library, "MediaServerHelper", lambda: SimpleNamespace(
        get_services=lambda **kwargs: {"test": service},
    ))
    monkeypatch.setattr(folio_library.SecurityUtils, "sign_url", lambda url: url)
    calls = []

    def lookup(services, origin, memo):
        calls.append(origin["media_id"])
        return {"url": "http://library.invalid/poster", "reference": {"item_id": origin["media_id"]}}

    monkeypatch.setattr(folio_library, "_lookup_poster", lookup)
    return calls


def movie(index, month=11):
    return {"type": "movie", "media_source": "douban", "media_id": str(index),
            "timestamp": f"2026-{month:02d}-01 12:00:00", "poster_path": "fallback"}


def test_timeline_bounds_network_and_keeps_raw_history(poster_lookup):
    data = {str(i): movie(i + 1, 11 - i // 60) for i in range(360)}
    plugin = MemoryPlugin({"folio_data": data})
    first = dashboard_folio.get_folio_data(plugin)["data"]
    assert len(first) == 150
    assert {record["timestamp"][5:7] for record in first.values()} == {"11", "10", "09"}
    assert len(poster_lookup) == 150
    assert dashboard_folio.get_folio_data(plugin)["data"] == first
    assert len(poster_lookup) == 150
    assert dashboard_folio.get_folio_data(plugin, raw=True)["data"] == data
    assert plugin.data == {"folio_data": data}
    assert not plugin.writes


def test_window_crosses_year_and_skips_invalid_dates():
    data = {"old": {**movie(1), "timestamp": "2025-12-01 12:00:00"},
            "new": {**movie(2), "timestamp": "2026-01-01 12:00:00"},
            "invalid": {**movie(3), "timestamp": "invalid"}}
    assert len(dashboard_folio.visible_timeline_records(data)) == 2


def test_concurrent_timeline_requests_share_lookup(monkeypatch, poster_lookup):
    plugin = MemoryPlugin({"folio_data": {"movie": movie(1)}})
    entered, release = Event(), Event()
    original = folio_library._lookup_poster

    def lookup(*args):
        entered.set()
        assert release.wait(3)
        return original(*args)

    monkeypatch.setattr(folio_library, "_lookup_poster", lookup)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(dashboard_folio.get_folio_data, plugin)
        assert entered.wait(3)
        second = pool.submit(dashboard_folio.get_folio_data, plugin)
        release.set()
        assert first.result(3) == second.result(3)
    assert len(poster_lookup) == 1


def test_stopped_lookup_cannot_republish_cache(monkeypatch, poster_lookup):
    plugin = MemoryPlugin({"folio_data": {"movie": movie(1)}})
    original = folio_library._lookup_poster

    def lookup(*args):
        lifecycle.start(plugin)
        return original(*args)

    monkeypatch.setattr(folio_library, "_lookup_poster", lookup)
    dashboard_folio.get_folio_data(plugin)
    assert plugin._folio_library_poster_cache == {}


def records(count):
    return [{"title": f"film-{i}", "media_source": "douban", "media_id": str(i + 1),
             "time": f"2026-11-01 00:{i // 60:02d}:{i % 60:02d}", "status": "success"}
            for i in range(count)]


def test_page_reads_never_write_and_maintenance_archives_once():
    plugin = MemoryPlugin({"subscribe_records": records(500)})
    assert dashboard.api_subscribe_history(plugin)["data"]["total"] == 5
    dashboard.api_stats(plugin)
    dashboard.api_overview(plugin)
    dashboard.api_archive_records(plugin)
    assert not plugin.writes
    dashboard.maintain_records(plugin)
    assert plugin.writes == {"archive_records": 1, "subscribe_records": 1}
    assert len(plugin.data["archive_records"]) == 495
    assert len(plugin.data["subscribe_records"]) == 5
    before = deepcopy(plugin.data)
    plugin.writes.clear()
    dashboard.maintain_records(plugin)
    assert not plugin.writes
    assert plugin.data == before


def test_archive_save_failure_keeps_all_source_records():
    plugin = MemoryPlugin({"subscribe_records": records(500)})
    before = deepcopy(plugin.data)
    plugin.fail_key = "archive_records"
    with pytest.raises(OSError, match="injected"):
        dashboard.maintain_records(plugin)
    assert plugin.data == before
    assert not plugin.writes


def test_normal_subscription_write_archives_overflow():
    plugin = MemoryPlugin({"subscribe_records": records(5)})
    subscription.write_subscribe_record(plugin, title="new", year="2026", media_source="douban", media_id="999")
    assert len(plugin.data["subscribe_records"]) == 5
    assert len(plugin.data["archive_records"]) == 1


def test_restoring_old_record_does_not_archive_then_delete_the_only_copy():
    restored = records(1)[0]
    plugin = MemoryPlugin({"subscribe_records": records(6)[1:], "archive_records": [
        {"id": "restore", "source": "subscribe_history", "record": restored},
    ]})
    assert archive.restore_archive_record(plugin, "restore", same_record)["success"]
    assert any(row["title"] == restored["title"] for row in plugin.data["subscribe_records"])
    assert plugin.data["archive_records"] == []


def legacy_dedupe(rows):
    merged, changed = [], False
    for row in rows:
        if not isinstance(row, dict):
            changed = True
            continue
        source, record = str(row.get("source") or ""), row.get("record") or {}
        for index, existing in enumerate(merged):
            if str(existing.get("source") or "") == source and archive.same_archive_record(source, existing.get("record") or {}, record):
                changed = True
                if archive.archive_record_score(record) > archive.archive_record_score(existing.get("record") or {}):
                    merged[index] = row
                break
        else:
            merged.append(row)
    return merged[-500:], changed or len(merged) != len(rows)


def test_grouped_dedupe_preserves_legacy_matching_and_order():
    variants = [{}, {"title": "same"}, {"title": "same", "media_source": "douban", "media_id": "1"},
                {"title": "same", "media_source": "douban", "media_id": "2"},
                {"title": "same", "unique": "one"}, {"title": "same", "unique": "two"},
                {"title": "same", "detail": "rich", "poster": "poster"}, {"title": "other"}]
    for shift in range(len(variants)):
        rows = [{"id": str(i), "source": "history" if i % 3 else "log", "record": record}
                for i, record in enumerate((variants[shift:] + variants[:shift]) * 3)] + [None]
        assert archive.dedupe_archive_records(rows) == legacy_dedupe(rows)


def test_distinct_archive_titles_avoid_pairwise_comparisons(monkeypatch):
    rows = [{"source": "subscribe_history", "record": row} for row in records(500)]
    calls = []
    original = archive.same_archive_record
    monkeypatch.setattr(archive, "same_archive_record", lambda *args: calls.append(1) or original(*args))
    assert archive.dedupe_archive_records(rows) == (rows, False)
    assert not calls
