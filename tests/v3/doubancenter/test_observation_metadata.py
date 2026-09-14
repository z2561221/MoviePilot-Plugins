"""观察日志海报保留、保守回填与历史迁移回归。"""

import datetime
from copy import deepcopy

from app.plugins.doubancenter import migration
from app.plugins.doubancenter.service import observation
from app.plugins.doubancenter.service.observation_metadata import enrich_log_metadata
from app.plugins.doubancenter.storage import records as storage

from tests.v3.doubancenter.test_migration import MemoryPlugin


def _snapshot(**updates):
    """返回含稳定身份的榜单或订阅记录。"""
    return {
        "title": "兰香如故", "media_source": "themoviedb", "media_id": "282326",
        "poster": "https://image.tmdb.org/poster.jpg", "rank_key": "tv_real_time",
        "rank_name": "实时热门", "link": "https://movie.douban.com/subject/36449295/",
        "unique": "dc2_rank:36449295", **updates,
    }


def test_completed_observation_log_keeps_media_snapshot():
    """观察满期的真实写入路径须保留海报、榜单和身份。"""
    plugin = MemoryPlugin({})
    plugin._observe_days = 2
    plugin._observe_rank_keys = ["tv_real_time"]
    observed_at = datetime.datetime.now(datetime.timezone.utc).astimezone() - datetime.timedelta(days=3)
    item = _snapshot(first_seen=observed_at.strftime("%Y-%m-%d %H:%M:%S"))
    assert not observation.check_observe(plugin, item["unique"], [item], rank_key="tv_real_time")
    log = plugin.data[storage.ANTI_CHEAT_LOGS_KEY][0]
    assert log["reason"] == "观察完成"
    for field in ("poster", "rank_key", "rank_name", "media_source", "media_id", "link"):
        assert log[field] == item[field]


def test_existing_log_is_enriched_without_overwriting_time_detail_or_poster():
    """补全已有摘要不受完成日志去重阻挡，保留原始事实和已存海报。"""
    log = {"title": "兰香如故", "reason": "观察完成", "time": "2026-09-14 12:46:53",
           "detail": "已过 2 天，达到 2 天", "count": 3, "link": ""}
    original = deepcopy(log)
    snapshot = _snapshot(first_seen="2026-09-12", subscribed=True, subscribed_at="2026-09-14 12:47:05")
    result, changed = observation.reconcile_anti_cheat_logs(
        [log], subscribe_records=[snapshot], ranks=[{"key": "tv_real_time", "history": [snapshot]}],
        archived_completion_titles=set(), existing_subscription_checker=lambda _: False,
    )
    assert changed is True
    assert len(result) == 1
    assert result[0]["poster"] == snapshot["poster"]
    for field in ("time", "detail", "count", "reason"):
        assert result[0][field] == original[field]
    assert log == original
    again, changed = enrich_log_metadata(result, [_snapshot(poster="new-poster")])
    assert changed is False
    assert again == result


def test_title_only_log_is_not_filled_from_ambiguous_or_conflicting_media():
    """同名不同身份和半截身份不凭标题猜测海报。"""
    log = {"title": "兰香如故", "reason": "观察完成"}
    result, changed = enrich_log_metadata([log], [_snapshot(), _snapshot(media_id="other")])
    assert (result, changed) == ([log], False)
    half = {**log, "media_source": "douban"}
    assert enrich_log_metadata([half], [_snapshot()]) == ([half], False)
    known = {**log, "media_source": "themoviedb", "media_id": "other"}
    assert enrich_log_metadata([known], [_snapshot()]) == ([known], False)


def test_initialization_persists_missing_log_metadata_once():
    """初始化补旧日志并保持幂等，后续刷新不依赖临时榜单是否仍在。"""
    log = {"title": "兰香如故", "reason": "观察完成", "time": "2026-09-14 12:46:53", "link": ""}
    plugin = MemoryPlugin({storage.ANTI_CHEAT_LOGS_KEY: [log], storage.SUBSCRIBE_RECORDS_KEY: [_snapshot()]})
    result = migration.migrate_plugin_media_identity(plugin)
    assert storage.ANTI_CHEAT_LOGS_KEY in result["changed_keys"]
    assert plugin.data[storage.ANTI_CHEAT_LOGS_KEY][0]["poster"] == _snapshot()["poster"]
    del plugin.data[storage.SUBSCRIBE_RECORDS_KEY]
    assert migration.migrate_plugin_media_identity(plugin)["changed_keys"] == []
