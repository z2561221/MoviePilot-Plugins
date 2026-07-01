import importlib.util
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _MemoryPlugin:
    """用于榜单历史服务测试的内存插件。"""

    def __init__(self, rank_keys=None):
        """初始化仪表盘榜单配置。"""
        self._dashboard_rank_keys = rank_keys


def _load_service():
    """加载榜单历史仪表盘服务模块。"""
    module_name = "doubancenter_service_dashboard_rank_history"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_DIR / "service" / "dashboard_rank_history.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class DashboardRankHistoryServiceTest(unittest.TestCase):
    def test_build_rank_history_response_reads_configured_rank_keys(self):
        """榜单历史服务只返回已配置且非空的榜单数据。"""
        service = _load_service()
        plugin = _MemoryPlugin(["tv_global", "", None, "movie_weekly"])
        calls = []

        def read_rank_items(plugin_obj, rank_key, limit=5):
            calls.append((plugin_obj, rank_key, limit))
            return [{"title": rank_key, "limit": limit}]

        result = service.build_rank_history_response(plugin, read_rank_items)

        self.assertEqual(
            result,
            {
                "data": {
                    "tv_global": [{"title": "tv_global", "limit": 5}],
                    "movie_weekly": [{"title": "movie_weekly", "limit": 5}],
                }
            },
        )
        self.assertEqual(
            [(rank_key, limit) for _, rank_key, limit in calls],
            [("tv_global", 5), ("movie_weekly", 5)],
        )
        self.assertTrue(all(plugin_obj is plugin for plugin_obj, _, _ in calls))

    def test_build_rank_history_response_handles_missing_rank_keys(self):
        """榜单历史服务在未配置榜单时返回空数据。"""
        service = _load_service()
        plugin = _MemoryPlugin(None)

        result = service.build_rank_history_response(
            plugin,
            lambda plugin_obj, rank_key, limit=5: [{"title": rank_key}],
        )

        self.assertEqual(result, {"data": {}})


if __name__ == "__main__":
    unittest.main()
