from __future__ import annotations

import ast
import types
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"


def _load_retry_dirty_function():
    source = (PLUGIN_DIR / "modules" / "transfer.py").read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    retry_func = next(
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name == "retry_dirty_torrent_names"
    )
    compiled = compile(ast.Module(body=[retry_func], type_ignores=[]), "transfer_retry_dirty", "exec")
    namespace = {
        "ServiceInfo": object,
        "logger": types.SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
        ),
        "is_dirty_renamed_torrent_name": _dirty_name_detector,
    }
    exec(compiled, namespace)
    return namespace["retry_dirty_torrent_names"]


def _load_retry_functions():
    source = (PLUGIN_DIR / "modules" / "transfer.py").read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    retry_funcs = [
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"retry_pending_renames", "retry_dirty_torrent_names"}
    ]
    compiled = compile(ast.Module(body=retry_funcs, type_ignores=[]), "transfer_retry", "exec")
    namespace = {
        "ServiceInfo": object,
        "logger": types.SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
        ),
        "is_dirty_renamed_torrent_name": _dirty_name_detector,
    }
    exec(compiled, namespace)
    return namespace


def _load_retry_rename_by_hash_function():
    source = (PLUGIN_DIR / "modules" / "rename.py").read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    required_names = {"_get_torrent_name", "_get_tracker_urls", "retry_rename_by_hash"}
    retry_funcs = [
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name in required_names
    ]
    present_names = {node.name for node in retry_funcs}
    missing_names = required_names - present_names
    if missing_names:
        raise AssertionError(f"missing helper functions: {sorted(missing_names)}")
    compiled = compile(ast.Module(body=retry_funcs, type_ignores=[]), "rename_retry_single", "exec")
    namespace = {
        "logger": types.SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
        ),
        "get_hash": lambda torrent, dl_type: torrent.get("hash"),
        "get_label": lambda torrent, dl_type: [
            label.strip() for label in torrent.get("tags", "").split(",") if label.strip()
        ],
        "get_save_path": lambda torrent, dl_type: torrent.get("save_path"),
    }
    exec(compiled, namespace)
    return namespace["retry_rename_by_hash"]


def _dirty_name_detector(value: str) -> bool:
    original = str(value or "")
    return " | " in original or "\u7c7b\u578b" in original or "\u4e3b\u6f14" in original


class FakeQbTorrent(dict):
    pass


class FakeDownloader:
    def __init__(self, torrents):
        self._torrents = torrents
        self.queried_ids = None

    def get_torrents(self, ids=None):
        self.queried_ids = ids
        return self._torrents, None


class FakePlugin:
    _rename_enabled = True

    def __init__(self, fail_hashes=None):
        self.fail_hashes = set(fail_hashes or [])
        self.renamed = []
        self.service = None
        self._todownloader = "QB2"
        self.failed_retry_count = 0

    def get_hash(self, torrent, dl_type):
        return torrent.get("hash")

    def get_save_path(self, torrent, dl_type):
        return torrent.get("save_path")

    def _rename_torrent(self, dl, dl_type, torrent_hash, torrent_name, save_path):
        if torrent_hash in self.fail_hashes:
            raise RuntimeError("rename boom")
        self.renamed.append((torrent_hash, torrent_name, save_path))

    def service_info(self, downloader):
        return self.service

    def _retry_failed_renames(self, to_service):
        return self.failed_retry_count


class FakeSingleRetryPlugin:
    _rename_enabled = True
    _tag_enabled = True

    def __init__(self):
        self.renamed = []
        self.tagged = []

    def _rename_torrent(self, dl, dl_type, torrent_hash, torrent_name, save_path):
        self.renamed.append((dl_type, torrent_hash, torrent_name, save_path))

    def _tag_torrent(self, dl, dl_type, torrent_hash, torrent_tags, trackers):
        self.tagged.append((dl_type, torrent_hash, torrent_tags, trackers))


