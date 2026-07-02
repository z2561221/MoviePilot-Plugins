from __future__ import annotations

import ast
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"

ENTRYPOINT_DEAD_IMPORTS = {
    "os",
    "re",
    "time",
    "Path",
    "Union",
    "MetaInfo",
    "NotificationType",
    "MediaType",
    "SystemConfigKey",
}

NEW_BACKEND_DIRS = (
    PLUGIN_DIR / "adapter",
    PLUGIN_DIR / "model",
    PLUGIN_DIR / "service",
)


def _module(path: Path) -> ast.Module:
    """解析 Python 文件为 AST。"""
    return ast.parse(path.read_text(encoding="utf-8"))


def _imported_names(path: Path) -> set[str]:
    """返回文件顶层导入的本地名称。"""
    names = set()
    for node in _module(path).body:
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _has_chinese(text: str) -> bool:
    """判断文本是否包含中文字符。"""
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def test_downloadmanagerlocal_entrypoint_has_no_known_dead_refactor_imports():
    imported_names = _imported_names(PLUGIN_DIR / "__init__.py")

    assert not (ENTRYPOINT_DEAD_IMPORTS & imported_names)


def test_downloadmanagerlocal_new_backend_public_surfaces_have_chinese_docstrings():
    missing = []
    for directory in NEW_BACKEND_DIRS:
        for path in directory.glob("*.py"):
            for node in ast.walk(_module(path)):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if node.name.startswith("_"):
                    continue
                docstring = ast.get_docstring(node) or ""
                if not _has_chinese(docstring):
                    missing.append(f"{path.relative_to(REPO).as_posix()}:{node.lineno}:{node.name}")

    assert missing == []
