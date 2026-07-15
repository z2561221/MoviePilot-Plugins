import importlib.util
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _PluginBase:
    """用于隔离入口初始化测试的宿主插件基类。"""

    def __init__(self, *args, **kwargs):
        """初始化测试用配置记录。"""
        self.saved_config = None

    def update_config(self, config):
        """记录插件写回配置。"""
        self.saved_config = dict(config)


class _EventManager:
    """提供 MoviePilot 事件注册装饰器占位。"""

    def register(self, *args, **kwargs):
        """返回原函数，避免真实注册事件。"""
        return lambda func: func


def _install_app_stubs():
    """安装入口模块依赖的宿主 app 占位模块。"""
    app = types.ModuleType("app")
    app.__path__ = []
    core = types.ModuleType("app.core")
    core.__path__ = []
    event = types.ModuleType("app.core.event")
    event.eventmanager = _EventManager()
    event.Event = object
    plugins = types.ModuleType("app.plugins")
    plugins._PluginBase = _PluginBase
    schemas = types.ModuleType("app.schemas")
    schemas.__path__ = []
    schema_types = types.ModuleType("app.schemas.types")
    schema_types.EventType = types.SimpleNamespace(WebhookMessage="WebhookMessage")
    sys.modules.update({
        "app": app,
        "app.core": core,
        "app.core.event": event,
        "app.plugins": plugins,
        "app.schemas": schemas,
        "app.schemas.types": schema_types,
    })


def _install_plugin_stubs(package_name):
    """安装入口模块依赖的插件内部占位模块。"""
    calls = {"wish": [], "rank": []}

    dashboard = types.ModuleType(f"{package_name}.dashboard")
    dashboard.get_dashboard = lambda *args, **kwargs: None

    feed = types.ModuleType(f"{package_name}.feed")
    feed.default_observe_rank_keys = lambda: []
    feed.run_once = lambda plugin: calls["rank"].append(plugin)
    feed.run_scheduled = lambda plugin: None

    folio = types.ModuleType(f"{package_name}.folio")
    folio.run_wish_scheduled = lambda plugin: calls["wish"].append(plugin)

    migration = types.ModuleType(f"{package_name}.migration")
    migration.normalize_legacy_subscribe_usernames = lambda: None

    utils = types.ModuleType(f"{package_name}.utils")
    utils.normalize_rss_domain = lambda value: value

    controller = types.ModuleType(f"{package_name}.controller")
    controller.__path__ = []
    controller_api = types.ModuleType(f"{package_name}.controller.api")
    for name in (
        "get_api",
        "api_folio_data",
        "api_overview",
        "api_config",
        "api_rank_history",
        "api_refresh_rss",
        "api_stats",
    ):
        setattr(controller_api, name, lambda *args, **kwargs: None)
    controller_api.api_resolve_media = lambda *args, **kwargs: None
    controller_api.api_subscribe = lambda *args, **kwargs: None
    controller_api.api_subscribe_history = lambda *args, **kwargs: None
    controller_api.api_pending_observations = lambda *args, **kwargs: None
    controller_api.api_anti_cheat_logs = lambda *args, **kwargs: None
    controller_api.api_delete_subscribe_history = lambda *args, **kwargs: None
    controller_api.api_delete_observation = lambda *args, **kwargs: None
    controller_api.api_delete_anti_cheat_log = lambda *args, **kwargs: None
    controller_api.api_archive_records = lambda *args, **kwargs: None
    controller_api.api_restore_archive = lambda *args, **kwargs: None
    controller_api.api_delete_archive = lambda *args, **kwargs: None

    service = types.ModuleType(f"{package_name}.service")
    service.__path__ = []
    scheduler = types.ModuleType(f"{package_name}.service.scheduler")
    scheduler.get_services = lambda *args, **kwargs: []
    scheduler.stop_scheduler = lambda plugin: None
    webhook = types.ModuleType(f"{package_name}.service.webhook")
    webhook.handle_sync_log = lambda *args, **kwargs: None
    webhook.handle_sync_played = lambda *args, **kwargs: None

    sys.modules.update({
        f"{package_name}.dashboard": dashboard,
        f"{package_name}.feed": feed,
        f"{package_name}.folio": folio,
        f"{package_name}.migration": migration,
        f"{package_name}.utils": utils,
        f"{package_name}.controller": controller,
        f"{package_name}.controller.api": controller_api,
        f"{package_name}.service": service,
        f"{package_name}.service.scheduler": scheduler,
        f"{package_name}.service.webhook": webhook,
    })
    return calls


def _load_plugin_entry():
    """加载隔离包名下的 DoubanCenter 入口模块。"""
    package_name = "doubancenter_init_test"
    for name in list(sys.modules):
        if name == package_name or name.startswith(f"{package_name}."):
            sys.modules.pop(name, None)
    _install_app_stubs()
    calls = _install_plugin_stubs(package_name)
    spec = importlib.util.spec_from_file_location(
        package_name,
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module, calls


class DoubanCenterWishOnlyOnceTest(unittest.TestCase):
    def test_init_plugin_persists_missing_wish_once_default(self):
        """旧配置缺少想看立即运行字段时会补齐默认值。"""
        module, _calls = _load_plugin_entry()
        plugin = module.DoubanCenter()

        plugin.init_plugin({"enabled": True})

        self.assertFalse(plugin.saved_config["wish_onlyonce"])
        self.assertFalse(plugin.saved_config["discovery_page_enabled"])

    def test_init_plugin_runs_wish_once_and_resets_flag(self):
        """想看立即运行开关会触发一次同步并写回关闭。"""
        module, calls = _load_plugin_entry()
        plugin = module.DoubanCenter()

        plugin.init_plugin({"wish_onlyonce": True, "wish_user": "tester"})

        self.assertEqual(calls["wish"], [plugin])
        self.assertEqual(calls["rank"], [])
        self.assertFalse(plugin.saved_config["wish_onlyonce"])

    def test_discovery_page_nav_respects_plugin_state_and_switch(self):
        """发现页入口应同时受插件启用状态与独立开关控制。"""
        module, _calls = _load_plugin_entry()
        plugin = module.DoubanCenter()

        plugin.init_plugin({"enabled": False, "discovery_page_enabled": True})
        self.assertEqual(plugin.get_sidebar_nav(), [])

        plugin.init_plugin({"enabled": True, "discovery_page_enabled": False})
        self.assertEqual(plugin.get_sidebar_nav(), [])

        plugin.init_plugin({"enabled": True, "discovery_page_enabled": True})
        self.assertEqual(
            plugin.get_sidebar_nav(),
            [
                {
                    "nav_key": "main",
                    "title": "豆瓣中心",
                    "icon": "mdi-book-open-page-variant-outline",
                    "section": "discovery",
                    "permission": "discovery",
                    "order": 20,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
