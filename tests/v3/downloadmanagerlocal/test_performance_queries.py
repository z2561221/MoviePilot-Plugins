"""性能优化的查询预算与业务边界；只使用内存存储和下载器替身。"""

from collections import Counter
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.plugins.downloadmanagerlocal.controller import handlers
from app.plugins.downloadmanagerlocal.model.state import RENAME_RECORDS_KEY, RENAME_RETRY_STATE_KEY
from app.plugins.downloadmanagerlocal.model.sync_delete import BLOCKS_KEY
from app.plugins.downloadmanagerlocal.service import archive, diagnostics, rename, speed_monitor, sync_delete
from app.plugins.downloadmanagerlocal.utils import torrent_adapter


class Store:
    """统计持久层读取并返回独立快照。"""

    def __init__(self, data=None):
        """创建当前实例的数据与读计数。"""
        self.data = data or {}
        self.reads = Counter()

    def get_data(self, key):
        """模拟持久层独立解码出的对象。"""
        self.reads[key] += 1
        return deepcopy(self.data.get(key))

    def save_data(self, key, value):
        """只保存到本测试的内存字典。"""
        self.data[key] = deepcopy(value)


def test_rename_selection_reads_archive_once_and_keeps_retry_semantics():
    """大量已归档失败记录只读一次状态，成功干净记录不进入补刀。"""
    history = {str(i): {"success": False} for i in range(1000)}
    history.update(failed={"success": False}, clean={"success": True, "after_name": "Example"})
    history[" 0 "] = {"success": False}
    plugin = Store({RENAME_RECORDS_KEY: history, RENAME_RETRY_STATE_KEY: {
        str(i): {"archived": True} for i in range(1000)
    }})
    assert rename.get_failed_rename_hashes(plugin) == {"failed"}
    assert plugin.reads == {RENAME_RECORDS_KEY: 1, RENAME_RETRY_STATE_KEY: 1}
    plugin.data[RENAME_RETRY_STATE_KEY]["0"]["archived"] = False
    assert rename.get_failed_rename_hashes(plugin) == {"0", " 0 ", "failed"}


def test_retry_rechecks_archive_after_downloader_response():
    """筛选后被归档的任务仍在执行前跳过，不使用旧快照放行。"""
    plugin = Store({RENAME_RECORDS_KEY: {"abc": {"success": False}}})
    plugin._rename_enabled, plugin._tag_enabled = True, False
    plugin.is_rename_archived = lambda key: archive.is_rename_archived(plugin, key)

    def query(ids):
        """模拟查询在途时管理员归档了该任务。"""
        assert ids == ["abc"]
        plugin.data[RENAME_RETRY_STATE_KEY] = {"abc": {"archived": True}}
        return [{"hash": "abc"}], None

    result = rename.retry_failed_renames(plugin, SimpleNamespace(
        type="qbittorrent", instance=SimpleNamespace(get_torrents=query),
    ))
    assert result["attempted"] == 0
    assert result["skipped"] == 1


@pytest.mark.parametrize("kind", ["qbittorrent", "transmission"])
def test_download_events_query_only_target_and_periodic_scan_stays_complete(monkeypatch, kind):
    """20 个事件只转换 20 项，周期扫描仍能发现事件以外的下载。"""
    items = [{"hash": f"{i:040x}", "name": "Example", "added_on": 100,
              "total_size": 1000, "downloaded": 100, "state": "downloading"}
             for i in range(5000)]
    if kind == "transmission":
        items = [SimpleNamespace(hashString=item["hash"], name="Example", dateAdded=100,
                                 totalSize=1000, downloadedEver=100, status="downloading")
                 for item in items]
    calls, converted = [], []

    def query(ids=None):
        """模拟两类宿主下载器的 ID 筛选。"""
        calls.append(ids)
        return [item for item in items if ids is None or (
            item["hash"] if kind == "qbittorrent" else item.hashString) in ids], None

    original = torrent_adapter.normalize_torrent

    def normalize(*args):
        """统计实际归一化的任务条数。"""
        converted.append(1)
        return original(*args)

    monkeypatch.setattr(torrent_adapter, "normalize_torrent", normalize)
    monkeypatch.setattr(speed_monitor, "dispatch_pending_speed_alerts", lambda *_: None)
    plugin = Store()
    plugin._enabled = plugin._speed_monitor_enabled = True
    plugin._speed_monitor_downloaders = ["D"]
    plugin.service_info = lambda _: SimpleNamespace(type=kind, instance=SimpleNamespace(get_torrents=query))
    for number in range(20):
        result = speed_monitor.handle_download_added_event(plugin, SimpleNamespace(
            event_data={"downloader": "D", "hash": f"{number:040x}"}), now=1000 + number)
        assert result["found"]
    assert calls == [[f"{number:040x}"] for number in range(20)]
    assert len(converted) == 20
    assert len(plugin._speed_monitor_runtime.sessions) == 20
    speed_monitor.scan_speed_monitor(plugin, now=1100)
    assert calls[-1] is None
    assert len(plugin._speed_monitor_runtime.sessions) == 5000


