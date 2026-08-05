import importlib.util
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _load_module(name, path):
    """按独立模块名加载目标测试模块。"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_rank_model():
    """加载不依赖 MoviePilot 宿主的榜单模型。"""
    return _load_module("doubancenter_custom_rank_model", PLUGIN_DIR / "model" / "rank.py")


def _load_rss_adapter():
    """安装最小宿主桩并加载 RSS 适配器。"""
    app = types.ModuleType("custom_rank_app")
    app.__path__ = []
    core = types.ModuleType("custom_rank_app.core")
    core.__path__ = []
    config = types.ModuleType("custom_rank_app.core.config")
    config.settings = types.SimpleNamespace(PROXY=None)
    log = types.ModuleType("custom_rank_app.log")
    log.logger = types.SimpleNamespace(error=lambda *args, **kwargs: None)
    utils_package = types.ModuleType("custom_rank_app.utils")
    utils_package.__path__ = []
    dom = types.ModuleType("custom_rank_app.utils.dom")
    dom.DomUtils = object
    http = types.ModuleType("custom_rank_app.utils.http")
    http.RequestUtils = object
    package = types.ModuleType("doubancenter_custom")
    package.__path__ = [str(PLUGIN_DIR)]
    local_utils = types.ModuleType("doubancenter_custom.utils")
    local_utils.normalize_rss_domain = lambda value: str(value or "").rstrip("/")
    sys.modules.update({
        "custom_rank_app": app,
        "custom_rank_app.core": core,
        "custom_rank_app.core.config": config,
        "custom_rank_app.log": log,
        "custom_rank_app.utils": utils_package,
        "custom_rank_app.utils.dom": dom,
        "custom_rank_app.utils.http": http,
        "doubancenter_custom": package,
        "doubancenter_custom.utils": local_utils,
    })

    # 适配器使用固定的 app 包名，替换为与真实导入路径相同的最小桩。
    sys.modules["app"] = types.ModuleType("app")
    sys.modules["app"].__path__ = []
    sys.modules["app.core"] = types.ModuleType("app.core")
    sys.modules["app.core"].__path__ = []
    app_config = types.ModuleType("app.core.config")
    app_config.settings = types.SimpleNamespace(PROXY=None)
    sys.modules["app.core.config"] = app_config
    app_log = types.ModuleType("app.log")
    app_log.logger = types.SimpleNamespace(error=lambda *args, **kwargs: None)
    sys.modules["app.log"] = app_log
    sys.modules["app.utils"] = types.ModuleType("app.utils")
    sys.modules["app.utils"].__path__ = []
    app_dom = types.ModuleType("app.utils.dom")
    app_dom.DomUtils = object
    sys.modules["app.utils.dom"] = app_dom
    app_http = types.ModuleType("app.utils.http")
    app_http.RequestUtils = object
    sys.modules["app.utils.http"] = app_http
    real_package = types.ModuleType("doubancenter")
    real_package.__path__ = [str(PLUGIN_DIR)]
    adapter_package = types.ModuleType("doubancenter.adapter")
    adapter_package.__path__ = [str(PLUGIN_DIR / "adapter")]
    real_utils = types.ModuleType("doubancenter.utils")
    real_utils.normalize_rss_domain = lambda value: str(value or "").rstrip("/")
    sys.modules["doubancenter"] = real_package
    sys.modules["doubancenter.adapter"] = adapter_package
    sys.modules["doubancenter.utils"] = real_utils
    return _load_module("doubancenter.adapter.rss_custom_test", PLUGIN_DIR / "adapter" / "rss.py")


rank = _load_rank_model()
rss = _load_rss_adapter()


class CustomRanksModelTest(unittest.TestCase):
    """验证自定义榜单模型边界。"""

    def test_normalize_custom_ranks_rejects_invalid_and_duplicate_entries(self):
        result = rank.normalize_custom_ranks([
            {"key": "custom_highscore", "name": "高分动画", "route": "/anime/rss?tag=top", "media_type": "movie"},
            {"key": "custom_highscore", "name": "重复", "route": "/duplicate"},
            {"key": "tv_global", "name": "覆盖内置", "route": "/tv"},
            {"key": "custom_absolute", "name": "绝对地址", "route": "https://example.test/rss"},
            {"key": "custom_fragment", "name": "带片段", "route": "/rss#top"},
            {"key": "custom_media", "name": "错误类型", "route": "/rss", "media_type": "comic"},
        ])

        self.assertEqual(result, [{
            "key": "custom_highscore",
            "name": "高分动画",
            "route": "/anime/rss?tag=top",
            "media_type": "movie",
        }])

    def test_effective_ranks_adds_custom_definition_without_mutating_builtins(self):
        custom = {"key": "custom_tv", "name": "自定义剧集", "route": "/custom/feed", "media_type": "tv"}
        ranks = rank.effective_ranks([custom])

        self.assertEqual(len(ranks), 7)
        self.assertEqual(ranks[-1]["key"], "custom_tv")
        self.assertFalse(ranks[-1]["coming"])
        self.assertEqual(ranks[-1]["filters"], ["vote", "year"])
        self.assertEqual(rank.BUILTIN_RANKS[-1]["key"], "bangumi")

    def test_media_type_priority_is_item_then_config_then_route(self):
        rank_def = {"key": "custom_movie", "route": "/tv/feed", "media_type": "movie"}

        self.assertEqual(rank.infer_media_type(rank_def, {"mtype": "tv"}), "tv")
        self.assertEqual(rank.infer_media_type(rank_def, {"mtype": "", "media_type": ""}), "movie")
        self.assertEqual(rank.infer_media_type({"key": "custom_auto", "route": "/movie/feed", "media_type": "auto"}, {}), "movie")


class RssHubUrlTest(unittest.TestCase):
    """验证 RSSHub 路由 URL 构造。"""

    def test_build_url_overrides_existing_limit_and_preserves_other_query(self):
        result = rss.build_rsshub_url(
            "https://rsshub.example/",
            "/anime/feed?tag=top&limit=1&empty=",
            5,
        )

        self.assertEqual(result, "https://rsshub.example/anime/feed?tag=top&empty=&limit=5")

    def test_build_url_rejects_absolute_host_and_fragment_routes(self):
        for route in ("anime/feed", "//evil.example/feed", "https://evil.example/feed", "/feed#frag"):
            with self.subTest(route=route):
                with self.assertRaises(ValueError):
                    rss.build_rsshub_url("https://rsshub.example", route, 5)


if __name__ == "__main__":
    unittest.main()
