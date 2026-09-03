"""归档恢复后命名历史排序测试。"""

from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path

PLUGIN_DIR = Path(
    os.environ.get("DOWNLOADMANAGERLOCAL_PLUGIN_DIR")
    or Path(__file__).resolve().parents[1]
)


def _load(module_name: str):
    """加载指定下载中心模块。"""
    for name in list(sys.modules):
        if name == "downloadmanagerlocal" or name.startswith("downloadmanagerlocal."):
            sys.modules.pop(name)
    package = types.ModuleType("downloadmanagerlocal")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["downloadmanagerlocal"] = package
    return importlib.import_module(f"downloadmanagerlocal.{module_name}")


class FakePlugin:
    """提供归档恢复所需的内存数据接口。"""

    def __init__(self, data: dict) -> None:
        """初始化插件持久化数据。"""
        self.data = data

    def get_data(self, key: str):
        """读取插件持久化数据。"""
        return self.data.get(key)

    def save_data(self, key: str, value) -> None:
        """保存插件持久化数据。"""
        self.data[key] = value


def test_restore_archive_updates_existing_history_time_without_duplication(monkeypatch) -> None:
    """恢复归档应更新原记录时间，不新增记录或原始时间字段。"""
    archive = _load("service.archive")
    plugin = FakePlugin({
        archive.RETRY_STATE_KEY: {
            "abc": {
                "hash": "abc",
                "name": "待恢复种子",
                "archived": True,
                "fail_count": 3,
                "archived_at": "2026-08-30 10:00:00",
            }
        },
        archive.RENAME_RECORDS_KEY: {
            "abc": {
                "hash": "abc",
                "original_name": "原始名称",
                "after_name": "命名后",
                "success": False,
                "time": "2026-08-30 10:00:00",
            }
        },
    })
    monkeypatch.setattr(archive, "now_text", lambda: "2026-08-31 12:34:56")

    result = archive.restore_rename_archive(plugin, "abc")

    assert result == {"code": 0, "msg": "已恢复，后续将重新参与补刀", "hash": "abc"}
    assert list(plugin.data[archive.RENAME_RECORDS_KEY]) == ["abc"]
    assert plugin.data[archive.RENAME_RECORDS_KEY]["abc"]["time"] == "2026-08-31 12:34:56"
    assert "original_time" not in plugin.data[archive.RENAME_RECORDS_KEY]["abc"]
    restored = plugin.data[archive.RETRY_STATE_KEY]["abc"]
    assert restored["archived"] is False
    assert restored["fail_count"] == 0
    assert restored["restored_at"] == "2026-08-31 12:34:56"
    assert "archived_at" not in restored


def test_rename_history_places_restored_record_by_updated_time() -> None:
    """命名历史应按恢复后的新时间把记录排到顶部。"""
    handlers = _load("controller.handlers")
    plugin = FakePlugin({
        handlers.RENAME_RECORDS_KEY: {
            "old": {"hash": "old", "time": "2026-08-30 10:00:00"},
            "restored": {"hash": "restored", "time": "2026-08-31 12:34:56"},
        },
        handlers.RENAME_RETRY_STATE_KEY: {},
    })

    result = handlers.api_rename_history(plugin)

    assert [item.hash for item in result.items] == ["restored", "old"]
