"""反馈事件分段账本的幂等、并发与恢复测试。"""

import copy
import importlib
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_feedback_repository_test"
PROFILE_ID = "emby:home:user-1"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

feedback_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")

FeedbackEvent = feedback_module.FeedbackEvent
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
            raise RuntimeError("injected save failure")
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除指定键。"""
        self.data.pop(key, None)


def _event(idempotency_key, *, profile_id=PROFILE_ID, kind="like", comment=""):
    """构造一条尚未分配序号的反馈事件。"""
    return FeedbackEvent(
        profile_id=profile_id,
        kind=kind,
        candidate_id="tmdb:tv:100",
        run_id="run-1",
        analysis_id="analysis-1",
        comment=comment,
        created_by_mp_user_id="7",
        idempotency_key=idempotency_key,
        supersedes="event-old" if kind == "correction" else "",
    )


def test_feedback_event_round_trip_preserves_locked_contract_fields():
    """持久化事件完整保留计划锁定字段并拒绝待写入字典。"""
    stored = _event("request-1", kind="correction", comment="这部作品不是我喜欢的节奏").assign_persistence(
        event_id="event-1",
        sequence=3,
        created_at="2026-07-28T00:00:00+00:00",
    )

    restored = FeedbackEvent.from_dict(stored.to_dict())

    assert restored == stored
    assert set(restored.to_dict()) == {
        "event_id",
        "profile_id",
        "sequence",
        "kind",
        "candidate_id",
        "run_id",
        "analysis_id",
        "comment",
        "created_by_mp_user_id",
        "created_at",
        "idempotency_key",
        "supersedes",
        "status",
        "schema_version",
    }
    with pytest.raises(ValueError, match="positive sequence"):
        FeedbackEvent.from_dict(_event("draft").to_dict())


def test_one_hundred_concurrent_duplicates_create_one_business_event():
    """100 个并发重复回调返回同一事件且账本只增加一次。"""
    plugin = FakePlugin()
    repositories = [AgentRankRepository(plugin) for _ in range(4)]

    def append(index):
        return repositories[index % len(repositories)].append_feedback_event(
            _event("same-callback", comment=f"attempt-{index}")
        )

    with ThreadPoolExecutor(max_workers=24) as executor:
        results = list(executor.map(append, range(100)))

    events = repositories[0].load_feedback_events(PROFILE_ID)
    assert len(events) == 1
    assert {result.event.event_id for result in results} == {events[0].event_id}
    assert {result.event.sequence for result in results} == {1}
    assert {result.event.comment for result in results} == {events[0].comment}
    assert sum(result.created for result in results) == 1
    assert repositories[1].load_feedback_event(PROFILE_ID, "same-callback") == events[0]


def test_concurrent_unique_events_receive_strictly_increasing_sequences():
    """同一 profile 的并发不同事件获得无重复、无空洞的单调序号。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin, feedback_segment_size=17)

    with ThreadPoolExecutor(max_workers=20) as executor:
        list(
            executor.map(
                lambda index: repository.append_feedback_event(
                    _event(f"request-{index}")
                ),
                range(100),
            )
        )

    events = repository.load_feedback_events(PROFILE_ID)
    assert [event.sequence for event in events] == list(range(1, 101))
    assert len({event.event_id for event in events}) == 100
    assert len(
        [key for key in plugin.data if key.startswith("feedback_event_segment:")]
    ) == 6