class DownloadManagerLocalStabilityBaselineTest(unittest.TestCase):
    def test_init_has_no_duplicate_relative_import_lines(self) -> None:
        init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
        relative_imports = [
            line.strip()
            for line in init_source.splitlines()
            if line.strip().startswith("from .")
        ]

        duplicates = sorted(
            {line for line in relative_imports if relative_imports.count(line) > 1}
        )

        self.assertEqual(duplicates, [])

    def test_dirty_rename_scan_skips_clean_and_hashless_torrents(self) -> None:
        retry_dirty_torrent_names = _load_retry_dirty_function()
        plugin = FakePlugin()
        service = types.SimpleNamespace(
            type="qbittorrent",
            instance=FakeDownloader(
                [
                    {
                        "name": (
                            "[ Cang Yuan Tu (2023) - S01E82 ] - Azure Legacy S01E82 "
                            "2023 2160p WEB-DL H265 AAC-ADWeb\u6ca7\u5143\u56fe "
                            "\u7b2c82\u96c6 | \u7c7b\u578b\uff1a\u52a8\u4f5c"
                        ),
                        "save_path": "/downloads/dirty-no-hash",
                    },
                    {
                        "hash": "clean",
                        "name": (
                            "[ Cang Yuan Tu (2023) - S01E82 ] - Azure Legacy S01E82 "
                            "2023 2160p WEB-DL H265 AAC-ADWeb"
                        ),
                        "save_path": "/downloads/clean",
                    },
                    {
                        "hash": "dirty",
                        "name": (
                            "[ Beyond Time (2025) - S01E17 ] - Beyond Time s Gaze "
                            "S01E17 2025 2160p WEB-DL H265 AAC-ADWeb\u5149\u9634"
                            "\u4e4b\u5916 \u7b2c17\u96c6 | \u4e3b\u6f14\uff1aA"
                        ),
                        "save_path": "/downloads/dirty",
                    },
                ]
            ),
        )

        retry_dirty_torrent_names(plugin, service)

        self.assertEqual(
            plugin.renamed,
            [
                (
                    "dirty",
                    (
                        "[ Beyond Time (2025) - S01E17 ] - Beyond Time s Gaze "
                        "S01E17 2025 2160p WEB-DL H265 AAC-ADWeb\u5149\u9634"
                        "\u4e4b\u5916 \u7b2c17\u96c6 | \u4e3b\u6f14\uff1aA"
                    ),
                    "/downloads/dirty",
                )
            ],
        )

    def test_dirty_rename_scan_continues_after_one_rename_failure(self) -> None:
        retry_dirty_torrent_names = _load_retry_dirty_function()
        plugin = FakePlugin(fail_hashes={"broken"})
        service = types.SimpleNamespace(
            type="qbittorrent",
            instance=FakeDownloader(
                [
                    {
                        "hash": "broken",
                        "name": "Release S01E01 2026 2160p WEB-DL H265 AAC-GRP "
                        "\u5267\u96c6 \u7b2c1\u96c6 | \u7c7b\u578b\uff1a\u52a8\u753b",
                        "save_path": "/downloads/broken",
                    },
                    {
                        "hash": "second",
                        "name": "Release S01E02 2026 2160p WEB-DL H265 AAC-GRP "
                        "\u5267\u96c6 \u7b2c2\u96c6 | \u7c7b\u578b\uff1a\u52a8\u753b",
                        "save_path": "/downloads/second",
                    },
                ]
            ),
        )

        retry_dirty_torrent_names(plugin, service)

        self.assertEqual(len(plugin.renamed), 1)
        self.assertEqual(plugin.renamed[0][0], "second")

    def test_dirty_rename_scan_returns_success_count(self) -> None:
        retry_dirty_torrent_names = _load_retry_dirty_function()
        plugin = FakePlugin()
        service = types.SimpleNamespace(
            type="qbittorrent",
            instance=FakeDownloader(
                [
                    {
                        "hash": "dirty",
                        "name": "Release S01E01 2026 WEB-DL H265-GRP "
                        "\u7b2c1\u96c6 | \u7c7b\u578b\uff1a\u52a8\u753b",
                        "save_path": "/downloads/dirty",
                    },
                    {
                        "hash": "clean",
                        "name": "Release S01E02 2026 WEB-DL H265-GRP",
                        "save_path": "/downloads/clean",
                    },
                ]
            ),
        )

        self.assertEqual(retry_dirty_torrent_names(plugin, service), 1)

    def test_pending_rename_retry_returns_action_report_for_manual_api(self) -> None:
        retry_funcs = _load_retry_functions()
        retry_pending_renames = retry_funcs["retry_pending_renames"]
        plugin = FakePlugin()
        plugin.failed_retry_count = 2
        plugin.service = types.SimpleNamespace(
            type="qbittorrent",
            instance=FakeDownloader(
                [
                    {
                        "hash": "dirty",
                        "name": "Release S01E01 2026 WEB-DL H265-GRP "
                        "\u7b2c1\u96c6 | \u7c7b\u578b\uff1a\u52a8\u753b",
                        "save_path": "/downloads/dirty",
                    }
                ]
            ),
        )

        report = retry_pending_renames(plugin)

        self.assertEqual(report["code"], 0)
        self.assertEqual(report["history"], 2)
        self.assertEqual(report["dirty"], 1)
        self.assertEqual(report["total"], 3)

    def test_single_hash_retry_queries_only_that_torrent_and_reapplies_actions(self) -> None:
        retry_rename_by_hash = _load_retry_rename_by_hash_function()
        torrent = FakeQbTorrent(
            hash="hash-one",
            name="Release S01E01 2026 WEB-DL H265-GRP",
            save_path="/downloads/show",
            tags="old,seed",
        )
        torrent.trackers = [{"tier": 0, "url": "https://tracker.example/announce"}]
        downloader = FakeDownloader([torrent])
        plugin = FakeSingleRetryPlugin()
        service = types.SimpleNamespace(type="qbittorrent", instance=downloader)

        report = retry_rename_by_hash(plugin, service, "hash-one")

        self.assertEqual(report["code"], 0)
        self.assertEqual(downloader.queried_ids, ["hash-one"])
        self.assertEqual(
            plugin.renamed,
            [
                (
                    "qbittorrent",
                    "hash-one",
                    "Release S01E01 2026 WEB-DL H265-GRP",
                    "/downloads/show",
                )
            ],
        )
        self.assertEqual(
            plugin.tagged,
            [
                (
                    "qbittorrent",
                    "hash-one",
                    ["old", "seed"],
                    ["https://tracker.example/announce"],
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
