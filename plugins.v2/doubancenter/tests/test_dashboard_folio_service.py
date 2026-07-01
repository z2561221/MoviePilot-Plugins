import importlib.util
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _MemoryPlugin:
    """用于豆瓣时间线服务测试的内存插件存储。"""

    def __init__(self, data=None):
        """初始化内存存储和时间线配置。"""
        self.data = data or {}
        self._folio_pc_month = 2
        self._folio_pc_num = 1
        self._folio_mobile_month = 1
        self._folio_mobile_num = 2

    def get_data(self, key, **kwargs):
        """读取指定存储键。"""
        plugin_id = kwargs.get("plugin_id") or ""
        if plugin_id:
            return self.data.get((plugin_id, key))
        return self.data.get(key)

    def save_data(self, key, value):
        """保存指定存储键。"""
        self.data[key] = value


def _install_stubs():
    """安装加载服务所需的包占位。"""
    package = types.ModuleType("doubancenter")
    package.__path__ = [str(PLUGIN_DIR)]
    service_package = types.ModuleType("doubancenter.service")
    service_package.__path__ = [str(PLUGIN_DIR / "service")]
    sys.modules.update({
        "doubancenter": package,
        "doubancenter.service": service_package,
    })


def _load_service():
    """加载豆瓣时间线服务模块。"""
    _install_stubs()
    module_name = "doubancenter.service.dashboard_folio"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_DIR / "service" / "dashboard_folio.py",
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "doubancenter.service"
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class DashboardFolioServiceTest(unittest.TestCase):
    def test_build_timeline_items_groups_months_and_limits_items(self):
        """豆瓣时间线会按月份倒序分组，并限制每月展示条数。"""
        service = _load_service()
        data = {
            "old": {
                "subject_id": "100",
                "subject_name": "旧片",
                "poster_path": "https://img.example.com/original/old.jpg",
                "timestamp": "2026-04-01 10:00:00",
            },
            "may": {
                "subject_id": "101",
                "subject_name": "五月",
                "poster_path": "https://img.example.com/original/may.jpg",
                "timestamp": "2026-05-01 10:00:00",
            },
            "june1": {
                "subject_id": "102",
                "subject_name": "六月一",
                "poster_path": "https://img.example.com/original/june1.jpg",
                "timestamp": "2026-06-01 10:00:00",
            },
            "june2": {
                "subject_id": "103",
                "subject_name": "六月二",
                "poster_path": "https://img.example.com/original/june2.jpg",
                "timestamp": "2026-06-02 10:00:00",
            },
        }

        items = service.build_timeline_items(data, mobile=False, month_limit=2, item_limit=1)

        self.assertEqual(len(items), 2)
        self.assertIn("6月", items[0]["content"][0]["content"][0]["html"])
        self.assertIn("看过2部", items[0]["content"][0]["content"][0]["html"])
        june_cards = items[0]["content"][0]["content"][1]["content"]
        self.assertEqual(len(june_cards), 1)
        self.assertEqual(
            june_cards[0]["content"][0]["content"][0]["props"]["src"],
            "https://img.example.com/w200/june2.jpg",
        )
        self.assertIn("5月", items[1]["content"][0]["content"][0]["html"])

    def test_build_timeline_items_resolves_missing_poster_and_uses_mobile_size(self):
        """豆瓣时间线会补识别缺失海报，并在移动端使用小尺寸样式。"""
        service = _load_service()
        calls = []

        def resolve_poster(item):
            calls.append(item["subject_name"])
            return "https://img.example.com/original/resolved.jpg"

        items = service.build_timeline_items(
            {
                "1": {
                    "subject_id": "201",
                    "subject_name": "待识别",
                    "timestamp": "2026-06-02 10:00:00",
                }
            },
            mobile=True,
            month_limit=2,
            item_limit=2,
            poster_resolver=resolve_poster,
        )

        card_props = items[0]["content"][0]["content"][1]["content"][0]["content"][0]["content"][0]["props"]
        self.assertEqual(calls, ["待识别"])
        self.assertEqual(card_props["src"], "https://img.example.com/w200/resolved.jpg")
        self.assertEqual(card_props["style"], "width:44px;height:66px;")

    def test_get_folio_data_falls_back_to_original_plugin_storage(self):
        """当前插件没有豆瓣时间数据时会回退读取原 DoubanCenter 数据。"""
        service = _load_service()
        plugin = _MemoryPlugin({
            "folio_data": {},
            ("DoubanCenter", "folio_data"): {"1": {"subject_name": "原始数据"}},
        })

        result = service.get_folio_data(plugin)

        self.assertEqual(result, {"data": {"1": {"subject_name": "原始数据"}}})


if __name__ == "__main__":
    unittest.main()
