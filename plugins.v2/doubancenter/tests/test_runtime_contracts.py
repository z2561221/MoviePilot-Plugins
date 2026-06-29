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

    def test_frontend_api_routes_use_bear_auth(self):
        controller_text = (PLUGIN_DIR / "controller" / "api.py").read_text(encoding="utf-8")

        self.assertGreaterEqual(controller_text.count('"auth": "bear"'), 15)
        self.assertNotIn('"auth": "apikey"', controller_text)

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
