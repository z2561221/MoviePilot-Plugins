"""验证 IYUU 实际目标记录与停止代次边界，禁止真实外部调用。"""

import threading
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.service import cleanup, iyuu


def test_split_downloader_history_cleans_actual_destination(monkeypatch):
    """主辅分离的历史及同步删除均指向实际目标下载器。"""
    state, added, deleted = {}, [], []
    source = SimpleNamespace(name="QB1")
    target = SimpleNamespace(name="QB2")
    plugin = SimpleNamespace(
        _event=threading.Event(), _iyuu_success_caches=[], _iyuu_error_caches=[],
        _iyuu_permanent_error_caches=[], _iyuu_sites=[],
        iyuu_helper=SimpleNamespace(
            get_seed_info=lambda hashes: ({"mother": {"torrent": [{"sid": 1, "info_hash": "child"}]}}, ""),
            get_torrent_url=lambda sid: ("https://example.invalid", "/download"),
        ),
        get_data=lambda key=None: state.get(key),
        save_data=lambda key, value: state.__setitem__(key, value),
        service_info=lambda name: SimpleNamespace(instance=SimpleNamespace(
            delete_torrents=lambda **kw: deleted.append((name, kw["ids"])),
        )),
    )
    monkeypatch.setattr(iyuu, "get_url_domain", lambda url: "example.invalid")
    monkeypatch.setattr(iyuu, "get_site_indexer", lambda domain: {"url": "https://example.invalid", "id": 1})
    monkeypatch.setattr(iyuu, "iyuu_auto_service_info", lambda p: target)
    monkeypatch.setattr(iyuu, "iyuu_download_torrent", lambda p, **kw: (added.append(kw["service"].name) or True))
    iyuu.iyuu_seed_torrents(plugin, [{"hash": "mother", "save_path": "/fake"}], source)
    cleanup._cleanup_iyuu_targets(plugin, "mother")
    assert added == ["QB2"]
    assert deleted == [("QB2", ["child"])]


@pytest.mark.parametrize("kind", ["qbittorrent", "transmission"])
@pytest.mark.parametrize("clear_event", [False, True])
def test_stop_or_reinitialize_blocks_iyuu_add(kind, clear_event):
    """停止或重初始化清除事件后，旧批次都不得继续添加目标。"""
    event = threading.Event()
    event.set()
    if clear_event:
        event.clear()
    plugin = SimpleNamespace(_event=event, _transfer_stop_generation=2)
    writes = []
    service = SimpleNamespace(type=kind, instance=SimpleNamespace(add_torrent=lambda **kw: writes.append(kw)))
    result = iyuu.iyuu_download(plugin, service, b"fake", "/fake", "", "site", stop_generation=1)
    assert result is None
    assert writes == []


def test_stop_during_seed_lookup_blocks_followup(monkeypatch):
    """IYUU 查询期间停用时，返回结果不能再触发站点或下载器处理。"""
    event = threading.Event()

    def lookup(hashes):
        """模拟请求返回时停止事件已到达。"""
        event.set()
        return {"mother": {"torrent": [{"sid": 1, "info_hash": "child"}]}}, ""

    plugin = SimpleNamespace(_event=event, iyuu_helper=SimpleNamespace(get_seed_info=lookup))
    calls = []
    monkeypatch.setattr(iyuu, "iyuu_download_torrent", lambda *a, **kw: calls.append(kw))
    iyuu.iyuu_seed_torrents(plugin, [{"hash": "mother"}], SimpleNamespace(name="QB1"))
    assert calls == []
