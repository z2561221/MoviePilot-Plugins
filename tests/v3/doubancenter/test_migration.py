"""豆瓣中心 V3 存量媒体身份迁移测试。"""

from copy import deepcopy

import pytest
from app.plugins.doubancenter import migration
from app.plugins.doubancenter.storage import records as storage


class MemoryPlugin:
    """提供内存版插件数据读写接口。"""

    def __init__(self, data):
        self.data = deepcopy(data)

    def get_data(self, key, **kwargs):
        """读取指定存储键。"""
        return deepcopy(self.data.get(key))

    def save_data(self, key, value):
        """保存指定存储键。"""
        self.data[key] = deepcopy(value)


def test_media_identity_migration_is_idempotent_and_preserves_unresolved_records():
    """迁移应覆盖各类记录、保留 unresolved，并在第二次执行时无变化。"""
    rank_key = storage.rank_history_key("coming")
    custom_key = storage.custom_rank_history_key("/custom/list")
    plugin = MemoryPlugin({
        storage.SUBSCRIBE_RECORDS_KEY: [
            {"title": "TMDB", "tmdbid": 11},
            {"title": "Dynamic", "media_source": "vendor.one", "media_id": "abc"},
            {"title": "Half", "media_source": "douban"},
        ],
        storage.ANTI_CHEAT_LOGS_KEY: [
            {"title": "Bangumi", "bangumiid": 22},
            {"title": "仅记录观察结果", "reason": "未达到订阅条件"},
        ],
        storage.ARCHIVE_RECORDS_KEY: [
            {"id": "a1", "source": "subscribe_history", "record": {"title": "豆瓣", "doubanid": 33}},
            {
                "id": "a2",
                "source": "anti_cheat_log",
                "record": {"title": "旧观察日志", "reason": "观察结束"},
            },
        ],
        storage.FOLIO_DATA_KEY: {"条目": {"subject_id": 44, "subject_name": "条目"}},
        storage.FOLIO_WAIT_KEY: {"等待": {"subject_id": "55", "subject_name": "等待"}},
        storage.FOLIO_WISH_QUEUE_KEY: [{"subject_id": 66, "title": "想看"}],
        rank_key: [{"title": "榜单", "tmdb_id": 77}],
        custom_key: [{"title": "自定义", "douban_id": 88}],
    })

    first = migration.migrate_plugin_media_identity(
        plugin,
        rank_keys=["coming"],
        custom_rank_sources=["/custom/list"],
    )
    assert first["changed_keys"]
    assert first["unresolved_count"] == 1
    assert plugin.data[storage.SUBSCRIBE_RECORDS_KEY][0]["media_source"] == "themoviedb"
    assert plugin.data[storage.SUBSCRIBE_RECORDS_KEY][0]["media_id"] == "11"
    assert "tmdbid" not in plugin.data[storage.SUBSCRIBE_RECORDS_KEY][0]
    assert plugin.data[storage.SUBSCRIBE_RECORDS_KEY][1]["media_source"] == "vendor.one"
    assert plugin.data[storage.SUBSCRIBE_RECORDS_KEY][2] == {"title": "Half", "media_source": "douban"}
    assert plugin.data[storage.ARCHIVE_RECORDS_KEY][0]["record"]["media_source"] == "douban"
    assert plugin.data[storage.ARCHIVE_RECORDS_KEY][0]["media_id"] == "33"
    assert "doubanid" not in plugin.data[storage.ARCHIVE_RECORDS_KEY][0]["record"]
    assert plugin.data[storage.ANTI_CHEAT_LOGS_KEY][1] == {
        "title": "仅记录观察结果",
        "reason": "未达到订阅条件",
    }
    assert plugin.data[storage.ARCHIVE_RECORDS_KEY][1]["record"] == {
        "title": "旧观察日志",
        "reason": "观察结束",
    }
    assert plugin.data[storage.FOLIO_DATA_KEY]["条目"]["media_source"] == "douban"
    assert plugin.data[storage.FOLIO_WAIT_KEY]["等待"]["media_id"] == "55"
    assert plugin.data[storage.FOLIO_WISH_QUEUE_KEY][0]["media_id"] == "66"
    assert plugin.data[rank_key][0]["media_id"] == "77"
    assert plugin.data[custom_key][0]["media_id"] == "88"

    snapshot = deepcopy(plugin.data)
    second = migration.migrate_plugin_media_identity(
        plugin,
        rank_keys=["coming"],
        custom_rank_sources=["/custom/list"],
    )
    assert second["changed_keys"] == []
    assert second["unresolved_count"] == 1
    assert plugin.data == snapshot


