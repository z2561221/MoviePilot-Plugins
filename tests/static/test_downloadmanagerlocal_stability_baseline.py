from __future__ import annotations

import ast
import json
import re
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"


def _fake_bdecode(content):
    return {"info": {"name": "Original.Release.S01E01.2026.WEB-DL-GRP"}}


def _fake_folder_bdecode(content):
    return {
        "info": {
            "name": "污染原名 第1集 | 类型：动画",
            "files": [
                {"path": ["Clean.Release.S01E01.2026.WEB-DL-GRP", "episode.mkv"]},
            ],
        }
    }


def _fake_all_dirty_bdecode(content):
    return {
        "info": {
            "name": "污染原名 第1集 | 类型：动画",
            "files": [
                {"path": ["污染文件夹 第1集 | 类型：动画", "污染文件 第1集 | 主演：A.mkv"]},
            ],
        }
    }


def _test_clean_original_name(value: str) -> str:
    """测试用原始名清洗桩。"""
    cleaned = str(value or "").strip()
    while True:
        next_cleaned = re.sub(r"^\s*\[[^\]]+\]\s*(?:-\s*)*", "", cleaned).strip()
        next_cleaned = re.sub(r"^(?:-\s*)+", "", next_cleaned).strip()
        if next_cleaned == cleaned:
            break
        cleaned = next_cleaned
    cleaned = cleaned.split(" | ", 1)[0].strip()
    return cleaned


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
        "resolve_retry_original_name": lambda plugin, torrent_hash, current_name, content_name="": content_name or current_name,
        "_get_torrent_content_name": lambda torrent, dl_type: torrent.get("content_path", ""),
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
        "resolve_retry_original_name": lambda plugin, torrent_hash, current_name, content_name="": content_name or current_name,
        "_get_torrent_content_name": lambda torrent, dl_type: torrent.get("content_path", ""),
    }
    exec(compiled, namespace)
    return namespace


def _load_retry_rename_by_hash_function():
    source = (PLUGIN_DIR / "modules" / "rename.py").read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    required_names = {
        "_add_original_name_candidate",
        "_add_download_history_candidates",
        "_add_rename_record_candidates",
        "_add_torrent_file_candidates",
        "_build_original_name_candidate_items",
        "_get_bencoded_value",
        "_get_original_torrent_name_candidates",
        "_get_original_torrent_name",
        "_get_torrent_content_name",
        "_get_torrent_name",
        "_get_tracker_urls",
        "_path_name_candidate",
        "_score_original_name_candidate",
        "_to_text",
        "_find_iyuu_source_hash",
        "_find_iyuu_source_hash_from_files",
        "_is_iyuu_seed_tags",
        "rename_iyuu_torrent_by_source_record",
        "resolve_retry_original_name",
        "retry_rename_by_hash",
        "save_rename_record",
    }
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
        "Path": Path,
        "bdecode": _fake_bdecode,
        "clean_torrent_original_name": _test_clean_original_name,
        "is_polluted_original_name": lambda value: " | " in str(value or "") or "类型" in str(value or ""),
        "json": json,
        "re": re,
        "datetime": datetime,
    }
    exec(compiled, namespace)
    return namespace["retry_rename_by_hash"]


def _load_original_name_candidates_function():
    source = (PLUGIN_DIR / "modules" / "rename.py").read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    required_names = {
        "_add_original_name_candidate",
        "_add_download_history_candidates",
        "_add_rename_record_candidates",
        "_add_torrent_file_candidates",
        "_build_original_name_candidate_items",
        "_get_bencoded_value",
        "_get_original_torrent_name_candidates",
        "_to_text",
    }
    funcs = [
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name in required_names
    ]
    present_names = {node.name for node in funcs}
    missing_names = required_names - present_names
    if missing_names:
        raise AssertionError(f"missing helper functions: {sorted(missing_names)}")
    namespace = {
        "Path": Path,
        "bdecode": _fake_folder_bdecode,
        "clean_torrent_original_name": lambda value: str(value or "").strip(),
        "is_polluted_original_name": lambda value: " | " in str(value or "") or "类型" in str(value or ""),
        "logger": types.SimpleNamespace(warning=lambda *args, **kwargs: None),
    }
    exec(compile(ast.Module(body=funcs, type_ignores=[]), "rename_original_candidates", "exec"), namespace)
    return namespace["_get_original_torrent_name_candidates"]


def _dirty_name_detector(value: str) -> bool:
    original = str(value or "")
    return " | " in original or "\u7c7b\u578b" in original or "\u4e3b\u6f14" in original


class FakeQbTorrent(dict):
    pass


