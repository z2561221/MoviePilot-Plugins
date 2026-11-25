"""通用 Pieces-hash 配置与指纹工具测试。"""

import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.plugins.downloadmanagerlocal.adapter import moviepilot as adapter
from app.plugins.downloadmanagerlocal.service import config as service_config
from app.plugins.downloadmanagerlocal.service import pieces
from app.plugins.downloadmanagerlocal.utils.config import (
    PLUGIN_CONFIG_DEFAULTS,
    normalize_pieces_site_keys,
)


def torrent_content(pieces_data=b"p" * 20):
    """生成仅用于算法测试的最小 v1 torrent 元数据。"""
    return b"d4:infod6:lengthi1e6:pieces20:" + pieces_data + b"ee"


def qb_service(*, progress=1.0, torrents=None, content=None):
    """创建不连接下载器的 qBittorrent 服务替身。"""
    instance = SimpleNamespace(
        is_inactive=Mock(return_value=False),
        get_torrents=Mock(return_value=(torrents or [{"hash": "a" * 40, "name": "已完成", "progress": progress}], False)),
        qbc=SimpleNamespace(torrents_export=Mock(return_value=content or torrent_content())),
    )
    return SimpleNamespace(type="qbittorrent", instance=instance)


def test_pieces_hash_uses_sha1_of_bencoded_v1_pieces_field():
    """只对 v1 pieces 原始字节求 SHA-1，不使用种子 info hash。"""
    raw_pieces = bytes(range(20))

    assert pieces.pieces_hash_from_torrent(torrent_content(raw_pieces)) == hashlib.sha1(raw_pieces).hexdigest()


def test_pieces_hash_roundtrips_valid_utf8_pieces_without_text_loss():
    """解码库返回可读字符串时仍按 UTF-8 还原原始 pieces 字节。"""
    raw_pieces = "é".encode() * 10

    assert pieces.pieces_hash_from_torrent(torrent_content(raw_pieces)) == hashlib.sha1(raw_pieces).hexdigest()


@pytest.mark.parametrize("content", [b"", b"<html>login</html>", b"d4:infod6:lengthi1eee"])
def test_invalid_or_v2_only_torrent_metadata_is_rejected(content):
    """无有效 v1 pieces 字段时不生成可用于查询的指纹。"""
    with pytest.raises(ValueError):
        pieces.pieces_hash_from_torrent(content)


def test_export_requires_a_completed_qb_torrent_and_uses_export_api(monkeypatch):
    """仅对已完成的准确 hash 调用 qB 导出接口。"""
    service = qb_service()
    monkeypatch.setattr(adapter, "get_downloader_service", lambda name: service)

    source, content = adapter.export_qb_completed_torrent("qB1", "A" * 40)

    assert source == {"hash": "a" * 40, "name": "已完成"}
    assert content == torrent_content()
    service.instance.qbc.torrents_export.assert_called_once_with(torrent_hash="a" * 40)


def test_incomplete_torrent_never_calls_export(monkeypatch):
    """下载未完成或状态未知时不读取 torrent 文件。"""
    service = qb_service(progress=0.99)
    monkeypatch.setattr(adapter, "get_downloader_service", lambda name: service)

    with pytest.raises(ValueError, match="已完成"):
        adapter.export_qb_completed_torrent("qB1", "a" * 40)

    service.instance.qbc.torrents_export.assert_not_called()


def test_pieces_site_keys_keep_multiline_frog_format():
    """Passkey 文本按行决定参与站点并原样保存。"""
    site_keys = "Example tracker:key-one\n青蛙:key-two:3"

    assert normalize_pieces_site_keys(site_keys) == site_keys
    assert normalize_pieces_site_keys({"8": "key-one"}) == ""


def test_pieces_configuration_uses_generic_site_and_key_defaults():
    """Passkey 文本是唯一参与站点配置字段。"""
    assert "pieces_enabled" not in PLUGIN_CONFIG_DEFAULTS
    assert "pieces_sites" not in PLUGIN_CONFIG_DEFAULTS
    assert PLUGIN_CONFIG_DEFAULTS["pieces_site_keys"] == ""


def test_runtime_pieces_config_uses_passkey_lines_and_drops_legacy_site_selection(monkeypatch):
    """运行时以 Passkey 文本配置站点，并丢弃旧选择器保存的 ID。"""
    monkeypatch.setattr(service_config, "create_downloader_helper", lambda: None)
    plugin = SimpleNamespace(
        _trim_seed_cache=Mock(),
        _custom_sites=lambda: [{"id": "custom", "name": "Example tracker"}],
    )
    site_keys = "Example tracker:test-passkey\n青蛙:another-key:3"

    normalized = service_config.initialize_runtime_config(plugin, {
        "pieces_enabled": False,
        "pieces_sites": [7, "custom", "removed", "custom"],
        "pieces_site_keys": site_keys,
    })

    assert not hasattr(plugin, "_pieces_enabled")
    assert plugin._pieces_site_keys == site_keys
    assert not hasattr(plugin, "_pieces_sites")
    assert "pieces_sites" not in normalized
    assert "pieces_enabled" not in normalized
    assert normalized["pieces_site_keys"] == site_keys


def test_frog_preview_routes_are_not_exposed():
    """只提供配置时不暴露青蛙单颗预览或 qB 种子列表接口。"""
    from app.plugins.downloadmanagerlocal.controller.api import build_api_routes

    routes = {route["path"] for route in build_api_routes(Mock())}

    assert "/pieces/sources" not in routes
    assert "/pieces/preview" not in routes
    assert "/reseed/start" not in routes
