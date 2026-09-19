"""续季年份必须贯穿展示和订阅筛选，所有写入均停留在内存替身。"""

from types import SimpleNamespace

import pytest
from app.plugins.doubancenter import utils
from app.plugins.doubancenter.service import rank_pipeline, subscription
from app.plugins.doubancenter.storage import records
from app.schemas.types import MediaType
from app.sdk.media import MetaInfo

from tests.v3.doubancenter import test_rank_seasons


rank_lab = test_rank_seasons.rank_lab
RANK = {"key": "bangumi", "name": "BangumiTV", "route": "/bangumi.tv/anime/followrank"}
TITLE = "Re：从零开始的异世界生活 第四季 夺还篇"


@pytest.fixture
def season_lab(rank_lab, monkeypatch):
    """母剧始于 2016 年，当前第四季首播于 2026 年。"""
    rank_lab.media.title = "Re：从零开始的异世界生活"
    rank_lab.media.year = "2016"
    rank_lab.media.season_info = [{"season_number": 4, "air_date": "2026-04-08"}]
    rank_lab.plugin._rank_configs["bangumi"] = {"year": 2026}
    monkeypatch.setattr(subscription, "is_existing_library_media", lambda *a, **kw: False)
    return rank_lab


def snapshot(lab, *, old_year="2016", source_year=""):
    """覆盖已经保存错误展示年份的榜单记录。"""
    return {
        "raw": {"title": TITLE},
        "entry": {"title": TITLE, "year": old_year, "source_year": source_year,
                  "season": 4, "unique": "lab:re-zero-four", "media_type": "tv"},
        "mediainfo": lab.media,
    }


@pytest.mark.parametrize("old_year", ["2016", "2026", ""])
def test_snapshot_uses_season_year_once_and_preserves_it_in_history(season_lab, old_year):
    """旧展示年份不能挡住新季，也不能再次用母剧年份拒绝订阅。"""
    rank_pipeline._process_general_snapshots(
        season_lab.plugin, [snapshot(season_lab, old_year=old_year)], RANK,
    )
    assert len(season_lab.added) == 1
    assert season_lab.added[0]["season"] == 4
    assert records.read_rank_history(season_lab.plugin, "bangumi")[0]["year"] == "2026"


def test_legacy_general_path_uses_the_same_season_year(season_lab, monkeypatch):
    """直接 RSS 处理与快照处理保持相同的年份筛选语义。"""
    meta = MetaInfo(TITLE)
    meta.begin_season = 4
    monkeypatch.setattr(rank_pipeline, "_fetch_rss", lambda *a: [{"title": TITLE}])
    monkeypatch.setattr(rank_pipeline, "_recognize_rss_item", lambda *a: (meta, season_lab.media, "tv"))
    rank_pipeline._process_general(season_lab.plugin, "https://example.test/rss", RANK)
    assert len(season_lab.added) == 1
    assert season_lab.added[0]["season"] == 4
    assert records.read_rank_history(season_lab.plugin, "bangumi")[0]["year"] == "2026"


def test_rsshub_partial_subject_uses_existing_host_season_metadata(season_lab, monkeypatch):
    """RSSHub 没有 date 时复用宿主已有的季信息，不增加远程请求。"""
    monkeypatch.setattr(rank_pipeline.bangumi_tmdb_service, "recognize_bangumi_tmdb", lambda *a, **kw: {
        "subject": {"id": 633836, "name_cn": TITLE}, "season": 4,
        "year": "2016", "title": TITLE, "mediainfo": season_lab.media,
    })
    entry = {"year": "2016"}
    assert rank_pipeline._apply_bangumi_recognition(season_lab.plugin, {"title": TITLE}, entry) is season_lab.media
    assert entry["year"] == "2026"
    assert entry["source_year"] == ""


def test_bangumi_year_falls_back_to_target_tmdb_season_date(season_lab, monkeypatch):
    """识别对象只有母剧年份时，按目标季 TMDB 日期保存续季年份。"""
    entry = {"year": "2016", "season": 4, "tmdbid": 65942}
    media = SimpleNamespace(**vars(season_lab.media))
    media.season_info = []
    media.season_years = {}
    monkeypatch.setattr(
        rank_pipeline.bangumi_tmdb_service,
        "recognize_bangumi_tmdb",
        lambda *args, **kwargs: {
            "subject": {"id": 633836, "name_cn": TITLE},
            "season": 4,
            "year": "2016",
            "title": TITLE,
            "mediainfo": media,
        },
    )
    monkeypatch.setattr(season_lab.plugin.chain, "tmdb_info", lambda **kwargs: {
        "season_number": 4, "air_date": "2026-04-08",
    })
    assert rank_pipeline._apply_bangumi_recognition(
        season_lab.plugin, {"title": TITLE}, entry,
    ) is media
    assert entry["year"] == "2026"


def test_known_bangumi_quarter_year_has_priority_over_tmdb_season_year(season_lab):
    """跨年分割放送使用可信来源条目年份，不强行退回整季首播年。"""
    season_lab.plugin._rank_configs["bangumi"]["year"] = 2027
    rank_pipeline._process_general_snapshots(
        season_lab.plugin, [snapshot(season_lab, source_year="2027")], RANK,
    )
    assert len(season_lab.added) == 1
    assert records.read_rank_history(season_lab.plugin, "bangumi")[0]["year"] == "2027"


def test_unknown_season_year_remains_retryable(season_lab, monkeypatch):
    """本季信息缺失时保持未知，随后补齐元数据即可重新进入订阅流程。"""
    season_lab.media.season_info = []
    monkeypatch.setattr(season_lab.plugin.chain, "tmdb_info", lambda **kwargs: {})
    lines = []
    entry = snapshot(season_lab)
    rank_pipeline._process_general_snapshots(season_lab.plugin, [entry], RANK, result_lines=lines)
    assert season_lab.added == []
    assert any("本季年份" in line and "待重试" in line for line in lines)
    season_lab.media.season_years = {"4": "2026"}
    rank_pipeline._process_general_snapshots(season_lab.plugin, [entry], RANK)
    assert len(season_lab.added) == 1


@pytest.mark.parametrize(("year", "expected"), [("2021", "2021"), ("2026", "2026"), (None, "")])
def test_movie_year_keeps_its_original_meaning(year, expected):
    """电影年份不受续季规则影响。"""
    assert utils.get_media_year(SimpleNamespace(type=MediaType.MOVIE, year=year)) == expected
