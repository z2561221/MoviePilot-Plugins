import json
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


def test_rank_subscribe_buttons_use_native_subscribe_dialog_with_fallback():
    for expose_name in ("Dashboard", "Page"):
        script = _read_exposed_asset(expose_name)

        assert "nativeSubscribe" in script
        assert "resolve_media" in script
        assert "props.nativeSubscribe" in script
        assert "subscribeViaNativeDialog" in script
        assert "await subscribeRankItem(rk, item)" in script


def test_rank_dialog_actions_include_equal_width_tmdb_button():
    for expose_name in ("Dashboard", "Page"):
        script = _read_exposed_asset(expose_name)

        assert "function doOpenTmdb()" in script
        assert "https://www.themoviedb.org/movie/" in script
        assert "https://www.themoviedb.org/tv/" in script
        assert "_createTextVNode(\"TMDB\"" in script
        assert "class: \"dc-dialog-action text-none\"" in script
        assert "\"disabled\": !dialogItem.value?.item?.tmdbid && !dialogItem.value?.item?.tmdb_id" in script


def test_rank_dialog_source_button_uses_douban_and_bangumi_brand_colors():
    for expose_name in ("Dashboard", "Page"):
        script = _read_exposed_asset(expose_name)

        assert "color: \"info\"" in script
        assert "function sourceButtonColor()" in script
        assert "return '#08B810'" in script
        assert "return '#F838A0'" in script
        assert "color: sourceButtonColor()" in script


def test_doubancenter_native_subscribe_release_version_is_consistent():
    plugin_json = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    package_json = json.loads((ROOT / "package.v2.json").read_text(encoding="utf-8"))
    init_py = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")

    assert plugin_json["version"] == "1.2.4"
    assert plugin_json["history"]["v1.2.4"].startswith("[1]")
    assert package_json["DoubanCenter"]["version"] == "1.2.4"
    assert package_json["DoubanCenter"]["history"]["v1.2.4"] == plugin_json["history"]["v1.2.4"]
    assert re.search(r'plugin_version\s*=\s*"1\.2\.4"', init_py)


def test_doubancenter_scheduled_task_refreshes_dashboard_rss_before_subscribe():
    init_py = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")

    assert re.search(r"def\s+__run_all\(self\):\s+feed\.run_scheduled\(self\)", init_py)


def test_doubancenter_observation_ui_replaces_anti_cheat_wording():
    config_script = _read_exposed_asset("Config")
    page_script = _read_exposed_asset("Page")
    init_py = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    dashboard_py = (PLUGIN_DIR / "dashboard.py").read_text(encoding="utf-8")

    assert "observe_rank_keys" in config_script
    for text in (config_script, init_py, dashboard_py):
        assert "anti_cheat_enabled" not in text
        assert "anti_cheat_min_vote" not in text
    assert "启用 TMDB 评分过滤" not in config_script
    assert "最低 TMDB 评分" not in config_script
    assert "观察榜单" in config_script
    assert "观察设置" in config_script
    assert "防刷榜设置" not in config_script
    assert "防刷日志" not in page_script
    assert "观察日志" in page_script
