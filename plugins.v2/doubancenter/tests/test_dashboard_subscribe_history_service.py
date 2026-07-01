import importlib.util
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _MemoryPlugin:
    """用于订阅历史服务测试的内存版插件存储。"""

    def __init__(self, data=None):
        """初始化内存存储。"""
        self.data = data or {}

    def get_data(self, key, **kwargs):
        """读取指定存储键。"""
        return self.data.get(key)

    def save_data(self, key, value):
        """保存指定存储键。"""
        self.data[key] = value


def _archive_record(plugin, source, record, source_name, dedupe=False):
    """把归档记录写入内存存储。"""
    archives = plugin.data.setdefault("archive_records", [])
    item = {
        "id": f"a{len(archives) + 1}",
        "source": source,
        "source_name": source_name,
        "title": record.get("title") or "",
        "record": dict(record),
    }
    archives.append(item)
    return item


def _load_service():
    package = types.ModuleType("doubancenter")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["doubancenter"] = package
    module_name = "doubancenter.service.dashboard_subscribe_history"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_DIR / "service" / "dashboard_subscribe_history.py",
        submodule_search_locations=[str(PLUGIN_DIR / "service")],
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "doubancenter.service"
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


dashboard_subscribe_history = _load_service()


class DashboardSubscribeHistoryServiceTest(unittest.TestCase):
    def test_paginate_subscribe_history_dedupes_sorts_archives_overflow_and_reports_metadata(self):
        """订阅历史列表会去重、倒序、归档溢出并返回分页元数据。"""
        plugin = _MemoryPlugin({
            "subscribe_records": [
                {"title": "条目0", "tmdbid": 0, "time": "2026-07-01 10:00:00"},
                {"title": "条目1", "tmdbid": 1, "time": "2026-07-01 11:00:00"},
                {"title": "条目2", "tmdbid": 2, "time": "2026-07-01 12:00:00"},
                {"title": "条目3", "tmdbid": 3, "time": "2026-07-01 13:00:00"},
                {"title": "条目4", "tmdbid": 4, "time": "2026-07-01 14:00:00"},
                {"title": "条目5", "tmdbid": 5, "time": "2026-07-01 15:00:00", "note": "old"},
                {"title": "条目5", "tmdbid": 5, "time": "2026-07-01 16:00:00", "note": "new"},
                {"title": "条目6", "tmdbid": 6, "time": "2026-07-01 17:00:00"},
            ]
        })

        page = dashboard_subscribe_history.paginate_subscribe_history(plugin, page=1, page_size=3, limit=5)

        self.assertEqual([item["title"] for item in page["items"]], ["条目6", "条目5", "条目4"])
        self.assertEqual(page["total"], 5)
        self.assertEqual(page["page"], 1)
        self.assertEqual(page["page_size"], 3)
        self.assertEqual(page["total_pages"], 2)
        self.assertEqual(plugin.data["subscribe_records"][1]["note"], "new")
        self.assertEqual([item["title"] for item in plugin.data["archive_records"]], ["条目1", "条目0"])

    def test_delete_subscribe_history_archives_matching_record_and_saves_kept_records(self):
        """删除订阅历史时归档匹配记录并保存剩余记录。"""
        plugin = _MemoryPlugin({
            "subscribe_records": [
                {"title": "保留", "time": "2026-06-21 10:00:00", "tmdbid": 1},
                {"title": "删除", "time": "2026-06-22 10:00:00", "tmdbid": 2},
            ]
        })

        result = dashboard_subscribe_history.delete_subscribe_history(
            plugin,
            time="2026-06-22 10:00:00",
            title="删除",
            tmdbid=2,
            archive_record_callback=_archive_record,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["archive_id"], "a1")
        self.assertEqual([item["title"] for item in plugin.data["subscribe_records"]], ["保留"])
        self.assertEqual(plugin.data["archive_records"][0]["source"], "subscribe_history")

    def test_dedupe_records_keeps_latest_record_for_same_subscription_key(self):
        records = [
            {
                "status": "success",
                "tmdbid": "123",
                "title": "测试剧",
                "year": "2026",
                "rank_key": "tv_global",
                "time": "2026-07-01 10:00:00",
                "note": "old",
            },
            {
                "status": "success",
                "tmdbid": "123",
                "title": "测试剧",
                "year": "2026",
                "rank_key": "tv_global",
                "time": "2026-07-02 10:00:00",
                "note": "new",
            },
            {
                "status": "failed",
                "tmdbid": "123",
                "title": "测试剧",
                "year": "2026",
                "rank_key": "tv_global",
                "time": "2026-07-03 10:00:00",
            },
        ]

        merged, changed = dashboard_subscribe_history.dedupe_records(records)

        self.assertTrue(changed)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["note"], "new")
        self.assertEqual(merged[0]["time"], "2026-07-02 10:00:00")
        self.assertEqual(merged[1]["status"], "failed")

    def test_dedupe_records_filters_invalid_input_and_limits_history(self):
        records = [
            {"title": f"条目{i}", "tmdbid": str(i), "time": f"2026-07-01 10:{i % 60:02d}:00"}
            for i in range(505)
        ]
        records.insert(3, "bad")
        records.insert(7, None)

        merged, changed = dashboard_subscribe_history.dedupe_records(records)

        self.assertTrue(changed)
        self.assertEqual(len(merged), 500)
        self.assertEqual(merged[0]["title"], "条目5")
        self.assertEqual(merged[-1]["title"], "条目504")

    def test_dedupe_records_normalizes_non_list_input(self):
        merged, changed = dashboard_subscribe_history.dedupe_records({"bad": "value"})

        self.assertEqual(merged, [])
        self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
