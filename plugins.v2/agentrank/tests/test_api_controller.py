"""AgentRank bearer route, participating-user, response, and error tests."""

import asyncio
import importlib
import inspect
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_api_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

fastapi_module = sys.modules.setdefault("fastapi", ModuleType("fastapi"))
fastapi_params_module = sys.modules.setdefault(
    "fastapi.params", ModuleType("fastapi.params")
)


class DependsParam:
    """测试使用的最小 FastAPI 依赖描述。"""

    def __init__(self, dependency=None):
        self.dependency = dependency


class HTTPException(Exception):
    """测试使用的最小 FastAPI HTTP 异常。"""

    def __init__(self, status_code, detail=None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


def Depends(dependency=None):
    """构造测试依赖描述。"""
    return DependsParam(dependency)


fastapi_module.Depends = Depends
fastapi_module.HTTPException = HTTPException
fastapi_params_module.Depends = DependsParam

app_module = sys.modules.setdefault("app", ModuleType("app"))
schemas_module = sys.modules.setdefault("app.schemas", ModuleType("app.schemas"))
core_module = sys.modules.setdefault("app.core", ModuleType("app.core"))
security_module = sys.modules.setdefault(
    "app.core.security", ModuleType("app.core.security")
)


class TokenPayload:
    """测试使用的最小 MoviePilot 登录载荷。"""

    def __init__(self, sub=None, username=None, super_user=False):
        self.sub = sub
        self.username = username
        self.super_user = super_user


def verify_token():
    """为 FastAPI endpoint 签名提供测试鉴权依赖。"""
    return TokenPayload(sub=1, username="admin", super_user=True)


app_module.schemas = schemas_module
app_module.core = core_module
core_module.security = security_module
schemas_module.TokenPayload = TokenPayload
security_module.verify_token = verify_token

board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
profile_module = importlib.import_module(f"{PACKAGE_NAME}.model.profile")
preferences_module = importlib.import_module(f"{PACKAGE_NAME}.model.profile_preferences")
run_module = importlib.import_module(f"{PACKAGE_NAME}.model.run")
archive_module = importlib.import_module(f"{PACKAGE_NAME}.model.archive")
playback_module = importlib.import_module(f"{PACKAGE_NAME}.model.playback")
identity_module = importlib.import_module(f"{PACKAGE_NAME}.model.identity")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
controller_module = importlib.import_module(f"{PACKAGE_NAME}.controller.api")

RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
UserProfile = profile_module.UserProfile
ProfilePreferences = preferences_module.ProfilePreferences
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
            "profile_access_map": {"7": [HOME_PROFILE]},
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
            status="success", message="ok", run_id="run-new", final_count=5
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
    for route in routes:
        token_parameters = [
            parameter
            for parameter in inspect.signature(route["endpoint"]).parameters.values()
            if isinstance(parameter.default, DependsParam)
        ]
        assert len(token_parameters) == 1
        assert token_parameters[0].default.dependency is verify_token


def test_superuser_can_access_every_configured_profile_and_full_options():
    """超级用户可读取全部已配置画像身份与完整配置选项。"""
    plugin = FakePlugin()
    _seed(plugin)
    controller = AgentRankApiController(plugin)
    token = TokenPayload(sub=1, username="admin", super_user=True)

    assert controller.endpoint_overview(HOME_PROFILE, token)["success"] is True
    assert controller.endpoint_board(REMOTE_PROFILE, token)["success"] is True
    options = controller.endpoint_config_options(token)
    assert options["data"]["config"]["profile_access_map"] == {
        "7": [HOME_PROFILE]
    }


def test_regular_user_is_limited_to_explicit_profile_mapping_for_reads_and_writes():
    """普通用户只能读写显式授权画像，用户名相同也不能猜测授权。"""
    plugin = FakePlugin()
    _seed(plugin)
    controller = AgentRankApiController(plugin)
    allowed = TokenPayload(sub=7, username="Alice", super_user=False)
    unmapped_same_name = TokenPayload(sub=8, username="Alice", super_user=False)

    assert controller.endpoint_overview(HOME_PROFILE, allowed)["success"] is True
    archived = controller.endpoint_archive(
        {"profile_id": HOME_PROFILE, "candidate_id": "tmdb:1"}, allowed
    )
    assert archived["data"]["changed"] is True

    for token, profile_id in (
        (allowed, REMOTE_PROFILE),
        (unmapped_same_name, HOME_PROFILE),
        (allowed, "emby:unknown:user-9"),
    ):
        with pytest.raises(fastapi_module.HTTPException) as caught:
            controller.endpoint_profile(profile_id, token)
        assert caught.value.status_code == 403
        assert caught.value.detail["error"]["code"] == "profile_forbidden"

    with pytest.raises(fastapi_module.HTTPException) as caught:
        controller.endpoint_archive(
            {"profile_id": REMOTE_PROFILE, "candidate_id": "tmdb:2"}, allowed
        )
    assert caught.value.status_code == 403
    assert caught.value.detail["error"]["code"] == "profile_forbidden"


def test_regular_user_status_is_filtered_and_config_options_are_forbidden():
    """普通用户状态只显示授权画像，完整配置接口仅对管理员开放。"""
    plugin = FakePlugin()
    controller = AgentRankApiController(plugin)
    allowed = TokenPayload(sub=7, username="Alice", super_user=False)
    unmapped = TokenPayload(sub=8, username="Alice", super_user=False)

    allowed_status = controller.endpoint_status(allowed)["data"]
    assert allowed_status["profiles"] == [
        {"profile_id": HOME_PROFILE, "username": "Alice"}
    ]
    assert allowed_status["default_profile_id"] == HOME_PROFILE

    hidden_status = controller.endpoint_status(unmapped)["data"]
    assert hidden_status["profiles"] == []
    assert hidden_status["default_profile_id"] == ""
    assert hidden_status["playback"] is None

    with pytest.raises(fastapi_module.HTTPException) as caught:
        controller.endpoint_config_options(allowed)
    assert caught.value.status_code == 403
    assert caught.value.detail["error"]["code"] == "superuser_required"


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

        def enumerate_libraries(self, identity):
            return [{"id": "movies", "name": "电影", "collection_type": "movies"}]

    plugin._emby_access = EmbyAccess()
    data = AgentRankApiController(plugin).config_options()["data"]
    profile_ids = {item["profile_id"] for item in data["emby_identities"]}
    assert profile_ids == {HOME_PROFILE, REMOTE_PROFILE, "emby:home:user-2"}
    assert data["config"]["emby_identities"] == [HOME_IDENTITY, REMOTE_IDENTITY]
    assert data["emby_libraries"][HOME_PROFILE][0]["name"] == "电影"


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


def test_profile_tags_are_merged_archived_and_restored_without_cross_pollution():
    """删除标签进入归档，恢复原类别且正负标签切换不污染归档。"""
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
    assert removed["data"]["profile"]["archived_profile_tags"] == [
        {"kind": "positive", "tag": "悬疑"}
    ]
    assert negative["data"]["profile"]["negative_tags"] == ["拖沓", "过度煽情"]
    preferences = plugin._repository.load_profile_preferences(HOME_PROFILE)
    assert preferences.custom_tags == ["冷门佳作"]
    assert preferences.archived_tags == ["悬疑"]
    assert preferences.archived_negative_tags == []

    restored = controller.update_profile_tag(
        {"profile_id": HOME_PROFILE, "kind": "positive", "action": "restore", "tag": "悬疑"}
    )

    assert restored["data"]["profile"]["tags"] == ["悬疑", "科幻", "冷门佳作"]
    assert restored["data"]["profile"]["archived_profile_tags"] == []


def test_legacy_suppressed_tags_migrate_without_opposite_category_shadows():
    """旧屏蔽字段迁移时排除由正负类别切换产生的内部影子。"""
    preferences = ProfilePreferences.from_dict(
        {
            "profile_id": HOME_PROFILE,
            "custom_tags": ["冷门佳作"],
            "custom_negative_tags": ["过度煽情"],
            "suppressed_tags": ["悬疑", "过度煽情"],
            "suppressed_negative_tags": ["冷门佳作", "拖沓"],
            "schema_version": 2,
        }
    )

    assert preferences.archived_tags == ["悬疑"]
    assert preferences.archived_negative_tags == ["拖沓"]
    assert preferences.schema_version == 3


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
