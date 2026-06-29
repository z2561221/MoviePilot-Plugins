from pathlib import Path
import unittest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
CONFIG_VUE = PLUGIN_DIR / "src" / "components" / "Config.vue"
DIST_ASSETS = PLUGIN_DIR / "dist" / "assets"


def _compact_css(text: str) -> str:
    return "".join(text.split())


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

        config_css_files = list(DIST_ASSETS.glob("__federation_expose_Config-*.css"))
        self.assertEqual(len(config_css_files), 1)
        compact_css = _compact_css(config_css_files[0].read_text(encoding="utf-8"))
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


if __name__ == "__main__":
    unittest.main()
