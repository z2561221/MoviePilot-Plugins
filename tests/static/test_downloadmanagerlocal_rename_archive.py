from __future__ import annotations

import ast
import unittest
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"


def _load_archive_namespace():
    source = (PLUGIN_DIR / "modules" / "rename_archive.py").read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    funcs = [
        node
        for node in module_ast.body
        if isinstance(node, (ast.Assign, ast.FunctionDef))
    ]
    namespace = {"datetime": datetime}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), "rename_archive", "exec"), namespace)
    return namespace


class FakeArchivePlugin:
    def __init__(self):
        self.data = {}

    def get_data(self, key):
        return self.data.get(key)

    def save_data(self, key, value):
        self.data[key] = value


class DownloadManagerLocalRenameArchiveTest(unittest.TestCase):
    def test_records_failure_and_archives_after_threshold(self) -> None:
        ns = _load_archive_namespace()
        plugin = FakeArchivePlugin()

        self.assertFalse(ns["is_rename_archived"](plugin, "hash-one"))

        first = ns["record_rename_failure"](
            plugin,
            "hash-one",
            "污染当前名 第1集 | 类型：动画",
            "NO_TRUSTED_SOURCE",
            "原始发布名污染且无可信候选",
        )
        self.assertFalse(first["archived"])
        self.assertEqual(first["fail_count"], 1)

        ns["record_rename_failure"](
            plugin,
            "hash-one",
            "污染当前名 第1集 | 类型：动画",
            "NO_TRUSTED_SOURCE",
            "原始发布名污染且无可信候选",
        )
        third = ns["record_rename_failure"](
            plugin,
            "hash-one",
            "污染当前名 第1集 | 类型：动画",
            "NO_TRUSTED_SOURCE",
            "原始发布名污染且无可信候选",
        )

        self.assertTrue(third["archived"])
        self.assertTrue(ns["is_rename_archived"](plugin, "hash-one"))
        self.assertEqual(third["category"], "NO_TRUSTED_SOURCE")
        self.assertEqual(third["archive_reason"], "连续补刀失败 3 次：原始发布名污染且无可信候选")

    def test_success_clears_retry_state(self) -> None:
        ns = _load_archive_namespace()
        plugin = FakeArchivePlugin()

        ns["record_rename_failure"](plugin, "hash-one", "Name", "MEDIA_RECOGNIZE_FAILED", "媒体识别失败")
        ns["clear_rename_retry_state"](plugin, "hash-one")

        self.assertFalse(ns["is_rename_archived"](plugin, "hash-one"))
        self.assertNotIn("hash-one", plugin.data.get("rename_retry_state", {}))

    def test_restore_archive_clears_archived_state(self) -> None:
        ns = _load_archive_namespace()
        plugin = FakeArchivePlugin()
        for _ in range(3):
            ns["record_rename_failure"](plugin, "hash-one", "Name", "UNKNOWN_ERROR", "失败")

        result = ns["restore_rename_archive"](plugin, "hash-one")

        self.assertEqual(result["code"], 0)
        self.assertFalse(ns["is_rename_archived"](plugin, "hash-one"))
        self.assertEqual(plugin.data["rename_retry_state"]["hash-one"]["fail_count"], 0)
        self.assertFalse(plugin.data["rename_retry_state"]["hash-one"]["archived"])

    def test_api_and_page_expose_archive_surface(self) -> None:
        init_source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
        api_source = (PLUGIN_DIR / "api.py").read_text(encoding="utf-8")
        page_source = (PLUGIN_DIR / "src" / "components" / "Page.vue").read_text(encoding="utf-8")

        self.assertIn('"path": "/rename_archive"', init_source)
        self.assertIn('"path": "/restore_rename_archive"', init_source)
        self.assertIn("def api_rename_archive(plugin", api_source)
        self.assertIn("def api_restore_rename_archive(plugin", api_source)
        self.assertIn("activeTab = ref('history')", page_source)
        self.assertNotIn("loadOverview", page_source)
        self.assertIn("loadArchive", page_source)
        self.assertIn("restoreArchive", page_source)


if __name__ == "__main__":
    unittest.main()
