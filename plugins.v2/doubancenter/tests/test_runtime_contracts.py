import ast
import json
import re
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_DIR.parents[1]


class DoubanCenterRuntimeContractsTest(unittest.TestCase):
    def test_metadata_versions_stay_in_sync(self):
        init_text = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8-sig")
        plugin_json = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
        ai_spec = json.loads((PLUGIN_DIR / "ai_spec.json").read_text(encoding="utf-8"))
        package = json.loads((REPO_ROOT / "package.v2.json").read_text(encoding="utf-8"))

        version = re.search(r'plugin_version\s*=\s*"([^"]+)"', init_text).group(1)

        self.assertEqual(plugin_json["version"], version)
        self.assertEqual(ai_spec["version"], version)
        self.assertEqual(package["DoubanCenter"]["version"], version)
        self.assertIn(f"v{version}", plugin_json["history"])
        self.assertIn(f"v{version}", package["DoubanCenter"]["history"])

    def test_latest_history_text_stays_in_sync(self):
        init_text = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8-sig")
        plugin_json = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
        package = json.loads((REPO_ROOT / "package.v2.json").read_text(encoding="utf-8"))

        version = re.search(r'plugin_version\s*=\s*"([^"]+)"', init_text).group(1)
        history_key = f"v{version}"

        self.assertEqual(
            plugin_json["history"][history_key],
            package["DoubanCenter"]["history"][history_key],
        )

    def test_plugin_entry_public_members_have_docstrings(self):
        tree = ast.parse((PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8-sig"))
        missing = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            if ast.get_docstring(node) is None:
                missing.append(f"{node.name}:{node.lineno}")

        self.assertEqual(missing, [])

    def test_all_public_source_members_have_chinese_docstrings(self):
        missing = []
        non_chinese = []
        cjk_pattern = re.compile(r"[\u4e00-\u9fff]")

        for source_path in sorted(PLUGIN_DIR.rglob("*.py")):
            if "tests" in source_path.parts or "__pycache__" in source_path.parts:
                continue
            tree = ast.parse(source_path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if node.name.startswith("_"):
                    continue
                docstring = ast.get_docstring(node)
                rel_path = source_path.relative_to(PLUGIN_DIR).as_posix()
                marker = f"{rel_path}:{node.name}:{node.lineno}"
                if not docstring:
                    missing.append(marker)
                elif not cjk_pattern.search(docstring):
                    non_chinese.append(marker)

        self.assertEqual(missing, [])
        self.assertEqual(non_chinese, [])

    def test_frontend_api_routes_use_bear_auth(self):
        controller_text = (PLUGIN_DIR / "controller" / "api.py").read_text(encoding="utf-8")

        self.assertGreaterEqual(controller_text.count('"auth": "bear"'), 15)
        self.assertNotIn('"auth": "apikey"', controller_text)

    def test_frontend_source_uses_injected_api_only(self):
        api_source = (PLUGIN_DIR / "src" / "components" / "api.js").read_text(encoding="utf-8")

        self.assertNotIn("fetch(", api_source)
        self.assertIn("api.get", api_source)
        self.assertIn("api.post", api_source)

    def test_vue_runtime_asset_contract_is_preserved(self):
        init_text = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8-sig")

        self.assertIn('return "vue", "dist/assets"', init_text)
        self.assertTrue((PLUGIN_DIR / "dist" / "assets" / "remoteEntry.js").exists())

    def test_frontend_metadata_and_page_toolbar_are_standardized(self):
        init_text = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8-sig")
        version = re.search(r'plugin_version\s*=\s*"([^"]+)"', init_text).group(1)
        frontend_package = json.loads((PLUGIN_DIR / "package.json").read_text(encoding="utf-8"))
        vite_config = (PLUGIN_DIR / "vite.config.js").read_text(encoding="utf-8")
        page_source = (PLUGIN_DIR / "src" / "components" / "Page.vue").read_text(encoding="utf-8")
        config_source = (PLUGIN_DIR / "src" / "components" / "Config.vue").read_text(encoding="utf-8")
        overview_source = (PLUGIN_DIR / "service" / "dashboard_overview.py").read_text(encoding="utf-8")

        self.assertEqual(frontend_package["version"], version)
        self.assertIn("name: 'DoubanCenter'", vite_config)
        self.assertIn("<VToolbar", page_source)
        self.assertIn("dc-page-toolbar", page_source)
        self.assertIn("订阅观察", config_source)
        self.assertIn("订阅观察", overview_source)
        self.assertNotIn("条件筛选", overview_source)

    def test_wish_sync_config_defaults_are_declared(self):
        config_source = (PLUGIN_DIR / "model" / "config.py").read_text(encoding="utf-8")
        init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8-sig")

        for key in (
            '"wish_enabled"',
            '"wish_cron"',
            '"wish_user"',
            '"wish_notify"',
            '"wish_max_pages"',
        ):
            self.assertIn(key, config_source)
            self.assertIn(key, init_source)

        self.assertIn('"wish_max_pages": 1', config_source)
        self.assertIn('DEFAULT_WISH_CRON = "*/30 * * * *"', config_source)
        self.assertIn('"wish_cron": DEFAULT_WISH_CRON', config_source)

    def test_wish_sync_storage_helpers_are_declared(self):
        storage_source = (PLUGIN_DIR / "storage" / "records.py").read_text(encoding="utf-8")

        for name in (
            "FOLIO_WISH_STATE_KEY",
            "FOLIO_WISH_SEEN_KEY",
            "FOLIO_WISH_QUEUE_KEY",
            "FOLIO_WISH_PROCESSED_KEY",
            "FOLIO_WISH_FAILED_KEY",
            "read_folio_wish_state",
            "save_folio_wish_state",
            "read_folio_wish_seen",
            "save_folio_wish_seen",
            "read_folio_wish_queue",
            "save_folio_wish_queue",
            "read_folio_wish_processed",
            "save_folio_wish_processed",
            "read_folio_wish_failed",
            "save_folio_wish_failed",
        ):
            self.assertIn(name, storage_source)

    def test_backend_refactor_context_is_documented(self):
        context_path = PLUGIN_DIR / "ai_spec" / "plugin_context.md"

        self.assertTrue(context_path.exists())
        text = context_path.read_text(encoding="utf-8")
        for phrase in (
            "controller/api.py",
            "service/subscription.py",
            "service/observation.py",
            "service/archive.py",
            "storage/records.py",
            "禁止未确认时修改 Vue 联邦产物",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
