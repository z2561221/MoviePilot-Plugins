from pathlib import Path
import re
import unittest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
CONFIG_VUE = PLUGIN_DIR / "src" / "components" / "Config.vue"
PAGE_VUE = PLUGIN_DIR / "src" / "components" / "Page.vue"
APP_PAGE_VUE = PLUGIN_DIR / "src" / "components" / "AppPage.vue"
DASHBOARD_VUE = PLUGIN_DIR / "src" / "components" / "Dashboard.vue"
API_JS = PLUGIN_DIR / "src" / "components" / "api.js"
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

        self.assertIn("const regionOptions", text)
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
        self.assertIn(".dc-rank-card-body { grid-template-columns: 1fr; }", text)

        compact_css = _compact_css(_active_css_text("./Config"))
        self.assertIn("gap:4px", compact_css)
        self.assertIn("display:grid;grid-template-columns:minmax(150px,220px)minmax(0,1fr)", compact_css)
        self.assertIn("border-radius:8px;padding:5px10px", compact_css)
        self.assertIn("grid-template-columns:repeat(auto-fit,minmax(142px,auto))", compact_css)
        self.assertIn("@media(max-width:760px)", compact_css)
        self.assertIn("grid-template-columns:1fr", compact_css)

    def test_config_normalizes_legacy_null_nested_config(self):
        """旧配置中的空嵌套对象不应导致 Vue 设置页白屏。"""
        text = CONFIG_VUE.read_text(encoding="utf-8")

        required_fragments = [
            "function normalizeInitialConfig",
            "m.rank_configs && typeof m.rank_configs === 'object' && !Array.isArray(m.rank_configs)",
            "m.rank_configs = {}",
            "form.rank_configs[rd.key]",
        ]
        for fragment in required_fragments:
            self.assertIn(fragment, text)

    def test_mobile_config_dialog_matches_download_center_shell(self):
        """移动端设置页外壳应与下载中心保持一致。"""
        text = CONFIG_VUE.read_text(encoding="utf-8")

        required_fragments = [
            ".dc-config { width: min(100%, calc(100vw - 16px)); padding: 4px; }",
            ".dc-card { height: min(860px, calc(100dvh - 16px)); }",
            ".dc-rank-card-body { grid-template-columns: 1fr; }",
            ".dc-rank-field { grid-template-columns: 42px minmax(0, 1fr); }",
            ".dc-rank-input { width: 100%; max-width: none; }",
        ]
        for fragment in required_fragments:
            self.assertIn(fragment, text)

        compact_css = _compact_css(_active_css_text("./Config"))
        required_css_fragments = [
            ".dc-config[data-v-",
            "width:min(100%,calc(100vw-16px));padding:4px",
            "height:min(860px,calc(100dvh-16px))",
            ".dc-rank-card-body[data-v-",
            "grid-template-columns:1fr",
            ".dc-rank-field[data-v-",
            "grid-template-columns:42pxminmax(0,1fr)",
            ".dc-rank-input[data-v-",
            "width:100%;max-width:none",
        ]
        for fragment in required_css_fragments:
            self.assertIn(fragment, compact_css)

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

    def test_discovery_page_switch_reuses_detail_page(self):
        """发现页开关应暴露全页组件，并复用详情页而非复制业务逻辑。"""
        config_text = CONFIG_VUE.read_text(encoding="utf-8")
        page_text = PAGE_VUE.read_text(encoding="utf-8")
        app_page_text = APP_PAGE_VUE.read_text(encoding="utf-8")
        remote_text = (DIST_ASSETS / "remoteEntry.js").read_text(encoding="utf-8")

        self.assertIn("discovery_page_enabled: false", config_text)
        self.assertIn('v-model="form.discovery_page_enabled"', config_text)
        self.assertIn('label="开启发现页"', config_text)
        self.assertIn("保存并刷新 MP 页面", config_text)
        self.assertIn("import Page from './Page.vue'", app_page_text)
        self.assertIn("nativeSubscribe: { type: Function, default: null }", app_page_text)
        self.assertIn(':api="props.api"', app_page_text)
        self.assertIn(':native-subscribe="props.nativeSubscribe"', app_page_text)
        self.assertIn("getPluginConfig", app_page_text)
        self.assertIn("savePluginConfig", app_page_text)
        self.assertIn('@switch="openSettings"', app_page_text)
        self.assertIn("<VSnackbar", app_page_text)
        self.assertIn("appPage: { type: Boolean, default: false }", page_text)
        self.assertIn("showSettings: { type: Boolean, default: false }", page_text)
        self.assertIn('v-if="props.showSettings || !props.appPage"', page_text)
        self.assertIn('"./AppPage"', remote_text)
        app_page_css = re.search(
            r'dynamicLoadingCss\(\[([^\]]+)\], false, \'\./AppPage\'\)',
            remote_text,
        )
        self.assertIsNotNone(app_page_css)
        self.assertIn("__federation_expose_AppPage-", app_page_css.group(1))
        self.assertIn("__federation_expose_Page-", app_page_css.group(1))

    def test_rank_rows_share_regions_and_custom_source_contract(self):
        text = CONFIG_VUE.read_text(encoding="utf-8")

        self.assertIn("const regionOptions", text)
        self.assertIn('v-model="form.rank_configs[rd.key].regions"', text)
        self.assertIn("multiple chips", text)
        self.assertIn('VExpansionPanel title="数据源设置"', text)
        self.assertIn('v-model="rd.model.name"', text)
        self.assertIn('v-model="rd.model.route"', text)
        self.assertIn("function requestRemoveCustomRank", text)
        self.assertIn("class=\"dc-delete-rank\"", text)
        self.assertNotIn("customMediaTypes", text)
        self.assertNotIn("v-model=\"rd.media_type\"", text)
        self.assertIn("delete m.rank_configs[rd.key].media_type", text)
        self.assertIn("custom_ranks: (form.custom_ranks || []).map", text)

    def test_page_labels_douban_wish_subscription_stats(self):
        """详情页订阅统计应将豆瓣想看显示为独立分类。"""
        text = PAGE_VUE.read_text(encoding="utf-8")

        self.assertIn("douban_wish: '豆瓣想看'", text)
        self.assertIn("douban_wish: '#10b981'", text)

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

    def test_dashboard_initial_load_times_out_and_keeps_partial_data(self):
        """仪表盘首次挂载应限时并发请求，且允许核心数据先于时间线收口。"""
        text = DASHBOARD_VUE.read_text(encoding="utf-8")
        load_block = re.search(r"async function load\(\) \{.*?^\}", text, re.MULTILINE | re.DOTALL)

        self.assertIsNotNone(load_block)
        load_text = load_block.group(0)
        self.assertIn("const folioRequest = getPluginApi(props.api, 'folio_data', { timeoutMs: INITIAL_LOAD_TIMEOUT_MS })", load_text)
        self.assertIn("getPluginApi(props.api, 'config', { timeoutMs: INITIAL_LOAD_TIMEOUT_MS })", load_text)
        self.assertIn("getPluginApi(props.api, 'rank_history', { timeoutMs: INITIAL_LOAD_TIMEOUT_MS })", load_text)
        self.assertIn("await Promise.allSettled(coreRequests.map(item => item.run))", load_text)
        self.assertIn("await Promise.allSettled([folioRequest])", load_text)
        self.assertIn("loading.value = false", load_text)
        self.assertIn("loadError.value = errors.length", load_text)
        self.assertNotIn("await Promise.all([", load_text)

        self.assertIn('<VProgressLinear v-if="loading || folioLoading"', text)
        self.assertIn('@click="load">重试</VBtn>', text)
        self.assertNotIn('<VProgressCircular v-if="loading"', text)

    def test_discovery_initial_load_times_out_and_keeps_partial_data(self):
        """发现页请求应独立收口，失败时保留成功数据并提供重试。"""
        page_text = PAGE_VUE.read_text(encoding="utf-8")
        api_text = API_JS.read_text(encoding="utf-8")
        load_block = re.search(r"async function loadAll\(\) \{.*?^\}", page_text, re.MULTILINE | re.DOTALL)

        self.assertIsNotNone(load_block)
        load_text = load_block.group(0)
        self.assertIn("await Promise.allSettled(requests.map(async request =>", load_text)
        self.assertIn("{ timeoutMs: INITIAL_LOAD_TIMEOUT_MS }", load_text)
        self.assertIn("request.apply(value)", load_text)
        self.assertIn("loadError.value = failed.length", load_text)
        self.assertNotIn("archive_records", load_text)
        self.assertNotIn("await Promise.all([", load_text)

        self.assertIn('<VProgressLinear v-if="loading"', page_text)
        self.assertIn("archivePage ? loadArchive() : loadAll()", page_text)
        self.assertNotIn('<VProgressCircular v-if="loading"', page_text)
        self.assertIn("error.code = 'PLUGIN_API_TIMEOUT'", api_text)
        self.assertIn("return await Promise.race([request, timeout])", api_text)

    def test_small_posters_share_w200_url_conversion_and_lazy_loading(self):
        """仪表盘与详情页小海报应统一降到 w200 并保持 VImg 懒加载。"""
        api_text = API_JS.read_text(encoding="utf-8")
        dashboard_text = DASHBOARD_VUE.read_text(encoding="utf-8")
        page_text = PAGE_VUE.read_text(encoding="utf-8")

        self.assertIn("export function toPosterThumbnail(url)", api_text)
        self.assertIn("replace(/\\/(?:original|w500)\\//, '/w200/')", api_text)
        self.assertNotIn("data:image", api_text)
        self.assertNotIn(".replace('/original/', '/w200/')", dashboard_text)
        self.assertGreaterEqual(dashboard_text.count("toPosterThumbnail("), 3)
        self.assertGreaterEqual(page_text.count("toPosterThumbnail("), 5)
        self.assertIn(':src="toPosterThumbnail(item.poster)"', dashboard_text)
        self.assertNotIn(':src="item.poster"', page_text)
        self.assertNotIn(':src="log.poster"', page_text)
        self.assertNotIn(" eager", dashboard_text)
        self.assertNotIn(" eager", page_text)

    def test_detail_history_posters_use_compact_rectangular_style(self):
        """归档、订阅历史和观察日志海报应统一为紧凑矩形。"""
        text = PAGE_VUE.read_text(encoding="utf-8")

        self.assertEqual(
            text.count('<VAvatar rounded="sm" class="dc-history-poster'),
            3,
        )
        self.assertIn(
            ".dc-history-poster { flex: 0 0 24px !important; width: 24px !important; height: 36px !important;",
            text,
        )
        self.assertNotIn('<VAvatar size="28" rounded="sm" class="dc-history-poster', text)

    def test_rank_posters_reuse_detail_rectangular_size(self):
        """仪表盘与详情榜单应复用 24×36 矩形海报规格。"""
        dashboard_text = DASHBOARD_VUE.read_text(encoding="utf-8")
        page_text = PAGE_VUE.read_text(encoding="utf-8")

        self.assertIn('<VAvatar rounded="sm" class="dc-rank-poster">', dashboard_text)
        self.assertIn('<VAvatar rounded="sm" class="dc-rank-poster">', page_text)
        self.assertNotIn('<VAvatar size="16" class="dc-rank-poster">', dashboard_text)
        self.assertNotIn('<VAvatar size="20" rounded="sm" class="dc-rank-poster">', page_text)
        self.assertIn(".dc-rank-row { display: flex; align-items: center; gap: 3px; min-height: 40px;", dashboard_text)
        self.assertIn(".dc-rank-row { display: flex; align-items: center; gap: 4px; min-width: 0; min-height: 42px;", page_text)
        for text in (dashboard_text, page_text):
            self.assertIn(
                ".dc-rank-poster { flex: 0 0 24px !important; width: 24px !important; height: 36px !important;",
                text,
            )

        dashboard_css = _compact_css(_active_css_text("./Dashboard"))
        page_css = _compact_css(_active_css_text("./Page"))
        for css in (dashboard_css, page_css):
            self.assertIn("flex:0024px!important;width:24px!important;height:36px!important", css)
            self.assertIn("min-width:24px;min-height:36px;aspect-ratio:2/3", css)
        self.assertIn("min-height:40px", dashboard_css)
        self.assertIn("min-height:42px", page_css)

    def test_rank_titles_wrap_to_two_lines(self):
        """仪表盘与详情榜单长标题应自适应换行并限制为两行。"""
        for source_path, expose_name in (
            (DASHBOARD_VUE, "./Dashboard"),
            (PAGE_VUE, "./Page"),
        ):
            text = source_path.read_text(encoding="utf-8")
            match = re.search(r"\.dc-rank-title \{([^}]+)\}", text)
            self.assertIsNotNone(match)
            title_css = _compact_css(match.group(1))
            self.assertIn("display:-webkit-box", title_css)
            self.assertIn("-webkit-box-orient:vertical", title_css)
            self.assertIn("-webkit-line-clamp:2", title_css)
            self.assertIn("white-space:normal", title_css)
            self.assertIn("overflow-wrap:anywhere", title_css)
            self.assertNotIn("white-space:nowrap", title_css)

            built_css = _compact_css(_active_css_text(expose_name))
            self.assertIn("display:-webkit-box", built_css)
            self.assertIn("-webkit-box-orient:vertical", built_css)
            self.assertIn("-webkit-line-clamp:2", built_css)
            self.assertIn("white-space:normal", built_css)
            self.assertIn("overflow-wrap:anywhere", built_css)

    def test_dashboard_timeline_scroll_is_isolated_on_mobile(self):
        """追影时间线横滑不应带动榜单，月份组在移动端也保持单行。"""
        text = DASHBOARD_VUE.read_text(encoding="utf-8")

        required_fragments = [
            'class="dc-timeline-scroll"',
            'class="dc-timeline-months"',
            'class="dc-timeline-month"',
            ".dc-card { border-radius: 16px;",
            "max-width: 100%;",
            ".dc-rank-grid { display: grid;",
            "overflow-x: hidden;",
            ".dc-tl-cell { overflow: hidden;",
            ".dc-timeline-scroll {",
            "overflow-x: auto;",
            "overscroll-behavior-x: contain;",
            "touch-action: pan-x;",
            "scrollbar-width: none;",
            "-ms-overflow-style: none;",
            ".dc-timeline-scroll::-webkit-scrollbar { display: none; }",
            ".dc-timeline-months {",
            "flex-wrap: nowrap;",
            ".dc-timeline-month { flex: 0 0 auto;",
        ]
        for fragment in required_fragments:
            self.assertIn(fragment, text)

        self.assertNotIn('class="d-flex flex-wrap" style="gap: 8px"', text)

    def test_tmdb_actions_use_theme_adaptive_contrast_color(self):
        """TMDB 操作按钮不应继承宿主主题中偏淡的 info 色。"""
        for path in (PAGE_VUE, DASHBOARD_VUE):
            text = path.read_text(encoding="utf-8")

            self.assertIn(
                'class="dc-dialog-action dc-dialog-action--tmdb text-none"',
                text,
                path.name,
            )
            self.assertNotIn(
                'color="info" prepend-icon="mdi-movie-open-outline"',
                text,
                path.name,
            )
            self.assertIn(
                ".dc-dialog-action--tmdb {",
                text,
                path.name,
            )
            self.assertIn(
                "color: #0288d1 !important;",
                text,
                path.name,
            )
            self.assertIn(
                "color: color-mix(in srgb, #0288d1 78%, rgb(var(--v-theme-on-surface)) 22%) !important;",
                text,
                path.name,
            )

    def test_dashboard_timeline_display_options_are_removed_from_config_ui(self):
        """仪表显示不再提供豆瓣时间线显示数量设置。"""
        config_text = CONFIG_VUE.read_text(encoding="utf-8")
        dashboard_text = DASHBOARD_VUE.read_text(encoding="utf-8")

        removed_fragments = [
            "豆瓣时间线显示设置",
            "大屏显示月份数",
            "大屏每月最多显示数",
            "小屏显示月份数",
            "小屏每月最多显示数",
            "folio_pc_month",
            "folio_pc_num",
            "folio_mobile_month",
            "folio_mobile_num",
        ]
        for fragment in removed_fragments:
            self.assertNotIn(fragment, config_text)

        self.assertNotIn("config.value?.folio_pc_month", dashboard_text)
        self.assertNotIn("config.value?.folio_pc_num", dashboard_text)
        self.assertIn("const TIMELINE_MONTH_LIMIT = 3", dashboard_text)
        self.assertIn("const TIMELINE_ITEM_LIMIT = 50", dashboard_text)

    def test_folio_sync_wish_tabs_and_controls_contract(self):
        """豆瓣时间配置页会先显示同步想看，再显示同步观影。"""
        text = CONFIG_VUE.read_text(encoding="utf-8")

        self.assertIn("wish_enabled: false", text)
        self.assertIn("wish_cron: '*/30 * * * *'", text)
        self.assertIn("wish_user: ''", text)
        self.assertIn("wish_notify: false", text)
        self.assertIn("wish_onlyonce: false", text)
        self.assertIn("wish_days: 7", text)
        self.assertIn("folio_exclude_live_tv: true", text)
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
            'v-model="form.folio_exclude_live_tv"',
            "排除电视直播源",
        ]
        for fragment in required_controls:
            self.assertIn(fragment, text)

    def test_overview_flow_labels_use_grouped_contract(self):
        """运行链路使用榜单、豆瓣时间、公共归档三组结构。"""
        text = OVERVIEW_SERVICE.read_text(encoding="utf-8")

        required_labels = [
            "榜单订阅",
            "豆瓣时间",
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
            "公共归档",
            "条目删除",
            "归档入库",
            "手动恢复",
            "记录清理",
        ]
        for label in required_labels:
            self.assertIn(label, text)

    def test_overview_flow_frontend_supports_nested_flows(self):
        """运行链路前端支持豆瓣时间下的子链路渲染。"""
        text = CONFIG_VUE.read_text(encoding="utf-8")

        required_fragments = [
            "flow.flows",
            "subFlow in flow.flows",
            "dc-flow-sub",
            "subFlow.steps",
        ]
        for fragment in required_fragments:
            self.assertIn(fragment, text)

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

    def test_source_action_uses_real_href_and_douban_detail_fallback(self):
        """豆瓣来源按钮只能指向条目详情或标题搜索，不能冒充榜单集合。"""
        source_text = (PLUGIN_DIR / "src" / "components" / "source.js").read_text(encoding="utf-8")
        for path in (PAGE_VUE, DASHBOARD_VUE):
            text = path.read_text(encoding="utf-8")
            self.assertIn(':href="sourceButtonHref() || undefined"', text, path.name)
            self.assertIn('@click="openSource"', text, path.name)
            self.assertIn('target="_blank"', text, path.name)
            self.assertIn('rel="noopener noreferrer"', text, path.name)
            self.assertIn('return sourceButtonAppUrl() || webUrl', text, path.name)
            self.assertNotIn("doOpenSource", text, path.name)

        for fragment in (
            "function routePath(value)",
            "function isDoubanRoute(value)",
            "function doubanSearchUrl(item)",
            "function isCustomRank(rankKey, config)",
            "https://movie.douban.com/subject/",
            "const year = stringValue(item?.year)",
            "function isDoubanSubjectLink(value)",
            "export function doubanDispatchUrl(subjectId, mediaType = 'tv')",
            "appUrl: doubanAppUrl(rankKey, item, config)",
        ):
            self.assertIn(fragment, source_text)
        self.assertNotIn("function doubanCollectionUrl", source_text)
        self.assertNotIn("subject_collection/", source_text)

        built_source = next(DIST_ASSETS.glob("source-*.js"), None)
        self.assertIsNotNone(built_source)
        built_text = built_source.read_text(encoding="utf-8")
        self.assertIn("function routePath(value)", built_text)
        self.assertIn("https://movie.douban.com/subject/", built_text)
        self.assertNotIn("function doubanCollectionUrl", built_text)

    def test_mobile_layout_uses_single_column_page_and_dispatch_timeline(self):
        """移动端榜单保持可读单列，时间线继续使用豆瓣 App dispatch。"""
        page_text = PAGE_VUE.read_text(encoding="utf-8")
        dashboard_text = DASHBOARD_VUE.read_text(encoding="utf-8")
        self.assertIn(".dc-rank-grid { grid-template-columns: minmax(0, 1fr);", page_text)
        self.assertIn(".dc-toolbar-action", page_text)
        self.assertIn(".dc-dialog-actions", page_text)
        self.assertIn(":href=\"doubanDispatchUrl(item.subject_id, item.type)\"", dashboard_text)
        self.assertIn(".dc-dialog-actions", dashboard_text)


if __name__ == "__main__":
    unittest.main()
