from __future__ import annotations

import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"


class DownloadManagerLocalManualRetryApiTest(unittest.TestCase):
    def test_plugin_registers_manual_retry_api_route(self) -> None:
        init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
        route_source = (PLUGIN_DIR / "controller" / "api.py").read_text(encoding="utf-8")
        api_source = (PLUGIN_DIR / "api.py").read_text(encoding="utf-8")

        self.assertIn("api_retry_renames", init_source)
        self.assertIn('"path": "/retry_renames"', route_source)
        self.assertIn("def api_retry_renames(plugin):", api_source)
        self.assertIn("plugin._retry_pending_renames()", api_source)

    def test_plugin_registers_single_retry_api_route(self) -> None:
        init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
        route_source = (PLUGIN_DIR / "controller" / "api.py").read_text(encoding="utf-8")
        api_source = (PLUGIN_DIR / "api.py").read_text(encoding="utf-8")

        self.assertIn("api_retry_rename", init_source)
        self.assertIn('"path": "/retry_rename"', route_source)
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


if __name__ == "__main__":
    unittest.main()