class FakeDownloader:
    def __init__(self, torrents):
        self._torrents = torrents
        self.queried_ids = None
        self.renamed = []
        self.qbc = self

    def get_torrents(self, ids=None):
        self.queried_ids = ids
        return self._torrents, None

    def torrents_rename(self, torrent_hash, new_torrent_name):
        self.renamed.append((torrent_hash, new_torrent_name))


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
    _fromtorrentpath = ""

    def __init__(self):
        self.renamed = []
        self.tagged = []
        self.data = {}

    def _rename_torrent(self, dl, dl_type, torrent_hash, torrent_name, save_path):
        self.renamed.append((dl_type, torrent_hash, torrent_name, save_path))

    def _tag_torrent(self, dl, dl_type, torrent_hash, torrent_tags, trackers):
        self.tagged.append((dl_type, torrent_hash, torrent_tags, trackers))

    def get_data(self, key):
        return self.data.get(key, {})

    def save_data(self, key, value):
        self.data[key] = value


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

    def test_dirty_rename_scan_summarizes_archived_skip_logs(self) -> None:
        source = (PLUGIN_DIR / "modules" / "transfer.py").read_text(encoding="utf-8")

        self.assertIn("archived_skip_count", source)
        self.assertIn("跳过已归档补刀记录 {archived_skip_count} 个", source)
        self.assertNotIn("跳过已归档补刀记录 hash=", source)

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

    def test_single_hash_retry_uses_original_torrent_info_name_for_rename(self) -> None:
        retry_rename_by_hash = _load_retry_rename_by_hash_function()
        with tempfile.TemporaryDirectory() as temp_dir:
            torrent_file = Path(temp_dir) / "hash-one.torrent"
            torrent_file.write_bytes(b"fake torrent content")
            torrent = FakeQbTorrent(
                hash="hash-one",
                name="[ Show (2026) - S01E01 ] - Dirty Current Name | 类型：动画",
                save_path="/downloads/show",
                tags="old,seed",
            )
            torrent.trackers = []
            downloader = FakeDownloader([torrent])
            plugin = FakeSingleRetryPlugin()
            plugin._fromtorrentpath = temp_dir
            service = types.SimpleNamespace(type="qbittorrent", instance=downloader)

            report = retry_rename_by_hash(plugin, service, "hash-one")

            self.assertEqual(report["code"], 0)
            self.assertEqual(
                plugin.renamed,
                [
                    (
                        "qbittorrent",
                        "hash-one",
                        "Original.Release.S01E01.2026.WEB-DL-GRP",
                        "/downloads/show",
                    )
                ],
            )

    def test_single_hash_retry_uses_qb_content_folder_when_torrent_name_is_stacked(self) -> None:
        retry_rename_by_hash = _load_retry_rename_by_hash_function()
        torrent = FakeQbTorrent(
            hash="hash-one",
            name=(
                "[ 进击的巨人 (2013) - S02 ] - [ 进击的巨人 (2013) - S02 ] - "
                "Attack on Titan S02 2017 1080p CR WEB-DL H.264 AAC 2.0-FROGWeb"
            ),
            content_path=(
                "/downloads/进击的巨人.Attack.on.Titan.S02.2017.1080p.CR.WEB-DL."
                "H.264.AAC-FROGWeb"
            ),
            save_path="/downloads",
            tags="old,seed",
        )
        torrent.trackers = []
        downloader = FakeDownloader([torrent])
        plugin = FakeSingleRetryPlugin()
        service = types.SimpleNamespace(type="qbittorrent", instance=downloader)

        report = retry_rename_by_hash(plugin, service, "hash-one")

        self.assertEqual(report["code"], 0)
        self.assertEqual(
            plugin.renamed,
            [
                (
                    "qbittorrent",
                    "hash-one",
                    "进击的巨人.Attack.on.Titan.S02.2017.1080p.CR.WEB-DL.H.264.AAC-FROGWeb",
                    "/downloads",
                )
            ],
        )

    def test_single_hash_retry_accepts_clean_release_from_polluted_current_name(self) -> None:
        retry_rename_by_hash = _load_retry_rename_by_hash_function()
        torrent = FakeQbTorrent(
            hash="hash-one",
            name=(
                "[ 碟中谍8：最终清算 (2025) ] - [ 碟中谍8：最终清算 (2025) ] - "
                "Mission.Impossible.The.Final.Reckoning.2025.1080p.iT.WEB-DL."
                "DDP5.1.Atmos.H264-Breeze@Sunny"
            ),
            save_path="/downloads",
            tags="old",
        )
        torrent.trackers = []
        downloader = FakeDownloader([torrent])
        plugin = FakeSingleRetryPlugin()
        service = types.SimpleNamespace(type="qbittorrent", instance=downloader)

        report = retry_rename_by_hash(plugin, service, "hash-one")

        self.assertEqual(report["code"], 0)
        self.assertEqual(
            plugin.renamed[0][2],
            "Mission.Impossible.The.Final.Reckoning.2025.1080p.iT.WEB-DL.DDP5.1.Atmos.H264-Breeze@Sunny",
        )

    def test_single_hash_retry_reuses_source_record_for_iyuu_seed_tag(self) -> None:
        retry_rename_by_hash = _load_retry_rename_by_hash_function()
        torrent = FakeQbTorrent(
            hash="seed-hash",
            name=(
                "[ 碟中谍8：最终清算 (2025) ] - [ 碟中谍8：最终清算 (2025) ] - "
                "Mission.Impossible.The.Final.Reckoning.2025.1080p.iT.WEB-DL."
                "DDP5.1.Atmos.H264-Breeze@Sunny"
            ),
            save_path="/downloads",
            tags="铺种",
        )
        torrent.trackers = []
        downloader = FakeDownloader([torrent])
        plugin = FakeSingleRetryPlugin()
        plugin.data = {
            "iyuu_source_seed-hash": "source-hash",
            "rename_records": {
                "source-hash": {
                    "success": True,
                    "after_name": "[ 碟中谍8：最终清算 (2025) ] - Source.Release.Name",
                }
            },
        }
        service = types.SimpleNamespace(type="qbittorrent", instance=downloader)

        report = retry_rename_by_hash(plugin, service, "seed-hash")

        self.assertEqual(report["code"], 0)
        self.assertEqual(
            downloader.renamed,
            [
                (
                    "seed-hash",
                    (
                        "[碟中谍8：最终清算 (2025)] - "
                        "Mission.Impossible.The.Final.Reckoning.2025.1080p.iT.WEB-DL."
                        "DDP5.1.Atmos.H264-Breeze@Sunny"
                    ),
                )
            ],
        )
        self.assertEqual(plugin.renamed, [])

    def test_single_hash_retry_rejects_all_polluted_original_name_candidates(self) -> None:
        source = (PLUGIN_DIR / "modules" / "rename.py").read_text(encoding="utf-8")
        module_ast = ast.parse(source)
        required_names = {
            "_add_original_name_candidate",
            "_add_download_history_candidates",
            "_add_rename_record_candidates",
            "_add_torrent_file_candidates",
            "_build_original_name_candidate_items",
            "_get_bencoded_value",
            "_get_original_torrent_name",
            "_get_torrent_content_name",
            "_get_torrent_name",
            "_get_tracker_urls",
            "_path_name_candidate",
            "_score_original_name_candidate",
            "_to_text",
            "_find_iyuu_source_hash",
            "_find_iyuu_source_hash_from_files",
            "_is_iyuu_seed_tags",
            "rename_iyuu_torrent_by_source_record",
            "resolve_retry_original_name",
            "retry_rename_by_hash",
            "save_rename_record",
        }
        funcs = [
            node
            for node in module_ast.body
            if isinstance(node, ast.FunctionDef) and node.name in required_names
        ]
        namespace = {
            "logger": types.SimpleNamespace(
                info=lambda *args, **kwargs: None,
                warning=lambda *args, **kwargs: None,
                error=lambda *args, **kwargs: None,
            ),
            "get_hash": lambda torrent, dl_type: torrent.get("hash"),
            "get_label": lambda torrent, dl_type: [],
            "get_save_path": lambda torrent, dl_type: torrent.get("save_path"),
            "Path": Path,
            "bdecode": _fake_all_dirty_bdecode,
            "clean_torrent_original_name": _test_clean_original_name,
            "is_polluted_original_name": lambda value: " | " in str(value or "") or "类型" in str(value or "") or "主演" in str(value or ""),
            "json": json,
            "re": re,
            "datetime": datetime,
        }
        exec(compile(ast.Module(body=funcs, type_ignores=[]), "rename_dirty_candidates", "exec"), namespace)
        retry_rename_by_hash = namespace["retry_rename_by_hash"]

        with tempfile.TemporaryDirectory() as temp_dir:
            torrent_file = Path(temp_dir) / "hash-one.torrent"
            torrent_file.write_bytes(b"fake torrent content")
            torrent = FakeQbTorrent(
                hash="hash-one",
                name="污染当前名 第1集 | 类型：动画",
                save_path="/downloads/show",
                tags="",
            )
            torrent.trackers = []
            downloader = FakeDownloader([torrent])
            plugin = FakeSingleRetryPlugin()
            plugin._fromtorrentpath = temp_dir
            service = types.SimpleNamespace(type="qbittorrent", instance=downloader)

            report = retry_rename_by_hash(plugin, service, "hash-one")

        self.assertEqual(report["code"], 1)
        self.assertEqual(report["msg"], "原始发布名污染，无法可靠补刀")
        self.assertEqual(plugin.renamed, [])

    def test_original_torrent_name_candidates_include_inner_folder_name(self) -> None:
        get_candidates = _load_original_name_candidates_function()
        plugin = FakeSingleRetryPlugin()
        with tempfile.TemporaryDirectory() as temp_dir:
            torrent_file = Path(temp_dir) / "hash-one.torrent"
            torrent_file.write_bytes(b"fake torrent content")
            plugin._fromtorrentpath = temp_dir

            candidates = get_candidates(plugin, "hash-one")

        self.assertIn("Clean.Release.S01E01.2026.WEB-DL-GRP", candidates)


if __name__ == "__main__":
    unittest.main()
