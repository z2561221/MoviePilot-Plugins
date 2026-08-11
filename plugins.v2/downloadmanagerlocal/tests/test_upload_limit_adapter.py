from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace


PLUGIN_DIR = Path(
    os.environ.get("DOWNLOADMANAGERLOCAL_PLUGIN_DIR")
    or Path(__file__).resolve().parents[1]
)


def _load(module_name: str):
    """加载不执行插件入口的上传限速适配模块。"""
    for name in list(sys.modules):
        if name == "downloadmanagerlocal" or name.startswith("downloadmanagerlocal."):
            sys.modules.pop(name)
    package = types.ModuleType("downloadmanagerlocal")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["downloadmanagerlocal"] = package
    return importlib.import_module(f"downloadmanagerlocal.{module_name}")


class FakeQbClient:
    """记录 qB 全局与单种上传限速调用。"""

    def __init__(self):
        """初始化普通/备用限速与调用记录。"""
        self.transfer = SimpleNamespace(upload_limit=0, download_limit=987654)
        self.preferences = {"alt_up_limit": 50 * 1024}
        self.preference_calls = []
        self.torrent_calls = []

    def app_preferences(self):
        """返回 qB 偏好设置。"""
        return dict(self.preferences)

    def app_set_preferences(self, payload):
        """记录 qB 偏好更新。"""
        self.preference_calls.append(dict(payload))
        self.preferences.update(payload)

    def torrents_set_upload_limit(self, limit, torrent_hashes):
        """记录 qB 单种上传限速。"""
        self.torrent_calls.append((limit, torrent_hashes))


class FakeTransmissionClient:
    """记录 Transmission Session 与单种限速调用。"""

    def __init__(self):
        """初始化 Session、任务与调用记录。"""
        self.session = {
            "speed_limit_up": 55,
            "speed_limit_up_enabled": False,
            "speed_limit_down": 999,
            "speed_limit_down_enabled": False,
        }
        self.session_calls = []
        self.torrent_calls = []
        self.arguments = None
        self.torrents = []

    def get_session(self):
        """返回 Transmission Session。"""
        return dict(self.session)

    def set_session(self, **kwargs):
        """记录 Session 更新且保留未传入字段。"""
        self.session_calls.append(dict(kwargs))
        self.session.update(kwargs)

    def get_torrents(self, arguments):
        """记录请求字段并返回任务。"""
        self.arguments = list(arguments)
        return list(self.torrents)

    def change_torrent(self, **kwargs):
        """记录单种限速更新。"""
        self.torrent_calls.append(dict(kwargs))


def test_qb_global_limit_controls_normal_and_alternate_without_touching_download():
    """qB 总上限应同时写普通/备用上传限速并保留下载限速。"""
    adapter = _load("adapter.upload_limit")
    client = FakeQbClient()
    instance = SimpleNamespace(qbc=client)

    original = adapter.read_global_upload_settings(instance, "qbittorrent")
    applied = adapter.write_global_upload_limit(instance, "qbittorrent", 100)

    assert original.upload_limit_bps == 0
    assert original.alternate_upload_limit_bps == 50 * 1024
    assert applied.upload_limit_bps == 100 * 1024
    assert client.transfer.upload_limit == 100 * 1024
    assert client.transfer.download_limit == 987654
    assert client.preference_calls == [{"alt_up_limit": 100 * 1024}]

    adapter.restore_global_upload_settings(instance, "qbittorrent", original)
    assert client.transfer.upload_limit == 0
    assert client.preferences["alt_up_limit"] == 50 * 1024
    assert client.transfer.download_limit == 987654


def test_transmission_global_limit_updates_only_upload_session_fields():
    """Transmission 总上限不得改写下载 Session 设置。"""
    adapter = _load("adapter.upload_limit")
    client = FakeTransmissionClient()
    instance = SimpleNamespace(trc=client)

    original = adapter.read_global_upload_settings(instance, "transmission")
    adapter.write_global_upload_limit(instance, "transmission", 100)

    assert original.upload_limit_bps == 55 * 1024
    assert original.upload_enabled is False
    assert client.session_calls[-1] == {
        "speed_limit_up": 100,
        "speed_limit_up_enabled": True,
    }
    assert client.session["speed_limit_down"] == 999
    assert client.session["speed_limit_down_enabled"] is False

    adapter.restore_global_upload_settings(instance, "transmission", original)
    assert client.session_calls[-1] == {
        "speed_limit_up": 55,
        "speed_limit_up_enabled": False,
    }


def test_qb_zero_task_allocation_uses_one_byte_instead_of_unlimited_zero():
    """qB 的逻辑零额度必须写 1 B/s，不能调用 0 导致不限速。"""
    adapter = _load("adapter.upload_limit")
    client = FakeQbClient()
    instance = SimpleNamespace(qbc=client)

    applied = adapter.write_torrent_upload_limit(instance, "qbittorrent", "abc", 0)

    assert applied.limit_bps == 1
    assert applied.enabled is True
    assert client.torrent_calls == [(1, "abc")]


def test_transmission_zero_task_allocation_keeps_upload_limited_true():
    """Transmission 的逻辑零额度应显式启用限速并写入 0。"""
    adapter = _load("adapter.upload_limit")
    client = FakeTransmissionClient()
    instance = SimpleNamespace(trc=client)

    applied = adapter.write_torrent_upload_limit(instance, "transmission", "def", 0)

    assert applied.limit_bps == 0
    assert applied.enabled is True
    assert client.torrent_calls == [{
        "ids": "def",
        "uploadLimited": True,
        "uploadLimit": 0,
    }]


def test_transmission_extra_fields_are_requested_and_normalized():
    """Transmission 应补读 uploadLimit/uploadLimited 并归一完成时间与实时上传。"""
    adapter = _load("adapter.upload_limit")
    client = FakeTransmissionClient()
    client.torrents = [SimpleNamespace(
        hashString="TR-HASH",
        name="TR Seed",
        status="seeding",
        labels=["🏠M-Team"],
        totalSize=4096,
        percentDone=1,
        leftUntilDone=0,
        addedDate=100,
        doneDate=120,
        rateUpload=4096,
        uploadLimit=8,
        uploadLimited=True,
    )]
    instance = SimpleNamespace(trc=client)

    items, error = adapter.list_upload_torrents(instance, "TR", "transmission")

    assert error == ""
    assert "uploadLimit" in client.arguments
    assert "uploadLimited" in client.arguments
    assert len(items) == 1
    item = items[0]
    assert item.torrent_hash == "tr-hash"
    assert item.labels == ("🏠M-Team",)
    assert item.completed is True
    assert item.added_at == 100
    assert item.completed_at == 120
    assert item.upload_rate_bps == 4096
    assert item.upload_settings.limit_bps == 8 * 1024
    assert item.upload_settings.enabled is True


def test_restore_transmission_torrent_preserves_original_enable_state():
    """停用恢复应同时恢复 Transmission 单种限额和启用状态。"""
    adapter = _load("adapter.upload_limit")
    model = importlib.import_module("downloadmanagerlocal.model.upload_limit")
    client = FakeTransmissionClient()
    instance = SimpleNamespace(trc=client)

    restored = adapter.restore_torrent_upload_settings(
        instance,
        "transmission",
        "def",
        model.TorrentUploadSettings(limit_bps=25 * 1024, enabled=False),
    )

    assert restored.limit_bps == 25 * 1024
    assert restored.enabled is False
    assert client.torrent_calls[-1] == {
        "ids": "def",
        "uploadLimited": False,
        "uploadLimit": 25,
    }
