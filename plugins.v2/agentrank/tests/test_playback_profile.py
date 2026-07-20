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
emby_module = importlib.import_module(f"{PACKAGE_NAME}.adapter.emby_playback")

PlaybackSample = model.PlaybackSample
PlaybackSnapshot = model.PlaybackSnapshot
PlaybackProfileService = service_module.PlaybackProfileService
PlaybackReportingAdapter = reporting_module.PlaybackReportingAdapter
within_recent_days = emby_module._within_recent_days

PROFILE_ID = "emby:home:user-1"


def _config(**overrides):
    """返回包含一个受控 Emby identity 的播放测试配置。"""
    config = {
        "emby_identities": [
            {
                "server_name": "home",
                "user_id": "user-1",
                "username": "Alice",
                "profile_id": PROFILE_ID,
                "schema_version": 1,
            }
        ],
        "default_profile_id": PROFILE_ID,
        "playback_enabled": True,
        "playback_source_mode": "auto",
    }
    config.update(overrides)
    return config


class FakeRepository:
    """提供播放快照所需的最小内存仓库。"""

    def __init__(self):
        self.snapshots = {}

    def load_playback_snapshot(self, username):
        return self.snapshots.get(username)

    def save_playback_snapshot(self, snapshot):
        self.snapshots[snapshot.profile_id] = snapshot


class FakeAdapter:
    """返回预设快照并记录传入的 Emby 用户名。"""

    def __init__(self, result):
        self.result = result
        self.usernames = []

    def collect(self, username, **kwargs):
        self.usernames.append(username)
        return PlaybackSnapshot.from_dict(self.result.to_dict())


class FakeResponse:
    """提供适配器状态分类所需的最小 HTTP 响应。"""

    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeReportingAccess:
    """按队列返回 Playback Reporting HTTP 响应。"""

    def __init__(self, responses):
        self.responses = list(responses)

    def services(self):
        return {"Emby": object()}

    def credentials(self, service):
        return "http://emby/", "secret", object()

    def resolve_user(self, instance, username):
        return "user-id"

    def request(self):
        return self

    def post_res(self, url, params=None, json=None):
        return self.responses.pop(0)

    def get_res(self, url, params=None):
        return FakeResponse(200, {"Items": []})

    def synced_item(self, server, item_id):
        return {}


def _ready(source, confidence="high"):
    return PlaybackSnapshot(
        profile_id=PROFILE_ID,
        username="Alice",
        source=source,
        confidence=confidence,
        status="ready",
        samples=[PlaybackSample("tmdb:movie:1", "One", "movie", tmdb_id="1", completed=True)],
    )


def test_auto_prefers_playback_reporting_and_uses_identity_username():
    """自动模式使用受控 identity 显示名读取 Playback Reporting。"""
    repo = FakeRepository()
    reporting = FakeAdapter(_ready("playback_reporting"))
    native = FakeAdapter(_ready("emby_native", "medium"))
    service = PlaybackProfileService(repo, reporting, native)

    result = service.collect(PROFILE_ID, _config())

    assert result.source == "playback_reporting"
    assert reporting.usernames == ["Alice"]
    assert native.usernames == []


def test_auto_falls_back_to_native_when_reporting_is_not_installed():
    """404/未安装结果自动切换 Emby 原生状态。"""
    repo = FakeRepository()
    reporting = FakeAdapter(PlaybackSnapshot("alice", "playback_reporting", "high", "not_installed"))
    native = FakeAdapter(_ready("emby_native", "medium"))
    result = PlaybackProfileService(repo, reporting, native).collect(
        PROFILE_ID, _config()
    )
    assert result.source == "emby_native"
    assert result.fallback_from == ["playback_reporting:not_installed"]


def test_auto_falls_back_to_native_when_reporting_has_no_usable_rows():
    """已安装但没有可用记录时，自动模式继续读取 Emby 原生状态。"""
    repo = FakeRepository()
    reporting = FakeAdapter(PlaybackSnapshot("alice", "playback_reporting", "high", "ready"))
    native = FakeAdapter(_ready("emby_native", "medium"))
    result = PlaybackProfileService(repo, reporting, native).collect(
        PROFILE_ID, _config()
    )
    assert result.source == "emby_native"
    assert result.fallback_from == ["playback_reporting:empty"]


def test_transient_reporting_uses_recent_snapshot_before_native():
    """Playback Reporting 暂时故障时优先保留最近成功快照。"""
    repo = FakeRepository()
    repo.save_playback_snapshot(_ready("playback_reporting"))
    reporting = FakeAdapter(PlaybackSnapshot("alice", "playback_reporting", "high", "transient_error"))
    native = FakeAdapter(_ready("emby_native", "medium"))
    result = PlaybackProfileService(repo, reporting, native).collect(
        PROFILE_ID, _config(playback_cache_days=7)
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


def test_emby_native_respects_recent_playback_window():
    """Emby 原生分支只保留回溯窗口内的最近播放时间。"""
    assert within_recent_days("2099-01-01T00:00:00Z", 180) is True
    assert within_recent_days("2000-01-01T00:00:00Z", 180) is False
    assert within_recent_days("", 180) is True


def test_reporting_permission_error_is_not_misclassified_as_missing_plugin():
    """401/403 明确返回 permission_error，而不是 not_installed。"""
    for status_code in (401, 403):
        result = PlaybackReportingAdapter(
            FakeReportingAccess([FakeResponse(status_code)])
        ).collect("alice")
        assert result.status == "permission_error"


def test_reporting_requires_both_routes_to_return_404_before_not_installed():
    """两个兼容端点均为 404 时才判定未安装。"""
    result = PlaybackReportingAdapter(
        FakeReportingAccess([FakeResponse(404), FakeResponse(404)])
    ).collect("alice")
    assert result.status == "not_installed"


def test_transient_reporting_without_cache_continues_to_native():
    """瞬时错误且没有成功快照时继续读取 Emby 原生状态。"""
    repo = FakeRepository()
    reporting = FakeAdapter(
        PlaybackSnapshot("alice", "playback_reporting", "high", "transient_error")
    )
    native = FakeAdapter(_ready("emby_native", "medium"))
    result = PlaybackProfileService(repo, reporting, native).collect(
        PROFILE_ID, _config()
    )
    assert result.source == "emby_native"
    assert result.fallback_from == ["playback_reporting:transient_error"]
