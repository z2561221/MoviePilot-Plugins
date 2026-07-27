"""确认态偏好记忆、墓碑、重放和 CAS 仓储测试。"""

import copy
import importlib
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_memory_repository_test"
PROFILE_ID = "emby:home:user-1"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

memory_module = importlib.import_module(f"{PACKAGE_NAME}.model.memory")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")

PreferenceMemory = memory_module.PreferenceMemory
PreferenceMemoryItem = memory_module.PreferenceMemoryItem
AgentRankRepository = repository_module.AgentRankRepository


class FakePlugin:
    """用内存字典模拟 MoviePilot 插件数据接口与单次失败注入。"""

    def __init__(self, data=None, fail_once_on_key=""):
        self.data = copy.deepcopy(dict(data or {}))
        self.fail_once_on_key = str(fail_once_on_key or "")
        self.failed = False

    def get_data(self, key=None):
        """返回持久化值的独立副本。"""
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """保存独立副本，并可在指定键首次写入时模拟故障。"""
        if key == self.fail_once_on_key and not self.failed:
            self.failed = True
            raise RuntimeError("injected memory save failure")
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除指定键。"""
        self.data.pop(key, None)


def _item(
    item_id,
    sequence,
    *,
    category="tag",
    value="悬疑",
    polarity="positive",
    tombstone=False,
    supersedes=(),
):
    """构造一条有明确用户反馈证据的确认态记忆项。"""
    return PreferenceMemoryItem(
        item_id=item_id,
        category=category,
        value=value,
        polarity=polarity,
        strength=0.8,
        certainty=0.9,
        evidence_refs=(f"feedback:{sequence}",),
        source_event_sequence=sequence,
        created_at=f"2026-07-28T00:00:{sequence:02d}+00:00",
        status="archived" if tombstone else "active",
        tombstone=tombstone,
        supersedes=tuple(supersedes),
    )


def _apply(memory, item, expected_revision=None):
    """按记忆当前 revision 应用单项确认投影。"""
    return memory.project(
        [item],
        expected_revision=(
            memory.memory_revision
            if expected_revision is None
            else expected_revision
        ),
        source_event_sequence=item.source_event_sequence,
    )


def test_memory_item_round_trip_preserves_confirmed_evidence_contract():
    """记忆项完整保留类别、极性、强度、确定性、证据和谱系字段。"""
    item = _item("memory-1", 1)

    restored = PreferenceMemoryItem.from_dict(item.to_dict())

    assert restored == item
    assert restored.preference_key == "tag:悬疑"
    with pytest.raises(ValueError, match="confirmed evidence"):
        PreferenceMemoryItem(
            item_id="invalid",
            category="tag",
            value="悬疑",
            polarity="positive",
            strength=0.8,
            certainty=0.9,
            evidence_refs=(),
            source_event_sequence=1,
            created_at="2026-07-28T00:00:01+00:00",
        )


def test_tombstone_survives_replay_and_blocks_unlinked_profile_rebuild():
    """删除墓碑经完整重放仍是当前状态，无谱系的新画像标签不能复活。"""
    first = _apply(PreferenceMemory.empty(PROFILE_ID), _item("memory-1", 1))
    assert first.applied is True
    deleted = _apply(
        first.memory,
        _item(
            "memory-2",
            2,
            tombstone=True,
            supersedes=("memory-1",),
        ),
    )

    assert deleted.applied is True
    assert deleted.memory.memory_revision == 2
    assert deleted.memory.active_items() == ()
    assert deleted.memory.is_tombstoned("tag", "悬疑") is True
    assert PreferenceMemory.replay(PROFILE_ID, deleted.memory.items) == deleted.memory

    rebuild = _apply(deleted.memory, _item("memory-rebuild", 3))
    assert rebuild.applied is False
    assert rebuild.status == "superseded"
    assert rebuild.reason == "missing_latest_supersedes"
    assert rebuild.memory == deleted.memory
    assert rebuild.memory.is_tombstoned("tag", "悬疑") is True


def test_explicit_restore_must_supersede_current_tombstone():
    """只有显式替代当前墓碑的新确认项才能恢复已删除偏好。"""
    active = _apply(PreferenceMemory.empty(PROFILE_ID), _item("memory-1", 1)).memory
    deleted = _apply(
        active,
        _item("memory-2", 2, tombstone=True, supersedes=("memory-1",)),
    ).memory

    restored = _apply(
        deleted,
        _item("memory-3", 3, supersedes=("memory-2",)),
    )

    assert restored.applied is True
    assert restored.memory.memory_revision == 3
    assert restored.memory.is_tombstoned("tag", "悬疑") is False
    assert [item.item_id for item in restored.memory.active_items()] == ["memory-3"]
    assert [item.status for item in restored.memory.items] == [
        "superseded",
        "superseded",
        "active",
    ]


def test_stale_sequence_and_revision_conflicts_never_overwrite_new_memory():
    """晚到事件和旧 revision 回调只返回 superseded，当前记忆逐字段不变。"""
    current = _apply(PreferenceMemory.empty(PROFILE_ID), _item("memory-1", 5)).memory
    snapshot = current.to_dict()

    stale_sequence = current.project(
        [_item("memory-old", 4, value="喜剧")],
        expected_revision=1,
        source_event_sequence=4,
    )
    stale_revision = current.project(
        [_item("memory-late", 6, value="科幻")],
        expected_revision=0,
        source_event_sequence=6,
    )

    assert stale_sequence.status == "superseded"
    assert stale_sequence.reason == "stale_event_sequence"
    assert stale_revision.status == "superseded"
    assert stale_revision.reason == "memory_revision_conflict"
    assert stale_sequence.memory.to_dict() == snapshot
    assert stale_revision.memory.to_dict() == snapshot


def test_one_event_projects_multiple_preferences_as_one_revision():
    """同一确认事件可原子写入多个不同偏好，但 revision 只增加一次。"""
    memory = PreferenceMemory.empty(PROFILE_ID)
    result = memory.project(
        [
            _item("memory-tag", 7, category="tag", value="悬疑"),
            _item("memory-pace", 7, category="pace", value="紧凑"),
        ],
        expected_revision=0,
        source_event_sequence=7,
    )

    assert result.applied is True
    assert result.memory.memory_revision == 1
    assert result.memory.last_event_sequence == 7
    assert PreferenceMemory.replay(PROFILE_ID, result.memory.items) == result.memory


def test_repository_cas_allows_only_one_concurrent_projection():
    """并发使用同一 expected_revision 时只有一项应用，其余均被标记 superseded。"""
    plugin = FakePlugin()
    repositories = [AgentRankRepository(plugin) for _ in range(4)]

    def project(index):
        return repositories[index % len(repositories)].project_preference_memory(
            PROFILE_ID,
            [_item(f"memory-{index}", 1, value=f"标签{index}")],
            expected_revision=0,
            source_event_sequence=1,
        )

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(project, range(100)))

    memory = repositories[0].load_preference_memory(PROFILE_ID)
    assert sum(result.applied for result in results) == 1
    assert sum(result.status == "superseded" for result in results) == 99
    assert memory.memory_revision == 1
    assert len(memory.active_items()) == 1


def test_repository_write_failure_restores_previous_memory():
    """确认态记忆写入失败时恢复旧 revision 和墓碑历史。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    first = repository.project_preference_memory(
        PROFILE_ID,
        [_item("memory-1", 1)],
        expected_revision=0,
        source_event_sequence=1,
    )
    before = copy.deepcopy(plugin.data)
    memory_key = repository._profile_key("preference_memory", PROFILE_ID)
    plugin.fail_once_on_key = memory_key

    with pytest.raises(RuntimeError, match="injected memory save failure"):
        repository.project_preference_memory(
            PROFILE_ID,
            [_item("memory-2", 2, tombstone=True, supersedes=("memory-1",))],
            expected_revision=first.memory.memory_revision,
            source_event_sequence=2,
        )

    assert plugin.data == before
    assert repository.load_preference_memory(PROFILE_ID) == first.memory


