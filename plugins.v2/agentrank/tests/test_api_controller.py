"""AgentRank bearer route, participating-user, response, and error tests."""

import asyncio
import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_api_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
profile_module = importlib.import_module(f"{PACKAGE_NAME}.model.profile")
run_module = importlib.import_module(f"{PACKAGE_NAME}.model.run")
archive_module = importlib.import_module(f"{PACKAGE_NAME}.model.archive")
playback_module = importlib.import_module(f"{PACKAGE_NAME}.model.playback")
identity_module = importlib.import_module(f"{PACKAGE_NAME}.model.identity")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
controller_module = importlib.import_module(f"{PACKAGE_NAME}.controller.api")

RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
UserProfile = profile_module.UserProfile
RecommendationRun = run_module.RecommendationRun
ArchiveFeedback = archive_module.ArchiveFeedback
ArchiveEntry = archive_module.ArchiveEntry
PlaybackSnapshot = playback_module.PlaybackSnapshot
EmbyIdentity = identity_module.EmbyIdentity
AgentRankRepository = repository_module.AgentRankRepository
AgentRankApiController = controller_module.AgentRankApiController
ApiContractError = controller_module.ApiContractError
build_api_routes = controller_module.build_api_routes

HOME_PROFILE = "emby:home:user-1"
REMOTE_PROFILE = "emby:remote:user-1"
HOME_IDENTITY = {
    "server_name": "home",
    "user_id": "user-1",
    "username": "Alice",
    "profile_id": HOME_PROFILE,
    "schema_version": 1,
}
REMOTE_IDENTITY = {
    "server_name": "remote",
    "user_id": "user-1",
    "username": "Alice",
    "profile_id": REMOTE_PROFILE,
    "schema_version": 1,
}


class FakePlugin:
    """In-memory plugin with configurable runtime refresh results."""

    plugin_version = "1.0.0"

    def __init__(self):
        self.data = {}
        self._enabled = True
        self._config = {
            "enabled": True,
            "emby_identities": [HOME_IDENTITY, REMOTE_IDENTITY],
            "default_profile_id": HOME_PROFILE,
            "weights": {"rating_weight": 0.7},
            "_validation_errors": [],
        }
        self._enablement = {
            "requested": True,
            "allowed": True,
            "status": "ready",
            "message": "Playback Reporting 已就绪",
            "capabilities": {},
        }
        self._repository = AgentRankRepository(self)
        self.refresh_result = SimpleNamespace(
            status="success", message="ok", run_id="run-new", final_count=10
        )
        self._runtime = SimpleNamespace(refresh=self._refresh)

    def get_state(self):
        return self._enabled

    def get_data(self, key=None):
        return self.data.get(key)

    def save_data(self, key=None, value=None):
        self.data[key] = value

    def del_data(self, key=None):
        self.data.pop(key, None)

    async def _refresh(self, profile_id):
        if isinstance(self.refresh_result, Exception):
            raise self.refresh_result
        return self.refresh_result


def _seed(plugin):
    plugin._repository.save_profile(
        UserProfile(
            profile_id=HOME_PROFILE,
            username="Alice",
            summary="画像",
            run_id="run-old",
        )
    )
    plugin._repository.save_board(
        RecommendationBoard(
            profile_id=HOME_PROFILE,
            username="Alice",
            run_id="run-old",
            status="success",
            recommendations=[
                RecommendationItem(candidate_id="tmdb:1", rank=1, title="One")
            ],
        )
    )
    plugin._repository.append_run(
        RecommendationRun(
            profile_id=HOME_PROFILE,
            username="Alice",
            run_id="run-old",
            status="success",
        )
    )


def test_route_table_covers_frontend_contract_and_every_route_is_bearer():
    """All profile and mutation surfaces are registered as bearer-only routes."""
    routes = build_api_routes(FakePlugin())
    paths = {route["path"] for route in routes}
    assert paths == {
        "/status",
        "/overview",
        "/config/options",
        "/board",
        "/profile",
        "/refresh",
        "/playback/sync",
        "/archive",
        "/restore",
        "/archive/delete",
        "/profile/clear",
        "/profile/tags",
        "/run-history",
        "/subscribe",
    }
    assert all(route["auth"] == "bear" for route in routes)


@pytest.mark.parametrize("profile_id", ["", None])
def test_profile_endpoints_reject_missing_id_without_default_fallback(profile_id):
    """敏感读取不得用 default_profile_id 替换缺失的显式身份。"""
    controller = AgentRankApiController(FakePlugin())
    with pytest.raises(ApiContractError) as caught:
        controller.board(profile_id)
    assert caught.value.status_code == 422
    assert caught.value.code == "profile_id_required"


def test_unknown_profile_returns_stable_404_error():
    """未配置的 profile_id 不能读取其他 Emby 身份数据。"""
    controller = AgentRankApiController(FakePlugin())
    with pytest.raises(ApiContractError) as caught:
        controller.profile("emby:other:user-9")
    assert caught.value.status_code == 404
    assert caught.value.code == "unknown_profile"


