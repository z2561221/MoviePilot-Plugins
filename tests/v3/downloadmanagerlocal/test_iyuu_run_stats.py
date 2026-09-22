"""验证 IYUU 预检提前返回时不会重复结算上一轮计数。"""

from __future__ import annotations

from types import SimpleNamespace

from app.plugins.downloadmanagerlocal.service import iyuu


def test_skipped_iyuu_runs_do_not_flush_previous_round_counts(monkeypatch):
    """没有可用 IYUU 服务时，连续调度不应重复写入旧的成功失败数。"""
    plugin = SimpleNamespace(
        iyuu_helper=None,
        _iyuu_success=3,
        _iyuu_fail=2,
    )
    recorded = []
    monkeypatch.setattr(iyuu, "iyuu_service_infos", lambda _plugin: None)
    monkeypatch.setattr(
        iyuu,
        "record_iyuu_results",
        lambda _plugin, **counts: recorded.append(counts),
    )

    iyuu.iyuu_auto_seed(plugin)
    iyuu.iyuu_auto_seed(plugin)

    assert recorded == []
