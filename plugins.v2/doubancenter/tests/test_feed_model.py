import importlib.util
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _load_rank_model():
    spec = importlib.util.spec_from_file_location("doubancenter_model_rank", PLUGIN_DIR / "model" / "rank.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rank = _load_rank_model()


class DoubanCenterFeedModelTest(unittest.TestCase):
    def test_infer_media_type_prefers_item_type_then_rank_route(self):
        movie_rank = {"key": "movie_weekly", "route": "/douban/list/movie_weekly_best"}
        tv_rank = {"key": "tv_global", "route": "/douban/list/tv_global_best_weekly"}

        self.assertEqual(rank.infer_media_type(movie_rank, {"mtype": "tv"}), "tv")
        self.assertEqual(rank.infer_media_type(movie_rank, {"mtype": ""}), "movie")
        self.assertEqual(rank.infer_media_type(tv_rank, {"mtype": ""}), "tv")

    def test_record_history_item_merges_placeholder_without_observing_flag(self):
        history = [{"unique": "rank:1", "title": "旧标题", "time": "2026-01-01 00:00:00", "observing": True}]
        entry = {"unique": "rank:1", "title": "新标题", "tmdbid": 123}

        rank.record_history_item(history, entry)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["title"], "新标题")
        self.assertEqual(history[0]["tmdbid"], 123)
        self.assertNotIn("observing", history[0])

    def test_record_history_item_preserves_existing_dashboard_fields(self):
        history = [{"unique": "rank:1", "title": "old", "rank_index": 0, "rank_refreshed_at": "2026-06-21 10:00:00"}]
        entry = {"unique": "rank:1", "title": "new", "subscribed": True}

        rank.record_history_item(history, entry)

        self.assertEqual(history[0]["title"], "new")
        self.assertEqual(history[0]["rank_index"], 0)
        self.assertTrue(history[0]["subscribed"])

    def test_positive_number_accepts_only_positive_numeric_values(self):
        self.assertTrue(rank.positive_number("1"))
        self.assertTrue(rank.positive_number(0.5))
        self.assertFalse(rank.positive_number(0))
        self.assertFalse(rank.positive_number(""))
        self.assertFalse(rank.positive_number("not-a-number"))

    def test_year_below_min_uses_first_four_digits(self):
        self.assertTrue(rank.year_below_min("2023-05-01", 2024))
        self.assertFalse(rank.year_below_min("2024-01-01", 2024))
        self.assertFalse(rank.year_below_min("", 2024))
        self.assertFalse(rank.year_below_min("bad", 2024))
        self.assertFalse(rank.year_below_min("2023", 0))


if __name__ == "__main__":
    unittest.main()