def test_legacy_username_payload_is_not_accepted_as_profile_identity():
    """旧 username 请求字段不得回退或猜测为 profile_id。"""
    controller = AgentRankApiController(FakePlugin())
    with pytest.raises(ApiContractError) as caught:
        asyncio.run(controller.refresh({"username": "alice"}))
    assert caught.value.code == "profile_id_required"


def test_options_overview_board_profile_and_history_have_stable_data_shape():
    """Read APIs always return success plus a data object with explicit empties."""
    plugin = FakePlugin()
    _seed(plugin)
    controller = AgentRankApiController(plugin)

    options = controller.config_options()
    overview = controller.overview(HOME_PROFILE)
    board = controller.board(HOME_PROFILE)
    profile = controller.profile(HOME_PROFILE)
    history = controller.run_history(HOME_PROFILE)

    assert options["success"] is True
    assert options["data"]["emby_identities"] == [HOME_IDENTITY, REMOTE_IDENTITY]
    assert options["data"]["default_profile_id"] == HOME_PROFILE
    assert options["data"]["enablement"]["status"] == "ready"
    assert "users" not in options["data"]
    assert "default_user" not in options["data"]
    assert overview["data"]["profile_id"] == HOME_PROFILE
    assert overview["data"]["username"] == "Alice"
    assert overview["data"]["board"]["run_id"] == "run-old"
    assert overview["data"]["profile"]["summary"] == "画像"
    assert overview["data"]["history"][0]["run_id"] == "run-old"
    assert overview["data"]["history_total"] == 1
    assert board["data"]["recommendations"][0]["candidate_id"] == "tmdb:1"
    assert profile["data"]["summary"] == "画像"
    assert history["data"]["items"][0]["run_id"] == "run-old"


def test_config_options_merges_online_emby_identities_with_selected_offline_values():
    """配置选择器可显示在线用户，同时保留离线但已选的稳定身份。"""
    plugin = FakePlugin()

    class EmbyAccess:
        def enumerate_identities(self):
            return [EmbyIdentity("home", "user-2", "Bob")]

    plugin._emby_access = EmbyAccess()
    data = AgentRankApiController(plugin).config_options()["data"]
    profile_ids = {item["profile_id"] for item in data["emby_identities"]}
    assert profile_ids == {HOME_PROFILE, REMOTE_PROFILE, "emby:home:user-2"}
    assert data["config"]["emby_identities"] == [HOME_IDENTITY, REMOTE_IDENTITY]


def test_status_and_overview_expose_gate_reason_and_preserve_old_board():
    """依赖阻断原因可见，且只读总览仍能查看旧画像和榜单。"""
    plugin = FakePlugin()
    _seed(plugin)
    plugin._enabled = False
    plugin._enablement = {
        "requested": True,
        "allowed": False,
        "status": "not_installed",
        "message": "未安装 Playback Reporting，插件无法启用",
        "capabilities": {
            HOME_PROFILE: {
                "profile_id": HOME_PROFILE,
                "status": "not_installed",
                "message": "未安装 Playback Reporting",
                "source": "playback_reporting",
            }
        },
    }
    controller = AgentRankApiController(plugin)

    status = controller.status()
    overview = controller.overview(HOME_PROFILE)

    assert status["data"]["enabled"] is False
    assert status["data"]["state"] == "blocked"
    assert status["data"]["enablement"]["status"] == "not_installed"
    assert overview["data"]["enablement"]["message"] == plugin._enablement["message"]
    assert overview["data"]["board"]["run_id"] == "run-old"
    assert overview["data"]["profile"]["run_id"] == "run-old"

    with pytest.raises(ApiContractError) as caught:
        asyncio.run(controller.refresh({"profile_id": HOME_PROFILE}))
    assert caught.value.status_code == 409
    assert caught.value.code == "plugin_blocked"


def test_refresh_maps_running_and_downstream_failure_to_stable_contracts():
    """Refresh exposes concurrency state and maps unexpected runtime errors."""
    plugin = FakePlugin()
    controller = AgentRankApiController(plugin)
    plugin.refresh_result = SimpleNamespace(
        status="running", message="busy", run_id="", final_count=0
    )

    running = asyncio.run(controller.refresh({"profile_id": HOME_PROFILE}))
    assert running["data"]["status"] == "running"

    plugin.refresh_result = RuntimeError("boom")
    with pytest.raises(ApiContractError) as caught:
        asyncio.run(controller.refresh({"profile_id": HOME_PROFILE}))
    assert caught.value.status_code == 502
    assert caught.value.code == "refresh_failed"


def test_playback_sync_uses_profile_scope_and_returns_status():
    """手动同步只读取受控 profile_id，并返回统一播放快照契约。"""
    plugin = FakePlugin()
    calls = []

    class PlaybackService:
        def collect(self, profile_id, config):
            calls.append((profile_id, config["default_profile_id"]))
            return PlaybackSnapshot(
                profile_id, "emby_native", "medium", "ready", username="Alice"
            )

        def status(self, profile_id):
            return PlaybackSnapshot(
                profile_id, "unavailable", "low", "idle", username="Alice"
            )

    plugin._playback_service = PlaybackService()
    result = asyncio.run(
        AgentRankApiController(plugin).playback_sync({"profile_id": HOME_PROFILE})
    )
    assert result["data"]["source"] == "emby_native"
    assert calls == [(HOME_PROFILE, HOME_PROFILE)]


