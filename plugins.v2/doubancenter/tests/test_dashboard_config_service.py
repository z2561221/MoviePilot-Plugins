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
            dashboard_rank_keys=["tv_global"],
            blacklist_keywords="跳过,忽略",
            observe_days="7",
            observe_rank_keys=["movie_weekly"],
        )

        self.assertNotIn("folio_pc_month", result)
        self.assertNotIn("folio_pc_num", result)
        self.assertNotIn("folio_mobile_month", result)
        self.assertNotIn("folio_mobile_num", result)
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

    def test_build_config_returns_wish_status_for_config_ui(self):
        """配置补充接口会返回同步想看状态，供前端展示。"""
        result = dashboard_config.build_config(
            builtin_ranks=[],
            rank_enabled_checker=lambda key: True,
            dashboard_rank_keys=[],
            blacklist_keywords="",
            observe_days=0,
            observe_rank_keys=[],
            wish_enabled=True,
            wish_cron="*/30 * * * *",
            wish_user="home",
            wish_notify=True,
            wish_onlyonce=True,
            wish_max_pages=2,
            wish_days=3,
            wish_state={"initialized": True, "last_error": "cookie invalid", "last_run": "2026-07-05 10:00:00"},
            wish_queue=[{"subject_id": "1"}],
            wish_processed=[{"subject_id": "2"}, {"subject_id": "3"}],
            wish_failed=[{"subject_id": "4"}],
        )

        self.assertEqual(
            result["wish_status"],
            {
                "enabled": True,
                "cron": "*/30 * * * *",
                "user": "home",
                "notify": True,
                "onlyonce": True,
                "max_pages": 2,
                "days": 3,
                "initialized": True,
                "last_error": "cookie invalid",
                "last_run": "2026-07-05 10:00:00",
                "queue": 1,
                "processed": 2,
                "failed": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
