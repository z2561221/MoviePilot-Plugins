"""AgentRank archive feedback, restore, and atomic cleanup tests."""

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_archive_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
profile_module = importlib.import_module(f"{PACKAGE_NAME}.model.profile")
run_module = importlib.import_module(f"{PACKAGE_NAME}.model.run")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
service_module = importlib.import_module(f"{PACKAGE_NAME}.service.archive")

RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
UserProfile = profile_module.UserProfile
RecommendationRun = run_module.RecommendationRun
AgentRankRepository = repository_module.AgentRankRepository
ArchiveService = service_module.ArchiveService


class FakePlugin:
    """In-memory plugindata store with one-shot deletion failure injection."""

    def __init__(self):
        self.data = {}
        self.fail_delete_key = None

    def get_data(self, key=None):
        return self.data.get(key)

    def save_data(self, key=None, value=None):
        self.data[key] = value

    def del_data(self, key=None):
        if self.fail_delete_key == key:
            self.fail_delete_key = None
            raise RuntimeError("injected delete failure")
        self.data.pop(key, None)


def _board(username="alice"):
    return RecommendationBoard(
        username=username,
        run_id="run-1",
        status="success",
        recommendations=[
            RecommendationItem(candidate_id="c1", rank=1, title="One"),
            RecommendationItem(candidate_id="c2", rank=2, title="Two"),
            RecommendationItem(candidate_id="c3", rank=3, title="Three"),
        ],
    )


def test_ignore_removes_board_item_and_archives_original_rank():
    """Ignoring a recommendation preserves its original rank and payload."""
    repository = AgentRankRepository(FakePlugin())
    repository.save_board(_board())
    service = ArchiveService(repository)

    result = service.ignore("alice", "c2")

    assert result.changed is True
    assert [item.candidate_id for item in repository.load_board("alice").recommendations] == [
        "c1",
        "c3",
    ]
    entry = repository.load_archive("alice").entries[0]
    assert entry.candidate_id == "c2"
    assert entry.original_rank == 2
    assert entry.recommendation["title"] == "Two"


def test_restore_uses_open_original_rank_and_removes_negative_feedback():
    """An unoccupied original rank is restored exactly and archive feedback is removed."""
    repository = AgentRankRepository(FakePlugin())
    repository.save_board(_board())
    service = ArchiveService(repository)
    service.ignore("alice", "c2")

    result = service.restore("alice", "c2")

    assert result.changed is True
    board = repository.load_board("alice")
    assert [(item.candidate_id, item.rank) for item in board.recommendations] == [
        ("c1", 1),
        ("c2", 2),
        ("c3", 3),
    ]
    assert repository.load_archive("alice").entries == []


def test_restore_appends_when_original_rank_is_now_occupied():
    """A restored item appends when a newer item occupies its former rank."""
    repository = AgentRankRepository(FakePlugin())
    repository.save_board(_board())
    service = ArchiveService(repository)
    service.ignore("alice", "c2")
    board = repository.load_board("alice")
    board.recommendations.append(RecommendationItem(candidate_id="c4", rank=2, title="Four"))
    repository.save_board(board)

    service.restore("alice", "c2")

    restored = next(
        item for item in repository.load_board("alice").recommendations if item.candidate_id == "c2"
    )
    assert restored.rank == 4


def test_ignore_and_restore_are_idempotent():
    """Repeated archive actions return unchanged without duplicating records."""
    repository = AgentRankRepository(FakePlugin())
    repository.save_board(_board())
    service = ArchiveService(repository)

    assert service.ignore("alice", "c2").changed is True
    assert service.ignore("alice", "c2").changed is False
    assert len(repository.load_archive("alice").entries) == 1
    assert service.restore("alice", "c2").changed is True
    assert service.restore("alice", "c2").changed is False


def test_cross_user_board_payload_is_rejected():
    """A mismatched stored owner cannot be mutated through another user's key."""
    plugin = FakePlugin()
    plugin.data["recommendation_board:alice"] = _board(username="bob").to_dict()
    repository = AgentRankRepository(plugin)
    service = ArchiveService(repository)

    with pytest.raises(PermissionError, match="username"):
        service.ignore("alice", "c1")

    assert plugin.data["recommendation_board:alice"]["username"] == "bob"


def test_profile_cleanup_rolls_back_both_objects_when_second_delete_fails():
    """A partial deletion restores both profile and board exactly."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_profile(UserProfile(username="alice", summary="keep"))
    repository.save_board(_board())
    plugin.fail_delete_key = "recommendation_board:alice"
    service = ArchiveService(repository)

    with pytest.raises(RuntimeError, match="injected delete failure"):
        service.clear_profile("alice")

    assert repository.load_profile("alice").summary == "keep"
    assert repository.load_board("alice").run_id == "run-1"


def test_profile_cleanup_leaves_archive_history_and_global_config_untouched():
    """Successful cleanup deletes only the current profile and board keys."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_profile(UserProfile(username="alice", summary="remove"))
    repository.save_board(_board())
    repository.append_run(RecommendationRun(username="alice", run_id="run-1"))
    archive = repository.load_archive("alice")
    repository.save_archive(archive)
    plugin.data["plugin_global_config"] = {"enabled": True}
    service = ArchiveService(repository)

    result = service.clear_profile("alice")

    assert result.changed is True
    assert repository.load_profile("alice") is None
    assert repository.load_board("alice") is None
    assert "archive:alice" in plugin.data
    assert "run_history:alice" in plugin.data
    assert plugin.data["plugin_global_config"] == {"enabled": True}