def test_archive_restore_delete_and_clear_are_idempotent():
    """Repeated mutation requests return changed=false instead of duplicating effects."""
    plugin = FakePlugin()
    _seed(plugin)
    controller = AgentRankApiController(plugin)

    first_archive = controller.archive({"profile_id": HOME_PROFILE, "candidate_id": "tmdb:1"})
    second_archive = controller.archive({"profile_id": HOME_PROFILE, "candidate_id": "tmdb:1"})
    first_restore = controller.restore({"profile_id": HOME_PROFILE, "candidate_id": "tmdb:1"})
    second_restore = controller.restore({"profile_id": HOME_PROFILE, "candidate_id": "tmdb:1"})
    controller.archive({"profile_id": HOME_PROFILE, "candidate_id": "tmdb:1"})
    first_delete = controller.delete_archive(
        {"profile_id": HOME_PROFILE, "candidate_id": "tmdb:1"}
    )
    second_delete = controller.delete_archive(
        {"profile_id": HOME_PROFILE, "candidate_id": "tmdb:1"}
    )
    first_clear = controller.clear_profile({"profile_id": HOME_PROFILE, "confirm": True})
    second_clear = controller.clear_profile({"profile_id": HOME_PROFILE, "confirm": True})

    assert first_archive["data"]["changed"] is True
    assert second_archive["data"]["changed"] is False
    assert first_restore["data"]["changed"] is True
    assert second_restore["data"]["changed"] is False
    assert first_delete["data"]["changed"] is True
    assert second_delete["data"]["changed"] is False
    assert first_clear["data"]["changed"] is True
    assert second_clear["data"]["changed"] is False


def test_clear_profile_requires_explicit_confirmation():
    """Destructive profile cleanup has a hard confirmation parameter gate."""
    controller = AgentRankApiController(FakePlugin())
    with pytest.raises(ApiContractError) as caught:
        controller.clear_profile({"profile_id": HOME_PROFILE, "confirm": False})
    assert caught.value.status_code == 409
    assert caught.value.code == "confirmation_required"


def test_profile_tags_are_merged_and_deleted_agent_tags_stay_suppressed():
    """人工标签独立持久化，删除 Agent 标签后画像响应不再显示它。"""
    plugin = FakePlugin()
    plugin._repository.save_profile(
        UserProfile(
            profile_id=HOME_PROFILE,
            username="Alice",
            summary="画像",
            tags=["悬疑", "科幻"],
            negative_tags=["拖沓"],
        )
    )
    controller = AgentRankApiController(plugin)

    added = controller.update_profile_tag(
        {"profile_id": HOME_PROFILE, "kind": "positive", "action": "add", "tag": "冷门佳作"}
    )
    removed = controller.update_profile_tag(
        {"profile_id": HOME_PROFILE, "kind": "positive", "action": "remove", "tag": "悬疑"}
    )
    negative = controller.update_profile_tag(
        {"profile_id": HOME_PROFILE, "kind": "negative", "action": "add", "tag": "过度煽情"}
    )

    assert added["data"]["changed"] is True
    assert removed["data"]["profile"]["tags"] == ["科幻", "冷门佳作"]
    assert negative["data"]["profile"]["negative_tags"] == ["拖沓", "过度煽情"]
    preferences = plugin._repository.load_profile_preferences(HOME_PROFILE)
    assert preferences.custom_tags == ["冷门佳作"]
    assert preferences.suppressed_tags == ["悬疑", "过度煽情"]


def test_profile_tag_rejects_invalid_kind_action_and_multiline_text():
    """人工标签 API 拒绝未知类别、动作和带换行的文本。"""
    controller = AgentRankApiController(FakePlugin())
    for payload in (
        {"profile_id": HOME_PROFILE, "kind": "other", "action": "add", "tag": "科幻"},
        {"profile_id": HOME_PROFILE, "kind": "positive", "action": "move", "tag": "科幻"},
        {"profile_id": HOME_PROFILE, "kind": "positive", "action": "add", "tag": "科幻\n悬疑"},
    ):
        with pytest.raises(ApiContractError) as caught:
            controller.update_profile_tag(payload)
        assert caught.value.code == "invalid_profile_tag"


def test_subscribe_route_is_stable_but_deferred_to_safety_task():
    """The route exists now and returns a stable unavailable error until Task 4.3."""
    controller = AgentRankApiController(FakePlugin())
    with pytest.raises(ApiContractError) as caught:
        controller.subscribe({"profile_id": HOME_PROFILE, "candidate_id": "tmdb:1"})
    assert caught.value.status_code == 409
    assert caught.value.code == "subscription_not_ready"
