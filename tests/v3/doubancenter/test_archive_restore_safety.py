"""Archive restoration keeps the recovery copy until its destination is saved."""

from copy import deepcopy
from threading import RLock

import pytest

from app.plugins.doubancenter.service.archive import restore_archive_record


class MemoryPlugin:
    def __init__(self, source, record):
        self.data = {
            "archive_records": [{"id": "archive-1", "source": source, "record": record}],
        }
        self.fail_key = ""
        self._rank_lock = RLock()
        self.writes = []

    def get_data(self, key):
        return deepcopy(self.data.get(key))

    def save_data(self, key, value):
        if key == self.fail_key:
            raise OSError("injected storage failure")
        self.writes.append(key)
        self.data[key] = deepcopy(value)


def same_record(item, unique, time, title, _tmdbid):
    return (item.get("unique"), item.get("time"), item.get("title")) == (unique, time, title)


def record():
    return {
        "unique": "sample", "title": "Sample", "time": "2026-10-30 12:00:00",
        "rank_key": "popular", "reason": "sample",
    }


@pytest.mark.parametrize("source,payload", [
    ("unknown", record()),
    ("observation", {"unique": "sample", "title": "Sample"}),
    ("subscribe_history", ["invalid record"]),
])
def test_invalid_archive_preserves_the_original(source, payload):
    plugin = MemoryPlugin(source, payload)
    before = deepcopy(plugin.data)
    result = restore_archive_record(plugin, "archive-1", same_record)
    assert result["success"] is False
    assert plugin.data == before
    assert plugin.writes == []


@pytest.mark.parametrize("source,target", [
    ("subscribe_history", "subscribe_records"),
    ("anti_cheat_log", "anti_cheat_logs"),
    ("observation", "rank_history_popular"),
])
def test_destination_failure_keeps_archive_and_retry_restores_once(source, target):
    plugin = MemoryPlugin(source, record())
    before = deepcopy(plugin.data)
    plugin.fail_key = target
    with pytest.raises(OSError, match="injected"):
        restore_archive_record(plugin, "archive-1", same_record)
    assert plugin.data == before
    plugin.fail_key = ""
    assert restore_archive_record(plugin, "archive-1", same_record)["success"] is True
    assert len(plugin.data[target]) == 1
    assert plugin.data["archive_records"] == []
    assert plugin.writes == [target, "archive_records"]


@pytest.mark.parametrize("source,target", [
    ("subscribe_history", "subscribe_records"),
    ("anti_cheat_log", "anti_cheat_logs"),
    ("observation", "rank_history_popular"),
])
def test_archive_cleanup_failure_is_safe_to_retry_without_duplicates(source, target):
    plugin = MemoryPlugin(source, record())
    original_archive = deepcopy(plugin.data["archive_records"])
    plugin.fail_key = "archive_records"
    with pytest.raises(OSError, match="injected"):
        restore_archive_record(plugin, "archive-1", same_record)
    assert plugin.data["archive_records"] == original_archive
    assert len(plugin.data[target]) == 1
    plugin.fail_key = ""
    assert restore_archive_record(plugin, "archive-1", same_record)["success"] is True
    assert plugin.data["archive_records"] == []
    assert len(plugin.data[target]) == 1


def test_missing_archive_does_not_write_anything():
    plugin = MemoryPlugin("subscribe_history", record())
    assert restore_archive_record(plugin, "missing", same_record)["success"] is False
    assert plugin.writes == []
