"""完播回调推进看过，停止、中途退出和取消已看不能冒充完播。"""

import copy
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter.adapter import folio_library
from app.plugins.doubancenter.model import folio_record
from app.plugins.doubancenter.service import folio, webhook
from app.plugins.doubancenter.storage import records as storage

from tests.v3.doubancenter.folio_fakes import FolioPlugin, mushoku_media


def _event(name, channel="emby", payload=None, **kwargs):
    """按宿主公开字段构造事件，不连接真实媒体服务器。"""
    return SimpleNamespace(event_data=SimpleNamespace(
        event=name, channel=channel, user_name="tester", save_reason=None,
        json_object=payload, **kwargs,
    ))


def _dispatch(plugin, event):
    """重放同一 Webhook 的两个生产处理器，而非直接传 played=True。"""
    webhook.handle_sync_log(plugin, event)
    webhook.handle_sync_played(
        plugin, event, sync_log=lambda **kwargs: webhook.handle_sync_log(plugin, **kwargs),
    )


@pytest.mark.parametrize("name,channel,payload,reason", [
    ("playback.stop", "emby", {"PlaybackInfo": {"PlayedToCompletion": True}}, None),
    ("PlaybackStop", "jellyfin", {"PlayedToCompletion": True}, None),
    ("UserDataSaved", "jellyfin", {"Played": True}, "PlaybackFinished"),
    ("UserDataSaved", "jellyfin", {"Played": True}, "TogglePlayed"),
    ("UserDataSaved", "jellyfin", {}, "TogglePlayed"),
    ("item.markplayed", "emby", {}, None),
    ("media.scrobble", "plex", {}, None),
])
def test_confirmed_completion_enters_played_handler(name, channel, payload, reason):
    plugin = SimpleNamespace(_enabled=True, _folio_enabled=True, _folio_user="tester")
    event = _event(name, channel, payload)
    event.event_data.save_reason = reason
    calls = []
    webhook.handle_sync_played(plugin, event, sync_log=lambda **kwargs: calls.append(kwargs))
    assert calls == [{"event": event, "played": True}]


@pytest.mark.parametrize("name,channel,payload,reason", [
    ("playback.stop", "emby", None, None),
    ("playback.stop", "emby", [], None),
    ("playback.stop", "emby", {"PlaybackInfo": None}, None),
    ("playback.stop", "emby", {"PlaybackInfo": []}, None),
    ("playback.stop", "emby", {"PlaybackInfo": {"PlayedToCompletion": False}}, None),
    ("playback.stop", "emby", {"PlaybackInfo": {"PlayedToCompletion": "false"}}, None),
    ("playback.stop", "emby", {"PlaybackInfo": {"PlayedToCompletion": "true"}}, None),
    ("playback.stop", "emby", {"PlaybackInfo": {"PlayedToCompletion": 1}}, None),
    ("playback.stop", "emby", {"Item": {"UserData": {"Played": True}}}, None),
    ("playback.stop", "emby", {"TranscodingInfo": {"CompletionPercentage": 100}}, None),
    ("playback.pause", "emby", {"PlaybackInfo": {"PlayedToCompletion": True}}, None),
    ("playback.start", "emby", {"PlaybackInfo": {"PlayedToCompletion": True}}, None),
    ("playback.stop", "unknown", {"PlaybackInfo": {"PlayedToCompletion": True}}, None),
    ("PlaybackStop", "jellyfin", {}, None),
    ("PlaybackStop", "jellyfin", {"PlayedToCompletion": False}, None),
    ("PlaybackStop", "jellyfin", {"PlayedToCompletion": "true"}, None),
    ("PlaybackStop", "jellyfin", {"PlayedToCompletion": 1}, None),
    ("PlaybackProgress", "jellyfin", {"PlayedToCompletion": True}, None),
    ("UserDataSaved", "jellyfin", {}, "PlaybackFinished"),
    ("UserDataSaved", "jellyfin", {"Played": False}, "PlaybackFinished"),
    ("UserDataSaved", "jellyfin", {"Played": "true"}, "PlaybackFinished"),
    ("UserDataSaved", "jellyfin", {"Played": True}, "PlaybackProgress"),
    ("UserDataSaved", "jellyfin", {"Played": False}, "TogglePlayed"),
    ("UserDataSaved", "jellyfin", {"Played": "false"}, "TogglePlayed"),
    ("system.serverstartup", "emby", {}, None),
])
def test_unconfirmed_events_do_not_enter_played_handler(name, channel, payload, reason):
    plugin = SimpleNamespace(_enabled=True, _folio_enabled=True, _folio_user="tester")
    event = _event(name, channel, payload, percentage=100)
    event.event_data.save_reason = reason
    calls = []
    webhook.handle_sync_played(plugin, event, sync_log=lambda **kwargs: calls.append(kwargs))
    assert calls == []


@pytest.mark.parametrize("enabled,folio_enabled,user", [
    (False, True, "tester"), (True, False, "tester"), (True, True, "other"),
    (True, True, None),
])
def test_completion_respects_enablement_and_user(enabled, folio_enabled, user):
    plugin = SimpleNamespace(_enabled=enabled, _folio_enabled=folio_enabled, _folio_user="tester")
    event = _event("playback.stop", payload={"PlaybackInfo": {"PlayedToCompletion": True}})
    event.event_data.user_name = user
    calls = []
    webhook.handle_sync_played(plugin, event, sync_log=lambda **kwargs: calls.append(kwargs))
    assert calls == []


