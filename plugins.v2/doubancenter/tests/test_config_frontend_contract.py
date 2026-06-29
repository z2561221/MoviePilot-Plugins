from pathlib import Path
import unittest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
CONFIG_VUE = PLUGIN_DIR / "src" / "components" / "Config.vue"


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


if __name__ == "__main__":
    unittest.main()
