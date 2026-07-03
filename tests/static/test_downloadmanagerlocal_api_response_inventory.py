from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO / "plugins.v2" / "downloadmanagerlocal"
HANDLERS = PLUGIN_DIR / "controller" / "handlers.py"


def _handler_source() -> str:
    """读取下载中心 API handler 源码。"""
    return HANDLERS.read_text(encoding="utf-8")


def test_downloadmanagerlocal_overview_response_inventory():
    source = _handler_source()

    assert "def api_overview(plugin):" in source
    for key in [
        '"code"',
        '"plugin"',
        '"config"',
        '"downloaders"',
        '"rename_history"',
        '"archive"',
        '"cards"',
        '"transfer"',
        '"iyuu"',
        '"rename"',
        '"seed"',
    ]:
        assert key in source


def test_downloadmanagerlocal_history_and_archive_response_inventory():
    source = _handler_source()

    assert "def api_rename_history(plugin, page: int = 1, page_size: int = 15):" in source
    for key in ['"total"', '"page"', '"page_size"', '"total_pages"', '"items"']:
        assert key in source

    assert "def api_rename_archive(plugin, page: int = 1, page_size: int = 15):" in source
    assert "plugin.list_rename_archive(page, page_size)" in source
    assert "def api_restore_rename_archive(plugin, hash: str = \"\"):" in source
    assert "plugin.restore_rename_archive(hash)" in source
    assert "def api_delete_rename_archive(plugin, hash: str = \"\"):" in source
    assert "plugin.delete_rename_archive(hash)" in source


def test_downloadmanagerlocal_retry_and_delete_response_inventory():
    source = _handler_source()

    assert "def api_retry_renames(plugin):" in source
    for key in ['"code"', '"msg"', '"history"', '"dirty"', '"total"']:
        assert key in source
    assert "plugin._retry_pending_renames()" in source

    assert "def api_retry_rename(plugin, hash: str = \"\"):" in source
    assert "plugin._retry_rename(hash)" in source
    assert "def api_delete_rename_history(plugin, hash: str = \"\"):" in source
    assert '"已删除"' in source
    assert '"记录不存在"' in source


def test_downloadmanagerlocal_diagnostics_and_recovery_response_inventory():
    source = _handler_source()

    assert "def api_diagnostics(plugin):" in source
    assert "plugin._diagnostics()" in source
    assert '"诊断失败: {e}"' in source

    assert "def api_recovery_torrent(plugin, hash: str = \"\"):" in source
    for message in ['"缺少 hash 参数"', '"未找到成功的重命名记录"', '"原始名称为空"']:
        assert message in source