@pytest.mark.parametrize("response,success", [(([], None), True), (([], "offline"), False)])
def test_target_poll_keeps_empty_and_error_distinct(response, success):
    """定向查询不把失败当成任务缺失，也不改成全量重试。"""
    calls = []

    def query(ids):
        """返回预设查询结果并记录参数。"""
        calls.append(ids)
        return response

    result = torrent_adapter.poll_downloader(SimpleNamespace(get_torrents=query), "D", "qbittorrent", ids=["abc"])
    assert result.success is success
    assert calls == [["abc"]]
    assert result.items == ()
    assert torrent_adapter.poll_downloader(SimpleNamespace(get_torrents=query), "D", "qbittorrent", ids=[]).success
    assert calls == [["abc"]]


def test_block_scan_builds_one_index_per_batch_and_preserves_identity():
    """5000 个任务只遍历一次 1000 条标记，隔离下载器和新创建的同 hash。"""
    visits = []

    class Blocks(dict):
        """计数标记遍历，保留普通字典查找行为。"""

        def values(self):
            """记录构建索引时实际访问的每条标记。"""
            for value in super().values():
                visits.append(1)
                yield value

    blocks = Blocks({str(i): {"downloader": "D", "identity": [f"{i:040x}", 100, "/data"]}
                     for i in range(1000)})
    plugin = Store({BLOCKS_KEY: blocks})

    @sync_delete.coordinated
    def scan(current):
        """执行实际批次入口与逐任务避让检查。"""
        for number in range(5000):
            task = {"hash": f"{number:040x}", "added_on": 100}
            assert sync_delete.task_blocked(current, "D", task, "qbittorrent") is (number < 1000)
        assert not sync_delete.task_blocked(current, "other", {"hash": "0" * 40, "added_on": 100}, "qbittorrent")
        assert not sync_delete.task_blocked(current, "D", {"hash": "0" * 40, "added_on": 101}, "qbittorrent")

    scan(plugin)
    assert len(visits) == 1000
    assert plugin.reads[BLOCKS_KEY] == 1
    assert plugin._sync_delete_block_index is None


def test_nested_block_snapshot_restores_outer_and_next_batch_refreshes():
    """嵌套失败恢复外层索引，退出批次后从持久层读取新状态。"""
    plugin = Store({BLOCKS_KEY: {"old": {"downloader": "D", "identity": ["abc", 100, "/data"]}}})
    task = {"hash": "abc", "added_on": 100}

    @sync_delete.coordinated
    def inner(current):
        """内层读取已更新的快照，并模拟业务异常。"""
        assert not sync_delete.task_blocked(current, "D", task, "qbittorrent")
        raise RuntimeError("test failure")

    @sync_delete.coordinated
    def outer(current):
        """外层在内层异常后继续使用自己的批次快照。"""
        assert sync_delete.task_blocked(current, "D", task, "qbittorrent")
        current.data[BLOCKS_KEY] = {}
        with pytest.raises(RuntimeError, match="test failure"):
            inner(current)
        assert sync_delete.task_blocked(current, "D", task, "qbittorrent")

    outer(plugin)
    assert not sync_delete.task_blocked(plugin, "D", task, "qbittorrent")
    assert not sync_delete.task_blocked(Store(), "D", task, "qbittorrent")


def test_overview_reuses_diagnostics_archive_snapshot(monkeypatch):
    """真实诊断和总览组合只读取一次归档状态，并保持限速卡片一致。"""
    plugin = Store()
    plugin._fromdownloader = plugin._todownloader = plugin._fromtorrentpath = ""
    plugin._frompath = plugin._topath = ""
    for name in ("enabled", "transfer_active", "transfer_enabled", "transfer_fallback_enabled",
                 "rename_enabled", "tag_enabled", "iyuu_enabled", "seed_autostart", "seed_skipverify"):
        setattr(plugin, "_" + name, False)
    plugin.plugin_name, plugin.plugin_version = "下载中心", "test"
    plugin.get_state = lambda: False
    plugin.rename_archive_stats = lambda: archive.rename_archive_stats(plugin)
    plugin._diagnostics = lambda: diagnostics.build_diagnostics(plugin)
    monkeypatch.setattr(handlers, "_speed_monitor_overview", lambda _: {})
    monkeypatch.setattr(handlers, "get_upload_limit_status", lambda _: {"managed_torrents": 123, "active": True})
    result = handlers.api_overview(plugin)
    assert plugin.reads[RENAME_RETRY_STATE_KEY] == 1
    assert result.archive["archived"] == 0
    assert result.upload_limit["managed_torrents"] == result.cards["upload_limit"]["managed"] == 123
