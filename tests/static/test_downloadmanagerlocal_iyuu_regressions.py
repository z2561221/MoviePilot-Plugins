import importlib.util
import json
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"
IYUU_SOURCE = PLUGIN_DIR / "service" / "iyuu.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_qbittorrent_labels_are_read_from_tags_not_category():
    adapter = _load_module(PLUGIN_DIR / "utils" / "torrent_adapter.py", "torrent_adapter")

    labels = adapter.get_label(
        {"tags": "MoviePilot, 已整理, 🌱铺种", "category": "剧集/国产剧"},
        "qbittorrent",
    )

    assert labels == ["MoviePilot", "已整理", "🌱铺种"]


def test_iyuu_successful_seed_is_added_to_success_cache():
    source = IYUU_SOURCE.read_text(encoding="utf-8")

    assert "append_iyuu_cache(plugin._iyuu_success_caches, seed.get(\"info_hash\"))" in source


def test_iyuu_rejects_html_content_before_adding_to_downloader():
    source = IYUU_SOURCE.read_text(encoding="utf-8")

    assert "is_torrent_content(content)" in source
    assert "下载到的内容不是有效 torrent 文件" in source


def test_downloadmanagerlocal_runtime_version_matches_market_metadata():
    package = json.loads((REPO / "package.v2.json").read_text(encoding="utf-8"))
    plugin_meta = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'plugin_version\s*=\s*"([^"]+)"', init_source)

    assert match
    assert match.group(1) == package["DownloadManagerLocal"]["version"] == plugin_meta["version"]
