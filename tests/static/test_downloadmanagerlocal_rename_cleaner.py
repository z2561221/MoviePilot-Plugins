from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RenameCleanerTest(unittest.TestCase):
    def test_removes_appended_chinese_subtitle_from_original_release_name(self) -> None:
        cleaner = _load_module(PLUGIN_DIR / "utils" / "name_cleaner.py", "name_cleaner")

        self.assertEqual(
            cleaner.clean_torrent_original_name(
                "Azure Legacy S01E82 2023 2160p HQ WEB-DL H265 AAC-ADWeb"
                "沧元图 第82集 | 类型：动作 动画 奇幻 古装 | 沧元图 第三季 *酷喵TV*"
            ),
            "Azure Legacy S01E82 2023 2160p HQ WEB-DL H265 AAC-ADWeb",
        )
        self.assertEqual(
            cleaner.clean_torrent_original_name(
                "Beyond Time s Gaze S01E17 2025 2160p WEB-DL H265 AAC-ADWeb"
                "光阴之外 第17集 | 类型：动作 动画 奇幻 武侠 古装 | 主演：陈张太康 凌振赫 "
                "常文涛 万舒心 刘思岑 | 光阴之外 3D动画版 / 光阴之外·末世的微光 "
                "/ 光阴之外·除凶七血瞳 / 光阴之外·新的开始 / 光阴之外·决战人鱼岛 "
                "/ 光阴之外·决战海尸族 *酷喵TV*"
            ),
            "Beyond Time s Gaze S01E17 2025 2160p WEB-DL H265 AAC-ADWeb",
        )

    def test_cleans_already_renamed_dirty_qbittorrent_names_without_stacking_dashes(self) -> None:
        cleaner = _load_module(PLUGIN_DIR / "utils" / "name_cleaner.py", "name_cleaner")

        self.assertEqual(
            cleaner.clean_torrent_original_name(
                "[ 沧元图 (2023) - S01E81 ] - - - - Azure Legacy S01E81 2023 "
                "2160p HQ WEB-DL H265 AAC-ADWeb沧元图 第81集 | 类型：动作 动画 奇幻 古装"
            ),
            "Azure Legacy S01E81 2023 2160p HQ WEB-DL H265 AAC-ADWeb",
        )

    def test_keeps_clean_release_names_unchanged(self) -> None:
        cleaner = _load_module(PLUGIN_DIR / "utils" / "name_cleaner.py", "name_cleaner")

        self.assertEqual(
            cleaner.clean_torrent_original_name(
                "Azure Legacy S01E82 2023 2160p HQ WEB-DL H265 AAC-ADWeb"
            ),
            "Azure Legacy S01E82 2023 2160p HQ WEB-DL H265 AAC-ADWeb",
        )

    def test_detects_dirty_renamed_torrent_names_for_retry(self) -> None:
        cleaner = _load_module(PLUGIN_DIR / "utils" / "name_cleaner.py", "name_cleaner")

        self.assertTrue(
            cleaner.is_dirty_renamed_torrent_name(
                "[ 沧元图 (2023) - S01E82 ] - Azure Legacy S01E82 2023 2160p HQ WEB-DL "
                "H265 AAC-ADWeb沧元图 第82集 | 类型：动作 动画 奇幻 古装 | 沧元图 第三季 *酷喵TV*]"
            )
        )
        self.assertFalse(
            cleaner.is_dirty_renamed_torrent_name(
                "[ 沧元图 (2023) - S01E82 ] - Azure Legacy S01E82 2023 2160p HQ WEB-DL "
                "H265 AAC-ADWeb"
            )
        )

    def test_collects_failed_and_dirty_success_records_for_retry(self) -> None:
        cleaner = _load_module(PLUGIN_DIR / "utils" / "name_cleaner.py", "name_cleaner")

        records = {
            "failed": {"success": False, "after_name": "anything"},
            "dirty": {
                "success": True,
                "after_name": (
                    "[ 光阴之外 (2025) - S01E17 ] - Beyond Time s Gaze S01E17 2025 "
                    "2160p WEB-DL H265 AAC-ADWeb光阴之外 第17集 | 类型：动作 动画 奇幻 武侠 古装"
                ),
            },
            "clean": {
                "success": True,
                "after_name": (
                    "[ 光阴之外 (2025) - S01E17 ] - Beyond Time s Gaze S01E17 2025 "
                    "2160p WEB-DL H265 AAC-ADWeb"
                ),
            },
        }

        self.assertEqual(cleaner.collect_retry_rename_hashes(records), {"failed", "dirty"})


if __name__ == "__main__":
    unittest.main()
