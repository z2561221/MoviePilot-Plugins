"""辅种已接收目标跨故障与重载续办，绝不重复提交。"""

from copy import deepcopy
import threading
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.model.state import IYUU_PENDING_KEY, SEED_RECHECK_QUEUE_KEY
from app.plugins.downloadmanagerlocal.service import iyuu, recheck


@pytest.mark.parametrize("failure", ["journal", "accepted_save", "history", "queue", "recheck", "stop"])
def test_accepted_target_recovers_without_duplicate_submission(monkeypatch, failure):
    """故障注入覆盖意图落盘、接收回写、历史、队列、校验及停止。"""
    data, added, existing = {}, [], set()
    fault = {"value": failure}

    def save(key, value):
        """模拟真实序列化存储和指定阶段失败。"""
        if fault["value"] == "journal" and key == IYUU_PENDING_KEY:
            raise OSError("journal unavailable")
        if fault["value"] == "accepted_save" and key == IYUU_PENDING_KEY and any(v.get("download_id") for v in value.values()):
            raise OSError("accepted write unavailable")
        if fault["value"] == "history" and key == "iyuu_mother":
            raise OSError("history unavailable")
        if fault["value"] == "queue" and key == SEED_RECHECK_QUEUE_KEY:
            raise OSError("queue unavailable")
        data[key] = deepcopy(value)

    plugin = SimpleNamespace(
        _event=threading.Event(), _transfer_stop_generation=0,
        _iyuu_total=0, _iyuu_realtotal=0, _iyuu_success=0, _iyuu_fail=0,
        _iyuu_cached=0, _iyuu_exist=0, _iyuu_success_caches=[],
        _iyuu_error_caches=[], _iyuu_permanent_error_caches=[], _iyuu_sites=[],
        _seed_skipverify=False, _seed_autostart=True, _seed_max_wait_minutes=120,
        _rename_enabled=False, _tag_enabled=False,
        iyuu_helper=SimpleNamespace(
            get_seed_info=lambda hashes: ({"mother": {"torrent": [{"sid": 1, "info_hash": "child"}]}}, ""),
            get_torrent_url=lambda sid: ("https://example.invalid", "/download"),
        ),
        get_data=lambda key=None: deepcopy(data.get(key)), save_data=save,
    )
    service = SimpleNamespace(name="QB", type="qbittorrent", instance=SimpleNamespace(
        get_torrents=lambda **kw: ([{"hash": "child"}] if existing else [], None),
        recheck_torrents=lambda **kw: fault["value"] != "recheck",
    ))
    plugin.service_info = lambda name: service
    plugin._register_seed_recheck = lambda *args: recheck.register_seed_recheck(plugin, *args)

    def add(*args, **kwargs):
        """只记录提交，在接收返回边界可触发停止。"""
        added.append("child")
        existing.add("child")
        if fault["value"] == "stop":
            plugin._event.set()
        return "child"

    monkeypatch.setattr(recheck, "ensure_seed_recheck_worker", lambda p: None)
    monkeypatch.setattr(iyuu, "get_url_domain", lambda url: "example.invalid")
    monkeypatch.setattr(iyuu, "get_site_indexer", lambda domain: {"id": 1, "name": "fake", "url": "https://example.invalid"})
    monkeypatch.setattr(iyuu, "iyuu_auto_service_info", lambda p: service)
    monkeypatch.setattr(iyuu, "check_site", lambda domain: (False, ""))
    monkeypatch.setattr(iyuu, "iyuu_get_download_url", lambda *a, **kw: "https://example.invalid/torrent")
    monkeypatch.setattr(iyuu, "download_torrent_content", lambda **kw: (None, b"fake", None, None, None))
    monkeypatch.setattr(iyuu, "is_torrent_content", lambda content: True)
    monkeypatch.setattr(iyuu, "iyuu_download", add)
    monkeypatch.setattr(iyuu, "is_downloader_type", lambda kind, service: kind == service.type)
    try:
        iyuu.iyuu_seed_torrents(plugin, [{"hash": "mother", "save_path": "/fake"}], service)
    except OSError:
        assert failure in {"journal", "accepted_save"}
    assert plugin._iyuu_success_caches == []
    if failure == "journal":
        assert added == []
        return
    assert added == ["child"] and data[IYUU_PENDING_KEY]

    # 新实例只读取存储恢复身份；不依赖旧实例的内存缓存。
    fault["value"] = None
    restored = SimpleNamespace(**vars(plugin))
    restored._event = threading.Event()
    restored._transfer_stop_generation = 1
    restored._iyuu_success_caches = []
    restored._register_seed_recheck = lambda *args: recheck.register_seed_recheck(restored, *args)
    iyuu._resume_iyuu_postprocess(restored, 1)
    assert added == ["child"]
    assert data[IYUU_PENDING_KEY] == {}
    assert data["iyuu_mother"] == [{"downloader": "QB", "torrents": ["child"]}]
    assert "QB::child" in data[SEED_RECHECK_QUEUE_KEY]
    assert restored._iyuu_success_caches == ["child"]
    assert restored._iyuu_success == 1
    iyuu._resume_iyuu_postprocess(restored, 1)
    assert restored._iyuu_success == 1
