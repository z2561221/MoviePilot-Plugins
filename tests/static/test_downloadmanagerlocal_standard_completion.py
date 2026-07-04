from __future__ import annotations

import ast
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"
ENTRYPOINT = PLUGIN_DIR / "__init__.py"

ENTRYPOINT_BUSINESS_METHODS = {
    "check_recheck",
    "_sweep_paused_seed_tasks",
    "__can_seeding",
    "on_transfer_complete",
}

RECHECK_ENTRYPOINT_METHODS = {
    "check_recheck",
    "_sweep_paused_seed_tasks",
    "__can_seeding",
}

EVENT_ENTRYPOINT_METHODS = {
    "on_transfer_complete",
}

ENTRYPOINT_FORBIDDEN_IMPORT_SNIPPETS = {
    "from datetime import datetime, timedelta",
    "import pytz",
    "from apscheduler.schedulers.background import BackgroundScheduler",
    "from app.core.config import settings",
    "from app.plugins.downloadmanagerlocal.iyuu_helper import IyuuHelper",
}


def _plugin_python_files() -> list[Path]:
    """返回插件包内需要参与标准审计的 Python 文件。"""
    return [
        path
        for path in PLUGIN_DIR.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def _parse(path: Path) -> ast.Module:
    """解析 Python 文件为 AST。"""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _has_chinese(text: str) -> bool:
    """判断文本是否包含中文字符。"""
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
    """统计函数体内除 docstring 外的顶层可执行语句数量。"""
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return len(body)


def _heavy_entrypoint_methods() -> list[str]:
    """列出仍在入口层承载明显业务逻辑的方法。"""
    module = _parse(ENTRYPOINT)
    heavy: list[str] = []
    for node in ast.walk(module):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in ENTRYPOINT_BUSINESS_METHODS:
            continue
        if _executable_statement_count(node) > 3:
            heavy.append(f"{ENTRYPOINT.relative_to(REPO).as_posix()}:{node.lineno}:{node.name}")
    return sorted(heavy)


def _thin_delegate_gaps(method_names: set[str]) -> list[str]:
    """列出不是单行服务委托形态的入口方法。"""
    module = _parse(ENTRYPOINT)
    gaps: list[str] = []
    for node in ast.walk(module):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in method_names:
            continue
        body = list(node.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]
        if len(body) != 1:
            gaps.append(f"{ENTRYPOINT.relative_to(REPO).as_posix()}:{node.lineno}:{node.name}")
            continue
        statement = body[0]
        call = None
        if isinstance(statement, ast.Return):
            call = statement.value
        elif isinstance(statement, ast.Expr):
            call = statement.value
        if not isinstance(call, ast.Call):
            gaps.append(f"{ENTRYPOINT.relative_to(REPO).as_posix()}:{node.lineno}:{node.name}")
    return sorted(gaps)


def _module_business_files() -> list[str]:
    """列出仍在 modules 层定义业务函数或类的文件。"""
    business_files: list[str] = []
    modules_dir = PLUGIN_DIR / "modules"
    for path in modules_dir.glob("*.py"):
        if path.name == "__init__.py":
            continue
        module = _parse(path)
        definitions = [
            node.name
            for node in module.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if definitions:
            business_files.append(f"{path.relative_to(REPO).as_posix()}::{','.join(definitions[:5])}")
    return sorted(business_files)


def _module_definitions(module_name: str) -> list[str]:
    """列出指定 modules 文件中仍保留的顶层函数或类定义。"""
    path = PLUGIN_DIR / "modules" / module_name
    module = _parse(path)
    return [
        node.name
        for node in module.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def test_downloadmanagerlocal_standard_completion_baseline_gaps_are_visible():
    """确认当前标准收尾任务确实有可观测缺口。"""
    remaining_gaps = {
        "public_docstrings": _public_docstring_gaps(),
        "module_business_files": _module_business_files(),
    }
    assert any(remaining_gaps.values()), remaining_gaps


def test_downloadmanagerlocal_recheck_entrypoint_is_thin():
    """做种校验运行时逻辑必须由 service/recheck 持有，入口层只做薄委托。"""
    assert _thin_delegate_gaps(RECHECK_ENTRYPOINT_METHODS) == []


def test_downloadmanagerlocal_transfer_complete_entrypoint_is_thin():
    """TransferComplete 延迟调度必须由 service 边界持有，入口层只做事件委托。"""
    assert _thin_delegate_gaps(EVENT_ENTRYPOINT_METHODS) == []


def test_downloadmanagerlocal_entrypoint_size_and_imports_are_slim():
    """入口层必须保持插件契约定位，不直接持有生命周期调度依赖。"""
    source = ENTRYPOINT.read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 520
    forbidden_imports = [
        snippet
        for snippet in ENTRYPOINT_FORBIDDEN_IMPORT_SNIPPETS
        if snippet in source
    ]
    assert forbidden_imports == []


def test_downloadmanagerlocal_transfer_and_rename_modules_are_shims():
    """transfer/rename legacy modules 只能作为兼容 shim，不再定义业务函数。"""
    assert _module_definitions("transfer.py") == []
    assert _module_definitions("rename.py") == []


def test_downloadmanagerlocal_iyuu_module_is_shim():
    """IYUU legacy module 只能作为兼容 shim，不再定义辅种业务函数。"""
    assert _module_definitions("iyuu.py") == []


@pytest.mark.xfail(reason="standard completion is implemented by the phased ledger", strict=True)
def test_downloadmanagerlocal_standard_completion_target_is_reached():
    """最终标准完成态：公有文档、入口瘦身和 modules 边界全部收束。"""
    assert _public_docstring_gaps() == []
    assert _heavy_entrypoint_methods() == []
    assert _module_business_files() == []
