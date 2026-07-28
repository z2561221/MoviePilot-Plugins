"""数据保留、脱敏导出和分级重置的边界与故障恢复测试。"""

import copy
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_data_lifecycle_test"
PROFILE_ID = "emby:home:user-1"
OTHER_PROFILE_ID = "emby:home:user-2"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

archive_module = importlib.import_module(f"{PACKAGE_NAME}.model.archive")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
snapshot_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate_snapshot")
feedback_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback")
memory_module = importlib.import_module(f"{PACKAGE_NAME}.model.memory")
playback_module = importlib.import_module(f"{PACKAGE_NAME}.model.playback")
preferences_module = importlib.import_module(
    f"{PACKAGE_NAME}.model.profile_preferences"
)
profile_module = importlib.import_module(f"{PACKAGE_NAME}.model.profile")
run_module = importlib.import_module(f"{PACKAGE_NAME}.model.run")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
lifecycle_module = importlib.import_module(f"{PACKAGE_NAME}.service.data_lifecycle")

ArchiveEntry = archive_module.ArchiveEntry
ArchiveFeedback = archive_module.ArchiveFeedback
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
Candidate = candidate_module.Candidate
CandidateSnapshot = snapshot_module.CandidateSnapshot
FeedbackEvent = feedback_module.FeedbackEvent
PreferenceMemoryItem = memory_module.PreferenceMemoryItem
PlaybackSnapshot = playback_module.PlaybackSnapshot
ProfilePreferences = preferences_module.ProfilePreferences
UserProfile = profile_module.UserProfile
RecommendationRun = run_module.RecommendationRun
AgentRankRepository = repository_module.AgentRankRepository
DataLifecycleError = lifecycle_module.DataLifecycleError
DataLifecycleService = lifecycle_module.DataLifecycleService


class FakePlugin:
    """提供独立副本、单次保存/删除失败和宿主外部状态的内存插件。"""

    def __init__(self):
        self.data = {}
        self.fail_once_on_save = ""
        self.fail_once_on_delete = ""
        self.failed_save = False
        self.failed_delete = False
        self.external_subscriptions = ["tmdb:tv:900"]
        self.external_library = ["tmdb:movie:901"]
        self._config = {"enabled": True, "private_runtime_key": "must-stay"}

    def get_data(self, key=None):
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        if key == self.fail_once_on_save and not self.failed_save:
            self.failed_save = True
            raise RuntimeError("injected save failure")
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        if key == self.fail_once_on_delete and not self.failed_delete:
            self.failed_delete = True
            raise RuntimeError("injected delete failure")
        self.data.pop(key, None)


def _snapshot(run_id, index=1, profile_id=PROFILE_ID):
    return CandidateSnapshot.create(
        profile_id=profile_id,
        run_id=run_id,
        profile_version={"run_id": run_id, "schema_version": 6},
        retrieval_plan={"media_types": ["tv"]},
        candidates=[
            Candidate(
                candidate_id=f"tmdb:tv:{100 + index}",
                title=f"候选{index}",
                media_type="tv",
                source_ids={"tmdb": str(100 + index)},
            )
        ],
        generated_at=f"2026-07-28T00:00:{index:02d}+00:00",
    )


def _feedback(key, index=1):
    return FeedbackEvent(
        profile_id=PROFILE_ID,
        kind="like",
        candidate_id=f"tmdb:tv:{100 + index}",
        run_id=f"run-{index}",
        analysis_id=f"analysis-{index}",
        comment="",
        created_by_mp_user_id="7",
        idempotency_key=key,
    )


def _seed_profile(repository, plugin):
    repository.save_profile(
        UserProfile(
            profile_id=PROFILE_ID,
            username="Alice",
            summary="喜欢悬疑",
            tags=["悬疑"],
            ranking_tags=["推理"],
            run_id="run-1",
        )
    )
    repository.save_board(
        RecommendationBoard(
            profile_id=PROFILE_ID,
            run_id="run-1",
            username="Alice",
            recommendations=[
                RecommendationItem(
                    candidate_id="tmdb:tv:101",
                    rank=1,
                    title="候选1",
                    reason="节奏匹配",
                    summary="完整短句",
                    confidence=0.8,
                    media_type="tv",
                    source_ids={"tmdb": "101"},
                )
            ],
        )
    )
    repository.save_archive(
        ArchiveFeedback(
            profile_id=PROFILE_ID,
            entries=[
                ArchiveEntry(
                    candidate_id="tmdb:tv:102",
                    original_rank=2,
                    recommendation={"private": "must-not-export"},
                )
            ],
        )
    )
    repository.save_profile_preferences(
        ProfilePreferences(
            profile_id=PROFILE_ID,
            custom_tags=["慢热"],
            archived_negative_tags=["误判标签"],
        )
    )
    repository.save_playback_snapshot(
        PlaybackSnapshot(profile_id=PROFILE_ID, source="playback_reporting")
    )
    repository.append_run(
        RecommendationRun(
            profile_id=PROFILE_ID,
            run_id="run-1",
            status="success",
            metrics={"agent_model": "model-a", "agent_calls": 2},
        )
    )
    repository.save_candidate_snapshot(_snapshot("run-1"))
    repository.append_feedback_event(_feedback("feedback-1"))
    repository.project_preference_memory(
        PROFILE_ID,
        [
            PreferenceMemoryItem(
                item_id="memory-1",
                category="tag",
                value="悬疑",
                polarity="positive",
                strength=0.8,
                certainty=0.9,
                evidence_refs=("feedback:1",),
                source_event_sequence=1,
                created_at="2026-07-28T00:00:01+00:00",
            )
        ],
        expected_revision=0,
        source_event_sequence=1,
    )
    plugin.data[repository._learning_key("feedback_queue", PROFILE_ID)] = [
        {"event": "queued"}
    ]
    plugin.data[repository.telegram_sessions_key] = {
        "target": {"profile_id": PROFILE_ID, "token": "private-session"},
        "other": {"profile_id": OTHER_PROFILE_ID, "token": "keep-session"},
    }


