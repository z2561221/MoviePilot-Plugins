from __future__ import annotations

import ast
import json
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
V2_DIR = REPO / "plugins.v2" / "localtoolkit"
V3_DIR = REPO / "plugins.v3" / "localtoolkit"
V2_PACKAGE = REPO / "package.local.v2.json"
V3_PACKAGE = REPO / "package.local.v3.json"
FORBIDDEN_V3_IMPORT_PREFIXES = ("app.core", "app.helper", "app.utils")
FORBIDDEN_V3_IMPORTS = {"app.log"}


def _load_json(path: Path) -> dict:
    """读取 JSON 对象。"""
    return json.loads(path.read_text(encoding="utf-8"))


def _plugin_version(path: Path) -> str:
    """从插件入口读取版本号。"""
    match = re.search(r'plugin_version\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"))
    assert match is not None
    return match.group(1)


def _public_docstring_gaps() -> list[str]:
    """列出 V3 源码中缺少中文文档字符串的公有定义。"""
    gaps = []
    for path in V3_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            docstring = ast.get_docstring(node) or ""
            if not any("\u4e00" <= char <= "\u9fff" for char in docstring):
                gaps.append(f"{path.relative_to(REPO).as_posix()}:{node.lineno}:{node.name}")
    return sorted(gaps)


def _v3_legacy_imports() -> list[str]:
    """列出 V3 源码中仍会触发宿主兼容导入的路径。"""
    imports = []
    for path in V3_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name in FORBIDDEN_V3_IMPORTS or name.startswith(FORBIDDEN_V3_IMPORT_PREFIXES):
                    imports.append(f"{path.relative_to(REPO).as_posix()}:{node.lineno}:{name}")
    return sorted(imports)


def test_localtoolkit_v3_generation_metadata_is_isolated() -> None:
    """确认 V2 阻止回退且 V3 使用独立本地索引和版本。"""
    v2_package = _load_json(V2_PACKAGE)["LocalToolkit"]
    v2_plugin = _load_json(V2_DIR / "plugin.json")
    v3_package = _load_json(V3_PACKAGE)["LocalToolkit"]
    v3_plugin = _load_json(V3_DIR / "plugin.json")

    assert v2_package["version"] == "1.2.13"
    assert v2_package["v3"] is False
    assert v2_plugin["v3"] is False
    assert v3_package == v3_plugin
    assert v3_package["version"] == _plugin_version(V3_DIR / "__init__.py") == "3.0.0"
    assert v3_package["system_version"] == ">=3.0.0"
    assert not (V3_DIR / "tests").exists()


def test_localtoolkit_v3_api_and_federation_contracts_are_present() -> None:
    """确认 V3 API 使用具体模型且联邦前端只解一层响应。"""
    controller = (V3_DIR / "controller" / "api.py").read_text(encoding="utf-8")
    frontend_api = (V3_DIR / "frontend" / "src" / "api.js").read_text(encoding="utf-8")

    assert controller.count('"response_model"') == 5
    assert '"response_model": ToolkitStatusData' in controller
    assert '"response_model": schemas.Response[ToolkitRunData]' in controller
    assert '"response_model": ToolkitHistoryData' in controller
    assert '"response_model": ToolkitOptionsData' in controller
    assert '"response_model": schemas.Response[None]' in controller
    assert "response.data.data" not in frontend_api
    assert "return response.data" in frontend_api
    assert (V3_DIR / "dist" / "assets" / "remoteEntry.js").is_file()


def test_localtoolkit_v3_uses_public_media_server_sdk() -> None:
    """确认 V3 媒体服务器适配器使用公开 SDK。"""
    adapter = (V3_DIR / "adapter" / "media_server.py").read_text(encoding="utf-8")

    assert "from app.sdk.services import MediaServerHelper" in adapter
    assert "app.helper.mediaserver" not in adapter


def test_localtoolkit_v3_uses_canonical_sdk_imports() -> None:
    """确认 V3 源码不再依赖会触发兼容告警的宿主旧入口。"""
    assert _v3_legacy_imports() == []
    base = (V3_DIR / "service" / "base.py").read_text(encoding="utf-8")
    cleanup = (V3_DIR / "service" / "library_cleanup.py").read_text(encoding="utf-8")
    assert "from app.schemas.types import MessageType" in base
    assert "from app.schemas.types import MessageType" in cleanup
    assert "NotificationType" not in base
    assert "NotificationType" not in cleanup


def test_localtoolkit_v3_public_docstrings_are_complete() -> None:
    """确认 V3 公有类、函数和方法都具备中文文档字符串。"""
    assert _public_docstring_gaps() == []
