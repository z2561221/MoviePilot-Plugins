import datetime
import importlib.util
import re
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
    local_utils.build_resolution_rule = lambda filters: None

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


def _import_migration():
    _install_stubs()
    sys.modules.pop("doubancenter.migration", None)
    spec = importlib.util.spec_from_file_location("doubancenter.migration", PLUGIN_DIR / "migration.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["doubancenter.migration"] = module
    spec.loader.exec_module(module)
    return module


def _import_service(name):
    _install_stubs()
    module_name = f"doubancenter.service.{name}"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_DIR / "service" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _Plugin:
    _enabled = True
    _notify = False
    _folio_enabled = True
    _observe_days = 2
    _observe_rank_keys = ["coming", "tv_real_time"]
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
        self.messages = []

    def get_data(self, key):
        return self.data.get(key)

    def save_data(self, key, value):
        self.data[key] = value

    def post_message(self, **kwargs):
        self.messages.append(kwargs)


class _MediaInfo:
    def __init__(self, title="测试电影", year="2026", mtype=_MediaType.MOVIE, tmdb_id=12345):
        self.title = title
        self.year = year
        self.type = mtype
        self.tmdb_id = tmdb_id
        self.vote_average = 8.0
        self.title_year = f"{title} ({year})" if year else title

    def get_poster_image(self):
        return "poster.jpg"

    def get_message_image(self):
        return "message.jpg"


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

    def test_default_observe_rank_keys_target_volatile_ranks(self):
        plugin = _Plugin()

        self.assertTrue(self.feed._rank_observe_enabled(plugin, "coming"))
        self.assertTrue(self.feed._rank_observe_enabled(plugin, "tv_real_time"))
        self.assertFalse(self.feed._rank_observe_enabled(plugin, "tv_global"))
        self.assertFalse(self.feed._rank_observe_enabled(plugin, "movie_weekly"))

    def test_observe_allows_item_after_window(self):
        plugin = _Plugin()
        old_time = (datetime.datetime.now() - datetime.timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        history = [{"unique": "rank:1", "title": "测试电影", "time": old_time, "observing": True}]

        should_skip = self.feed._check_observe(plugin, "rank:1", history, title="测试电影")

        self.assertFalse(should_skip)
        logs = plugin.data["anti_cheat_logs"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["reason"], "观察完成")
        self.assertEqual(logs[0]["title"], "测试电影")
        self.assertIn("达到", logs[0]["detail"])
        self.assertIsNone(plugin.data.get("archive_records"))

    def test_custom_rank_history_key_is_stable(self):
        source = "https://example.com/rss?token=abc"

        first = self.feed._custom_rank_history_key(source)
        second = self.feed._custom_rank_history_key(source)

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("rank_history_custom_"))
        self.assertNotIn("-", first)

    def test_migration_normalizes_legacy_subscribe_usernames(self):
        migration = _import_migration()

        class FakeOper:
            def __init__(self):
                self.records = [
                    types.SimpleNamespace(id=1, username="豆瓣榜单"),
                    types.SimpleNamespace(id=2, username="豆瓣中心-即映"),
                    types.SimpleNamespace(id=3, username="豆瓣中心"),
                    types.SimpleNamespace(id=4, username="其他来源"),
                ]
                self.updates = []

            def list(self):
                return self.records

            def update(self, record_id, payload):
                self.updates.append((record_id, payload))

        oper = FakeOper()

        changed = migration.normalize_operation_records(oper)

        self.assertEqual(changed, 2)
        self.assertEqual(
            oper.updates,
            [
                (1, {"username": "豆瓣中心"}),
                (2, {"username": "豆瓣中心"}),
            ],
        )

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

    def test_observe_uses_rank_selection_not_anti_cheat_switch(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = False
        plugin._observe_rank_keys = ["tv_real_time"]
        history = []

        should_skip = self.feed._check_observe(plugin, "rank:1", history, title="测试电影", rank_key="tv_real_time")

        self.assertTrue(should_skip)
        self.assertEqual(history[0]["unique"], "rank:1")

    def test_observe_days_make_subscription_safe_when_observe_ranks_selected(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = False
        plugin._observe_days = 2
        plugin._observe_rank_keys = ["coming"]

        has_filter = self.feed._has_global_subscription_filter(plugin)

        self.assertTrue(has_filter)

    def test_blacklist_stays_active_when_anti_cheat_disabled(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = False
        plugin._blacklist_keywords = "综艺"

        should_skip = self.feed._check_blacklist(plugin, "测试综艺")
        has_filter = self.feed._has_global_subscription_filter(plugin)

        self.assertTrue(should_skip)
        self.assertTrue(has_filter)

    def test_blacklist_matches_description_regex_and_space_tokens(self):
        plugin = _Plugin()
        plugin._blacklist_keywords = "regex:诺曼底\\d+小时\n葬送 芙莉莲"

        regex_hit = self.feed._check_blacklist(plugin, "普通标题", description="诺曼底72小时 热门条目", link="https://rsshub.example/a")
        token_hit = self.feed._check_blacklist(plugin, "葬送的芙莉莲 第二季", description="", link="https://rsshub.example/b")
        miss = self.feed._check_blacklist(plugin, "葬送的普通剧", description="没有另一个关键词")

        self.assertTrue(regex_hit)
        self.assertTrue(token_hit)
        self.assertFalse(miss)
        self.assertEqual(plugin.data["anti_cheat_logs"][0]["link"], "https://rsshub.example/a")

    def test_global_subscription_filter_ignores_legacy_score_flags(self):
        plugin = _Plugin()
        plugin._blacklist_keywords = ""
        plugin._observe_days = 0
        plugin._observe_rank_keys = []
        plugin._anti_cheat_enabled = True
        plugin._anti_cheat_min_vote = 9.0

        has_filter = self.feed._has_global_subscription_filter(plugin)

        self.assertFalse(has_filter)

    def test_process_general_subscribes_low_tmdb_score_without_score_filter(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = True
        plugin._anti_cheat_min_vote = 9.0
        plugin._observe_days = 0
        plugin._observe_rank_keys = []
        calls = []

        def low_score_media(title, year, mtype):
            mediainfo = _MediaInfo(title=title, year=year, mtype=mtype, tmdb_id=67890)
            mediainfo.vote_average = 3.2
            return mediainfo

        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: low_score_media(meta.title, meta.year, mtype)
        )
        self.feed._fetch_rss = lambda self_obj, url: [
            {"title": "低分也订阅", "link": "https://example.com/a", "mtype": "tv", "year": "2026"}
        ]
        self.feed._add_sub = lambda self_obj, mediainfo, meta=None, rank_key="", rank_name="", **kwargs: calls.append((rank_key, mediainfo.title, mediainfo.vote_average)) or True

        self.feed._process_general(plugin, "https://rsshub.example/douban/list/tv_global_best_weekly?limit=1", {"key": "tv_global", "name": "全球口碑", "route": "/douban/list/tv_global_best_weekly"})

        self.assertEqual(calls, [("tv_global", "低分也订阅", 3.2)])
        self.assertEqual(plugin.data.get("anti_cheat_logs"), None)

    def test_anti_cheat_ignores_zero_tmdb_vote(self):
        plugin = _Plugin()
        mediainfo = _MediaInfo(title="暂无评分")
        mediainfo.vote_average = 0

        self.assertFalse(hasattr(self.feed, "_check_anti_cheat"))
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

    def test_successful_subscription_cleans_observe_anti_cheat_logs(self):
        plugin = _Plugin()
        plugin.data["anti_cheat_logs"] = [
            {"title": "keep", "reason": "TMDB评分过低", "detail": "d", "time": "2026-06-21 10:00:00"},
            {"title": "target", "reason": "观察期首次记录", "detail": "需要观察 2 天", "time": "2026-06-21 10:00:00"},
            {"title": "target", "reason": "观察期未满", "detail": "已过 1 天，需要 2 天", "time": "2026-06-22 10:00:00"},
            {"title": "target", "reason": "\u89c2\u5bdf\u671f\u5b8c\u6210", "detail": "已过 2 天，达到 2 天", "time": "2026-06-23 10:00:00"},
        ]

        class SubscribeChain:
            def add(self, **kwargs):
                return 1, ""

        self.feed.SubscribeChain = SubscribeChain

        result = self.feed._add_sub(plugin, _MediaInfo(title="target", mtype=_MediaType.TV), rank_key="tv_global")

        self.assertTrue(result)
        self.assertEqual([item["title"] for item in plugin.data["anti_cheat_logs"]], ["keep", "target"])
        self.assertEqual(plugin.data["anti_cheat_logs"][1]["reason"], "观察完成")

    def test_existing_subscription_branch_cleans_observe_anti_cheat_logs(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = True
        plugin._observe_days = 2
        plugin._observe_rank_keys = ["tv_global"]
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title="existing", year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        plugin.data["anti_cheat_logs"] = [
            {"title": "keep", "reason": "TMDB low", "detail": "d", "time": "2026-06-21 10:00:00"},
            {"title": "existing", "reason": "\u89c2\u5bdf\u671f\u9996\u6b21\u8bb0\u5f55", "detail": "d", "time": "2026-06-21 10:00:00"},
            {"title": "existing", "reason": "\u89c2\u5bdf\u671f\u672a\u6ee1", "detail": "d", "time": "2026-06-22 10:00:00"},
        ]

        class UnusedDownloadChain:
            def get_no_exists_info(self, meta=None, mediainfo=None):
                raise AssertionError("不应在订阅前读取媒体库存在状态")

        class ExistingSubscribeChain:
            def exists(self, mediainfo=None, meta=None):
                return True

        self.feed.DownloadChain = UnusedDownloadChain
        self.feed.SubscribeChain = ExistingSubscribeChain
        self.feed._fetch_rss = lambda self_obj, url: [
            {"title": "existing", "link": "https://example.com/a", "mtype": "tv", "year": "2026"}
        ]

        self.feed._process_general(plugin, "https://rsshub.example/douban/list/tv_global_best_weekly?limit=1", {"key": "tv_global", "name": "rank", "route": "/douban/list/tv_global_best_weekly"})

        self.assertEqual([item["title"] for item in plugin.data["anti_cheat_logs"]], ["keep"])

    def test_write_subscribe_record_deduplicates_same_media_rank_and_status(self):
        plugin = _Plugin()
        media = _MediaInfo(title="duplicate", year="2026", mtype=_MediaType.TV, tmdb_id=67890)

        self.feed._write_subscribe_record(plugin, media, rank_key="tv_global", rank_name="全球口碑")
        self.feed._write_subscribe_record(plugin, media, rank_key="tv_global", rank_name="全球口碑")

        self.assertEqual(len(plugin.data["subscribe_records"]), 1)
        self.assertEqual(plugin.data["subscribe_records"][0]["title"], "duplicate")

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
        self.assertEqual(plugin.data["anti_cheat_logs"][0]["reason"], "黑名拦截")
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
        original_subscribe = self.feed.subscribe_to_rank_snapshots

        def fake_refresh(plugin_obj, rank_keys=None, limit_by_rank=None, with_snapshots=False):
            calls.append(("refresh", rank_keys, limit_by_rank, with_snapshots))
            return {}, {"snapshot": True}

        def fake_subscribe(plugin_obj, snapshots):
            calls.append(("subscribe_snapshots", snapshots))

        self.feed.refresh_rank_data = fake_refresh
        self.feed.subscribe_to_rank_snapshots = fake_subscribe
        try:
            self.feed.run_once(plugin)
        finally:
            self.feed.refresh_rank_data = original_refresh
            self.feed.subscribe_to_rank_snapshots = original_subscribe

        self.assertEqual(calls, [("refresh", None, {}, True), ("subscribe_snapshots", {"snapshot": True})])

    def test_scheduled_run_refreshes_rank_data_then_subscribes_by_config(self):
        plugin = _Plugin()
        calls = []
        original_refresh = self.feed.refresh_rank_data
        original_subscribe = self.feed.subscribe_to_rank_snapshots

        def fake_refresh(plugin_obj, rank_keys=None, limit_by_rank=None, with_snapshots=False):
            calls.append(("refresh", rank_keys, limit_by_rank, with_snapshots))
            return {}, {"snapshot": True}

        def fake_subscribe(plugin_obj, snapshots):
            calls.append(("subscribe_snapshots", snapshots))

        self.feed.refresh_rank_data = fake_refresh
        self.feed.subscribe_to_rank_snapshots = fake_subscribe
        try:
            self.feed.run_scheduled(plugin)
        finally:
            self.feed.refresh_rank_data = original_refresh
            self.feed.subscribe_to_rank_snapshots = original_subscribe

        self.assertEqual(calls, [("refresh", None, {}, True), ("subscribe_snapshots", {"snapshot": True})])

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

    def test_subscribe_to_ranks_skips_enabled_rank_when_count_is_zero(self):
        plugin = _Plugin()
        plugin._rsshub_domain = "https://rsshub.example"
        plugin._rank_configs = {"tv_global": {"enabled": True, "count": 0}}
        calls = []
        original_fetch = self.feed._fetch_rss
        self.feed._fetch_rss = lambda self_obj, url: calls.append(url) or []
        try:
            self.feed.subscribe_to_ranks(plugin, refresh_when_unsafe=False)
        finally:
            self.feed._fetch_rss = original_fetch

        self.assertEqual(calls, [])

    def test_run_once_uses_single_recognized_snapshot_for_subscription_window(self):
        plugin = _Plugin()
        plugin._rsshub_domain = "https://rsshub.example"
        plugin._observe_days = 0
        plugin._rank_configs = {"tv_global": {"enabled": True, "count": 7}}
        fetch_urls = []
        recognize_calls = []
        subscribed = []

        def make_items(limit):
            return [
                {"title": f"item-{index}", "link": f"https://example.com/{index}", "mtype": "tv", "year": "2026"}
                for index in range(1, limit + 1)
            ]

        def fake_fetch(self_obj, url):
            fetch_urls.append(url)
            match = re.search(r"limit=(\d+)", url)
            return make_items(int(match.group(1)) if match else 0)

        def fake_recognize(meta, mtype):
            recognize_calls.append(meta.title)
            return _MediaInfo(title=f"CN {meta.title}", year=meta.year, mtype=mtype, tmdb_id=1000 + len(recognize_calls))

        plugin.chain = types.SimpleNamespace(recognize_media=fake_recognize)
        original_fetch = self.feed._fetch_rss
        original_add_sub = self.feed._add_sub
        original_sleep = self.feed.time.sleep
        self.feed._fetch_rss = fake_fetch
        self.feed._add_sub = lambda self_obj, mediainfo, meta=None, rank_key="", rank_name="", **kwargs: subscribed.append((rank_key, mediainfo.title)) or True
        self.feed.time.sleep = lambda seconds: None
        try:
            self.feed.run_once(plugin)
        finally:
            self.feed._fetch_rss = original_fetch
            self.feed._add_sub = original_add_sub
            self.feed.time.sleep = original_sleep

        self.assertEqual(fetch_urls, ["https://rsshub.example/douban/list/tv_global_best_weekly?limit=7"])
        self.assertEqual(recognize_calls, [f"item-{index}" for index in range(1, 8)])
        self.assertEqual(subscribed, [("tv_global", f"CN item-{index}") for index in range(1, 8)])
        dashboard_items = self.feed.get_dashboard_rank_items(plugin, "tv_global", limit=5)
        self.assertEqual([item["title"] for item in dashboard_items], [f"CN item-{index}" for index in range(1, 6)])

    def test_run_once_keeps_observation_inside_subscription_window_outside_display_window(self):
        plugin = _Plugin()
        plugin._rsshub_domain = "https://rsshub.example"
        plugin._observe_days = 2
        plugin._observe_rank_keys = ["tv_global"]
        plugin._rank_configs = {"tv_global": {"enabled": True, "count": 7}}
        first_seen = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        plugin.data["rank_history_tv_global"] = [
            {
                "title": "old item 6",
                "unique": "dc2_rank:https://example.com/6",
                "first_seen": first_seen,
                "observing": True,
            }
        ]

        def fake_fetch(self_obj, url):
            return [
                {"title": f"item-{index}", "link": f"https://example.com/{index}", "mtype": "tv", "year": "2026"}
                for index in range(1, 8)
            ]

        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        original_fetch = self.feed._fetch_rss
        original_add_sub = self.feed._add_sub
        original_sleep = self.feed.time.sleep
        self.feed._fetch_rss = fake_fetch
        self.feed._add_sub = lambda *args, **kwargs: True
        self.feed.time.sleep = lambda seconds: None
        try:
            self.feed.run_once(plugin)
        finally:
            self.feed._fetch_rss = original_fetch
            self.feed._add_sub = original_add_sub
            self.feed.time.sleep = original_sleep

        indexed = {item["unique"]: item for item in plugin.data["rank_history_tv_global"]}
        self.assertTrue(indexed["dc2_rank:https://example.com/6"]["observing"])
        self.assertNotIn("observe_dropped_at", indexed["dc2_rank:https://example.com/6"])

    def test_snapshot_subscription_logs_filter_summary_and_skip_reason(self):
        plugin = _Plugin()
        plugin._rank_configs = {"tv_global": {"enabled": True, "count": 1, "vote": "9.0", "year": "2024"}}
        media = _MediaInfo(title="low score", year="2026", mtype=_MediaType.TV, tmdb_id=67890)
        media.vote_average = 7.0
        messages = []

        class CaptureLogger:
            def info(self, message, *args, **kwargs):
                messages.append(str(message))

            def warning(self, message, *args, **kwargs):
                messages.append(str(message))

            def error(self, message, *args, **kwargs):
                messages.append(str(message))

        original_logger = self.feed.logger
        self.feed.logger = CaptureLogger()
        try:
            self.feed.subscribe_to_rank_snapshots(
                plugin,
                {
                    "tv_global": {
                        "items": [
                            {
                                "raw": {"title": "low score", "link": "https://example.com/a", "mtype": "tv", "year": "2026"},
                                "entry": {
                                    "title": "low score",
                                    "link": "https://example.com/a",
                                    "media_type": "tv",
                                    "year": "2026",
                                    "unique": "dc2_rank:https://example.com/a",
                                },
                                "mediainfo": media,
                            }
                        ]
                    }
                },
            )
        finally:
            self.feed.logger = original_logger

        summaries = [message for message in messages if "豆瓣中心：[全球口碑] 订阅筛选完成" in message]
        self.assertEqual(len(summaries), 1)
        self.assertIn("筛选条件：候选 1 条；评分>=9.0；年份>=2024", summaries[0])
        self.assertIn("- 跳过《low score》：评分 7.0 < 9.0", summaries[0])

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
        self.feed._add_sub = lambda self_obj, mediainfo, meta=None, rank_key="", rank_name="", **kwargs: calls.append((rank_key, mediainfo.title)) or True

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

    def test_process_general_still_observes_when_media_exists_only_in_library(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = True
        plugin._observe_days = 2
        plugin._observe_rank_keys = ["tv_global"]
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
        self.assertTrue(history[0]["observing"])
        self.assertNotIn("existing", history[0])

    def test_merge_rank_items_recognizes_display_items_without_subscribing(self):
        plugin = _Plugin()
        calls = []
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: calls.append((meta.title, mtype)) or _MediaInfo(title=f"CN {meta.title}", year="2026", mtype=mtype, tmdb_id=67890)
        )
        rank = {"key": "tv_global", "name": "global", "route": "/douban/list/tv_global_best_weekly"}

        history = self.feed._merge_rank_items(
            plugin,
            "tv_global",
            [{"title": "rss item", "link": "https://example.com/a", "mtype": "tv", "year": "2026"}],
            rank,
        )

        self.assertEqual(calls, [("rss item", _MediaType.TV)])
        self.assertEqual(history[0]["title"], "CN rss item")
        self.assertEqual(history[0]["tmdbid"], 67890)
        self.assertEqual(history[0]["poster"], "poster.jpg")
        self.assertNotIn("subscribe_records", plugin.data)

    def test_process_general_marks_refreshed_item_as_observing(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = True
        plugin._observe_days = 2
        plugin._observe_rank_keys = ["tv_global"]
        plugin._observe_rank_keys = ["tv_global"]
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

    def test_process_general_skips_observe_for_unselected_weekly_rank(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = False
        plugin._observe_days = 2
        plugin._observe_rank_keys = ["coming", "tv_real_time"]
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        plugin.data["rank_history_tv_global"] = []
        calls = []
        self.feed._fetch_rss = lambda self_obj, url: [
            {"title": "稳定周榜", "link": "https://example.com/a", "mtype": "tv", "year": "2026"}
        ]
        self.feed._add_sub = lambda self_obj, mediainfo, meta=None, rank_key="", rank_name="", **kwargs: calls.append((rank_key, mediainfo.title)) or True

        self.feed._process_general(plugin, "https://rsshub.example/douban/list/tv_global_best_weekly?limit=1", {"key": "tv_global", "name": "全球口碑", "route": "/douban/list/tv_global_best_weekly"})

        self.assertEqual(calls, [("tv_global", "稳定周榜")])
        self.assertTrue(plugin.data["rank_history_tv_global"][0]["subscribed"])

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

    def test_process_coming_ignores_legacy_region_and_genre_filters(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = False
        plugin._observe_days = 0
        plugin._region_filters = ["美国"]
        plugin._genre_filters = ["悬疑"]
        plugin._rank_configs = {"coming": {"wish_count": 1000, "air_days": 7}}
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        self.feed.utils.match_any_filter = lambda values, filters: False
        self.feed.utils.get_tmdb_air_date = lambda *args, **kwargs: "2026-06-25"
        self.feed.utils.is_within_days = lambda *args, **kwargs: True
        self.feed._fetch_coming_rss = lambda self_obj, url: [
            {"title": "地区不匹配但应忽略", "link": "https://example.com/a", "year": "2026", "wish_count": 2000, "regions": ["日本"], "genres": ["动画"]}
        ]
        calls = []
        self.feed._add_sub = lambda *args, **kwargs: calls.append(kwargs) or True

        self.feed._process_coming(plugin, "https://rsshub.example/douban/tv/coming?limit=1", {"key": "coming", "name": "即将上映", "route": "/douban/tv/coming"})

        self.assertEqual(len(calls), 1)

    def test_process_coming_drops_observations_outside_count_window(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = True
        plugin._observe_days = 2
        plugin._observe_rank_keys = ["coming"]
        plugin._rank_configs = {"coming": {"count": 1, "wish_count": 1000, "air_days": 7}}
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        plugin.data["coming_history"] = [
            {
                "title": "跌出候选",
                "unique": "dc2_coming:https://example.com/old",
                "first_seen": "2026-07-01 10:00:00",
                "observing": True,
            }
        ]
        plugin.data["anti_cheat_logs"] = [
            {"title": "跌出候选", "reason": "观察期未满", "detail": "已过 1 天，需要 2 天", "time": "2026-07-02 10:00:00"}
        ]
        self.feed._fetch_coming_rss = lambda self_obj, url: [
            {"title": "仍在候选", "link": "https://example.com/new", "year": "2026", "wish_count": 2000}
        ]
        self.feed.utils.get_tmdb_air_date = lambda *args, **kwargs: "2026-07-05"
        self.feed.utils.is_within_days = lambda *args, **kwargs: True
        self.feed._add_sub = lambda *args, **kwargs: True

        self.feed._process_coming(
            plugin,
            "https://rsshub.example/douban/tv/coming?limit=1",
            {"key": "coming", "name": "即将上映", "route": "/douban/tv/coming"},
        )

        dropped = plugin.data["coming_history"][0]
        self.assertFalse(dropped["observing"])
        self.assertIn("observe_dropped_at", dropped)
        self.assertEqual(dropped["observe_dropped_reason"], "跌出榜单")

    def test_process_coming_snapshots_drops_observations_outside_count_window(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = True
        plugin._observe_days = 2
        plugin._observe_rank_keys = ["coming"]
        plugin._rank_configs = {"coming": {"count": 1, "wish_count": 1000, "air_days": 7}}
        plugin.chain = types.SimpleNamespace()
        plugin.data["coming_history"] = [
            {
                "title": "快照跌出候选",
                "unique": "dc2_coming:https://example.com/old-snapshot",
                "first_seen": "2026-07-01 10:00:00",
                "observing": True,
            }
        ]
        snapshots = [
            {
                "raw": {"title": "快照仍在候选", "link": "https://example.com/new-snapshot", "year": "2026", "wish_count": 2000},
                "entry": {
                    "title": "快照仍在候选",
                    "link": "https://example.com/new-snapshot",
                    "year": "2026",
                    "wish_count": 2000,
                    "unique": "dc2_coming:https://example.com/new-snapshot",
                },
                "mediainfo": _MediaInfo(title="快照仍在候选", year="2026", mtype=_MediaType.TV, tmdb_id=67890),
            }
        ]
        self.feed.utils.get_tmdb_air_date = lambda *args, **kwargs: "2026-07-05"
        self.feed.utils.is_within_days = lambda *args, **kwargs: True
        self.feed._add_sub = lambda *args, **kwargs: True

        self.feed._process_coming_snapshots(
            plugin,
            snapshots,
            {"key": "coming", "name": "即将上映", "route": "/douban/tv/coming", "coming": True},
        )

        dropped = plugin.data["coming_history"][0]
        self.assertFalse(dropped["observing"])
        self.assertIn("observe_dropped_at", dropped)

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
            {"title": "existing", "unique": "rank:1", "first_seen": first_seen, "observing": True, "existing": True, "existing_reason": "subscribe"},
            {"title": "subscribed", "unique": "rank:2", "first_seen": first_seen, "observing": True, "subscribed": True},
            {"title": "pending", "unique": "rank:3", "first_seen": first_seen, "observing": True},
        ]

        result = dashboard.api_pending_observations(plugin)["data"]

        self.assertEqual([item["unique"] for item in result], ["rank:3"])

    def test_pending_observations_keeps_item_when_only_library_exists(self):
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

        self.assertEqual([item["unique"] for item in result], ["rank:1"])
        self.assertTrue(plugin.data["rank_history_tv_global"][0]["observing"])
        self.assertNotIn("existing", plugin.data["rank_history_tv_global"][0])

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

    def test_subscribe_history_api_deduplicates_existing_records(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin.data["subscribe_records"] = [
            {"title": "same", "year": "2026", "tmdbid": 1, "rank_key": "tv_global", "status": "success", "time": "2026-06-21 10:00:00"},
            {"title": "same", "year": "2026", "tmdbid": 1, "rank_key": "tv_global", "status": "success", "time": "2026-06-22 10:00:00"},
            {"title": "other", "year": "2026", "tmdbid": 2, "rank_key": "tv_global", "status": "success", "time": "2026-06-22 11:00:00"},
        ]

        result = dashboard.api_subscribe_history(plugin)["data"]

        self.assertEqual(result["total"], 2)
        self.assertEqual([item["title"] for item in plugin.data["subscribe_records"]], ["other", "same"])
        self.assertEqual(plugin.data["subscribe_records"][1]["time"], "2026-06-22 10:00:00")

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

    def test_merge_bangumi_rank_items_stores_recognized_chinese_title(self):
        plugin = _Plugin()
        calls = []

        def recognize_media(meta, mtype):
            calls.append((meta.title, meta.year, mtype))
            return _MediaInfo(title="中文动画", year="2026", mtype=mtype, tmdb_id=67890)

        plugin.chain = types.SimpleNamespace(recognize_media=recognize_media)
        rank = {"key": "bangumi", "name": "BangumiTV", "route": "/bangumi.tv/anime/followrank"}

        history = self.feed._merge_rank_items(
            plugin,
            "bangumi",
            [{"title": "Japanese Anime", "link": "https://bgm.tv/subject/123", "mtype": "tv", "year": ""}],
            rank,
        )

        self.assertEqual(calls, [("Japanese Anime", None, _MediaType.TV)])
        self.assertEqual(history[0]["title"], "中文动画")
        self.assertEqual(history[0]["original_title"], "Japanese Anime")
        self.assertEqual(history[0]["year"], "2026")
        self.assertEqual(history[0]["tmdbid"], 67890)
        self.assertEqual(history[0]["media_type"], "tv")

    def test_dashboard_rank_items_migrates_cached_bangumi_title_by_tmdbid(self):
        plugin = _Plugin()
        calls = []
        plugin.data["rank_history_bangumi"] = [
            {
                "title": "Japanese Anime",
                "year": "",
                "tmdbid": 67890,
                "unique": "dc2_rank:https://bgm.tv/subject/123",
                "rank_index": 0,
                "rank_refreshed_at": "2026-06-21 10:00:00",
            }
        ]

        def recognize_media(meta, mtype, tmdbid=None):
            calls.append((meta.title, tmdbid, mtype))
            return _MediaInfo(title="中文动画", year="2026", mtype=mtype, tmdb_id=tmdbid)

        plugin.chain = types.SimpleNamespace(recognize_media=recognize_media)

        result = self.feed.get_dashboard_rank_items(plugin, "bangumi", limit=5)

        self.assertEqual(calls, [("Japanese Anime", 67890, _MediaType.TV)])
        self.assertEqual(result[0]["title"], "中文动画")
        self.assertEqual(result[0]["original_title"], "Japanese Anime")
        self.assertEqual(result[0]["tmdbid"], 67890)
        self.assertEqual(plugin.data["rank_history_bangumi"][0]["title"], "中文动画")

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
        recognize_calls = []
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: recognize_calls.append(meta.title) or _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
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
        self.assertEqual(recognize_calls, ["聪明镇", "昨夜降至", "全球第一", "全球第二"])

    def test_refresh_rank_data_requests_only_five_items(self):
        plugin = _Plugin()
        plugin._rsshub_domain = "https://rsshub.example"
        urls = []
        self.feed._fetch_rss = lambda self_obj, url: urls.append(url) or []
        original_sleep = self.feed.time.sleep
        self.feed.time.sleep = lambda seconds: None
        try:
            self.feed.refresh_rank_data(plugin, rank_keys=["tv_global"])
        finally:
            self.feed.time.sleep = original_sleep

        self.assertEqual(urls, ["https://rsshub.example/douban/list/tv_global_best_weekly?limit=5"])

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

    def test_process_general_drops_observation_when_item_leaves_candidate_window(self):
        plugin = _Plugin()
        plugin._anti_cheat_enabled = True
        plugin._observe_days = 2
        plugin._observe_rank_keys = ["tv_global"]
        first_seen = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        plugin.data["rank_history_tv_global"] = [
            {
                "title": "跌出榜单",
                "unique": "dc2_rank:https://example.com/old",
                "first_seen": first_seen,
                "observing": True,
            }
        ]
        plugin.chain = types.SimpleNamespace(
            recognize_media=lambda meta, mtype: _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=67890)
        )
        self.feed._fetch_rss = lambda self_obj, url: [
            {"title": "新条目", "link": "https://example.com/new", "mtype": "tv", "year": "2026"}
        ]

        self.feed._process_general(plugin, "https://rsshub.example/douban/list/tv_global_best_weekly?limit=1", {"key": "tv_global", "name": "全球口碑", "route": "/douban/list/tv_global_best_weekly"})

        indexed = {item["unique"]: item for item in plugin.data["rank_history_tv_global"]}
        self.assertFalse(indexed["dc2_rank:https://example.com/old"].get("observing"))
        self.assertEqual(indexed["dc2_rank:https://example.com/old"]["observe_dropped_reason"], "跌出榜单")

    def test_dashboard_subscribe_ignores_library_exists_when_item_has_none(self):
        dashboard = _import_dashboard()
        captured = {}

        class MediaChain:
            def recognize_media(self, meta, mtype):
                return _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=24680)

        class DownloadChain:
            def get_no_exists_info(self, meta, mediainfo):
                raise AssertionError("不应在订阅前读取媒体库存在状态")

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
        self.assertEqual(captured["username"], "豆瓣中心")

        self.assertIsNone(captured["season"])

    def test_dashboard_subscribe_can_use_bangumi_subject_without_tmdbid(self):
        dashboard = _import_dashboard()
        captured = {}

        class MediaChain:
            def recognize_media(self, meta, mtype, bangumiid=None):
                return None

        class SubscribeChain:
            def add(self, **kwargs):
                captured.update(kwargs)
                return 1, ""

        sys.modules["app.chain.media"].MediaChain = MediaChain
        sys.modules["app.chain.subscribe"].SubscribeChain = SubscribeChain
        sys.modules["doubancenter.feed"]._fetch_bangumi_subject = lambda plugin, bangumiid: {
            "id": int(bangumiid),
            "name_cn": "中文动画",
            "date": "2026-04-08",
            "images": {"large": "bangumi.jpg"},
        }

        result = dashboard.api_subscribe_from_rank(_Plugin(), None, "tv", "Japanese Anime", "", bangumi_id=547888)

        self.assertTrue(result["success"])
        self.assertEqual(captured["title"], "中文动画")
        self.assertEqual(captured["year"], "2026")
        self.assertEqual(captured["mtype"], _MediaType.TV)
        self.assertEqual(captured["bangumiid"], 547888)
        self.assertIsNone(captured["tmdbid"])
        self.assertEqual(captured["username"], "豆瓣中心")

    def test_dashboard_resolve_media_does_not_create_subscription(self):
        dashboard = _import_dashboard()
        calls = []

        class MediaChain:
            def recognize_media(self, meta, mtype):
                calls.append((meta.title, meta.year, mtype))
                return _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=24680)

        sys.modules["app.chain.media"].MediaChain = MediaChain

        result = dashboard.api_resolve_media_from_rank(_Plugin(), "tv", "手动剧集", "2026")

        self.assertTrue(result["success"])
        self.assertEqual(calls, [("手动剧集", "2026", _MediaType.TV)])
        self.assertEqual(result["data"]["tmdb_id"], 24680)
        self.assertEqual(result["data"]["type"], "电视剧")

    def test_dashboard_resolve_media_falls_back_to_tmdbid_when_title_unrecognized(self):
        dashboard = _import_dashboard()

        class MediaChain:
            def recognize_media(self, meta, mtype):
                return None

        sys.modules["app.chain.media"].MediaChain = MediaChain

        result = dashboard.api_resolve_media_from_rank(_Plugin(), "tv", "Japanese Anime", "", tmdb_id=67890)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["title"], "Japanese Anime")
        self.assertEqual(result["data"]["tmdb_id"], 67890)
        self.assertEqual(result["data"]["media_id"], 67890)
        self.assertEqual(result["data"]["type"], "电视剧")

    def test_dashboard_resolve_media_uses_bangumiid_when_tmdb_unrecognized(self):
        dashboard = _import_dashboard()
        calls = []

        class MediaChain:
            def recognize_media(self, meta, mtype, bangumiid=None):
                calls.append((meta.title, mtype, bangumiid))
                if bangumiid:
                    media = _MediaInfo(title="中文动画", year="2026", mtype=mtype, tmdb_id=None)
                    media.bangumi_id = bangumiid
                    media.poster_path = "bangumi.jpg"
                    return media
                return None

        sys.modules["app.chain.media"].MediaChain = MediaChain

        result = dashboard.api_resolve_media_from_rank(_Plugin(), "tv", "Japanese Anime", "", bangumi_id=547888)

        self.assertTrue(result["success"])
        self.assertEqual(calls, [("Japanese Anime", _MediaType.TV, None), ("Japanese Anime", _MediaType.TV, 547888)])
        self.assertEqual(result["data"]["title"], "中文动画")
        self.assertEqual(result["data"]["bangumi_id"], 547888)
        self.assertEqual(result["data"]["mediaid_prefix"], "bangumi")
        self.assertEqual(result["data"]["media_id"], 547888)
        self.assertEqual(result["data"]["source"], "bangumi")

    def test_dashboard_resolve_media_uses_bangumi_subject_when_chain_misses(self):
        dashboard = _import_dashboard()

        class MediaChain:
            def recognize_media(self, meta, mtype, bangumiid=None):
                return None

        sys.modules["app.chain.media"].MediaChain = MediaChain
        sys.modules["doubancenter.feed"]._fetch_bangumi_subject = lambda plugin, bangumiid: {
            "id": int(bangumiid),
            "name": "Japanese Anime",
            "name_cn": "中文动画",
            "date": "2026-04-08",
            "images": {"large": "bangumi.jpg"},
            "summary": "简介",
        }

        result = dashboard.api_resolve_media_from_rank(_Plugin(), "tv", "Japanese Anime", "", bangumi_id=547888)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["title"], "中文动画")
        self.assertEqual(result["data"]["year"], "2026")
        self.assertEqual(result["data"]["bangumi_id"], 547888)
        self.assertEqual(result["data"]["mediaid_prefix"], "bangumi")
        self.assertEqual(result["data"]["poster_path"], "bangumi.jpg")

    def _active_asset_text(self, expose_name, suffix):
        remote_entry = PLUGIN_DIR / "dist" / "assets" / "remoteEntry.js"
        remote_text = remote_entry.read_text(encoding="utf-8")
        pattern = rf'dynamicLoadingCss\(\["([^"]+)"\], false, \'{expose_name}\'\);.*?__federation_import\(\'\.\/([^\']+{suffix})\'\)'
        match = re.search(pattern, remote_text, re.S)
        self.assertIsNotNone(match)
        return (remote_entry.parent / match.group(2)).read_text(encoding="utf-8")

    def _active_css_text(self, expose_name):
        remote_entry = PLUGIN_DIR / "dist" / "assets" / "remoteEntry.js"
        remote_text = remote_entry.read_text(encoding="utf-8")
        match = re.search(rf'dynamicLoadingCss\(\["([^"]+)"\], false, \'{expose_name}\'\)', remote_text)
        self.assertIsNotNone(match)
        return (remote_entry.parent / match.group(1)).read_text(encoding="utf-8")

    def test_active_config_rank_inputs_fit_five_digits(self):
        remote_entry = PLUGIN_DIR / "dist" / "assets" / "remoteEntry.js"
        remote_text = remote_entry.read_text(encoding="utf-8")
        match = re.search(r'dynamicLoadingCss\(\["([^"]+)"\], false, \'./Config\'\)', remote_text)
        self.assertIsNotNone(match)

        css = (remote_entry.parent / match.group(1)).read_text(encoding="utf-8")

        self.assertIn("grid-template-columns: 28px 110px", css)
        self.assertIn("width: 110px", css)
        self.assertIn("max-width: 118px", css)

    def test_active_frontend_uses_native_subscribe_with_silent_fallback(self):
        for expose_name in ("./Page", "./Dashboard"):
            js = self._active_asset_text(expose_name, ".js")
            self.assertIn("bangumi_id", js)
            self.assertIn("subscribe?", js)
            self.assertIn("resolve_media?", js)
            self.assertIn("nativeSubscribe", js)
            self.assertIn("subscribeViaNativeDialog", js)
            self.assertNotIn("MoviePilotNativeSubscribe", js)
            self.assertNotIn("MP native subscribe bridge is unavailable", js)
            self.assertNotIn("dc-subscribe-season-dialog", js)
            self.assertNotIn("addHostSubscribe", js)
            self.assertNotIn("dc-native", js)

    def test_active_config_hides_subscription_notify_switch(self):
        js = self._active_asset_text("./Config", ".js")

        self.assertNotIn("modelValue: form.notify", js)
        self.assertNotIn("(form.notify) =", js)
        self.assertIn("form.folio_notify", js)

    def test_active_rank_panel_keeps_poster_title_and_raw_monospace_wish_count(self):
        dashboard_js = self._active_asset_text("./Dashboard", ".js")
        page_js = self._active_asset_text("./Page", ".js")
        dashboard_css = self._active_css_text("./Dashboard")
        page_css = self._active_css_text("./Page")

        for js in (dashboard_js, page_js):
            self.assertIn("dc-rank-wish", js)
            self.assertNotIn("toLocaleString", js)
            self.assertIn('class: "dc-rank-row"', js)
            self.assertIn("_component_VAvatar", js)
            self.assertIn("_component_VImg", js)
            rank_row_start = js.find('class: "dc-rank-row"')
            rank_row_end = js.find('class: "dc-rank-empty"', rank_row_start)
            rank_row_block = js[rank_row_start:rank_row_end if rank_row_end != -1 else rank_row_start + 3000]
            self.assertNotIn("item.year", rank_row_block)
            self.assertNotIn("item.rank_name", rank_row_block)
            self.assertNotIn("dc-rank-meta", rank_row_block)

        compact_css = dashboard_css + "\n" + page_css
        self.assertIn("font-variant-numeric:tabular-nums", compact_css.replace(" ", ""))
        self.assertIn("dc-rank-poster", compact_css)

    def test_active_detail_rows_use_compact_log_style(self):
        page_js = self._active_asset_text("./Page", ".js")
        page_css = self._active_css_text("./Page").replace(" ", "")

        self.assertIn("cheatLogs.value = logs.filter(log => !log || !['黑名拦截', '黑名单关键词'].includes(log.reason)).slice(-5);", page_js)
        self.assertIn("blacklistEntries.value = logs.filter(log => log && ['黑名拦截', '黑名单关键词'].includes(log.reason)).slice().reverse().slice(0, 5);", page_js)
        self.assertNotIn('class: "dc-history-row dc-log-row"', page_js)
        self.assertIn('class: "dc-history-row dc-status-row"', page_js)
        self.assertIn('class: "dc-history-row dc-status-row dc-history-row--clickable"', page_js)
        self.assertIn('class: "dc-row-status"', page_js)
        log_block = re.search(
            r"_renderList\(cheatLogs\.value\.slice\(\)\.reverse\(\), \(log, i\) => \{[\s\S]*?rowKey\('log', log, i\)[\s\S]*?\]\)\)",
            page_js,
        )
        self.assertIsNotNone(log_block)
        log_block_text = log_block.group(0)
        self.assertIn('class: "dc-history-row dc-status-row"', log_block_text)
        self.assertNotIn('class: "dc-cheat-row', log_block_text)
        self.assertIn("(log.poster)", log_block_text)
        self.assertIn("src: log.poster", log_block_text)
        self.assertIn('icon: "mdi-filmstrip"', log_block_text)
        self.assertIn("rankChipStyle(log.rank_key)", log_block_text)
        self.assertIn('class: "dc-rank-chip mr-1"', log_block_text)
        self.assertNotIn("color: rankColors[log.rank_key] || 'primary'", log_block_text)
        self.assertIn("_toDisplayString(log.rank_name || log.rank_key || '观察日志')", log_block_text)
        self.assertIn('class: "dc-history-list"', page_js)
        self.assertRegex(
            page_js,
            r"_renderList\(cheatLogs\.value\.slice\(\)\.reverse\(\), \(log, i\)[\s\S]*?class: \"dc-history-row dc-status-row\"[\s\S]*?class: \"dc-row-status\"[\s\S]*?class: \"dc-row-action\"",
        )
        self.assertIn("dc-status-row", page_css)
        self.assertIn("grid-template-columns:autominmax(0,1fr)autoauto", page_css)
        self.assertIn(".dc-row-status", page_css)
        self.assertIn("grid-template-columns:autominmax(0,1fr)auto", page_css)
        self.assertNotIn("grid-template-columns:44pxminmax(0,1fr)34px", page_css)
        self.assertNotIn("border-radius:50%!important", page_css)

    def test_anti_cheat_logs_reconcile_finished_observations(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin.data["subscribe_records"] = [
            {"title": "done", "status": "success", "time": "2026-06-22 10:00:00"}
        ]
        plugin.data["rank_history_tv_real_time"] = [
            {
                "title": "done",
                "unique": "rank:done",
                "first_seen": "2026-06-20 10:00:00",
                "subscribed": True,
                "subscribed_at": "2026-06-22 10:00:00",
                "link": "https://example.com/done",
            }
        ]
        plugin.data["rank_history_tv_global"] = [
            {"title": "existing", "unique": "rank:1", "observing": True, "existing": True, "existing_reason": "subscribe"}
        ]
        plugin.data["anti_cheat_logs"] = [
            {"title": "done", "reason": "\u89c2\u5bdf\u671f\u672a\u6ee1", "detail": "d", "time": "2026-06-21 10:00:00"},
            {"title": "done", "reason": "\u89c2\u5bdf\u671f\u5b8c\u6210", "detail": "实时热门：2026-06-20 10:00:00 -> 2026-06-22 10:00:00", "time": "2026-06-22 10:00:00"},
            {"title": "existing", "reason": "\u89c2\u5bdf\u671f\u9996\u6b21\u8bb0\u5f55", "detail": "d", "time": "2026-06-21 11:00:00"},
            {"title": "keep", "reason": "\u89c2\u5bdf\u671f\u672a\u6ee1", "detail": "d", "time": "2026-06-21 12:00:00"},
            {"title": "keep", "reason": "\u89c2\u5bdf\u671f\u672a\u6ee1", "detail": "d", "time": "2026-06-21 12:00:00"},
        ]

        logs = dashboard.api_anti_cheat_logs(plugin)["data"]

        self.assertEqual([item["title"] for item in logs], ["done", "keep"])
        self.assertEqual(logs[0]["reason"], "观察完成")
        self.assertIn("2026-06-20 10:00:00", logs[0]["detail"])
        self.assertEqual(logs[1]["count"], 2)
        self.assertIsNone(plugin.data.get("archive_records"))
        self.assertEqual(plugin.data["anti_cheat_logs"], logs)

        dashboard.api_anti_cheat_logs(plugin)

        self.assertIsNone(plugin.data.get("archive_records"))

    def test_dashboard_rank_history_snapshots_read_builtin_rank_histories(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin.data["rank_history_tv_real_time"] = [{"title": "实时"}]
        plugin.data["rank_history_tv_global"] = [{"title": "全球"}]

        snapshots = dashboard._rank_history_snapshots(plugin)

        indexed = {rank["key"]: rank["history"] for rank in snapshots}
        self.assertEqual(indexed["tv_real_time"], [{"title": "实时"}])
        self.assertEqual(indexed["tv_global"], [{"title": "全球"}])

    def test_overview_reports_flow_order_and_archive_counts(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin._observe_days = 3
        plugin._rank_configs = {"tv_global": {"enabled": True}, "movie_weekly": {"enabled": True}}
        plugin.data["rank_history_tv_global"] = [
            {"title": "观察", "rank_refreshed_at": "2026-06-22 10:00:00", "observing": True}
        ]
        plugin.data["subscribe_records"] = [
            {"title": "订阅", "time": "2026-06-22 11:00:00", "rank_key": "tv_global", "media_type": "电视剧"}
        ]
        plugin.data["anti_cheat_logs"] = [
            {"title": "防刷", "reason": "黑名单关键词", "time": "2026-06-22 12:00:00"}
        ]
        plugin.data["archive_records"] = [
            {"id": "a1", "source": "subscribe_history", "title": "旧订阅"}
        ]
        plugin.data["folio_data"] = {"1": {"subject_name": "看过", "timestamp": "2026-06-22 09:00:00"}}

        result = dashboard.api_overview(plugin)

        self.assertEqual(result["code"], 0)
        self.assertEqual([item["label"] for item in result["flows"]], ["榜单订阅", "归档治理", "豆瓣时间"])
        self.assertEqual(result["cards"]["rss"]["enabled"], 2)
        self.assertEqual(result["cards"]["archive"]["total"], 1)
        self.assertEqual(result["attention"]["blacklist_hits"], 1)
        self.assertEqual(result["governance"]["archive_records"], 1)

    def test_detail_deletes_move_records_into_archive(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin.data["subscribe_records"] = [
            {"title": "订阅删除", "time": "2026-06-22 10:00:00", "tmdbid": 2}
        ]
        plugin.data["rank_history_tv_global"] = [
            {"title": "观察删除", "unique": "dc2_rank:a", "observing": True}
        ]
        plugin.data["anti_cheat_logs"] = [
            {"title": "防刷删除", "reason": "观察期未满", "time": "2026-06-22 11:00:00"}
        ]

        sub_result = dashboard.api_delete_subscribe_history(plugin, time="2026-06-22 10:00:00", title="订阅删除", tmdbid=2)
        obs_result = dashboard.api_delete_observation(plugin, unique="dc2_rank:a", rank_key="tv_global")
        log_result = dashboard.api_delete_anti_cheat_log(plugin, time="2026-06-22 11:00:00", title="防刷删除", reason="观察期未满")

        self.assertTrue(sub_result["success"])
        self.assertTrue(obs_result["success"])
        self.assertTrue(log_result["success"])
        archives = plugin.data["archive_records"]
        self.assertEqual([item["source"] for item in archives], ["subscribe_history", "observation", "anti_cheat_log"])
        self.assertEqual([item["title"] for item in archives], ["订阅删除", "观察删除", "防刷删除"])
        self.assertEqual(plugin.data["subscribe_records"], [])
        self.assertFalse(plugin.data["rank_history_tv_global"][0]["observing"])
        self.assertEqual(plugin.data["anti_cheat_logs"], [])

    def test_archive_record_can_restore_and_be_deleted(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin.data["subscribe_records"] = [
            {"title": "可恢复", "time": "2026-06-22 10:00:00", "tmdbid": 3}
        ]

        dashboard.api_delete_subscribe_history(plugin, time="2026-06-22 10:00:00", title="可恢复", tmdbid=3)
        archive_id = plugin.data["archive_records"][0]["id"]

        records = dashboard.api_archive_records(plugin)["data"]
        self.assertEqual(records["total"], 1)
        self.assertEqual(records["items"][0]["id"], archive_id)

        restored = dashboard.api_restore_archive(plugin, archive_id=archive_id)
        self.assertTrue(restored["success"])
        self.assertEqual(plugin.data["subscribe_records"][0]["title"], "可恢复")
        self.assertEqual(plugin.data["archive_records"], [])

        dashboard.api_delete_subscribe_history(plugin, time="2026-06-22 10:00:00", title="可恢复", tmdbid=3)
        archive_id = plugin.data["archive_records"][0]["id"]
        deleted = dashboard.api_delete_archive(plugin, archive_id=archive_id)

        self.assertTrue(deleted["success"])
        self.assertEqual(plugin.data["archive_records"], [])

    def test_legacy_observation_completion_archives_return_to_logs(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin.data["archive_records"] = [
            {
                "id": "legacy",
                "source": "observation_completed",
                "source_name": "观察完成",
                "title": "旧完成",
                "time": "2026-06-22 10:00:00",
                "reason": "观察完成",
                "archived_at": "2026-06-28 10:00:00",
                "record": {"title": "旧完成", "time": "2026-06-22 10:00:00", "reason": "观察期完成", "detail": "已过 2 天，达到 2 天"},
            }
        ]

        logs = dashboard.api_anti_cheat_logs(plugin)["data"]
        archives = dashboard.api_archive_records(plugin)["data"]

        self.assertEqual([item["title"] for item in logs], ["旧完成"])
        self.assertEqual(logs[0]["reason"], "观察完成")
        self.assertEqual(archives["total"], 0)
        self.assertEqual(plugin.data["archive_records"], [])

    def test_detail_sections_archive_overflow_records(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin._observe_days = 3
        plugin.data["subscribe_records"] = [
            {"title": f"订阅{i}", "time": f"2026-06-22 10:00:0{i}", "tmdbid": i}
            for i in range(7)
        ]
        plugin.data["anti_cheat_logs"] = [
            {"title": f"黑名{i}", "reason": "黑名单关键词", "detail": "命中", "time": f"2026-06-22 11:00:0{i}"}
            for i in range(7)
        ] + [
            {"title": f"日志{i}", "reason": "观察期未满", "detail": "等待", "time": f"2026-06-22 12:00:0{i}"}
            for i in range(7)
        ]
        plugin.data["rank_history_tv_global"] = [
            {
                "title": f"观察{i}",
                "unique": f"rank:{i}",
                "first_seen": f"2026-06-22 13:00:0{i}",
                "observing": True,
            }
            for i in range(7)
        ]

        history = dashboard.api_subscribe_history(plugin)["data"]
        logs = dashboard.api_anti_cheat_logs(plugin)["data"]
        pending = dashboard.api_pending_observations(plugin)["data"]

        self.assertEqual(history["total"], 5)
        self.assertEqual([item["title"] for item in history["items"]], ["订阅6", "订阅5", "订阅4", "订阅3", "订阅2"])
        self.assertEqual(len(logs), 10)
        self.assertEqual(len([item for item in logs if item["reason"] == "黑名拦截"]), 5)
        self.assertEqual(len([item for item in logs if item["reason"] != "黑名拦截"]), 5)
        self.assertEqual([item["title"] for item in pending], ["观察6", "观察5", "观察4", "观察3", "观察2"])
        self.assertFalse(plugin.data["rank_history_tv_global"][0]["observing"])
        self.assertTrue(plugin.data["rank_history_tv_global"][0]["observe_deleted"])
        sources = [(item["source"], item["source_name"], item["title"]) for item in plugin.data["archive_records"]]
        self.assertIn(("subscribe_history", "订阅历史", "订阅1"), sources)
        self.assertIn(("subscribe_history", "订阅历史", "订阅0"), sources)
        self.assertIn(("anti_cheat_log", "黑名拦截", "黑名1"), sources)
        self.assertIn(("anti_cheat_log", "黑名拦截", "黑名0"), sources)
        self.assertIn(("anti_cheat_log", "观察日志", "日志1"), sources)
        self.assertIn(("anti_cheat_log", "观察日志", "日志0"), sources)
        self.assertIn(("observation", "观察队列", "观察1"), sources)
        self.assertIn(("observation", "观察队列", "观察0"), sources)

    def test_auto_subscription_uses_mp_default_message_instead_of_plugin_notify(self):
        plugin = _Plugin()
        plugin._notify = True
        captured = {}

        class SubscribeChain:
            def add(self, **kwargs):
                captured.update(kwargs)
                return 1, ""

        self.feed.SubscribeChain = SubscribeChain

        result = self.feed._add_sub(plugin, _MediaInfo(title="通知电影", mtype=_MediaType.MOVIE), rank_key="movie_weekly", rank_name="电影口碑")

        self.assertTrue(result)
        self.assertEqual(plugin.messages, [])
        self.assertNotEqual(captured.get("message"), False)

    def test_auto_subscription_uses_default_tmdb_without_season(self):
        plugin = _Plugin()
        captured = {}
        meta = _MetaInfo("葬送的芙莉莲 第二季")
        meta.type = _MediaType.TV
        meta.begin_season = 2

        class SubscribeChain:
            def add(self, **kwargs):
                captured.update(kwargs)
                return 1, ""

        self.feed.SubscribeChain = SubscribeChain

        result = self.feed._add_sub(plugin, _MediaInfo(title="葬送的芙莉莲", mtype=_MediaType.TV), meta=meta, rank_key="tv_global", rank_name="全球口碑")

        self.assertTrue(result)
        self.assertIsNone(captured["season"])

    def test_auto_subscription_ignores_legacy_resolution_filters(self):
        plugin = _Plugin()
        plugin._resolution_filters = ["2160p"]
        captured = {}
        self.feed.utils.build_resolution_rule = lambda filters: "2160p"

        class SubscribeChain:
            def add(self, **kwargs):
                captured.update(kwargs)
                return 1, ""

        self.feed.SubscribeChain = SubscribeChain

        result = self.feed._add_sub(plugin, _MediaInfo(title="默认订阅", mtype=_MediaType.MOVIE))

        self.assertTrue(result)
        self.assertIsNone(captured["resolution"])

    def test_auto_subscription_failure_writes_failed_history(self):
        plugin = _Plugin()

        class SubscribeChain:
            def add(self, **kwargs):
                return None, "MP 返回失败"

        self.feed.SubscribeChain = SubscribeChain

        result = self.feed._add_sub(plugin, _MediaInfo(title="失败电影", mtype=_MediaType.MOVIE), rank_key="movie_weekly", rank_name="电影口碑", source_link="https://rsshub.example/fail")

        self.assertFalse(result)
        self.assertEqual(plugin.data["subscribe_records"][0]["status"], "failed")
        self.assertEqual(plugin.data["subscribe_records"][0]["reason"], "MP 返回失败")
        self.assertEqual(plugin.data["subscribe_records"][0]["link"], "https://rsshub.example/fail")

    def test_dashboard_subscription_uses_mp_default_message_instead_of_plugin_notify(self):
        dashboard = _import_dashboard()
        plugin = _Plugin()
        plugin._notify = True
        captured = {}

        class MediaChain:
            def recognize_media(self, meta, mtype):
                return _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=24680)

        class DownloadChain:
            def get_no_exists_info(self, meta, mediainfo):
                raise AssertionError("不应在订阅前读取媒体库存在状态")

        class SubscribeChain:
            def exists(self, mediainfo, meta):
                return False

            def add(self, **kwargs):
                captured.update(kwargs)
                return 1, ""

        sys.modules["app.chain.media"].MediaChain = MediaChain
        sys.modules["app.chain.download"].DownloadChain = DownloadChain
        sys.modules["app.chain.subscribe"].SubscribeChain = SubscribeChain

        result = dashboard.api_subscribe_from_rank(plugin, None, "movie", "通知电影", "2026")

        self.assertTrue(result["success"])
        self.assertEqual(plugin.messages, [])
        self.assertNotEqual(captured.get("message"), False)

    def test_observation_service_records_first_seen(self):
        service = _import_service("observation")
        plugin = _Plugin()
        history = []

        should_skip = service.check_observe(plugin, "rank:1", history, title="测试电影", rank_key="coming")

        self.assertTrue(should_skip)
        self.assertEqual(history[0]["unique"], "rank:1")
        self.assertEqual(history[0]["title"], "测试电影")
        self.assertTrue(history[0]["observing"])
        self.assertEqual(plugin.data["anti_cheat_logs"][0]["reason"], "开始观察")

    def test_subscription_service_deduplicates_records(self):
        service = _import_service("subscription")
        plugin = _Plugin()
        mediainfo = _MediaInfo(title="测试电影", year="2026", tmdb_id=12345)

        service.write_subscribe_record(plugin, mediainfo, rank_key="coming", rank_name="即将上映")
        service.write_subscribe_record(plugin, mediainfo, rank_key="coming", rank_name="即将上映")

        records = plugin.data["subscribe_records"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "测试电影")
        self.assertTrue(service.history_item_subscribed({"subscribed": True}))

    def test_archive_service_deduplicates_more_complete_record(self):
        service = _import_service("archive")
        plugin = _Plugin()

        first = service.archive_record(plugin, "subscribe_history", {"title": "测试电影"}, "订阅历史", dedupe=True)
        second = service.archive_record(
            plugin,
            "subscribe_history",
            {"title": "测试电影", "tmdbid": 12345, "poster": "poster.jpg"},
            "订阅历史",
            dedupe=True,
        )

        archives = plugin.data["archive_records"]
        self.assertEqual(len(archives), 1)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(archives[0]["record"]["tmdbid"], 12345)


if __name__ == "__main__":
    unittest.main()
