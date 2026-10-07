"""转种查询、校验和删除失败必须保留源任务与续办阶段。"""

import threading
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.service import transfer


@pytest.mark.parametrize("failure", ["query_error", "missing", "recheck", "delete", "ok"])
def test_transfer_completion_requires_successful_target_and_writes(monkeypatch, failure):
    """真实后处理链拒绝失败返回，恢复后同一目标可完成收尾。"""
    data, deleted, checked = {}, [], []
    stage = {"failure": failure}

    def query(**kwargs):
        """仅查询模拟目标，连接错误与空结果分别覆盖。"""
        if stage["failure"] == "query_error":
            return None, "connection failed"
        if stage["failure"] == "missing":
            return [], None
        return [{"hash": "a", "name": "Example", "save_path": "/fake"}], None

    def recheck(**kwargs):
        """模拟校验请求的布尔回执。"""
        checked.append(kwargs)
        return stage["failure"] != "recheck"

    def delete(**kwargs):
        """模拟源任务删除，始终禁止删除文件。"""
        assert kwargs["delete_file"] is False
        deleted.append(kwargs)
        return stage["failure"] != "delete"

    source = SimpleNamespace(name="source", instance=SimpleNamespace(delete_torrents=delete))
    target = SimpleNamespace(name="target", type="qbittorrent", instance=SimpleNamespace(
        get_torrents=query, recheck_torrents=recheck,
    ))
    plugin = SimpleNamespace(
        _event=threading.Event(), _transfer_stop_generation=0,
        _deletesource=True, _deleteduplicate=False, _seed_skipverify=False,
        _seed_autostart=True, _rename_enabled=False, _tag_enabled=False,
        save_data=lambda key, value: data.__setitem__(key, value),
        _register_seed_recheck=lambda *args: None,
    )
    monkeypatch.setattr(transfer, "is_downloader_type", lambda kind, service: service.type == kind)
    result = transfer._finish_saved_transfer(plugin, source, target, "a", "a", 0)
    assert result is (failure == "ok")
    assert data["source-a"]["delete_source"] is (failure == "ok")
    assert data["source-a"]["transfer_state"] == ("completed" if failure == "ok" else "stopped_after_add")
    if failure in {"query_error", "missing", "recheck"}:
        assert deleted == []
    stage["failure"] = "ok"
    assert transfer._finish_saved_transfer(plugin, source, target, "a", "a", 0)
    assert data["source-a"]["transfer_state"] == "completed"
