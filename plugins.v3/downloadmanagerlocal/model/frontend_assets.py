"""只解析本插件构建清单；旧版本或损坏清单退回已有兼容入口。"""

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

LEGACY_ASSETS_PATH = "dist/assets"


def federation_assets_path(plugin_root: Path) -> str:
    """接受完整、安全的内容目录；不从清单加载代码或访问任意外部路径。"""
    try:
        root = plugin_root.resolve()
        manifest_file = root / "dist/federation.json"
        if (manifest_file.is_symlink() or not manifest_file.is_file() or manifest_file.resolve() != manifest_file
                or manifest_file.stat().st_size > 1024 * 1024):
            return LEGACY_ASSETS_PATH
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
            return LEGACY_ASSETS_PATH
        revision = manifest.get("revision")
        if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{64}", revision):
            return LEGACY_ASSETS_PATH
        expected = f"dist/assets/r{revision}"
        if manifest.get("path") != expected:
            return LEGACY_ASSETS_PATH
        folder = root / expected
        if folder.is_symlink() or not folder.is_dir() or folder.resolve() != folder:
            return LEGACY_ASSETS_PATH
        files = manifest.get("files")
        if not isinstance(files, dict) or "remoteEntry.js" not in files or len(files) > 4096:
            return LEGACY_ASSETS_PATH
        for name, digest in files.items():
            if (not isinstance(name, str) or "\\" in name or ":" in name or name.startswith("/")
                    or any(part in ("", ".", "..") for part in name.split("/"))
                    or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                return LEGACY_ASSETS_PATH
            asset = folder / PurePosixPath(name)
            if (asset.is_symlink() or not asset.is_file() or not asset.is_relative_to(folder)
                    or asset.resolve() != asset):
                return LEGACY_ASSETS_PATH
        hashes = sorted(files.items(), key=lambda item: item[0].encode("utf-8"))
        encoded = json.dumps(hashes, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != revision:
            return LEGACY_ASSETS_PATH
        return expected
    except (OSError, ValueError, TypeError, UnicodeError):
        return LEGACY_ASSETS_PATH
