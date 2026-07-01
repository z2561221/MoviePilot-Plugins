from __future__ import annotations

import ast
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"

FORBIDDEN_UI_PATHS = [
    "plugins.v2/downloadmanagerlocal/src",
    "plugins.v2/downloadmanagerlocal/dist",
    "plugins.v2/downloadmanagerlocal/index.html",
    "plugins.v2/downloadmanagerlocal/vite.config.js",
    "plugins.v2/downloadmanagerlocal/package.json",
    "plugins.v2/downloadmanagerlocal/package-lock.json",
    "plugins.v2/downloadmanagerlocal/pnpm-lock.yaml",
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
    """从插件入口静态提取 get_api 路由元数据。"""
    source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    plugin_class = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "DownloadManagerLocal"
    )
    get_api = next(
        node
        for node in plugin_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "get_api"
    )
    return_node = next(
        node
        for node in ast.walk(get_api)
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


def test_downloadmanagerlocal_init_plugin_delegates_config_initialization():
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

    assert "_initialize_runtime_config_impl" in called_names


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


def test_downloadmanagerlocal_backend_refactor_does_not_touch_ui_worktree_paths():
    assert _git_diff_names() == []
    assert _git_diff_names("--cached") == []


def test_downloadmanagerlocal_backend_branch_diff_does_not_touch_ui_paths():
    has_origin_main = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        cwd=REPO,
        text=True,
        capture_output=True,
    )
    if has_origin_main.returncode != 0:
        return

    assert _git_diff_names("origin/main...HEAD") == []
