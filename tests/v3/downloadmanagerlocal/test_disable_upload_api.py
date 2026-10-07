"""限速停用必须确认持久化，不能只修改进程内开关。"""

from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.controller import handlers


@pytest.mark.parametrize("failure", ["read", "save", None])
def test_disable_requires_persisted_configuration(monkeypatch, failure):
    """读取或保存失败不得停止 worker，成功时重载读取的开关也应关闭。"""
    stored = {"upload_limit_enabled": True, "other": "keep"}
    effects = []

    def save(config):
        """仅在存储确认成功后替换配置。"""
        if failure == "save":
            return False
        stored.update(config)
        return True

    plugin = SimpleNamespace(_upload_limit_enabled=True,
        get_config=lambda: None if failure == "read" else dict(stored), update_config=save)
    monkeypatch.setattr(handlers, "stop_upload_limit_worker", lambda p: effects.append("stop"))
    monkeypatch.setattr(handlers, "restore_upload_limits", lambda p: (
        effects.append("restore") or {"code": 0, "msg": "restored", "errors": [], "downloaders": []}))
    result = handlers.api_upload_limit_disable_restore(plugin)
    assert result.success is (failure is None)
    assert plugin._upload_limit_enabled is (failure is not None)
    assert stored["upload_limit_enabled"] is (failure is not None)
    assert stored["other"] == "keep"
    assert effects == ([] if failure else ["stop", "restore"])
