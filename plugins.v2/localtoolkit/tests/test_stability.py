import importlib
import inspect
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _Logger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _PluginBase:
    def __init__(self):
        self._data = {}
        self._posted = []
        self._saved_config = None

    def get_data(self, key=None):
        return self._data.get(key)

    def save_data(self, key=None, value=None):
        self._data[key] = value

    def update_config(self, config):
        self._saved_config = config

    def post_message(self, **kwargs):
        self._posted.append(kwargs)


class _NotificationType:
    Plugin = "Plugin"


class _Settings:
    CACHE_BACKEND_URL = "redis://127.0.0.1:6379"


class _RedisModule(types.ModuleType):
    def from_url(self, *args, **kwargs):
        raise RuntimeError("redis unavailable")


class _CronTrigger:
    @classmethod
    def from_crontab(cls, expr):
        fields = str(expr or "").split()
        if len(fields) != 5:
            raise ValueError("wrong number of cron fields")
        return ("cron", expr)


class _MediaServerHelper:
    def get_configs(self):
        return {}

    def get_services(self, name_filters=None):
        return {}


class _PluginManager:
    def get_plugin_config(self, plugin_id):
        return {}


class _CleanupAdapter:
    def __init__(self, candidates=None, delete_results=None):
        self.candidates = list(candidates or [])
        self.delete_results = list(delete_results or [])
        self.deleted = []

    def list_servers(self):
        return [{"title": "emby", "value": "emby"}]

    def list_libraries(self, selected_server="", selected_user=""):
        return [{"title": "Movies", "value": "library-1"}]

    def list_users(self, selected_server=""):
        return [{"title": "admin", "value": "admin"}]

    def iter_candidates(self, config):
        return iter(self.candidates)

    def delete_item(self, candidate):
        self.deleted.append(candidate.movie_id)
        if self.delete_results:
            return self.delete_results.pop(0)
        return True


def _install_stubs():
    app = types.ModuleType("app")
    app.__path__ = []

    plugins = types.ModuleType("app.plugins")
    plugins._PluginBase = _PluginBase

    log = types.ModuleType("app.log")
    log.logger = _Logger()

    schemas = types.ModuleType("app.schemas")
    schemas.__path__ = []

    schema_types = types.ModuleType("app.schemas.types")
    schema_types.NotificationType = _NotificationType

    core = types.ModuleType("app.core")
    core.__path__ = []

    core_config = types.ModuleType("app.core.config")
    core_config.settings = _Settings()

    core_plugin = types.ModuleType("app.core.plugin")
    core_plugin.PluginManager = _PluginManager

    helper = types.ModuleType("app.helper")
    helper.__path__ = []

    mediaserver = types.ModuleType("app.helper.mediaserver")
    mediaserver.MediaServerHelper = _MediaServerHelper

    apscheduler = types.ModuleType("apscheduler")
    apscheduler.__path__ = []

    triggers = types.ModuleType("apscheduler.triggers")
    triggers.__path__ = []

    cron = types.ModuleType("apscheduler.triggers.cron")
    cron.CronTrigger = _CronTrigger

    sys.modules.update(
        {
            "app": app,
            "app.plugins": plugins,
            "app.log": log,
            "app.schemas": schemas,
            "app.schemas.types": schema_types,
            "app.core": core,
            "app.core.config": core_config,
            "app.core.plugin": core_plugin,
            "app.helper": helper,
            "app.helper.mediaserver": mediaserver,
            "redis": _RedisModule("redis"),
            "apscheduler": apscheduler,
            "apscheduler.triggers": triggers,
            "apscheduler.triggers.cron": cron,
        }
    )


def _import_fresh_plugin():
    _install_stubs()
    package_root = str(PLUGIN_DIR.parent)
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    for name in list(sys.modules):
        if name == "localtoolkit" or name.startswith("localtoolkit."):
            sys.modules.pop(name)
    return importlib.import_module("localtoolkit")


