"""目标季日期、提前窗口及元数据恢复的隔离回归。"""

import datetime
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter import utils
from app.plugins.doubancenter.service import rank_pipeline
from app.plugins.doubancenter.storage import records

from tests.v3.doubancenter import test_rank_seasons

rank_lab = test_rank_seasons.rank_lab


class FixedDatetime(datetime.datetime):
    """固定到北京时间 2026 年 9 月 9 日，避免日期测试随时间失效。"""

    @classmethod
    def now(cls, tz=None):
        """返回固定实验时间。"""
        return cls(2026, 9, 9, 12, 0, tzinfo=tz)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    """仅冻结日期工具使用的时钟。"""
    monkeypatch.setattr(utils, "datetime", SimpleNamespace(datetime=FixedDatetime, date=datetime.date))


def coming_snapshot(lab):
    """构造原始英文续季名与已识别 TMDB 详情的输入快照。"""
    return {
        "raw": {"title": "Slow Horses Season 6", "link": "https://example.test/subject/36689816"},
        "entry": {"title": "流人 第六季", "season": 6, "unique": "lab:season-six"},
        "mediainfo": lab.media,
    }


COMING = {"key": "coming", "name": "即将上映", "coming": True, "date_mode": "future"}


def test_valid_snapshot_avoids_an_extra_network_lookup(rank_lab):
    """已有本季首播日期时，额外 TMDB 接口不可用也应在提前窗口内订阅。"""
    lookups = []

    def unavailable(**kwargs):
        """模拟日期接口超时，并记录是否发生了多余请求。"""
        lookups.append(kwargs)
        raise TimeoutError("laboratory timeout")

    rank_lab.plugin.chain.tmdb_info = unavailable
    rank_lab.plugin._rank_configs["coming"]["air_days"] = 10
    rank_pipeline._process_coming_snapshots(rank_lab.plugin, [coming_snapshot(rank_lab)], COMING)

    assert lookups == []
    assert len(rank_lab.added) == 1
    assert rank_lab.added[0]["season"] == 6
    assert records.read_rank_history(rank_lab.plugin, "coming")[0]["air_date"] == "2026-09-19"


@pytest.mark.parametrize(("date", "subscribed"), [
    ("2026-09-20", False), ("2026-09-19", True),
    ("2026-09-09", True), ("2026-09-08", False),
])
def test_coming_window_includes_ten_days_and_premiere_day(rank_lab, date, subscribed):
    """上映前十天与上映当天可订阅，十一天前和上映后不通过未来窗口。"""
    rank_lab.media.season_info[0]["air_date"] = date
    rank_lab.plugin._rank_configs["coming"]["air_days"] = 10
    rank_pipeline._process_coming_snapshots(rank_lab.plugin, [coming_snapshot(rank_lab)], COMING)
    assert bool(rank_lab.added) is subscribed


@pytest.mark.parametrize("season", [0, 2, 6])
def test_missing_target_season_never_uses_first_season_date(rank_lab, season):
    """续季和特别篇缺少日期时，整剧首播日期不能冒充目标季日期。"""
    rank_lab.media.season_info = []
    chain = SimpleNamespace(tmdb_info=lambda **_kwargs: {"first_air_date": "2026-09-19", "seasons": []})
    assert utils.get_media_release_date(rank_lab.media, season=season) is None
    assert utils.get_tmdb_air_date(chain, 95480, season=season) is None


@pytest.mark.parametrize("season", [None, 1])
def test_first_season_and_movies_keep_series_release_fallback(rank_lab, season):
    """首季或未指定季时仍可使用整剧首播日期，不改变电影日期读取。"""
    rank_lab.media.season_info = []
    chain = SimpleNamespace(tmdb_info=lambda **_kwargs: {"first_air_date": "2022-04-01"})
    assert utils.get_media_release_date(rank_lab.media, season=season) == "2022-04-01"
    assert utils.get_tmdb_air_date(chain, 95480, season=season) == "2022-04-01"


def test_season_query_failure_can_recover_from_series_season_list():
    """季详情暂时不可用时仍能从整剧详情中的对应季恢复日期。"""
    lookups = []

    def lookup(**kwargs):
        """模拟季接口超时和含本季日期的剧集接口。"""
        lookups.append(kwargs.get("season"))
        if kwargs.get("season") == 6:
            raise TimeoutError("laboratory season timeout")
        return {"first_air_date": "2022-04-01", "seasons": [
            None, {"season_number": "bad"},
            {"season_number": "6", "air_date": "2026-09-19T00:00:00Z"},
        ]}

    assert utils.get_tmdb_air_date(SimpleNamespace(tmdb_info=lookup), 95480, season=6) == "2026-09-19"
    assert lookups == [6, None]


def test_wrong_season_response_cannot_supply_target_date():
    """意外返回别的季时不能把其日期用于订阅。"""
    chain = SimpleNamespace(tmdb_info=lambda **_kwargs: {
        "season_number": 1, "air_date": "2026-09-19", "first_air_date": "2022-04-01",
    })
    assert utils.get_tmdb_air_date(chain, 95480, season=6) is None


@pytest.mark.parametrize("date", [None, "2026", "2026-02-30", "2026-13-19"])
def test_invalid_target_date_is_not_replaced_with_series_date(rank_lab, date):
    """缺失、未定档和损坏的目标季日期都保持待确认。"""
    rank_lab.media.season_info[0]["air_date"] = date
    assert utils.get_media_release_date(rank_lab.media, season=6) is None


def test_missing_date_remains_retryable_until_target_season_is_known(rank_lab):
    """本轮缺少目标季日期不标记已订阅，下轮补齐后仍能自动订阅。"""
    rank_lab.plugin._rank_configs["coming"]["air_days"] = 10
    rank_lab.media.season_info = []
    rank_lab.plugin.chain.tmdb_info = lambda **_kwargs: {"first_air_date": "2022-04-01", "seasons": []}
    snapshot = coming_snapshot(rank_lab)
    lines = []
    rank_pipeline._process_coming_snapshots(rank_lab.plugin, [snapshot], COMING, result_lines=lines)
    assert rank_lab.added == []
    assert any("第6季首播日期" in line and "下轮重试" in line for line in lines)
    assert not any(item.get("subscribed") for item in records.read_rank_history(rank_lab.plugin, "coming"))

    rank_lab.media.season_info = [{"season_number": 6, "air_date": "2026-09-19"}]
    rank_pipeline._process_coming_snapshots(rank_lab.plugin, [snapshot], COMING)
    assert len(rank_lab.added) == 1
    assert rank_lab.added[0]["season"] == 6


def test_direct_coming_rss_uses_the_same_target_season_date(rank_lab, monkeypatch):
    """传统 RSS 入口同样复用第六季日期，不受整剧首播日期影响。"""
    rank_lab.plugin._rank_configs["coming"]["air_days"] = 10
    monkeypatch.setattr(rank_pipeline, "_fetch_coming_rss", lambda *_args: [
        {"title": "Slow Horses Season 6", "link": "https://example.test/subject/36689816"},
    ])
    rank_pipeline._process_coming(rank_lab.plugin, "https://example.test/rss", COMING)
    assert len(rank_lab.added) == 1
    assert rank_lab.added[0]["season"] == 6
    assert records.read_rank_history(rank_lab.plugin, "coming")[0]["air_date"] == "2026-09-19"
