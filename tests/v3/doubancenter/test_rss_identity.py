"""RSS identity parsing and bounded, order-independent enrichment."""

from types import SimpleNamespace

import pytest

from app.plugins.doubancenter.adapter import rss
from app.plugins.doubancenter.service import rank_pipeline
from app.plugins.doubancenter.service import rank_snapshot


@pytest.mark.parametrize("value", [
    "https://movie.douban.com/subject/35322132/",
    "https://m.douban.com/movie/subject/35322132?from=rss#details",
    "https://www.douban.com/doubanapp/dispatch/movie/35322132",
    "https://www.douban.com/doubanapp/dispatch/tv/35322132?from=rss",
    "https://www.douban.com/dispatch/movie/35322132/",
    "https://m.douban.com/movie/35322132/",
    "https://m.douban.com/tv/35322132#details",
    "douban://douban.com/movie/35322132",
    "//movie.douban.com/subject/35322132/",
    "/subject/35322132/",
    "/dispatch/tv/35322132",
    "custom_rank:https://www.douban.com/doubanapp/dispatch/movie/35322132",
])
def test_subject_id_reads_supported_douban_links(value):
    assert rss.douban_subject_id(value) == "35322132"


@pytest.mark.parametrize("value", [
    None,
    "",
    "35322132",
    "https://www.themoviedb.org/movie/35322132",
    "https://example.com/subject/35322132/",
    "https://douban.com.example.com/movie/35322132",
    "https://notdouban.com/movie/35322132",
    "https://douban.com@evil.example/movie/35322132",
    "https://m.douban.com/movie/35322132oops",
    "https://m.douban.com/subject_collection/movie_hot/items",
    "https://www.douban.com/doubanapp/dispatch/book/35322132",
])
def test_subject_id_does_not_guess_foreign_or_invalid_ids(value):
    assert rss.douban_subject_id(value) == ""


@pytest.mark.parametrize("route", [
    "/douban/list/movie_hot?limit=20",
    "/douban/list/movie_hot/score=8?limit=20",
    "/douban/list/movie_real_time_hotest/score=7?filter=2026&limit=20",
])
def test_rank_rss_dispatch_links_need_no_rexxar_request(route):
    addr = "https://rsshub.example" + route
    requested = []
    document = """<rss><channel><title>Filtered rank</title>
      <link>https://movie.douban.com/</link>
      <item><title>Example A</title>
        <link>https://www.douban.com/doubanapp/dispatch/movie/35322132</link>
        <description>2026</description></item>
      <item><title>Example B</title>
        <link>https://m.douban.com/movie/35322133</link></item>
    </channel></rss>"""

    class Request:
        def __init__(self, **_kwargs):
            pass

        def get_res(self, url):
            requested.append(url)
            assert url == addr, "RSS links already contain IDs; no fallback is allowed"
            return SimpleNamespace(status_code=200, text=document)

    items = rss.fetch_rank(SimpleNamespace(_proxy=False), addr, request_utils_cls=Request)

    assert [item["doubanid"] for item in items] == ["35322132", "35322133"]
    assert requested == [addr]


def enrich(monkeypatch, items, remote_items, addr="https://rsshub.example/douban/list/movie_hot"):
    calls = []

    def remote(_plugin, collection, count, **_kwargs):
        calls.append((collection, count))
        return remote_items

    monkeypatch.setattr(rss, "_rexxar_items", remote)
    rss._enrich_douban_ids(SimpleNamespace(), addr, items)
    return calls


def test_enrichment_uses_unique_titles_not_positions(monkeypatch):
    items = [{"title": "Example A"}, {"title": "Example B"}]
    remote = [
        {"title": "Unrelated", "id": "100"},
        {"title": "EXAMPLE B", "id": "102"},
        {"title": "Example A", "id": "101"},
    ]

    calls = enrich(monkeypatch, items, remote)

    assert [item["doubanid"] for item in items] == ["101", "102"]
    assert calls == [("movie_hot", rss._DOUBAN_REXXAR_MAX_ITEMS)]


@pytest.mark.parametrize("items, remote", [
    ([{"title": "Same"}, {"title": "Same"}], [{"title": "Same", "id": "101"}]),
    ([{"title": "Same"}], [{"title": "Same", "id": "101"}, {"title": "Same", "id": "102"}]),
    ([{"title": "A-B"}], [{"title": "AB", "id": "101"}]),
    ([{"title": "Missing"}], []),
    ([{"title": "Missing"}], [{"title": "Other", "id": "101"}]),
    ([{"title": "Invalid"}], [{"title": "Invalid", "id": "not-an-id"}]),
])
def test_enrichment_skips_ambiguous_or_missing_matches(monkeypatch, items, remote):
    enrich(monkeypatch, items, remote)
    assert all(not item.get("doubanid") for item in items)


