"""批量写入预算、部分失败和停止边界，下载器全部为内存替身。"""

import runpy
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.adapter.upload_limit import (
    normalize_upload_torrent,
)
from app.plugins.downloadmanagerlocal.service import upload_limit_apply as apply
from app.plugins.downloadmanagerlocal.service import upload_limiter as limiter

fakes = runpy.run_path(str(Path(__file__).with_name("test_upload_limiter_service.py")))


@pytest.mark.parametrize("kind", ["qbittorrent", "transmission"])
def test_thousand_equal_limits_use_ten_requests_then_zero_when_unchanged(kind):
    """1000项同额度只发10块，下一轮未变化不写入。"""
    factory = fakes["qb_torrent" if kind == "qbittorrent" else "tr_torrent"]
    items = [factory(str(n), "A", rate=1024) for n in range(1000)]
    instance = fakes["FakeQbInstance" if kind == "qbittorrent" else "FakeTransmissionInstance"](items)
    plugin = fakes["FakePlugin"]({"D": SimpleNamespace(type=kind, instance=instance)}, ["D"], {"D": 5000}, {"A": {"limit_kib": 2000}})
    result = limiter.run_upload_limit_cycle(plugin, now=1000)
    calls = instance.qbc.torrent_calls if kind == "qbittorrent" else instance.trc.torrent_calls
    assert len(calls) == 10 and not result["errors"]
    assert all(len(call[0] if kind == "qbittorrent" else call["ids"]) == 100 for call in calls)
    calls.clear()
    limiter.run_upload_limit_cycle(plugin, now=1030)
    assert not calls


def case(count=205):
    """为直接执行模块构造已确定额度的隔离输入。"""
    instance = fakes["FakeQbInstance"]([fakes["qb_torrent"](str(n), "A", limit_kib=7) for n in range(count)])
    tasks = {item.key: item for item in [normalize_upload_torrent(raw, "D", "qbittorrent") for raw in instance.qbc.torrents]}
    records = {key: {"original_settings": {"limit_bps": 7 * 1024, "enabled": True}} for key in tasks}
    contexts = {"D": SimpleNamespace(service=SimpleNamespace(instance=instance))}
    desired = {key: 2 for key in tasks}
    return instance, tasks, records, contexts, desired


def test_partial_batch_error_retains_original_and_does_not_retry_failed_members():
    """失败块部分生效仍保留原值；其它块可执行，失败块不逐项盲重试。"""
    instance, tasks, records, contexts, desired = case()
    write = instance.qbc.torrents_set_upload_limit
    calls = []

    def partial(limit, torrent_hashes):
        """第一块只写首项后抛错，模拟响应未知。"""
        calls.append(torrent_hashes)
        if len(calls) == 1:
            write(limit, torrent_hashes[0])
            raise RuntimeError("partial RPC error")
        return write(limit, torrent_hashes)

    instance.qbc.torrents_set_upload_limit = partial
    errors = defaultdict(list)
    apply.apply_torrent_limits(tasks, contexts, records, desired, 1000, lambda: None, errors)
    assert len(calls) == 3 and len(errors["D"]) == 100
    assert records["D:0"]["original_settings"]["limit_bps"] == 7 * 1024
    assert "last_written_settings" not in records["D:0"]
    current = normalize_upload_torrent(instance.qbc.torrents[0], "D", "qbittorrent")
    assert apply.matches_managed_settings(records["D:0"], current.upload_settings)
    assert "pending_write_settings" not in records["D:204"]


def test_stop_after_first_batch_never_sends_remaining_batches():
    """块请求返回后停止，下一块不得进入下载器。"""
    instance, tasks, records, contexts, desired = case()
    original = instance.qbc.torrents_set_upload_limit
    stopped = False

    def write(*args, **kwargs):
        """第一块生效后模拟用户停用。"""
        nonlocal stopped
        original(*args, **kwargs)
        stopped = True

    def checkpoint():
        """复用真实停止异常，中断全部后续块。"""
        if stopped:
            raise limiter.UploadCycleStopped("stopped")

    instance.qbc.torrents_set_upload_limit = write
    with pytest.raises(limiter.UploadCycleStopped):
        apply.apply_torrent_limits(tasks, contexts, records, desired, 1000, checkpoint, defaultdict(list))
    assert len(instance.qbc.torrent_calls) == 1


def test_failed_intent_restore_keeps_manual_override_and_original_limits():
    """待确认意图匹配时恢复旧值，管理员随后改值则保留手动设置。"""
    instance, _tasks, records, _contexts, _desired = case(2)
    for record in records.values():
        record.update(downloader_id="D", pending_write_settings={"limit_bps": 2048, "enabled": True})
    instance.qbc.torrents[0]["up_limit"] = 2048
    instance.qbc.torrents[1]["up_limit"] = 9 * 1024
    snapshots = {item.key: item for item in [normalize_upload_torrent(raw, "D", "qbittorrent") for raw in instance.qbc.torrents]}
    result = limiter._release_downloader_torrent_limits(state={"torrents": records}, downloader_id="D", instance=instance,
                                                       downloader_type="qbittorrent", snapshots=snapshots)
    assert result["restored"] == 1 and result["preserved_manual"] == 1
    assert instance.qbc.torrents[0]["up_limit"] == 7 * 1024
    assert instance.qbc.torrents[1]["up_limit"] == 9 * 1024
