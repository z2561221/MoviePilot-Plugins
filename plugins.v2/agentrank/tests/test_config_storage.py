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
DEFAULT_AGENT_PROMPT = config_module.DEFAULT_AGENT_PROMPT
LEGACY_DEFAULT_AGENT_PROMPT = config_module.LEGACY_DEFAULT_AGENT_PROMPT
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


def test_discovery_page_defaults_on_and_candidate_pool_defaults_to_fifty():
    """发现页入口保持兼容开启，候选池默认收缩到五十。"""
    defaults = AgentRankConfig.from_mapping({})
    assert defaults.discovery_page_enabled is True
    assert defaults.candidate_pool_size == 50
    assert set(defaults.discovery_sources) == {
        "douban",
        "tmdb_movies",
        "tmdb_tv",
        "bangumi",
    }
    assert "extensions" not in normalize_config(
        {"discovery_sources": {"douban": False, "extensions": True}}
    )["discovery_sources"]
    assert AgentRankConfig.from_mapping(
        {"discovery_page_enabled": False}
    ).discovery_page_enabled is False


def test_run_once_switch_defaults_off_and_accepts_explicit_request():
    """立即运行开关默认关闭，并可作为一次性配置请求持久化。"""
    assert AgentRankConfig.from_mapping({}).onlyonce is False
    assert AgentRankConfig.from_mapping({"onlyonce": True}).onlyonce is True


def test_playback_source_defaults_and_user_mapping_are_bounded():
    """播放画像默认自动探测，用户映射和阈值进入规范化配置。"""
    config = AgentRankConfig.from_mapping(
        {
            "users": ["alice"],
            "playback_user_map": {"alice": "Emby Alice", "": "ignored", "bob": ""},
            "playback_source_mode": "emby_native",
            "playback_completion_threshold": 0.9,
        }
    )
    assert config.playback_source_mode == "emby_native"
    assert config.playback_user_map == {"alice": "Emby Alice"}
    assert config.playback_completion_threshold == 0.9
    assert AgentRankConfig.from_mapping({}).playback_source_mode == "auto"


def test_playback_snapshot_is_scoped_and_does_not_store_sensitive_fields():
    """播放快照按用户隔离，持久化字段不包含设备、地址或凭据。"""
    from agentrank_contract_test.model.playback import PlaybackSample, PlaybackSnapshot

    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_playback_snapshot(
        PlaybackSnapshot(
            profile_id="emby:home:user-1",
            username="Alice",
            source="playback_reporting",
            confidence="high",
            status="ready",
            samples=[PlaybackSample("tmdb:movie:1", "One", "movie", tmdb_id="1", completed=True)],
        )
    )
    stored = plugin.data["playback_snapshot:profile:emby%3Ahome%3Auser-1"]
    assert repository.load_playback_snapshot("emby:home:user-1").samples[0].completed is True
    assert repository.load_playback_snapshot("emby:remote:user-1") is None
    assert "api_key" not in stored and "device" not in stored and "client" not in stored


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


def test_agent_prompt_is_editable_but_non_empty_and_bounded():
    """自定义排序提示词会持久化，空值或超长值则安全回退。"""
    custom = "多推荐冷门科幻，文案俏皮但不要剧透。"
    assert AgentRankConfig.from_mapping({"agent_prompt": custom}).agent_prompt == custom

    empty = normalize_config({"agent_prompt": "  "})
    oversized = normalize_config({"agent_prompt": "字" * 4001})
    assert empty["agent_prompt"] == DEFAULT_AGENT_PROMPT
    assert oversized["agent_prompt"] == DEFAULT_AGENT_PROMPT
    assert any("agent_prompt" in error for error in empty["_validation_errors"])
    assert any("agent_prompt" in error for error in oversized["_validation_errors"])


def test_legacy_default_prompt_migrates_without_overwriting_custom_prompt():
    """仅旧版内置默认值自动升级，用户真正自定义的提示词保持不变。"""
    custom = "只推荐我没看过的冷门历史剧。"

    assert normalize_config({"agent_prompt": LEGACY_DEFAULT_AGENT_PROMPT})[
        "agent_prompt"
    ] == DEFAULT_AGENT_PROMPT
    assert normalize_config({"agent_prompt": custom})["agent_prompt"] == custom