@pytest.mark.parametrize("rss_meta, remote_meta, expected", [
    ({"year": 2026}, {"year": "2025"}, None),
    ({"year": "2026"}, {"year": 2026}, "101"),
    ({"year": 2026}, {}, "101"),
    ({"mtype": "movie"}, {"type": "tv"}, None),
    ({"mtype": "tv"}, {"subtype": "movie"}, None),
    ({"mtype": "movie"}, {"type": "movie"}, "101"),
    ({"mtype": "unknown"}, {"type": "tv"}, "101"),
    ({"mtype": "tv"}, {"uri": "douban://douban.com/movie/101"}, None),
    ({"mtype": "movie"}, {"type": "movie", "subtype": "tv"}, None),
])
def test_enrichment_rejects_known_year_or_type_conflicts(monkeypatch, rss_meta, remote_meta, expected):
    items = [{"title": "Example", **rss_meta}]
    remote = [{"title": "Example", "id": "101", **remote_meta}]

    enrich(monkeypatch, items, remote)

    assert items[0].get("doubanid") == expected


def test_enrichment_preserves_existing_and_does_not_reuse_ids(monkeypatch):
    items = [
        {"title": "Existing", "doubanid": "101"},
        {"title": "Alias"},
        {"title": "New"},
    ]
    remote = [
        {"title": "Existing", "id": "999"},
        {"title": "Alias", "id": "101"},
        {"title": "New", "id": "102"},
    ]

    enrich(monkeypatch, items, remote)

    assert [item.get("doubanid") for item in items] == ["101", None, "102"]


@pytest.mark.parametrize("items, addr", [
    ([], "https://rsshub.example/douban/list/movie_hot"),
    ([{"title": "Known", "doubanid": "101"}], "https://rsshub.example/douban/list/movie_hot"),
    ([{"title": "Missing"}], "https://rsshub.example/douban/list/movie_hot/score=8?limit=20"),
    ([{"title": "Missing"}], "https://rsshub.example/bangumi/calendar"),
])
def test_enrichment_does_not_expand_request_scope(monkeypatch, items, addr):
    assert enrich(monkeypatch, items, [], addr=addr) == []


def test_existing_rank_record_can_recover_id_from_dispatch_link():
    assert rank_pipeline._record_douban_id({
        "unique": "custom_rank:https://www.douban.com/doubanapp/dispatch/movie/35322132",
    }) == "35322132"


def test_refreshed_snapshot_saves_id_without_losing_observation(monkeypatch):
    link = "https://www.douban.com/doubanapp/dispatch/movie/35322132"
    previous = {"title": "Example", "unique": "dc2_rank:" + link,
                "douban_id": None, "observing": True, "first_seen": "2026-10-18 12:00:00"}
    saved = []
    monkeypatch.setattr(rank_snapshot.storage, "read_rank_history", lambda *_: [previous])

    def save(_plugin, _key, history):
        saved.extend(history)
        return history

    monkeypatch.setattr(rank_snapshot.storage, "save_rank_history", save)
    rank_snapshot.merge_rank_items(
        object(), "custom_filtered",
        [{"title": "Example", "link": link, "doubanid": rss.douban_subject_id(link)}],
        {"name": "Filtered rank", "route": "/douban/list/movie_hot/score=8"},
        infer_media_type=lambda *_: "movie",
        recognize_item=lambda *_: None,
        preserve_existing_identity=lambda *_: None,
    )

    assert len(saved) == 1
    assert saved[0]["douban_id"] == "35322132"
    assert saved[0]["observing"] is True
    assert saved[0]["first_seen"] == previous["first_seen"]


def test_missing_ids_make_one_bounded_request():
    calls = []

    class Request:
        def __init__(self, **_kwargs):
            pass

        def get_res(self, url):
            calls.append(url)
            return SimpleNamespace(status_code=200, json=lambda: {"subject_collection_items": [
                {"title": "Other", "id": "100"},
                {"title": "Example", "uri": "douban://douban.com/movie/101", "year": "2026"},
            ]})

    items = [{"title": "Example", "year": 2026}]
    rss._enrich_douban_ids(
        SimpleNamespace(_proxy=False), "https://rsshub.example/douban/list/movie_hot?filter=2026",
        items, request_utils_cls=Request,
    )

    assert items[0]["doubanid"] == "101"
    assert calls == [
        "https://m.douban.com/rexxar/api/v2/subject_collection/movie_hot/items?playable=0&start=0&count=50",
    ]
