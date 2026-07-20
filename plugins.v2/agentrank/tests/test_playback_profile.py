"""AgentRank Playback Reporting 身份作用域与快照回退测试。"""

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_playback_test"
package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

identity_module = importlib.import_module(f"{PACKAGE_NAME}.model.identity")
model = importlib.import_module(f"{PACKAGE_NAME}.model.playback")
service_module = importlib.import_module(f"{PACKAGE_NAME}.service.playback_profile")
reporting_module = importlib.import_module(f"{PACKAGE_NAME}.adapter.playback_reporting")

EmbyIdentity = identity_module.EmbyIdentity
PlaybackCapability = model.PlaybackCapability
PlaybackSample = model.PlaybackSample
PlaybackSnapshot = model.PlaybackSnapshot
PlaybackProfileService = service_module.PlaybackProfileService
PlaybackReportingAdapter = reporting_module.PlaybackReportingAdapter

IDENTITY = EmbyIdentity("home", "user-1", "Alice")
PROFILE_ID = IDENTITY.profile_id


def _config(**overrides):
    """返回包含一个受控 Emby identity 的播放测试配置。"""
    config = {
        "emby_identities": [IDENTITY.to_dict()],
        "default_profile_id": PROFILE_ID,
        "playback_enabled": True,
    }
    config.update(overrides)
    return config


class FakeRepository:
    """提供播放快照所需的最小内存仓库。"""

    def __init__(self):
        self.snapshots = {}

    def load_playback_snapshot(self, profile_id):
        return self.snapshots.get(profile_id)

    def save_playback_snapshot(self, snapshot):
        self.snapshots[snapshot.profile_id] = snapshot


class FakeAdapter:
    """返回预设快照并记录传入的稳定 Emby identity。"""

    def __init__(self, result, capability=None):
        self.result = result
        self.capability = capability
        self.identities = []
        self.probe_identities = []

    def collect(self, identity, **kwargs):
        self.identities.append(identity)
        return PlaybackSnapshot.from_dict(self.result.to_dict())

    def probe(self, identity):
        self.probe_identities.append(identity)
        return PlaybackCapability.from_dict(self.capability.to_dict())


class FakeResponse:
    """提供适配器状态分类所需的最小 HTTP 响应。"""

    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeReportingAccess:
    """按队列返回指定 identity 的 Playback Reporting HTTP 响应。"""

    def __init__(self, responses, details=None, credentials=None):
        self.responses = list(responses)
        self.details = list(details or [])
        self.connection = credentials or ("http://emby/", "secret", object())
        self.post_calls = []

    def resolve_service(self, server_name):
        return ("home", object()) if server_name == "home" else ("", None)

    def credentials(self, service):
        return self.connection

    def request(self):
        return self

    def post_res(self, url, params=None, json=None):
        self.post_calls.append((url, dict(params or {}), dict(json or {})))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def get_res(self, url, params=None):
        if self.details:
            return FakeResponse(200, {"Items": self.details})
        return FakeResponse(200, {"Items": []})

    def synced_item(self, server, item_id):
        return {}


def _ready():
    return PlaybackSnapshot(
        profile_id=PROFILE_ID,
        username="Alice",
        source="playback_reporting",
        confidence="high",
        status="ready",
        samples=[
            PlaybackSample(
                "tmdb:movie:1", "One", "movie", tmdb_id="1", completed=True
            )
        ],
    )


def test_profile_service_passes_the_exact_configured_identity():
    """播放服务按 profile_id 传递完整 identity，不再按显示名猜用户。"""
    repo = FakeRepository()
    reporting = FakeAdapter(_ready())
    service = PlaybackProfileService(repo, reporting)

    result = service.collect(PROFILE_ID, _config())

    assert result.source == "playback_reporting"
    assert reporting.identities == [IDENTITY]
    assert result.profile_id == PROFILE_ID
    assert result.username == "Alice"


