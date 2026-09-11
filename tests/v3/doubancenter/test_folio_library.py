"""媒体库季海报的身份匹配、鉴权隔离、回退与只读展示回归。"""

import copy
import io
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from app.plugins.doubancenter.adapter import folio_library
from app.plugins.doubancenter.model import folio_record
from app.plugins.doubancenter.service import dashboard_folio, folio
from PIL import Image

from tests.v3.doubancenter.folio_fakes import FolioPlugin, mushoku_media


def _record(season=2):
    """构造已核实的分段档案，原始海报用于回退。"""
    return {
        "subject_id": "35306636", "media_source": "douban", "media_id": "35306636",
        "subject_name": "无职转生 Part.2", "type": "电视剧", "timestamp": "2026-09-10 10:00:00",
        "identity_status": "verified", "identity_scope": "season",
        "poster_path": "https://img3.doubanio.com/part2.webp",
        "origin": {"type": "tv", "media_source": "themoviedb", "media_id": "94664",
                   "season": season, "episode_group": "cours"},
    }


@pytest.fixture
def library(monkeypatch):
    """用带不同整剧和季条目的 HTTP 替身隔离真实媒体库与凭据。"""
    content = io.BytesIO()
    Image.new("RGB", (4, 6), "blue").save(content, format="JPEG")
    service = SimpleNamespace(name="Embyserver", type="emby", config=SimpleNamespace(config={
        "host": "http://library.invalid:8096", "apikey": "test-library-key",
    }))
    state = SimpleNamespace(
        services={service.name: service}, calls=[], fail=False, content=content.getvalue(),
        series=[{"Id": "series-1", "Type": "Series", "ProviderIds": {"Tmdb": "94664"},
                 "ImageTags": {"Primary": "whole-show"}}],
        seasons=[{"Id": f"season-{number}", "Type": "Season", "SeriesId": "series-1",
                  "IndexNumber": number, "ImageTags": {"Primary": f"poster-{number}"}}
                 for number in (1, 2, 3)],
    )

    def request_factory(headers=None, **options):
        """模拟真实网络接口并记录认证是否留在服务端。"""
        def get(url, params=None, **kwargs):
            """返回整剧、季列表或图片，支持故障注入。"""
            state.calls.append((url, params, headers, kwargs, options))
            if state.fail:
                return SimpleNamespace(status_code=503)
            if "/Images/" in url:
                return SimpleNamespace(status_code=200, content=state.content)
            items = state.seasons if "/Seasons" in url else state.series
            return SimpleNamespace(status_code=200, json=lambda: {
                "Items": copy.deepcopy(items), "TotalRecordCount": len(items),
            })
        return SimpleNamespace(get_res=get)

    monkeypatch.setattr(folio_library, "RequestUtils", request_factory)
    monkeypatch.setattr(folio_library, "MediaServerHelper", lambda: SimpleNamespace(
        get_services=lambda **kwargs: state.services,
    ))
    monkeypatch.setattr(folio_library.SecurityUtils, "sign_url", lambda url: url + "#mp_sig=test")
    return state


def test_group_season_uses_matching_library_primary_and_keeps_raw_records(library):
    """播放第 2 段取媒体库第 2 季，两个 UI 共用代理且不改持久化档案。"""
    plugin = FolioPlugin({"第二段": _record()})
    before = copy.deepcopy(plugin.data)
    data = dashboard_folio.get_folio_data(plugin)["data"]
    record = next(iter(data.values()))
    proxy = urlsplit(record["poster_path"])
    image_url = parse_qs(proxy.query)["imgurl"][0]
    assert proxy.path == "/api/v1/system/img/0"
    assert "/Items/season-2/Images/Primary?" in image_url
    assert "tag=poster-2" in image_url and "mp_sig=test" in image_url
    assert "test-library-key" not in str(data) and "api_key" not in image_url
    assert record["poster_fallback_path"] == _record()["poster_path"]
    assert record["library_poster"]["season_id"] == "season-2"
    assert record["timestamp"] == _record()["timestamp"]
    assert record["subject_id"] == _record()["subject_id"]
    assert plugin.data == before
    requests = len(library.calls)
    assert dashboard_folio.get_folio_data(plugin, raw=True)["data"] == before["folio_data"]
    cards = dashboard_folio.get_timeline_items(plugin)
    assert record["poster_path"] in str(cards)
    assert len(library.calls) == requests
    assert library.calls[0][1]["AnyProviderIdEquals"] == "tmdb.94664"
    assert library.calls[0][2] == {"X-Emby-Token": "test-library-key"}
    assert library.calls[-1][2] is None
    assert all(call[3]["allow_redirects"] is False for call in library.calls)


