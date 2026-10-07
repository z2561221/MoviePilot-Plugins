"""恢复原名接口使用宿主运行服务并保留失败历史。"""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from app.schemas import ServiceInfo
from app.plugins.downloadmanagerlocal.controller import handlers


@pytest.mark.parametrize("available", [True, False])
def test_recovery_uses_service_instance(monkeypatch, available):
    """配置对象不提供实例；接口必须走运行服务，失败不改写历史。"""
    calls = []
    records = {"a": {"original_name": "Original", "after_name": "Renamed", "success": True}}
    plugin = SimpleNamespace(_todownloader="QB", get_data=lambda key: deepcopy(records),
        save_data=lambda key, value: records.update(value))
    service = ServiceInfo(name="QB", type="qbittorrent", instance=SimpleNamespace(
        qbc=SimpleNamespace(torrents_rename=lambda **kw: calls.append(kw))))
    monkeypatch.setattr(handlers, "get_downloader_service", lambda name: service if available else None)
    result = handlers.api_recovery_torrent(plugin, "a")
    assert result.success is available
    assert records["a"]["after_name"] == ("Original" if available else "Renamed")
    assert calls == ([{"torrent_hash": "a", "new_torrent_name": "Original"}] if available else [])