def test_repository_isolates_profiles_and_candidate_runs():
    """Every persisted object is scoped by profile_id and candidate run id."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    home = "emby:home:user-1"
    remote = "emby:remote:user-1"

    repository.save_profile(UserProfile(profile_id=home, username="Alice", summary="A"))
    repository.save_profile(UserProfile(profile_id=remote, username="Alice", summary="B"))
    repository.save_board(RecommendationBoard(profile_id=home, username="Alice", run_id="run-a"))
    repository.save_archive(ArchiveFeedback(profile_id=home, username="Alice"))
    repository.save_candidate_snapshot("run-a", home, [Candidate(candidate_id="c1", title="One")])
    repository.save_candidate_snapshot("run-b", home, [Candidate(candidate_id="c2", title="Two")])

    assert repository.load_profile(home).summary == "A"
    assert repository.load_profile(remote).summary == "B"
    assert repository.load_board(remote) is None
    assert repository.load_archive(remote).profile_id == remote
    assert repository.load_candidate_snapshot("run-a", home)[0].candidate_id == "c1"
    assert repository.load_candidate_snapshot("run-b", home)[0].candidate_id == "c2"


def test_corrupted_storage_recovers_and_records_evidence():
    """Malformed stored values do not break loading and leave an audit record."""
    key = "profile_snapshot:profile:emby%3Ahome%3Auser-1"
    plugin = FakePlugin({key: "not-a-mapping"})
    repository = AgentRankRepository(plugin)

    assert repository.load_profile("emby:home:user-1") is None
    recovery_log = plugin.data["agentrank_recovery_log"]
    assert recovery_log[-1]["key"] == key
    assert recovery_log[-1]["action"] == "ignored_corrupt_data"


def test_legacy_username_keys_remain_isolated_and_untouched():
    """旧 username 键不被新 profile_id 读取、迁移或删除。"""
    legacy = {"username": "alice", "summary": "legacy"}
    plugin = FakePlugin(
        {
            "profile:alice": legacy,
            "profile_snapshot:alice": {"username": "alice", "summary": "old"},
        }
    )
    repository = AgentRankRepository(plugin)

    assert repository.load_profile("emby:home:user-1") is None
    repository.clear_profile_and_board("emby:home:user-1")
    assert plugin.data["profile:alice"] == legacy
    assert plugin.data["profile_snapshot:alice"]["username"] == "alice"
    assert "agentrank_recovery_log" not in plugin.data


def test_candidate_snapshot_rejects_cross_profile_and_run_payloads():
    """候选载荷必须同时匹配请求的 profile_id 与 run_id。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    home = "emby:home:user-1"
    remote = "emby:remote:user-1"
    source_key = "candidate_snapshot:profile:emby%3Ahome%3Auser-1:run:run-a"
    repository.save_candidate_snapshot(
        "run-a", home, [Candidate(candidate_id="c1", title="One")]
    )

    cross_profile_key = (
        "candidate_snapshot:profile:emby%3Aremote%3Auser-1:run:run-a"
    )
    plugin.data[cross_profile_key] = dict(plugin.data[source_key])
    assert repository.load_candidate_snapshot("run-a", remote) == []
    assert plugin.data["agentrank_recovery_log"][-1]["detail"] == (
        "candidate snapshot profile_id mismatch"
    )

    cross_run_key = "candidate_snapshot:profile:emby%3Ahome%3Auser-1:run:run-b"
    plugin.data[cross_run_key] = dict(plugin.data[source_key])
    assert repository.load_candidate_snapshot("run-b", home) == []
    assert plugin.data["agentrank_recovery_log"][-1]["detail"] == (
        "candidate snapshot run_id mismatch"
    )


def test_run_history_is_user_scoped_and_bounded():
    """Run history keeps newest records only and never crosses usernames."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin, history_limit=3)
    for index in range(5):
        repository.append_run(
            RecommendationRun(profile_id="emby:home:user-1", username="Alice", run_id=f"run-{index}")
        )
    repository.append_run(
        RecommendationRun(profile_id="emby:remote:user-1", username="Alice", run_id="remote-run")
    )

    assert [item.run_id for item in repository.load_run_history("emby:home:user-1")] == [
        "run-4",
        "run-3",
        "run-2",
    ]
    assert [item.run_id for item in repository.load_run_history("emby:remote:user-1")] == [
        "remote-run"
    ]
