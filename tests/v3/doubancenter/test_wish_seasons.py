"""想看季号经真实订阅服务透传，外部查询和数据写入均使用内存替身。"""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter.service import folio, subscription
from app.schemas.types import MediaSource, MediaType


@pytest.fixture
def wish_season_lab(monkeypatch):
    saved, checked, added, received = {}, [], [], []
    existing = {"active": set(), "history": set(), "library": set()}
    plugin = SimpleNamespace(
        get_data=lambda key: deepcopy(saved.get(key)),
        save_data=lambda key, value: saved.__setitem__(key, deepcopy(value)),
    )
    media = SimpleNamespace(
        title="信号", year="2016", type=MediaType.TV,
        media_source=MediaSource.TMDB, media_id="777", tmdb_id=777,
        get_poster_image=lambda: "", episode_group=None,
    )

    def exists(kind, season):
        checked.append((kind, season))
        return (season if season is not None else 1) in existing[kind]

    class FakeSubscribeChain:
        def exists(self, *, mediainfo, meta):
            assert mediainfo is media
            return exists("active", getattr(meta, "begin_season", None))

        def add(self, **kwargs):
            added.append(kwargs)
            existing["active"].add(kwargs["season"])
            return len(added), ""

    class FakeSubscribeOper:
        def exists(self, **kwargs):
            return exists("active", kwargs.get("season"))

        def exist_history(self, **kwargs):
            return exists("history", kwargs.get("season"))

    class FakeMediaServerOper:
        def exists(self, **kwargs):
            return exists("library", kwargs.get("season"))

    original_subscribe = subscription.add_subscription

    def subscribe(*args, **kwargs):
        received.append(kwargs)
        return original_subscribe(
            *args, **kwargs,
            subscribe_chain_cls=FakeSubscribeChain,
            subscribe_oper_cls=FakeSubscribeOper,
            media_server_oper_cls=FakeMediaServerOper,
        )

    monkeypatch.setattr(subscription, "add_subscription", subscribe)
    monkeypatch.setattr(subscription.observation, "cleanup_observe_logs", lambda *a, **kw: None)
    return SimpleNamespace(
        plugin=plugin, media=media, saved=saved, checked=checked,
        added=added, received=received, existing=existing,
    )


@pytest.mark.parametrize("existing_kind", ["active", "history", "library"])
@pytest.mark.parametrize("title", [
    "信号 第二季", "Signal Season 2", "Signal 2nd Season", "信号 S02",
    "信号 第二季 / Signal Season 2", "信号 / Signal Season 2",
])
def test_wish_second_season_is_not_blocked_by_first(wish_season_lab, title, existing_kind):
    """第一季在订阅、历史或媒体库中存在时，第二季仍应单独订阅。"""
    lab = wish_season_lab
    item = {"subject_id": "123", "title": title, "year": "2026", "link": "https://example.test/123"}
    lab.saved["folio_wish_queue"] = [item]
    lab.existing[existing_kind].add(1)

    folio.process_wish_queue(lab.plugin, recognize=lambda *_: lab.media)

    assert len(lab.added) == 1
    assert lab.added[0]["season"] == 2
    assert lab.added[0]["media_id"] == "777"
    assert lab.checked and {season for _, season in lab.checked} == {2}
    assert lab.received[0]["meta"].org_string == title.split(" / ", 1)[0]
    assert lab.received[0]["meta"].year == "2026"
    assert lab.received[0]["record_title"] == title
    assert lab.received[0]["source_link"] == item["link"]
    assert lab.saved["subscribe_records"][0]["title"] == title
    assert lab.saved["subscribe_records"][0]["season"] == 2
    assert lab.saved["folio_wish_queue"] == []
    assert len(lab.saved["folio_wish_processed"]) == 1

    lab.saved["folio_wish_queue"] = [item]
    folio.process_wish_queue(lab.plugin, recognize=lambda *_: lab.media)
    assert len(lab.added) == 1
    assert lab.saved["folio_wish_queue"] == []
    assert 1 in lab.existing[existing_kind]


@pytest.mark.parametrize("title,media_type,season", [
    ("信号", MediaType.TV, None),
    ("1899", MediaType.TV, None),
    ("Dune Part Two", MediaType.MOVIE, None),
    ("信号 S00", MediaType.TV, 0),
])
def test_wish_preserves_movies_unmarked_titles_and_specials(
    wish_season_lab, title, media_type, season,
):
    """无季号不猜测，电影不凭续作名分季，特别篇保留零季。"""
    lab = wish_season_lab
    lab.media.type = media_type
    lab.saved["folio_wish_queue"] = [{"subject_id": "123", "title": title, "year": "2026"}]

    folio.process_wish_queue(lab.plugin, recognize=lambda *_: lab.media)

    assert len(lab.added) == 1
    assert lab.added[0]["season"] == season
    assert lab.added[0]["mtype"] == media_type
    assert lab.checked and {value for _, value in lab.checked} == {season}
    assert lab.received[0]["meta"].year == "2026"
