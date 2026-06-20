import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _Logger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _MediaType:
    MOVIE = "movie"
    TV = "tv"


class _NotificationType:
    Subscribe = "Subscribe"


class _MetaInfo:
    def __init__(self, title):
        self.title = title
        self.year = None
        self.type = None
        self.begin_season = None


def _install_stubs():
    app = types.ModuleType("app")
    app.__path__ = []

    chain = types.ModuleType("app.chain")
    chain.__path__ = []

    download = types.ModuleType("app.chain.download")
    download.DownloadChain = type("DownloadChain", (), {})

    subscribe = types.ModuleType("app.chain.subscribe")
    subscribe.SubscribeChain = type("SubscribeChain", (), {})

    core = types.ModuleType("app.core")
    core.__path__ = []

    config = types.ModuleType("app.core.config")
    config.settings = types.SimpleNamespace(PROXY=None)

    metainfo = types.ModuleType("app.core.metainfo")
    metainfo.MetaInfo = _MetaInfo

    log = types.ModuleType("app.log")
    log.logger = _Logger()

    schemas = types.ModuleType("app.schemas")
    schemas.__path__ = []

    schema_types = types.ModuleType("app.schemas.types")
    schema_types.MediaType = _MediaType
    schema_types.NotificationType = _NotificationType

    utils_pkg = types.ModuleType("app.utils")
    utils_pkg.__path__ = []

    dom = types.ModuleType("app.utils.dom")
    dom.DomUtils = type("DomUtils", (), {})

    http = types.ModuleType("app.utils.http")
    http.RequestUtils = type("RequestUtils", (), {})

    package = types.ModuleType("doubancenter")
    package.__path__ = [str(PLUGIN_DIR)]

    local_utils = types.ModuleType("doubancenter.utils")
    local_utils.match_any_filter = lambda values, filters: True
    local_utils.get_tmdb_air_date = lambda *args, **kwargs: None
    local_utils.is_within_days = lambda *args, **kwargs: True

    sys.modules.update(
        {
            "app": app,
            "app.chain": chain,
            "app.chain.download": download,
            "app.chain.subscribe": subscribe,
            "app.core": core,
            "app.core.config": config,
            "app.core.metainfo": metainfo,
            "app.log": log,
            "app.schemas": schemas,
            "app.schemas.types": schema_types,
            "app.utils": utils_pkg,
            "app.utils.dom": dom,
            "app.utils.http": http,
            "doubancenter": package,
            "doubancenter.utils": local_utils,
        }
    )


def _import_feed():
    _install_stubs()
    sys.modules.pop("doubancenter.feed", None)
    spec = importlib.util.spec_from_file_location("doubancenter.feed", PLUGIN_DIR / "feed.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["doubancenter.feed"] = module
    spec.loader.exec_module(module)
    return module


class _Plugin:
    _observe_days = 2

    def __init__(self):
        self.data = {}

    def get_data(self, key):
        return self.data.get(key)

    def save_data(self, key, value):
        self.data[key] = value


class DoubanCenterFeedSafetyTest(unittest.TestCase):
    def setUp(self):
        self.feed = _import_feed()

    def test_observe_records_first_seen_and_skips_new_item(self):
        plugin = _Plugin()
        history = []

        should_skip = self.feed._check_observe(plugin, "rank:1", history, title="测试电影")

        self.assertTrue(should_skip)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["unique"], "rank:1")
        self.assertEqual(history[0]["title"], "测试电影")
        self.assertTrue(history[0]["observing"])

    def test_observe_allows_item_after_window(self):
        plugin = _Plugin()
        old_time = (datetime.datetime.now() - datetime.timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        history = [{"unique": "rank:1", "title": "测试电影", "time": old_time, "observing": True}]

        should_skip = self.feed._check_observe(plugin, "rank:1", history, title="测试电影")

        self.assertFalse(should_skip)

    def test_custom_rank_history_key_is_stable(self):
        source = "https://example.com/rss?token=abc"

        first = self.feed._custom_rank_history_key(source)
        second = self.feed._custom_rank_history_key(source)

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("rank_history_custom_"))
        self.assertNotIn("-", first)

    def test_rank_media_type_uses_rank_route(self):
        movie_rank = {"key": "movie_weekly", "route": "/douban/list/movie_weekly_best"}
        tv_rank = {"key": "tv_global", "route": "/douban/list/tv_global_best_weekly"}

        self.assertEqual(self.feed._rank_media_type(movie_rank, {"mtype": ""}), "movie")
        self.assertEqual(self.feed._rank_media_type(tv_rank, {"mtype": ""}), "tv")

    def test_record_history_item_replaces_observe_placeholder(self):
        history = [{"unique": "rank:1", "title": "旧标题", "time": "2026-01-01 00:00:00", "observing": True}]
        entry = {"unique": "rank:1", "title": "新标题", "tmdbid": 123}

        self.feed._record_history_item(history, entry)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["title"], "新标题")
        self.assertEqual(history[0]["tmdbid"], 123)
        self.assertNotIn("observing", history[0])

    def test_trim_history_keeps_newest_items(self):
        history = [{"unique": str(i)} for i in range(5)]

        trimmed = self.feed._trim_history(history, limit=3)

        self.assertEqual([item["unique"] for item in trimmed], ["2", "3", "4"])


if __name__ == "__main__":
    unittest.main()
