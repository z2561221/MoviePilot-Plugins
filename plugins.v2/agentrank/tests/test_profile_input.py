"""AgentRank subscription adapter and profile-input normalization tests."""

import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_profile_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

adapter_module = importlib.import_module(f"{PACKAGE_NAME}.adapter.subscription")
service_module = importlib.import_module(f"{PACKAGE_NAME}.service.profile_input")

SubscriptionAdapter = adapter_module.SubscriptionAdapter
ProfileInputService = service_module.ProfileInputService


class FakeSubscribeOper:
    """Return deliberately mixed records while recording scoped calls."""

    def __init__(self, records):
        self.records = list(records)
        self.calls = []

    def list_by_username(self, username, state=None, mtype=None):
        self.calls.append((username, state, mtype))
        return list(self.records)


def _record(**values):
    defaults = {
        "username": "alice",
        "name": "默认标题",
        "year": "2025",
        "type": "电视剧",
        "tmdbid": None,
        "doubanid": None,
        "bangumiid": None,
        "tvdbid": None,
        "imdbid": None,
        "mediaid": None,
        "vote": None,
        "date": "2026-01-01 10:00:00",
        "note": None,
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


def test_adapter_calls_only_current_core_username_query_and_filters_mixed_rows():
    """Alice input never scans or accepts an explicitly Bob-owned row."""
    oper = FakeSubscribeOper(
        [
            _record(username="alice", name="Alice Show", tmdbid=1),
            _record(username="bob", name="Bob Show", tmdbid=2),
        ]
    )
    adapter = SubscriptionAdapter(oper=oper)

    records = adapter.list_by_username("alice")

    assert oper.calls == [("alice", None, None)]
    assert [record.name for record in records] == ["Alice Show"]


def test_profile_input_normalizes_available_movie_tv_and_anime_fields():
    """Available IDs and descriptive metadata survive normalization."""
    records = [
        _record(
            name="Movie",
            type="电影",
            tmdbid=11,
            year="2024",
            vote=8.7,
            note={
                "genres": ["悬疑", "犯罪"],
                "actors": ["演员甲"],
                "directors": ["导演乙"],
                "regions": ["中国大陆"],
            },
        ),
        _record(name="TV", type="电视剧", doubanid="22", year=None),
        _record(name="Anime", type="动漫", bangumiid=33, media_category="动画"),
    ]
    service = ProfileInputService(SubscriptionAdapter(FakeSubscribeOper(records)))

    result = service.collect("alice", minimum_samples=1)

    assert result.status == "ready"
    assert [sample.media_type for sample in result.samples] == ["movie", "tv", "anime"]
    movie = result.samples[0]
    assert movie.ids == {"tmdb": "11"}
    assert movie.genres == ["悬疑", "犯罪"]
    assert movie.actors == ["演员甲"]
    assert movie.directors == ["导演乙"]
    assert movie.regions == ["中国大陆"]
    assert movie.rating == 8.7
    assert result.samples[1].year is None


def test_profile_input_stably_deduplicates_ids_and_keeps_newest_record():
    """Duplicate media identities collapse after newest-first ordering."""
    records = [
        _record(name="Old", tmdbid=99, date="2024-01-01 00:00:00"),
        _record(name="New", tmdbid=99, date="2026-01-01 00:00:00"),
        _record(name="Fallback", tmdbid=None, year="2025", type="电影", date="2025-01-01 00:00:00"),
        _record(name="Fallback", tmdbid=None, year="2025", type="电影", date="2025-01-01 00:00:00"),
    ]
    service = ProfileInputService(SubscriptionAdapter(FakeSubscribeOper(records)))

    result = service.collect("alice", minimum_samples=1)

    assert [sample.title for sample in result.samples] == ["New", "Fallback"]
    assert result.samples[0].stable_id == "tmdb:99"
    assert result.samples[1].stable_id == "fallback:movie:Fallback:2025"


def test_recent_scope_and_limit_are_applied_before_minimum_sample_gate():
    """Recent mode filters old records and returns an explicit insufficient state."""
    records = [
        _record(name="Recent", tmdbid=1, date="2026-06-01 00:00:00"),
        _record(name="Old", tmdbid=2, date="2020-01-01 00:00:00"),
        _record(name="No Date", tmdbid=3, date=None),
    ]
    service = ProfileInputService(SubscriptionAdapter(FakeSubscribeOper(records)))

    result = service.collect(
        "alice",
        profile_scope="recent",
        recent_days=180,
        sample_limit=10,
        minimum_samples=2,
        now=datetime(2026, 7, 12, tzinfo=timezone.utc),
    )

    assert result.status == "sample_insufficient"
    assert [sample.title for sample in result.samples] == ["Recent"]
    assert result.sample_count == 1
    assert result.minimum_samples == 2


def test_missing_title_is_rejected_without_aborting_other_samples():
    """Malformed subscriptions are counted while other valid rows remain usable."""
    records = [
        _record(name=None, tmdbid=1),
        _record(name="Valid", tmdbid=2, note=[1, 2, 3]),
    ]
    service = ProfileInputService(SubscriptionAdapter(FakeSubscribeOper(records)))

    result = service.collect("alice", minimum_samples=1)

    assert result.status == "ready"
    assert [sample.title for sample in result.samples] == ["Valid"]
    assert result.rejected_count == 1
