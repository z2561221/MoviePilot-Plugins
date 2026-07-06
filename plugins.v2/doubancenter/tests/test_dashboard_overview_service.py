import importlib.util
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _Logger:
    def info(self, *args, **kwargs):
        pass


class _MemoryPlugin:
    """用于运行总览服务测试的内存版插件存储。"""

    def __init__(self, data=None):
        """初始化内存存储。"""
        self.data = data or {}
        self._enabled = True
        self._rank_configs = {"tv_global": {"enabled": True}}
        self._observe_days = 3
        self._observe_rank_keys = ["tv_global"]
        self._folio_enabled = True
        self._folio_user = "Home"

    def get_data(self, key, **kwargs):
        """读取指定存储键。"""
        return self.data.get(key)

    def save_data(self, key, value):
        """保存指定存储键。"""
        self.data[key] = value


def _load_service():
    app = types.ModuleType("app")
    app.__path__ = []
    log = types.ModuleType("app.log")
    log.logger = _Logger()
    package = types.ModuleType("doubancenter")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules.update({
        "app": app,
        "app.log": log,
        "doubancenter": package,
    })
    module_name = "doubancenter.service.dashboard_overview"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_DIR / "service" / "dashboard_overview.py",
        submodule_search_locations=[str(PLUGIN_DIR / "service")],
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "doubancenter.service"
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dashboard_overview = _load_service()


