import importlib.util
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _load_service():
    spec = importlib.util.spec_from_file_location(
        "doubancenter_service_rank_refresh",
        PLUGIN_DIR / "service" / "rank_refresh.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rank_refresh = _load_service()


class RankRefreshServiceTest(unittest.TestCase):
    def test_dashboard_rank_sort_key_uses_rank_index_then_title(self):
        self.assertLess(
            rank_refresh.dashboard_rank_sort_key({"rank_index": 1, "title": "B"}),
            rank_refresh.dashboard_rank_sort_key({"rank_index": 2, "title": "A"}),
        )
        self.assertLess(
            rank_refresh.dashboard_rank_sort_key({"rank_index": "bad", "title": "A"}),
            rank_refresh.dashboard_rank_sort_key({"rank_index": "bad", "title": "B"}),
        )

    def test_dashboard_rank_items_use_latest_refresh_batch(self):
        history = [
            {"title": "old", "rank_refreshed_at": "2026-01-01 00:00:00", "rank_index": 0},
            {"title": "new-b", "rank_refreshed_at": "2026-01-02 00:00:00", "rank_index": 1},
            {"title": "new-a", "rank_refreshed_at": "2026-01-02 00:00:00", "rank_index": 0},
        ]

        items = rank_refresh.dashboard_rank_items(history, limit=5)

        self.assertEqual([item["title"] for item in items], ["new-a", "new-b"])

    def test_dashboard_rank_items_fallback_to_latest_history_without_batch(self):
        history = [{"title": str(i)} for i in range(5)]

        items = rank_refresh.dashboard_rank_items(history, limit=2)

        self.assertEqual([item["title"] for item in items], ["4", "3"])


if __name__ == "__main__":
    unittest.main()
