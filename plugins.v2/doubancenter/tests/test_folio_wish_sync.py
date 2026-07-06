import importlib.util
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _MemoryPlugin:
    """用于豆瓣想看同步测试的内存插件存储。"""

    def __init__(self, data=None):
        """初始化内存存储与想看配置。"""
        self.data = data or {}
        self._wish_user = ""
        self._wish_max_pages = 1
        self._wish_days = 7
        self._wish_notify = False

    def get_data(self, key, **kwargs):
        """读取指定存储键。"""
        return self.data.get(key)

    def save_data(self, key, value):
        """保存指定存储键。"""
        self.data[key] = value


class _FakeApi:
    """用于注入的假豆瓣想看接口。"""

    def __init__(self, items):
        """记录返回条目与调用参数。"""
        self._items = items
        self.calls = []

    def get_wish_items(self, user_id="", max_pages=1, days=7, request_get=None):
        """返回预置的想看条目并记录调用参数。"""
        self.calls.append({"user_id": user_id, "max_pages": max_pages, "days": days})
        return list(self._items)


def _install_stubs():
    """安装 folio 依赖所需的宿主包占位。"""
    app = types.ModuleType("app")
    app.__path__ = []
    chain = types.ModuleType("app.chain")
    chain.__path__ = []
    media = types.ModuleType("app.chain.media")
    media.MediaChain = type("MediaChain", (), {})
    core = types.ModuleType("app.core")
    core.__path__ = []
    metainfo = types.ModuleType("app.core.metainfo")
    metainfo.MetaInfo = type("MetaInfo", (), {})
    meta = types.ModuleType("app.core.meta")
    meta.MetaBase = object
    log = types.ModuleType("app.log")
    log.logger = types.SimpleNamespace(
        info=lambda *a, **k: None,
        warn=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    schemas = types.ModuleType("app.schemas")
    schemas.__path__ = []
    schema_types = types.ModuleType("app.schemas.types")
    schema_types.MediaType = type("MediaType", (), {})
    schema_types.NotificationType = types.SimpleNamespace(MediaServer="MediaServer")
    config = types.ModuleType("app.core.config")
    config.settings = types.SimpleNamespace(USER_AGENT="test-agent")
    helper = types.ModuleType("app.helper")
    helper.__path__ = []
    cookiecloud = types.ModuleType("app.helper.cookiecloud")
    cookiecloud.CookieCloudHelper = object
    utils_pkg = types.ModuleType("app.utils")
    utils_pkg.__path__ = []
    http = types.ModuleType("app.utils.http")
    http.RequestUtils = type("RequestUtils", (), {})
    requests_module = types.ModuleType("requests")
    requests_module.get = lambda *a, **k: None
    requests_module.post = lambda *a, **k: None
    bs4_module = types.ModuleType("bs4")
    bs4_module.BeautifulSoup = object
    pytz_module = types.ModuleType("pytz")
    pytz_module.timezone = lambda *a, **k: None
    package = types.ModuleType("doubancenter")
    package.__path__ = [str(PLUGIN_DIR)]
    storage_pkg = types.ModuleType("doubancenter.storage")
    storage_pkg.__path__ = [str(PLUGIN_DIR / "storage")]
    sys.modules.update({
        "app": app,
        "app.chain": chain,
        "app.chain.media": media,
        "app.core": core,
        "app.core.config": config,
        "app.core.metainfo": metainfo,
        "app.core.meta": meta,
        "app.log": log,
        "app.schemas": schemas,
        "app.schemas.types": schema_types,
        "app.helper": helper,
        "app.helper.cookiecloud": cookiecloud,
        "app.utils": utils_pkg,
        "app.utils.http": http,
        "requests": requests_module,
        "bs4": bs4_module,
        "pytz": pytz_module,
        "doubancenter": package,
        "doubancenter.storage": storage_pkg,
    })


def _load_folio():
    """加载 folio 模块。"""
    _install_stubs()
    for name in ("doubancenter.utils", "doubancenter.doubanapi",
                 "doubancenter.storage.records", "doubancenter.folio"):
        sys.modules.pop(name, None)
    for name, rel in (
        ("doubancenter.utils", "utils.py"),
        ("doubancenter.doubanapi", "doubanapi.py"),
        ("doubancenter.storage.records", "storage/records.py"),
        ("doubancenter.folio", "folio.py"),
    ):
        spec = importlib.util.spec_from_file_location(name, PLUGIN_DIR / rel)
        module = importlib.util.module_from_spec(spec)
        module.__package__ = name.rsplit(".", 1)[0]
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["doubancenter.folio"]


folio = _load_folio()


def _item(subject_id, title):
    """构造一个想看条目。"""
    return {"subject_id": subject_id, "title": title, "year": "2026",
            "link": f"https://movie.douban.com/subject/{subject_id}/",
            "poster": "", "wish_time": ""}


class FolioWishSyncTest(unittest.TestCase):
    def test_first_run_builds_baseline_without_queue(self):
        """首次运行只建立基线，不把历史想看入队。"""
        plugin = _MemoryPlugin()
        api = _FakeApi([_item("1", "甲"), _item("2", "乙")])

        folio.run_wish_sync(plugin, api=api)

        state = plugin.data.get("folio_wish_state") or {}
        seen = plugin.data.get("folio_wish_seen") or []
        queue = plugin.data.get("folio_wish_queue") or []
        self.assertTrue(state.get("initialized"))
        self.assertEqual({r["subject_id"] for r in seen}, {"1", "2"})
        self.assertEqual(queue, [])

    def test_later_run_enqueues_only_new_items(self):
        """基线建立后，只有新增想看条目才会入队。"""
        plugin = _MemoryPlugin()
        api = _FakeApi([_item("1", "甲")])
        folio.run_wish_sync(plugin, api=api)

        api2 = _FakeApi([_item("2", "乙"), _item("1", "甲")])
        folio.run_wish_sync(plugin, api=api2)

        queue = plugin.data.get("folio_wish_queue") or []
        seen_ids = {r["subject_id"] for r in (plugin.data.get("folio_wish_seen") or [])}
        self.assertEqual([r["subject_id"] for r in queue], ["2"])
        self.assertEqual(seen_ids, {"1", "2"})

    def test_default_sync_passes_user_and_recent_days(self):
        """默认同步带上配置的想看用户和最近天数。"""
        plugin = _MemoryPlugin()
        plugin._wish_user = "tester"
        plugin._wish_days = 3
        api = _FakeApi([_item("1", "甲")])

        folio.run_wish_sync(plugin, api=api)

        self.assertEqual(len(api.calls), 1)
        self.assertEqual(api.calls[0]["days"], 3)
        self.assertEqual(api.calls[0]["user_id"], "tester")

    def test_scheduled_entry_invokes_sync(self):
        """定时入口会真正触发想看同步逻辑。"""
        plugin = _MemoryPlugin()
        calls = []
        original = folio.run_wish_sync
        folio.run_wish_sync = lambda self, **kwargs: calls.append(self)
        try:
            folio.run_wish_scheduled(plugin)
        finally:
            folio.run_wish_sync = original
        self.assertEqual(calls, [plugin])


class FolioWishQueueProcessTest(unittest.TestCase):
    def _plugin_with_queue(self):
        plugin = _MemoryPlugin()
        plugin.data["folio_wish_state"] = {"initialized": True}
        plugin.data["folio_wish_queue"] = [
            {"subject_id": "1", "title": "\u7532", "year": "2026", "link": "https://movie.douban.com/subject/1/"},
            {"subject_id": "2", "title": "\u4e59", "year": "2025", "link": "https://movie.douban.com/subject/2/"},
        ]
        return plugin

    def test_process_queue_subscribes_and_writes_rank_key(self):
        """\u5904\u7406\u961f\u5217\u4f1a\u521b\u5efa\u8ba2\u9605\u5e76\u5199\u5165 rank_key=douban_wish\u3002"""
        plugin = self._plugin_with_queue()
        calls = []

        def fake_recognize(title, year):
            return types.SimpleNamespace(title=title, year=year, tmdb_id=int(year))

        def fake_subscribe(self, mediainfo, meta=None, rank_key="", rank_name="", source_link=""):
            calls.append((mediainfo.title, rank_key, rank_name, source_link))
            return True

        folio.process_wish_queue(plugin, recognize=fake_recognize, subscribe=fake_subscribe)

        self.assertEqual([c[0] for c in calls], ["\u7532", "\u4e59"])
        self.assertTrue(all(c[1] == "douban_wish" for c in calls))
        self.assertTrue(all(c[2] == "\u8c46\u74e3\u60f3\u770b" for c in calls))
        self.assertEqual(plugin.data.get("folio_wish_queue"), [])
        processed = plugin.data.get("folio_wish_processed") or []
        self.assertEqual({r["subject_id"] for r in processed}, {"1", "2"})

    def test_process_queue_records_failed_recognition_without_crash(self):
        """\u8bc6\u522b\u5931\u8d25\u7684\u6761\u76ee\u4f1a\u88ab\u8bb0\u5f55\u4e14\u4e0d\u5d29\u6e83\u8c03\u5ea6\u3002"""
        plugin = self._plugin_with_queue()

        def fake_recognize(title, year):
            if title == "\u7532":
                return None
            return types.SimpleNamespace(title=title, year=year, tmdb_id=int(year))

        subscribed = []

        def fake_subscribe(self, mediainfo, meta=None, rank_key="", rank_name="", source_link=""):
            subscribed.append(mediainfo.title)
            return True

        folio.process_wish_queue(plugin, recognize=fake_recognize, subscribe=fake_subscribe)

        failed = plugin.data.get("folio_wish_failed") or []
        self.assertEqual({r["subject_id"] for r in failed}, {"1"})
        self.assertEqual(subscribed, ["\u4e59"])
        self.assertEqual(plugin.data.get("folio_wish_queue"), [])

    def test_process_queue_marks_existing_without_infinite_retry(self):
        """\u5df2\u5b58\u5728\u8ba2\u9605\u7684\u6761\u76ee\u4e0d\u4f1a\u65e0\u9650\u91cd\u8bd5\u3002"""
        plugin = self._plugin_with_queue()

        def fake_recognize(title, year):
            return types.SimpleNamespace(title=title, year=year, tmdb_id=int(year))

        def fake_subscribe(self, mediainfo, meta=None, rank_key="", rank_name="", source_link=""):
            return False

        folio.process_wish_queue(plugin, recognize=fake_recognize, subscribe=fake_subscribe)

        self.assertEqual(plugin.data.get("folio_wish_queue"), [])
        processed_ids = {r["subject_id"] for r in (plugin.data.get("folio_wish_processed") or [])}
        self.assertEqual(processed_ids, {"1", "2"})


class FolioWishErrorStateTest(unittest.TestCase):
    def test_cookie_invalid_preserves_queue_and_writes_state_error(self):
        """cookie \u5931\u6548\u65f6\u4fdd\u7559\u961f\u5217\u4e0e\u5df2\u89c1\uff0c\u5e76\u5199\u5165\u72b6\u6001\u9519\u8bef\u3002"""
        plugin = _MemoryPlugin()
        plugin.data["folio_wish_state"] = {"initialized": True}
        plugin.data["folio_wish_seen"] = [{"subject_id": "1", "title": "\u7532"}]
        plugin.data["folio_wish_queue"] = [{"subject_id": "9", "title": "\u65e7"}]

        class _CookieApi:
            def get_wish_items(self, user_id="", max_pages=1, days=7, request_get=None):
                raise RuntimeError("cookie invalid")

        folio.run_wish_sync(plugin, api=_CookieApi())

        state = plugin.data.get("folio_wish_state") or {}
        self.assertTrue(state.get("last_error"))
        self.assertIn("读取想看失败", state.get("last_error"))
        self.assertIn("cookie invalid", state.get("last_error"))
        self.assertEqual(plugin.data.get("folio_wish_queue"), [{"subject_id": "9", "title": "\u65e7"}])
        self.assertEqual(plugin.data.get("folio_wish_seen"), [{"subject_id": "1", "title": "\u7532"}])

    def test_subscription_failure_records_wish_failed_state(self):
        """\u8ba2\u9605\u5931\u8d25\u65f6\u5199\u5165\u60f3\u770b\u5931\u8d25\u72b6\u6001\u4e14\u4e0d\u91cd\u590d\u91cd\u8bd5\u3002"""
        plugin = _MemoryPlugin()
        plugin.data["folio_wish_state"] = {"initialized": True}
        plugin.data["folio_wish_queue"] = [
            {"subject_id": "1", "title": "\u7532", "year": "2026", "link": "https://movie.douban.com/subject/1/"},
        ]

        def fake_recognize(title, year):
            return types.SimpleNamespace(title=title, year=year, tmdb_id=int(year))

        def fake_subscribe(self, mediainfo, meta=None, rank_key="", rank_name="", source_link=""):
            return {"status": "failed", "reason": "subscribe_failed"}

        folio.process_wish_queue(plugin, recognize=fake_recognize, subscribe=fake_subscribe)

        failed = plugin.data.get("folio_wish_failed") or []
        self.assertEqual({r["subject_id"] for r in failed}, {"1"})
        self.assertTrue(all(r.get("reason") == "subscribe_failed" for r in failed))
        self.assertEqual(plugin.data.get("folio_wish_queue"), [])
        state = plugin.data.get("folio_wish_state") or {}
        self.assertEqual(state.get("last_failed"), 1)


if __name__ == "__main__":
    unittest.main()
