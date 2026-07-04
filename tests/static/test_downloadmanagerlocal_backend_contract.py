from __future__ import annotations

import ast
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"
FRONTEND_DIR = PLUGIN_DIR / "frontend"
DIST_ASSETS_DIR = PLUGIN_DIR / "dist" / "assets"

FORBIDDEN_UI_PATHS = [
    "plugins.v2/downloadmanagerlocal/frontend",
    "plugins.v2/downloadmanagerlocal/dist",
]

LEGACY_FRONTEND_PATHS = [
    PLUGIN_DIR / "src",
    PLUGIN_DIR / "index.html",
    PLUGIN_DIR / "vite.config.js",
    PLUGIN_DIR / "package.json",
    PLUGIN_DIR / "package-lock.json",
    PLUGIN_DIR / "pnpm-lock.yaml",
]

EXPECTED_FRONTEND_FILES = [
    FRONTEND_DIR / "index.html",
    FRONTEND_DIR / "vite.config.js",
    FRONTEND_DIR / "package.json",
    FRONTEND_DIR / "package-lock.json",
    FRONTEND_DIR / "pnpm-lock.yaml",
    FRONTEND_DIR / "src" / "components" / "Config.vue",
    FRONTEND_DIR / "src" / "components" / "Page.vue",
    FRONTEND_DIR / "src" / "components" / "api.js",
]

EXPECTED_ROUTES = {
    "/downloaders": {"auth": "bear", "methods": ("GET",), "summary": "获取下载器列表"},
    "/rename_history": {"auth": "bear", "methods": ("GET",), "summary": "获取重命名历史"},
    "/overview": {"auth": "bear", "methods": ("GET",), "summary": "获取下载中心总览"},
    "/diagnostics": {"auth": "bear", "methods": ("GET",), "summary": "获取诊断信息"},
    "/retry_renames": {"auth": "bear", "methods": ("POST",), "summary": "一键补刀重命名"},
    "/retry_rename": {"auth": "bear", "methods": ("POST",), "summary": "单条补刀重命名"},
    "/delete_rename_history": {"auth": "bear", "methods": ("POST",), "summary": "删除重命名历史记录"},
    "/rename_archive": {"auth": "bear", "methods": ("GET",), "summary": "获取补刀归档记录"},
    "/restore_rename_archive": {"auth": "bear", "methods": ("POST",), "summary": "恢复补刀归档记录"},
    "/delete_rename_archive": {"auth": "bear", "methods": ("POST",), "summary": "删除补刀归档记录"},
    "/recovery_torrent": {"auth": "bear", "methods": ("POST",), "summary": "恢复种子原始名称"},
    "/sites": {"auth": "bear", "methods": ("GET",), "summary": "获取站点列表（用于辅种站点选择）"},
}


def _literal(node: ast.AST):
    """解析 API 路由元数据中的字面量。"""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return tuple(_literal(item) for item in node.elts)
    raise AssertionError(f"unsupported literal node: {ast.dump(node)}")


def _route_metadata() -> dict:
    """从 API 路由构造器静态提取路由元数据。"""
    source = (PLUGIN_DIR / "controller" / "api.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    route_builder = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_api_routes"
    )
    return_node = next(
        node
        for node in ast.walk(route_builder)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.List)
    )

    routes = {}
    for item in return_node.value.elts:
        assert isinstance(item, ast.Dict)
        values = {}
        for key_node, value_node in zip(item.keys, item.values):
            if not isinstance(key_node, ast.Constant):
                continue
            if key_node.value in {"path", "auth", "methods", "summary"}:
                values[key_node.value] = _literal(value_node)
        routes[values["path"]] = {
            "auth": values["auth"],
            "methods": values["methods"],
            "summary": values["summary"],
        }
    return routes


def _downloadmanagerlocal_class() -> ast.ClassDef:
    """返回下载中心插件主类 AST。"""
    source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    return next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "DownloadManagerLocal"
    )


def _git_diff_names(*args: str) -> list[str]:
    """返回指定 git diff 范围中的文件清单。"""
    result = subprocess.run(
        ["git", "diff", "--name-only", *args, "--", *FORBIDDEN_UI_PATHS],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_downloadmanagerlocal_api_routes_keep_frontend_contract():
    routes = _route_metadata()

    assert routes == EXPECTED_ROUTES


def test_downloadmanagerlocal_get_api_delegates_route_builder():
    plugin_class = _downloadmanagerlocal_class()
    get_api = next(
        node
        for node in plugin_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "get_api"
    )
    called_names = {
        node.func.id
        for node in ast.walk(get_api)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "_build_api_routes_impl" in called_names


def test_downloadmanagerlocal_api_handlers_keep_compatibility_shim():
    shim_source = (PLUGIN_DIR / "api.py").read_text(encoding="utf-8")
    handler_source = (PLUGIN_DIR / "controller" / "handlers.py").read_text(encoding="utf-8")

    assert "from .controller.handlers import" in shim_source
    assert "def api_overview(plugin):" in handler_source
    assert "def api_retry_rename(plugin, hash: str = \"\"):" in handler_source
    assert "def api_diagnostics(plugin):" in handler_source


def test_downloadmanagerlocal_init_plugin_delegates_lifecycle_initialization():
    plugin_class = _downloadmanagerlocal_class()
    init_plugin = next(
        node
        for node in plugin_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "init_plugin"
    )
    called_names = {
        node.func.id
        for node in ast.walk(init_plugin)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "_initialize_plugin_impl" in called_names


def test_downloadmanagerlocal_get_service_delegates_service_registration():
    plugin_class = _downloadmanagerlocal_class()
    get_service = next(
        node
        for node in plugin_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "get_service"
    )
    called_names = {
        node.func.id
        for node in ast.walk(get_service)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "_build_plugin_services_impl" in called_names


def test_downloadmanagerlocal_service_builder_preserves_scheduler_service_metadata():
    source = (PLUGIN_DIR / "service" / "scheduler.py").read_text(encoding="utf-8")

    assert '"id": "TorrentTransferFallback"' in source
    assert '"name": "转移做种兜底服务"' in source
    assert '"trigger": "interval"' in source
    assert '"id": "IYUUAutoSeed"' in source
    assert '"name": "IYUU自动辅种服务"' in source
    assert "CronTrigger.from_crontab(plugin._iyuu_cron)" in source


def test_downloadmanagerlocal_entrypoint_drops_migrated_heavy_imports():
    source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    imported_names = {
        alias.name
        for node in module.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert not {
        "urljoin",
        "bdecode",
        "bencode",
        "etree",
        "SiteOper",
        "SystemConfigOper",
        "SitesHelper",
        "TorrentHelper",
        "TransHandler",
        "Qbittorrent",
        "Transmission",
        "RequestUtils",
        "StringUtils",
    } & imported_names


def test_downloadmanagerlocal_frontend_sources_use_standard_layout():
    for path in LEGACY_FRONTEND_PATHS:
        assert not path.exists()

    for path in EXPECTED_FRONTEND_FILES:
        assert path.is_file()


def test_downloadmanagerlocal_frontend_build_targets_plugin_dist_assets():
    vite_source = (FRONTEND_DIR / "vite.config.js").read_text(encoding="utf-8")

    assert "outDir: '../dist'" in vite_source
    assert "emptyOutDir: true" in vite_source
    assert "target: 'esnext'" in vite_source
    assert (DIST_ASSETS_DIR / "remoteEntry.js").is_file()
