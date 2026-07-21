from __future__ import annotations

import ast
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"

SERVICE_EXPORTS = {
    "archive.py": {
        "clear_rename_retry_state",
        "delete_rename_archive",
        "is_rename_archived",
        "list_rename_archive",
        "record_rename_failure",
        "rename_archive_stats",
        "restore_rename_archive",
    },
    "diagnostics.py": {"build_diagnostics"},
    "iyuu.py": {
        "append_iyuu_cache",
        "custom_sites",
        "iyuu_auto_seed",
        "iyuu_auto_service_info",
        "iyuu_download",
        "iyuu_download_torrent",
        "iyuu_get_download_url",
        "iyuu_save_history",
        "iyuu_seed_torrents",
        "iyuu_service_infos",
        "trim_seed_cache",
        "update_iyuu_config",
    },
    "recheck.py": {
        "can_seed_paused_torrent",
        "ensure_seed_recheck_worker",
        "load_seed_recheck_queue",
        "process_seed_recheck_once",
        "register_seed_recheck",
        "run_recheck_cycle",
        "save_seed_recheck_queue",
        "seed_is_checking",
        "seed_is_error",
        "seed_is_ready",
        "seed_is_timeout",
        "seed_recheck_loop",
        "seed_should_remove_missing",
        "sweep_paused_seed_tasks",
    },
    "rename.py": {
        "format_torrent_name",
        "get_failed_rename_hashes",
        "rename_iyuu_torrent_by_source_record",
        "rename_torrent",
        "retry_failed_renames",
        "retry_rename_by_hash",
        "save_rename_record",
    },
    "site_tag.py": {
        "create_temporary_tag",
        "execute_tag_cleanup",
        "find_site_by_domain",
        "forget_temporary_tag",
        "release_temporary_tag",
        "scan_and_clean_tags",
        "tag_torrent",
    },
    "transfer.py": {
        "delayed_transfer",
        "download_torrent",
        "fallback_transfer",
        "post_transfer_process",
        "retry_pending_renames",
        "transfer",
        "validate_config",
    },
    "cleanup.py": {
        "cleanup_by_hash",
        "cleanup_by_path",
        "handle_plugin_action_event",
        "handle_sync_delete_by_hash_event",
        "handle_webhook_message_event",
    },
}


def _assigned_all(module: ast.Module) -> set[str]:
    """读取模块级 __all__ 导出集合。"""
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            continue
        assert isinstance(node.value, (ast.Tuple, ast.List))
        return {
            item.value
            for item in node.value.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        }
    return set()


def _has_chinese(text: str) -> bool:
    """判断文本中是否包含中文字符。"""
    return any("\u4e00" <= char <= "\u9fff" for char in text or "")


def test_downloadmanagerlocal_service_facades_declare_public_exports():
    for filename, expected_exports in SERVICE_EXPORTS.items():
        source = (PLUGIN_DIR / "service" / filename).read_text(encoding="utf-8")
        module = ast.parse(source)

        assert _assigned_all(module) == expected_exports


def test_downloadmanagerlocal_new_public_helpers_have_chinese_docstrings():
    checked_files = [
        PLUGIN_DIR / "adapter" / "moviepilot.py",
        PLUGIN_DIR / "model" / "state.py",
    ]
    missing = []
    for path in checked_files:
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in module.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
                docstring = ast.get_docstring(node) or ""
                if not _has_chinese(docstring):
                    missing.append(f"{path.relative_to(REPO).as_posix()}::{node.name}")

    assert missing == []
