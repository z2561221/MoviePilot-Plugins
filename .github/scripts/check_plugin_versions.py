"""校验各代插件索引与源码元数据版本一致。"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Iterable, Optional


PACKAGE_LAYOUTS = {
    "package.json": "plugins",
    "package.v2.json": "plugins.v2",
    "package.v3.json": "plugins.v3",
}


def read_json(path: Path) -> dict:
    """读取 JSON 对象文件。"""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def source_plugin_version(path: Path) -> Optional[str]:
    """通过 AST 读取插件类的 plugin_version 常量。"""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if any(isinstance(target, ast.Name) and target.id == "plugin_version" for target in targets):
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
    return None


def check_package(repo_root: Path, package_path: Path, plugin_ids: Optional[set[str]] = None) -> list[str]:
    """校验一个索引文件对应代际的插件版本。"""
    plugin_root_name = PACKAGE_LAYOUTS.get(package_path.name)
    if not plugin_root_name:
        return [f"unsupported package index: {package_path.name}"]
    package = read_json(package_path)
    errors = []
    for plugin_id, metadata in package.items():
        if plugin_ids and plugin_id not in plugin_ids:
            continue
        plugin_dir = repo_root / plugin_root_name / plugin_id.lower()
        init_file = plugin_dir / "__init__.py"
        if not init_file.is_file():
            errors.append(f"{package_path.name}:{plugin_id}: missing {init_file.relative_to(repo_root)}")
            continue
        expected = str((metadata or {}).get("version") or "")
        actual = source_plugin_version(init_file)
        if not expected or actual != expected:
            errors.append(f"{package_path.name}:{plugin_id}: index={expected!r} source={actual!r}")
        for metadata_name in ("plugin.json", "package.json"):
            metadata_path = plugin_dir / metadata_name
            if not metadata_path.is_file():
                continue
            local_version = str(read_json(metadata_path).get("version") or "")
            if local_version and local_version != expected:
                errors.append(
                    f"{package_path.name}:{plugin_id}: {metadata_name}={local_version!r} index={expected!r}"
                )
    return errors


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_files", nargs="+", type=Path)
    parser.add_argument("--plugin", action="append", default=[])
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    """运行版本一致性校验并返回进程退出码。"""
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path.cwd().resolve()
    selected = {value for value in args.plugin if value} or None
    errors = []
    for raw_path in args.package_files:
        package_path = raw_path if raw_path.is_absolute() else repo_root / raw_path
        if not package_path.is_file():
            errors.append(f"missing package index: {package_path}")
            continue
        errors.extend(check_package(repo_root, package_path, selected))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Plugin versions are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