class DashboardOverviewServiceTest(unittest.TestCase):
    def test_build_overview_response_reads_cleans_saves_and_builds_overview(self):
        """运行总览 service 会读取并治理数据后组装总览。"""
        ranks = [{"key": "tv_global", "name": "全球口碑"}]
        plugin = _MemoryPlugin({
            "subscribe_records": [
                {
                    "title": "done",
                    "tmdbid": 1,
                    "year": "2026",
                    "rank_key": "tv_global",
                    "time": "2026-07-01 09:00:00",
                    "media_type": "电视剧",
                    "note": "old",
                },
                {
                    "title": "done",
                    "tmdbid": 1,
                    "year": "2026",
                    "rank_key": "tv_global",
                    "time": "2026-07-01 10:00:00",
                    "media_type": "电视剧",
                    "note": "new",
                },
            ],
            "anti_cheat_logs": [
                {"title": "done", "reason": "观察期未满", "detail": "wait", "time": "2026-07-01 09:00:00"},
                {"title": "keep", "reason": "观察期未满", "detail": "wait", "time": "2026-07-01 09:30:00"},
                {"title": "keep", "reason": "观察期未满", "detail": "wait", "time": "2026-07-01 09:30:00"},
            ],
            "archive_records": [
                {"id": "a1", "source": "subscribe_history", "title": "old", "record": {"title": "old", "time": "2026-07-01 08:00:00"}},
                {"id": "a2", "source": "subscribe_history", "title": "old", "record": {"title": "old", "time": "2026-07-01 08:00:00", "poster": "p"}},
            ],
            "folio_data": {"1": {"subject_name": "看过"}},
            "rank_history_tv_global": [
                {
                    "title": "done",
                    "first_seen": "2026-07-01 08:00:00",
                    "subscribed": True,
                    "subscribed_at": "2026-07-01 10:00:00",
                    "rank_refreshed_at": "2026-07-01 10:00:00",
                },
                {"title": "pending", "observing": True, "rank_refreshed_at": "2026-07-01 11:00:00"},
            ],
        })

        result = dashboard_overview.build_overview_response(
            plugin,
            builtin_ranks=ranks,
            rank_history_reader=lambda plugin, key: plugin.data.get(f"rank_history_{key}", []),
            existing_subscription_checker=lambda item: False,
        )

        self.assertEqual(result["code"], 0)
        self.assertEqual(result["cards"]["subscribe"]["total"], 1)
        self.assertEqual(result["cards"]["archive"]["total"], 1)
        self.assertEqual(result["cards"]["folio"]["items"], 1)
        self.assertEqual(result["attention"]["pending_observations"], 1)
        self.assertEqual(result["attention"]["anti_cheat_logs"], 2)
        self.assertEqual(plugin.data["subscribe_records"][0]["note"], "new")
        self.assertEqual(plugin.data["anti_cheat_logs"][-1]["reason"], "观察完成")
        self.assertEqual(plugin.data["anti_cheat_logs"][0]["count"], 2)
        self.assertEqual(plugin.data["archive_records"][0]["id"], "a2")

    def test_build_overview_reports_cards_attention_and_flows(self):
        ranks = [
            {"key": "tv_global", "name": "全球口碑"},
            {"key": "movie_weekly", "name": "电影口碑"},
        ]
        histories = {
            "tv_global": [
                {
                    "title": "观察中",
                    "rank_refreshed_at": "2026-06-22 10:00:00",
                    "observing": True,
                },
                {
                    "title": "忽略",
                    "rank_refreshed_at": "2026-06-21 10:00:00",
                    "observe_deleted": True,
                },
            ],
            "movie_weekly": [
                {
                    "title": "已订阅",
                    "rank_refreshed_at": "2026-06-23 10:00:00",
                    "observing": True,
                    "subscribed": True,
                }
            ],
        }
        stats = {
            "total": 1,
            "rank_dist": {"tv_global": 1, "movie_weekly": 0},
            "rank_stats": [
                {"key": "tv_global", "name": "全球口碑", "count": 1},
                {"key": "movie_weekly", "name": "电影口碑", "count": 0},
            ],
            "type_dist": {"电影": 0, "电视剧": 1},
            "month_new": 1,
        }

        result = dashboard_overview.build_overview(
            builtin_ranks=ranks,
            rank_histories=histories,
            subscribe_records=[{"title": "订阅"}],
            anti_cheat_logs=[{"reason": "黑名单关键词"}],
            archive_records=[{"id": "a1"}],
            folio_data={"1": {"subject_name": "看过"}},
            stats=stats,
            rank_configs={"tv_global": {"enabled": True}},
            enabled=True,
            observe_days=3,
            observe_rank_keys=["tv_global"],
            folio_enabled=True,
            folio_user="Home",
            existing_subscription_checker=lambda item: False,
        )

        self.assertEqual(result["code"], 0)
        self.assertEqual(result["cards"]["rss"]["enabled"], 1)
        self.assertEqual(result["cards"]["rss"]["total"], 2)
        self.assertEqual(result["cards"]["rss"]["items"], 3)
        self.assertEqual(result["cards"]["rss"]["last_refresh"], "2026-06-23 10:00:00")
        self.assertEqual(result["cards"]["archive"]["pending"], 1)
        self.assertEqual(result["cards"]["archive"]["ignored"], 1)
        self.assertEqual(result["cards"]["folio"]["items"], 1)
        self.assertEqual(result["attention"]["blacklist_hits"], 1)
        self.assertEqual(result["attention"]["month_new"], 1)
        self.assertEqual(result["governance"]["archive_records"], 1)
        self.assertEqual(result["stats"], stats)
        self.assertEqual([item["label"] for item in result["flows"]], ["榜单订阅", "豆瓣时间", "公共归档"])

    def test_build_overview_reports_wish_status_and_flow(self):
        """运行总览会在豆瓣时间下展示想看与观影两条链路。"""
        result = dashboard_overview.build_overview(
            builtin_ranks=[],
            rank_histories={},
            subscribe_records=[],
            anti_cheat_logs=[],
            archive_records=[],
            folio_data={},
            stats={},
            rank_configs={},
            enabled=True,
            observe_days=0,
            observe_rank_keys=[],
            folio_enabled=True,
            folio_user="Home",
            existing_subscription_checker=lambda item: False,
            wish_enabled=True,
            wish_state={"initialized": True, "last_run": "2026-07-05 10:00:00", "last_error": "cookie invalid"},
            wish_queue=[{"subject_id": "1"}, {"subject_id": "2"}],
            wish_failed=[{"subject_id": "3"}],
        )

        folio_group = next(item for item in result["flows"] if item["label"] == "豆瓣时间")
        self.assertNotIn("steps", folio_group)
        self.assertEqual([item["label"] for item in folio_group["flows"]], ["同步想看", "同步观影"])
        flow = next(item for item in folio_group["flows"] if item["label"] == "同步想看")
        self.assertEqual(flow["steps"], ["周期触发", "读取想看", "新增入队", "媒体识别", "创建订阅"])
        folio_flow = next(item for item in folio_group["flows"] if item["label"] == "同步观影")
        self.assertEqual(folio_flow["steps"], ["媒体事件", "条目识别", "豆瓣同步", "写入时间"])
        self.assertEqual(
            result["cards"]["folio"]["wish"],
            {
                "enabled": True,
                "initialized": True,
                "queue": 2,
                "failed": 1,
                "last_run": "2026-07-05 10:00:00",
                "last_error": "cookie invalid",
            },
        )
        self.assertEqual(result["attention"]["wish_queue"], 2)
        self.assertEqual(result["attention"]["wish_failed"], 1)

    def test_build_overview_skips_existing_subscription_observations(self):
        ranks = [{"key": "tv_global", "name": "全球口碑"}]
        histories = {
            "tv_global": [
                {"title": "已有订阅", "observing": True},
                {"title": "媒体库已有", "observing": True, "existing": True},
                {"title": "待观察", "observing": True},
            ]
        }

        result = dashboard_overview.build_overview(
            builtin_ranks=ranks,
            rank_histories=histories,
            subscribe_records=[],
            anti_cheat_logs=[],
            archive_records=[],
            folio_data={},
            stats={},
            rank_configs={},
            enabled=False,
            observe_days=0,
            observe_rank_keys=[],
            folio_enabled=False,
            folio_user="",
            existing_subscription_checker=lambda item: item.get("title") == "已有订阅",
        )

        self.assertEqual(result["attention"]["pending_observations"], 1)
        self.assertEqual(result["cards"]["observe"]["enabled"], False)


if __name__ == "__main__":
    unittest.main()
