"""验证自动开始、清理重试、辅种并发和统计跨日边界。"""

import threading
import time
from types import SimpleNamespace

from app.plugins.downloadmanagerlocal.model import state
from app.plugins.downloadmanagerlocal.service import cleanup, iyuu, recheck


def test_autostart_off_retains_ready_task_without_start():
    """关闭自动开始时保留待处理队列，重新开启才启动。"""
    started = []
    plugin = SimpleNamespace(
        _seed_autostart=False, _seed_max_wait_minutes=120,
        service_info=lambda _: SimpleNamespace(type="qbittorrent", instance=SimpleNamespace(
            get_torrents=lambda **kw: ([{"hash": "a", "state": "pausedUP", "progress": 1}], None),
            start_torrents=lambda **kw: started.append(kw),
        )), get_hash=lambda torrent, kind: torrent["hash"],
    )
    queue = {"QB2::a": {"hash": "a", "downloader": "QB2", "created_at": time.time()}}
    recheck.process_seed_recheck_once(plugin, queue)
    assert started == [] and queue
    plugin._seed_autostart = True
    recheck.process_seed_recheck_once(plugin, queue)
    assert len(started) == 1 and not queue


def test_failed_cleanup_retries_then_deduplicates_success():
    """删除失败不占用去重窗口，成功后的重复事件才跳过。"""
    calls = []

    def delete(**kwargs):
        """第一次故障、第二次成功，均不访问真实下载器。"""
        calls.append(kwargs)
        return len(calls) > 1

    plugin = SimpleNamespace(
        _fromdownloader="QB1",
        get_data=lambda key: {"to_download": "QB2", "to_download_id": "child"} if key == "QB1-source" else [],
        service_info=lambda _: SimpleNamespace(instance=SimpleNamespace(delete_torrents=delete)),
    )
    assert cleanup.cleanup_by_hash(plugin, "source")["transfer_deleted"] == 0
    assert cleanup.cleanup_by_hash(plugin, "source")["transfer_deleted"] == 1
    assert cleanup.cleanup_by_hash(plugin, "source")["skipped"] is True
    assert len(calls) == 2


def test_iyuu_failure_count_is_independent_of_success(monkeypatch):
    """失败可多于成功，跨日仅清零当日计数。"""
    data = {}
    plugin = SimpleNamespace(get_data=lambda key: data.get(key), save_data=lambda key, value: data.__setitem__(key, value))
    monkeypatch.setattr(state, "today_stamp", lambda: "2026-09-24")
    state.record_iyuu_results(plugin, success=0, fail=3)
    assert state.load_iyuu_stats(plugin)["today_fail"] == 3
    monkeypatch.setattr(state, "today_stamp", lambda: "2026-09-25")
    result = state.load_iyuu_stats(plugin)
    assert result["today_fail"] == 0 and result["fail_total"] == 3


def test_transfer_prior_days_total_rolls_forward_without_recount(monkeypatch):
    """今日和兜底次日归零，昨日成功只纳入累计一次。"""
    data = {"transfer_stats": {"success_total": 227, "fallback_success": 89,
                              "today_date": "2026-09-24", "today_success": 31, "today_fallback": 7}}
    plugin = SimpleNamespace(get_data=lambda key: data.get(key), save_data=lambda key, value: data.__setitem__(key, value))
    monkeypatch.setattr(state, "today_stamp", lambda: "2026-09-24")
    before = state.load_transfer_stats(plugin)
    assert (before["today_success"], before["today_fallback"], before["success_total"] - before["today_success"]) == (31, 7, 196)
    monkeypatch.setattr(state, "today_stamp", lambda: "2026-09-25")
    after = state.load_transfer_stats(plugin)
    assert (after["today_success"], after["today_fallback"], after["success_total"] - after["today_success"]) == (0, 0, 227)
    state.record_transfer_success(plugin, 2, fallback=True)
    next_stats = state.load_transfer_stats(plugin)
    assert (next_stats["today_success"], next_stats["today_fallback"], next_stats["success_total"] - next_stats["today_success"]) == (2, 2, 227)


def test_overlapping_iyuu_run_does_not_reset_active_counters(monkeypatch):
    """重叠触发直接跳过，活动批次和后续独立批次各结算一次。"""
    entered, finish = threading.Event(), threading.Event()
    plugin = SimpleNamespace(_event=threading.Event())
    calls, totals = [], []

    def run(p, generation):
        """将首批次挂在可控屏障上，验证重复触发行为。"""
        calls.append(generation)
        p._iyuu_success = 1
        entered.set()
        assert finish.wait(3)

    monkeypatch.setattr(iyuu, "_iyuu_auto_seed", run)
    monkeypatch.setattr(iyuu, "record_iyuu_results", lambda p, **counts: totals.append(counts))
    worker = threading.Thread(target=iyuu.iyuu_auto_seed, args=(plugin,))
    worker.start()
    try:
        assert entered.wait(2)
        iyuu.iyuu_auto_seed(plugin)
        assert len(calls) == 1 and plugin._iyuu_success == 1
    finally:
        finish.set()
        worker.join(4)
    iyuu.iyuu_auto_seed(plugin)
    assert len(calls) == 2
    assert [item["success"] for item in totals] == [1, 1]
