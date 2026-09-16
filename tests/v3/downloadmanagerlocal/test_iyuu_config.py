"""IYUU 缓存写回必须保留当前插件实例的业务配置。"""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import Mock

import pytest
from app.plugins.downloadmanagerlocal import DownloadManagerLocal
from app.plugins.downloadmanagerlocal.service.iyuu import update_iyuu_config


def _plugin(monkeypatch, config, *, clone=False):
    plugin_class = DownloadManagerLocal
    if clone:
        plugin_class = type("DownloadManagerLocal1", (DownloadManagerLocal,), {})
    plugin = object.__new__(plugin_class)
    plugin._iyuu_permanent_error_caches = ["permanent"]
    plugin._iyuu_error_caches = ["retry"]
    plugin._iyuu_success_caches = ["seeded"]
    reader = Mock(return_value=config)
    writer = Mock(return_value=True)
    monkeypatch.setattr(plugin, "get_config", reader)
    monkeypatch.setattr(plugin, "update_config", writer)
    return plugin, reader, writer


@pytest.mark.parametrize("clone", [False, True], ids=["source", "clone"])
def test_cache_write_preserves_current_instance_settings(monkeypatch, clone):
    """旧系统配置键为空时仍保留实例设置、未知字段和现有缓存。"""
    config = {
        "enabled": True,
        "fromdownloader": "clone-source" if clone else "source",
        "todownloader": "target",
        "iyuu_enabled": True,
        "iyuu_downloaders": ["target"],
        "speed_monitor_enabled": True,
        "upload_limit_downloader_limits_kib": {"target": 122},
        "future_setting": {"preserve": True},
        "iyuu_success_caches": ["old"],
    }
    original = deepcopy(config)
    plugin, reader, writer = _plugin(monkeypatch, config, clone=clone)

    update_iyuu_config(plugin)

    saved = writer.call_args.kwargs["config"]
    assert saved == {
        **original,
        "iyuu_permanent_error_caches": ["permanent"],
        "iyuu_error_caches": ["retry"],
        "iyuu_success_caches": ["seeded"],
    }
    reader.assert_called_once_with()
    assert config == original


@pytest.mark.parametrize("config", [None, [], "invalid"])
def test_unavailable_config_never_writes_cache_only_payload(monkeypatch, config):
    """配置读取无有效字典时拒绝覆盖，不能把未知状态当空配置。"""
    plugin, _, writer = _plugin(monkeypatch, config)

    with pytest.raises(TypeError, match="读取插件配置失败"):
        update_iyuu_config(plugin)

    writer.assert_not_called()


def test_config_read_exception_never_writes(monkeypatch):
    """读取异常沿调用链返回，原有持久化设置不受影响。"""
    plugin, reader, writer = _plugin(monkeypatch, {})
    reader.side_effect = RuntimeError("configuration read failed")

    with pytest.raises(RuntimeError, match="configuration read failed"):
        update_iyuu_config(plugin)

    writer.assert_not_called()


def test_explicit_initialization_config_is_preserved(monkeypatch):
    """初始化已传入最新配置时不重读旧快照，也不改写调用方字典。"""
    config = {"enabled": True, "iyuu_sites": [2, 7], "custom_option": "keep"}
    original = deepcopy(config)
    plugin, reader, writer = _plugin(monkeypatch, None)

    update_iyuu_config(plugin, config)

    reader.assert_not_called()
    saved = writer.call_args.kwargs["config"]
    assert all(saved[key] == value for key, value in original.items())
    assert saved["iyuu_success_caches"] == ["seeded"]
    assert config == original
