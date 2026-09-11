"""真实完整季与 Cours 错位、单季单档案及播放时间回归。"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter.adapter import folio_library, folio_media
from app.plugins.doubancenter.controller import schemas as api_schemas
from app.plugins.doubancenter.model import folio_record
from app.plugins.doubancenter.service import folio, folio_repair, folio_watch

from tests.v3.doubancenter.folio_fakes import (
    MUSHOKU_SUBJECTS,
    FolioMediaChain,
    FolioPlugin,
    mushoku_media,
)

SUBJECTS = [*MUSHOKU_SUBJECTS,
    {"id": "36576576", "title": "无职转生Ⅱ 到了异世界就拿出真本事 Part 2", "year": "2024",
     "type": "tv", "is_tv": True, "episodes_count": 12, "pubdate": ["2024-04-07"]},
    {"id": "35460732", "title": "无职转生Ⅲ 到了异世界就拿出真本事", "year": "2026",
     "type": "tv", "is_tv": True, "episodes_count": 14, "pubdate": ["2026-07-04"]},
]


def _season(number):
    """使用本次实例已确认的季条目、集数与首尾播出日期。"""
    count, dates = {
        1: (23, [(1, "2021-01-11"), (12, "2021-10-04"), (23, "2021-12-20")]),
        2: (24, [(1, "2023-07-10"), (13, "2024-04-08"), (24, "2024-07-01")]),
        3: (11, [(1, "2026-07-04"), (11, "2026-09-07")]),
    }[number]
    return {"reference": {"server": "Embyserver", "series_id": "72893", "season_id": str({1: 72894, 2: 72960, 3: 73028}[number])},
            "season": number, "episode_count": count, "episode_numbers": list(range(1, count + 1)),
            "air_date": dates[0][1], "episodes": [{"episode": episode, "air_date": date} for episode, date in dates]}


def _origin(number):
    return folio_library.bind_season(folio._playback_origin(mushoku_media(), "TV", number), _season(number))


@pytest.mark.parametrize("number,subject_id,related", [(1, "30513783", ["30513783", "35306636"]),
    (2, "35460731", ["35460731", "36576576"]), (3, "35460732", ["35460732"])])
def test_library_season_overrides_cours_without_splitting_parts(number, subject_id, related):
    media = mushoku_media()
    result = folio_media.resolve_tv_subject(FolioMediaChain(media, SUBJECTS), media, _origin(number))
    assert result["resolved"] is True
    assert result["subject_id"] == subject_id
    assert result["identity_scope"] == "library_season"
    assert result["facts"]["episode_group"] == ""
    assert result["facts"]["episode_count"] == _season(number)["episode_count"]
    assert [item["subject_id"] for item in result["related_subjects"]] == related


def test_timeline_keeps_library_seasons_distinct_and_merges_part_aliases():
    base = {"subject_id": "30513783", "media_id": "30513783", "media_source": "douban", "type": "TV",
            "timestamp": "2026-08-17 20:12:05", "identity_status": "verified", "identity_scope": "library_season"}
    data = {"first": {**base, "origin": _origin(1), "subject_name": "无职转生 Part.1"},
            "part_alias": {**base, "origin": _origin(1), "subject_id": "35306636", "media_id": "35306636",
                           "timestamp": "2026-08-21 02:34:44", "subject_name": "无职转生 Part.2"},
            "second": {**base, "origin": _origin(2), "subject_name": "无职转生Ⅱ Part.1"},
            "third": {**base, "origin": _origin(3), "subject_name": "无职转生Ⅲ"}}
    before = copy.deepcopy(data)
    result = folio_record.timeline_records(data)
    assert len(result) == 3 and data == before
    assert all("Part" not in row["display_title"] for row in result.values())
    first = next(row for row in result.values() if row["origin"]["season"] == 1)
    assert first["timestamp"] == "2026-08-17 20:12:05" and first["subject_id"] == "30513783"


def test_library_repair_revalidates_wrong_verified_identity_and_preserves_old_sync(monkeypatch, tmp_path):
    media = mushoku_media()
    chain = FolioMediaChain(media, SUBJECTS)
    monkeypatch.setattr(folio_repair, "MediaChain", lambda: chain)
    monkeypatch.setattr(folio_library, "load_season", lambda plugin, origin, **kwargs: _season(origin["season"]))
    data, targets = {}, []
    first_dates = ["2026-08-17 20:12:05", "2026-09-02 02:37:21", "2026-09-10 03:13:25"]
    for number, old in enumerate(MUSHOKU_SUBJECTS, 1):
        key = f"library-{number}"
        data[key] = {"subject_id": old["id"], "media_id": old["id"], "media_source": "douban",
                     "subject_name": old["title"], "timestamp": "2026-09-10 04:00:00", "type": "TV",
                     "identity_status": "verified", "identity_scope": "season",
                     "origin": folio._playback_origin(media, "TV", number)}
        targets.append({"key": key, "media_source": "themoviedb", "media_id": "94664", "season": number,
                        "episode_group": "", "library_season": True,
                        "first_played_at": first_dates[number - 1], "time_evidence": "verified log"})
    plugin = FolioPlugin(data, tmp_path)
    plan = folio_repair.preview(plugin, targets)
    assert plan["ready"] and plan["changed"] == 3
    assert plugin.data["folio_data"] == data
    assert folio_repair.apply(plugin, plan["plan_id"])["updated"] == 3
    rows = list(plugin.data["folio_data"].values())
    assert [row["subject_id"] for row in rows] == ["30513783", "35460731", "35460732"]
    assert [row["timestamp"] for row in rows] == first_dates
    assert all(row["last_synced_at"] == "2026-09-10 04:00:00" for row in rows)
    assert len(folio_record.timeline_records(plugin.data["folio_data"])) == 3
    assert folio_repair.preview(plugin, targets)["changed"] == 0


def test_first_episode_date_survives_skip_retry_and_marked_events(monkeypatch):
    plugin, media = FolioPlugin(), mushoku_media()
    plugin._folio_first = True
    chain = FolioMediaChain(media, SUBJECTS)
    monkeypatch.setattr(folio, "MediaChain", lambda: chain)
    monkeypatch.setattr(folio, "_series_context", lambda *args: {"title": media.title, "media_source": "themoviedb", "media_id": "94664"})
    monkeypatch.setattr(folio, "_recognize_media", lambda *args, **kwargs: media)
    monkeypatch.setattr(folio_library, "load_season", lambda *args, **kwargs: _season(2))
    calls = []

    class Account:
        def __init__(self, **kwargs):
            pass

        def set_watching_status(self, **kwargs):
            calls.append(kwargs)
            return len(calls) > 1

    monkeypatch.setattr(folio, "DoubanApi", Account)
    event = SimpleNamespace(item_name=media.title, item_type="TV", season_id=2, episode_id=1,
                            server_name="Embyserver", item_id="72893",
                            json_object={"Item": {"SeriesId": "72893", "SeasonId": "72960"}, "Date": "2026-09-02T02:37:21"})
    processed = {}
    folio._process_tv_show(plugin, event, processed)
    assert not processed and not calls
    event.episode_id = 2
    event.json_object["Date"] = "2026-09-02T03:01:47"
    folio._process_tv_show(plugin, event, processed)
    assert not processed and len(calls) == 1
    folio._process_tv_show(plugin, event, processed)
    assert len(processed) == 1 and len(calls) == 2
    record = next(iter(processed.values()))
    assert record["timestamp"] == "2026-09-02 02:37:21" and record["subject_id"] == "35460731"
    event.episode_id = 24
    event.json_object["Date"] = "2026-09-09T23:57:02"
    folio._process_tv_show(plugin, event, processed, played=True)
    record = next(iter(processed.values()))
    assert record["timestamp"] == "2026-09-02 02:37:21"
    assert record["last_marked_at"] == "2026-09-09 23:57:02" and record["watch_status"] == "collect"
    assert record["last_synced_at"] != record["timestamp"]


def test_started_last_library_episode_is_not_a_completion(monkeypatch):
    media, plugin = mushoku_media(), FolioPlugin()
    plugin._folio_first = False
    monkeypatch.setattr(folio, "_series_context", lambda *args: {"title": media.title, "media_source": "themoviedb", "media_id": "94664"})
    monkeypatch.setattr(folio, "_recognize_media", lambda *args, **kwargs: media)
    monkeypatch.setattr(folio_library, "load_season", lambda *args, **kwargs: _season(3))
    calls = []
    monkeypatch.setattr(folio, "_sync_to_douban", lambda plugin, title, status, *args, **kwargs: calls.append(status))
    event = SimpleNamespace(item_name=media.title, item_type="TV", season_id=3, episode_id=11,
                            server_name="Embyserver", item_id="72893", json_object={"Item": {"SeriesId": "72893", "SeasonId": "73028"}})
    folio._process_tv_show(plugin, event, {})
    assert calls == ["do"]


def test_time_restore_requires_evidence_and_rejects_later_dates():
    record = {"timestamp": "2026-09-02 03:01:50"}
    with pytest.raises(ValueError, match="来源"):
        folio_watch.restore_first_playback(record, "2026-09-02 02:37:21", "")
    with pytest.raises(ValueError, match="不能晚于"):
        folio_watch.restore_first_playback(record, "2026-09-03 02:37:21", "verified log")


def test_old_cours_retry_uses_repaired_library_identity_without_promoting_old_status(monkeypatch):
    origin = _origin(3)
    old_origin = folio._playback_origin(mushoku_media(), "TV", 3)
    record = {"origin": origin, "subject_id": "35460732", "subject_name": "无职转生Ⅲ",
              "media_source": "douban", "media_id": "35460732", "type": "电视剧",
              "identity_status": "verified", "identity_scope": "library_season",
              "timestamp": "2026-09-10 03:13:25", "first_played_at": "2026-09-10 03:13:25",
              "poster_path": "https://img3.doubanio.com/third.webp"}
    plugin = FolioPlugin({"old-title": record})
    plugin._wait_process = {"old-waiting": {"origin": old_origin, "subject_id": "35460731",
                           "identity_status": "verified", "status": "collect"}}
    calls = []

    class Account:
        def __init__(self, **kwargs):
            pass

        def set_watching_status(self, **kwargs):
            calls.append(kwargs)
            return True

    monkeypatch.setattr(folio, "DoubanApi", Account)
    processed = plugin.get_data("folio_data")
    assert folio._sync_to_douban(plugin, "old-title", "do", "TV", processed, origin=old_origin)
    assert [(call["subject_id"], call["status"]) for call in calls] == [("35460732", "do")]
    assert len(processed) == 1 and not plugin._wait_process
    assert processed["old-title"]["timestamp"] == record["timestamp"]


def test_library_lookup_failure_does_not_fall_back_to_wrong_cours(monkeypatch):
    plugin, media = FolioPlugin(), mushoku_media()
    plugin._folio_first = False
    monkeypatch.setattr(folio, "_series_context", lambda *args: {"title": media.title, "media_source": "themoviedb", "media_id": "94664"})
    monkeypatch.setattr(folio, "_recognize_media", lambda *args, **kwargs: media)
    monkeypatch.setattr(folio_library, "load_season", lambda *args, **kwargs: None)
    monkeypatch.setattr(folio, "_sync_to_douban", lambda *args, **kwargs: pytest.fail("不能按外部 Cours 继续写入"))
    event = SimpleNamespace(item_name=media.title, item_type="TV", season_id=3, episode_id=2,
                            server_name="Embyserver", item_id="72893", json_object={
                                "Item": {"SeriesId": "72893", "SeasonId": "73028"}, "Date": "2026-09-10T03:36:19"})
    folio._process_tv_show(plugin, event, {})
    waiting = next(iter(plugin._wait_process.values()))
    assert waiting["identity_status"] == "unresolved" and waiting["origin"]["library_season"] == {}
    observed = next(iter(plugin.data[folio_watch.TIMES_KEY].values()))
    assert observed["first_played_at"] == "2026-09-10 03:36:19"


def test_legacy_retry_resolves_library_before_unrepaired_cours_can_duplicate(monkeypatch):
    """复现真实旧队列：重试缺服务器和剧集组，历史记录尚未手动迁移。"""
    media = mushoku_media()
    old_origin = folio._playback_origin(media, "TV", 3)
    record = {"origin": old_origin, "subject_id": "35460731", "subject_name": "无职转生Ⅱ",
              "media_source": "douban", "media_id": "35460731", "type": "电视剧",
              "identity_status": "verified", "identity_scope": "season",
              "timestamp": "2026-09-10 03:36:20"}
    plugin = FolioPlugin({"old-title": record})
    retry_origin = {**old_origin, "episode_group": ""}
    plugin._wait_process = {"old-retry": {"origin": retry_origin, "status": "do", "type": "TV"}}
    monkeypatch.setattr(folio_library, "load_season", lambda *args, **kwargs: _season(3))
    monkeypatch.setattr(folio, "MediaChain", lambda: FolioMediaChain(media, SUBJECTS))
    calls = []

    def mark(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(folio, "DoubanApi", lambda **kwargs: SimpleNamespace(set_watching_status=mark))
    processed = plugin.get_data("folio_data")
    assert folio._sync_to_douban(plugin, "old-title", "do", "TV", processed, origin=retry_origin)
    assert list(processed) == ["old-title"] and not plugin._wait_process
    assert calls[0]["subject_id"] == "35460732"
    assert processed["old-title"]["origin"]["mediaserver"]["season_id"] == "73028"
    assert processed["old-title"]["timestamp"] == record["timestamp"]


@pytest.fixture
def merge_plugin(monkeypatch, tmp_path):
    """模拟已修复主记录与旧队列在修复窗口内新增的同季记录。"""
    record = {"origin": _origin(3), "subject_id": "35460732", "subject_name": "无职转生Ⅲ",
              "media_source": "douban", "media_id": "35460732", "type": "电视剧",
              "identity_status": "verified", "identity_scope": "library_season",
              "timestamp": "2026-09-10 03:13:25", "first_played_at": "2026-09-10 03:13:25",
              "last_synced_at": "2026-09-10 03:36:20", "timestamp_source": "verified_playback_evidence"}
    alias = {**record, "origin": {"media_source": "themoviedb", "media_id": "94664", "type": "tv",
                                  "season": 3, "episode_group": ""},
             "identity_scope": "season", "timestamp": "2026-09-11 12:55:13",
             "last_synced_at": "2026-09-11 12:55:13", "watch_status": "do", "custom": {"keep": True}}
    alias.pop("first_played_at")
    plugin = FolioPlugin({"main": record, "legacy-retry": alias,
                          "unrelated": {"subject_id": "other", "timestamp": "2026-09-11 12:55:00"}}, tmp_path)
    target = {"key": "main", "media_source": "themoviedb", "media_id": "94664", "type": "tv",
              "season": 3, "episode_group": "", "library_season": True, "merge_keys": ["legacy-retry"]}
    monkeypatch.setattr(folio_repair, "MediaChain", lambda: FolioMediaChain(mushoku_media(), SUBJECTS))
    monkeypatch.setattr(folio_library, "load_season", lambda *args, **kwargs: _season(3))
    return plugin, target


def test_explicit_same_library_alias_merge_is_backed_up_and_idempotent(merge_plugin):
    plugin, target = merge_plugin
    before = plugin.get_data("folio_data")
    plan = folio_repair.preview(plugin, [target])
    assert plan["ready"] and plan["changed"] == 1
    assert plan["timeline_before"] == 3 and plan["timeline_after"] == 2
    assert plugin.get_data("folio_data") == before
    response = api_schemas.FolioRepairPreviewData.model_validate(plan).model_dump()
    assert response["items"][0]["merge_before"] == {"legacy-retry": before["legacy-retry"]}
    result = folio_repair.apply(plugin, plan["plan_id"])
    assert result["updated"] == result["merged"] == 1 and result["raw_count"] == 2
    assert json.loads(Path(result["backup_path"]).read_text(encoding="utf-8"))["data"] == before
    after = plugin.get_data("folio_data")
    assert after["unrelated"] == before["unrelated"] and "legacy-retry" not in after
    assert after["main"]["timestamp"] == before["main"]["timestamp"]
    assert after["main"]["last_synced_at"] == before["legacy-retry"]["last_synced_at"]
    assert after["main"]["merged_aliases"] == {"legacy-retry": before["legacy-retry"]}
    assert folio_repair.preview(plugin, [target])["changed"] == 0
    assert folio_repair.apply(plugin, plan["plan_id"])["merged"] == 0


@pytest.mark.parametrize("mismatch", ["season", "server", "subject"])
def test_library_alias_merge_rejects_other_identity(merge_plugin, mismatch):
    plugin, target = merge_plugin
    alias = plugin.data["folio_data"]["legacy-retry"]
    if mismatch == "season":
        alias["origin"]["season"] = 2
    elif mismatch == "server":
        alias["origin"]["mediaserver"] = {**_season(3)["reference"], "server": "Other"}
    else:
        alias["subject_id"] = "30513783"
    before = plugin.get_data("folio_data")
    with pytest.raises(ValueError, match="不属于"):
        folio_repair.preview(plugin, [target])
    assert plugin.get_data("folio_data") == before


@pytest.mark.parametrize("change", ["updated_alias", "new_native_alias"])
def test_library_alias_merge_refuses_concurrent_changes(merge_plugin, change):
    plugin, target = merge_plugin
    plan = folio_repair.preview(plugin, [target])
    if change == "updated_alias":
        plugin.data["folio_data"]["legacy-retry"]["timestamp"] = "2026-09-11 13:00:00"
    else:
        plugin.data["folio_data"]["unexpected"] = copy.deepcopy(plugin.data["folio_data"]["legacy-retry"])
    before = plugin.get_data("folio_data")
    with pytest.raises(ValueError, match="预览后"):
        folio_repair.apply(plugin, plan["plan_id"])
    assert plugin.get_data("folio_data") == before
    assert list(plugin.data_path.iterdir()) == []
