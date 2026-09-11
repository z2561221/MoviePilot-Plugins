"""观影分季匹配、播放状态和时间线去重的行为测试。"""

import copy
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from app.plugins.doubancenter.adapter import folio_media
from app.plugins.doubancenter.model import folio_record
from app.plugins.doubancenter.service import dashboard_folio, folio
from tests.v3.doubancenter.folio_fakes import (
    FolioMediaChain, FolioPlugin, HUANZHU_SUBJECTS, MUSHOKU_SUBJECTS,
    huanzhu_media, mushoku_media,
)


@pytest.mark.parametrize("season,expected", [(1, "1786739"), (2, "1786740")])
def test_huanzhu_uses_season_and_all_regional_air_dates(season, expected):
    """整剧 IMDb 错候选必须接受季首播日校验，不能遮蔽台湾首播日。"""
    media = huanzhu_media()
    chain = FolioMediaChain(media, HUANZHU_SUBJECTS)
    result = folio_media.resolve_tv_subject(chain, media, folio._playback_origin(media, "TV", season))
    assert result["subject_id"] == expected
    assert result["identity_scope"] == "season"
    assert result["poster_path"].endswith(f"hz{season}.jpg")


@pytest.mark.parametrize("season,expected,native", [(1, "30513783", 1), (2, "35306636", 1), (3, "35460731", 2)])
def test_mushoku_group_number_is_not_tmdb_season_number(season, expected, native):
    """分段匹配各自的豆瓣条目海报，原始 TMDB 季只保留为缺图回退依据。"""
    media = mushoku_media()
    result = folio_media.resolve_tv_subject(
        FolioMediaChain(media, MUSHOKU_SUBJECTS), media, folio._playback_origin(media, "TV", season),
    )
    assert result["subject_id"] == expected
    assert result["facts"]["native_season"] == native
    assert result["facts"]["season"] == season
    subject = next(item for item in MUSHOKU_SUBJECTS if item["id"] == expected)
    assert result["poster_path"] == subject["pic"]["large"]
    assert result["facts"]["poster_path"].endswith(f"mt{native}.jpg")


@pytest.mark.parametrize("season,native", [(1, 1), (2, 1), (3, 2)])
def test_missing_subject_poster_uses_correct_original_season(season, native):
    """豆瓣条目缺图时回退实际原始季，不把播放分段号当作 TMDB 季。"""
    media = mushoku_media()
    subjects = [{key: value for key, value in item.items() if key != "pic"} for item in MUSHOKU_SUBJECTS]
    result = folio_media.resolve_tv_subject(
        FolioMediaChain(media, subjects), media, folio._playback_origin(media, "TV", season),
    )
    assert result["resolved"] is True
    assert result["poster_path"].endswith(f"mt{native}.jpg")


def test_ambiguous_same_date_candidates_are_not_selected():
    """两个同名同日候选没有唯一身份时保持未决。"""
    media = huanzhu_media()
    candidates = HUANZHU_SUBJECTS + [{**HUANZHU_SUBJECTS[1], "id": "other"}]
    result = folio_media.resolve_tv_subject(FolioMediaChain(media, candidates), media, folio._playback_origin(media, "TV", 2))
    assert result["resolved"] is False
    assert "不唯一" in result["reason"]


def test_group_missing_map_and_same_year_without_dates_are_unresolved():
    """剧集组映射缺失或只有年份时，不能把同年 Part.2 合并到首部。"""
    media = mushoku_media()
    origin = folio._playback_origin(media, "TV", 2)
    candidates = [{**item, "pubdate": []} for item in MUSHOKU_SUBJECTS]
    assert not folio_media.resolve_tv_subject(FolioMediaChain(media, candidates), media, origin)["resolved"]
    media.episode_groups = []
    media.season_info = []
    assert not folio_media.season_facts(media, origin)["resolved"]


