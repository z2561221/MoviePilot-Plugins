"""AgentRank configuration and per-user repository tests."""

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_contract_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

config_module = importlib.import_module(f"{PACKAGE_NAME}.model.config")
profile_module = importlib.import_module(f"{PACKAGE_NAME}.model.profile")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
archive_module = importlib.import_module(f"{PACKAGE_NAME}.model.archive")
run_module = importlib.import_module(f"{PACKAGE_NAME}.model.run")
candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")

AgentRankConfig = config_module.AgentRankConfig
ConfigValidationError = config_module.ConfigValidationError
WEIGHT_DEFAULTS = config_module.WEIGHT_DEFAULTS
normalize_config = config_module.normalize_config
UserProfile = profile_module.UserProfile
RecommendationBoard = board_module.RecommendationBoard
ArchiveFeedback = archive_module.ArchiveFeedback
RecommendationRun = run_module.RecommendationRun
Candidate = candidate_module.Candidate
AgentRankRepository = repository_module.AgentRankRepository


class FakePlugin:
    """In-memory stand-in for MoviePilot plugindata methods."""

    def __init__(self, data=None):
        self.data = dict(data or {})

    def get_data(self, key=None):
        return self.data.get(key)

    def save_data(self, key=None, value=None):
        self.data[key] = value

    def del_data(self, key=None):
        self.data.pop(key, None)


def test_config_has_exact_ten_weight_defaults_and_valid_bounds():
    """The strict config model exposes all ten specified 0-1 weights."""
    assert WEIGHT_DEFAULTS == {
        "type_weight": 0.8,
        "theme_weight": 0.8,
        "actor_weight": 0.5,
        "director_weight": 0.4,
        "region_weight": 0.4,
        "year_weight": 0.3,
        "rating_weight": 0.7,
        "heat_weight": 0.6,
        "freshness_weight": 0.5,
        "similarity_weight": 0.8,
    }
    config = AgentRankConfig.from_mapping({"weights": WEIGHT_DEFAULTS})
    assert config.weights == WEIGHT_DEFAULTS

    with pytest.raises(ConfigValidationError, match="type_weight"):
        AgentRankConfig.from_mapping({"weights": {"type_weight": 1.1}})


def test_default_user_validation_is_visible_and_never_silently_reassigned():
    """An invalid default user remains visible as an error, not another user."""
    with pytest.raises(ConfigValidationError, match="default_user"):
        AgentRankConfig.from_mapping({"users": ["alice"], "default_user": "bob"})

    normalized = normalize_config({"users": ["alice"], "default_user": "bob"})
    assert normalized["default_user"] == "bob"
    assert any("default_user" in error for error in normalized["_validation_errors"])


def test_config_normalization_recovers_invalid_values_without_load_failure():
    """Plugin initialization gets safe values plus recoverable validation evidence."""
    normalized = normalize_config(
        {
            "users": ["alice", "alice", "", None],
            "weights": {"rating_weight": "broken"},
            "candidate_pool_size": -5,
            "confidence_threshold": 9,
            "action_mode": "unsafe",
            "auto_subscribe_top_n": 99,
        }
    )

    assert normalized["users"] == ["alice"]
    assert normalized["weights"]["rating_weight"] == WEIGHT_DEFAULTS["rating_weight"]
    assert normalized["candidate_pool_size"] >= 10
    assert 0 <= normalized["confidence_threshold"] <= 1
    assert normalized["action_mode"] == "notify"
    assert normalized["auto_subscribe_top_n"] <= normalized["auto_subscribe_limit"]
    assert normalized["_validation_errors"]

    corrupted = normalize_config("broken")
    assert corrupted["weights"] == WEIGHT_DEFAULTS
    assert corrupted["_validation_errors"] == ["config must be a mapping"]


def test_repository_isolates_users_and_candidate_runs():
    """Every persisted object is scoped by username and candidate run id."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)

    repository.save_profile(UserProfile(username="alice", summary="A"))
    repository.save_profile(UserProfile(username="bob", summary="B"))
    repository.save_board(RecommendationBoard(username="alice", run_id="run-a"))
    repository.save_archive(ArchiveFeedback(username="alice"))
    repository.save_candidate_snapshot("run-a", "alice", [Candidate(candidate_id="c1", title="One")])
    repository.save_candidate_snapshot("run-b", "alice", [Candidate(candidate_id="c2", title="Two")])

    assert repository.load_profile("alice").summary == "A"
    assert repository.load_profile("bob").summary == "B"
    assert repository.load_board("bob") is None
    assert repository.load_archive("bob").username == "bob"
    assert repository.load_candidate_snapshot("run-a", "alice")[0].candidate_id == "c1"
    assert repository.load_candidate_snapshot("run-b", "alice")[0].candidate_id == "c2"


def test_corrupted_storage_recovers_and_records_evidence():
    """Malformed stored values do not break loading and leave an audit record."""
    plugin = FakePlugin({"profile_snapshot:alice": "not-a-mapping"})
    repository = AgentRankRepository(plugin)

    assert repository.load_profile("alice") is None
    recovery_log = plugin.data["agentrank_recovery_log"]
    assert recovery_log[-1]["key"] == "profile_snapshot:alice"
    assert recovery_log[-1]["action"] == "ignored_corrupt_data"


def test_legacy_profile_migrates_to_current_key_with_evidence():
    """A valid legacy record is copied to the current key and migration is logged."""
    plugin = FakePlugin({"profile:alice": {"username": "alice", "summary": "legacy"}})
    repository = AgentRankRepository(plugin)

    profile = repository.load_profile("alice")
    assert profile.summary == "legacy"
    assert plugin.data["profile_snapshot:alice"]["schema_version"] >= 1
    assert plugin.data["agentrank_recovery_log"][-1]["action"] == "migrated_legacy_key"


def test_run_history_is_user_scoped_and_bounded():
    """Run history keeps newest records only and never crosses usernames."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin, history_limit=3)
    for index in range(5):
        repository.append_run(RecommendationRun(username="alice", run_id=f"run-{index}"))
    repository.append_run(RecommendationRun(username="bob", run_id="bob-run"))

    assert [item.run_id for item in repository.load_run_history("alice")] == [
        "run-4",
        "run-3",
        "run-2",
    ]
    assert [item.run_id for item in repository.load_run_history("bob")] == ["bob-run"]
