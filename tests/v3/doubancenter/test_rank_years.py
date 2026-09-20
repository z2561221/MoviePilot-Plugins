"""续季年份必须贯穿展示和订阅筛选，所有写入均停留在内存替身。"""

import datetime
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter import utils
from app.plugins.doubancenter.service import rank_pipeline, rank_timing, subscription
from app.plugins.doubancenter.storage import records
from app.schemas.types import MediaType
from app.sdk.media import MetaInfo

from tests.v3.doubancenter import test_rank_seasons


rank_lab = test_rank_seasons.rank_lab
RANK = {"key": "bangumi", "name": "BangumiTV", "route": "/bangumi.tv/anime/followrank"}
TITLE = "Re：从零开始的异世界生活 第四季 夺还篇"


class FixedDatetime(datetime.datetime):
    """冻结上映窗口实验的日期，不随执行时间漂移。"""

    @classmethod
    def now(cls, tz=None):
        """返回固定的实验时间。"""
        return cls(2026, 9, 9, 12, tzinfo=tz)


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
    assert season_lab.added == []  # 单独的年份映射不足以证明原生季日期。
    season_lab.media.season_info = [{"season_number": 4, "air_date": "2026-04-08"}]
    rank_pipeline._process_general_snapshots(season_lab.plugin, [entry], RANK)
    assert len(season_lab.added) == 1


@pytest.mark.parametrize(("year", "expected"), [("2021", "2021"), ("2026", "2026"), (None, "")])
def test_movie_year_keeps_its_original_meaning(year, expected):
    """电影年份不受续季规则影响。"""
    assert utils.get_media_year(SimpleNamespace(type=MediaType.MOVIE, year=year)) == expected


@pytest.mark.parametrize("direct", [False, True])
def test_resolved_date_passes_air_window_in_both_paths(season_lab, monkeypatch, direct):
    """无季详情的识别对象仍可通过日期回退完成上映窗口筛选。"""
    monkeypatch.setattr(
        utils, "datetime", SimpleNamespace(datetime=FixedDatetime, date=datetime.date),
    )
    season_lab.media.season_info = []
    season_lab.media.season_years = {}
    season_lab.plugin._rank_configs["bangumi"]["air_days"] = 365
    calls = []

    def load(**kwargs):
        """仅返回对应的原生第四季日期。"""
        calls.append(kwargs)
        return {"season_number": 4, "air_date": "2026-04-08"}

    monkeypatch.setattr(season_lab.plugin.chain, "tmdb_info", load)
    if direct:
        meta = MetaInfo(TITLE)
        meta.begin_season = 4
        monkeypatch.setattr(
            rank_pipeline, "_fetch_rss", lambda *a: [{"title": TITLE, "year": "2016"}],
        )
        monkeypatch.setattr(
            rank_pipeline, "_recognize_rss_item", lambda *a: (meta, season_lab.media, "tv"),
        )
        rank_pipeline._process_general(season_lab.plugin, "https://example.test/rss", RANK)
    else:
        rank_pipeline._process_general_snapshots(season_lab.plugin, [snapshot(season_lab)], RANK)
    assert len(calls) == len(season_lab.added) == 1
    record = records.read_rank_history(season_lab.plugin, "bangumi")[0]
    assert (record["year"], record["air_date"], record["season"]) == ("2026", "2026-04-08", 4)
    assert season_lab.media.year == "2016"


def test_native_identity_supplies_missing_tmdb_alias(season_lab, monkeypatch):
    """宿主只提供统一 TMDB 身份时仍能查询季日期，不依赖旧别名。"""
    season_lab.media.tmdb_id = None
    season_lab.media.season_info = []
    calls = []

    def load(**kwargs):
        """记录最终使用的身份和季号。"""
        calls.append(kwargs)
        return {"season_number": 4, "air_date": "2026-04-08"}

    monkeypatch.setattr(season_lab.plugin.chain, "tmdb_info", load)
    rank_pipeline._process_general_snapshots(season_lab.plugin, [snapshot(season_lab)], RANK)
    assert len(season_lab.added) == 1
    assert [(call["tmdbid"], call["season"]) for call in calls] == [(95480, 4)]