@pytest.mark.parametrize(
    "status",
    [
        "ready",
        "not_installed",
        "permission_error",
        "transient_error",
        "emby_unavailable",
    ],
)
def test_profile_service_preserves_every_probe_status_for_exact_identity(status):
    """画像服务按精确 identity 原样返回全部五类能力状态。"""
    capability = PlaybackCapability(PROFILE_ID, status, "探测结果")
    reporting = FakeAdapter(_ready(), capability=capability)

    result = PlaybackProfileService(FakeRepository(), reporting).probe(
        PROFILE_ID, _config()
    )

    assert result.status == status
    assert result.profile_id == PROFILE_ID
    assert reporting.probe_identities == [IDENTITY]


def test_not_installed_result_is_preserved_without_native_userdata_fallback():
    """未安装结果直接保留，不再读取 Emby 原生 UserData。"""
    repo = FakeRepository()
    reporting = FakeAdapter(
        PlaybackSnapshot(PROFILE_ID, "playback_reporting", "high", "not_installed")
    )

    result = PlaybackProfileService(repo, reporting).collect(PROFILE_ID, _config())

    assert result.status == "not_installed"
    assert result.source == "playback_reporting"
    assert repo.load_playback_snapshot(PROFILE_ID).status == "not_installed"


def test_ready_empty_result_remains_playback_reporting_evidence():
    """已安装但无记录时保留空快照，由编排器执行样本门槛。"""
    repo = FakeRepository()
    reporting = FakeAdapter(
        PlaybackSnapshot(PROFILE_ID, "playback_reporting", "high", "ready")
    )

    result = PlaybackProfileService(repo, reporting).collect(PROFILE_ID, _config())

    assert result.status == "ready"
    assert result.sample_count == 0
    assert result.source == "playback_reporting"


def test_transient_reporting_uses_recent_success_snapshot():
    """Playback Reporting 暂时故障时保留最近成功快照。"""
    repo = FakeRepository()
    repo.save_playback_snapshot(_ready())
    reporting = FakeAdapter(
        PlaybackSnapshot(PROFILE_ID, "playback_reporting", "high", "transient_error")
    )

    result = PlaybackProfileService(repo, reporting).collect(
        PROFILE_ID, _config(playback_cache_days=7)
    )

    assert result.status == "cached"
    assert result.source == "playback_reporting"


def test_reporting_query_is_read_only_and_excludes_device_fields():
    """固定 SQL 只查询播放聚合字段，不把客户端和设备送入插件。"""
    query = PlaybackReportingAdapter._query(180)
    assert query.startswith("SELECT")
    assert "FROM PlaybackActivity" in query
    assert "SUM(PlayDuration)" in query
    assert "LIMIT 500" in query
    assert "DELETE" not in query.upper()
    assert "ClientName" not in query and "DeviceName" not in query


def test_reporting_probe_query_is_minimal_and_read_only():
    """能力探测只验证 PlaybackActivity 可读性，不读取播放明细。"""
    query = PlaybackReportingAdapter._probe_query()
    assert query.startswith("SELECT COUNT(1)")
    assert "FROM PlaybackActivity" in query
    assert "DELETE" not in query.upper()
    assert "UserId" not in query and "ItemId" not in query


@pytest.mark.parametrize(
    ("responses", "expected_status"),
    [
        ([FakeResponse(200, {})], "ready"),
        ([FakeResponse(404), FakeResponse(404)], "not_installed"),
        ([FakeResponse(401)], "permission_error"),
        ([FakeResponse(403)], "permission_error"),
        ([FakeResponse(500)], "transient_error"),
        ([FakeResponse(404), FakeResponse(503)], "transient_error"),
        ([None], "transient_error"),
        ([TimeoutError("timeout")], "transient_error"),
    ],
)
def test_reporting_probe_classifies_http_and_transport_states(
    responses, expected_status
):
    """探测必须区分可用、双 404、权限失败与所有瞬时故障。"""
    access = FakeReportingAccess(responses)

    capability = PlaybackReportingAdapter(access).probe(IDENTITY)

    assert capability.status == expected_status
    assert capability.ready is (expected_status == "ready")
    assert capability.profile_id == PROFILE_ID
    assert "secret" not in capability.to_dict().values()
    if expected_status == "not_installed":
        assert [call[0] for call in access.post_calls] == [
            "http://emby/user_usage_stats/submit_custom_query",
            "http://emby/emby/user_usage_stats/submit_custom_query",
        ]