def test_feedback_events_rotate_segments_and_support_cursor_reads():
    """小分段上限会轮换段，游标和 limit 仍按全局序号读取。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin, feedback_segment_size=2)
    for index in range(5):
        repository.append_feedback_event(_event(f"request-{index}"))

    index_key = repository._feedback_index_key(PROFILE_ID)
    index = plugin.data[index_key]
    assert [item["event_count"] for item in index["segments"]] == [2, 2, 1]
    assert index["next_sequence"] == 6
    assert [
        event.sequence
        for event in repository.load_feedback_events(
            PROFILE_ID, after_sequence=2, limit=2
        )
    ] == [3, 4]


def test_feedback_ledger_is_profile_isolated_and_leaves_legacy_data_untouched():
    """新账本只创建反馈键，不迁移或改写现有画像、榜单、归档和历史。"""
    legacy = {
        "profile_snapshot:profile:emby%3Ahome%3Auser-1": {"summary": "old"},
        "recommendation_board:profile:emby%3Ahome%3Auser-1": {"run_id": "old"},
        "archive:profile:emby%3Ahome%3Auser-1": {"entries": ["old"]},
        "run_history:profile:emby%3Ahome%3Auser-1": [{"run_id": "old"}],
    }
    plugin = FakePlugin(legacy)
    repository = AgentRankRepository(plugin)

    home = repository.append_feedback_event(_event("home")).event
    remote = repository.append_feedback_event(
        _event("remote", profile_id="emby:remote:user-1")
    ).event

    assert repository.load_feedback_events(PROFILE_ID) == [home]
    assert repository.load_feedback_events("emby:remote:user-1") == [remote]
    assert {key: plugin.data[key] for key in legacy} == legacy


def test_index_write_failure_rolls_back_index_and_segment():
    """索引写入失败时恢复写前索引和事件段，不留下半事件。"""
    probe = AgentRankRepository(FakePlugin())
    index_key = probe._feedback_index_key(PROFILE_ID)
    plugin = FakePlugin(fail_once_on_key=index_key)
    repository = AgentRankRepository(plugin)

    with pytest.raises(RuntimeError, match="injected save failure"):
        repository.append_feedback_event(_event("request-failed"))

    assert index_key not in plugin.data
    assert not any(key.startswith("feedback_event_segment:") for key in plugin.data)
    assert repository.load_feedback_events(PROFILE_ID) == []


def test_existing_segment_is_restored_when_later_index_update_fails():
    """已有段追加后索引失败时，段与索引都恢复到上一条可信事件。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin, feedback_segment_size=10)
    first = repository.append_feedback_event(_event("request-1")).event
    index_key = repository._feedback_index_key(PROFILE_ID)
    before = copy.deepcopy(plugin.data)
    plugin.fail_once_on_key = index_key

    with pytest.raises(RuntimeError, match="injected save failure"):
        repository.append_feedback_event(_event("request-2"))

    assert {
        key: value
        for key, value in plugin.data.items()
        if key != repository.recovery_log_key
    } == before
    assert repository.load_feedback_events(PROFILE_ID) == [first]
    assert repository.load_feedback_event(PROFILE_ID, "request-2") is None


def test_segment_write_failure_does_not_advance_existing_index():
    """新段写入失败时不推进 next_sequence，也不生成幂等指针。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin, feedback_segment_size=1)
    first = repository.append_feedback_event(_event("request-1")).event
    second_segment_key = repository._feedback_segment_key(PROFILE_ID, 2)
    before = copy.deepcopy(plugin.data)
    plugin.fail_once_on_key = second_segment_key

    with pytest.raises(RuntimeError, match="injected save failure"):
        repository.append_feedback_event(_event("request-2"))

    assert {
        key: value
        for key, value in plugin.data.items()
        if key != repository.recovery_log_key
    } == before
    assert repository.load_feedback_events(PROFILE_ID) == [first]
    assert second_segment_key not in plugin.data


def test_corrupt_index_is_preserved_and_cannot_be_overwritten_by_append():
    """损坏的新索引保持原值，追加必须失败而不能把事实账本清空重建。"""
    probe = AgentRankRepository(FakePlugin())
    index_key = probe._feedback_index_key(PROFILE_ID)
    corrupt = {"profile_id": PROFILE_ID, "next_sequence": "broken"}
    plugin = FakePlugin({index_key: corrupt})
    repository = AgentRankRepository(plugin)

    with pytest.raises(ValueError, match="index is corrupt"):
        repository.append_feedback_event(_event("request-1"))

    assert plugin.data[index_key] == corrupt
    assert plugin.data[repository.recovery_log_key][-1]["key"] == index_key
    assert not any(key.startswith("feedback_event_segment:") for key in plugin.data)


def test_orphan_segment_is_preserved_instead_of_silently_overwritten():
    """索引缺失但段存在时拒绝重建，保留掉电后的待恢复事实。"""
    probe = AgentRankRepository(FakePlugin())
    segment_key = probe._feedback_segment_key(PROFILE_ID, 1)
    orphan = {"unexpected": "old feedback facts"}
    plugin = FakePlugin({segment_key: orphan})
    repository = AgentRankRepository(plugin)

    with pytest.raises(ValueError, match="unindexed"):
        repository.append_feedback_event(_event("request-1"))

    assert plugin.data[segment_key] == orphan
    assert plugin.data[repository.recovery_log_key][-1]["action"] == (
        "preserved_orphan_feedback_segment"
    )
