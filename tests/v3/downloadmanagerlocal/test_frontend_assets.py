"""构建清单只选择安全完整的内容目录，旧版本及坏清单保留原路径。"""

import hashlib
import json
from copy import deepcopy

import pytest
from app.plugins.downloadmanagerlocal.model.frontend_assets import (
    LEGACY_ASSETS_PATH,
    federation_assets_path,
)


def build(root):
    files = {"remoteEntry.js": b"entry", "nested/image.png": b"image"}
    hashes = sorted((name, hashlib.sha256(content).hexdigest()) for name, content in files.items())
    revision = hashlib.sha256(json.dumps(hashes, separators=(",", ":")).encode()).hexdigest()
    path = f"dist/assets/r{revision}"
    for name, content in files.items():
        target = root / path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    manifest = {"schema_version": 1, "path": path, "revision": revision, "files": dict(hashes)}
    save(root, manifest)
    return manifest


def save(root, manifest):
    (root / "dist/federation.json").write_bytes((json.dumps(manifest, ensure_ascii=False) + "\n").encode("utf-8"))


def test_valid_content_path_matches_host_entry_contract(tmp_path):
    manifest = build(tmp_path)
    assert federation_assets_path(tmp_path) == manifest["path"]
    assert (tmp_path / manifest["path"] / "remoteEntry.js").is_file()


def test_old_build_without_manifest_keeps_legacy_path(tmp_path):
    assert federation_assets_path(tmp_path) == LEGACY_ASSETS_PATH


@pytest.mark.parametrize("broken", [None, [], "invalid", {}, {"schema_version": 2}])
def test_malformed_manifest_cannot_select_a_path(tmp_path, broken):
    build(tmp_path)
    save(tmp_path, broken)
    assert federation_assets_path(tmp_path) == LEGACY_ASSETS_PATH


@pytest.mark.parametrize("change", [
    {"path": "../outside"}, {"path": "dist/assets"}, {"revision": "../../outside"},
    {"files": {"remoteEntry.js": "a" * 64, "../outside": "b" * 64}},
    {"files": {"remoteEntry.js": "a" * 64, "C:/outside": "b" * 64}},
    {"files": {"remoteEntry.js": "a" * 64, "nested\\image.png": "b" * 64}},
    {"files": {"remoteEntry.js": "a" * 64, "nested//image.png": "b" * 64}},
    {"files": {"remoteEntry.js": "a" * 64}},
])
def test_path_and_digest_conflicts_use_safe_fallback(tmp_path, change):
    manifest = build(tmp_path)
    manifest.update(deepcopy(change))
    save(tmp_path, manifest)
    assert federation_assets_path(tmp_path) == LEGACY_ASSETS_PATH


def test_missing_directory_or_asset_does_not_publish_partial_build(tmp_path):
    manifest = build(tmp_path)
    (tmp_path / manifest["path"] / "nested/image.png").unlink()
    assert federation_assets_path(tmp_path) == LEGACY_ASSETS_PATH
    manifest["path"] = f"dist/assets/r{'a' * 64}"
    manifest["revision"] = "a" * 64
    save(tmp_path, manifest)
    assert federation_assets_path(tmp_path) == LEGACY_ASSETS_PATH


def test_invalid_json_is_not_treated_as_ready(tmp_path):
    build(tmp_path)
    (tmp_path / "dist/federation.json").write_bytes(b"{invalid")
    assert federation_assets_path(tmp_path) == LEGACY_ASSETS_PATH


def test_production_render_hook_selects_shipped_revision():
    from pathlib import Path

    from app.plugins.downloadmanagerlocal import DownloadManagerLocal

    root = Path(__file__).resolve().parents[3] / "plugins.v3/downloadmanagerlocal"
    manifest = json.loads((root / "dist/federation.json").read_text(encoding="utf-8"))
    assert DownloadManagerLocal.get_render_mode() == ("vue", manifest["path"])
    assert manifest["path"].startswith("dist/assets/r")
