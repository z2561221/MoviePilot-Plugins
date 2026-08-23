"""验证下载中心总览累计计数。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.plugins.downloadmanagerlocal.controller import handlers
from app.plugins.downloadmanagerlocal.model.state import load_transfer_stats
from app.plugins.downloadmanagerlocal.service import transfer as transfer_service


class FakePlugin:
    """提供总览和转种测试所需的最小插件行为。"""

    def __init__(self, data: dict | None = None) -> None:
        """初始化内存持久化数据与总览状态。"""
        self.data = dict(data or {})
        self._transfer_enabled = True
        self._transfer_active = True
        self._transfer_fallback_enabled = True
        self._iyuu_enabled = True
        self._iyuu_success = 0
        self._iyuu_fail = 0
        self._iyuu_cached = 0
        self._iyuu_success_caches = ["seed-a", "SEED-A", "seed-b"]
        self._iyuu_error_caches = ["seed-c", "seed-d"]
        self._iyuu_permanent_error_caches = ["SEED-D", "seed-e"]
        self._rename_enabled = True
        self._seed_autostart = True
        self._seed_skipverify = False
        self._upload_limit_enabled = False

    def get_data(self, key: str):
        """读取内存持久化数据。"""
        return self.data.get(key)

    def save_data(self, key: str, value) -> None:
        """写入内存持久化数据。"""
        self.data[key] = value

    @staticmethod
    def _diagnostics() -> dict:
        """返回空诊断摘要。"""
        return {"rename_history": {}}

    @staticmethod
    def rename_archive_stats() -> dict:
        """返回空归档统计。"""
        return {}


def test_overview_uses_persisted_transfer_and_iyuu_cache_totals(monkeypatch) -> None:
    """总览必须返回累计转种统计与去重后的 IYUU 缓存数量。"""
    plugin = FakePlugin({
        "transfer_stats": {
            "schema_version": 1,
            "success_total": 12,
            "fallback_success": 4,
        }
    })
    monkeypatch.setattr(handlers, "get_upload_limit_status", lambda _plugin: {})
    monkeypatch.setattr(handlers, "_speed_monitor_overview", lambda _plugin: {})

    result = handlers.api_overview(plugin)

    assert result.cards["transfer"]["success_total"] == 12
    assert result.cards["transfer"]["fallback_success"] == 4
    assert result.cards["iyuu"]["success_total"] == 2
    assert result.cards["iyuu"]["fail_total"] == 3
    assert result.cards["iyuu"]["success"] == 0
    assert result.cards["iyuu"]["fail"] == 0


def test_transfer_successes_persist_total_and_fallback_subset(monkeypatch, tmp_path: Path) -> None:
    """成功转种必须累计总数，并只把兜底扫描计入兜底子集。"""
    source_hash = "source-hash"
    (tmp_path / f"{source_hash}.torrent").write_bytes(b"torrent")

    class SourceDownloader:
        """返回一个已完成任务的源下载器替身。"""

        @staticmethod
        def get_completed_torrents() -> list[dict]:
            """返回单个已完成任务。"""
            return [{"hash": source_hash}]

    class TargetDownloader:
        """模拟尚未存在目标任务的下载器替身。"""

        @staticmethod
        def get_torrents(ids=None):
            """返回空目标查询结果。"""
            return [], None

    plugin = FakePlugin()
    source_service = SimpleNamespace(name="源下载器", type="transmission", instance=SourceDownloader())
    target_service = SimpleNamespace(name="目标下载器", type="transmission", instance=TargetDownloader())
    plugin._fromdownloader = "source"
    plugin._todownloader = "target"
    plugin._fromtorrentpath = str(tmp_path)
    plugin._event = SimpleNamespace(is_set=lambda: False)
    plugin._delay_minutes = 25
    plugin._nopaths = ""
    plugin._includecategory = ""
    plugin._transferemptylabel = True
    plugin._nolabels = ""
    plugin._includelabels = ""
    plugin._deleteduplicate = False
    plugin._frompath = "/downloads"
    plugin._topath = "/downloads"
    plugin._deletesource = False
    plugin._notify = False
    plugin.service_info = lambda downloader_id: source_service if downloader_id == "source" else target_service
    plugin.get_hash = lambda torrent, _type: torrent["hash"]
    plugin.get_save_path = lambda _torrent, _type: "/downloads/example"
    plugin.get_label = lambda _torrent, _type: []
    plugin.get_category = lambda _torrent, _type: ""
    plugin.convert_save_path = lambda path, _source, _target: path
    plugin._register_seed_recheck = lambda *_args: None
    plugin._retry_failed_renames = lambda _service: None

    monkeypatch.setattr(transfer_service, "validate_config", lambda _plugin: True)
    monkeypatch.setattr(transfer_service, "download_torrent", lambda *_args, **_kwargs: "target-hash")
    monkeypatch.setattr(transfer_service, "post_transfer_process", lambda *_args: None)
    monkeypatch.setattr(transfer_service, "is_downloader_type", lambda *_args, **_kwargs: False)

    transfer_service.transfer(plugin, trigger_source="事件驱动")
    transfer_service.transfer(plugin, trigger_source="兜底扫描")

    assert load_transfer_stats(plugin) == {
        "schema_version": 1,
        "success_total": 2,
        "fallback_success": 1,
    }


def test_page_uses_cumulative_counter_copy() -> None:
    """详情页必须展示累计转种与持久化 IYUU 计数。"""
    page_source = (
        Path(__file__).resolve().parents[3]
        / "plugins.v3/downloadmanagerlocal/frontend/src/components/Page.vue"
    ).read_text(encoding="utf-8")

    assert "累计成功 ${cards.transfer?.success_total || 0} · 其中兜底 ${cards.transfer?.fallback_success || 0}" in page_source
    assert "已铺种 ${cards.iyuu?.success_total || 0} · 失败 ${cards.iyuu?.fail_total || 0}" in page_source
    assert "兜底服务已启用" not in page_source
