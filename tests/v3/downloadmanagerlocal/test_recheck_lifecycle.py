"""验证做种校验 worker 的停止、队列隔离和并发合并。"""

from __future__ import annotations

import threading
from copy import deepcopy
from types import SimpleNamespace

from app.plugins.downloadmanagerlocal.service import lifecycle, recheck


def test_initialization_resumes_persisted_recheck_once(monkeypatch):
    """启用后恢复已有校验队列，重复初始化不遗留旧 worker。"""
    data = {"seed_recheck_queue": {"QB1::a": {"hash": "a", "downloader": "QB1"}}}
    plugin = _plugin(data)
    plugin._event = threading.Event()
    plugin._transfer_active = False
    plugin._onlyonce = False
    plugin._iyuu_enabled = False
    plugin._speed_monitor_enabled = False
    plugin._upload_limit_enabled = False
    plugin.stop_service = lambda: recheck.stop_seed_recheck_worker(plugin)
    monkeypatch.setattr(lifecycle, "initialize_runtime_config", lambda p, c: c)
    monkeypatch.setattr(lifecycle, "load_upload_limit_state", lambda p: {})
    starts = []
    monkeypatch.setattr(lifecycle, "ensure_seed_recheck_worker", lambda p: starts.append(p))
    lifecycle.initialize_plugin(plugin, {"enabled": True})
    assert starts == [plugin]
    plugin._enabled = False
    lifecycle.initialize_plugin(plugin, {"enabled": False})
    assert starts == [plugin]


def test_recheck_restart_after_old_worker_finishes(monkeypatch):
    """旧 worker 停止超时后，恢复请求在旧线程结束时接续。"""
    plugin = _plugin({})
    plugin._event = threading.Event()
    plugin._seed_recheck_running = True
    old_stop = threading.Event()
    old_stop.set()
    plugin._seed_recheck_stop_event = old_stop
    recheck.ensure_seed_recheck_worker(plugin)
    assert plugin._seed_recheck_restart_pending is True
    starts = []
    monkeypatch.setattr(recheck, "ensure_seed_recheck_worker", lambda p: starts.append(p))
    recheck.seed_recheck_loop(plugin, old_stop)
    assert starts == [plugin]


def _plugin(data, **kwargs):
    """构造做种校验服务最小插件替身。"""
    plugin = SimpleNamespace(
        _enabled=True,
        _seed_max_wait_minutes=120,
        _seed_check_interval=0.01,
        _seed_recheck_running=False,
        _seed_recheck_lock=threading.RLock(),
        _seed_recheck_queue_lock=None,
        _seed_recheck_thread=None,
        _seed_recheck_stop_event=None,
        get_data=lambda key: deepcopy(data.get(key)),
        save_data=lambda key, value: data.__setitem__(key, deepcopy(value)),
        **kwargs,
    )
    return plugin


def test_queue_identity_keeps_same_hash_on_two_downloaders(monkeypatch):
    """相同 hash 在不同下载器中必须保持两条独立记录。"""
    data = {}
    plugin = _plugin(data)
    monkeypatch.setattr(recheck, "ensure_seed_recheck_worker", lambda _plugin: None)

    recheck.register_seed_recheck(plugin, "QB1", ["same-hash"], "transfer")
    recheck.register_seed_recheck(plugin, "QB2", ["same-hash"], "iyuu")

    queue = recheck.load_seed_recheck_queue(plugin)
    assert set(queue) == {"QB1::same-hash", "QB2::same-hash"}


def test_worker_merge_preserves_task_registered_during_scan(monkeypatch):
    """旧扫描结果写回时不得覆盖扫描期间新增的队列项。"""
    old_key = "QB1::old-hash"
    data = {
        "seed_recheck_queue": {
            old_key: {
                "hash": "old-hash", "downloader": "QB1", "created_at": 1,
                "updated_at": 1, "max_wait_minutes": 120,
            }
        }
    }
    plugin = _plugin(data)
    monkeypatch.setattr(recheck, "ensure_seed_recheck_worker", lambda _plugin: None)
    before = recheck.load_seed_recheck_queue(plugin)
    after = {}
    recheck.register_seed_recheck(plugin, "QB2", ["new-hash"], "iyuu")

    recheck._merge_processed_queue(plugin, before, after)

    queue = recheck.load_seed_recheck_queue(plugin)
    assert "QB1::old-hash" not in queue
    assert "QB2::new-hash" in queue


def test_stop_event_blocks_ready_task_write():
    """停止事件已经设置时，ready 任务不得调用 start_torrents。"""
    started = []
    stop_event = threading.Event()
    stop_event.set()
    torrent = {"hash": "ready", "state": "pausedUP"}
    service = SimpleNamespace(
        type="qbittorrent",
        instance=SimpleNamespace(
            get_torrents=lambda ids: ([torrent], None),
            start_torrents=lambda ids: started.append(ids),
        ),
    )
    plugin = _plugin(
        {},
        service_info=lambda _name: service,
        get_hash=lambda item, _kind: item["hash"],
    )
    queue = {
        "QB1::ready": {
            "hash": "ready", "downloader": "QB1", "created_at": 1,
            "updated_at": 1, "max_wait_minutes": 120,
        }
    }

    recheck.process_seed_recheck_once(plugin, queue, stop_event=stop_event)

    assert started == []


def test_successful_empty_poll_removes_expired_item():
    """成功空查询也必须让超时队列项退出。"""
    service = SimpleNamespace(
        type="qbittorrent",
        instance=SimpleNamespace(get_torrents=lambda ids: ([], None)),
    )
    plugin = _plugin(
        {},
        service_info=lambda _name: service,
        get_hash=lambda item, _kind: item["hash"],
    )
    queue = {
        "QB1::missing": {
            "hash": "missing", "downloader": "QB1", "created_at": 1,
            "updated_at": 1, "max_wait_minutes": 1,
        }
    }

    changed = recheck.process_seed_recheck_once(plugin, queue)

    assert changed is True
    assert queue == {}
