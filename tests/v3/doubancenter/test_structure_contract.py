"""结构重构保留新旧入口行为、运行状态隔离和领域依赖方向。"""

import ast
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter import DoubanCenter
from app.plugins.doubancenter.model.runtime import RuntimeState
from app.plugins.doubancenter.service import lifecycle, rank_candidates, wish_sync


def test_runtime_state_is_owned_by_each_real_plugin_instance():
    first, second = object.__new__(DoubanCenter), object.__new__(DoubanCenter)
    assert isinstance(first.runtime_state, RuntimeState)
    assert first._rank_lock is not second._rank_lock
    assert first._sync_lock is not second._sync_lock
    assert first._folio_poster_lock is not second._folio_poster_lock
    first._folio_series_cache["one"] = (1, {})
    first._wish_notification_last_times["one"] = 1
    assert second._folio_series_cache == {}
    assert second._wish_notification_last_times == {}
    lifecycle.start(first)
    old = first._run_stop
    lifecycle.start(first)
    assert old.is_set() and not first._run_stop.is_set()
    assert first.runtime_state.stop_event is first._run_stop
    assert first.runtime_state.series_cache == {}
    with pytest.raises(lifecycle.RunStopped), lifecycle.scope(first, old):
        lifecycle.checkpoint(first)


@pytest.mark.parametrize("coming", [False, True])
@pytest.mark.parametrize("mode", ["success", "blacklist", "existing", "unknown", "observe", "subscribe_failed"])
def test_legacy_rss_and_snapshot_have_equivalent_policy_and_records(monkeypatch, coming, mode):
    """共同的门禁次序和副作用保持一致，旧入口仍在黑名单之后识别。"""
    raw = {"title": "Series Season 2", "year": "2026", "season": 2, "link": "https://example.invalid/one", "wish_count": 100}
    rank = {"key": "coming" if coming else "tv_global", "name": "Rank", "coming": coming}
    media = SimpleNamespace(title="Series", tmdb_id=123, type="电视剧", vote_average=8, get_poster_image=lambda: "poster")
    monkeypatch.setattr(rank_candidates, "datetime", SimpleNamespace(datetime=SimpleNamespace(now=lambda: datetime(2026, 11, 15, 12, tzinfo=timezone.utc))))
    monkeypatch.setattr(rank_candidates.rank_timing, "resolve_release", lambda *args, **kwargs: ("2026", "2026-11-15"))
    monkeypatch.setattr(rank_candidates.utils, "get_tmdb_air_date", lambda *args, **kwargs: "2026-11-15")
    monkeypatch.setattr(rank_candidates.rank_notifications, "send_pending", lambda *args: None)
    monkeypatch.setattr(rank_candidates.rank_notifications, "enrich_observation", lambda *args, **kwargs: None)
    monkeypatch.setattr(rank_candidates, "_cleanup_observe_logs", lambda *args, **kwargs: None)
    traces = []

    def execute(legacy):
        trace, data = [], {}
        plugin = SimpleNamespace(_rank_configs={}, _blacklist_keywords="", _observe_days=0, _custom_ranks=[],
                                 get_data=lambda key: deepcopy(data.get(key)), save_data=lambda key, value: data.__setitem__(key, deepcopy(value)))
        lifecycle.start(plugin)
        meta = rank_candidates._snapshot_meta(raw, {}, rank_candidates.MediaType.TV)
        plugin.chain = SimpleNamespace(recognize_media=lambda **kwargs: trace.append("recognize") or media)
        monkeypatch.setattr(rank_candidates, "_fetch_coming_rss", lambda *args: [deepcopy(raw)])
        monkeypatch.setattr(rank_candidates, "_fetch_rss", lambda *args: [deepcopy(raw)])
        monkeypatch.setattr(rank_candidates, "_recognize_rss_item", lambda *args: trace.append("recognize") or (meta, media, "tv"))
        monkeypatch.setattr(rank_candidates, "_check_blacklist", lambda *args, **kwargs: trace.append("blacklist") or mode == "blacklist")
        monkeypatch.setattr(rank_candidates, "_check_rank_region", lambda *args, **kwargs: trace.append("region") or True)
        monkeypatch.setattr(rank_candidates, "_is_existing_media", lambda *args: trace.append("existing") or (None if mode == "unknown" else mode == "existing"))
        monkeypatch.setattr(rank_candidates, "_check_observe", lambda *args, **kwargs: trace.append("observe") or mode == "observe")
        monkeypatch.setattr(rank_candidates, "_add_sub", lambda *args, **kwargs: trace.append(("subscribe", args[2].begin_season, kwargs)) or mode != "subscribe_failed")
        if legacy:
            processor = rank_candidates._process_coming if coming else rank_candidates._process_general
            processor(plugin, "https://example.invalid/rss", rank)
        else:
            processor = rank_candidates._process_coming_snapshots if coming else rank_candidates._process_general_snapshots
            processor(plugin, [{"raw": deepcopy(raw), "entry": {}, "mediainfo": media}], rank)
        traces.append(trace)
        return data

    assert execute(True) == execute(False)
    assert [entry for entry in traces[0] if entry != "recognize"] == traces[1]
    if mode == "blacklist":
        assert "recognize" not in traces[0]


def test_domain_services_do_not_import_or_call_back_to_pipeline():
    root = Path(__file__).resolve().parents[3] / "plugins.v3/doubancenter"
    for name in ("rank_media.py", "rank_candidates.py", "rank_recognition.py", "wish_sync.py"):
        tree = ast.parse((root / "service" / name).read_text(encoding="utf-8"))
        modules = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert not any(module.endswith(("rank_pipeline", "folio")) for module in modules)
    assert not hasattr(wish_sync, "sync_log_handler")
