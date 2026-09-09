"""榜单识别到自动订阅的季号回归，所有外部操作均使用内存边界。"""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter import utils
from app.plugins.doubancenter.service import rank_pipeline, subscription
from app.plugins.doubancenter.storage import records
from app.schemas.types import MediaSource, MediaType
from app.sdk.media import MetaInfo


@pytest.fixture
def rank_lab(monkeypatch):
    """以同一 TMDB 剧集身份检查识别、查重和新增订阅收到的季号。"""
    saved, recognized, checked, added = {}, [], [], []
    media = SimpleNamespace(
        title="Slow Horses", year="2022", type=MediaType.TV,
        media_source=MediaSource.TMDB, media_id="95480", tmdb_id=95480,
        bangumi_id=None, douban_id=None, vote_average=8,
        season_info=[{"season_number": 6, "air_date": "2026-09-19"}],
        release_date="2022-04-01", get_poster_image=lambda: "",
    )

    def recognize(**kwargs):
        """只提供剧集级 TMDB 详情，季号必须由插件保留。"""
        recognized.append(kwargs["meta"].begin_season)
        return media

    class FakeSubscribeChain:
        """捕获真实订阅服务传给宿主的参数。"""

        def exists(self, *, mediainfo, meta):
            """模拟当前剧集尚未订阅。"""
            assert mediainfo is media
            checked.append(meta.begin_season)
            return False

        def add(self, **kwargs):
            """记录订阅请求，不创建真实订阅。"""
            added.append(kwargs)
            return len(added), ""

    class FakeSubscribeOper:
        """隔离宿主订阅数据库。"""

        def exists(self, **_kwargs):
            """当前没有活动订阅。"""
            return False

        def exist_history(self, **_kwargs):
            """当前没有已完成订阅。"""
            return False

    monkeypatch.setattr(rank_pipeline, "SubscribeChain", FakeSubscribeChain)
    monkeypatch.setattr(subscription, "_default_subscribe_oper_cls", lambda: FakeSubscribeOper)
    plugin = SimpleNamespace(
        chain=SimpleNamespace(
            recognize_media=recognize,
            convert_media_identity=lambda **_kwargs: {"id": 95480},
            tmdb_info=lambda **_kwargs: {"air_date": "2026-09-19"},
        ),
        get_data=lambda key: deepcopy(saved.get(key)),
        save_data=lambda key, value: saved.__setitem__(key, deepcopy(value)),
        _rank_configs={"coming": {"air_days": 0}, "tv_global": {"air_days": 0}},
        _blacklist_keywords="", _observe_days=0, _observe_rank_keys=[],
    )
    return SimpleNamespace(
        plugin=plugin, media=media, saved=saved,
        recognized=recognized, checked=checked, added=added,
    )


@pytest.mark.parametrize("rank_key", ["tv_global", "coming"])
@pytest.mark.parametrize("title", [
    "Slow Horses Season 6", "Slow Horses 6th season", "Slow Horses season6",
    "Slow Horses S06", "流人 第六季",
])
def test_refresh_and_auto_subscription_keep_requested_season(rank_lab, rank_key, title):
    """续季经过刷新、TMDB 转换和两类自动订阅后仍为第六季。"""
    rank = {
        "key": rank_key, "name": "实验榜单", "coming": rank_key == "coming",
        "route": "/douban/tv/coming" if rank_key == "coming" else "/douban/list/tv_global_best_weekly",
    }
    item = {"title": title, "doubanid": "36689816", "link": "https://example.test/subject/36689816"}
    _, snapshots = rank_pipeline._merge_rank_items(
        rank_lab.plugin, rank_key, [item], rank, return_snapshot=True,
    )
    assert rank_lab.recognized == [6]
    assert snapshots[0]["entry"]["season"] == 6
    process = rank_pipeline._process_coming_snapshots if rank_key == "coming" else rank_pipeline._process_general_snapshots
    process(rank_lab.plugin, snapshots, rank)

    assert len(rank_lab.added) == 1
    assert rank_lab.added[0]["season"] == 6
    assert rank_lab.added[0]["media_id"] == "95480"
    assert rank_lab.checked and set(rank_lab.checked) == {6}
    assert records.read_rank_history(rank_lab.plugin, rank_key)[0]["season"] == 6
    assert rank_lab.saved["subscribe_records"][0]["season"] == 6

    process(rank_lab.plugin, snapshots, rank)
    assert len(rank_lab.added) == 1


def test_snapshot_uses_chinese_display_title_when_raw_title_has_no_season():
    """RSS 原名不含季号时保留中文展示名中的明确季号。"""
    meta = rank_pipeline._snapshot_meta(
        {"title": "Slow Horses"}, {"title": "流人 第六季"}, MediaType.TV,
    )
    assert meta.begin_season == 6


@pytest.mark.parametrize("season", [0, 6, "6"])
def test_explicit_season_survives_snapshot_and_direct_recognition(rank_lab, season):
    """不依赖标题也能传递显式季号，包括特别篇的零季。"""
    item = {"title": "Slow Horses", "season": season}
    meta = rank_pipeline._snapshot_meta(item, {"season": season}, MediaType.TV)
    assert meta.begin_season == int(season)
    recognized_meta, media, _ = rank_pipeline._recognize_rss_item(
        rank_lab.plugin, item, {"key": "tv_global", "route": "/douban/list/tv_global_best_weekly"},
    )
    assert media is rank_lab.media
    assert recognized_meta.begin_season == int(season)


@pytest.mark.parametrize("title", ["Slow Horses", "1899", "The 100", "某剧2", "Four Seasons"])
def test_unmarked_titles_do_not_invent_a_season(title):
    """普通标题中的数字或季节词不能用于猜测最新季。"""
    assert utils.resolve_media_season(MetaInfo(title)) is None


@pytest.mark.parametrize("value", [True, False, -1, "bad", 2.5])
def test_invalid_season_does_not_override_title(value):
    """损坏的季号字段不能覆盖标题中已确认的第六季。"""
    assert utils.resolve_media_season(MetaInfo("Slow Horses Season 6"), season=value) == 6
