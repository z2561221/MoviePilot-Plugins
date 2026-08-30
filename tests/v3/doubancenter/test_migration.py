"""豆瓣中心 V3 存量媒体身份迁移测试。"""

from copy import deepcopy

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