class LocalToolkitStabilityTest(unittest.TestCase):
    def setUp(self):
        module = _import_fresh_plugin()
        self.plugin = module.LocalToolkit()
        self.plugin.init_plugin({"migration_done": True})

    def test_history_pagination_sanitizes_bad_query_values(self):
        self.plugin._data["tool_history"] = [{"idx": i} for i in range(35)]

        response = self.plugin.api_history(page="bad", page_size="0")

        self.assertEqual(response["page"], 1)
        self.assertEqual(response["page_size"], 15)
        self.assertEqual(response["total"], 35)
        self.assertEqual(response["total_pages"], 3)
        self.assertEqual(len(response["items"]), 15)

    def test_history_endpoint_annotations_allow_sanitizing_bad_query_values(self):
        signature = inspect.signature(self.plugin.api_history)

        self.assertIs(signature.parameters["page"].annotation, Any)
        self.assertIs(signature.parameters["page_size"].annotation, Any)

    def test_history_pagination_clamps_page_size(self):
        self.plugin._data["tool_history"] = [{"idx": i} for i in range(150)]

        response = self.plugin.api_history(page=1, page_size=500)

        self.assertEqual(response["page_size"], 100)
        self.assertEqual(len(response["items"]), 100)

    def test_migration_marks_done_when_no_legacy_configs_exist(self):
        module = _import_fresh_plugin()
        plugin = module.LocalToolkit()

        plugin.init_plugin({})

        self.assertTrue(plugin._config["migration_done"])
        self.assertIsNotNone(plugin._saved_config)
        self.assertTrue(plugin._saved_config["migration_done"])

    def test_vue_mode_get_page_returns_empty_schema(self):
        self.assertEqual(self.plugin.get_page(), [])

    def test_vue_mode_get_form_returns_empty_schema_with_config_model(self):
        schema, model = self.plugin.get_form()

        self.assertEqual(schema, [])
        self.assertEqual(model, self.plugin._config)

    def test_history_pagination_ignores_corrupt_history_data(self):
        self.plugin._data["tool_history"] = {"bad": "shape"}

        response = self.plugin.api_history()

        self.assertEqual(response["total"], 0)
        self.assertEqual(response["items"], [])

    def test_add_history_recovers_from_corrupt_history_storage(self):
        from localtoolkit.modules.base import BaseToolModule

        self.plugin._data["tool_history"] = {"bad": "shape"}
        module = BaseToolModule(self.plugin)
        module.module_key = "demo"
        module.module_name = "Demo"

        module.add_history(status="success", summary="ok", duration=1.2345)

        saved = self.plugin._data["tool_history"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["module"], "demo")
        self.assertEqual(saved[0]["duration"], 1.234)

    def test_api_run_returns_error_when_module_raises(self):
        class CrashingModule:
            module_name = "Crash"

            def run_once(self):
                raise RuntimeError("boom")

        self.plugin.tmdb_cache = CrashingModule()

        response = self.plugin.api_run("tmdb_cache")

        self.assertFalse(response["success"])
        self.assertIn("boom", response["message"])

    def test_api_status_keeps_other_modules_when_one_status_fails(self):
        class CrashingModule:
            module_name = "Crash"

            def get_status(self):
                raise RuntimeError("boom")

        self.plugin.check_missing = CrashingModule()

        response = self.plugin.api_status()

        self.assertIn("tmdb_cache", response["modules"])
        self.assertFalse(response["modules"]["check_missing"]["success"])
        self.assertIn("boom", response["modules"]["check_missing"]["error"])

    def test_invalid_cron_does_not_break_service_registration(self):
        from localtoolkit.modules.library_cleanup import LibraryCleanupModule

        module = LibraryCleanupModule(self.plugin)
        module.load_config({"enabled": True, "cron": "not-a-cron"})

        self.assertEqual(module.get_service(), [])

    def test_library_cleanup_default_config_uses_requested_two_conditions(self):
        from localtoolkit.modules.library_cleanup import LibraryCleanupModule

        defaults = LibraryCleanupModule(self.plugin).get_default_config()

        self.assertEqual(defaults["filter_favorite"], "unfav")
        self.assertEqual(defaults["filter_played"], "played")
        self.assertEqual(defaults["days_threshold"], 20)
        self.assertEqual(defaults["filter_favorite_2"], "unfav")
        self.assertEqual(defaults["filter_played_2"], "unplayed")
        self.assertEqual(defaults["days_threshold_2"], 40)

    def test_library_cleanup_legacy_saved_config_loads_with_second_condition_defaults(self):
        module = _import_fresh_plugin()
        plugin = module.LocalToolkit()

        plugin.init_plugin(
            {
                "enabled": True,
                "migration_done": True,
                "library_cleanup": {
                    "enabled": True,
                    "filter_favorite": "unfav",
                    "filter_played": "played",
                    "days_threshold": 25,
                },
            }
        )

        cleanup_config = plugin._config["library_cleanup"]
        self.assertEqual(cleanup_config["days_threshold"], 25)
        self.assertEqual(cleanup_config["filter_favorite_2"], "unfav")
        self.assertEqual(cleanup_config["filter_played_2"], "unplayed")
        self.assertEqual(cleanup_config["days_threshold_2"], 40)

    def test_library_cleanup_uses_adapter_for_options(self):
        from localtoolkit.modules.library_cleanup import LibraryCleanupModule

        module = LibraryCleanupModule(self.plugin, adapter=_CleanupAdapter())
        module.load_config({"selected_server": "emby", "selected_user": "admin"})

        options = module.get_options()

        self.assertEqual(options["servers"], [{"title": "emby", "value": "emby"}])
        self.assertEqual(options["libraries"], [{"title": "Movies", "value": "library-1"}])
        self.assertEqual(options["users"], [{"title": "admin", "value": "admin"}])

    def test_library_cleanup_includes_unmatched_emby_video_without_tmdb(self):
        from localtoolkit.adapter.media_server import MediaServerCleanupAdapter

        class RawVideoAdapter(MediaServerCleanupAdapter):
            def __init__(self):
                super().__init__(helper=_MediaServerHelper(), chain=None)

            def _library_items_by_http(self, server, library_id, selected_user):
                return [{
                    "Id": "video-704",
                    "Name": "JUR-704",
                    "Type": "Video",
                    "DateCreated": "2026-04-01T00:00:00Z",
                    "ProviderIds": {},
                    "UserData": {"Played": True, "IsFavorite": False},
                }]

        movies = list(RawVideoAdapter().iter_library_candidates(
            server="Embyserver",
            library_id="6741",
            library_name="Movies",
            selected_user="Z&X",
        ))

        self.assertEqual(len(movies), 1)
        self.assertEqual(movies[0].title, "JUR-704")
        self.assertEqual(movies[0].movie_id, "video-704")
        self.assertTrue(movies[0].played)
        self.assertFalse(movies[0].favorite)

    def test_library_cleanup_keeps_last_error_when_adapter_raises(self):
        from localtoolkit.modules.library_cleanup import LibraryCleanupModule

        class BrokenAdapter(_CleanupAdapter):
            def iter_candidates(self, config):
                raise RuntimeError("boom")

        module = LibraryCleanupModule(self.plugin, adapter=BrokenAdapter())
        module.load_config({"enabled": True})

        response = module.run_once()

        self.assertFalse(response["success"])
        self.assertIn("boom", module.last_error)

    def test_library_cleanup_auto_delete_sends_only_auto_delete_notice(self):
        self.skipTest("旧 delegate 行为已由自持 adapter 流程用例覆盖")
        from datetime import datetime, timezone
        from localtoolkit.modules.library_cleanup import LibraryCleanupModule

        class Movie:
            movie_id = "movie-1"
            code = "CODE-001"
            date_created = "2026-05-29T00:00:00Z"
            date_created_obj = datetime(2026, 5, 29, tzinfo=timezone.utc)

        class Result:
            qualified_count = 1
            qualified_movies = [Movie()]

        class Delegate:
            def __init__(self):
                self._notify = True
                self.deleted = []

            def run_cleanup(self):
                if self._notify:
                    self._posted.append({"title": "delegate", "text": "原版检查报告"})
                return Result()

            def _emby_delete(self, movie_id):
                self.deleted.append(movie_id)
                return True

            def get_data(self, key=None):
                return {"qualified_count": 1}

        module = LibraryCleanupModule(self.plugin)
        module.load_config({"notify": True, "auto_delete": True, "auto_delete_delay": 0, "days_threshold": 20})
        delegate = Delegate()
        delegate._posted = self.plugin._posted
        module._delegate = lambda: delegate

        response = module.run_once()

        self.assertTrue(response["success"])
        self.assertEqual(delegate.deleted, ["movie-1"])
        self.assertEqual(len(self.plugin._posted), 1)
        self.assertEqual(self.plugin._posted[0]["title"], "清库存检查报告")
        self.assertIn("即将开始自动删除", self.plugin._posted[0]["text"])

    def test_library_cleanup_manual_mode_sends_only_delegate_notice(self):
        self.skipTest("旧 delegate 行为已由自持 adapter 流程用例覆盖")
        from datetime import datetime, timezone
        from localtoolkit.modules.library_cleanup import LibraryCleanupModule

        class Movie:
            movie_id = "movie-1"
            code = "CODE-001"
            date_created = "2026-05-29T00:00:00Z"
            date_created_obj = datetime(2026, 5, 29, tzinfo=timezone.utc)

        class Result:
            qualified_count = 1
            qualified_movies = [Movie()]

        class Delegate:
            def __init__(self):
                self._notify = True

            def run_cleanup(self):
                if self._notify:
                    self._posted.append({"title": "delegate", "text": "原版检查报告"})
                return Result()

            def get_data(self, key=None):
                return {"qualified_count": 1}

        module = LibraryCleanupModule(self.plugin)
        module.load_config({"notify": True, "auto_delete": False, "days_threshold": 20})
        delegate = Delegate()
        delegate._posted = self.plugin._posted
        module._delegate = lambda: delegate

        response = module.run_once()

        self.assertTrue(response["success"])
        self.assertEqual(len(self.plugin._posted), 1)
        self.assertEqual(self.plugin._posted[0]["title"], "delegate")
        self.assertNotIn("即将开始自动删除", self.plugin._posted[0]["text"])

    def test_library_cleanup_auto_delete_zero_match_sends_clean_notice(self):
        self.skipTest("旧 delegate 行为已由自持 adapter 流程用例覆盖")
        from localtoolkit.modules.library_cleanup import LibraryCleanupModule

        class Result:
            qualified_count = 0
            qualified_movies = []

        class Delegate:
            def __init__(self):
                self._notify = True

            def run_cleanup(self):
                if self._notify:
                    self._posted.append({"title": "delegate", "text": "原版检查报告"})
                return Result()

            def get_data(self, key=None):
                return {"qualified_count": 0}

        module = LibraryCleanupModule(self.plugin)
        module.load_config({"notify": True, "auto_delete": True})
        delegate = Delegate()
        delegate._posted = self.plugin._posted
        module._delegate = lambda: delegate

        response = module.run_once()

        self.assertTrue(response["success"])
        self.assertEqual(len(self.plugin._posted), 1)
        self.assertEqual(self.plugin._posted[0]["title"], "清库存检查报告")
        self.assertIn("媒体库很干净", self.plugin._posted[0]["text"])

    def test_library_cleanup_auto_delete_aborts_when_over_limit(self):
        self.skipTest("旧 delegate 行为已由自持 adapter 流程用例覆盖")
        from datetime import datetime, timezone
        from localtoolkit.modules.library_cleanup import LibraryCleanupModule

        class Movie:
            def __init__(self, index):
                self.movie_id = f"movie-{index}"
                self.code = f"CODE-{index:03d}"
                self.date_created = "2026-05-29T00:00:00Z"
                self.date_created_obj = datetime(2026, 5, 29, tzinfo=timezone.utc)

        class Result:
            qualified_count = 2
            qualified_movies = [Movie(1), Movie(2)]

        class Delegate:
            def __init__(self):
                self._notify = True
                self.deleted = []

            def run_cleanup(self):
                return Result()

            def _emby_delete(self, movie_id):
                self.deleted.append(movie_id)
                return True

            def get_data(self, key=None):
                return {"qualified_count": 2}

        module = LibraryCleanupModule(self.plugin)
        module.load_config({
            "notify": True,
            "auto_delete": True,
            "auto_delete_delay": 0,
            "auto_delete_max_count": 1,
        })
        delegate = Delegate()
        module._delegate = lambda: delegate

        response = module.run_once()

        self.assertFalse(response["success"])
        self.assertEqual(delegate.deleted, [])
        self.assertIn("超过自动删除上限", response["summary"])


    def test_library_cleanup_owned_auto_delete_sends_configured_notice(self):
        from datetime import datetime, timezone
        from localtoolkit.modules.library_cleanup import LibraryCleanupModule
        from localtoolkit.model.library_cleanup import CleanupCandidate

        movie = CleanupCandidate(
            movie_id="movie-1",
            code="CODE-001",
            date_created="2026-05-29T00:00:00Z",
            date_created_obj=datetime(2026, 5, 29, tzinfo=timezone.utc),
            played=True,
            favorite=False,
        )
        adapter = _CleanupAdapter([movie])
        module = LibraryCleanupModule(self.plugin, adapter=adapter)
        module.load_config({
            "notify": True,
            "auto_delete": True,
            "auto_delete_delay": 0,
            "days_threshold": 20,
            "filter_played": "played",
            "filter_favorite": "unfav",
        })

        response = module.run_once()

        self.assertTrue(response["success"])
        self.assertEqual(adapter.deleted, ["movie-1"])
        self.assertEqual(self.plugin._posted[0]["title"], "清理库存检查报告")
        self.assertIn("即将开始自动删除", self.plugin._posted[0]["text"])
        self.assertIn("条件一：未收藏 + 已看过 + 超过 20 天", self.plugin._posted[0]["text"])
        self.assertIn("自动删除：已开启", self.plugin._posted[0]["text"])
        saved = self.plugin._data["library_cleanup_result"]
        self.assertEqual(saved["condition_label"], "条件一（未收藏 + 已看过 + 超过20天）")
        self.assertEqual(saved["deletion"], {"success_count": 1, "fail_count": 0})

    def test_library_cleanup_owned_manual_mode_sends_dynamic_notice(self):
        from datetime import datetime, timezone
        from localtoolkit.modules.library_cleanup import LibraryCleanupModule
        from localtoolkit.model.library_cleanup import CleanupCandidate

        movie = CleanupCandidate(
            movie_id="movie-1",
            code="CODE-001",
            date_created="2026-05-29T00:00:00Z",
            date_created_obj=datetime(2026, 5, 29, tzinfo=timezone.utc),
            played=True,
            favorite=False,
        )
        module = LibraryCleanupModule(self.plugin, adapter=_CleanupAdapter([movie]))
        module.load_config({
            "notify": True,
            "auto_delete": False,
            "days_threshold": 20,
            "filter_played": "played",
            "filter_favorite": "unfav",
        })

        response = module.run_once()

        self.assertTrue(response["success"])
        self.assertEqual(self.plugin._posted[0]["title"], "清理库存检查报告")
        self.assertNotIn("即将开始自动删除", self.plugin._posted[0]["text"])
        self.assertIn("条件一：未收藏 + 已看过 + 超过 20 天", self.plugin._posted[0]["text"])
        self.assertIn("自动删除：未开启", self.plugin._posted[0]["text"])
        saved = self.plugin._data["library_cleanup_result"]
        self.assertEqual(saved["condition_label"], "条件一（未收藏 + 已看过 + 超过20天）")
        self.assertEqual(saved["conditions"], ["条件一（未收藏 + 已看过 + 超过20天）"])
        self.assertEqual(saved["qualified_count"], 1)
        self.assertEqual(saved["qualified_movies"][0]["movie_id"], "movie-1")

    def test_library_cleanup_owned_zero_match_sends_clean_notice(self):
        from localtoolkit.modules.library_cleanup import LibraryCleanupModule

        module = LibraryCleanupModule(self.plugin, adapter=_CleanupAdapter())
        module.load_config({"notify": True, "auto_delete": True})

        response = module.run_once()

        self.assertTrue(response["success"])
        self.assertEqual(self.plugin._posted[0]["title"], "清理库存检查报告")
        self.assertIn("媒体库很干净", self.plugin._posted[0]["text"])

    def test_library_cleanup_owned_auto_delete_aborts_when_over_limit(self):
        from datetime import datetime, timezone
        from localtoolkit.modules.library_cleanup import LibraryCleanupModule
        from localtoolkit.model.library_cleanup import CleanupCandidate

        movies = [
            CleanupCandidate(
                movie_id=f"movie-{index}",
                code=f"CODE-{index:03d}",
                date_created="2026-05-29T00:00:00Z",
                date_created_obj=datetime(2026, 5, 29, tzinfo=timezone.utc),
                played=True,
                favorite=False,
            )
            for index in (1, 2)
        ]
        adapter = _CleanupAdapter(movies)
        module = LibraryCleanupModule(self.plugin, adapter=adapter)
        module.load_config({
            "notify": True,
            "auto_delete": True,
            "auto_delete_delay": 0,
            "auto_delete_max_count": 1,
            "filter_played": "played",
            "filter_favorite": "unfav",
        })

        response = module.run_once()

        self.assertFalse(response["success"])
        self.assertEqual(adapter.deleted, [])
        self.assertIn("超过自动删除上限", response["summary"])

    def test_library_cleanup_two_conditions_return_or_union_without_duplicates(self):
        from datetime import datetime, timedelta, timezone
        from localtoolkit.model.library_cleanup import (
            CleanupCandidate,
            filter_cleanup_candidates,
        )

        now = datetime(2026, 7, 9, tzinfo=timezone.utc)

        def candidate(movie_id, days, played, favorite):
            return CleanupCandidate(
                movie_id=movie_id,
                code=movie_id.upper(),
                title=movie_id,
                date_created=(now - timedelta(days=days)).isoformat(),
                date_created_obj=now - timedelta(days=days),
                played=played,
                favorite=favorite,
            )

        config = {
            "filter_favorite": "unfav",
            "filter_played": "played",
            "days_threshold": 20,
            "filter_favorite_2": "unfav",
            "filter_played_2": "unplayed",
            "days_threshold_2": 40,
        }
        movies = [
            candidate("played-25", 25, True, False),
            candidate("unplayed-45", 45, False, False),
            candidate("duplicate", 60, False, False),
            candidate("duplicate", 60, False, False),
            candidate("favorite-80", 80, True, True),
            candidate("too-new", 30, False, False),
        ]

        result = filter_cleanup_candidates(movies, config, now=now)

        self.assertEqual(
            [movie.movie_id for movie in result.qualified_movies],
            ["played-25", "unplayed-45", "duplicate"],
        )
        self.assertEqual(result.qualified_count, 3)

    def test_library_cleanup_condition_label_matches_current_settings(self):
        from localtoolkit.model.library_cleanup import (
            build_cleanup_conditions,
            format_conditions_label,
        )

        label = format_conditions_label(
            build_cleanup_conditions(
                {
                    "filter_favorite": "unfav",
                    "filter_played": "played",
                    "days_threshold": 20,
                    "filter_favorite_2": "unfav",
                    "filter_played_2": "unplayed",
                    "days_threshold_2": 40,
                }
            )
        )

        self.assertEqual(
            label,
            "条件一（未收藏 + 已看过 + 超过20天）或 条件二（未收藏 + 未看过 + 超过40天）",
        )

        changed_label = format_conditions_label(
            build_cleanup_conditions(
                {
                    "filter_favorite": "fav",
                    "filter_played": "played",
                    "days_threshold": 10,
                    "filter_favorite_2": "unfav",
                    "filter_played_2": "played",
                    "days_threshold_2": 15,
                }
            )
        )

        self.assertEqual(
            changed_label,
            "条件一（已收藏 + 已看过 + 超过10天）或 条件二（未收藏 + 已看过 + 超过15天）",
        )

    def test_library_cleanup_report_uses_markdown_and_movie_titles(self):
        from datetime import datetime, timezone
        from localtoolkit.modules.library_cleanup import LibraryCleanupModule
        from localtoolkit.model.library_cleanup import CleanupCandidate, filter_cleanup_candidates

        checked_at = datetime(2026, 7, 11, tzinfo=timezone.utc)
        module = LibraryCleanupModule(self.plugin, adapter=_CleanupAdapter())
        module.load_config({
            "auto_delete": False,
            "filter_favorite": "unfav",
            "filter_played": "played",
            "days_threshold": 20,
            "filter_favorite_2": "unfav",
            "filter_played_2": "unplayed",
            "days_threshold_2": 60,
        })
        result = filter_cleanup_candidates([
            CleanupCandidate(
                movie_id="67698",
                code="67698",
                title="JUR-704",
                date_created="2026-05-10T15:01:30Z",
                played=False,
                favorite=False,
            ),
        ], module.config, now=checked_at)

        text = module._build_report_text(result, "符合条件 1 部，删除成功 0 部，失败 0 部", checked_at)

        self.assertIn("**清理库存检查报告**", text)
        self.assertIn("**筛选条件**", text)
        self.assertIn("条件一：未收藏 + 已看过 + 超过 20 天", text)
        self.assertIn("条件二：未收藏 + 未看过 + 超过 60 天", text)
        self.assertIn("**检查结果**", text)
        self.assertIn("符合条件：1 部", text)
        self.assertIn("自动删除：未开启", text)
        self.assertIn("**待处理列表**", text)
        self.assertIn("1. JUR-704 | 61天 | 2026-05-10", text)
        self.assertNotIn("1. 67698 |", text)

    def test_library_cleanup_legacy_single_condition_config_stays_valid(self):
        from localtoolkit.model.library_cleanup import (
            build_cleanup_conditions,
            format_conditions_label,
        )

        conditions = build_cleanup_conditions(
            {
                "filter_favorite": "unfav",
                "filter_played": "played",
                "days_threshold": 20,
            }
        )

        self.assertEqual(len(conditions), 1)
        self.assertEqual(
            format_conditions_label(conditions),
            "条件一（未收藏 + 已看过 + 超过20天）",
        )


if __name__ == "__main__":
    unittest.main()