def test_corrupt_memory_is_preserved_and_cannot_be_overwritten():
    """损坏的新记忆保持原值，投影失败且留下恢复证据。"""
    probe = AgentRankRepository(FakePlugin())
    memory_key = probe._profile_key("preference_memory", PROFILE_ID)
    corrupt = {"profile_id": PROFILE_ID, "memory_revision": "broken"}
    plugin = FakePlugin({memory_key: corrupt})
    repository = AgentRankRepository(plugin)

    with pytest.raises(ValueError, match="memory is corrupt"):
        repository.project_preference_memory(
            PROFILE_ID,
            [_item("memory-1", 1)],
            expected_revision=0,
            source_event_sequence=1,
        )

    assert plugin.data[memory_key] == corrupt
    assert plugin.data[repository.recovery_log_key][-1]["key"] == memory_key


def test_new_memory_key_is_profile_isolated_and_leaves_legacy_keys_untouched():
    """确认记忆只写新命名空间，不迁移或修改现有画像、标签和榜单。"""
    legacy = {
        "profile_snapshot:profile:emby%3Ahome%3Auser-1": {"summary": "old"},
        "profile_preferences:profile:emby%3Ahome%3Auser-1": {
            "archived_tags": ["悬疑"]
        },
        "recommendation_board:profile:emby%3Ahome%3Auser-1": {"run_id": "old"},
    }
    plugin = FakePlugin(legacy)
    repository = AgentRankRepository(plugin)

    repository.project_preference_memory(
        PROFILE_ID,
        [_item("memory-home", 1)],
        expected_revision=0,
        source_event_sequence=1,
    )
    repository.project_preference_memory(
        "emby:remote:user-1",
        [_item("memory-remote", 1, value="喜剧")],
        expected_revision=0,
        source_event_sequence=1,
    )

    assert {key: plugin.data[key] for key in legacy} == legacy
    assert repository.load_preference_memory(PROFILE_ID).items[0].item_id == (
        "memory-home"
    )
    assert repository.load_preference_memory("emby:remote:user-1").items[0].item_id == (
        "memory-remote"
    )
