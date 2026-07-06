from pathlib import Path
import re
import unittest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
CONFIG_VUE = PLUGIN_DIR / "src" / "components" / "Config.vue"
PAGE_VUE = PLUGIN_DIR / "src" / "components" / "Page.vue"
DASHBOARD_VUE = PLUGIN_DIR / "src" / "components" / "Dashboard.vue"
DIST_ASSETS = PLUGIN_DIR / "dist" / "assets"
OVERVIEW_SERVICE = PLUGIN_DIR / "service" / "dashboard_overview.py"


def _compact_css(text: str) -> str:
    return "".join(text.split())


def _active_css_text(expose_name: str) -> str:
    remote_entry = DIST_ASSETS / "remoteEntry.js"
    remote_text = remote_entry.read_text(encoding="utf-8")
    match = re.search(rf'dynamicLoadingCss\(\["([^"]+)"\], false, \'{expose_name}\'\)', remote_text)
    if not match:
        raise AssertionError(f"missing active CSS mapping for {expose_name}")
    return (remote_entry.parent / match.group(1)).read_text(encoding="utf-8")


class ConfigFrontendContractTest(unittest.TestCase):
    def test_config_vue_hides_backend_cleaned_legacy_fields(self):
        text = CONFIG_VUE.read_text(encoding="utf-8")

        forbidden_fragments = [
            "const regionOptions",
            "const genreOptions",
            "const resolutionOptions",
            'v-model="form.region_filters"',
            'v-model="form.genre_filters"',
            'v-model="form.resolution_filters"',
            'v-model="form.custom_rss_addrs"',
            "自定义 RSS 地址",
        ]
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, text)

        self.assertIn("region_filters: []", text)
        self.assertIn("genre_filters: []", text)
        self.assertIn("resolution_filters: []", text)
        self.assertIn("custom_rss_addrs: ''", text)

    def test_config_vue_uses_backend_rank_count_default(self):
        text = CONFIG_VUE.read_text(encoding="utf-8")

        self.assertNotIn("count: 10", text)
        self.assertGreaterEqual(text.count("count: 0"), 6)
        self.assertIn('v-model.number="form.rank_configs[rd.key].count" type="number" min="0"', text)

    def test_rank_list_uses_compact_grid_style(self):
        text = CONFIG_VUE.read_text(encoding="utf-8")

        self.assertIn(".dc-rank-list-1col { display: flex; flex-direction: column; gap: 4px; }", text)
        self.assertIn(
            ".dc-rank-card { display: grid; grid-template-columns: minmax(150px, 220px) minmax(0, 1fr);",
            text,
        )
        self.assertIn("align-items: center; column-gap: 12px; min-height: 42px;", text)
        self.assertIn("border-radius: 8px; padding: 5px 10px;", text)
        self.assertIn(".dc-rank-card-header { margin-bottom: 0; min-width: 0; }", text)
        self.assertIn(
            ".dc-rank-card-body { display: grid; grid-template-columns: repeat(auto-fit, minmax(142px, auto));",
            text,
        )
        self.assertIn("@media (max-width: 760px)", text)
        self.assertIn(".dc-rank-card { grid-template-columns: 1fr; row-gap: 4px; }", text)
        self.assertIn(".dc-rank-card-body { grid-template-columns: repeat(2, minmax(142px, auto)); }", text)

        compact_css = _compact_css(_active_css_text("./Config"))
        self.assertIn("gap:4px", compact_css)
        self.assertIn("display:grid;grid-template-columns:minmax(150px,220px)minmax(0,1fr)", compact_css)
        self.assertIn("border-radius:8px;padding:5px10px", compact_css)
        self.assertIn("grid-template-columns:repeat(auto-fit,minmax(142px,auto))", compact_css)
        self.assertIn("@media(max-width:760px)", compact_css)
        self.assertIn("grid-template-columns:repeat(2,minmax(142px,auto))", compact_css)

    def test_dist_assets_do_not_keep_unreachable_old_chunks(self):
        stale_assets = [
            "__federation_expose_Dashboard-5Zx_46S8.js",
            "__federation_expose_Dashboard-CdVplNao.css",
            "__federation_expose_Page-C8136Oog.js",
            "__federation_expose_Page-DvJzpI8-.css",
            "__federation_shared_vuetify",
        ]

        for asset in stale_assets:
            self.assertFalse((DIST_ASSETS / asset).exists(), asset)

    def test_page_source_keeps_runtime_detail_behaviour(self):
        text = PAGE_VUE.read_text(encoding="utf-8")

        required_fragments = [
            "nativeSubscribe",
            "blacklistEntries",
            "pending_observations",
            "rank_history",
            "archive_records",
            "delete_observation",
            "delete_subscribe_history",
            "delete_anti_cheat_log",
            "restore_archive",
            "delete_archive",
            "resolve_media",
            "bangumi_id",
            "subscribeViaNativeDialog",
        ]
        for fragment in required_fragments:
            self.assertIn(fragment, text)

        self.assertIn("!['黑名拦截', '黑名单关键词'].includes(log.reason)", text)
        self.assertIn("['黑名拦截', '黑名单关键词'].includes(log.reason)", text)
        self.assertNotIn("if (c) cheatLogs.value = c", text)

    def test_dashboard_source_keeps_native_subscribe_behaviour(self):
        text = DASHBOARD_VUE.read_text(encoding="utf-8")

        required_fragments = [
            "nativeSubscribe",
            "resolve_media",
            "bangumi_id",
            "subscribeViaNativeDialog",
            "postPluginApi(props.api, `subscribe?",
            "showActionDialog",
            "dc-rank-wish",
        ]
        for fragment in required_fragments:
            self.assertIn(fragment, text)

        self.assertNotIn("getPluginApi(props.api, `subscribe?", text)

    def test_folio_sync_wish_tabs_and_controls_contract(self):
        """豆瓣时间配置页会先显示同步想看，再显示同步观影。"""
        text = CONFIG_VUE.read_text(encoding="utf-8")

        self.assertIn("wish_enabled: false", text)
        self.assertIn("wish_cron: '*/30 * * * *'", text)
        self.assertIn("wish_user: ''", text)
        self.assertIn("wish_notify: false", text)
        self.assertIn("wish_onlyonce: false", text)
        self.assertIn("wish_days: 7", text)
        self.assertIn("title: '同步想看'", text)
        self.assertIn("title: '同步观影'", text)
        self.assertLess(text.index("title: '同步想看'"), text.index("title: '同步观影'"))
        self.assertNotIn("title: '同步设置'", text)

        required_controls = [
            'v-model="form.wish_enabled"',
            'v-model="form.wish_cron"',
            'v-model="form.wish_user"',
            'v-model="form.wish_notify"',
            'v-model="form.wish_onlyonce"',
            'v-model.number="form.wish_days"',
            "立即运行一次",
            "overview?.cards?.folio?.wish",
            "通过豆瓣动态 feed 同步",
        ]
        for fragment in required_controls:
            self.assertIn(fragment, text)

    def test_overview_flow_labels_use_wish_sync_contract(self):
        """运行链路使用统一的同步想看文案。"""
        text = OVERVIEW_SERVICE.read_text(encoding="utf-8")

        required_labels = [
            "同步想看",
            "周期触发",
            "读取想看",
            "新增入队",
            "媒体识别",
            "创建订阅",
            "同步观影",
            "媒体事件",
            "条目识别",
            "豆瓣同步",
            "写入时间",
        ]
        for label in required_labels:
            self.assertIn(label, text)

    def test_overview_and_rank_header_visual_contract(self):
        config_text = CONFIG_VUE.read_text(encoding="utf-8")
        dashboard_text = DASHBOARD_VUE.read_text(encoding="utf-8")
        page_text = PAGE_VUE.read_text(encoding="utf-8")

        overview_start = config_text.find('<span>运行链路</span>')
        self.assertGreaterEqual(overview_start, 0)
        overview_end = config_text.find('<div class="dc-flow">', overview_start)
        self.assertGreater(overview_end, overview_start)
        overview_header = config_text[overview_start:overview_end]
        self.assertNotIn('icon="mdi-refresh"', overview_header)
        self.assertNotIn('@click="loadOverview"', overview_header)

        bright_rank_colors = [
            "#f97316",
            "#06b6d4",
            "#eab308",
            "#ef4444",
            "#ec4899",
            "#8b5cf6",
        ]
        for text in (dashboard_text, page_text):
            self.assertIn(":style=\"rankIconStyle(", text)
            for color in bright_rank_colors:
                self.assertIn(color, text)
            self.assertNotIn("#fb923c", text)
            self.assertNotIn("#d97706", text)
            self.assertNotIn(":color=\"rankColors[rk] || 'primary'\"", text)
            self.assertNotIn(":color=\"rankColors[key] || 'primary'\"", text)

        self.assertIn("function rankChipStyle(key)", page_text)
        self.assertIn(":style=\"rankChipStyle(item.rank_key)\"", page_text)
        self.assertIn(":style=\"rankChipStyle(log.rank_key)\"", page_text)
        self.assertIn("class=\"dc-rank-chip mr-1\"", page_text)
        self.assertNotIn(":color=\"rankColors[item.rank_key] || 'primary'\"", page_text)
        self.assertNotIn(":color=\"rankColors[log.rank_key] || 'primary'\"", page_text)

    def test_page_source_keeps_current_detail_layout_contract(self):
        text = PAGE_VUE.read_text(encoding="utf-8")

        required_fragments = [
            'class="dc-section dc-section--archive"',
            'class="dc-section dc-section--stats"',
            'class="dc-section dc-section--rank"',
            'class="dc-section dc-section--blacklist"',
            'class="dc-section dc-section--observe"',
            'class="dc-section dc-section--history"',
            'class="dc-section dc-section--logs"',
            ".dc-section--archive {",
            ".dc-section--rank {",
            ".dc-section--stats {",
            "grid-column: 1 / -1",
        ]
        for fragment in required_fragments:
            self.assertIn(fragment, text)

    def test_page_source_keeps_archive_rows_full_width(self):
        text = PAGE_VUE.read_text(encoding="utf-8")

        self.assertIn('class="dc-history-row dc-archive-row"', text)
        self.assertIn(".dc-archive-row {", text)
        self.assertIn("auto minmax(0, 1fr) auto auto", text)

    def test_rank_action_dialog_keeps_current_visual_contract(self):
        for path in (PAGE_VUE, DASHBOARD_VUE):
            text = path.read_text(encoding="utf-8")

            self.assertIn('class="dc-action-dialog"', text, path.name)
            self.assertIn('size="36" rounded="md"', text, path.name)
            self.assertIn("dialogPoster", text, path.name)
            self.assertIn("dc-dialog-action text-none", text, path.name)
            self.assertIn('prepend-icon="mdi-plus-circle-outline"', text, path.name)
            self.assertIn('prepend-icon="mdi-movie-open-outline"', text, path.name)
            self.assertIn(".dc-dialog-action {", text, path.name)


if __name__ == "__main__":
    unittest.main()
