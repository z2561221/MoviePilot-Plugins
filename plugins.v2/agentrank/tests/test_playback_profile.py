"""AgentRank 播放数据源优先级与快照回退测试。"""

import importlib
import sys
from pathlib import Path
from types import ModuleType


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_playback_test"
package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

model = importlib.import_module(f"{PACKAGE_NAME}.model.playback")
service_module = importlib.import_module(f"{PACKAGE_NAME}.service.playback_profile")
reporting_module = importlib.import_module(f"{PACKAGE_NAME}.adapter.playback_reporting")

PlaybackSample = model.PlaybackSample
PlaybackSnapshot = model.PlaybackSnapshot
PlaybackProfileService = service_module.PlaybackProfileService
PlaybackReportingAdapter = reporting_module.PlaybackReportingAdapter


class FakeRepository:
    """提供播放快照所需的最小内存仓库。"""

    def __init__(self):
        self.snapshots = {}

    def load_playback_snapshot(self, username):
        return self.snapshots.get(username)

    def save_playback_snapshot(self, snapshot):
        self.snapshots[snapshot.username] = snapshot


class FakeAdapter:
    """返回预设快照并记录传入的 Emby 用户名。"""

    def __init__(self, result):
        self.result = result
        self.usernames = []

    def collect(self, username, **kwargs):
        self.usernames.append(username)
        return PlaybackSnapshot.from_dict(self.result.to_dict())


def _ready(source, confidence="high"):
    return PlaybackSnapshot(
        username="alice",
        source=source,
        confidence=confidence,
        status="ready",
        samples=[PlaybackSample("tmdb:movie:1", "One", "movie", tmdb_id="1", completed=True)],
    )


def test_auto_prefers_playback_reporting_and_applies_user_mapping():
    """自动模式优先使用高置信 Playback Reporting。"""
    repo = FakeRepository()
    reporting = FakeAdapter(_ready("playback_reporting"))
    native = FakeAdapter(_ready("emby_native", "medium"))
    service = PlaybackProfileService(repo, reporting, native)

    result = service.collect(
        "alice",
        {
            "playback_enabled": True,
            "playback_source_mode": "auto",
            "playback_user_map": {"alice": "emby-alice"},
        },
    )

    assert result.source == "playback_reporting"
    assert reporting.usernames == ["emby-alice"]
    assert native.usernames == []


def test_auto_falls_back_to_native_when_reporting_is_not_installed():
    """404/未安装结果自动切换 Emby 原生状态。"""
    repo = FakeRepository()
    reporting = FakeAdapter(PlaybackSnapshot("alice", "playback_reporting", "high", "not_installed"))
    native = FakeAdapter(_ready("emby_native", "medium"))
    result = PlaybackProfileService(repo, reporting, native).collect(
        "alice", {"playback_enabled": True, "playback_source_mode": "auto"}
    )
    assert result.source == "emby_native"
    assert result.fallback_from == ["playback_reporting:not_installed"]


def test_transient_reporting_uses_recent_snapshot_before_native():
    """Playback Reporting 暂时故障时优先保留最近成功快照。"""
    repo = FakeRepository()
    repo.save_playback_snapshot(_ready("playback_reporting"))
    reporting = FakeAdapter(PlaybackSnapshot("alice", "playback_reporting", "high", "transient_error"))
    native = FakeAdapter(_ready("emby_native", "medium"))
    result = PlaybackProfileService(repo, reporting, native).collect(
        "alice", {"playback_enabled": True, "playback_source_mode": "auto", "playback_cache_days": 7}
    )
    assert result.status == "cached"
    assert result.source == "playback_reporting"
    assert native.usernames == []


def test_reporting_query_is_read_only_and_excludes_device_fields():
    """固定 SQL 只查询播放聚合字段，不把客户端和设备送入插件。"""
    query = PlaybackReportingAdapter._query(180)
    assert query.startswith("SELECT")
    assert "FROM PlaybackActivity" in query
    assert "SUM(PlayDuration)" in query
    assert "LIMIT 500" in query
    assert "DELETE" not in query.upper()
    assert "ClientName" not in query and "DeviceName" not in query


def test_playback_adapters_use_mp_synced_item_identity_before_agent_context():
    """适配器源码明确通过 MP 媒体库同步身份完成 ItemId 到 TMDB 的映射。"""
    emby_source = Path(PLUGIN_DIR / "adapter/emby_playback.py").read_text(encoding="utf-8")
    reporting_source = Path(PLUGIN_DIR / "adapter/playback_reporting.py").read_text(encoding="utf-8")
    assert "synced_item" in emby_source
    assert "synced_item" in reporting_source
    assert "MediaServerItem.get_by_server_itemid" in emby_source
