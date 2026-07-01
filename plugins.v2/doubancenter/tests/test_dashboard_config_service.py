import importlib.util
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _load_service():
    spec = importlib.util.spec_from_file_location(
        "doubancenter_service_dashboard_config",
        PLUGIN_DIR / "service" / "dashboard_config.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dashboard_config = _load_service()


class DashboardConfigServiceTest(unittest.TestCase):
    def test_build_config_returns_runtime_config_and_enabled_rank_options(self):
        ranks = [
            {"key": "tv_global", "name": "全球口碑"},
            {"key": "movie_weekly", "name": "电影口碑"},
            {"key": "bad_rank", "name": "未启用"},
        ]

        result = dashboard_config.build_config(
            builtin_ranks=ranks,
            rank_enabled_checker=lambda key: key != "bad_rank",
            folio_pc_month="4",
            folio_pc_num="60",
            folio_mobile_month="2",
            folio_mobile_num="18",
            dashboard_rank_keys=["tv_global"],
            blacklist_keywords="跳过,忽略",
            observe_days="7",
            observe_rank_keys=["movie_weekly"],
        )

        self.assertEqual(result["folio_pc_month"], "4")
        self.assertEqual(result["folio_pc_num"], "60")
        self.assertEqual(result["folio_mobile_month"], "2")
        self.assertEqual(result["folio_mobile_num"], "18")
        self.assertEqual(result["dashboard_rank_keys"], ["tv_global"])
        self.assertEqual(
            result["rank_options"],
            [
                {"title": "全球口碑", "value": "tv_global"},
                {"title": "电影口碑", "value": "movie_weekly"},
            ],
        )
        self.assertEqual(result["blacklist_keywords"], "跳过,忽略")
        self.assertEqual(result["observe_days"], 7)
        self.assertEqual(result["observe_rank_keys"], ["movie_weekly"])

    def test_build_config_normalizes_missing_values_for_frontend(self):
        result = dashboard_config.build_config(
            builtin_ranks=[
                {"key": "coming", "name": "即将上映"},
                {"key": "", "name": "缺失键"},
                "bad",
            ],
            rank_enabled_checker=lambda key: True,
            folio_pc_month=3,
            folio_pc_num=50,
            folio_mobile_month=2,
            folio_mobile_num=15,
            dashboard_rank_keys=None,
            blacklist_keywords=None,
            observe_days=None,
            observe_rank_keys=None,
        )

        self.assertEqual(result["dashboard_rank_keys"], [])
        self.assertEqual(result["rank_options"], [{"title": "即将上映", "value": "coming"}])
        self.assertEqual(result["blacklist_keywords"], "")
        self.assertEqual(result["observe_days"], 0)
        self.assertEqual(result["observe_rank_keys"], [])


if __name__ == "__main__":
    unittest.main()
