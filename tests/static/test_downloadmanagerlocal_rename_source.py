from __future__ import annotations

import ast
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
RENAME_PATH = REPO / "plugins.v2" / "downloadmanagerlocal" / "service" / "rename.py"


def _function_source(name: str) -> str:
    """读取指定重命名辅助函数的源码。"""
    module = ast.parse(RENAME_PATH.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(RENAME_PATH.read_text(encoding="utf-8"), node) or ""
    raise AssertionError(f"missing function: {name}")


def test_rename_meta_prioritizes_original_torrent_name_and_preserves_episode_signal():
    """重命名元数据必须优先保留种子原始名中的 S01E20。"""
    source = _function_source("_build_rename_meta")

    assert "current_name = clean_torrent_original_name(torrent_name).strip()" in source
    assert "source_name = current_name or history_name" in source
    assert "history_meta = MetaInfo(title=f\"{history_season}{history_episode}\"" in source


def test_rename_history_branch_uses_shared_meta_builder():
    """下载历史分支也必须走原始种子名优先的元数据构造器。"""
    source = RENAME_PATH.read_text(encoding="utf-8")

    assert "meta = _build_rename_meta(torrent_name, downloadhis)" in source
    assert "meta = MetaInfo(title=history_name or downloadhis.torrent_name" not in source