@pytest.fixture
def playback_lab(monkeypatch):
    """保留事件路由、分季判定及去重，替换识别、查库和豆瓣写入。"""
    media, plugin, calls = mushoku_media(), FolioPlugin(), []
    plugin._enabled = plugin._folio_enabled = True
    plugin._folio_user = "tester"
    plugin._folio_first = False
    plugin._folio_exclude = ""
    season = {
        "reference": {"server": "lab", "series_id": "series", "season_id": "season"},
        "season": 3, "episode_count": 11, "episode_numbers": list(range(1, 12)),
        "air_date": "2026-07-04", "episodes": [],
    }
    monkeypatch.setattr(folio, "_series_context", lambda *args: {
        "title": media.title, "media_source": "themoviedb", "media_id": "94664",
    })
    monkeypatch.setattr(folio, "_recognize_media", lambda *args, **kwargs: media)
    monkeypatch.setattr(folio_library, "load_season", lambda *args, **kwargs: copy.deepcopy(season))
    monkeypatch.setattr(folio, "check_cookie_periodically", lambda *args: None)

    def write_status(plugin, title, status, item_type, processed, mediainfo, *, origin):
        calls.append(status)
        key = folio_record.origin_key(origin)
        processed[key] = {"origin": origin, "watch_status": status}
        storage.save_folio_data(plugin, processed)
        return True

    monkeypatch.setattr(folio, "_sync_to_douban", write_status)
    return plugin, calls


def _episode_event(name, *, channel="emby", complete=None, episode=11):
    payload = {"Item": {"Type": "Episode", "SeriesId": "series", "SeasonId": "season"}}
    if channel == "jellyfin":
        payload = {"ItemType": "Episode", "SeasonNumber": 3, "EpisodeNumber": episode}
        if complete is not None:
            payload["PlayedToCompletion"] = complete
    elif channel == "plex":
        payload = {"Metadata": {"type": "episode", "parentIndex": 3, "index": episode}}
    elif complete is not None:
        payload["PlaybackInfo"] = {"PlayedToCompletion": complete}
    return _event(
        name, channel=channel, payload=payload, item_name="Lab S03E11", item_path="/lab/episode.mkv",
        item_type="TV", media_type="Episode", server_name="lab", item_id="series",
        season_id=3, episode_id=episode,
    )


@pytest.mark.parametrize("channel,start_event,stop_event,finished_event,payload,reason,episode", [
    ("emby", "playback.start", "playback.stop", "playback.stop",
     {"PlaybackInfo": {"PlayedToCompletion": True}}, None, 11),
    ("jellyfin", "PlaybackStart", "PlaybackStop", "PlaybackStop",
     {"PlayedToCompletion": True}, None, 13),
    ("jellyfin", "PlaybackStart", "PlaybackStop", "UserDataSaved",
     {"Played": True}, "PlaybackFinished", 13),
    ("plex", "media.play", "media.stop", "media.scrobble", {}, None, 13),
])
def test_last_episode_natural_completion_promotes_watching_and_deduplicates(
    playback_lab, channel, start_event, stop_event, finished_event, payload, reason, episode,
):
    plugin, calls = playback_lab
    start = _episode_event(start_event, channel=channel, episode=episode)
    _dispatch(plugin, start)
    assert calls == ["do"]
    _dispatch(plugin, _episode_event(stop_event, channel=channel, complete=False, episode=episode))
    assert calls == ["do"]
    completion = _episode_event(finished_event, channel=channel, episode=episode)
    completion.event_data.save_reason = reason
    completion.event_data.json_object.update(payload)
    _dispatch(plugin, completion)
    assert calls == ["do", "collect"]
    _dispatch(plugin, completion)
    manual = _episode_event("UserDataSaved" if channel == "jellyfin" else "item.markplayed",
                            channel=channel, episode=episode)
    manual.event_data.save_reason = "TogglePlayed"
    manual.event_data.json_object["Played"] = True
    _dispatch(plugin, manual)
    _dispatch(plugin, start)
    assert calls == ["do", "collect"]
    assert next(iter(plugin.data["folio_data"].values()))["watch_status"] == "collect"


def test_nonfinal_episode_completion_does_not_mark_season_watched(playback_lab):
    plugin, calls = playback_lab
    _dispatch(plugin, _episode_event("playback.stop", complete=True, episode=10))
    assert calls == ["do"]


def test_missing_library_context_still_requires_confirmed_completion(playback_lab, monkeypatch):
    plugin, calls = playback_lab
    monkeypatch.setattr(folio_library, "playback_context", lambda *args: {})
    _dispatch(plugin, _episode_event("playback.start", episode=13))
    assert calls == ["do"]
    _dispatch(plugin, _episode_event("playback.stop", complete=True, episode=13))
    assert calls == ["do", "collect"]


def test_unknown_library_season_does_not_guess_completion(playback_lab, monkeypatch):
    plugin, calls = playback_lab
    monkeypatch.setattr(folio_library, "load_season", lambda *args, **kwargs: None)
    _dispatch(plugin, _episode_event("playback.stop", complete=True))
    assert calls == []
    waiting = next(iter(plugin.data["folio_wait"].values()))
    assert waiting["status"] == "do" and waiting["identity_status"] == "unresolved"
