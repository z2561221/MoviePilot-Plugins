#!/usr/bin/env python3
"""以确定性规则为 MoviePilot V3 插件生成试行质量评分。"""

# 评分器需要在一个报告中聚合多个独立合同；这些局部复杂度不应转移到插件代码。
# pylint: disable=too-many-lines,too-many-instance-attributes,too-many-arguments
# pylint: disable=too-many-positional-arguments,too-many-locals,too-many-branches
# pylint: disable=too-many-statements

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


RULE_VERSION = "3.1.0"
PACKAGE_FILE = "package.v3.json"
SOURCE_ROOT = "plugins.v3"
TEST_ROOT = "tests/v3"
QUALITY_EXCEPTIONS_FILE = ".github/plugin-quality-exceptions.json"

DIMENSION_MAX = {
    "structure": 1.5,
    "contract": 2.0,
    "lifecycle": 1.5,
    "security": 1.0,
    "tests": 2.0,
    "metadata": 0.5,
    "runtime": 1.0,
    "documentation": 0.5,
}

FORBIDDEN_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+app\.(?:sdk\._legacy|core|helper|utils)(?:\.|\s|$)"
)
INTERNAL_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+app\."
    r"(?:application|domain|foundation|adapters|runtime)(?:\.|\s|$)"
)
INTERNAL_IMPORT_PREFIXES = (
    "app.application.",
    "app.domain.",
    "app.foundation.",
    "app.adapters.",
    "app.runtime.",
    "app.infrastructure.",
    "app.services.",
)
DB_MODEL_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+app\.db\.models(?:\.|\s|$)"
)
HOST_SESSION_IMPORT_RE = re.compile(
    r"^\s*from\s+app\.db(?:\.[^\s]+)?\s+import\s+.*\b"
    r"(?:ScopedSession|SessionFactory|AsyncSessionFactory)\b"
)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
SECRET_NAME_RE = re.compile(
    r"(?:^|_)(?:api_?key|access_?key|private_?key|password|passwd|secret|token)(?:$|_)",
    re.IGNORECASE,
)
SECRET_PLACEHOLDERS = (
    "changeme",
    "dummy",
    "example",
    "placeholder",
    "test",
    "your_",
    "your-",
    "<",
    "${",
)
SEMANTIC_DIRS = {
    "adapter",
    "controller",
    "model",
    "repository",
    "runtime",
    "service",
}
IGNORED_DIRS = {"__pycache__", ".pytest_cache", "node_modules"}


@dataclass(frozen=True)
class CheckResult:
    """记录单项评分、证据和修复建议。"""

    check_id: str
    dimension: str
    title: str
    max_points: float
    points: float
    status: str
    severity: str = "info"
    evidence: tuple[str, ...] = ()
    recommendation: str = ""

    @property
    def deduction(self) -> float:
        """返回本检查相对满分的扣分。"""
        return round(self.max_points - self.points, 3)


def _check(
    check_id: str,
    dimension: str,
    title: str,
    max_points: float,
    points: float,
    status: str,
    *,
    severity: str = "info",
    evidence: Iterable[str] = (),
    recommendation: str = "",
) -> CheckResult:
    """构造经过边界归一化的检查结果。"""
    normalized = max(0.0, min(float(points), float(max_points)))
    return CheckResult(
        check_id=check_id,
        dimension=dimension,
        title=title,
        max_points=float(max_points),
        points=round(normalized, 3),
        status=status,
        severity=severity,
        evidence=tuple(evidence),
        recommendation=recommendation,
    )


def _load_json(path: Path) -> dict[str, Any]:
    """读取 UTF-8 JSON 对象。"""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} 必须是 JSON 对象")
    return data


def _read_text(path: Path) -> str:
    """读取允许 BOM 的 UTF-8 文本。"""
    return path.read_text(encoding="utf-8-sig")


def _source_files(plugin_dir: Path) -> list[Path]:
    """返回插件内参与 Python 静态分析的源码文件。"""
    return sorted(
        path
        for path in plugin_dir.rglob("*.py")
        if not any(part in IGNORED_DIRS for part in path.parts)
    )


def _frontend_files(plugin_dir: Path) -> list[Path]:
    """返回未构建的前端源码文件，避免扫描压缩产物。"""
    frontend = plugin_dir / "frontend"
    if not frontend.is_dir():
        return []
    extensions = {".js", ".jsx", ".ts", ".tsx", ".vue"}
    return sorted(
        path
        for path in frontend.rglob("*")
        if path.is_file()
        and path.suffix.lower() in extensions
        and not any(part in IGNORED_DIRS for part in path.parts)
    )


def _parse_sources(files: Iterable[Path]) -> tuple[dict[Path, ast.Module], list[str]]:
    """解析 Python 文件并返回可定位的语法错误。"""
    trees: dict[Path, ast.Module] = {}
    errors: list[str] = []
    for path in files:
        try:
            trees[path] = ast.parse(_read_text(path), filename=str(path))
        except (SyntaxError, UnicodeError) as error:
            line = getattr(error, "lineno", None)
            suffix = f":{line}" if line is not None else ""
            errors.append(f"{path}{suffix}: {error}")
    return trees, errors


