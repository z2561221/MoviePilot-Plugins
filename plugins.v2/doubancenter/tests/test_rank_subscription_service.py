import importlib.util
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _load_service():
    package = type(sys)("doubancenter")
    package.__path__ = [str(PLUGIN_DIR)]
    service_package = type(sys)("doubancenter.service")
    service_package.__path__ = [str(PLUGIN_DIR / "service")]
    model_package = type(sys)("doubancenter.model")
    model_package.__path__ = [str(PLUGIN_DIR / "model")]
    sys.modules.update(
        {
            "doubancenter": package,
            "doubancenter.service": service_package,
            "doubancenter.model": model_package,
        }
    )

    rank_spec = importlib.util.spec_from_file_location(
        "doubancenter.model.rank",
        PLUGIN_DIR / "model" / "rank.py",
    )
    rank_module = importlib.util.module_from_spec(rank_spec)
    sys.modules[rank_spec.name] = rank_module
    rank_spec.loader.exec_module(rank_module)

    spec = importlib.util.spec_from_file_location(
        "doubancenter.service.rank_subscription",
        PLUGIN_DIR / "service" / "rank_subscription.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rank_subscription = _load_service()


class RankSubscriptionServiceTest(unittest.TestCase):
    def test_rank_config_helpers_read_rank_settings(self):
        configs = {"coming": {"enabled": True, "count": "3"}}

        self.assertEqual(rank_subscription.rank_config(configs, "coming"), {"enabled": True, "count": "3"})
        self.assertEqual(rank_subscription.rank_config(configs, "missing"), {})
        self.assertTrue(rank_subscription.rank_enabled(configs, "coming"))
        self.assertFalse(rank_subscription.rank_enabled(configs, "missing"))
        self.assertEqual(rank_subscription.rank_count(configs, "coming"), 3)

    def test_global_filter_uses_blacklist_or_observe_selection(self):
        self.assertTrue(rank_subscription.has_global_filter("综艺", observe_enabled=False))
        self.assertTrue(rank_subscription.has_global_filter("", observe_enabled=True))
        self.assertFalse(rank_subscription.has_global_filter("", observe_enabled=False))

    def test_rank_filter_uses_count_and_rank_specific_thresholds(self):
        coming = {"key": "coming", "coming": True}
        general = {"key": "movie_weekly", "coming": False}

        self.assertTrue(rank_subscription.has_rank_filter({"count": 1}, general))
        self.assertTrue(rank_subscription.has_rank_filter({"wish_count": "1000"}, coming))
        self.assertTrue(rank_subscription.has_rank_filter({"air_days": "7"}, coming))
        self.assertTrue(rank_subscription.has_rank_filter({"vote": "8.0"}, general))
        self.assertTrue(rank_subscription.has_rank_filter({"year": "2024"}, general))
        self.assertFalse(rank_subscription.has_rank_filter({}, general))

    def test_safety_filter_requires_global_or_enabled_rank_filter(self):
        ranks = [
            {"key": "coming", "coming": True},
            {"key": "movie_weekly", "coming": False},
        ]

        self.assertTrue(rank_subscription.has_safety_filter({}, ranks, blacklist_keywords="综艺"))
        self.assertTrue(rank_subscription.has_safety_filter({}, ranks, observe_enabled=True))
        self.assertTrue(
            rank_subscription.has_safety_filter(
                {"movie_weekly": {"enabled": True, "vote": "8.0"}},
                ranks,
            )
        )
        self.assertFalse(
            rank_subscription.has_safety_filter(
                {"movie_weekly": {"enabled": False, "vote": "8.0"}},
                ranks,
            )
        )
        self.assertFalse(rank_subscription.has_safety_filter({}, ranks))


if __name__ == "__main__":
    unittest.main()