@pytest.mark.parametrize("failure", ["missing", "wrong_parent", "wrong_type", "wrong_number", "duplicate",
                                      "wrong_provider", "bad_image", "bad_png", "offline", "multiple_servers"])
def test_unverified_or_unavailable_library_art_keeps_existing_poster(library, failure):
    """错误条目、歧义和不可用图片都必须保留原有海报。"""
    if failure == "missing":
        library.seasons[1]["ImageTags"] = {}
    elif failure == "wrong_parent":
        library.seasons[1]["SeriesId"] = "other-show"
    elif failure == "wrong_type":
        library.seasons[1]["Type"] = "Episode"
    elif failure == "wrong_number":
        library.seasons[1]["IndexNumber"] = 9
    elif failure == "duplicate":
        library.series.append({**library.series[0], "Id": "another-copy"})
    elif failure == "wrong_provider":
        library.series[0]["ProviderIds"]["Tmdb"] = "4285"
    elif failure == "bad_image":
        library.content = b"<html>login required</html>"
    elif failure == "bad_png":
        buffer = io.BytesIO()
        Image.new("RGB", (4, 6), "blue").save(buffer, format="PNG")
        content = bytearray(buffer.getvalue())
        chunk = content.index(b"IDAT")
        size = int.from_bytes(content[chunk - 4:chunk], "big")
        content[chunk + 4 + size] ^= 1
        library.content = bytes(content)
    elif failure == "offline":
        library.fail = True
    elif failure == "multiple_servers":
        library.services["Other"] = SimpleNamespace(
            name="Other", type="emby", config=library.services["Embyserver"].config,
        )
    records = {"记录": _record()}
    assert folio_library.project_posters(FolioPlugin(), records) == records


def test_exact_playback_server_and_season_id_are_respected(library):
    """已保存播放上下文时不能跨服务器或静默改用另一个季条目。"""
    record = _record()
    record["origin"]["mediaserver"] = {"server": "Embyserver", "series_id": "series-1", "season_id": "season-2"}
    result = folio_library.project_posters(FolioPlugin(), {"record": record})
    assert result["record"]["poster_source"] == "mediaserver"
    assert library.calls[0][1]["Ids"] == "series-1"
    record["origin"]["mediaserver"]["season_id"] = "season-3"
    assert folio_library.project_posters(FolioPlugin(), {"record": record}) == {"record": record}
    record["origin"]["mediaserver"]["server"] = "missing-server"
    assert folio_library.project_posters(FolioPlugin(), {"record": record}) == {"record": record}


def test_old_records_without_playback_evidence_and_movies_do_not_query(library):
    """不得从标题猜季，也不将电影套进季海报查询。"""
    old = _record()
    del old["origin"]
    records = {"第2季": old, "movie": {**_record(), "type": "电影"},
               "unresolved": {**_record(), "identity_status": "unresolved"}}
    assert folio_library.project_posters(FolioPlugin(), records) == records
    assert library.calls == []