def _literal_class_attributes(class_node: ast.ClassDef | None) -> dict[str, Any]:
    """提取插件类的字面量类属性。"""
    if class_node is None:
        return {}
    attributes: dict[str, Any] = {}
    for node in class_node.body:
        name = None
        value_node = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                name = target.id
                value_node = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
            value_node = node.value
        if name and value_node is not None:
            try:
                attributes[name] = ast.literal_eval(value_node)
            except (ValueError, TypeError):
                continue
    return attributes


def _plugin_class(tree: ast.Module | None, plugin_id: str) -> ast.ClassDef | None:
    """定位与 package ID 对应的插件类。"""
    if tree is None:
        return None
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    for node in classes:
        if node.name == plugin_id:
            return node
    for node in classes:
        if "plugin_version" in _literal_class_attributes(node):
            return node
    return None


def _class_methods(
    class_node: ast.ClassDef | None,
) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """返回插件类直接声明的方法。"""
    if class_node is None:
        return {}
    return {
        node.name: node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _substantive_body(function: ast.FunctionDef | ast.AsyncFunctionDef | None) -> bool:
    """判断方法体是否包含文档字符串之外的实际清理逻辑。"""
    if function is None:
        return False
    body = list(function.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            body = body[1:]
    for node in body:
        if isinstance(node, ast.Pass):
            continue
        if isinstance(node, ast.Return) and (
            node.value is None
            or isinstance(node.value, ast.Constant) and node.value.value is None
        ):
            continue
        return True
    return False


def _method_source(source: str, method: ast.AST | None) -> str:
    """提取方法对应的源码片段。"""
    if method is None:
        return ""
    return ast.get_source_segment(source, method) or ""


def _scan_imports(files: Iterable[Path], pattern: re.Pattern[str]) -> list[str]:
    """扫描匹配指定合同模式的导入语句。"""
    hits: list[str] = []
    for path in files:
        for line_number, line in enumerate(_read_text(path).splitlines(), start=1):
            if pattern.search(line):
                hits.append(f"{path}:{line_number}: {line.strip()}")
    return hits


def _load_quality_exceptions(repo: Path, plugin_id: str) -> tuple[set[tuple[str, str]], list[str]]:
    """读取插件逐符号内部导入例外，并校验其审计字段。"""
    path = repo / QUALITY_EXCEPTIONS_FILE
    if not path.is_file():
        return set(), []
    try:
        payload = _load_json(path)
    except (ValueError, json.JSONDecodeError) as error:
        return set(), [f"{QUALITY_EXCEPTIONS_FILE} 无法解析: {error}"]
    plugin_payload = payload.get(plugin_id, {})
    if plugin_payload in (None, {}):
        return set(), []
    if not isinstance(plugin_payload, dict):
        return set(), [f"{QUALITY_EXCEPTIONS_FILE}: {plugin_id} 必须是对象"]
    entries = plugin_payload.get("imports", [])
    if not isinstance(entries, list):
        return set(), [f"{QUALITY_EXCEPTIONS_FILE}: {plugin_id}.imports 必须是数组"]
    allowed: set[tuple[str, str]] = set()
    issues: list[str] = []
    required = ("module", "symbol", "reason", "host_version", "removal_condition", "test")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append(f"{QUALITY_EXCEPTIONS_FILE}: {plugin_id}.imports[{index}] 必须是对象")
            continue
        missing = [key for key in required if not str(entry.get(key, "")).strip()]
        module = str(entry.get("module", "")).strip()
        symbol = str(entry.get("symbol", "")).strip()
        if missing:
            issues.append(
                f"{QUALITY_EXCEPTIONS_FILE}: {plugin_id}.imports[{index}] 缺少 {', '.join(missing)}"
            )
            continue
        if not module.startswith(INTERNAL_IMPORT_PREFIXES):
            issues.append(
                f"{QUALITY_EXCEPTIONS_FILE}: {plugin_id}.imports[{index}] module 不是宿主内部路径"
            )
            continue
        allowed.add((module, symbol))
    return allowed, issues


def _scan_internal_import_symbols(files: Iterable[Path]) -> list[tuple[Path, int, str, str]]:
    """返回宿主内部导入的模块、符号和源码位置。"""
    hits: list[tuple[Path, int, str, str]] = []
    for path in files:
        try:
            tree = ast.parse(_read_text(path), filename=str(path))
        except (SyntaxError, UnicodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(INTERNAL_IMPORT_PREFIXES):
                    hits.extend(
                        (path, node.lineno, node.module, alias.name)
                        for alias in node.names
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(INTERNAL_IMPORT_PREFIXES):
                        hits.append((path, node.lineno, alias.name, "*"))
    return hits


def _call_name(call: ast.Call) -> str:
    """将调用目标转换为便于审计的点分名称。"""
    parts: list[str] = []
    node: ast.AST = call.func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _definition_time_side_effects(trees: dict[Path, ast.Module]) -> list[str]:
    """定位模块或类定义期明显会启动资源的调用。"""
    suspicious = (
        "create_task",
        "create_engine",
        "connect",
        "open",
        "start",
        "run_forever",
        "run_until_complete",
        "AsyncClient",
        "BackgroundScheduler",
        "BlockingScheduler",
        "Process",
        "Session",
        "Thread",
    )
    hits: list[str] = []

    def inspect_nodes(path: Path, nodes: Iterable[ast.stmt]) -> None:
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(node, ast.ClassDef):
                inspect_nodes(path, node.body)
                continue
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                name = _call_name(child)
                tail = name.rsplit(".", 1)[-1]
                if tail in suspicious:
                    hits.append(f"{path}:{getattr(child, 'lineno', '?')}: {name}()")

    for path, tree in trees.items():
        inspect_nodes(path, tree.body)
    return hits


def _plugin_owned_resource_markers(trees: dict[Path, ast.Module]) -> list[str]:
    """定位需要由插件 stop_service 释放的典型长期资源。"""
    resource_names = {
        "AsyncClient",
        "BackgroundScheduler",
        "BlockingScheduler",
        "Process",
        "Thread",
        "Timer",
        "create_engine",
        "create_task",
        "run_forever",
    }
    hits: list[str] = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name.rsplit(".", 1)[-1] in resource_names:
                hits.append(f"{path}:{getattr(node, 'lineno', 0)}: {name}()")
    return hits


def _assignment_names(node: ast.AST) -> list[str]:
    """提取赋值目标中的字段名。"""
    names: list[str] = []
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets.append(node.target)
    for target in targets:
        for child in ast.walk(target):
            if isinstance(child, ast.Name):
                names.append(child.id)
            elif isinstance(child, ast.Attribute):
                names.append(child.attr)
    return names


def _secret_literals(trees: dict[Path, ast.Module]) -> list[str]:
    """定位疑似直接写入源码的凭据字面量，不回显其内容。"""
    hits: list[str] = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            names = _assignment_names(node)
            if not any(SECRET_NAME_RE.search(name) for name in names):
                continue
            value_node = node.value
            if not isinstance(value_node, ast.Constant) or not isinstance(value_node.value, str):
                continue
            value = value_node.value.strip()
            lowered = value.lower()
            if len(value) < 12 or any(marker in lowered for marker in SECRET_PLACEHOLDERS):
                continue
            if set(value) <= {"*", "-", "_"}:
                continue
            hits.append(f"{path}:{getattr(node, 'lineno', '?')}: {', '.join(names)}")
    return hits


def _public_docstring_stats(trees: dict[Path, ast.Module]) -> tuple[int, int, list[str]]:
    """统计公共类、函数和方法的中文文档字符串覆盖。"""
    total = 0
    compliant = 0
    missing: list[str] = []

    def inspect(path: Path, node: ast.AST, prefix: str = "") -> None:
        nonlocal total, compliant
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                total += 1
                docstring = ast.get_docstring(node, clean=False) or ""
                if docstring and CHINESE_RE.search(docstring):
                    compliant += 1
                else:
                    qualified = f"{prefix}.{node.name}" if prefix else node.name
                    missing.append(f"{path}:{getattr(node, 'lineno', '?')}: {qualified}")
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        inspect(path, child, node.name)

    for path, tree in trees.items():
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                inspect(path, node)
    return total, compliant, missing


def _test_inventory(test_dir: Path) -> tuple[list[Path], int, list[str]]:
    """统计测试文件与测试函数数量。"""
    files = sorted(test_dir.rglob("test_*.py")) if test_dir.is_dir() else []
    cases = 0
    errors: list[str] = []
    for path in files:
        try:
            tree = ast.parse(_read_text(path), filename=str(path))
        except (SyntaxError, UnicodeError) as error:
            errors.append(f"{path}: {error}")
            continue
        cases += sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        )
    return files, cases, errors


def _render_mode(method: ast.AST | None) -> tuple[str, str] | None:
    """从字面量 return 中提取 Vue 渲染模式。"""
    if method is None:
        return None
    for node in ast.walk(method):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Tuple):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        if isinstance(value, tuple) and len(value) == 2 and all(
            isinstance(item, str) for item in value
        ):
            return value
    return None


def _relative(repo: Path, values: Iterable[str]) -> tuple[str, ...]:
    """尽量把证据路径压缩为仓库相对路径。"""
    prefix = str(repo.resolve()) + str(Path("/"))
    normalized: list[str] = []
    for value in values:
        normalized.append(value.replace(prefix, "").replace("\\", "/"))
    return tuple(normalized)


def _tree_hash(repo: Path, plugin_dir: Path, test_dir: Path, metadata: dict[str, Any]) -> str:
    """计算与评分输入绑定的内容哈希。"""
    digest = hashlib.sha256()
    paths: list[Path] = []
    for root in (plugin_dir, test_dir):
        if not root.is_dir():
            continue
        paths.extend(
            path
            for path in root.rglob("*")
            if path.is_file()
            and not any(part in IGNORED_DIRS for part in path.parts)
            and path.suffix.lower() not in {".pyc", ".pyo"}
        )
    for path in sorted(set(paths)):
        relative = path.relative_to(repo).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    digest.update(json.dumps(metadata, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def _git_sha(repo: Path) -> str | None:
    """读取当前 Git 提交；非 Git 夹具返回空值。"""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _status(points: float, maximum: float, *, blocker: bool = False) -> str:
    """根据得分比例生成稳定状态名。"""
    if blocker:
        return "blocked"
    if math.isclose(points, maximum):
        return "pass"
    if points <= 0:
        return "fail"
    return "partial"


def score_plugin(repo: Path, plugin_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """为单个 V3 插件生成静态试行评分报告。"""
    repo = repo.resolve()
    plugin_dir = repo / SOURCE_ROOT / plugin_id.lower()
    test_dir = repo / TEST_ROOT / plugin_id.lower()
    init_file = plugin_dir / "__init__.py"
    files = _source_files(plugin_dir) if plugin_dir.is_dir() else []
    trees, parse_errors = _parse_sources(files)
    init_tree = trees.get(init_file)
    class_node = _plugin_class(init_tree, plugin_id)
    attributes = _literal_class_attributes(class_node)
    methods = _class_methods(class_node)
    all_source = "\n".join(_read_text(path) for path in files)
    checks: list[CheckResult] = []

    identity_errors: list[str] = []
    if not plugin_dir.is_dir():
        identity_errors.append(f"缺少 {SOURCE_ROOT}/{plugin_id.lower()}")
    if not init_file.is_file():
        identity_errors.append("缺少 __init__.py")
    if class_node is None:
        identity_errors.append(f"缺少插件类 {plugin_id}")
    elif class_node.name != plugin_id:
        identity_errors.append(f"插件类为 {class_node.name}，与 package ID 不一致")
    checks.append(
        _check(
            "structure.identity",
            "structure",
            "目录、入口与插件 ID 一致",
            0.5,
            0.0 if identity_errors else 0.5,
            _status(0.0 if identity_errors else 0.5, 0.5, blocker=bool(identity_errors)),
            severity="blocker" if identity_errors else "info",
            evidence=identity_errors,
            recommendation="修复 package key、插件类名、小写目录名和入口文件映射。",
        )
    )

    line_counts = {path: len(_read_text(path).splitlines()) for path in files}
    total_lines = sum(line_counts.values())
    init_lines = line_counts.get(init_file, 0)
    semantic_dirs = sorted(
        path.name for path in plugin_dir.iterdir() if path.is_dir() and path.name in SEMANTIC_DIRS
    ) if plugin_dir.is_dir() else []
    if total_lines <= 600:
        boundary_points = 0.6 if init_lines <= 500 else 0.3
    elif len(semantic_dirs) >= 2 and init_lines <= max(600, int(total_lines * 0.25)):
        boundary_points = 0.6
    elif semantic_dirs and init_lines <= 800:
        boundary_points = 0.3
    else:
        boundary_points = 0.0
    checks.append(
        _check(
            "structure.boundaries",
            "structure",
            "入口规模与职责拆分",
            0.6,
            boundary_points,
            _status(boundary_points, 0.6),
            evidence=(
                f"Python {len(files)} 文件/{total_lines} 行，__init__.py {init_lines} 行",
                f"职责目录: {', '.join(semantic_dirs) if semantic_dirs else '无'}",
            ),
            recommendation="复杂插件把业务、外部调用和模型拆入 service/adapter/model 等边界。",
        )
    )

    packaged_tests = sorted(plugin_dir.rglob("test_*.py")) if plugin_dir.is_dir() else []
    source_artifacts = sorted(
        path
        for path in plugin_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}
    ) if plugin_dir.is_dir() else []
    purity_issues = [f"测试被打包进源码: {path}" for path in packaged_tests]
    purity_issues.extend(f"源码目录包含运行数据: {path}" for path in source_artifacts)
    checks.append(
        _check(
            "structure.source_purity",
            "structure",
            "源码包不混入测试或运行数据",
            0.4,
            0.0 if purity_issues else 0.4,
            _status(0.0 if purity_issues else 0.4, 0.4),
            evidence=_relative(repo, purity_issues),
            recommendation="把测试移到 tests/v3，运行数据改用 get_data_path()。",
        )
    )

    forbidden_imports = _scan_imports(files, FORBIDDEN_IMPORT_RE)
    checks.append(
        _check(
            "contract.forbidden_imports",
            "contract",
            "V3 禁用兼容导入为零",
            0.8,
            0.0 if forbidden_imports else 0.8,
            _status(0.0 if forbidden_imports else 0.8, 0.8, blocker=bool(forbidden_imports)),
            severity="blocker" if forbidden_imports else "info",
            evidence=_relative(repo, forbidden_imports),
            recommendation="迁移到 app.sdk.* 或登记并验证必要的内部路径例外。",
        )
    )

    db_model_imports = _scan_imports(files, DB_MODEL_IMPORT_RE)
    host_session_imports = _scan_imports(files, HOST_SESSION_IMPORT_RE)
    allowed_internal, exception_issues = _load_quality_exceptions(repo, plugin_id)
    internal_hits = _scan_internal_import_symbols(files)
    unreviewed_internal = [
        f"{path}:{line}: from {module} import {symbol}"
        for path, line, module, symbol in internal_hits
        if (module, symbol) not in allowed_internal
    ]
    internal_evidence = [
        *db_model_imports,
        *host_session_imports,
        *unreviewed_internal,
        *exception_issues,
    ]
    internal_blocker = bool(
        db_model_imports or host_session_imports or unreviewed_internal or exception_issues
    )
    internal_points = 0.4 if not internal_evidence else 0.0
    checks.append(
        _check(
            "contract.internal_imports",
            "contract",
            "宿主内部路径依赖受控",
            0.4,
            internal_points,
            _status(internal_points, 0.4, blocker=internal_blocker),
            severity="blocker" if internal_blocker else "warning" if internal_evidence else "info",
            evidence=_relative(repo, internal_evidence),
            recommendation=(
                "app.db.models.*、ScopedSession、SessionFactory 等宿主内部入口必须移除；"
                "其它内部路径需迁移到稳定 SDK，或建立逐符号允许清单。"
            ),
        )
    )

    render_mode = _render_mode(methods.get("get_render_mode"))
    vue_mode = bool(render_mode and render_mode[0] == "vue")
    has_api = "get_api" in methods or bool(re.search(r"\bdef\s+get_api\s*\(", all_source))
    remote_entry = plugin_dir / "dist/assets/remoteEntry.js"
    api_contracts: list[tuple[bool, str]] = []
    if vue_mode:
        api_contracts.append((render_mode == ("vue", "dist/assets"), f"render_mode={render_mode}"))
        api_contracts.append((remote_entry.is_file(), "dist/assets/remoteEntry.js"))
    if has_api:
        api_contracts.append(("response_model" in all_source, "API 声明 response_model"))
    if vue_mode and has_api:
        bearer_pattern = re.compile(r"['\"]auth['\"]\s*:\s*['\"]bear['\"]")
        api_contracts.append((bool(bearer_pattern.search(all_source)), "Vue API 使用 bearer 鉴权"))
    api_passed = sum(1 for passed, _ in api_contracts if passed)
    api_points = 0.4 if not api_contracts else 0.4 * api_passed / len(api_contracts)
    api_failures = [label for passed, label in api_contracts if not passed]
    checks.append(
        _check(
            "contract.api_ui",
            "contract",
            "API 与 Vue 联邦合同一致",
            0.4,
            api_points,
            _status(api_points, 0.4),
            evidence=api_failures or tuple(label for _, label in api_contracts),
            recommendation="补齐 response_model、bearer 鉴权、render_mode 和远程构建产物。",
        )
    )

    dependency_issues: list[str] = []
    requirements = plugin_dir / "requirements.txt"
    pyproject = plugin_dir / "pyproject.toml"
    plugin_lock = plugin_dir / "uv.lock"
    if requirements.is_file():
        dependency_issues.append("V3 插件仍包含 requirements.txt")
    if plugin_lock.is_file():
        dependency_issues.append("插件目录不应提交 uv.lock")
    if pyproject.is_file():
        try:
            project = tomllib.loads(_read_text(pyproject)).get("project", {})
            if "version" not in project.get("dynamic", []):
                dependency_issues.append('pyproject.toml 缺少 dynamic = ["version"]')
        except (tomllib.TOMLDecodeError, AttributeError) as error:
            dependency_issues.append(f"pyproject.toml 无法解析: {error}")
    checks.append(
        _check(
            "contract.dependencies",
            "contract",
            "V3 依赖声明符合共享环境边界",
            0.4,
            0.0 if dependency_issues else 0.4,
            _status(0.0 if dependency_issues else 0.4, 0.4),
            evidence=dependency_issues,
            recommendation="V3 依赖改用 pyproject.toml，动态版本且不提交插件锁文件。",
        )
    )

    lifecycle_missing = [name for name in ("init_plugin", "stop_service") if name not in methods]
    lifecycle_points = 0.6 * (2 - len(lifecycle_missing)) / 2
    checks.append(
        _check(
            "lifecycle.methods",
            "lifecycle",
            "生命周期入口完整",
            0.6,
            lifecycle_points,
            _status(lifecycle_points, 0.6, blocker=bool(lifecycle_missing)),
            severity="blocker" if lifecycle_missing else "info",
            evidence=tuple(f"缺少 {name}()" for name in lifecycle_missing),
            recommendation="实现可重复调用的 init_plugin() 与 stop_service()。",
        )
    )

    owned_resources = _plugin_owned_resource_markers(trees)
    stop_has_cleanup = _substantive_body(methods.get("stop_service"))
    cleanup_is_valid = stop_has_cleanup or ("stop_service" in methods and not owned_resources)
    cleanup_evidence: tuple[str, ...] = ()
    if not cleanup_is_valid:
        cleanup_evidence = (
            "stop_service 仅为空实现或 return None，且检测到插件自有长期资源"
            if owned_resources
            else "stop_service 仅为空实现或 return None",
        )
    elif not stop_has_cleanup:
        cleanup_evidence = (
            "未检测到插件自有线程、客户端、调度器或引擎，允许幂等空实现",
        )
    checks.append(
        _check(
            "lifecycle.cleanup",
            "lifecycle",
            "stop_service 包含资源清理逻辑",
            0.4,
            0.4 if cleanup_is_valid else 0.0,
            _status(0.4 if cleanup_is_valid else 0.0, 0.4),
            evidence=cleanup_evidence,
            recommendation="显式释放线程、任务、客户端、句柄和插件调度资源。",
        )
    )

    side_effects = _definition_time_side_effects(trees)
    checks.append(
        _check(
            "lifecycle.definition_side_effects",
            "lifecycle",
            "模块与类定义期无明显资源副作用",
            0.5,
            0.0 if side_effects else 0.5,
            _status(0.0 if side_effects else 0.5, 0.5),
            evidence=_relative(repo, side_effects),
            recommendation="把网络、数据库、线程和调度器启动移入 init_plugin()。",
        )
    )

    secret_literals = _secret_literals(trees)
    checks.append(
        _check(
            "security.secret_literals",
            "security",
            "源码中无疑似凭据字面量",
            0.5,
            0.0 if secret_literals else 0.5,
            _status(0.0 if secret_literals else 0.5, 0.5, blocker=bool(secret_literals)),
            severity="blocker" if secret_literals else "info",
            evidence=_relative(repo, secret_literals),
            recommendation="移除硬编码凭据并改用插件配置或环境安全入口。",
        )
    )

    frontend_token_hits: list[str] = []
    token_pattern = re.compile(r"(?:settings\s*\.\s*API_TOKEN|\bAPI_TOKEN\b)")
    for path in _frontend_files(plugin_dir):
        for line_number, line in enumerate(_read_text(path).splitlines(), start=1):
            if token_pattern.search(line):
                frontend_token_hits.append(f"{path}:{line_number}")
    checks.append(
        _check(
            "security.frontend_token",
            "security",
            "前端不读取宿主 API Token",
            0.25,
            0.0 if frontend_token_hits else 0.25,
            _status(0.0 if frontend_token_hits else 0.25, 0.25, blocker=bool(frontend_token_hits)),
            severity="blocker" if frontend_token_hits else "info",
            evidence=_relative(repo, frontend_token_hits),
            recommendation="通过宿主注入的 api prop 调用接口，不向浏览器暴露 API_TOKEN。",
        )
    )

    if not has_api:
        auth_points = 0.25
        auth_evidence: tuple[str, ...] = ("插件未声明动态 API",)
    elif vue_mode and re.search(r"['\"]auth['\"]\s*:\s*['\"]bear['\"]", all_source):
        auth_points = 0.25
        auth_evidence = ("Vue API bearer 鉴权已声明",)
    elif re.search(r"['\"]auth['\"]\s*:", all_source):
        auth_points = 0.125
        auth_evidence = ("API 已显式鉴权，但未确认全部 Vue 路由为 bearer",)
    elif vue_mode:
        auth_points = 0.0
        auth_evidence = ("Vue 模式存在 API，但未发现显式 bearer 鉴权",)
    else:
        auth_points = 0.25
        auth_evidence = ("非 Vue API 使用宿主默认 apikey 边界",)
    checks.append(
        _check(
            "security.api_auth",
            "security",
            "动态 API 鉴权边界明确",
            0.25,
            auth_points,
            _status(auth_points, 0.25),
            evidence=auth_evidence,
            recommendation="Vue 前端路由显式使用 bearer；其它路由确认 apikey 或权限合同。",
        )
    )

    checks.append(
        _check(
            "tests.syntax",
            "tests",
            "全部 Python 源码可完成 AST 解析",
            0.5,
            0.0 if parse_errors else 0.5,
            _status(0.0 if parse_errors else 0.5, 0.5, blocker=bool(parse_errors)),
            severity="blocker" if parse_errors else "info",
            evidence=_relative(repo, parse_errors),
            recommendation="先修复语法或编码错误，再执行任何运行态验收。",
        )
    )

    test_files, test_cases, test_parse_errors = _test_inventory(test_dir)
    required_cases = max(3, min(30, math.ceil(max(total_lines, 1) / 600)))
    test_ratio = min(1.0, test_cases / required_cases) if required_cases else 1.0
    test_points = 0.75 * test_ratio
    test_evidence = (
        f"{len(test_files)} 个测试文件，{test_cases} 个测试函数，建议基线 {required_cases}",
        *test_parse_errors,
    )
    checks.append(
        _check(
            "tests.inventory",
            "tests",
            "V3 测试库存与源码规模相称",
            0.75,
            test_points,
            _status(test_points, 0.75),
            evidence=test_evidence,
            recommendation="在 tests/v3/<plugin>/ 增加生命周期、错误分支和关键合同测试。",
        )
    )

    public_total, public_compliant, missing_docstrings = _public_docstring_stats(trees)
    doc_ratio = public_compliant / public_total if public_total else 1.0
    doc_points = 0.5 * doc_ratio
    checks.append(
        _check(
            "tests.docstrings",
            "tests",
            "公共符号具备中文文档字符串",
            0.5,
            doc_points,
            _status(doc_points, 0.5),
            evidence=(
                f"{public_compliant}/{public_total} 个公共符号合规",
                *_relative(repo, missing_docstrings[:20]),
            ),
            recommendation="为公共类、函数和方法补充简洁中文 docstring。",
        )
    )

    if vue_mode:
        assets_dir = plugin_dir / "dist/assets"
        other_assets = [
            path for path in assets_dir.glob("*") if path.is_file() and path != remote_entry
        ]
        asset_ok = remote_entry.is_file() and remote_entry.stat().st_size > 0 and bool(other_assets)
        asset_evidence = (
            f"remoteEntry={remote_entry.is_file()}，关联资产={len(other_assets)}",
        )
    else:
        asset_ok = True
        asset_evidence = ("非 Vue 联邦插件",)
    checks.append(
        _check(
            "tests.frontend_assets",
            "tests",
            "Vue 联邦运行产物完整",
            0.25,
            0.25 if asset_ok else 0.0,
            _status(0.25 if asset_ok else 0.0, 0.25),
            evidence=asset_evidence,
            recommendation="重新构建并保留 remoteEntry.js 及其引用的全部资产。",
        )
    )

    package_version = str(metadata.get("version") or "").strip()
    history = metadata.get("history")
    history_keys = list(history) if isinstance(history, dict) else []
    version_conditions = [
        (
            bool(SEMVER_RE.fullmatch(package_version)),
            f"package version={package_version or '<空>'}",
        ),
        (
            attributes.get("plugin_version") == package_version,
            f"plugin_version={attributes.get('plugin_version')!r}",
        ),
        (
            bool(history_keys) and history_keys[0] == f"v{package_version}",
            f"history 首项={history_keys[0] if history_keys else '<空>'}",
        ),
        (
            metadata.get("system_version") == ">=3.0.0",
            f"system_version={metadata.get('system_version')!r}",
        ),
    ]
    version_passed = sum(1 for passed, _ in version_conditions if passed)
    version_points = 0.3 * version_passed / len(version_conditions)
    version_failures = [label for passed, label in version_conditions if not passed]
    version_blocker = version_passed != len(version_conditions)
    checks.append(
        _check(
            "metadata.version",
            "metadata",
            "版本、history 与系统代际一致",
            0.3,
            version_points,
            _status(version_points, 0.3, blocker=version_blocker),
            severity="blocker" if version_blocker else "info",
            evidence=version_failures or tuple(label for _, label in version_conditions),
            recommendation="同步 plugin_version、package version、当前 history 和 system_version。",
        )
    )

    required_metadata = ("name", "description", "version", "icon", "author", "level", "history")
    missing_metadata = [key for key in required_metadata if metadata.get(key) in (None, "")]
    field_mapping = {
        "name": "plugin_name",
        "description": "plugin_desc",
        "icon": "plugin_icon",
        "author": "plugin_author",
        "labels": "plugin_label",
        "level": "auth_level",
    }
    mismatches: list[str] = []
    comparable = 0
    for package_key, class_key in field_mapping.items():
        if package_key not in metadata or class_key not in attributes:
            continue
        comparable += 1
        if str(metadata[package_key]).strip() != str(attributes[class_key]).strip():
            mismatches.append(f"{package_key} != {class_key}")
    presence_ratio = (len(required_metadata) - len(missing_metadata)) / len(required_metadata)
    match_ratio = (comparable - len(mismatches)) / comparable if comparable else 1.0
    metadata_points = 0.1 * presence_ratio + 0.1 * match_ratio
    checks.append(
        _check(
            "metadata.fields",
            "metadata",
            "package 元数据与类属性一致",
            0.2,
            metadata_points,
            _status(metadata_points, 0.2),
            evidence=tuple([*(f"缺少 {key}" for key in missing_metadata), *mismatches]),
            recommendation="补齐市场字段，并同步插件类中的名称、描述、图标、作者和权限。",
        )
    )

    checks.append(
        _check(
            "runtime.acceptance",
            "runtime",
            "真实 V3 宿主安装与运行态验收",
            1.0,
            0.0,
            "unverified",
            severity="unverified",
            evidence=("本规则版本仅生成 L1 静态证据",),
            recommendation="后续绑定当前 tree hash 的安装、GET reload、history/status/API 证据。",
        )
    )

    readme = plugin_dir / "README.md"
    checks.append(
        _check(
            "documentation.readme",
            "documentation",
            "插件目录包含使用说明",
            0.2,
            0.2 if readme.is_file() else 0.0,
            _status(0.2 if readme.is_file() else 0.0, 0.2),
            evidence=("README.md" if readme.is_file() else "缺少 README.md",),
            recommendation="补充用途、配置、限制和常见故障说明。",
        )
    )

    complex_plugin = total_lines > 1000 or len(files) > 10
    context_file = plugin_dir / "ai_spec/plugin_context.md"
    context_ok = not complex_plugin or context_file.is_file()
    checks.append(
        _check(
            "documentation.context",
            "documentation",
            "复杂插件维护上下文完整",
            0.3,
            0.3 if context_ok else 0.0,
            _status(0.3 if context_ok else 0.0, 0.3),
            evidence=(
                "简单插件无需 ai_spec/plugin_context.md"
                if not complex_plugin
                else "ai_spec/plugin_context.md 已存在"
                if context_file.is_file()
                else "复杂插件缺少 ai_spec/plugin_context.md",
            ),
            recommendation="记录入口、调用链、关键数据、禁止区域和验收方式。",
        )
    )

    dimensions: dict[str, dict[str, float]] = {}
    for dimension, maximum in DIMENSION_MAX.items():
        points = sum(item.points for item in checks if item.dimension == dimension)
        dimensions[dimension] = {"score": round(points, 3), "max": maximum}

    quality_max_score = round(
        sum(maximum for name, maximum in DIMENSION_MAX.items() if name != "runtime"),
        3,
    )
    quality_raw_score = round(
        sum(item.points for item in checks if item.dimension != "runtime"), 3
    )
    quality_score = round(
        min(quality_raw_score / quality_max_score * 10.0, 10.0)
        if quality_max_score
        else 0.0,
        2,
    )
    blockers = [item for item in checks if item.severity == "blocker" and item.status == "blocked"]

    def _grade(value: float) -> str:
        if value >= 9:
            return "A"
        if value >= 8:
            return "B"
        if value >= 7:
            return "C"
        if value >= 6:
            return "D"
        return "F"

    quality_grade = _grade(quality_score)
    readiness = "blocked" if blockers else "static_only"

    return {
        "rule_version": RULE_VERSION,
        "plugin_id": plugin_id,
        "generation": "v3",
        "plugin_version": package_version,
        "quality_score": quality_score,
        "quality_raw_score": quality_raw_score,
        "quality_max_score": quality_max_score,
        "grade": quality_grade,
        "readiness": readiness,
        "evidence_level": "L1",
        "blocker_count": len(blockers),
        "blockers": [item.check_id for item in blockers],
        "git_sha": _git_sha(repo),
        "tree_sha256": _tree_hash(repo, plugin_dir, test_dir, metadata),
        "dimensions": dimensions,
        "checks": [
            {**asdict(item), "deduction": item.deduction}
            for item in checks
        ],
    }


def score_repository(repo: Path, plugin_ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """读取 package.v3.json 并为选定插件生成报告。"""
    package_path = repo / PACKAGE_FILE
    if not package_path.is_file():
        raise FileNotFoundError(f"缺少 {package_path}")
    package = _load_json(package_path)
    requested = list(plugin_ids or package.keys())
    lookup = {plugin_id.lower(): plugin_id for plugin_id in package}
    selected: list[str] = []
    unknown: list[str] = []
    for value in requested:
        for item in str(value).split(","):
            normalized = item.strip().lower()
            if not normalized:
                continue
            plugin_id = lookup.get(normalized)
            if plugin_id is None:
                unknown.append(item.strip())
            elif plugin_id not in selected:
                selected.append(plugin_id)
    if unknown:
        raise ValueError(f"package.v3.json 中不存在插件: {', '.join(unknown)}")
    return [score_plugin(repo, plugin_id, package[plugin_id]) for plugin_id in selected]


def _deductions(report: dict[str, Any]) -> list[dict[str, Any]]:
    """返回有扣分或阻断意义的检查项。"""
    return [
        item
        for item in report["checks"]
        if item["deduction"] > 0 or item["severity"] in {"blocker", "unverified"}
    ]


def render_text(reports: list[dict[str, Any]], *, details: bool = False) -> str:
    """渲染适合终端阅读的中文报告。"""
    lines = [f"MoviePilot V3 插件试行评分规则 v{RULE_VERSION}"]
    for report in reports:
        lines.append("")
        lines.append(
            f"{report['plugin_id']} 规范质量 {report['quality_score']:.2f}/10 ({report['grade']}) | "
            f"{report['readiness']} | {report['evidence_level']} | "
            f"阻断项 {report['blocker_count']} | tree {report['tree_sha256'][:12]}"
        )
        items = report["checks"] if details else _deductions(report)
        for item in items:
            marker = "!" if item["severity"] == "blocker" else "-"
            lines.append(
                f"  {marker} [{item['dimension']}] {item['title']}: "
                f"{item['points']:.3f}/{item['max_points']:.3f} ({item['status']})"
            )
            for evidence in item["evidence"][:5]:
                lines.append(f"      证据: {evidence}")
            if item["recommendation"] and (details or item["deduction"] > 0):
                lines.append(f"      建议: {item['recommendation']}")
    return "\n".join(lines) + "\n"


def render_markdown(reports: list[dict[str, Any]]) -> str:
    """渲染可用于 PR 或构建产物的 Markdown 报告。"""
    lines = [
        f"# MoviePilot V3 插件试行评分 v{RULE_VERSION}",
        "",
        "| 插件 | 规范质量分 | 等级 | 状态 | 证据 | 阻断项 | Tree |",
        "| --- | ---: | --- | --- | --- | ---: | --- |",
    ]
    for report in reports:
        lines.append(
            f"| {report['plugin_id']} | {report['quality_score']:.2f}/10 ({report['grade']}) | "
            f"{report['readiness']} | {report['evidence_level']} | {report['blocker_count']} | "
            f"`{report['tree_sha256'][:12]}` |"
        )
    for report in reports:
        lines.extend(["", f"## {report['plugin_id']}", ""])
        deductions = _deductions(report)
        if not deductions:
            lines.append("无扣分项。")
            continue
        for item in deductions:
            lines.append(
                f"- `{item['check_id']}` {item['points']:.3f}/{item['max_points']:.3f}: "
                f"{item['title']} ({item['status']})"
            )
            if item["recommendation"]:
                lines.append(f"  建议：{item['recommendation']}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    """创建命令行解析器。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="插件仓根目录")
    parser.add_argument(
        "--plugin",
        action="append",
        help="仅评分指定插件；可重复传入或使用逗号分隔",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json", "markdown"),
        default="text",
        help="报告格式",
    )
    parser.add_argument("--output", type=Path, help="可选输出文件；默认写 stdout")
    parser.add_argument("--details", action="store_true", help="文本格式显示全部检查项")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="出现阻断项或低于 minimum 时返回 1；试行阶段默认关闭",
    )
    parser.add_argument("--minimum", type=float, default=8.0, help="strict 最低分")
    return parser


def main(argv: list[str] | None = None) -> int:
    """执行评分并按请求格式输出。"""
    args = build_parser().parse_args(argv)
    try:
        reports = score_repository(args.repo.resolve(), args.plugin)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        print(f"插件评分失败: {error}", file=sys.stderr)
        return 2

    if args.format == "json":
        content = json.dumps(
            {"rule_version": RULE_VERSION, "reports": reports},
            ensure_ascii=False,
            indent=2,
        ) + "\n"
    elif args.format == "markdown":
        content = render_markdown(reports)
    else:
        content = render_text(reports, details=args.details)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")

    if args.strict and any(
        report["blocker_count"] or report["quality_score"] < args.minimum for report in reports
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