def test_movie_and_unrelated_same_day_candidates_are_rejected():
    """同日期并不能让电影或其他作品冒充目标电视剧。"""
    media = huanzhu_media()
    candidates = [
        {**HUANZHU_SUBJECTS[1], "is_tv": False, "type": "movie"},
        {**HUANZHU_SUBJECTS[1], "id": "different", "title": "新还珠格格"},
    ]
    result = folio_media.resolve_tv_subject(FolioMediaChain(media, candidates), media, folio._playback_origin(media, "TV", 2))
    assert result["resolved"] is False


def test_series_fallback_needs_episode_coverage_and_matching_premiere():
    """豆瓣整剧条目可复用，但集数相同的不同年代重拍不能通过。"""
    media = huanzhu_media()
    whole = {**HUANZHU_SUBJECTS[0], "episodes_count": 192}
    chain = FolioMediaChain(media, [whole])
    result = folio_media.resolve_tv_subject(chain, media, folio._playback_origin(media, "TV", 2))
    assert result["subject_id"] == "1786739"
    assert result["identity_scope"] == "series"
    chain.subjects[0]["pubdate"] = ["2011-04-28"]
    chain.subjects[0]["year"] = "2011"
    assert not folio_media.resolve_tv_subject(chain, media, folio._playback_origin(media, "TV", 2))["resolved"]


def test_missing_season_poster_keeps_series_poster_and_actual_season():
    """目标季无海报时保留整剧图片并携带实际季号。"""
    media = huanzhu_media()
    media.season_info[1]["poster_path"] = None
    facts = folio_media.season_facts(media, folio._playback_origin(media, "TV", 2))
    assert facts["season"] == 2
    assert facts["season_poster"] is False
    assert facts["poster_path"] == media.poster_path


def test_duplicate_events_and_aliases_do_not_rewrite_completed_season(monkeypatch):
    """同播放身份仅写一次在看和一次看过，别名与重播不降级。"""
    media = huanzhu_media()
    chain = FolioMediaChain(media, HUANZHU_SUBJECTS)
    monkeypatch.setattr(folio, "MediaChain", lambda: chain)
    status_calls = []

    class Account:
        """仅记录状态写入，测试不得访问豆瓣。"""

        def __init__(self, **kwargs):
            """接收隔离 Cookie。"""

        def set_watching_status(self, **kwargs):
            """模拟成功。"""
            status_calls.append(kwargs)
            return True

    monkeypatch.setattr(folio, "DoubanApi", Account)
    plugin = FolioPlugin()
    processed = {}
    origin = folio._playback_origin(media, "TV", 2)
    for title, status in [("还珠格格 第2季", "do"), ("还珠格格第二部", "do"),
                          ("还珠格格 第2季", "collect"), ("还珠格格 第2季", "collect"),
                          ("还珠格格第二部", "do")]:
        assert folio._sync_to_douban(plugin, title, status, "TV", processed, media, origin=origin)
    assert [(row["subject_id"], row["status"]) for row in status_calls] == [("1786740", "do"), ("1786740", "collect")]
    assert len(processed) == 1
    record = next(iter(processed.values()))
    assert record["watch_status"] == "collect"
    assert record["season_label"] == "第2季"


def test_unknown_legacy_pending_subject_cannot_write_douban(monkeypatch):
    """只有旧标题和错误豆瓣 ID 的待重试项不能绕过季校验。"""
    plugin = FolioPlugin()
    plugin._wait_process = {"还珠格格 第2季": {"subject_id": "1786739", "status": "do", "type": "TV"}}
    monkeypatch.setattr(folio, "DoubanApi", lambda **kwargs: pytest.fail("未核验身份不能创建写入客户端"))
    assert not folio._sync_to_douban(plugin, "还珠格格 第2季", "do", "TV", {})
    assert plugin._wait_process["还珠格格 第2季"]["subject_id"] == "1786739"


