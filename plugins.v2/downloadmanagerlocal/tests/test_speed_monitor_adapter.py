from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


PLUGIN_DIR = Path(
    os.environ.get("DOWNLOADMANAGERLOCAL_PLUGIN_DIR")
    or Path(__file__).resolve().parents[1]
)


def _load_adapter():
    """按文件路径加载下载器字段适配器。"""
    path = PLUGIN_DIR / "utils" / "torrent_adapter.py"
    spec = importlib.util.spec_from_file_location("downloadmanagerlocal_speed_adapter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeDownloader:
    """模拟下载器轮询与删除接口。"""

    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.delete_calls = []

    def get_torrents(self):
        """返回预设轮询结果或抛出预设错误。"""
        if self.error:
            raise self.error
        return self.response

    def delete_torrents(self, ids, delete_file):
        """记录删除参数。"""
        self.delete_calls.append((list(ids), delete_file))
        return True


def test_qbittorrent_dict_normalizes_all_monitor_fields():
    adapter = _load_adapter()
    snapshot = adapter.normalize_torrent({
        "hash": "ABC123",
        "name": "Example",
        "total_size": 4096,
        "downloaded": 1024,
        "added_on": 123.5,
        "state": "stalledDL",
        "save_path": "/downloads",
        "dlspeed": 512,
    }, "qb-main", "qbittorrent")

    assert snapshot.downloader_id == "qb-main"
    assert snapshot.downloader_type == "qbittorrent"
    assert snapshot.torrent_hash == "abc123"
    assert snapshot.name == "Example"
    assert snapshot.total_bytes == 4096
    assert snapshot.downloaded_bytes == 1024
    assert snapshot.added_at == 123.5
    assert snapshot.state == "stalledDL"
    assert snapshot.state_category == adapter.TORRENT_ACTIVE
    assert snapshot.save_path == "/downloads"
    assert snapshot.download_speed_bps == 512


def test_transmission_object_and_missing_fields_return_stable_snapshot():
    adapter = _load_adapter()
    torrent = SimpleNamespace(
        hashString="DEF456",
        name="TR Example",
        totalSize=8000,
        downloadedEver=8000,
        dateAdded=321,
        status="seeding",
        downloadDir="/tr",
        rateDownload=0,
    )

    completed = adapter.normalize_torrent(torrent, "tr-backup", "transmission")
    missing = adapter.normalize_torrent(SimpleNamespace(), "tr-backup", "transmission")

    assert completed.torrent_hash == "def456"
    assert completed.total_bytes == 8000
    assert completed.downloaded_bytes == 8000
    assert completed.state_category == adapter.TORRENT_COMPLETED
    assert completed.save_path == "/tr"
    assert missing.torrent_hash == ""
    assert missing.total_bytes == 0
    assert missing.downloaded_bytes == 0
    assert missing.state_category == adapter.TORRENT_ACTIVE


@pytest.mark.parametrize(
    ("state", "category"),
    [
        ("downloading", "active"),
        ("pausedDL", "paused"),
        ("queuedDL", "queued"),
        ("seed pending", "queued"),
        ("checkingDL", "checking"),
        ("uploading", "completed"),
        ("missingFiles", "error"),
    ],
)
def test_status_names_map_to_monitor_categories(state, category):
    adapter = _load_adapter()

    assert adapter.classify_torrent_state(state, 1, 10) == category


def test_poll_result_distinguishes_success_empty_from_api_error():
    adapter = _load_adapter()

    empty = adapter.poll_downloader(FakeDownloader(([], None)), "qb", "qbittorrent")
    tuple_error = adapter.poll_downloader(
        FakeDownloader((None, "authentication failed")), "qb", "qbittorrent"
    )
    raised = adapter.poll_downloader(
        FakeDownloader(error=TimeoutError("timeout")), "tr", "transmission"
    )

    assert empty.success is True
    assert empty.items == ()
    assert empty.error == ""
    assert tuple_error.success is False
    assert tuple_error.items == ()
    assert "authentication failed" in tuple_error.error
    assert raised.success is False
    assert "timeout" in raised.error


@pytest.mark.parametrize("downloader_type", ["qbittorrent", "transmission"])
def test_delete_requires_explicit_true_and_always_deletes_torrent_files(downloader_type):
    adapter = _load_adapter()
    downloader = FakeDownloader()

    with pytest.raises(ValueError, match="delete_file=True"):
        adapter.delete_torrent_with_files(downloader, "abc", delete_file=False)
    assert downloader.delete_calls == []

    assert adapter.delete_torrent_with_files(
        downloader, "abc", delete_file=True
    ) is True
    assert downloader.delete_calls == [(["abc"], True)]
