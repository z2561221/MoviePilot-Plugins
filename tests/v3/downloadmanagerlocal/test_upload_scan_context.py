"""扫描上下文的单次读取、失败保留和部分分类进度契约。"""

import runpy
from pathlib import Path
from types import SimpleNamespace

from app.plugins.downloadmanagerlocal.service import upload_limit_scan as scan
from app.plugins.downloadmanagerlocal.service import upload_limiter as limiter

fakes = runpy.run_path(str(Path(__file__).with_name("test_upload_limiter_service.py")))


def plugin_case():
    """创建两项任务的隔离下载器与已启用站点策略。"""
    instance = fakes["FakeQbInstance"]([fakes["qb_torrent"]("one", "A"), fakes["qb_torrent"]("two", "A")])
    plugin = fakes["FakePlugin"]({"D": SimpleNamespace(type="qbittorrent", instance=instance)},
                                 ["D"], {"D": 100}, {"A": {"limit_kib": 20}})
    return plugin, instance


def test_cycle_reuses_one_downloader_poll_for_classification_allocation_and_summary(monkeypatch):
    """从扫描到状态汇总只查一次任务列表，避免结构拆分引入额外RPC。"""
    plugin, instance = plugin_case()
    calls = []
    read = instance.get_torrents

    def query():
        """记录实际下载器读取次数。"""
        calls.append(1)
        return read()

    monkeypatch.setattr(instance, "get_torrents", query)
    result = limiter.run_upload_limit_cycle(plugin, now=1000)
    assert len(calls) == 1
    assert result["managed_torrents"] == 2 and result["service_status"] == "running"
    assert result["downloaders"][0]["type"] == "qbittorrent"
    assert result["sites"][0]["torrent_count"] == 2


def test_failed_poll_does_not_purge_previous_torrent_state(monkeypatch):
    """任务读取失败时保留原宽限和恢复记录，不能把失败解释为空下载器。"""
    plugin, instance = plugin_case()
    limiter.run_upload_limit_cycle(plugin, now=1000)
    before = dict(plugin._upload_limit_state["torrents"])
    monkeypatch.setattr(instance, "get_torrents", lambda: ([], "offline"))
    result = limiter.run_upload_limit_cycle(plugin, now=1030)
    assert plugin._upload_limit_state["torrents"] == before
    assert result["service_status"] == "error"
    assert "offline" in result["errors"][0]


def test_classification_error_retains_preceding_valid_tasks(monkeypatch):
    """后项分类异常仍保留之前的有效任务，保持原逐项进度及异常汇总。"""
    plugin, _ = plugin_case()
    original = limiter._resolve_limited_site
    calls = []

    def resolve(*args):
        """第一项正常，第二项模拟异常输入。"""
        calls.append(1)
        if len(calls) == 2:
            raise ValueError("classification failed")
        return original(*args)

    monkeypatch.setattr(limiter, "_resolve_limited_site", resolve)
    result = limiter.run_upload_limit_cycle(plugin, now=1000)
    assert result["managed_torrents"] == 1
    assert result["service_status"] == "degraded"
    assert "classification failed" in result["errors"][0]


def test_scan_context_contains_completed_subset_without_losing_incomplete_tasks():
    """上下文保存完整列表及已完成子集，下游退出策略仍能找到未完成任务。"""
    plugin, instance = plugin_case()
    instance.qbc.torrents[1].update(state="downloading", progress=0.5, amount_left=512)
    context = scan.scan_downloader(plugin, "D", 100, {}, 1000, lambda: None)
    assert set(context.all_snapshots) == {"D:one", "D:two"}
    assert set(context.snapshots) == {"D:one"}
    assert context.initial_scan_pending
