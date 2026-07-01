import datetime
import importlib.util
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _load_service():
    spec = importlib.util.spec_from_file_location(
        "doubancenter_service_dashboard_stats",
        PLUGIN_DIR / "service" / "dashboard_stats.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dashboard_stats = _load_service()


class DashboardStatsServiceTest(unittest.TestCase):
    def test_build_stats_reports_rank_type_and_month_new(self):
        ranks = [
            {"key": "tv_global", "name": "全球口碑"},
            {"key": "movie_weekly", "name": "电影口碑"},
        ]
        records = [
            {"rank_key": "tv_global", "media_type": "电视剧", "time": "2026-07-01 10:00:00"},
            {"rank_key": "movie_weekly", "media_type": "电影", "time": "2026-06-30 10:00:00"},
            {"rank_key": "unknown_rank", "media_type": "纪录片", "time": "bad"},
            {"media_type": "电视剧", "time": ""},
        ]
        now = datetime.datetime(2026, 7, 15, 12, 0, 0)

        result = dashboard_stats.build_stats(records, ranks, now=now)

        self.assertEqual(result["total"], 4)
        self.assertEqual(result["rank_dist"], {"tv_global": 1, "movie_weekly": 1, "unknown": 2})
        self.assertEqual(result["type_dist"], {"电影": 1, "电视剧": 2})
        self.assertEqual(result["month_new"], 1)
        self.assertEqual(
            result["rank_stats"],
            [
                {"key": "tv_global", "name": "全球口碑", "count": 1},
                {"key": "movie_weekly", "name": "电影口碑", "count": 1},
                {"key": "unknown", "name": "未归类", "count": 2},
            ],
        )

    def test_build_stats_ignores_non_dict_records_and_empty_rank_list(self):
        now = datetime.datetime(2026, 7, 15, 12, 0, 0)

        result = dashboard_stats.build_stats(
            [
                {"rank_key": "x", "media_type": "电影", "time": "2026-07-02 10:00:00"},
                "bad",
                None,
            ],
            [],
            now=now,
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["rank_dist"], {"unknown": 1})
        self.assertEqual(result["rank_stats"], [{"key": "unknown", "name": "未归类", "count": 1}])
        self.assertEqual(result["type_dist"], {"电影": 1, "电视剧": 0})
        self.assertEqual(result["month_new"], 1)


if __name__ == "__main__":
    unittest.main()
