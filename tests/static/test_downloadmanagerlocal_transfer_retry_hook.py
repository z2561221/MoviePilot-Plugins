from __future__ import annotations

import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
TRANSFER_SOURCE = REPO / "plugins.v2" / "downloadmanagerlocal" / "service" / "transfer.py"


class TransferRetryHookTest(unittest.TestCase):
    def test_fallback_transfer_runs_rename_retry_before_transfer_scan(self) -> None:
        source = TRANSFER_SOURCE.read_text(encoding="utf-8")

        self.assertIn("def retry_pending_renames(plugin):", source)
        self.assertIn("def retry_dirty_torrent_names(plugin, to_service: ServiceInfo):", source)
        fallback_body = source.split("def fallback_transfer(plugin):", 1)[1].split(
            "def delayed_transfer(plugin):", 1
        )[0]
        self.assertLess(
            fallback_body.index("retry_pending_renames(plugin)"),
            fallback_body.index('transfer(plugin, trigger_source="兜底扫描")'),
        )

        retry_body = source.split("def retry_pending_renames(plugin):", 1)[1].split(
            "def fallback_transfer(plugin):", 1
        )[0]
        self.assertIn("retry_dirty_torrent_names(plugin, to_service)", retry_body)


if __name__ == "__main__":
    unittest.main()
