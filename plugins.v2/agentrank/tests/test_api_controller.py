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
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
controller_module = importlib.import_module(f"{PACKAGE_NAME}.controller.api")

RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
UserProfile = profile_module.UserProfile
RecommendationRun = run_module.RecommendationRun
ArchiveFeedback = archive_module.ArchiveFeedback
ArchiveEntry = archive_module.ArchiveEntry
AgentRankRepository = repository_module.AgentRankRepository
AgentRankApiController = controller_module.AgentRankApiController
ApiContractError = controller_module.ApiContractError
build_api_routes = controller_module.build_api_routes


class FakePlugin:
    """In-memory plugin with configurable runtime refresh results."""

    plugin_version = "1.0.0"

    def __init__(self):
        self.data = {}
        self._enabled = True
        self._config = {
            "enabled": True,
            "users": ["alice", "bob"],
            "default_user": "alice",
            "weights": {"rating_weight": 0.7},
            "_validation_errors": [],
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

    async def _refresh(self, username):
        if isinstance(self.refresh_result, Exception):
            raise self.refresh_result
        return self.refresh_result


def _seed(plugin):
    plugin._repository.save_profile(
        UserProfile(username="alice", summary="画像", run_id="run-old")
    )
    plugin._repository.save_board(
        RecommendationBoard(
            username="alice",
            run_id="run-old",
            status="success",
            recommendations=[
                RecommendationItem(candidate_id="tmdb:1", rank=1, title="One")
            ],
        )
    )
    plugin._repository.append_run(
        RecommendationRun(username="alice", run_id="run-old", status="success")
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
        "/archive",
        "/restore",
        "/archive/delete",
        "/profile/clear",
        "/run-history",
        "/subscribe",
    }
    assert all(route["auth"] == "bear" for route in routes)


@pytest.mark.parametrize("username", ["", None])
def test_user_endpoints_reject_missing_username_without_default_fallback(username):
    """Sensitive reads never silently replace a missing username with default_user."""
    controller = AgentRankApiController(FakePlugin())
    with pytest.raises(ApiContractError) as caught:
        controller.board(username)
    assert caught.value.status_code == 422
    assert caught.value.code == "username_required"


def test_unknown_user_returns_stable_404_error():
    """A logged-in but non-participating username cannot read another profile."""
    controller = AgentRankApiController(FakePlugin())
    with pytest.raises(ApiContractError) as caught:
        controller.profile("mallory")
    assert caught.value.status_code == 404
    assert caught.value.code == "unknown_user"


def test_options_overview_board_profile_and_history_have_stable_data_shape():
    """Read APIs always return success plus a data object with explicit empties."""
    plugin = FakePlugin()
    _seed(plugin)
    controller = AgentRankApiController(plugin)

    options = controller.config_options()
    overview = controller.overview("alice")
    board = controller.board("alice")
    profile = controller.profile("alice")
    history = controller.run_history("alice")

    assert options["success"] is True
    assert options["data"]["users"] == ["alice", "bob"]
    assert options["data"]["default_user"] == "alice"
    assert overview["data"]["board"]["run_id"] == "run-old"
    assert board["data"]["recommendations"][0]["candidate_id"] == "tmdb:1"
    assert profile["data"]["summary"] == "画像"
    assert history["data"]["items"][0]["run_id"] == "run-old"


def test_refresh_maps_running_and_downstream_failure_to_stable_contracts():
    """Refresh exposes concurrency state and maps unexpected runtime errors."""
    plugin = FakePlugin()
    controller = AgentRankApiController(plugin)
    plugin.refresh_result = SimpleNamespace(
        status="running", message="busy", run_id="", final_count=0
    )

    running = asyncio.run(controller.refresh({"username": "alice"}))
    assert running["data"]["status"] == "running"

    plugin.refresh_result = RuntimeError("boom")
    with pytest.raises(ApiContractError) as caught:
        asyncio.run(controller.refresh({"username": "alice"}))
    assert caught.value.status_code == 502
    assert caught.value.code == "refresh_failed"


def test_archive_restore_delete_and_clear_are_idempotent():
    """Repeated mutation requests return changed=false instead of duplicating effects."""
    plugin = FakePlugin()
    _seed(plugin)
    controller = AgentRankApiController(plugin)

    first_archive = controller.archive({"username": "alice", "candidate_id": "tmdb:1"})
    second_archive = controller.archive({"username": "alice", "candidate_id": "tmdb:1"})
    first_restore = controller.restore({"username": "alice", "candidate_id": "tmdb:1"})
    second_restore = controller.restore({"username": "alice", "candidate_id": "tmdb:1"})
    controller.archive({"username": "alice", "candidate_id": "tmdb:1"})
    first_delete = controller.delete_archive(
        {"username": "alice", "candidate_id": "tmdb:1"}
    )
    second_delete = controller.delete_archive(
        {"username": "alice", "candidate_id": "tmdb:1"}
    )
    first_clear = controller.clear_profile({"username": "alice", "confirm": True})
    second_clear = controller.clear_profile({"username": "alice", "confirm": True})

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
        controller.clear_profile({"username": "alice", "confirm": False})
    assert caught.value.status_code == 409
    assert caught.value.code == "confirmation_required"


def test_subscribe_route_is_stable_but_deferred_to_safety_task():
    """The route exists now and returns a stable unavailable error until Task 4.3."""
    controller = AgentRankApiController(FakePlugin())
    with pytest.raises(ApiContractError) as caught:
        controller.subscribe({"username": "alice", "candidate_id": "tmdb:1"})
    assert caught.value.status_code == 409
    assert caught.value.code == "subscription_not_ready"