def test_reporting_probe_classifies_missing_emby_and_credentials():
    """服务离线或连接信息缺失都属于 Emby 不可用，而非插件未安装。"""
    offline_access = FakeReportingAccess([])
    missing_credentials = FakeReportingAccess(
        [], credentials=("", "", object())
    )

    offline = PlaybackReportingAdapter(offline_access).probe(
        EmbyIdentity("offline", "user-1", "Alice")
    )
    unavailable = PlaybackReportingAdapter(missing_credentials).probe(IDENTITY)

    assert offline.status == "emby_unavailable"
    assert unavailable.status == "emby_unavailable"
    assert offline_access.post_calls == []
    assert missing_credentials.post_calls == []


def test_playback_capability_round_trip_rejects_unknown_status():
    """能力状态可安全往返，且未知分类不能进入后续门禁。"""
    capability = PlaybackCapability(PROFILE_ID, "ready", "可访问")

    restored = PlaybackCapability.from_dict(capability.to_dict())

    assert restored.to_dict() == capability.to_dict()
    assert "username" not in restored.to_dict()
    with pytest.raises(ValueError, match="unknown playback capability status"):
        PlaybackCapability(PROFILE_ID, "unknown")


def test_reporting_uses_shared_emby_synced_item_identity():
    """Playback Reporting 通过共享访问器映射 ItemId 到 TMDB。"""
    emby_source = Path(PLUGIN_DIR / "adapter/emby.py").read_text(encoding="utf-8")
    reporting_source = Path(
        PLUGIN_DIR / "adapter/playback_reporting.py"
    ).read_text(encoding="utf-8")
    assert "synced_item" in emby_source
    assert "synced_item" in reporting_source
    assert "MediaServerItem.get_by_server_itemid" in emby_source


def test_reporting_permission_error_is_not_misclassified_as_missing_plugin():
    """401/403 明确返回 permission_error，而不是 not_installed。"""
    for status_code in (401, 403):
        result = PlaybackReportingAdapter(
            FakeReportingAccess([FakeResponse(status_code)])
        ).collect(IDENTITY)
        assert result.status == "permission_error"
        assert result.profile_id == PROFILE_ID


def test_reporting_requires_both_routes_to_return_404_before_not_installed():
    """两个兼容端点均为 404 时才判定未安装。"""
    result = PlaybackReportingAdapter(
        FakeReportingAccess([FakeResponse(404), FakeResponse(404)])
    ).collect(IDENTITY)
    assert result.status == "not_installed"


def test_reporting_ready_snapshot_keeps_identity_and_matches_stable_user_id():
    """成功采样按稳定 UserId 命中，并保留原始 profile_id 与显示名。"""
    payload = {
        "columns": [
            "UserId",
            "UserName",
            "ItemId",
            "ItemType",
            "ItemName",
            "PlayCount",
            "WatchSeconds",
            "LastPlayedAt",
        ],
        "results": [
            [
                "user-1",
                "Renamed Alice",
                "item-1",
                "Movie",
                "One",
                1,
                6000,
                "2026-07-20T00:00:00Z",
            ]
        ],
    }
    access = FakeReportingAccess(
        [FakeResponse(200, payload)],
        details=[
            {
                "Id": "item-1",
                "Name": "One",
                "ProviderIds": {"Tmdb": "1"},
                "RunTimeTicks": 6_000 * 10_000_000,
            }
        ],
    )

    result = PlaybackReportingAdapter(access).collect(IDENTITY)

    assert result.status == "ready"
    assert result.profile_id == PROFILE_ID
    assert result.username == "Alice"
    assert result.samples[0].stable_id == "tmdb:movie:1"
    assert result.samples[0].completed is True


def test_transient_reporting_without_cache_stays_transient():
    """瞬时错误且没有成功快照时不得降级到原生 UserData。"""
    repo = FakeRepository()
    reporting = FakeAdapter(
        PlaybackSnapshot(PROFILE_ID, "playback_reporting", "high", "transient_error")
    )

    result = PlaybackProfileService(repo, reporting).collect(PROFILE_ID, _config())

    assert result.status == "transient_error"
    assert result.source == "playback_reporting"
