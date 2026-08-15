"""AgentRank configuration and per-user repository tests."""

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"
PACKAGE_NAME = "agentrank_contract_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

config_module = importlib.import_module(f"{PACKAGE_NAME}.model.config")
profile_module = importlib.import_module(f"{PACKAGE_NAME}.model.profile")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
archive_module = importlib.import_module(f"{PACKAGE_NAME}.model.archive")
run_module = importlib.import_module(f"{PACKAGE_NAME}.model.run")
candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
snapshot_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate_snapshot")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")

AgentRankConfig = config_module.AgentRankConfig
ConfigValidationError = config_module.ConfigValidationError
WEIGHT_DEFAULTS = config_module.WEIGHT_DEFAULTS
DEFAULT_AGENT_PROMPT = config_module.DEFAULT_AGENT_PROMPT
DEFAULT_PROFILE_PROMPT = config_module.DEFAULT_PROFILE_PROMPT
DEFAULT_RANKING_PROMPT = config_module.DEFAULT_RANKING_PROMPT
DEFAULT_COPY_PROMPT = config_module.DEFAULT_COPY_PROMPT
DEFAULT_CRITIC_PROMPT = config_module.DEFAULT_CRITIC_PROMPT
DEFAULT_PERSONA_PROMPT = config_module.DEFAULT_PERSONA_PROMPT
AGENT_DISPLAY_NAME_DEFAULT = config_module.AGENT_DISPLAY_NAME_DEFAULT
LEGACY_DEFAULT_AGENT_PROMPT = config_module.LEGACY_DEFAULT_AGENT_PROMPT
LEGACY_PLAYBACK_DEFAULT_AGENT_PROMPT = config_module.LEGACY_PLAYBACK_DEFAULT_AGENT_PROMPT
LEGACY_SUBSCRIPTION_DEFAULT_AGENT_PROMPT = (
    config_module.LEGACY_SUBSCRIPTION_DEFAULT_AGENT_PROMPT
)
normalize_config = config_module.normalize_config
default_config = config_module.default_config
UserProfile = profile_module.UserProfile
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
ArchiveFeedback = archive_module.ArchiveFeedback
RecommendationRun = run_module.RecommendationRun
Candidate = candidate_module.Candidate
CandidateSnapshot = snapshot_module.CandidateSnapshot
AgentRankRepository = repository_module.AgentRankRepository

HOME_IDENTITY = {
    "server_name": "home",
    "user_id": "user-1",
    "username": "Alice",
    "profile_id": "emby:home:user-1",
    "schema_version": 1,
}


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


def _candidate_snapshot(run_id, profile_id, candidates):
    """构造包含最小真实画像版本信息的 schema 3 候选快照。"""
    return CandidateSnapshot.create(
        profile_id=profile_id,
        run_id=run_id,
        profile_version={"run_id": f"profile-{run_id}", "schema_version": 4},
        retrieval_plan={},
        candidates=candidates,
    )


def test_internal_weight_defaults_are_not_user_config():
    """十项证据维度保留为内部基准，但旧权重不会进入规范化用户配置。"""
    assert WEIGHT_DEFAULTS == {
        "type_weight": 0.8,
        "theme_weight": 0.8,
        "actor_weight": 0.5,
        "director_weight": 0.4,
        "region_weight": 0.4,
        "year_weight": 0.9,
        "rating_weight": 0.9,
        "heat_weight": 0.9,
        "freshness_weight": 0.9,
        "similarity_weight": 0.9,
    }
    normalized = normalize_config(
        {"weights": {"type_weight": 1.1}, "theme_weight": 0.0}
    )
    assert "weights" not in normalized
    assert "theme_weight" not in normalized
    assert normalized["_validation_errors"] == []


def test_discovery_page_defaults_on_and_candidate_pool_defaults_to_fifteen():
    """发现页入口保持开启，来源选择退出用户配置且策略版本升级。"""
    defaults = AgentRankConfig.from_mapping({})
    assert defaults.discovery_page_enabled is True
    assert defaults.notification_type == "Plugin"
    assert defaults.interaction_mode == "auto"
    assert defaults.candidate_pool_size == 15
    assert defaults.strategy_version == 2
    migrated = normalize_config(
        {"discovery_sources": {"douban": False, "extensions": True}}
    )
    assert "discovery_sources" not in migrated
    assert AgentRankConfig.from_mapping(
        {"discovery_page_enabled": False}
    ).discovery_page_enabled is False
    assert AgentRankConfig.from_mapping(
        {"notification_type": "Agent"}
    ).notification_type == "Agent"
    invalid_notice = normalize_config({"notification_type": "unknown"})
    assert invalid_notice["notification_type"] == "Plugin"
    assert any("notification_type" in item for item in invalid_notice["_validation_errors"])