def test_candidate_index_is_atomic_and_retention_keeps_latest_snapshots():
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    index_key = repository._candidate_index_key(PROFILE_ID)
    plugin.fail_once_on_save = index_key

    with pytest.raises(RuntimeError, match="injected save failure"):
        repository.save_candidate_snapshot(_snapshot("run-failed", 1))

    assert index_key not in plugin.data
    assert repository._candidate_key("run-failed", PROFILE_ID) not in plugin.data

    plugin.fail_once_on_save = ""
    for index in range(1, 5):
        repository.save_candidate_snapshot(_snapshot(f"run-{index}", index))

    removed = repository.prune_candidate_snapshots(PROFILE_ID, 2)

    assert removed == 2
    assert [
        item["run_id"] for item in repository.candidate_snapshot_references(PROFILE_ID)
    ] == ["run-3", "run-4"]
    assert repository.load_candidate_snapshot_record("run-1", PROFILE_ID) is None
    assert repository.load_candidate_snapshot_record("run-4", PROFILE_ID) is not None


def test_feedback_retention_preserves_monotonic_sequence_after_prefix_prune():
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin, feedback_segment_size=2)
    for index in range(1, 8):
        repository.append_feedback_event(_feedback(f"feedback-{index}", index))

    assert repository.prune_feedback_events(PROFILE_ID, 3) == 4
    assert [event.sequence for event in repository.load_feedback_events(PROFILE_ID)] == [
        5,
        6,
        7,
    ]
    index = repository._load_feedback_index(PROFILE_ID, strict=True)
    assert index.retained_from_sequence == 5
    assert index.next_sequence == 8

    appended = repository.append_feedback_event(_feedback("feedback-8", 8)).event
    assert appended.sequence == 8
    assert repository.load_feedback_event(PROFILE_ID, "feedback-1") is None


