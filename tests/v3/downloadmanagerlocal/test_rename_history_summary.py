"""命名记录变动与统计缓存隔离。"""


def test_rename_summary_reuses_counts_and_observes_changes(monkeypatch):
    from types import SimpleNamespace
    from app.plugins.downloadmanagerlocal.service import diagnostics

    records = {"row": {"original_name": "A", "success": False, "reason": "before"}}
    reads = []
    monkeypatch.setattr(diagnostics, "is_dirty_renamed_torrent_name", lambda value: reads.append(value) or False)
    plugin = SimpleNamespace(get_data=lambda key: records)
    summary = diagnostics._rename_history_stats(plugin)
    summary["recent_failures"].clear()
    assert diagnostics._rename_history_stats(plugin)["recent_failures"][0]["reason"] == "before"
    assert len(reads) == 2
    records["row"]["success"] = True
    assert diagnostics._rename_history_stats(plugin)["success"] == 1
    records.clear()
    assert diagnostics._rename_history_stats(plugin)["total"] == 0