def test_cache_is_instance_scoped_and_refreshes_changed_image_tags(library, monkeypatch):
    """缓存抑制重复请求，到期后能跟随季海报更新，停用服务立即回退。"""
    now = [100.0]
    monkeypatch.setattr(folio_library.time, "monotonic", lambda: now[0])
    plugin = FolioPlugin()
    records = {"record": _record()}
    first = folio_library.project_posters(plugin, records)
    count = len(library.calls)
    assert folio_library.project_posters(plugin, records) == first
    assert len(library.calls) == count
    folio_library.project_posters(FolioPlugin(), records)
    assert len(library.calls) > count
    library.seasons[1]["ImageTags"]["Primary"] = "new-poster"
    now[0] += folio_library.CACHE_SECONDS + 1
    updated = folio_library.project_posters(plugin, records)
    assert updated["record"]["library_poster"]["image_tag"] == "new-poster"
    assert updated["record"]["poster_path"] != first["record"]["poster_path"]
    library.services.clear()
    assert folio_library.project_posters(plugin, records) == records


def test_playback_persists_raw_season_item_id_as_library_identity(monkeypatch):
    """真实播放入口保存 SeasonId，实际入库季覆盖识别缓存的 Cours。"""
    media, plugin, captured = mushoku_media(), FolioPlugin(), {}
    plugin._folio_first = False
    monkeypatch.setattr(folio, "_series_context", lambda *args: {
        "title": media.title, "media_source": "themoviedb", "media_id": "94664",
    })
    monkeypatch.setattr(folio, "_recognize_media", lambda *args, **kwargs: media)
    monkeypatch.setattr(folio_library, "load_season", lambda *args, **kwargs: {
        "reference": {"server": "Embyserver", "series_id": "72893", "season_id": "73028"},
        "season": 3, "episode_numbers": list(range(1, 12)), "episode_count": 11,
        "air_date": "2026-07-04", "episodes": [{"episode": 1, "air_date": "2026-07-04"}],
    })

    def capture(*args, origin=None):
        """读取准备交给同步链的播放上下文，不写入豆瓣。"""
        captured.update(origin)
        return False

    monkeypatch.setattr(folio, "_sync_to_douban", capture)
    event = SimpleNamespace(item_name=media.title, item_type="TV", season_id=3, episode_id=2,
                            server_name="Embyserver", item_id="72893",
                            json_object={"Item": {"SeriesId": "72893", "SeasonId": "73028", "Id": "episode-id"}})
    folio._process_tv_show(plugin, event, {})
    assert captured["season"] == 3
    assert captured["mediaserver"] == {"server": "Embyserver", "series_id": "72893", "season_id": "73028"}
    assert captured["episode_group"] == ""
    assert folio_record.origin_key(captured).startswith("folio:library:")
    assert folio_record.origin_key(captured) != folio_record.origin_key(folio._playback_origin(media, "TV", 3))
    del event.json_object["Item"]["SeasonId"]
    assert folio_library.playback_context(event)["season_id"] == ""


def test_library_episode_lookup_consumes_all_pages_and_rejects_wrong_parent(library, monkeypatch):
    """真实整季集数来自完整分页；缺页、跨季数据及重复页不能参与身份修复。"""
    get_json = folio_library._get_json
    pages = []
    wrong = [False]

    def read(service, path, params, memo):
        if not path.endswith("/Episodes"):
            return get_json(service, path, params, memo)
        start = params["StartIndex"]
        pages.append(start)
        numbers = range(start + 1, min(start + 200, 201) + 1)
        return {"TotalRecordCount": 201, "Items": [
            {"Id": f"episode-{number}", "Type": "Episode", "SeriesId": "series-1",
             "SeasonId": "wrong-season" if wrong[0] else "season-2", "ParentIndexNumber": 2,
             "IndexNumber": number, "PremiereDate": "2023-07-10T00:00:00Z"}
            for number in numbers]}

    monkeypatch.setattr(folio_library, "_get_json", read)
    plugin = FolioPlugin()
    origin = _record()["origin"]
    season = folio_library.load_season(plugin, origin)
    assert season["episode_count"] == 201 and pages == [0, 200]
    assert season["reference"]["season_id"] == "season-2"
    assert folio_library.load_season(plugin, origin) == season and pages == [0, 200]
    wrong[0] = True
    assert folio_library.load_season(plugin, origin, refresh=True) is None
