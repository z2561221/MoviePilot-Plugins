from __future__ import annotations

import ast
import time
import types
import unittest
from pathlib import Path
from typing import Optional


REPO = Path(__file__).resolve().parents[2]
TRANSFER_SOURCE = REPO / "plugins.v2" / "downloadmanagerlocal" / "service" / "transfer.py"


def _load_transfer_delay_status():
    """从转移服务中抽取延迟判断函数进行隔离测试。"""
    source = TRANSFER_SOURCE.read_text(encoding="utf-8")
    module = ast.parse(source)
    nodes = [
        node
        for node in module.body
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "_AUTOMATIC_DELAY_TRIGGER_SOURCES"
                for target in node.targets
            )
        )
        or (
            isinstance(node, ast.FunctionDef)
            and node.name == "_transfer_delay_status"
        )
    ]
    namespace = {"Optional": Optional, "time": time}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(TRANSFER_SOURCE), "exec"), namespace)
    return namespace["_transfer_delay_status"]


class DownloadManagerLocalTransferDelayTest(unittest.TestCase):
    """验证自动转移入口统一遵守完成延迟。"""

    def setUp(self) -> None:
        """准备固定延迟配置和时间基准。"""
        self.delay_status = _load_transfer_delay_status()
        self.plugin = types.SimpleNamespace(_delay_minutes=25)
        self.now = 1_800_000_000.0

    def test_fallback_scan_skips_recently_completed_qbittorrent(self) -> None:
        """兜底扫描不得转移完成不足配置延迟的 qB 任务。"""
        should_wait, age_minutes, delay_minutes = self.delay_status(
            self.plugin,
            {"completion_on": self.now - 10 * 60},
            "qbittorrent",
            "兜底扫描",
            self.now,
        )

        self.assertTrue(should_wait)
        self.assertEqual(age_minutes, 10)
        self.assertEqual(delay_minutes, 25)

    def test_event_driven_scan_skips_recently_completed_qbittorrent(self) -> None:
        """事件驱动扫描同样不得提前转移新完成的 qB 任务。"""
        should_wait, _, _ = self.delay_status(
            self.plugin,
            {"completion_on": self.now - 24 * 60},
            "qbittorrent",
            "事件驱动",
            self.now,
        )

        self.assertTrue(should_wait)

    def test_automatic_scan_allows_task_after_delay(self) -> None:
        """完成时间达到延迟阈值后自动扫描应允许继续转移。"""
        should_wait, age_minutes, _ = self.delay_status(
            self.plugin,
            {"completion_on": self.now - 25 * 60},
            "qbittorrent",
            "兜底扫描",
            self.now,
        )

        self.assertFalse(should_wait)
        self.assertEqual(age_minutes, 25)

    def test_manual_run_keeps_immediate_execution_semantics(self) -> None:
        """用户手动立即运行一次时不应被自动入口延迟门禁阻挡。"""
        should_wait, age_minutes, _ = self.delay_status(
            self.plugin,
            {"completion_on": self.now - 60},
            "qbittorrent",
            "手动/定时",
            self.now,
        )

        self.assertFalse(should_wait)
        self.assertIsNone(age_minutes)

    def test_missing_completion_time_preserves_existing_behavior(self) -> None:
        """无法取得完成时间时保持旧行为，避免永久跳过任务。"""
        should_wait, age_minutes, _ = self.delay_status(
            self.plugin,
            {},
            "qbittorrent",
            "事件驱动",
            self.now,
        )

        self.assertFalse(should_wait)
        self.assertIsNone(age_minutes)

    def test_transfer_loop_applies_delay_before_other_candidate_filters(self) -> None:
        """共享转移循环必须在候选过滤前应用统一延迟判断。"""
        source = TRANSFER_SOURCE.read_text(encoding="utf-8")
        transfer_body = source.split("def transfer(plugin, trigger_source", 1)[1].split(
            "def retry_pending_renames(plugin):", 1
        )[0]

        self.assertLess(
            transfer_body.index("_transfer_delay_status("),
            transfer_body.index("if plugin._nopaths and save_path:"),
        )
        self.assertIn("if should_wait:", transfer_body)
        self.assertIn("continue", transfer_body)


if __name__ == "__main__":
    unittest.main()
