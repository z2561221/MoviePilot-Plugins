"""验证下载器后处理与批量补刀的字段兼容和结果计数。"""

from __future__ import annotations

from types import SimpleNamespace

from app.plugins.downloadmanagerlocal.service import rename, site_tag, transfer
from app.plugins.downloadmanagerlocal.utils.torrent_adapter import get_tracker_urls


def test_qb_missing_trackers_is_an_empty_compatible_field() -> None:
    """qB 任务字典没有 trackers 时，后处理应得到空列表而不是抛属性异常。"""
    torrent = {"hash": "abc", "name": "seed", "tags": "🏠site", "save_path": "/downloads"}

    assert get_tracker_urls(torrent, "qbittorrent") == []


def test_qb_tracker_property_is_used_for_site_tagging() -> None:
    """qB TorrentDictionary 风格的 trackers 属性必须参与站点标签识别。"""
    class QbTorrent(dict):
        """模拟 qB 任务字典通过属性提供 trackers。"""

        @property
        def trackers(self):
            """返回 qB tracker 对象风格字段。"""
            return [SimpleNamespace(url="https://tracker.example/announce", tier=0)]

    torrent = QbTorrent({"hash": "abc", "tags": "", "save_path": "/downloads"})

    assert get_tracker_urls(torrent, "qbittorrent") == [
        "https://tracker.example/announce"
    ]


def test_site_tag_writes_qb_tag_from_tracker_property(monkeypatch) -> None:
    """tracker 属性识别站点后，必须实际调用 qB 标签写入接口。"""
    class QbTorrent(dict):
        """模拟带 tracker 属性的 qB 任务。"""

        @property
        def trackers(self):
            """返回站点 tracker。"""
            return [SimpleNamespace(url="https://tracker.example/announce", tier=0)]

    writes = []
    plugin = SimpleNamespace(
        _tracker_mappings={},
        _tag_siteprefix="🏠",
        _tag_enabled=True,
    )
    downloader = SimpleNamespace(
        set_torrents_tag=lambda **kwargs: writes.append(kwargs),
    )
    monkeypatch.setattr(site_tag, "find_site_by_domain", lambda domain: "ExampleSite")
    monkeypatch.setattr(site_tag, "get_url_domain", lambda url: "tracker.example")

    site_tag.tag_torrent(
        plugin,
        downloader,
        "qbittorrent",
        "abc",
        [],
        get_tracker_urls(QbTorrent({}), "qbittorrent"),
    )

    assert writes == [{"ids": "abc", "tags": ["🏠ExampleSite"]}]


def test_transfer_postprocess_calls_rename_and_tag_without_qb_trackers(monkeypatch) -> None:
    """真实 qB 字典缺少 trackers 时，转移后重命名和标签仍按顺序执行。"""
    calls = []
    torrent = {"hash": "abc", "name": "seed", "tags": "tag-a", "save_path": "/downloads"}
    downloader = SimpleNamespace(get_torrents=lambda ids: ([torrent], None))
    service = SimpleNamespace(type="qbittorrent", instance=downloader)
    plugin = SimpleNamespace(
        _rename_enabled=True,
        _tag_enabled=True,
        _rename_torrent=lambda *args: calls.append(("rename", args[-1])),
        _tag_torrent=lambda *args: calls.append(("tag", args[-1])),
        _transfer_stop_generation=0,
        _event=SimpleNamespace(is_set=lambda: False),
    )

    transfer.post_transfer_process(plugin, service, "abc", 0)

    assert calls == [("rename", "/downloads"), ("tag", [])]


def test_batch_retry_counts_real_success_and_failure(monkeypatch) -> None:
    """批量补刀计数必须依据重命名和标签返回值，而不是循环次数。"""
    torrents = [
        {"hash": "ok", "name": "ok", "save_path": "/downloads"},
        {"hash": "bad", "name": "bad", "save_path": "/downloads"},
    ]
    service = SimpleNamespace(
        type="qbittorrent",
        instance=SimpleNamespace(get_torrents=lambda ids: (torrents, None)),
    )
    plugin = SimpleNamespace(
        _rename_enabled=True,
        _tag_enabled=False,
        is_rename_archived=lambda value: False,
        get_data=lambda key: {},
    )
    monkeypatch.setattr(rename, "get_failed_rename_hashes", lambda _plugin: {"ok", "bad"})
    monkeypatch.setattr(rename, "resolve_retry_original_name", lambda *_args: "clean")
    monkeypatch.setattr(rename, "_get_torrent_content_name", lambda *_args: "original")
    monkeypatch.setattr(rename, "_find_iyuu_source_hash", lambda *_args: "")
    monkeypatch.setattr(rename, "rename_torrent", lambda _plugin, _dl, _kind, torrent_hash, *_args: torrent_hash == "ok")

    result = rename.retry_failed_renames(plugin, service)

    assert result["attempted"] == 2
    assert result["success"] == 1
    assert result["failed"] == 1


def test_retry_pending_renames_exposes_partial_failure(monkeypatch) -> None:
    """部分成功的批量补刀使用 code=2，并保留失败明细。"""
    plugin = SimpleNamespace(
        _todownloader="QB2",
        service_info=lambda _name: SimpleNamespace(instance=object()),
        _retry_failed_renames=lambda _service: {
            "attempted": 2, "success": 1, "failed": 1, "skipped": 0,
            "errors": ["hash-a: 重命名失败"],
        },
    )
    monkeypatch.setattr(transfer, "retry_dirty_torrent_names", lambda *_args: {
        "attempted": 1, "success": 1, "failed": 0, "skipped": 0, "errors": [],
    })

    result = transfer.retry_pending_renames(plugin)

    assert result["code"] == 2
    assert result["history"] == 1
    assert result["dirty"] == 1
    assert result["failed"] == 1
    assert result["errors"] == ["hash-a: 重命名失败"]
