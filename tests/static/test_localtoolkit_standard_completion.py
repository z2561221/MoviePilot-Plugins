from __future__ import annotations

import ast
import json
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "localtoolkit"
ENTRYPOINT = PLUGIN_DIR / "__init__.py"
PACKAGE = REPO / "package.v2.json"
PLUGIN_JSON = PLUGIN_DIR / "plugin.json"
REMOTE_ENTRY = PLUGIN_DIR / "dist" / "assets" / "remoteEntry.js"
VITE_CONFIG = PLUGIN_DIR / "frontend" / "vite.config.js"
CONFIG_VUE = PLUGIN_DIR / "frontend" / "src" / "components" / "Config.vue"
FRONTEND_API = PLUGIN_DIR / "frontend" / "src" / "api.js"

ENTRYPOINT_HEAVY_METHODS = {
    "init_plugin",
    "get_api",
    "api_status",
    "api_run",
    "api_history",
    "api_options",
    "api_invalidate_cache",
}

MODULE_BUSINESS_FILES = {
    "base.py",
    "check_missing.py",
    "library_cleanup.py",
    "tmdb_cache.py",
}


def _parse(path: Path) -> ast.Module:
    """解析指定 Python 文件为 AST。"""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _plugin_python_files() -> list[Path]:
    """返回工具中心插件中参与标准审计的 Python 文件。"""
    return [
        path
        for path in PLUGIN_DIR.rglob("*.py")
        if "__pycache__" not in path.parts
        and "tests" not in path.parts
    ]


def _has_chinese(text: str) -> bool:
    """判断 docstring 是否包含中文字符。"""
    return any("\u4e00" <= char <= "\u9fff" for char in text or "")


def _public_docstring_gaps() -> list[str]:
    """列出缺少中文 docstring 的公有类、函数和方法。"""
    gaps: list[str] = []
    for path in _plugin_python_files():
        module = _parse(path)
        for node in ast.walk(module):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            docstring = ast.get_docstring(node) or ""
            if not _has_chinese(docstring):
                gaps.append(f"{path.relative_to(REPO).as_posix()}:{node.lineno}:{node.name}")
    return sorted(gaps)


def _executable_statement_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """统计函数体内除 docstring 外的顶层可执行语句数。"""
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return len(body)


def _heavy_entrypoint_methods() -> list[str]:
    """列出入口层仍然承载明显业务逻辑的方法。"""
    module = _parse(ENTRYPOINT)
    heavy: list[str] = []
    for node in ast.walk(module):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in ENTRYPOINT_HEAVY_METHODS:
            continue
        if _executable_statement_count(node) > 2:
            heavy.append(f"{ENTRYPOINT.relative_to(REPO).as_posix()}:{node.lineno}:{node.name}")
    return sorted(heavy)