def test_non_privacy_defaults_follow_current_runtime_without_private_identity():
    """新装默认复制当前非隐私设置，但不固化任何 Emby 私有身份。"""
    defaults = default_config()

    expected_non_privacy = {
        "discovery_page_enabled": True,
        "strategy_version": 2,
        "onlyonce": False,
        "schedule_enabled": True,
        "cron": "5 18 * * *",
        "minimum_samples": 5,
        "candidate_pool_size": 15,
        "confidence_threshold": 0.6,
        "action_mode": "notify",
        "interaction_mode": "auto",
        "notify": True,
        "notification_type": "Plugin",
        "auto_subscribe_top_n": 0,
        "auto_subscribe_limit": 10,
        "history_limit": 50,
        "candidate_snapshot_limit": 20,
        "feedback_event_limit": 1000,
        "feedback_queue_limit": 200,
        "conversation_message_limit": 200,
        "attribution_record_limit": 500,
        "analysis_record_limit": 500,
        "profile_cache_enabled": True,
        "rebuild_profile_each_run": False,
        "playback_enabled": True,
        "playback_recent_days": 90,
        "playback_completion_threshold": 0.85,
        "playback_abandon_minutes": 20,
        "playback_cache_days": 7,
    }

    assert {key: defaults[key] for key in expected_non_privacy} == expected_non_privacy
    assert defaults["enabled"] is False
    assert defaults["emby_identities"] == []
    assert defaults["default_profile_id"] == ""
    assert "profile_access_map" not in defaults
    assert defaults["emby_library_ids"] is None
    assert "media_types" not in defaults
    assert "exclude_keywords" not in defaults


@pytest.mark.parametrize(
    ("field_name", "default_value"),
    [
        ("candidate_snapshot_limit", 20),
        ("feedback_event_limit", 1000),
        ("feedback_queue_limit", 200),
        ("conversation_message_limit", 200),
        ("attribution_record_limit", 500),
        ("analysis_record_limit", 500),
    ],
)
def test_retention_limits_are_positive_bounded_non_privacy_settings(
    field_name, default_value
):
    """保留上限可配置，但零值、负值和超大值均回退并显示错误。"""
    assert getattr(AgentRankConfig.from_mapping({}), field_name) == default_value
    for invalid in (0, -1, 100001):
        normalized = normalize_config({field_name: invalid})
        assert normalized[field_name] == default_value
        assert any(field_name in error for error in normalized["_validation_errors"])


def test_run_once_switch_defaults_off_and_accepts_explicit_request():
    """立即运行开关默认关闭，并可作为一次性配置请求持久化。"""
    assert AgentRankConfig.from_mapping({}).onlyonce is False
    assert AgentRankConfig.from_mapping({"onlyonce": True}).onlyonce is True


def test_emby_identity_config_ignores_legacy_profile_access_map():
    """旧访问映射可留在历史输入中，但不再进入运行时配置。"""
    config = AgentRankConfig.from_mapping(
        {
            "enabled": True,
            "emby_identities": [HOME_IDENTITY],
            "default_profile_id": "emby:home:user-1",
            "profile_access_map": {7: ["emby:home:user-1"]},
            # 旧字段可以留在历史配置中，但不再进入运行时模型。
            "playback_source_mode": "emby_native",
            "playback_completion_threshold": 0.9,
        }
    )
    assert config.emby_identities == [HOME_IDENTITY]
    assert config.default_profile_id == "emby:home:user-1"
    assert config.playback_completion_threshold == 0.9
    assert "profile_access_map" not in config.to_dict()
    assert "playback_source_mode" not in config.to_dict()
    assert "users" not in config.to_dict()
    assert "default_user" not in config.to_dict()
    assert "playback_user_map" not in config.to_dict()
    assert "playback_source_mode" not in default_config()


def test_legacy_profile_access_map_does_not_add_validation_errors():
    """废弃访问映射中的旧值不再阻止配置加载。"""
    normalized = normalize_config(
        {
            "emby_identities": [HOME_IDENTITY],
            "profile_access_map": {
                "alice": ["emby:home:user-1"],
                "7": ["emby:remote:user-1"],
            },
        }
    )

    assert "profile_access_map" not in normalized
    assert not any("profile_access_map" in error for error in normalized["_validation_errors"])


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


