import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = ROOT / "plugins.v2" / "localtoolkit"
CONFIG_SOURCE = PLUGIN_DIR / "frontend" / "src" / "components" / "Config.vue"
CONFIG_DIST = PLUGIN_DIR / "dist" / "assets" / "__federation_expose_Config-6Bf_KoOA.js"


def test_localtoolkit_overview_tab_uses_runtime_overview_label():
    source = CONFIG_SOURCE.read_text(encoding="utf-8")
    dist = CONFIG_DIST.read_text(encoding="utf-8")

    for text in (source, dist):
        assert "title: '运行总览'" in text
        assert "title: '总览'" not in text


def test_localtoolkit_release_version_is_consistent():
    package_json = json.loads((ROOT / "package.v2.json").read_text(encoding="utf-8"))
    plugin_json = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    init_py = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")

    assert package_json["LocalToolkit"]["version"] == "1.2.10"
    assert plugin_json["version"] == "1.2.10"
    assert package_json["LocalToolkit"]["history"]["v1.2.10"] == plugin_json["history"]["v1.2.10"]
    assert package_json["LocalToolkit"]["history"]["v1.2.10"].startswith("[1]")
    assert re.search(r'plugin_version\s*=\s*"1\.2\.10"', init_py)
