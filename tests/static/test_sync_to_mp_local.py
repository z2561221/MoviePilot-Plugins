from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.sync_to_mp_local import sync_to_target  # noqa: E402


class SyncToMpLocalTest(unittest.TestCase):
    def test_merges_selected_package_entries_and_preserves_other_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            target = root / "target"
            (source / "plugins.v2" / "doubancenter").mkdir(parents=True)
            (target / "plugins.v2").mkdir(parents=True)

            (source / "package.v2.json").write_text(
                json.dumps(
                    {
                        "DoubanCenter": {
                            "name": "豆瓣中心",
                            "version": "1.1.1",
                            "icon": "douban.png",
                        },
                        "DownloadManagerLocal": {
                            "name": "下载管理",
                            "version": "3.1.4",
                            "icon": "download.png",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (target / "package.v2.json").write_text(
                json.dumps(
                    {
                        "DoubanCenter": {"name": "旧豆瓣中心", "version": "1.1.0"},
                        "MediaServerIncrementalSync": {
                            "name": "媒体库增量同步",
                            "version": "9.9.9",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (source / "plugins.v2" / "doubancenter" / "__init__.py").write_text(
                "plugin_version = '1.1.1'\n",
                encoding="utf-8",
            )

            actions = sync_to_target(source, target, ["DoubanCenter"])

            merged = json.loads((target / "package.v2.json").read_text(encoding="utf-8"))
            self.assertEqual(merged["DoubanCenter"]["version"], "1.1.1")
            self.assertEqual(merged["MediaServerIncrementalSync"]["version"], "9.9.9")
            self.assertNotIn("DownloadManagerLocal", merged)
            self.assertIn("package:DoubanCenter", actions)

    def test_replaces_selected_plugin_directory_without_touching_unselected_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            target = root / "target"
            source_plugin = source / "plugins.v2" / "downloadmanagerlocal"
            target_plugin = target / "plugins.v2" / "downloadmanagerlocal"
            other_plugin = target / "plugins.v2" / "localtoolkit"
            source_icon_dir = source / "icons"

            source_plugin.mkdir(parents=True)
            target_plugin.mkdir(parents=True)
            other_plugin.mkdir(parents=True)
            source_icon_dir.mkdir(parents=True)
            (target / "icons").mkdir(parents=True)

            (source / "package.v2.json").write_text(
                json.dumps(
                    {
                        "DownloadManagerLocal": {
                            "name": "下载管理",
                            "version": "3.1.4",
                            "icon": "download.png",
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (target / "package.v2.json").write_text(
                json.dumps({"LocalToolkit": {"name": "本地工具", "version": "0.1.0"}}),
                encoding="utf-8",
            )
            (source_plugin / "__init__.py").write_text("new\n", encoding="utf-8")
            (source_plugin / "__pycache__").mkdir()
            (source_plugin / "__pycache__" / "bad.pyc").write_bytes(b"cache")
            (target_plugin / "__init__.py").write_text("old\n", encoding="utf-8")
            (target_plugin / "stale.txt").write_text("remove me\n", encoding="utf-8")
            (other_plugin / "keep.txt").write_text("keep me\n", encoding="utf-8")
            (source_icon_dir / "download.png").write_bytes(b"png")

            actions = sync_to_target(source, target, ["DownloadManagerLocal"])

            self.assertEqual((target_plugin / "__init__.py").read_text(encoding="utf-8"), "new\n")
            self.assertFalse((target_plugin / "stale.txt").exists())
            self.assertFalse((target_plugin / "__pycache__").exists())
            self.assertEqual((other_plugin / "keep.txt").read_text(encoding="utf-8"), "keep me\n")
            self.assertEqual((target / "icons" / "download.png").read_bytes(), b"png")
            self.assertIn("plugin:DownloadManagerLocal", actions)
            self.assertIn("icon:download.png", actions)

    def test_merges_local_only_index_for_explicit_local_plugin_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            target = root / "target"
            (source / "plugins.v2" / "localtoolkit").mkdir(parents=True)
            (target / "plugins.v2").mkdir(parents=True)
            (source / "package.v2.json").write_text("{}", encoding="utf-8")
            (source / "package.local.v2.json").write_text(
                json.dumps({"LocalToolkit": {"name": "工具中心", "version": "1.2.13"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            (target / "package.v2.json").write_text("{}", encoding="utf-8")
            (source / "plugins.v2" / "localtoolkit" / "__init__.py").write_text(
                "plugin_version = '1.2.13'\n", encoding="utf-8"
            )

            actions = sync_to_target(source, target, ["LocalToolkit"])

            merged = json.loads((target / "package.v2.json").read_text(encoding="utf-8"))
            self.assertEqual(merged["LocalToolkit"]["version"], "1.2.13")
            self.assertIn("package:LocalToolkit", actions)


if __name__ == "__main__":
    unittest.main()
