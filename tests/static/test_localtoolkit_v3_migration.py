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


def test_localtoolkit_v3_public_docstrings_are_complete() -> None:
    """确认 V3 公有类、函数和方法都具备中文文档字符串。"""
    assert _public_docstring_gaps() == []