@pytest.mark.parametrize("poster", [
    "https://image.tmdb.org/t/p/original/u7LWdKmEdEr6Ui3GZMsFGlKZQBd.jpg",
    "https://img3.doubanio.com/view/photo/m_ratio_poster/public/p2649427633.webp",
])
def test_verified_season_cannot_be_reidentified_from_shared_poster(poster):
    """已核验分段的 ID 和独立豆瓣海报不能被旧海报维护覆盖。"""
    record = {"subject_id": "35306636", "subject_name": "无职转生 Part.2", "media_source": "douban",
              "media_id": "35306636", "identity_status": "verified", "type": "电视剧",
              "poster_path": poster}
    plugin = FolioPlugin({"无职 第2季": record})
    assert folio.repair_folio_history(plugin) == 0
    assert plugin.data["folio_data"]["无职 第2季"]["media_id"] == "35306636"
    assert plugin.data["folio_data"]["无职 第2季"]["poster_path"] == poster


def test_legacy_timeline_uses_host_proxy_for_douban_posters():
    """旧版时间线与 Vue 一样经宿主图片代理访问豆瓣图，保留完整图片参数。"""
    poster = "https://img3.doubanio.com/view/photo/m_ratio_poster/public/p2649427633.webp?size=small&v=2"
    card = dashboard_folio._poster_card({"subject_id": "35306636"}, poster)
    image = card["content"][0]["content"][0]
    source = urlsplit(image["props"]["src"])
    assert source.path == "/api/v1/system/img/0"
    assert parse_qs(source.query) == {"imgurl": [poster], "cache": ["true"]}


def test_timeline_is_readonly_and_deduplicates_by_source_type_and_id():
    """最新观看时间决定展示月份，保留不同 ID、来源、类型及未决记录。"""
    base = {"subject_id": "1", "media_source": "douban", "media_id": "1", "type": "TV", "timestamp": "2026-08-01 10:00:00"}
    data = {
        "旧标题": base,
        "新标题": {**base, "timestamp": "2026-09-01 10:00:00"},
        "另一个季": {**base, "subject_id": "2", "media_id": "2"},
        "另一个来源": {**base, "media_source": "vendor.test"},
        "电影": {**base, "type": "MOV"},
        "未核实": {**base, "identity_status": "unresolved"},
        "无效时间": {**base, "timestamp": "bad-date"},
    }
    before = copy.deepcopy(data)
    projected = folio_record.timeline_records(data)
    assert data == before
    assert len(projected) == 5
    assert "新标题" in [item["display_title"] for item in projected.values()]
    assert "旧标题" not in [item["display_title"] for item in projected.values()]
    plugin = FolioPlugin(data)
    assert dashboard_folio.get_folio_data(plugin)["data"] == projected
    assert dashboard_folio.get_folio_data(plugin, raw=True)["data"] == data
    cards = dashboard_folio.build_timeline_items(data, month_limit=3, item_limit=50)
    assert len(cards) == 2
    assert "看过1部" in cards[0]["content"][0]["content"][0]["html"]


def test_original_identity_is_normalized_and_not_inferred_from_legacy_title():
    """同名标题不能让不同源身份共用同步状态。"""
    origin = {"type": "TV", "media_source": "themoviedb", "media_id": "4285", "season": "2"}
    assert folio_record.origin_key(origin) == folio_record.origin_key({**origin, "season": 2})
    assert folio_record.origin_key({**origin, "media_id": "0"}) == ""
    assert folio_record.find_record({"同名": {"watch_status": "collect"}}, origin, "同名")[1] == {}


def test_playback_entry_passes_actual_group_season_not_cached_media_season(monkeypatch):
    """实际入口必须把播放器第 3 季传下去，缓存中的 season=1 不能覆盖它。"""
    media = mushoku_media()
    plugin = FolioPlugin()
    plugin._folio_first = False
    captured = {}
    monkeypatch.setattr(folio, "_series_context", lambda *args: {"title": media.title, "media_source": "themoviedb", "media_id": "94664"})
    monkeypatch.setattr(folio, "_recognize_media", lambda *args, **kwargs: media)

    def capture(*args, origin=None):
        """只捕获播放上下文，状态写入另有真实逻辑测试。"""
        captured.update(origin)
        return False

    monkeypatch.setattr(folio, "_sync_to_douban", capture)
    event = SimpleNamespace(item_name=media.title, item_type="TV", season_id="3", episode_id="2")
    folio._process_tv_show(plugin, event, {})
    assert captured["season"] == 3
    assert captured["episode_group"] == "61d225784d0e8d0069c57beb"


