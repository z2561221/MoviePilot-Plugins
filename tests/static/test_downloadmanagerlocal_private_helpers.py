import ast
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"


def _plugin_python_files() -> list[Path]:
    """返回需要参与私有 helper 静态审计的插件 Python 文件。"""
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


def _private_docstring_gaps() -> list[str]:
    """列出缺少中文 docstring 的私有类、函数和方法。"""
    gaps: list[str] = []
    for path in _plugin_python_files():
        module = _parse(path)
        for node in ast.walk(module):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("_"):
                continue
            if node.name.startswith("__") and node.name.endswith("__"):
                continue
            docstring = ast.get_docstring(node) or ""
            if not _has_chinese(docstring):
                gaps.append(f"{path.relative_to(REPO).as_posix()}:{node.lineno}:{node.name}")
    return sorted(gaps)


def _unreachable_after_return() -> list[str]:
    """列出函数体顶层 return 后仍保留语句的死代码位置。"""
    offenders: list[str] = []
    for path in _plugin_python_files():
        module = _parse(path)
        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = list(node.body)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                body = body[1:]
            for index, statement in enumerate(body[:-1]):
                if isinstance(statement, ast.Return):
                    next_statement = body[index + 1]
                    offenders.append(
                        f"{path.relative_to(REPO).as_posix()}:{getattr(next_statement, 'lineno', statement.lineno)}:{node.name}"
                    )
    return sorted(offenders)


def test_downloadmanagerlocal_modules_do_not_call_plugin_private_members():
    module_paths = [
        PLUGIN_DIR / "modules" / "transfer.py",
        PLUGIN_DIR / "modules" / "iyuu.py",
        PLUGIN_DIR / "modules" / "recheck.py",
    ]

    offenders = []
    for path in module_paths:
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if "plugin.__" in line and "plugin.__class__" not in line:
                offenders.append(f"{path.relative_to(REPO)}:{line_no}:{line.strip()}")

    assert offenders == []


def test_downloadmanagerlocal_private_helpers_have_chinese_docstrings():
    """私有 helper 也必须说明用途，避免迁移后形成隐藏黑盒。"""
    assert _private_docstring_gaps() == []


def test_downloadmanagerlocal_private_helpers_have_no_unreachable_return_tail():
    """私有 helper 不应在顶层 return 后继续保留不可达语句。"""
    assert _unreachable_after_return() == []
