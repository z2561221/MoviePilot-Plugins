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

    media = types.ModuleType("app.chain.media")
    media.MediaChain = type("MediaChain", (), {})

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
            "app.chain.media": media,
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


def _import_dashboard():
    _install_stubs()
    sys.modules.pop("doubancenter.dashboard", None)
    spec = importlib.util.spec_from_file_location("doubancenter.dashboard", PLUGIN_DIR / "dashboard.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["doubancenter.dashboard"] = module
    spec.loader.exec_module(module)
    return module


class _Plugin:
    _observe_days = 2
    _anti_cheat_enabled = True
    _anti_cheat_min_vote = 5.0
    _blacklist_keywords = ""
    _region_filters = []
    _genre_filters = []
    _resolution_filters = []
    _rank_configs = {}

    def __init__(self):
        self.data = {}

    def get_data(self, key):
        return self.data.get(key)

    def save_data(self, key, value):
        self.data[key] = value


class _MediaInfo:
    def __init__(self, title="测试电影", year="2026", mtype=_MediaType.MOVIE, tmdb_id=12345):
        self.title = title
        self.year = year
        self.type = mtype
        self.tmdb_id = tmdb_id
        self.vote_average = 8.0

    def get_poster_image(self):
        return "poster.jpg"


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

    def test_fetch_rss_uses_default_media_type_from_url(self):
        rss = """<?xml version="1.0"?>
<rss><channel><item><title>Test Movie</title><link>https://movie.douban.com/subject/1234567/</link><description>2026</description></item></channel></rss>"""

        class RequestUtils:
            def __init__(self, *args, **kwargs):
                pass

            def get_res(self, addr):
                return types.SimpleNamespace(text=rss)

        def tag_value(item, tag, default=""):
            nodes = item.getElementsByTagName(tag)
            if not nodes or not nodes[0].firstChild:
                return default
            return nodes[0].firstChild.nodeValue

        plugin = _Plugin()
        plugin._proxy = False
        self.feed.RequestUtils = RequestUtils
        self.feed.DomUtils.tag_value = staticmethod(tag_value)

        items = self.feed._fetch_rss(plugin, "https://rsshub.example/douban/list/movie_weekly_best")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["mtype"], "movie")
        self.assertEqual(items[0]["doubanid"], "1234567")

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

    def test_observe_is_ignored_when_anti_cheat_disabled(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = False
        history = []

        should_skip = self.feed._check_observe(plugin, "rank:1", history, title="测试电影")

        self.assertFalse(should_skip)
        self.assertEqual(history, [])

    def test_observe_days_do_not_make_subscription_safe_when_anti_cheat_disabled(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = False
        plugin._observe_days = 2

        has_filter = self.feed._has_global_subscription_filter(plugin)

        self.assertFalse(has_filter)

    def test_blacklist_stays_active_when_anti_cheat_disabled(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = False
        plugin._blacklist_keywords = "综艺"

        should_skip = self.feed._check_blacklist(plugin, "测试综艺")
        has_filter = self.feed._has_global_subscription_filter(plugin)

        self.assertTrue(should_skip)
        self.assertTrue(has_filter)

    def test_pending_observations_returns_observing_rank_items(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin._observe_days = 3
        first_seen = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        plugin.data["rank_history_tv_global"] = [
            {"title": "观察中剧集", "unique": "rank:1", "first_seen": first_seen, "observing": True}
        ]

        result = dashboard.api_pending_observations(plugin)["data"]

        self.assertEqual(result[0]["title"], "观察中剧集")
        self.assertEqual(result[0]["rank_key"], "tv_global")
        self.assertEqual(result[0]["rank_name"], "全球口碑")
        self.assertEqual(result[0]["observe_days"], 3)
        self.assertEqual(result[0]["elapsed_days"], 1)
        self.assertEqual(result[0]["remaining_days"], 2)

    def test_dashboard_rank_history_returns_latest_five_first(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin._dashboard_rank_keys = ["tv_global"]
        plugin.data["rank_history_tv_global"] = [{"title": f"第{i}条"} for i in range(7)]

        result = dashboard.api_rank_history(plugin)["data"]["tv_global"]

        self.assertEqual([item["title"] for item in result], ["第6条", "第5条", "第4条", "第3条", "第2条"])

    def test_merge_rank_items_keeps_media_type_and_year_for_dashboard_subscribe(self):
        plugin = _Plugin()
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        rank = {"key": "movie_weekly", "name": "电影口碑", "route": "/douban/list/movie_weekly_best"}

        history = self.feed._merge_rank_items(
            plugin,
            "movie_weekly",
            [{"title": "测试电影", "link": "https://movie.douban.com/subject/123/", "mtype": "movie", "year": "2026"}],
            rank,
        )

        self.assertEqual(history[0]["media_type"], "movie")
        self.assertEqual(history[0]["year"], "2026")

    def test_dashboard_subscribe_uses_recognized_tmdbid_when_item_has_none(self):
        dashboard = _import_dashboard()
        captured = {}

        class MediaChain:
            def recognize_media(self, meta, mtype):
                return _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=24680)

        class DownloadChain:
            def get_no_exists_info(self, meta, mediainfo):
                return False, None

        class SubscribeChain:
            def exists(self, mediainfo, meta):
                return False

            def add(self, **kwargs):
                captured.update(kwargs)
                return 1, ""

        sys.modules["app.chain.media"].MediaChain = MediaChain
        sys.modules["app.chain.download"].DownloadChain = DownloadChain
        sys.modules["app.chain.subscribe"].SubscribeChain = SubscribeChain

        result = dashboard.api_subscribe_from_rank(_Plugin(), None, "movie", "测试电影", "2026")

        self.assertTrue(result["success"])
        self.assertEqual(captured["tmdbid"], 24680)
        self.assertEqual(captured["mtype"], _MediaType.MOVIE)


if __name__ == "__main__":
    unittest.main()
