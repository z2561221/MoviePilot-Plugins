"""旧数据兼容、新 schema 增量迁移与失败回滚测试。"""

import copy
import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_storage_migration_test"
PROFILE_ID = "emby:home:user-1"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
migration_module = importlib.import_module(f"{PACKAGE_NAME}.service.storage_migration")
lifecycle_module = importlib.import_module(f"{PACKAGE_NAME}.service.lifecycle")

AgentRankRepository = repository_module.AgentRankRepository
AgentRankStorageMigrationService = migration_module.AgentRankStorageMigrationService
initialize_plugin = lifecycle_module.initialize_plugin
stop_plugin = lifecycle_module.stop_plugin


class FakePlugin:
    """模拟 MoviePilot 数据接口、生命周期字段和单次写失败。"""

    def __init__(self, data=None, fail_once_on_key=""):
        self.data = copy.deepcopy(dict(data or {}))
        self.fail_once_on_key = str(fail_once_on_key or "")
        self.failed = False
        self._runtime = None
        self._repository = None
        self._config = {}
        self._enabled = False
        self._enablement = {}
        self._migration_status = {}
        self._playback_service = None
        self._emby_access = None
        self.saved_config = None

    def get_data(self, key=None):
        """返回持久化值的独立副本。"""
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """保存独立副本，并可在指定键首次写入时模拟故障。"""
        if key == self.fail_once_on_key and not self.failed:
            self.failed = True
            raise RuntimeError("injected migration save failure")
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除指定键。"""
        self.data.pop(key, None)

    def stop_service(self):
        """按正式生命周期停止测试运行时。"""
        stop_plugin(self)

    def update_config(self, config=None):
        """记录一次性配置复位结果。"""
        self.saved_config = dict(config or {})


def _legacy_fixture(repository):
    """构造画像、榜单、归档、标签和运行历史的旧 schema 固件。"""
    return {
        repository._profile_key("profile_snapshot", PROFILE_ID): {
            "profile_id": PROFILE_ID,
            "username": "Alice",
            "summary": "旧画像摘要",
            "tags": ["悬疑", "群像"],
            "negative_tags": ["过度煽情"],
            "playback_count": 12,
            "playback_fingerprint": "playback-old",
            "filters": {"genre_ids": [9648]},
            "ranking_tags": ["反转"],
            "run_id": "run-old",
            "schema_version": 3,
        },
        repository._profile_key("recommendation_board", PROFILE_ID): {
            "profile_id": PROFILE_ID,
            "username": "Alice",
            "run_id": "run-old",
            "status": "success",
            "recommendations": [
                {
                    "candidate_id": "tmdb:tv:100",
                    "rank": 1,
                    "title": "旧榜单作品",
                    "tmdb_id": 100,
                    "reason": "旧推荐理由",
                    "summary": "旧简介",
                }
            ],
            "schema_version": 1,
        },
        repository._profile_key("archive", PROFILE_ID): {
            "profile_id": PROFILE_ID,
            "username": "Alice",
            "entries": [
                {
                    "candidate_id": "tmdb:tv:200",
                    "original_rank": 2,
                    "reason": "ignored",
                    "recommendation": {"title": "旧忽略作品"},
                }
            ],
            "schema_version": 1,
        },
        repository._profile_key("profile_preferences", PROFILE_ID): {
            "profile_id": PROFILE_ID,
            "username": "Alice",
            "custom_tags": ["烧脑"],
            "custom_negative_tags": ["流水账"],
            "suppressed_tags": ["悬疑"],
            "suppressed_negative_tags": ["过度煽情"],
            "schema_version": 2,
        },
        repository._profile_key("run_history", PROFILE_ID): [
            {
                "profile_id": PROFILE_ID,
                "username": "Alice",
                "run_id": "run-old",
                "status": "success",
                "message": "旧运行记录",
                "metrics": {"agent_calls": 2},
                "schema_version": 1,
            }
        ],
    }


def test_migration_preserves_old_fixture_field_by_field_and_creates_empty_schemas():
    """有效旧固件原值不变，读取兼容且只新增空反馈索引与空确认记忆。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    legacy = _legacy_fixture(repository)
    plugin.data.update(copy.deepcopy(legacy))
    before = copy.deepcopy(plugin.data)
    service = AgentRankStorageMigrationService(repository)

    first = service.migrate_profiles([PROFILE_ID])
    second = service.migrate_profiles([PROFILE_ID])

    assert first.status == "ready"
    assert first.profiles[0].created_keys == [
        "feedback_event_index",
        "preference_memory",
    ]
    assert first.profiles[0].observed == {
        "profile_present": True,
        "board_present": True,
        "archive_entry_count": 1,
        "custom_tag_count": 1,
        "custom_negative_tag_count": 1,
        "archived_tag_count": 1,
        "archived_negative_tag_count": 1,
        "run_history_count": 1,
    }
    assert second.profiles[0].created_keys == []
    assert {key: plugin.data[key] for key in before} == before

    profile = repository.load_profile(PROFILE_ID)
    board = repository.load_board(PROFILE_ID)
    archive = repository.load_archive(PROFILE_ID)
    preferences = repository.load_profile_preferences(PROFILE_ID)
    history = repository.load_run_history(PROFILE_ID)
    assert profile.summary == "旧画像摘要"
    assert profile.tags == ["悬疑", "群像"]
    assert board.recommendations[0].source_ids["tmdb"] == "100"
    assert archive.entries[0].recommendation["title"] == "旧忽略作品"
    assert preferences.archived_tags == ["悬疑"]
    assert preferences.archived_negative_tags == ["过度煽情"]
    assert history[0].metrics == {"agent_calls": 2}

    index_key = repository._feedback_index_key(PROFILE_ID)
    memory_key = repository._profile_key("preference_memory", PROFILE_ID)
    assert plugin.data[index_key]["next_sequence"] == 1
    assert plugin.data[index_key]["segments"] == []
    assert plugin.data[memory_key]["memory_revision"] == 0
    assert plugin.data[memory_key]["items"] == []


