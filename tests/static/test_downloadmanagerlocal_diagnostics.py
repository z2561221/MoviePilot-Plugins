from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"


class DownloadManagerLocalDiagnosticsTest(unittest.TestCase):
    def test_plugin_version_metadata_is_consistent(self) -> None:
        init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
        plugin_json = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
        package_json = json.loads((REPO / "package.v2.json").read_text(encoding="utf-8"))
        package_item = package_json["DownloadManagerLocal"]

        self.assertIn('plugin_version = "3.2.3"', init_source)
        self.assertEqual(plugin_json["version"], "3.2.3")
        self.assertEqual(package_item["version"], "3.2.3")
        self.assertIn("v3.2.1", plugin_json["history"])
        self.assertIn("v3.2.1", package_item["history"])
        self.assertIn("弹窗高度跳动", plugin_json["history"]["v3.2.1"])
        self.assertIn("弹窗高度跳动", package_item["history"]["v3.2.1"])
        self.assertIn("v3.2.0", plugin_json["history"])
        self.assertIn("v3.2.0", package_item["history"])

    def test_plugin_registers_diagnostics_api_route(self) -> None:
        init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
        api_source = (PLUGIN_DIR / "api.py").read_text(encoding="utf-8")

        self.assertIn("api_diagnostics", init_source)
        self.assertIn('"path": "/diagnostics"', init_source)
        self.assertIn("def api_diagnostics(plugin):", api_source)
        self.assertIn("plugin._diagnostics()", api_source)

    def test_downloaders_api_exposes_type_for_capability_warnings(self) -> None:
        api_source = (PLUGIN_DIR / "api.py").read_text(encoding="utf-8")
        config_source = (PLUGIN_DIR / "src" / "components" / "Config.vue").read_text(
            encoding="utf-8"
        )

        self.assertIn('"type": info.type', api_source)
        self.assertIn("selectedToDownloaderType", config_source)
        self.assertIn("Transmission 当前不支持种子重命名", config_source)
        self.assertIn("form.todownloader && selectedToDownloaderType === 'transmission'", config_source)

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

    def test_config_page_exposes_overview_and_detail_page_starts_with_history(self) -> None:
        page_source = (PLUGIN_DIR / "src" / "components" / "Page.vue").read_text(
            encoding="utf-8"
        )
        config_source = (PLUGIN_DIR / "src" / "components" / "Config.vue").read_text(
            encoding="utf-8"
        )

        self.assertIn("const activeTab = ref('history')", page_source)
        self.assertNotIn("activeTab = ref('overview')", page_source)
        self.assertNotIn("async function loadOverview()", page_source)
        self.assertIn("const diagnostics = ref(null)", page_source)
        self.assertIn("async function loadDiagnostics()", page_source)
        self.assertIn("getPluginApi(props.api, 'diagnostics')", page_source)
        self.assertIn("key: 'diagnostics'", page_source)
        self.assertIn("selectTab(tab.key)", page_source)
        self.assertIn("diagnostics?.plugin?.version", page_source)
        self.assertIn("diagnostics?.rename_archive?.archived", page_source)
        self.assertIn("const activeMain = ref('overview')", config_source)
        self.assertIn("const activeSub = ref('overview')", config_source)
        self.assertIn("getPluginApi(props.api, 'overview')", config_source)
        self.assertIn("title: '运行总览'", config_source)
        self.assertIn("运行链路", config_source)
        self.assertIn("兜底补刀", config_source)
        self.assertIn("width: min(1120px, calc(100vw - 48px))", config_source)
        self.assertIn("height: clamp(620px, calc(100vh - 96px), 760px)", config_source)
        self.assertIn("padding: 8px", config_source)
        self.assertIn(".dm-window { flex: 1 1 auto; min-height: 0; overflow-y: auto; }", config_source)
        self.assertIn(".dm-window--overview { overflow-y: hidden; }", config_source)
        self.assertIn("height: min(760px, calc(100dvh - 24px))", config_source)
        self.assertNotIn("width: min(1240px, calc(100vw - 48px))", config_source)
        self.assertNotIn("--dm-overview-card-height: 560px", config_source)
        self.assertNotIn("height: min(var(--dm-overview-card-height), calc(100vh - 56px))", config_source)
        self.assertNotIn("height: clamp(700px, calc(100vh - 56px), 900px)", config_source)
        self.assertIn("height: clamp(620px, calc(100vh - 120px), 780px)", page_source)
        self.assertIn("class=\"dm-state\"", page_source)
        self.assertIn("overflow-y: auto", page_source)

    def test_config_overview_runtime_flow_matches_design(self) -> None:
        config_source = (PLUGIN_DIR / "src" / "components" / "Config.vue").read_text(
            encoding="utf-8"
        )

        self.assertIn('class="dm-overview-section mb-3"', config_source)
        self.assertIn("运行链路", config_source)
        self.assertIn("runtimeFlows", config_source)
        self.assertIn("dm-flow", config_source)
        self.assertIn("dm-flow-block", config_source)
        self.assertIn("dm-flow-label", config_source)
        self.assertIn("dm-flow-row", config_source)
        self.assertIn("dm-flow-step", config_source)
        self.assertIn("dm-flow-arrow", config_source)
        self.assertIn('icon="mdi-arrow-right"', config_source)
        self.assertIn(":class=\"{ 'dm-window--overview': activeMain === 'overview' }\"", config_source)
        self.assertIn("转移做种", config_source)
        self.assertIn("IYUU铺种", config_source)
        self.assertIn("公共链路", config_source)
        self.assertIn("兜底补刀", config_source)
        self.assertIn("steps: ['下载完成', '延迟等待', '目标转移', '公共链路']", config_source)
        self.assertIn("steps: ['任务触发', '资源查询', '辅种下载', '公共链路']", config_source)
        self.assertIn("steps: ['命名处理', '站点标签', '做种校验']", config_source)
        self.assertIn("steps: ['异常命名', '兜底补刀', '失败计数', '归档恢复']", config_source)
        self.assertNotIn("steps: ['下载完成', '延迟等待', '目标转移', '命名处理', '站点标签', '做种校验']", config_source)
        self.assertNotIn("steps: ['任务触发', '资源查询', '辅种下载', '命名处理', '站点标签', '做种校验']", config_source)
        self.assertIn("dm-pane--overview", config_source)
        self.assertNotIn("运行拓扑", config_source)
        self.assertNotIn("竖向泳道 / 折线汇流 / 列对齐", config_source)
        self.assertNotIn("dm-runtime-topology", config_source)
        self.assertNotIn("topologyBadges", config_source)
        self.assertNotIn("topologyLanes", config_source)
        self.assertNotIn("dm-topology-rail", config_source)
        self.assertNotIn("dm-topology-merge", config_source)
        self.assertNotIn("dm-lane--transfer", config_source)
        self.assertNotIn("dm-lane--iyuu", config_source)
        self.assertNotIn("dm-lane--common", config_source)
        self.assertNotIn("dm-lane--fallback", config_source)
        self.assertNotIn("汇入", config_source)
        self.assertLess(
            config_source.index('class="dm-overview-section mb-3"'),
            config_source.index("dm-stat-grid"),
        )
        self.assertNotIn("链路一：转移做种", config_source)
        self.assertNotIn("链路二：IYUU铺种", config_source)
        self.assertNotIn("链路三：兜底补刀", config_source)

    def test_config_mobile_navigation_uses_horizontal_tabs(self) -> None:
        config_source = (PLUGIN_DIR / "src" / "components" / "Config.vue").read_text(
            encoding="utf-8"
        )

        self.assertIn('nav class="dm-nav"', config_source)
        self.assertIn('nav class="dm-nav-list py-2"', config_source)
        self.assertIn(".dm-nav-list { width: 100%; }", config_source)
        self.assertIn("@media (max-width: 760px)", config_source)
        self.assertIn("overflow-x: auto; overflow-y: hidden; scrollbar-width: none;", config_source)
        self.assertIn(".dm-nav::-webkit-scrollbar { display: none; }", config_source)
        self.assertIn(
            ".dm-nav-list { display: flex; flex-wrap: nowrap; gap: 6px; min-width: max-content; padding: 8px 12px !important; }",
            config_source,
        )
        self.assertIn(
            ".dm-nav-item { flex: 0 0 auto; min-width: 96px; margin: 0; padding-inline: 10px; }",
            config_source,
        )
        self.assertIn(
            ".dm-nav-item :deep(.v-list-item-title) { white-space: nowrap; }",
            config_source,
        )
        self.assertIn(
            ".dm-subtabs { flex-wrap: nowrap; overflow-x: auto; overflow-y: hidden; scrollbar-width: none; padding: 6px 12px; }",
            config_source,
        )
        self.assertIn(".dm-subtabs::-webkit-scrollbar { display: none; }", config_source)
        self.assertIn(".dm-subtab { flex: 0 0 auto; padding: 6px 12px; }", config_source)

    def test_diagnostics_reports_transmission_rename_capability(self) -> None:
        diagnostics_source = (PLUGIN_DIR / "modules" / "diagnostics.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('"种子重命名"', diagnostics_source)
        self.assertIn('to_service.get("type") == "transmission"', diagnostics_source)
        self.assertIn("不支持 Transmission", diagnostics_source)


if __name__ == "__main__":
    unittest.main()
