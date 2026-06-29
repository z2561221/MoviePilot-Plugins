from __future__ import annotations

import ast
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"


def _load_api_rename_history():
    source = (PLUGIN_DIR / "api.py").read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    func = next(
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name == "api_rename_history"
    )
    namespace = {}
    exec(compile(ast.Module(body=[func], type_ignores=[]), "api_rename_history", "exec"), namespace)
    return namespace["api_rename_history"]


class FakeHistoryPlugin:
    def __init__(self, records):
        self.records = records

    def get_data(self, key):
        return self.records if key == "rename_records" else {}


class DownloadManagerLocalManualRetryApiTest(unittest.TestCase):
    def test_plugin_registers_manual_retry_api_route(self) -> None:
        init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
        api_source = (PLUGIN_DIR / "api.py").read_text(encoding="utf-8")

        self.assertIn("api_retry_renames", init_source)
        self.assertIn('"path": "/retry_renames"', init_source)
        self.assertIn("def api_retry_renames(plugin):", api_source)
        self.assertIn("plugin._retry_pending_renames()", api_source)

    def test_plugin_registers_single_retry_api_route(self) -> None:
        init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
        api_source = (PLUGIN_DIR / "api.py").read_text(encoding="utf-8")

        self.assertIn("api_retry_rename", init_source)
        self.assertIn('"path": "/retry_rename"', init_source)
        self.assertIn("def api_retry_rename(plugin, hash: str = \"\"):", api_source)
        self.assertIn("plugin._retry_rename(hash)", api_source)

    def test_history_page_exposes_one_click_retry_button(self) -> None:
        page_source = (PLUGIN_DIR / "src" / "components" / "Page.vue").read_text(
            encoding="utf-8"
        )

        self.assertIn("const retrying = ref(false)", page_source)
        self.assertIn("async function doRetryRenames()", page_source)
        self.assertIn("postPluginApi(props.api, 'retry_renames'", page_source)
        self.assertIn('@click="doRetryRenames"', page_source)
        self.assertIn(':loading="retrying"', page_source)

    def test_history_page_exposes_row_retry_button(self) -> None:
        page_source = (PLUGIN_DIR / "src" / "components" / "Page.vue").read_text(
            encoding="utf-8"
        )

        self.assertIn("const retryingHash = ref('')", page_source)
        self.assertIn("async function doRetryRename(hash)", page_source)
        self.assertIn("postPluginApi(props.api, 'retry_rename', { hash })", page_source)
        self.assertIn('@click="doRetryRename(r.hash)"', page_source)
        self.assertIn(':loading="retryingHash === r.hash"', page_source)

    def test_post_plugin_api_adds_payload_to_query_params(self) -> None:
        api_helper = (PLUGIN_DIR / "src" / "components" / "api.js").read_text(
            encoding="utf-8"
        )
        built_helper = next((PLUGIN_DIR / "dist" / "assets").glob("_plugin-vue_export-helper-*.js")).read_text(
            encoding="utf-8"
        )

        for source in (api_helper, built_helper):
            self.assertIn("new URLSearchParams()", source)
            self.assertIn("params.set(key, value)", source)
            self.assertIn("query ? `?${query}` : ''", source)
            self.assertIn("api.post(url, payload)", source)

    def test_rename_history_backfills_hash_for_legacy_records(self) -> None:
        api_rename_history = _load_api_rename_history()
        plugin = FakeHistoryPlugin(
            {
                "hash-one": {
                    "original_name": "Original",
                    "after_name": "After",
                    "success": False,
                    "time": "2026-06-21 01:00:00",
                }
            }
        )

        result = api_rename_history(plugin)

        self.assertEqual(result["items"][0]["hash"], "hash-one")


if __name__ == "__main__":
    unittest.main()