def test_group_year_cannot_replace_native_season_date(season_lab, monkeypatch):
    """宿主按分组 order 生成的年份不能用于原生季筛选。"""
    season_lab.media.season_info = []
    season_lab.media.season_years = {4: "2024"}
    monkeypatch.setattr(season_lab.plugin.chain, "tmdb_info", lambda **kw: {
        "season_number": 4, "air_date": "2026-04-08",
    })
    rank_pipeline._process_general_snapshots(season_lab.plugin, [snapshot(season_lab)], RANK)
    assert len(season_lab.added) == 1
    assert records.read_rank_history(season_lab.plugin, "bangumi")[0]["year"] == "2026"


def test_refresh_and_subscription_reuse_date_without_mutating_media(season_lab, monkeypatch):
    """刷新后订阅复用本轮日期，保留分段年份且不修改宿主媒体对象。"""
    season_lab.media.season_info = []
    calls = []
    monkeypatch.setattr(season_lab.plugin.chain, "tmdb_info", lambda **kw: calls.append(kw) or {
        "season_number": 4, "air_date": "2026-04-08",
    })
    entry = snapshot(season_lab)["entry"]
    assert rank_timing.resolve_release(season_lab.plugin, season_lab.media, 4, entry=entry) == (
        "2026", "2026-04-08",
    )
    entry["source_year"] = "2027"
    assert rank_timing.resolve_release(
        season_lab.plugin, season_lab.media, 4, entry=entry, require_date=True,
    ) == ("2027", "2026-04-08")
    assert len(calls) == 1
    assert season_lab.media.year == "2016"
    assert season_lab.media.season_info == []
    season_lab.media.media_id = "65942"
    rank_timing.resolve_release(
        season_lab.plugin, season_lab.media, 4, entry=entry, require_date=True,
    )
    assert [call["tmdbid"] for call in calls] == [95480, 65942]


def test_existing_history_keeps_season_year(season_lab, monkeypatch):
    """已存在分支不能把刚解析的本季年份写回母剧年份。"""
    monkeypatch.setattr(rank_pipeline, "_is_existing_media", lambda *args: True)
    rank_pipeline._process_general_snapshots(season_lab.plugin, [snapshot(season_lab)], RANK)
    record = records.read_rank_history(season_lab.plugin, "bangumi")[0]
    assert record["existing"]
    assert (record["year"], record["season"]) == ("2026", 4)
    assert not season_lab.added


@pytest.mark.parametrize("source_year, expected", [("", "2026"), ("2027", "2027")])
def test_subscription_records_use_display_year_without_changing_host_identity(
    season_lab, source_year, expected,
):
    """档案使用本季或分段年份，宿主识别请求继续使用母剧的身份年份。"""
    rank_pipeline._process_general_snapshots(
        season_lab.plugin, [snapshot(season_lab, source_year=source_year)], RANK,
    )
    assert season_lab.saved["subscribe_records"][0]["year"] == expected
    assert records.read_rank_history(season_lab.plugin, "bangumi")[0]["year"] == expected
    assert season_lab.added[0]["year"] == season_lab.media.year == "2016"


def test_unknown_year_is_not_replaced_when_year_filter_is_disabled(season_lab, monkeypatch):
    """允许未知年份进入订阅时，榜单与订阅记录也保持未知。"""
    season_lab.plugin._rank_configs["bangumi"]["year"] = 0
    season_lab.media.season_info = []
    monkeypatch.setattr(season_lab.plugin.chain, "tmdb_info", lambda **kw: {})
    rank_pipeline._process_general_snapshots(season_lab.plugin, [snapshot(season_lab)], RANK)
    assert len(season_lab.added) == 1
    assert season_lab.saved["subscribe_records"][0]["year"] == ""
    assert records.read_rank_history(season_lab.plugin, "bangumi")[0]["year"] == ""


def test_failed_subscription_record_keeps_explicit_season_year(season_lab, monkeypatch):
    """查重失败的诊断记录同样使用本季年份，且不提交真实订阅。"""
    monkeypatch.setattr(subscription, "is_existing_media", lambda *args, **kw: None)
    meta = MetaInfo(TITLE)
    meta.begin_season = 4
    assert not subscription.add_subscription(
        season_lab.plugin, season_lab.media, meta=meta, record_year="2026",
    )
    assert not season_lab.added
    assert season_lab.saved["subscribe_records"][0]["year"] == "2026"
    assert season_lab.saved["subscribe_records"][0]["status"] == "failed"