def test_pending_completed_status_is_not_downgraded_by_later_start(monkeypatch):
    """待重试的看过状态优先于后来收到的在看事件。"""
    media = huanzhu_media()
    chain = FolioMediaChain(media, HUANZHU_SUBJECTS)
    monkeypatch.setattr(folio, "MediaChain", lambda: chain)
    calls = []

    class Account:
        """第一次模拟豆瓣写失败，第二次模拟成功。"""

        def __init__(self, **kwargs):
            """接收隔离配置。"""

        def set_watching_status(self, **kwargs):
            """记录写入状态。"""
            calls.append(kwargs["status"])
            return len(calls) > 1

    monkeypatch.setattr(folio, "DoubanApi", Account)
    plugin = FolioPlugin()
    processed = {}
    origin = folio._playback_origin(media, "TV", 2)
    assert not folio._sync_to_douban(plugin, "还珠格格 第2季", "collect", "TV", processed, media, origin=origin)
    assert folio._sync_to_douban(plugin, "还珠格格 第2季", "do", "TV", processed, media, origin=origin)
    assert calls == ["collect", "collect"]
    assert plugin._wait_process == {}


def test_sparse_imdb_summary_loads_tv_detail_even_when_search_is_empty(monkeypatch):
    """实际 IMDb 转换摘要缺类型时仍须回读详情，不能提前过滤掉首部。"""
    media = huanzhu_media()
    chain = FolioMediaChain(media, HUANZHU_SUBJECTS)
    monkeypatch.setattr(chain, "convert_media_identity", lambda **kwargs: {"id": "1786739", "title": "還珠格格"})
    monkeypatch.setattr(chain, "search_medias", lambda **kwargs: [])
    result = folio_media.resolve_tv_subject(chain, media, folio._playback_origin(media, "TV", 1))
    assert result["subject_id"] == "1786739"


@pytest.mark.parametrize("season,expected", [(1, "1786739"), (2, "1786740")])
def test_regional_premiere_difference_needs_matching_season_year_and_count(season, expected):
    """现场豆瓣仅含大陆首播日，仍可用明确部号、同年与相同集数核验。"""
    media = huanzhu_media()
    subjects = [{**item, "pubdate": item["pubdate"][:1]} for item in HUANZHU_SUBJECTS]
    result = folio_media.resolve_tv_subject(FolioMediaChain(media, subjects), media, folio._playback_origin(media, "TV", season))
    assert result["subject_id"] == expected
    check = next(item for item in result["checks"] if item["id"] == expected)
    assert check["match_basis"] == "season_year_episode_count"
    subjects[season - 1]["episodes_count"] = 999
    assert not folio_media.resolve_tv_subject(FolioMediaChain(media, subjects), media, folio._playback_origin(media, "TV", season))["resolved"]


def test_short_name_search_still_requires_full_series_and_group_date(monkeypatch):
    """长标题搜索为空时补短名，命中后仍按剧集组日期选取 Part.2。"""
    media = mushoku_media()
    chain = FolioMediaChain(media, MUSHOKU_SUBJECTS)
    search = chain.search_medias
    queries = []

    def short_search(meta, media_source=None):
        """模拟实际豆瓣只接受主标题的检索。"""
        queries.append(meta.name)
        return search(meta, media_source) if meta.name == "无职转生" else []

    monkeypatch.setattr(chain, "search_medias", short_search)
    result = folio_media.resolve_tv_subject(chain, media, folio._playback_origin(media, "TV", 2))
    assert result["subject_id"] == "35306636"
    assert "无职转生" in queries
