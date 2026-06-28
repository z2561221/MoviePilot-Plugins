import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = ROOT / "plugins.v2" / "doubancenter"
ASSETS_DIR = PLUGIN_DIR / "dist" / "assets"


def _read_exposed_asset(expose_name: str) -> str:
    remote_entry = (ASSETS_DIR / "remoteEntry.js").read_text(encoding="utf-8")
    match = re.search(
        rf'"\.\/{re.escape(expose_name)}":\(\)=>{{.*?__federation_import\(\'\.\/([^\']+)\'\)',
        remote_entry,
        flags=re.DOTALL,
    )
    assert match, f"{expose_name} asset is not exposed by remoteEntry.js"
    return (ASSETS_DIR / match.group(1)).read_text(encoding="utf-8")


def test_observation_rank_selector_precedes_days_field():
    config_script = _read_exposed_asset("Config")
    section_start = config_script.index("观察设置")
    rank_index = config_script.index('label: "观察榜单"', section_start)
    days_index = config_script.index('label: "观察期（天）"', section_start)

    assert rank_index < days_index
