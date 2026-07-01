from __future__ import annotations

import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"


class DownloadManagerLocalDiagnosticsTest(unittest.TestCase):
    def test_plugin_registers_diagnostics_api_route(self) -> None:
        init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
        route_source = (PLUGIN_DIR / "controller" / "api.py").read_text(encoding="utf-8")
        api_source = (PLUGIN_DIR / "controller" / "handlers.py").read_text(encoding="utf-8")

        self.assertIn("api_diagnostics", init_source)
        self.assertIn('"path": "/diagnostics"', route_source)
        self.assertIn("def api_diagnostics(plugin):", api_source)
        self.assertIn("plugin._diagnostics()", api_source)

    def test_plugin_exposes_diagnostics_wrapper(self) -> None:
        init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
        diagnostics_source = (PLUGIN_DIR / "modules" / "diagnostics.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("build_diagnostics as _build_diagnostics_impl", init_source)
        self.assertIn("def _diagnostics(self):", init_source)
        self.assertIn("return _build_diagnostics_impl(self)", init_source)
        self.assertIn("def build_diagnostics(plugin):", diagnostics_source)
        self.assertIn('"downloaders"', diagnostics_source)
        self.assertIn('"rename_history"', diagnostics_source)
        self.assertIn('"checks"', diagnostics_source)

    def test_history_page_exposes_diagnostics_tab(self) -> None:
        page_source = (PLUGIN_DIR / "src" / "components" / "Page.vue").read_text(
            encoding="utf-8"
        )

        self.assertIn("const activeTab = ref('history')", page_source)
        self.assertIn("const diagnostics = ref(null)", page_source)
        self.assertIn("async function loadDiagnostics()", page_source)
        self.assertIn("getPluginApi(props.api, 'diagnostics')", page_source)
        self.assertIn('value="diagnostics"', page_source)
        self.assertIn("@click=\"loadDiagnostics\"", page_source)
        self.assertIn("diagnostics?.plugin?.version", page_source)
        self.assertIn("diagnostics?.rename_history?.failed", page_source)


if __name__ == "__main__":
    unittest.main()