def test_default_profile_validation_is_visible_and_never_silently_reassigned():
    """无效默认身份必须报错，不得静默选择另一个 Emby 用户。"""
    invalid = {
        "enabled": True,
        "emby_identities": [HOME_IDENTITY],
        "default_profile_id": "emby:remote:user-1",
    }
    with pytest.raises(ConfigValidationError, match="default_profile_id"):
        AgentRankConfig.from_mapping(invalid)

    normalized = normalize_config(invalid)
    assert normalized["default_profile_id"] == "emby:remote:user-1"
    assert any(
        "default_profile_id" in error for error in normalized["_validation_errors"]
    )


def test_empty_and_invalid_emby_identity_config_is_explicit():
    """停用时允许空身份，启用时空身份或非法身份必须留下错误。"""
    assert AgentRankConfig.from_mapping({}).emby_identities == []
    empty = normalize_config({"enabled": True})
    invalid = normalize_config(
        {
            "emby_identities": [
                {"server_name": "home/server", "user_id": "id-1", "username": "Alice"}
            ]
        }
    )
    assert any("emby_identities" in error for error in empty["_validation_errors"])
    assert invalid["emby_identities"] == []
    assert any("is invalid" in error for error in invalid["_validation_errors"])


def test_config_normalization_recovers_invalid_values_without_load_failure():
    """Plugin initialization gets safe values plus recoverable validation evidence."""
    normalized = normalize_config(
        {
            "emby_identities": [HOME_IDENTITY],
            "default_profile_id": "emby:home:user-1",
            "weights": {"rating_weight": "broken"},
            "candidate_pool_size": -5,
            "confidence_threshold": 9,
            "action_mode": "unsafe",
            "interaction_mode": "too_loud",
            "auto_subscribe_top_n": 99,
        }
    )

    assert normalized["emby_identities"] == [HOME_IDENTITY]
    assert "weights" not in normalized
    assert normalized["candidate_pool_size"] >= 10
    assert 0 <= normalized["confidence_threshold"] <= 1
    assert normalized["action_mode"] == "notify"
    assert normalized["interaction_mode"] == "auto"
    assert any("interaction_mode" in error for error in normalized["_validation_errors"])
    assert normalized["auto_subscribe_top_n"] <= normalized["auto_subscribe_limit"]
    assert normalized["_validation_errors"]
    for removed in (
        "users",
        "default_user",
        "playback_user_map",
        "profile_scope",
        "recent_days",
        "subscription_sample_limit",
    ):
        assert removed not in normalized
        assert removed not in default_config()

    corrupted = normalize_config("broken")
    assert "weights" not in corrupted
    assert corrupted["_validation_errors"] == ["config must be a mapping"]


def test_rule_prompts_are_editable_non_empty_and_bounded():
    """四类规则提示词独立持久化，空值或超长值安全回退。"""
    defaults = {
        "profile_prompt": DEFAULT_PROFILE_PROMPT,
        "ranking_prompt": DEFAULT_RANKING_PROMPT,
        "copy_prompt": DEFAULT_COPY_PROMPT,
        "critic_prompt": DEFAULT_CRITIC_PROMPT,
    }
    for field_name, default in defaults.items():
        custom = f"自定义{field_name}"
        assert getattr(AgentRankConfig.from_mapping({field_name: custom}), field_name) == custom
        empty = normalize_config({field_name: "  "})
        oversized = normalize_config({field_name: "字" * 4001})
        assert empty[field_name] == default
        assert oversized[field_name] == default
        assert any(field_name in error for error in empty["_validation_errors"])
        assert any(field_name in error for error in oversized["_validation_errors"])

    assert "agent_prompt" not in default_config()


def test_agent_persona_defaults_separate_builtin_preset_from_custom_text():
    """默认显示克里斯蒂娜，内置预设不再占用自定义语气字段。"""
    defaults = default_config()
    assert AGENT_DISPLAY_NAME_DEFAULT == "克里斯蒂娜"
    assert defaults["agent_display_name"] == "克里斯蒂娜"
    assert defaults["persona_preset"] == "default"
    assert defaults["persona_prompt"] == ""

    blank = normalize_config({"persona_prompt": "  "})
    assert blank["persona_preset"] == "default"
    assert blank["persona_prompt"] == ""
    assert blank["_validation_errors"] == []

    migrated_default = normalize_config({"persona_prompt": DEFAULT_PERSONA_PROMPT})
    assert migrated_default["persona_preset"] == "default"
    assert migrated_default["persona_prompt"] == ""

    custom = normalize_config({"persona_prompt": "用简短的实验记录语气。"})
    assert custom["persona_preset"] == "custom"
    assert custom["persona_prompt"] == "用简短的实验记录语气。"

    oversized = normalize_config(
        {"persona_preset": "custom", "persona_prompt": "字" * 4001}
    )
    assert oversized["persona_prompt"] == ""
    assert any("persona_prompt" in error for error in oversized["_validation_errors"])


