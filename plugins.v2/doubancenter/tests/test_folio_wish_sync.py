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

    def get_wish_items(self, user_id="", max_pages=1, request_get=None):
        """返回预置的想看条目并记录调用参数。"""
        self.calls.append({"user_id": user_id, "max_pages": max_pages})
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

    def test_default_scan_requests_single_page_with_user(self):
        """默认扫描只请求一页，并带上配置的想看用户。"""
        plugin = _MemoryPlugin()
        plugin._wish_user = "tester"
        api = _FakeApi([_item("1", "甲")])

        folio.run_wish_sync(plugin, api=api)

        self.assertEqual(len(api.calls), 1)
        self.assertEqual(api.calls[0]["max_pages"], 1)
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


if __name__ == "__main__":
    unittest.main()