def test_migration_recovers_source_ids_from_existing_subject_links():
    """现场旧榜单和归档的条目链接可补来源身份，重复迁移不再写入。"""
    rank_key = storage.rank_history_key("coming")
    records = [
        {"title": "旧豆瓣榜单", "tmdbid": None, "link": "https://movie.douban.com/subject/35460732/"},
        {"title": "旧豆瓣派发", "douban_id": None, "link": "https://www.douban.com/doubanapp/dispatch/movie/37435796"},
        {"title": "旧电影榜单", "link": "https://movie.douban.com/subject/37153826/?from=rank"},
    ]
    archive = {"id": "old", "source": "subscribe_history", "custom": "keep",
               "record": {"title": "旧番剧", "link": "https://bgm.tv/subject/501963", "time": "2026-07-08"}}
    plugin = MemoryPlugin({rank_key: records, storage.ARCHIVE_RECORDS_KEY: [archive]})
    result = migration.migrate_plugin_media_identity(plugin, rank_keys=["coming"])
    assert result["unresolved_count"] == 0
    assert [item["media_id"] for item in plugin.data[rank_key]] == ["35460732", "37435796", "37153826"]
    assert all(item["media_source"] == "douban" for item in plugin.data[rank_key])
    migrated_archive = plugin.data[storage.ARCHIVE_RECORDS_KEY][0]
    assert migrated_archive["media_source"] == "bangumi"
    assert migrated_archive["media_id"] == "501963"
    assert migrated_archive["record"]["media_id"] == "501963"
    assert migrated_archive["record"]["time"] == "2026-07-08"
    assert migrated_archive["custom"] == "keep"
    snapshot = deepcopy(plugin.data)
    assert migration.migrate_plugin_media_identity(plugin, rank_keys=["coming"])["changed_keys"] == []
    assert plugin.data == snapshot


@pytest.mark.parametrize("record", [
    {"link": "https://movie.douban.com.evil.test/subject/123/"},
    {"link": "https://example.test/subject/123/"},
    {"link": "https://movie.douban.com/subject/0/"},
    {"link": "https://movie.douban.com/subject/123/reviews"},
    {"media_source": "themoviedb", "link": "https://movie.douban.com/subject/123/"},
    {"media_id": "456", "link": "https://bgm.tv/subject/123"},
])
def test_migration_keeps_ambiguous_or_incomplete_identity_unchanged(record):
    """非条目链接和已声明的半截身份不能被链接猜测覆盖。"""
    migrated, changed, unresolved = migration._migrate_record(record)
    assert migrated == record
    assert changed is False
    assert unresolved is True


def test_pending_folio_origin_is_reported_separately_without_fabricating_douban_identity(monkeypatch):
    """来源完整的待分季队列保留未知目标，真正残缺的来源仍计入迁移警告。"""
    pending = {
        "display_title": "待分季", "identity_status": "unresolved", "status": "do",
        "identity_reason": "未找到通过季首播日校验的豆瓣条目",
        "origin": {"media_source": "themoviedb", "media_id": "4285", "season": 1},
    }
    broken = {**pending, "origin": {"media_source": "themoviedb"}}
    plugin = MemoryPlugin({storage.FOLIO_WAIT_KEY: {"pending": pending, "broken": broken}})
    warnings, infos = [], []
    monkeypatch.setattr(migration, "_log_warning", warnings.append)
    monkeypatch.setattr(migration, "_log_info", infos.append)
    result = migration.migrate_plugin_media_identity(plugin)
    assert result["pending_folio_count"] == 1
    assert result["unresolved_count"] == 1
    assert result["changed_keys"] == []
    assert plugin.data[storage.FOLIO_WAIT_KEY] == {"pending": pending, "broken": broken}
    assert any("保留 1 条无法回填" in message for message in warnings)
    assert any("1 条观影记录待豆瓣分季匹配" in message for message in infos)