def test_legacy_default_prompt_migrates_without_overwriting_custom_prompt():
    """旧内置值升级为三套默认，自定义值复制到画像与排序。"""
    custom = "只推荐我没看过的冷门历史剧。"
    for legacy_default in (
        DEFAULT_AGENT_PROMPT,
        LEGACY_DEFAULT_AGENT_PROMPT,
        LEGACY_SUBSCRIPTION_DEFAULT_AGENT_PROMPT,
        LEGACY_PLAYBACK_DEFAULT_AGENT_PROMPT,
    ):
        migrated = normalize_config({"agent_prompt": legacy_default})
        assert migrated["profile_prompt"] == DEFAULT_PROFILE_PROMPT
        assert migrated["ranking_prompt"] == DEFAULT_RANKING_PROMPT
        assert migrated["copy_prompt"] == DEFAULT_COPY_PROMPT
        assert migrated["critic_prompt"] == DEFAULT_CRITIC_PROMPT
        assert "agent_prompt" not in migrated

    migrated_custom = normalize_config({"agent_prompt": custom})
    assert migrated_custom["profile_prompt"] == custom
    assert migrated_custom["ranking_prompt"] == custom
    assert migrated_custom["copy_prompt"] == DEFAULT_COPY_PROMPT
    assert migrated_custom["critic_prompt"] == DEFAULT_CRITIC_PROMPT
    assert "agent_prompt" not in migrated_custom

    explicit = normalize_config(
        {"agent_prompt": custom, "profile_prompt": "新的画像规则"}
    )
    assert explicit["profile_prompt"] == "新的画像规则"
    assert explicit["ranking_prompt"] == custom


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
    repository.save_candidate_snapshot(
        _candidate_snapshot(
            "run-a",
            home,
            [Candidate(candidate_id="tmdb:movie:1", title="One", media_type="movie")],
        )
    )
    repository.save_candidate_snapshot(
        _candidate_snapshot(
            "run-b",
            home,
            [Candidate(candidate_id="tmdb:tv:2", title="Two", media_type="tv")],
        )
    )

    assert repository.load_profile(home).summary == "A"
    assert repository.load_profile(remote).summary == "B"
    assert repository.load_board(remote) is None
    assert repository.load_archive(remote).profile_id == remote
    assert repository.load_candidate_snapshot("run-a", home)[0].candidate_id == (
        "tmdb:movie:1"
    )
    assert repository.load_candidate_snapshot("run-b", home)[0].candidate_id == (
        "tmdb:tv:2"
    )


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
        _candidate_snapshot(
            "run-a",
            home,
            [Candidate(candidate_id="tmdb:movie:1", title="One", media_type="movie")],
        )
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


def test_board_history_is_immutable_idempotent_and_full_reset_managed():
    """历史榜单只冻结每个 run_id 的首次内容，并随彻底重置删除。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin, history_limit=3)
    profile_id = "emby:home:user-1"

    first = RecommendationBoard(
        profile_id=profile_id,
        username="Alice",
        run_id="run-1",
        status="success",
        recommendations=[
            RecommendationItem(candidate_id="tmdb:movie:1", rank=1, title="One")
        ],
    )
    repository.save_board(first)
    first.recommendations[0].title = "Mutated after save"
    repository.save_board(
        RecommendationBoard(
            profile_id=profile_id,
            username="Alice",
            run_id="run-1",
            status="success",
            recommendations=[
                RecommendationItem(
                    candidate_id="tmdb:movie:1", rank=1, title="Replaced"
                )
            ],
        )
    )
    assert repository.load_board_history(profile_id)[0].recommendations[0].title == "One"

    for index in range(2, 5):
        repository.save_board(
            RecommendationBoard(
                profile_id=profile_id,
                username="Alice",
                run_id=f"run-{index}",
                status="success",
                recommendations=[
                    RecommendationItem(
                        candidate_id=f"tmdb:movie:{index}", rank=1, title=f"Title {index}"
                    )
                ],
            )
        )

    history = repository.load_board_history(profile_id)
    assert [item.run_id for item in history] == ["run-4", "run-3", "run-2"]
    assert history[0].recommendations[0].title == "Title 4"
    assert repository._board_history_key(profile_id) in repository.full_profile_storage_keys(
        profile_id
    )

    repository.reset_all_profile_data(profile_id)
    assert repository.load_board_history(profile_id) == []
