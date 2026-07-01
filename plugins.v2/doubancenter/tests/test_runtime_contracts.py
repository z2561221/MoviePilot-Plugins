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