def test_migration_failure_rolls_back_all_new_keys_and_keeps_old_fixture():
    """第二个新键写失败时回滚首键，旧数据不丢且状态和恢复日志可见。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    legacy = _legacy_fixture(repository)
    plugin.data.update(copy.deepcopy(legacy))
    before = copy.deepcopy(plugin.data)
    memory_key = repository._profile_key("preference_memory", PROFILE_ID)
    plugin.fail_once_on_key = memory_key

    report = AgentRankStorageMigrationService(repository).migrate_profiles(
        [PROFILE_ID]
    )

    assert report.status == "partial_failed"
    assert report.failure_count == 1
    assert report.profiles[0].error == "RuntimeError"
    assert {key: plugin.data[key] for key in before} == before
    assert repository._feedback_index_key(PROFILE_ID) not in plugin.data
    assert memory_key not in plugin.data
    assert plugin.data[repository.recovery_log_key][-1]["action"] == (
        "profile_storage_migration_failed"
    )


def test_corrupt_existing_new_schema_is_preserved_and_reported_failed():
    """已有损坏新键不会被空 schema 覆盖，迁移报告只暴露错误类型。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    index_key = repository._feedback_index_key(PROFILE_ID)
    corrupt = {"profile_id": PROFILE_ID, "next_sequence": "broken"}
    plugin.data[index_key] = copy.deepcopy(corrupt)

    report = AgentRankStorageMigrationService(repository).migrate_profiles(
        [PROFILE_ID]
    )

    assert report.status == "partial_failed"
    assert report.profiles[0].error == "ValueError"
    assert plugin.data[index_key] == corrupt
    assert repository._profile_key("preference_memory", PROFILE_ID) not in plugin.data


def test_lifecycle_runs_migration_and_surfaces_failure_without_rewriting_config():
    """插件初始化执行增量迁移，失败进入安全状态摘要和临时校验错误。"""
    plugin = FakePlugin()
    probe = AgentRankRepository(plugin)
    memory_key = probe._profile_key("preference_memory", PROFILE_ID)
    plugin.fail_once_on_key = memory_key

    def runtime_factory(plugin_arg, config_arg):
        plugin_arg._repository = AgentRankRepository(plugin_arg)
        runtime = SimpleNamespace(config=config_arg)
        runtime.stop = lambda: None
        return runtime

    initialize_plugin(
        plugin,
        {
            "enabled": False,
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
        },
        runtime_factory=runtime_factory,
    )

    assert plugin._migration_status["status"] == "partial_failed"
    assert plugin._migration_status["failure_count"] == 1
    assert any("迁移状态" in error for error in plugin._config["_validation_errors"])
    assert "_validation_errors" not in (plugin.saved_config or {})


def test_real_runtime_runs_migration_before_legacy_board_repairs():
    """真实依赖组装必须先观测和迁移，再允许旧榜单修复产生写副作用。"""
    source = (PLUGIN_DIR / "service" / "runtime.py").read_text(encoding="utf-8")
    migration_call = ").migrate_profiles(profile_ids).to_dict()"
    poster_repair_call = (
        "BoardPosterRepairService(repository, media_adapter).repair_profiles(profile_ids)"
    )
    source_repair_call = (
        "BoardSourceRepairService(repository, media_adapter).repair_profiles(profile_ids)"
    )

    assert source.index(migration_call) < source.index(poster_repair_call)
    assert source.index(migration_call) < source.index(source_repair_call)
