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
    local_utils.normalize_rss_domain = lambda value: value

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
    _folio_pc_month = 3
    _folio_pc_num = 50
    _folio_mobile_month = 2
    _folio_mobile_num = 15
    _dashboard_rank_keys = []

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

    def test_record_history_item_preserves_dashboard_rank_fields(self):
        history = [{"unique": "rank:1", "title": "old", "rank_index": 0, "rank_refreshed_at": "2026-06-21 10:00:00"}]
        entry = {"unique": "rank:1", "title": "new", "subscribed": True}

        self.feed._record_history_item(history, entry)

        self.assertEqual(history[0]["title"], "new")
        self.assertEqual(history[0]["rank_index"], 0)
        self.assertTrue(history[0]["subscribed"])

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

    def test_anti_cheat_ignores_zero_tmdb_vote(self):
        plugin = _Plugin()
        mediainfo = _MediaInfo(title="暂无评分")
        mediainfo.vote_average = 0

        should_skip = self.feed._check_anti_cheat(plugin, mediainfo)

        self.assertFalse(should_skip)
        self.assertEqual(plugin.data.get("anti_cheat_logs"), None)

    def test_anti_cheat_log_deduplicates_same_reason_title_and_detail(self):
        plugin = _Plugin()

        self.feed._log_anti_cheat(plugin, "observe", "title", "detail")
        self.feed._log_anti_cheat(plugin, "observe", "title", "detail")

        logs = plugin.data["anti_cheat_logs"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["reason"], "observe")
        self.assertEqual(logs[0]["title"], "title")
        self.assertEqual(logs[0]["count"], 2)

    def test_stats_returns_rank_breakdown_with_unknown_bucket(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin.data["subscribe_records"] = [
            {"title": "全球剧", "rank_key": "tv_global", "media_type": "电视剧", "time": "2026-06-22 10:00:00"},
            {"title": "旧记录", "rank_key": "", "media_type": "电影", "time": "2026-06-22 10:00:00"},
        ]

        data = dashboard.api_stats(plugin)["data"]

        rank_counts = {item["key"]: item["count"] for item in data["rank_stats"]}
        rank_names = {item["key"]: item["name"] for item in data["rank_stats"]}
        self.assertEqual(rank_counts["tv_global"], 1)
        self.assertEqual(rank_counts["coming"], 0)
        self.assertEqual(rank_counts["unknown"], 1)
        self.assertEqual(rank_names["unknown"], "未归类")

    def test_general_blacklist_skips_before_media_recognition(self):
        plugin = _Plugin()
        plugin._blacklist_keywords = "综艺"
        recognize_calls = []
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: recognize_calls.append(meta.title) or _MediaInfo(title=meta.title, year=meta.year, mtype=mtype)
        )
        plugin.data["rank_history_tv_global"] = [
            {"title": "测试综艺", "unique": "dc2_rank:https://example.com/a", "rank_index": 0}
        ]
        self.feed._fetch_rss = lambda self_obj, url: [
            {"title": "测试综艺", "link": "https://example.com/a", "mtype": "tv", "year": "2026"}
        ]

        self.feed._process_general(plugin, "https://rsshub.example/douban/list/tv_global_best_weekly?limit=1", {"key": "tv_global", "name": "全球口碑", "route": "/douban/list/tv_global_best_weekly"})

        self.assertEqual(recognize_calls, [])
        self.assertEqual(plugin.data["anti_cheat_logs"][0]["reason"], "黑名单关键词")
        self.assertNotIn("observing", plugin.data["rank_history_tv_global"][0])

    def test_general_year_filter_skips_before_observe(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = True
        plugin._observe_days = 2
        plugin._rank_configs = {"tv_global": {"year": 2027}}
        recognize_calls = []
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: recognize_calls.append(meta.title) or _MediaInfo(title=meta.title, year=meta.year, mtype=mtype)
        )
        plugin.data["rank_history_tv_global"] = [
            {"title": "旧年份条目", "unique": "dc2_rank:https://example.com/a", "time": "2026-06-21 10:00:00"}
        ]
        self.feed._fetch_rss = lambda self_obj, url: [
            {"title": "旧年份条目", "link": "https://example.com/a", "mtype": "tv", "year": "2026"}
        ]

        self.feed._process_general(plugin, "https://rsshub.example/douban/list/tv_global_best_weekly?limit=1", {"key": "tv_global", "name": "全球口碑", "route": "/douban/list/tv_global_best_weekly"})

        self.assertEqual(recognize_calls, [])
        self.assertNotIn("observing", plugin.data["rank_history_tv_global"][0])

    def test_run_once_refreshes_rank_data_then_subscribes_by_config(self):
        plugin = _Plugin()
        calls = []
        original_refresh = self.feed.refresh_rank_data
        original_subscribe = self.feed.subscribe_to_ranks

        def fake_refresh(plugin_obj, rank_keys=None):
            calls.append(("refresh", rank_keys))
            return {}

        def fake_subscribe(plugin_obj, refresh_when_unsafe=True):
            calls.append(("subscribe", refresh_when_unsafe))

        self.feed.refresh_rank_data = fake_refresh
        self.feed.subscribe_to_ranks = fake_subscribe
        try:
            self.feed.run_once(plugin)
        finally:
            self.feed.refresh_rank_data = original_refresh
            self.feed.subscribe_to_ranks = original_subscribe

        self.assertEqual(calls, [("refresh", None), ("subscribe", False)])

    def test_subscribe_to_ranks_can_skip_duplicate_refresh_when_unsafe(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = False
        plugin._observe_days = 0
        plugin._rank_configs = {}
        calls = []
        original_refresh = self.feed.refresh_rank_data
        self.feed.refresh_rank_data = lambda plugin_obj, rank_keys=None: calls.append(("refresh", rank_keys))
        try:
            self.feed.subscribe_to_ranks(plugin, refresh_when_unsafe=False)
        finally:
            self.feed.refresh_rank_data = original_refresh

        self.assertEqual(calls, [])

    def test_process_general_subscribes_after_dashboard_refresh_history_exists(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = False
        plugin._observe_days = 0
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        plugin.data["rank_history_tv_global"] = [
            {
                "title": "刷新条目",
                "unique": "dc2_rank:https://example.com/a",
                "rank_index": 0,
                "rank_refreshed_at": "2026-06-21 10:00:00",
            }
        ]
        calls = []
        self.feed._fetch_rss = lambda self_obj, url: [
            {"title": "刷新条目", "link": "https://example.com/a", "mtype": "tv", "year": "2026"}
        ]
        self.feed._add_sub = lambda self_obj, mediainfo, meta=None, rank_key="", rank_name="": calls.append((rank_key, mediainfo.title)) or True

        self.feed._process_general(plugin, "https://rsshub.example/douban/list/tv_global_best_weekly?limit=1", {"key": "tv_global", "name": "全球口碑", "route": "/douban/list/tv_global_best_weekly"})

        self.assertEqual(calls, [("tv_global", "刷新条目")])
        self.assertTrue(plugin.data["rank_history_tv_global"][0]["subscribed"])
        self.assertEqual(plugin.data["rank_history_tv_global"][0]["rank_index"], 0)

    def test_process_general_skips_existing_subscribed_marker(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = False
        plugin._observe_days = 0
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        plugin.data["rank_history_tv_global"] = [
            {"title": "已订阅", "unique": "dc2_rank:https://example.com/a", "subscribed": True}
        ]
        calls = []
        self.feed._fetch_rss = lambda self_obj, url: [
            {"title": "已订阅", "link": "https://example.com/a", "mtype": "tv", "year": "2026"}
        ]
        self.feed._add_sub = lambda *args, **kwargs: calls.append(args) or True

        self.feed._process_general(plugin, "https://rsshub.example/douban/list/tv_global_best_weekly?limit=1", {"key": "tv_global", "name": "全球口碑", "route": "/douban/list/tv_global_best_weekly"})

        self.assertEqual(calls, [])

    def test_process_general_skips_observe_when_media_exists_in_library(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = True
        plugin._observe_days = 2
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )

        class ExistingDownloadChain:
            def get_no_exists_info(self, meta=None, mediainfo=None):
                return True, None

        class EmptySubscribeChain:
            def exists(self, mediainfo=None, meta=None):
                return False

        self.feed.DownloadChain = ExistingDownloadChain
        self.feed.SubscribeChain = EmptySubscribeChain
        self.feed._fetch_rss = lambda self_obj, url: [
            {"title": "existing", "link": "https://example.com/a", "mtype": "tv", "year": "2026"}
        ]
        self.feed._add_sub = lambda *args, **kwargs: True

        self.feed._process_general(plugin, "https://rsshub.example/douban/list/tv_global_best_weekly?limit=1", {"key": "tv_global", "name": "rank", "route": "/douban/list/tv_global_best_weekly"})

        history = plugin.data["rank_history_tv_global"]
        self.assertEqual(len(history), 1)
        self.assertTrue(history[0]["existing"])
        self.assertNotIn("observing", history[0])

    def test_process_general_marks_refreshed_item_as_observing(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = True
        plugin._observe_days = 2
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        plugin.data["rank_history_tv_global"] = [
            {"title": "观察条目", "unique": "dc2_rank:https://example.com/a", "time": now, "rank_refreshed_at": now}
        ]
        calls = []
        self.feed._fetch_rss = lambda self_obj, url: [
            {"title": "观察条目", "link": "https://example.com/a", "mtype": "tv", "year": "2026"}
        ]
        self.feed._add_sub = lambda *args, **kwargs: calls.append(args) or True

        self.feed._process_general(plugin, "https://rsshub.example/douban/list/tv_global_best_weekly?limit=1", {"key": "tv_global", "name": "全球口碑", "route": "/douban/list/tv_global_best_weekly"})

        self.assertEqual(calls, [])
        self.assertTrue(plugin.data["rank_history_tv_global"][0]["observing"])
        self.assertEqual(plugin.data["rank_history_tv_global"][0]["first_seen"], now)

    def test_process_coming_observes_only_after_air_date_filter_passes(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = True
        plugin._observe_days = 2
        plugin._rank_configs = {"coming": {"wish_count": 1000, "air_days": 7}}
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        self.feed._fetch_coming_rss = lambda self_obj, url: [
            {"title": "远期剧集", "link": "https://example.com/a", "year": "2026", "wish_count": 2000, "regions": [], "genres": []}
        ]
        self.feed.utils.get_tmdb_air_date = lambda *args, **kwargs: "2026-12-31"
        self.feed.utils.is_within_days = lambda *args, **kwargs: False
        self.feed._add_sub = lambda *args, **kwargs: True

        self.feed._process_coming(plugin, "https://rsshub.example/douban/tv/coming?limit=1", {"key": "coming", "name": "即将上映", "route": "/douban/tv/coming"})

        self.assertEqual(plugin.data["coming_history"], [])

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

    def test_pending_observations_skips_existing_and_subscribed_items(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin._observe_days = 3
        first_seen = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        plugin.data["rank_history_tv_global"] = [
            {"title": "existing", "unique": "rank:1", "first_seen": first_seen, "observing": True, "existing": True},
            {"title": "subscribed", "unique": "rank:2", "first_seen": first_seen, "observing": True, "subscribed": True},
            {"title": "pending", "unique": "rank:3", "first_seen": first_seen, "observing": True},
        ]

        result = dashboard.api_pending_observations(plugin)["data"]

        self.assertEqual([item["unique"] for item in result], ["rank:3"])

    def test_pending_observations_marks_live_existing_item(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin._observe_days = 3
        first_seen = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        plugin.data["rank_history_tv_global"] = [
            {"title": "existing", "unique": "rank:1", "first_seen": first_seen, "observing": True}
        ]

        class ExistingMediaChain:
            def recognize_media(self, meta=None, mtype=None):
                return _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)

        class ExistingDownloadChain:
            def get_no_exists_info(self, meta=None, mediainfo=None):
                return True, None

        class EmptySubscribeChain:
            def exists(self, mediainfo=None, meta=None):
                return False

        sys.modules["app.chain.media"].MediaChain = ExistingMediaChain
        sys.modules["app.chain.download"].DownloadChain = ExistingDownloadChain
        sys.modules["app.chain.subscribe"].SubscribeChain = EmptySubscribeChain

        result = dashboard.api_pending_observations(plugin)["data"]

        self.assertEqual(result, [])
        self.assertFalse(plugin.data["rank_history_tv_global"][0]["observing"])
        self.assertTrue(plugin.data["rank_history_tv_global"][0]["existing"])

    def test_config_returns_blacklist_keywords_for_page(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin._blacklist_keywords = "综艺\n低分"

        result = dashboard.api_config(plugin)["data"]

        self.assertEqual(result["blacklist_keywords"], "综艺\n低分")

    def test_delete_subscribe_history_removes_one_record(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin.data["subscribe_records"] = [
            {"title": "保留", "time": "2026-06-21 10:00:00", "tmdbid": 1},
            {"title": "删除", "time": "2026-06-22 10:00:00", "tmdbid": 2},
        ]

        result = dashboard.api_delete_subscribe_history(plugin, time="2026-06-22 10:00:00", title="删除", tmdbid=2)

        self.assertTrue(result["success"])
        self.assertEqual([item["title"] for item in plugin.data["subscribe_records"]], ["保留"])

    def test_delete_observation_marks_item_ignored(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin.data["rank_history_tv_global"] = [
            {"title": "观察条目", "unique": "dc2_rank:a", "observing": True}
        ]

        result = dashboard.api_delete_observation(plugin, unique="dc2_rank:a", rank_key="tv_global")

        self.assertTrue(result["success"])
        self.assertFalse(plugin.data["rank_history_tv_global"][0]["observing"])
        self.assertTrue(plugin.data["rank_history_tv_global"][0]["observe_deleted"])

    def test_delete_anti_cheat_log_removes_one_record(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin.data["anti_cheat_logs"] = [
            {"title": "保留", "reason": "TMDB评分过低", "time": "2026-06-21 10:00:00"},
            {"title": "删除", "reason": "观察期未满", "time": "2026-06-22 10:00:00"},
        ]

        result = dashboard.api_delete_anti_cheat_log(plugin, time="2026-06-22 10:00:00", title="删除", reason="观察期未满")

        self.assertTrue(result["success"])
        self.assertEqual([item["title"] for item in plugin.data["anti_cheat_logs"]], ["保留"])

    def test_anti_cheat_logs_api_deduplicates_existing_records(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin.data["anti_cheat_logs"] = [
            {"title": "same", "reason": "observe", "detail": "d", "time": "2026-06-21 10:00:00"},
            {"title": "same", "reason": "observe", "detail": "d", "time": "2026-06-22 10:00:00"},
            {"title": "other", "reason": "observe", "detail": "d", "time": "2026-06-22 11:00:00"},
        ]

        result = dashboard.api_anti_cheat_logs(plugin)["data"]

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["title"], "same")
        self.assertEqual(result[0]["time"], "2026-06-22 10:00:00")
        self.assertEqual(result[0]["count"], 2)
        self.assertEqual(len(plugin.data["anti_cheat_logs"]), 2)

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

    def test_dashboard_rank_history_prefers_latest_refresh_batch_order(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin._dashboard_rank_keys = ["tv_global"]
        plugin.data["rank_history_tv_global"] = [
            {"title": "old-1", "unique": "old:1", "rank_index": 0, "rank_refreshed_at": "2026-06-20 10:00:00"},
            {"title": "new-2", "unique": "new:2", "rank_index": 1, "rank_refreshed_at": "2026-06-21 10:00:00"},
            {"title": "new-1", "unique": "new:1", "rank_index": 0, "rank_refreshed_at": "2026-06-21 10:00:00"},
            {"title": "old-2", "unique": "old:2", "rank_index": 1, "rank_refreshed_at": "2026-06-20 10:00:00"},
        ]

        result = dashboard.api_rank_history(plugin)["data"]["tv_global"]

        self.assertEqual([item["title"] for item in result], ["new-1", "new-2"])

    def test_refresh_rank_data_returns_dashboard_order_for_all_rank_types(self):
        plugin = _Plugin()
        plugin._rsshub_domain = "https://rsshub.example"
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        plugin.data["coming_history"] = [
            {
                "title": "旧即将播出",
                "unique": "dc2_coming:https://example.com/old-coming",
                "rank_index": 0,
                "rank_refreshed_at": "2026-06-20 10:00:00",
            }
        ]
        plugin.data["rank_history_tv_global"] = [
            {
                "title": "旧全球口碑",
                "unique": "dc2_rank:https://example.com/old-tv",
                "rank_index": 0,
                "rank_refreshed_at": "2026-06-20 10:00:00",
            }
        ]
        self.feed._fetch_coming_rss = lambda self_obj, url: [
            {"title": "聪明镇", "link": "https://example.com/smart-town", "year": "2026", "wish_count": 3000},
            {"title": "昨夜降至", "link": "https://example.com/last-night", "year": "2026", "wish_count": 2000},
        ]
        self.feed._fetch_rss = lambda self_obj, url: [
            {"title": "全球第一", "link": "https://example.com/global-1", "mtype": "tv", "year": "2026"},
            {"title": "全球第二", "link": "https://example.com/global-2", "mtype": "tv", "year": "2026"},
        ]
        original_sleep = self.feed.time.sleep
        self.feed.time.sleep = lambda seconds: None
        try:
            result = self.feed.refresh_rank_data(plugin, rank_keys=["coming", "tv_global"])
        finally:
            self.feed.time.sleep = original_sleep

        self.assertEqual([item["title"] for item in result["coming"]], ["聪明镇", "昨夜降至"])
        self.assertEqual([item["title"] for item in result["tv_global"]], ["全球第一", "全球第二"])

    def test_merge_rank_items_updates_existing_rank_order(self):
        plugin = _Plugin()
        plugin.data["rank_history_tv_global"] = [
            {
                "title": "old-a",
                "unique": "dc2_rank:https://example.com/a",
                "rank_index": 1,
                "rank_refreshed_at": "2026-06-20 10:00:00",
            },
            {
                "title": "old-b",
                "unique": "dc2_rank:https://example.com/b",
                "rank_index": 0,
                "rank_refreshed_at": "2026-06-20 10:00:00",
            },
        ]
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        rank = {"key": "tv_global", "name": "global", "route": "/douban/list/tv_global_best_weekly"}

        history = self.feed._merge_rank_items(
            plugin,
            "tv_global",
            [
                {"title": "new-b", "link": "https://example.com/b", "mtype": "tv", "year": "2026"},
                {"title": "new-a", "link": "https://example.com/a", "mtype": "tv", "year": "2026"},
            ],
            rank,
        )

        indexed = {item["unique"]: item for item in history}
        self.assertEqual(len(history), 2)
        self.assertEqual(indexed["dc2_rank:https://example.com/b"]["rank_index"], 0)
        self.assertEqual(indexed["dc2_rank:https://example.com/a"]["rank_index"], 1)
        self.assertEqual(indexed["dc2_rank:https://example.com/b"]["rank_order"], 1)
        self.assertEqual(indexed["dc2_rank:https://example.com/a"]["rank_order"], 2)
        self.assertEqual(
            indexed["dc2_rank:https://example.com/a"]["rank_refreshed_at"],
            indexed["dc2_rank:https://example.com/b"]["rank_refreshed_at"],
        )

    def test_merge_rank_items_preserves_observing_state_on_refresh(self):
        plugin = _Plugin()
        plugin.data["rank_history_tv_global"] = [
            {
                "title": "observing",
                "unique": "dc2_rank:https://example.com/a",
                "time": "2026-06-19 10:00:00",
                "first_seen": "2026-06-18 10:00:00",
                "observing": True,
            }
        ]
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        rank = {"key": "tv_global", "name": "global", "route": "/douban/list/tv_global_best_weekly"}

        history = self.feed._merge_rank_items(
            plugin,
            "tv_global",
            [{"title": "observing", "link": "https://example.com/a", "mtype": "tv", "year": "2026"}],
            rank,
        )

        self.assertTrue(history[0]["observing"])
        self.assertEqual(history[0]["first_seen"], "2026-06-18 10:00:00")
        self.assertEqual(history[0]["rank_index"], 0)

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