def test_repository_enforces_configured_retention_after_each_new_write():
    """运行期仓储写入超过上限时立即裁剪，而不是等到下次重启。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(
        plugin,
        feedback_segment_size=2,
        candidate_snapshot_limit=2,
        feedback_event_limit=3,
    )
    for index in range(1, 6):
        repository.save_candidate_snapshot(_snapshot(f"run-{index}", index))
        repository.append_feedback_event(_feedback(f"feedback-{index}", index))

    assert [
        item["run_id"] for item in repository.candidate_snapshot_references(PROFILE_ID)
    ] == ["run-4", "run-5"]
    assert [event.sequence for event in repository.load_feedback_events(PROFILE_ID)] == [
        3,
        4,
        5,
    ]


def test_export_uses_whitelists_and_redacts_addresses_and_credentials():
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed_profile(repository, plugin)
    profile = repository.load_profile(PROFILE_ID)
    profile.summary = "Authorization: Bearer topsecret http://192.168.1.2:8096"
    repository.save_profile(profile)
    board = repository.load_board(PROFILE_ID)
    board.recommendations[0].reason = "Cookie=session-secret https://emby.local/item"
    board.recommendations[0].poster_path = "http://private/poster.jpg"
    repository.save_board(board)
    run_key = repository._profile_key("run_history", PROFILE_ID)
    plugin.data[run_key][0]["errors"] = ["api_key=supersecret"]
    plugin.data[run_key][0]["metrics"].update(
        {
            "api_key": "supersecret",
            "endpoint": "http://private",
            "agent_model": "m",
            "policy_version": "policy-v1-safe",
            "policy_memory_revision": 3,
            "policy_algorithm_version": 1,
            "policy_evidence_count": 8,
        }
    )
    first_segment = repository._feedback_segment_key(PROFILE_ID, 1)
    plugin.data[first_segment]["events"][0]["comment"] = "token=feedback-secret"

    exported = DataLifecycleService(repository).export_profile(PROFILE_ID)
    serialized = json.dumps(exported, ensure_ascii=False).casefold()

    for forbidden in (
        "topsecret",
        "session-secret",
        "supersecret",
        "feedback-secret",
        "192.168.1.2",
        "emby.local",
        "http://",
        "poster_path",
        "recommendation\":",
        "errors\":",
        "api_key\":",
        "endpoint\":",
        "raw_chain_of_thought",
    ):
        assert forbidden not in serialized
    assert exported["run_history"][0]["metrics"]["agent_model"] == "m"
    assert exported["run_history"][0]["metrics"]["policy_version"] == (
        "policy-v1-safe"
    )
    assert exported["run_history"][0]["metrics"]["policy_memory_revision"] == 3
    assert exported["board"]["recommendations"][0]["candidate_id"] == "tmdb:tv:101"


def test_learning_reset_preserves_current_outputs_and_host_data():
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed_profile(repository, plugin)
    before = copy.deepcopy(plugin.data)
    service = DataLifecycleService(repository)

    with pytest.raises(DataLifecycleError, match="明确确认"):
        service.reset_learning(PROFILE_ID, False)
    assert plugin.data == before

    result = service.reset_learning(PROFILE_ID, True)

    assert result["mode"] == "learning"
    assert repository.load_profile(PROFILE_ID) is not None
    assert repository.load_board(PROFILE_ID) is not None
    assert repository.load_archive(PROFILE_ID).entries
    assert repository.load_profile_preferences(PROFILE_ID).custom_tags == ["慢热"]
    assert repository.load_playback_snapshot(PROFILE_ID) is not None
    assert repository.load_run_history(PROFILE_ID)
    assert repository.load_candidate_snapshot_record("run-1", PROFILE_ID) is not None
    assert repository.load_feedback_events(PROFILE_ID) == []
    assert repository.load_preference_memory(PROFILE_ID).memory_revision == 0
    assert repository._learning_key("feedback_queue", PROFILE_ID) not in plugin.data
    assert plugin.external_subscriptions == ["tmdb:tv:900"]
    assert plugin.external_library == ["tmdb:movie:901"]


def test_learning_reset_failure_rolls_back_every_touched_key():
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed_profile(repository, plugin)
    before = copy.deepcopy(plugin.data)
    plugin.fail_once_on_save = repository._profile_key("preference_memory", PROFILE_ID)

    with pytest.raises(RuntimeError, match="injected save failure"):
        repository.reset_learning_data(PROFILE_ID)

    comparable = {
        key: value
        for key, value in plugin.data.items()
        if key != repository.recovery_log_key
    }
    assert comparable == before


def test_full_reset_requires_bound_token_and_never_touches_host_state():
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed_profile(repository, plugin)
    service = DataLifecycleService(repository)

    prepared = service.prepare_full_reset(PROFILE_ID, "mp-user:7")
    token = prepared["confirmation_token"]
    stored = plugin.data[repository._confirmation_key(PROFILE_ID)]
    assert token not in json.dumps(stored)
    assert len(stored["token_hash"]) == 64

    with pytest.raises(DataLifecycleError, match="不属于当前用户"):
        service.reset_full(PROFILE_ID, "mp-user:8", token)
    with pytest.raises(DataLifecycleError, match="不正确"):
        service.reset_full(PROFILE_ID, "mp-user:7", "wrong-token")

    result = service.reset_full(PROFILE_ID, "mp-user:7", token)

    assert result["mode"] == "full"
    assert all(key not in plugin.data for key in repository.full_profile_storage_keys(PROFILE_ID))
    assert plugin.data[repository.telegram_sessions_key] == {
        "other": {"profile_id": OTHER_PROFILE_ID, "token": "keep-session"}
    }
    assert plugin._config["private_runtime_key"] == "must-stay"
    assert plugin.external_subscriptions == ["tmdb:tv:900"]
    assert plugin.external_library == ["tmdb:movie:901"]


def test_full_reset_delete_failure_restores_profile_and_confirmation():
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed_profile(repository, plugin)
    service = DataLifecycleService(repository)
    prepared = service.prepare_full_reset(PROFILE_ID, "mp-user:7")
    before = copy.deepcopy(plugin.data)
    plugin.fail_once_on_delete = repository._profile_key("archive", PROFILE_ID)

    with pytest.raises(RuntimeError, match="injected delete failure"):
        repository.reset_all_profile_data(PROFILE_ID)

    comparable = {
        key: value
        for key, value in plugin.data.items()
        if key != repository.recovery_log_key
    }
    assert comparable == before
    assert repository.load_reset_confirmation(PROFILE_ID) is not None
    assert prepared["confirmation_token"] not in json.dumps(plugin.data)


def test_expired_full_reset_confirmation_is_consumed_without_deleting_data():
    """过期令牌只清理确认记录，不触碰任何 profile 或宿主数据。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed_profile(repository, plugin)
    service = DataLifecycleService(repository)
    prepared = service.prepare_full_reset(PROFILE_ID, "mp-user:7")
    key = repository._confirmation_key(PROFILE_ID)
    plugin.data[key]["expires_at"] = "2000-01-01T00:00:00+00:00"

    with pytest.raises(DataLifecycleError, match="已过期"):
        service.reset_full(
            PROFILE_ID, "mp-user:7", prepared["confirmation_token"]
        )

    assert key not in plugin.data
    assert repository.load_profile(PROFILE_ID) is not None
    assert plugin.external_subscriptions == ["tmdb:tv:900"]
