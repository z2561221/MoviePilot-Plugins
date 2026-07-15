from __future__ import annotations

import ast
import time
import types
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"
CLEANUP_SOURCE = PLUGIN_DIR / "service" / "cleanup.py"
INIT_SOURCE = PLUGIN_DIR / "__init__.py"


def _load_cleanup_namespace():
    """加载同步删除函数，使用测试替身隔离 MoviePilot 运行时。"""
    source = CLEANUP_SOURCE.read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    funcs = [
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef)
    ]
    namespace = {
        "Any": object,
        "Dict": dict,
        "Iterable": object,
        "List": list,
        "Optional": object,
        "logger": types.SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
        ),
        "iyuu_history_key": lambda source_hash: f"iyuu_{source_hash}",
        "get_download_hash_by_fullpath": lambda path: "",
        "time": time,
        "RECENT_CLEANUP_WINDOW_SECONDS": 30,
    }
    compiled = compile(ast.Module(body=funcs, type_ignores=[]), "downloadmanagerlocal_cleanup", "exec")
    exec(compiled, namespace)
    return namespace


class FakeDownloader:
    """记录删除请求的下载器替身。"""

    def __init__(self, name: str, calls: list):
        self.name = name
        self.calls = calls

    def delete_torrents(self, delete_file: bool, ids: list):
        self.calls.append((self.name, delete_file, list(ids)))
        return True


class FakePlugin:
    """提供同步删除服务所需的最小插件替身。"""

    _fromdownloader = "QB1"

    def __init__(self, data: dict):
        self.data = data
        self.delete_calls = []

    def get_data(self, key):
        return self.data.get(key)

    def service_info(self, downloader):
        return types.SimpleNamespace(
            name=downloader,
            instance=FakeDownloader(downloader, self.delete_calls),
        )


def test_cleanup_by_hash_deletes_transfer_target_and_iyuu_seeds_with_files():
    namespace = _load_cleanup_namespace()
    cleanup_by_hash = namespace["cleanup_by_hash"]
    plugin = FakePlugin({
        "QB1-src_hash": {
            "to_download": "QB2",
            "to_download_id": "transfer_hash",
        },
        "iyuu_src_hash": [
            {"downloader": "QB2", "torrents": ["seed_a", "seed_b"]},
        ],
    })

    result = cleanup_by_hash(plugin, "src_hash", downloader="QB1", trigger="test")

    assert result["source_hash"] == "src_hash"
    assert result["transfer_deleted"] == 1
    assert result["iyuu_deleted"] == 2
    assert plugin.delete_calls == [
        ("QB2", True, ["transfer_hash"]),
        ("QB2", True, ["seed_a", "seed_b"]),
    ]


def test_webhook_library_deleted_resolves_path_then_deletes_with_files():
    namespace = _load_cleanup_namespace()
    namespace["get_download_hash_by_fullpath"] = lambda path: "src_hash" if path == "/media/A.mkv" else ""
    handle_webhook_message_event = namespace["handle_webhook_message_event"]
    plugin = FakePlugin({
        "QB1-src_hash": {"to_download": "QB2", "to_download_id": "transfer_hash"},
    })
    event = types.SimpleNamespace(event_data=types.SimpleNamespace(
        channel="emby",
        event="library.deleted",
        item_path="/media/A.mkv",
    ))

    result = handle_webhook_message_event(plugin, event)

    assert result["source_hash"] == "src_hash"
    assert plugin.delete_calls == [("QB2", True, ["transfer_hash"])]


def test_plugin_action_networkdisk_delete_uses_hash_or_path_cleanup():
    namespace = _load_cleanup_namespace()
    handle_plugin_action_event = namespace["handle_plugin_action_event"]
    plugin = FakePlugin({
        "QB1-src_hash": {"to_download": "QB2", "to_download_id": "transfer_hash"},
        "iyuu_src_hash": [{"downloader": "QB2", "torrents": ["seed_a"]}],
    })
    event = types.SimpleNamespace(event_data={
        "action": "networkdisk_del",
        "hash": "src_hash",
        "downloader": "QB1",
    })

    result = handle_plugin_action_event(plugin, event)

    assert result["transfer_deleted"] == 1
    assert result["iyuu_deleted"] == 1
    assert plugin.delete_calls == [
        ("QB2", True, ["transfer_hash"]),
        ("QB2", True, ["seed_a"]),
    ]


def test_plugin_entry_registers_sync_delete_events():
    init_source = INIT_SOURCE.read_text(encoding="utf-8")

    assert "EventType.DownloadFileDeleted" in init_source
    assert "EventType.DownloadDeleted" in init_source
    assert "EventType.WebhookMessage" in init_source
    assert "EventType.PluginAction" in init_source
    assert "_handle_sync_delete_by_hash_event_impl" in init_source
