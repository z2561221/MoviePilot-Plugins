import importlib.util
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _MemoryPlugin:
    """用于归档服务测试的内存版插件存储。"""

    def __init__(self, data=None):
        """初始化内存存储。"""
        self.data = data or {}

    def get_data(self, key, **kwargs):
        """读取指定存储键。"""
        return self.data.get(key)

    def save_data(self, key, value):
        """保存指定存储键。"""
        self.data[key] = value


def _install_package():
    """安装测试用的豆瓣中心包占位。"""
    package = types.ModuleType("doubancenter")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["doubancenter"] = package


def _load_service():
    """加载归档服务模块。"""
    _install_package()
    module_name = "doubancenter.service.archive"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_DIR / "service" / "archive.py",
        submodule_search_locations=[str(PLUGIN_DIR / "service")],
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "doubancenter.service"
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


archive_service = _load_service()


class DashboardArchiveServiceTest(unittest.TestCase):
    def test_archive_detail_overflow_keeps_latest_records_and_archives_the_rest(self):
        """详情溢出时只保留最新记录并归档旧记录。"""
        plugin = _MemoryPlugin()
        records = [
            {"title": "old", "time": "2026-07-01 10:00:00"},
            {"title": "archived-new", "archived_at": "2026-07-03 10:00:00"},
            {"title": "first-seen-new", "first_seen": "2026-07-02 10:00:00"},
        ]

        kept, changed = archive_service.archive_detail_overflow(
            plugin,
            records,
            source="subscribe_history",
            source_name="订阅历史",
            limit=2,
        )

        self.assertTrue(changed)
        self.assertEqual([item["title"] for item in kept], ["archived-new", "first-seen-new"])
        archives = plugin.data["archive_records"]
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0]["title"], "old")
        self.assertEqual(archives[0]["reason"], "超过详情页显示上限归档")

    def test_archive_anti_cheat_overflow_limits_blacklist_and_observation_logs_separately(self):
        """观察日志溢出时按黑名单和观察日志分组分别归档。"""
        plugin = _MemoryPlugin()
        logs = [
            {"title": "black-old", "reason": "黑名单关键词", "time": "2026-07-01 10:00:00"},
            {"title": "black-new", "reason": "黑名单关键词", "time": "2026-07-02 10:00:00"},
            {"title": "observe-old", "reason": "观察期未满", "time": "2026-07-01 11:00:00"},
            {"title": "observe-new", "reason": "观察期未满", "time": "2026-07-02 11:00:00"},
        ]

        kept, changed = archive_service.archive_anti_cheat_overflow(plugin, logs, limit=1)

        self.assertTrue(changed)
        self.assertEqual({item["title"] for item in kept}, {"black-new", "observe-new"})
        archives = plugin.data["archive_records"]
        self.assertEqual({item["source"] for item in archives}, {"anti_cheat_log"})
        self.assertEqual({item["source_name"] for item in archives}, {"黑名拦截", "观察日志"})
        self.assertEqual({item["title"] for item in archives}, {"black-old", "observe-old"})

    def test_paginate_archive_records_dedupes_sorts_and_reports_page_metadata(self):
        """归档分页会去重、倒序并返回分页元数据。"""
        plugin = _MemoryPlugin({
            "archive_records": [
                {
                    "id": "old-duplicate",
                    "source": "subscribe_history",
                    "title": "same",
                    "archived_at": "2026-07-01 10:00:00",
                    "record": {"title": "same", "time": "2026-07-01 10:00:00"},
                },
                {
                    "id": "complete-duplicate",
                    "source": "subscribe_history",
                    "title": "same",
                    "archived_at": "2026-07-02 10:00:00",
                    "record": {"title": "same", "time": "2026-07-01 10:00:00", "poster": "p.jpg"},
                },
                {
                    "id": "new",
                    "source": "anti_cheat_log",
                    "title": "new",
                    "archived_at": "2026-07-03 10:00:00",
                    "record": {"title": "new", "time": "2026-07-03 10:00:00"},
                },
                "bad",
            ]
        })

        page = archive_service.paginate_archive_records(plugin, page=1, page_size=1)

        self.assertEqual(page["total"], 2)
        self.assertEqual(page["page"], 1)
        self.assertEqual(page["page_size"], 1)
        self.assertEqual(page["total_pages"], 2)
        self.assertEqual(page["items"][0]["id"], "new")
        saved_ids = [item["id"] for item in plugin.data["archive_records"]]
        self.assertEqual(saved_ids, ["complete-duplicate", "new"])


if __name__ == "__main__":
    unittest.main()
