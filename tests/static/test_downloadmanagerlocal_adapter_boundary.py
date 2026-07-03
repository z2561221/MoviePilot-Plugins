from __future__ import annotations

import ast
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"
ADAPTER_PATH = PLUGIN_DIR / "adapter" / "moviepilot.py"

RESTRICTED_IMPORTS = {
    "app.db.downloadhistory_oper": {"DownloadHistoryOper"},
    "app.db.site_oper": {"SiteOper"},
    "app.db.systemconfig_oper": {"SystemConfigOper"},
    "app.helper.downloader": {"DownloaderHelper"},
    "app.helper.sites": {"SitesHelper"},
    "app.helper.torrent": {"TorrentHelper"},
    "app.modules.qbittorrent": {"Qbittorrent"},
    "app.modules.transmission": {"Transmission"},
    "app.utils.http": {"RequestUtils"},
    "app.utils.string": {"StringUtils"},
}

BACKEND_FILES = [
    PLUGIN_DIR / "__init__.py",
    PLUGIN_DIR / "iyuu_helper.py",
    PLUGIN_DIR / "controller" / "handlers.py",
    PLUGIN_DIR / "service" / "config.py",
    PLUGIN_DIR / "modules" / "iyuu.py",
    PLUGIN_DIR / "modules" / "rename.py",
    PLUGIN_DIR / "modules" / "site_tag.py",
    PLUGIN_DIR / "modules" / "transfer.py",
]


def _restricted_import_hits(path: Path) -> list[str]:
    """返回非 adapter 文件中仍直连 MoviePilot 外部访问类的导入。"""
    module = ast.parse(path.read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom) and node.module in RESTRICTED_IMPORTS:
            restricted_names = RESTRICTED_IMPORTS[node.module]
            for alias in node.names:
                if alias.name in restricted_names or "*" in restricted_names:
                    hits.append(f"{node.module}.{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for module_name in RESTRICTED_IMPORTS:
                    if alias.name == module_name:
                        hits.append(alias.name)
    return hits


def test_downloadmanagerlocal_moviepilot_adapter_centralizes_external_imports():
    adapter_source = ADAPTER_PATH.read_text(encoding="utf-8")

    for module_name, names in RESTRICTED_IMPORTS.items():
        assert f"from {module_name} import " in adapter_source
        for name in names:
            assert name in adapter_source


def test_downloadmanagerlocal_backend_uses_adapter_for_external_access():
    leaks = {
        path.relative_to(REPO).as_posix(): _restricted_import_hits(path)
        for path in BACKEND_FILES
    }
    leaks = {path: hits for path, hits in leaks.items() if hits}

    assert leaks == {}
