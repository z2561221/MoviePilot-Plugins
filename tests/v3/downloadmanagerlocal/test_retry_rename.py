"""归档记录直接补刀的实际结果与失败状态回归。"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.plugins.downloadmanagerlocal.service import archive, rename
from app.schemas.types import MediaType


@pytest.fixture
def archived_retry(monkeypatch):
    """构造已有归档、独立持久化快照和无外部副作用的下载器。"""
    torrent_hash = "archived-torrent"
    original_name = "Example.2026.1080p"
    data = {
        archive.RETRY_STATE_KEY: {
            torrent_hash: {
                "hash": torrent_hash,
                "name": original_name,
                "archived": True,
                "fail_count": 3,
                "archived_at": "2026-09-15 12:00:00",
            }
        },
        archive.RENAME_RECORDS_KEY: {
            torrent_hash: {
                "hash": torrent_hash,
                "original_name": original_name,
                "after_name": original_name,
                "success": False,
                "time": "2026-09-15 12:00:00",
            }
        },
    }
    plugin = SimpleNamespace(
        _rename_enabled=True,
        _tag_enabled=True,
        _rename_exclude_dirs="",
        _rename_movie_format="{{ title }}",
        _rename_tv_format="{{ title }}",
        chain=SimpleNamespace(recognize_media=Mock(return_value=SimpleNamespace(type=MediaType.MOVIE))),
        get_data=lambda key: deepcopy(data.get(key)),
        save_data=lambda key, value: data.__setitem__(key, deepcopy(value)),
        _tag_torrent=Mock(),
    )
    plugin._rename_torrent = lambda *args: rename.rename_torrent(plugin, *args)
    plugin.clear_rename_retry_state = lambda value: archive.clear_rename_retry_state(plugin, value)
    plugin.record_rename_failure = lambda *args, **kwargs: archive.record_rename_failure(plugin, *args, **kwargs)
    torrent = {"hash": torrent_hash, "name": original_name}
    downloader = SimpleNamespace(
        get_torrents=Mock(return_value=([torrent], None)),
        qbc=SimpleNamespace(torrents_rename=Mock()),
    )
    service = SimpleNamespace(type="qbittorrent", instance=downloader)
    monkeypatch.setattr(rename, "get_hash", lambda item, _kind: item["hash"])
    monkeypatch.setattr(rename, "get_save_path", lambda *_args: "/downloads/example")
    monkeypatch.setattr(rename, "get_label", lambda *_args: [])
    monkeypatch.setattr(rename, "_get_torrent_content_name", lambda *_args: original_name)
    monkeypatch.setattr(rename, "resolve_retry_original_name", lambda *_args: original_name)
    monkeypatch.setattr(rename, "_is_iyuu_seed_tags", lambda *_args: False)
    monkeypatch.setattr(rename, "get_download_history_by_hash", lambda *_args: None)
    monkeypatch.setattr(rename, "MetaInfo", lambda *_args: SimpleNamespace(title="Example"))
    monkeypatch.setattr(rename, "format_torrent_name", lambda *_args: "Example (2026)")
    return SimpleNamespace(plugin=plugin, data=data, service=service, downloader=downloader,
                           torrent_hash=torrent_hash, original_name=original_name)


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        ("excluded", "命中排除目录"),
        ("metadata", "元数据获取失败"),
        ("recognition", "媒体识别失败"),
        ("format", "格式化结果为空"),
        ("downloader", "rename rejected"),
    ],
)
def test_archived_retry_reports_rename_failure_and_preserves_archive(
    archived_retry, monkeypatch, failure, reason
):
    """失败不误报完成、不恢复归档，且失败次数只增加一次。"""
    case = archived_retry
    if failure == "excluded":
        case.plugin._rename_exclude_dirs = "/downloads"
    elif failure == "metadata":
        monkeypatch.setattr(rename, "MetaInfo", lambda *_args: None)
    elif failure == "recognition":
        case.plugin.chain.recognize_media.return_value = None
    elif failure == "format":
        monkeypatch.setattr(rename, "format_torrent_name", lambda *_args: "")
    else:
        case.downloader.qbc.torrents_rename.side_effect = RuntimeError(reason)

    result = rename.retry_rename_by_hash(case.plugin, case.service, case.torrent_hash)

    assert result["code"] == 1
    assert reason in result["msg"]
    state = case.data[archive.RETRY_STATE_KEY][case.torrent_hash]
    assert state["archived"] is True
    assert state["fail_count"] == 4
    assert state["reason"] == reason
    assert state["archived_at"] == "2026-09-15 12:00:00"
    assert "restored_at" not in state
    assert case.data[archive.RENAME_RECORDS_KEY][case.torrent_hash]["success"] is False
    case.plugin._tag_torrent.assert_called_once()


@pytest.mark.parametrize("unchanged", [False, True])
def test_archived_retry_success_clears_archive_and_updates_existing_history(
    archived_retry, monkeypatch, unchanged
):
    """成功或名称已正确时解除归档，沿用原 hash 的唯一命名历史。"""
    case = archived_retry
    expected_name = case.original_name if unchanged else "Example (2026)"
    monkeypatch.setattr(rename, "format_torrent_name", lambda *_args: expected_name)

    result = rename.retry_rename_by_hash(case.plugin, case.service, case.torrent_hash)

    assert result["code"] == 0
    assert case.torrent_hash not in case.data[archive.RETRY_STATE_KEY]
    records = case.data[archive.RENAME_RECORDS_KEY]
    assert list(records) == [case.torrent_hash]
    assert records[case.torrent_hash]["success"] is True
    assert records[case.torrent_hash]["after_name"] == expected_name
    assert records[case.torrent_hash]["time"] != "2026-09-15 12:00:00"
    assert "original_time" not in records[case.torrent_hash]
    assert case.downloader.qbc.torrents_rename.call_count == (0 if unchanged else 1)


def test_archived_retry_missing_torrent_keeps_archive(archived_retry):
    """目标任务缺失时保留归档并记录新失败原因。"""
    case = archived_retry
    case.downloader.get_torrents.return_value = ([], None)

    result = rename.retry_rename_by_hash(case.plugin, case.service, case.torrent_hash)

    assert result["code"] == 1
    state = case.data[archive.RETRY_STATE_KEY][case.torrent_hash]
    assert state["archived"] is True
    assert state["fail_count"] == 4
    assert state["category"] == "TASK_NOT_FOUND"
    case.downloader.qbc.torrents_rename.assert_not_called()