def _module_business_files() -> list[str]:
    """列出 modules 层仍定义业务类或业务函数的文件。"""
    files: list[str] = []
    modules_dir = PLUGIN_DIR / "modules"
    for name in sorted(MODULE_BUSINESS_FILES):
        path = modules_dir / name
        module = _parse(path)
        definitions = [
            node.name
            for node in module.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if definitions:
            files.append(f"{path.relative_to(REPO).as_posix()}::{','.join(definitions)}")
    return files


def _load_json(path: Path) -> dict:
    """读取 JSON 文件并返回对象。"""
    return json.loads(path.read_text(encoding="utf-8"))


def _entrypoint_plugin_version() -> str:
    """读取入口类声明的插件版本。"""
    match = re.search(r'plugin_version\s*=\s*"([^"]+)"', ENTRYPOINT.read_text(encoding="utf-8"))
    assert match is not None
    return match.group(1)


def test_localtoolkit_metadata_versions_are_consistent():
    """确认 package、plugin.json 与入口版本保持一致。"""
    package = _load_json(PACKAGE)
    plugin_json = _load_json(PLUGIN_JSON)
    assert package["LocalToolkit"]["version"] == plugin_json["version"] == _entrypoint_plugin_version()
    assert package["LocalToolkit"]["author_url"] == "https://github.com/z2561221"


def test_localtoolkit_vue_federation_contract_is_present():
    """确认 Vue 联邦运行资产和 expose 契约存在。"""
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
    vite_config = VITE_CONFIG.read_text(encoding="utf-8")
    assert "return 'vue', 'dist/assets'" in entrypoint
    assert REMOTE_ENTRY.exists()
    for expose in ("./Page", "./Config", "./Dashboard", "./AppPage"):
        assert expose in vite_config
    assert "emptyOutDir: true" in vite_config


def test_localtoolkit_public_docstrings_are_complete():
    """工具中心公有类、函数和方法必须具备中文 docstring。"""
    assert _public_docstring_gaps() == []


def test_localtoolkit_entrypoint_is_thin_contract_layer():
    """入口层必须只保留插件契约和薄委托，不承载业务流程。"""
    assert _heavy_entrypoint_methods() == []


def test_localtoolkit_modules_do_not_remain_second_service_layer():
    """modules 层不能继续作为第二套 service 层持有核心业务定义。"""
    assert _module_business_files() == []


def test_localtoolkit_mobile_primary_nav_is_horizontal():
    """移动端一级导航必须横向滚动，避免继续竖向占据首屏。"""
    source = CONFIG_VUE.read_text(encoding="utf-8")
    assert 'class="plugin-nav-list py-2"' in source
    assert re.search(r"@media\s*\(\s*max-width:\s*760px\s*\)", source, re.S)
    assert "max-width: 1024px" not in source
    assert "(hover: none)" not in source
    assert re.search(r"\.plugin-nav\s*\{[^}]*overflow-x:\s*auto", source, re.S)
    assert re.search(r"\.plugin-nav-list\s*\{[^}]*display:\s*flex", source, re.S)
    assert re.search(r"\.plugin-nav-list\s*\{[^}]*flex-wrap:\s*nowrap", source, re.S)
    assert re.search(r"\.plugin-nav-item\s*\{[^}]*flex:\s*0 0 auto", source, re.S)


def test_localtoolkit_config_uses_standard_stable_shell():
    """配置页必须使用标准稳定外壳和内容滚动区。"""
    source = CONFIG_VUE.read_text(encoding="utf-8")
    assert re.search(r"\.plugin-config\s*\{[^}]*width:\s*min\(1120px,\s*calc\(100vw - 48px\)\)", source, re.S)
    assert re.search(r"\.plugin-card\s*\{[^}]*height:\s*clamp\(760px,\s*calc\(100dvh - 48px\),\s*860px\)", source, re.S)
    assert re.search(r"\.plugin-card\s*\{[^}]*display:\s*flex[^}]*flex-direction:\s*column[^}]*overflow:\s*hidden", source, re.S)
    assert re.search(r"\.plugin-nav\s*\{[^}]*width:\s*160px[^}]*flex:\s*0 0 160px", source, re.S)
    assert re.search(r"\.plugin-body\s*\{[^}]*flex:\s*1 1 auto[^}]*min-height:\s*0[^}]*display:\s*flex", source, re.S)
    assert re.search(r"\.plugin-content\s*\{[^}]*flex:\s*1 1 auto[^}]*min-height:\s*0[^}]*display:\s*flex[^}]*flex-direction:\s*column", source, re.S)
    assert re.search(r"\.plugin-window\s*\{[^}]*flex:\s*1 1 auto[^}]*min-height:\s*0[^}]*overflow-y:\s*auto", source, re.S)
    assert ".plugin-window--overview" in source
    assert re.search(r"class=\"plugin-window\"[^>]*:class=\"\{ 'plugin-window--overview': activeMain === 'overview' \}\"", source, re.S)


def test_localtoolkit_config_navigation_uses_standard_tabs():
    """配置页一级导航和子标签必须使用标准 key 与默认项。"""
    source = CONFIG_VUE.read_text(encoding="utf-8")
    assert "const activeMain = ref('overview')" in source
    assert "const activeSub = ref('overview')" in source
    assert re.search(r"overview:\s*\[\{\s*key:\s*'overview',\s*title:\s*'运行总览'", source, re.S)
    assert "key: 'advanced', title: '高级选项'" in source
    assert "key: 'danger'" not in source
    assert "activeSub === 'advanced'" in source
    assert "activeSub === 'danger'" not in source


def test_localtoolkit_frontend_api_uses_injected_client_only():
    """Vue 联邦组件必须通过注入 API 调用插件接口。"""
    source = FRONTEND_API.read_text(encoding="utf-8")
    assert "fetch(" not in source
    assert "/api/v1/" not in source
    assert "if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')" in source
    assert "if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')" in source
    assert "return unwrap(await api.get(path))" in source
    assert "return unwrap(await api.post(path, body))" in source
