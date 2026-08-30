"""验证下载中心 V3 目录、索引与同步隔离合同。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ID = "DownloadManagerLocal"


def _load_sync_module():
    """从脚本路径加载同步模块，避免要求 scripts 为 Python 包。"""
    script = REPO_ROOT / "scripts/sync_to_mp_local.py"
    spec = importlib.util.spec_from_file_location("sync_to_mp_local", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v3_index_has_dedicated_download_manager() -> None:
    """V3 索引必须指向独立目录，并由旧索引阻止回退。"""
    package_v2 = json.loads((REPO_ROOT / "package.v2.json").read_text(encoding="utf-8"))
    package_v3 = json.loads((REPO_ROOT / "package.v3.json").read_text(encoding="utf-8"))
    metadata = package_v3[PLUGIN_ID]

    assert metadata["version"] == "3.3.3"
    assert metadata["system_version"] == ">=3.0.0"
    assert package_v2[PLUGIN_ID]["version"] == "3.2.9"
    assert package_v2[PLUGIN_ID]["v3"] is False
    assert (REPO_ROOT / "plugins.v3/downloadmanagerlocal/__init__.py").is_file()


def test_sync_generation_keeps_package_indexes_isolated(tmp_path: Path) -> None:
    """V3 同步只能写 package.v3.json/plugins.v3，不能污染 V2 索引。"""
    module = _load_sync_module()
    target = tmp_path / "local plugins"
    target.mkdir()
    (target / "package.v2.json").write_text(
        json.dumps({PLUGIN_ID: {"version": "3.2.9"}}),
        encoding="utf-8",
    )
    (target / "package.v3.json").write_text("{}\n", encoding="utf-8")

    actions = module.sync_to_target(
        REPO_ROOT,
        target,
        [PLUGIN_ID],
        generation="v3",
        include_icons=False,
    )

    package_v2 = json.loads((target / "package.v2.json").read_text(encoding="utf-8"))
    package_v3 = json.loads((target / "package.v3.json").read_text(encoding="utf-8"))
    assert package_v2[PLUGIN_ID]["version"] == "3.2.9"
    assert package_v3[PLUGIN_ID]["version"] == "3.3.3"
    assert (target / "plugins.v3/downloadmanagerlocal/__init__.py").is_file()
    assert not (target / "plugins.v2/downloadmanagerlocal").exists()
    assert f"plugin:{PLUGIN_ID}" in actions
