from __future__ import annotations

import ast
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ADAPTER_PATH = REPO / "plugins.v2" / "downloadmanagerlocal" / "utils" / "torrent_adapter.py"


def test_speed_monitor_adapter_declares_stable_snapshot_and_three_state_poll_result():
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    module = ast.parse(source)
    classes = {node.name for node in module.body if isinstance(node, ast.ClassDef)}
    functions = {node.name for node in module.body if isinstance(node, ast.FunctionDef)}

    assert {"TorrentSnapshot", "DownloaderPollResult"} <= classes
    assert {
        "normalize_torrent",
        "poll_success",
        "poll_error",
        "poll_downloader",
        "delete_torrent_with_files",
    } <= functions


def test_speed_monitor_delete_adapter_hard_codes_delete_file_true_at_downloader_call():
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    module = ast.parse(source)
    delete_func = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "delete_torrent_with_files"
    )
    calls = [
        node
        for node in ast.walk(delete_func)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "delete_torrents"
    ]

    assert len(calls) == 1
    keyword_values = {
        keyword.arg: keyword.value
        for keyword in calls[0].keywords
        if keyword.arg
    }
    assert ast.literal_eval(keyword_values["delete_file"]) is True


def test_speed_monitor_adapter_has_no_subscribe_assistant_dependency():
    source = ADAPTER_PATH.read_text(encoding="utf-8")

    assert "SubscribeAssistantEnhanced" not in source
    assert "subscribeassistantenhanced" not in source.lower()
