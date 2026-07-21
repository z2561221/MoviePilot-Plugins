from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable

PACKAGE_FILE = "package.v2.json"
LOCAL_PACKAGE_FILE = "package.local.v2.json"
PLUGINS_DIR = "plugins.v2"
ICONS_DIR = "icons"
DEFAULT_TARGET = Path(r"Z:\moviepilot-v2\config\local plugins")
IGNORE_NAMES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "__pycache__",
    "node_modules",
}
IGNORE_SUFFIXES = {".pyc", ".pyo", ".log"}


def read_package(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object keyed by plugin id")
    return data


def read_source_package(source_root: Path) -> dict:
    """读取在线索引与本地专用索引，并合并为同步清单。"""
    package = read_package(source_root / PACKAGE_FILE)
    local_package = read_package(source_root / LOCAL_PACKAGE_FILE)
    duplicate_ids = set(package).intersection(local_package)
    if duplicate_ids:
        names = ", ".join(sorted(duplicate_ids))
        raise ValueError(f"Plugin ids must not be duplicated across package indexes: {names}")
    package.update(local_package)
    return package


def write_package(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def plugin_dir_name(plugin_id: str) -> str:
    return plugin_id.lower()


def normalize_plugin_ids(source_package: dict, plugin_ids: Iterable[str] | None) -> list[str]:
    if not plugin_ids:
        return list(source_package.keys())

    aliases = {plugin_id.lower(): plugin_id for plugin_id in source_package}
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in plugin_ids:
        key = raw.strip()
        if not key:
            continue
        plugin_id = source_package.get(key) and key or aliases.get(key.lower())
        if not plugin_id:
            available = ", ".join(source_package.keys())
            raise KeyError(f"Unknown plugin '{raw}'. Available plugins: {available}")
        if plugin_id not in seen:
            normalized.append(plugin_id)
            seen.add(plugin_id)
    return normalized


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def safe_plugin_destination(target_root: Path, plugin_id: str) -> Path:
    plugins_root = (target_root / PLUGINS_DIR).resolve()
    destination = (plugins_root / plugin_dir_name(plugin_id)).resolve()
    if not is_relative_to(destination, plugins_root):
        raise ValueError(f"Unsafe plugin destination: {destination}")
    return destination


def ignore_transient_files(_directory: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        if name in IGNORE_NAMES or Path(name).suffix in IGNORE_SUFFIXES:
            ignored.add(name)
    return ignored


def copy_plugin_directory(source_root: Path, target_root: Path, plugin_id: str, dry_run: bool) -> str:
    source = source_root / PLUGINS_DIR / plugin_dir_name(plugin_id)
    destination = safe_plugin_destination(target_root, plugin_id)
    if not source.is_dir():
        raise FileNotFoundError(f"Missing source plugin directory: {source}")
    if dry_run:
        return f"plugin:{plugin_id}"

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not destination.is_dir():
            raise ValueError(f"Plugin destination exists but is not a directory: {destination}")
        if not is_relative_to(destination.resolve(), destination.parent.resolve()):
            raise ValueError(f"Refusing to remove unsafe destination: {destination}")
        shutil.rmtree(destination)
    shutil.copytree(source, destination, ignore=ignore_transient_files)
    return f"plugin:{plugin_id}"


def copy_icon(source_root: Path, target_root: Path, icon_name: str, dry_run: bool) -> str | None:
    if not icon_name or "://" in icon_name or Path(icon_name).name != icon_name:
        return None
    source = source_root / ICONS_DIR / icon_name
    if not source.is_file():
        return f"icon-missing:{icon_name}"
    if not dry_run:
        destination_dir = target_root / ICONS_DIR
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination_dir / icon_name)
    return f"icon:{icon_name}"


def sync_to_target(
    source_root: Path | str,
    target_root: Path | str,
    plugin_ids: Iterable[str] | None = None,
    *,
    dry_run: bool = False,
    include_icons: bool = True,
) -> list[str]:
    source_root = Path(source_root).resolve()
    target_root = Path(target_root).resolve()
    if not target_root.exists():
        raise FileNotFoundError(f"Target local plugin repo does not exist: {target_root}")

    source_package = read_source_package(source_root)
    target_package_path = target_root / PACKAGE_FILE
    target_package = read_package(target_package_path)
    selected_plugins = normalize_plugin_ids(source_package, plugin_ids)

    actions: list[str] = []
    for plugin_id in selected_plugins:
        actions.append(copy_plugin_directory(source_root, target_root, plugin_id, dry_run))
        if include_icons:
            icon_action = copy_icon(
                source_root,
                target_root,
                str(source_package[plugin_id].get("icon") or ""),
                dry_run,
            )
            if icon_action:
                actions.append(icon_action)

    for plugin_id in selected_plugins:
        target_package[plugin_id] = source_package[plugin_id]
        actions.append(f"package:{plugin_id}")

    if not dry_run:
        write_package(target_package_path, target_package)
    return actions


def split_plugin_args(values: Iterable[str] | None) -> list[str] | None:
    if values is None:
        return None
    plugins = []
    for value in values:
        plugins.extend(part.strip() for part in value.split(",") if part.strip())
    return plugins


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync selected local plugins into MoviePilot's local plugin repository."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Local MoviePilot-Plugins repository root.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(os.environ.get("MP_LOCAL_PLUGIN_REPO", str(DEFAULT_TARGET))),
        help="MoviePilot local plugin repository path, usually the SMB mapped path.",
    )
    parser.add_argument(
        "--plugin",
        action="append",
        help="Plugin id to sync. Repeat or comma-separate. Defaults to all local package entries.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned actions only.")
    parser.add_argument("--no-icons", action="store_true", help="Do not copy referenced icons.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        actions = sync_to_target(
            args.source,
            args.target,
            split_plugin_args(args.plugin),
            dry_run=args.dry_run,
            include_icons=not args.no_icons,
        )
    except Exception as exc:
        print(f"sync failed: {exc}", file=sys.stderr)
        return 1

    mode = "dry-run" if args.dry_run else "synced"
    print(f"{mode}: {args.source} -> {args.target}")
    for action in actions:
        print(f"- {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
