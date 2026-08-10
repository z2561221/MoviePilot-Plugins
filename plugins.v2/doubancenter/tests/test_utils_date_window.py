import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _load_utils():
    """使用最小 MoviePilot 宿主桩加载日期工具模块。"""
    module_names = (
        "app",
        "app.core",
        "app.core.config",
        "app.core.metainfo",
        "app.log",
        "app.schemas",
        "app.schemas.types",
        "pytz",
    )
    previous = {name: sys.modules.get(name) for name in module_names}
    app = types.ModuleType("app")
    app.__path__ = []
    core = types.ModuleType("app.core")
    core.__path__ = []
    config = types.ModuleType("app.core.config")
    config.settings = types.SimpleNamespace(TZ="Asia/Shanghai")
    metainfo = types.ModuleType("app.core.metainfo")
    metainfo.MetaInfo = type("MetaInfo", (), {})
    log = types.ModuleType("app.log")
    log.logger = types.SimpleNamespace(error=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)
    schemas = types.ModuleType("app.schemas")
    schemas.__path__ = []
    schema_types = types.ModuleType("app.schemas.types")
    schema_types.MediaType = types.SimpleNamespace(TV="tv")
    pytz = types.ModuleType("pytz")
    pytz.timezone = ZoneInfo
    sys.modules.update({
        "app": app,
        "app.core": core,
        "app.core.config": config,
        "app.core.metainfo": metainfo,
        "app.log": log,
        "app.schemas": schemas,
        "app.schemas.types": schema_types,
        "pytz": pytz,
    })
    try:
        spec = importlib.util.spec_from_file_location("doubancenter_utils_date_test", PLUGIN_DIR / "utils.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


utils = _load_utils()


class UtilsDateWindowTest(unittest.TestCase):
    """验证榜单上映日期提取与前后时间窗口。"""

    def test_get_media_release_date_prefers_requested_season(self):
        media = types.SimpleNamespace(
            release_date="2020-01-01",
            first_air_date="2020-01-02",
            season_info=[
                {"season_number": 1, "air_date": "2020-01-01"},
                {"season_number": 2, "air_date": "2026-08-15T00:00:00.000Z"},
            ],
        )

        self.assertEqual(utils.get_media_release_date(media, season=2), "2026-08-15")
        self.assertEqual(utils.get_media_release_date(media), "2020-01-01")

    def test_future_and_recent_windows_include_today_and_boundary(self):
        today = datetime.datetime.now(ZoneInfo("Asia/Shanghai")).date()

        self.assertTrue(utils.is_within_days(today.isoformat(), 0))
        self.assertTrue(utils.is_within_days((today + datetime.timedelta(days=7)).isoformat(), 7))
        self.assertFalse(utils.is_within_days((today - datetime.timedelta(days=1)).isoformat(), 7))
        self.assertTrue(utils.is_within_recent_days(f"{today - datetime.timedelta(days=7)}T12:30:00Z", 7))
        self.assertFalse(utils.is_within_recent_days((today + datetime.timedelta(days=1)).isoformat(), 7))

    def test_invalid_date_is_rejected(self):
        self.assertFalse(utils.is_within_days("not-a-date", 7))
        self.assertFalse(utils.is_within_recent_days("", 7))


if __name__ == "__main__":
    unittest.main()
