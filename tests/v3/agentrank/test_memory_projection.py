"""记忆提案确认、CAS 冲突、墓碑恢复和事务回滚测试。"""

import copy
import importlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"
PACKAGE_NAME = "agentrank_memory_projection_test"
PROFILE_ID = "emby:home:user-1"
FIXED_NOW = datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

feedback_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback")
decision_module = importlib.import_module(
    f"{PACKAGE_NAME}.model.feedback_decision"
)
memory_module = importlib.import_module(f"{PACKAGE_NAME}.model.memory")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
projection_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.memory_projection"
)
lifecycle_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.data_lifecycle"
)

FeedbackEvent = feedback_module.FeedbackEvent
MemoryProposal = decision_module.MemoryProposal
MemoryProposalChange = decision_module.MemoryProposalChange
PreferenceMemoryItem = memory_module.PreferenceMemoryItem
AgentRankRepository = repository_module.AgentRankRepository
MemoryConfirmationError = projection_module.MemoryConfirmationError
MemoryProjectionService = projection_module.MemoryProjectionService
DataLifecycleService = lifecycle_module.DataLifecycleService


class FakePlugin:
    """模拟可并发读写并可注入一次保存失败的插件数据接口。"""

    def __init__(self):
        """创建空存储、写锁和失败注入状态。"""
        self.data = {}
        self.lock = threading.RLock()
        self.fail_once_on_key = ""
        self.failed = False

    def get_data(self, key=None):
        """读取指定插件数据的独立副本。"""
        with self.lock:
            return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """保存独立副本或在指定键首次写入时模拟失败。"""
        with self.lock:
            if key == self.fail_once_on_key and not self.failed:
                self.failed = True
                raise RuntimeError("injected projection save failure")
            self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除指定插件数据。"""
        with self.lock:
            self.data.pop(key, None)


def _event(repository, key, candidate_id):
    """创建并持久化一条提案来源反馈事件。"""
    return repository.append_feedback_event(
        FeedbackEvent(
            profile_id=PROFILE_ID,
            kind="like",
            candidate_id=candidate_id,
            run_id="run-1",
            analysis_id="analysis-1",
            comment="喜欢这类作品",
            created_by_mp_user_id="mp-user-1",
            idempotency_key=key,
        )
    ).event


def _change(
    suffix,
    *,
    operation="add",
    category="genre",
    value="科幻",
    polarity="positive",
    certainty=0.8,
    target_ids=(),
):
    """构造一项用户可见的确定性变化预览。"""
    return MemoryProposalChange(
        change_id=f"change:{suffix}",
        operation=operation,
        category=category,
        value=value,
        polarity=polarity,
        certainty=certainty,
        evidence_refs=(f"event:{suffix}",),
        preview=f"拟确认偏好：{value}",
        target_memory_item_ids=tuple(target_ids),
    )


def _proposal(
    repository,
    event,
    *,
    suffix="1",
    expected_revision=0,
    changes=None,
    expires_at=None,
):
    """创建并保存一个待确认记忆提案。"""
    selected_changes = tuple(changes or (_change(suffix),))
    proposal = MemoryProposal(
        proposal_id=f"proposal:{suffix}",
        profile_id=PROFILE_ID,
        event_id=event.event_id,
        event_sequence=event.sequence,
        candidate_id=event.candidate_id,
        understanding_record_id=f"understanding:{suffix}",
        restatement="你明确表达了作品偏好",
        changes=selected_changes,
        evidence_refs=tuple(
            ref
            for change in selected_changes
            for ref in change.evidence_refs
        ),
        impact_preview=tuple(change.preview for change in selected_changes),
        expected_memory_revision=expected_revision,
        created_at=FIXED_NOW.isoformat(),
        expires_at=(expires_at or FIXED_NOW + timedelta(days=30)).isoformat(),
    )
    return repository.append_memory_proposal(proposal)


def _memory_item(
    item_id,
    sequence,
    *,
    category="genre",
    value="科幻",
    polarity="positive",
    strength=0.8,
    certainty=0.8,
    tombstone=False,
    supersedes=(),
):
    """构造测试用确认态记忆或墓碑。"""
    return PreferenceMemoryItem(
        item_id=item_id,
        category=category,
        value=value,
        polarity=polarity,
        strength=strength,
        certainty=certainty,
        evidence_refs=(f"feedback:{sequence}",),
        source_event_sequence=sequence,
        created_at=(FIXED_NOW + timedelta(minutes=sequence)).isoformat(),
        status="archived" if tombstone else "active",
        tombstone=tombstone,
        supersedes=tuple(supersedes),
    )


def test_confirm_projects_once_and_persists_complete_safe_audit():
    """首次确认只增加一个 revision，并保存操作者和投影项身份。"""
    repository = AgentRankRepository(FakePlugin())
    proposal = _proposal(
        repository, _event(repository, "event-1", "tmdb:tv:1")
    )
    service = MemoryProjectionService(
        repository, now_factory=lambda: FIXED_NOW
    )

    result = service.confirm(
        PROFILE_ID, proposal.proposal_id, actor_id="mp-user-1"
    )
    exported = DataLifecycleService(repository).export_profile(PROFILE_ID)
    exported_proposal = exported["memory_proposals"][0]

    assert result.applied is True
    assert result.status == "confirmed"
    assert result.memory.memory_revision == 1
    assert len(result.memory.active_items()) == 1
    assert result.proposal.resolved_by_mp_user_id == "mp-user-1"
    assert result.proposal.resolved_memory_revision == 1
    assert result.proposal.projected_memory_item_ids == (
        result.memory.active_items()[0].item_id,
    )
    assert exported_proposal["resolved_by_mp_user_id"] == "mp-user-1"
    assert exported_proposal["resolved_memory_revision"] == 1
    assert exported_proposal["projected_memory_item_ids"] == list(
        result.proposal.projected_memory_item_ids
    )
    assert "prompt" not in result.to_dict()


def test_repeated_confirmation_is_idempotent_and_does_not_change_actor():
    """重复确认返回原结果，不新增 revision 或改写首次确认人。"""
    repository = AgentRankRepository(FakePlugin())
    proposal = _proposal(
        repository, _event(repository, "event-1", "tmdb:tv:1")
    )
    service = MemoryProjectionService(
        repository, now_factory=lambda: FIXED_NOW
    )

    first = service.confirm(
        PROFILE_ID, proposal.proposal_id, actor_id="mp-user-1"
    )
    duplicate = service.confirm(
        PROFILE_ID, proposal.proposal_id, actor_id="mp-user-2"
    )

    assert first.applied is True
    assert duplicate.applied is False
    assert duplicate.reason == "already_confirmed"
    assert duplicate.memory.memory_revision == 1
    assert duplicate.proposal.resolved_by_mp_user_id == "mp-user-1"
    assert duplicate.proposal == first.proposal


def test_repeated_confirmation_rejects_tampered_projection_audit():
    """确认审计被改写后不得用“已确认”掩盖记忆与提案不一致。"""
    repository = AgentRankRepository(FakePlugin())
    proposal = _proposal(
        repository, _event(repository, "event-1", "tmdb:tv:1")
    )
    service = MemoryProjectionService(
        repository, now_factory=lambda: FIXED_NOW
    )
    confirmed = service.confirm(
        PROFILE_ID, proposal.proposal_id, actor_id="mp-user-1"
    ).proposal
    repository.replace_memory_proposal(
        replace(
            confirmed,
            projected_memory_item_ids=("preference-memory:tampered",),
        ),
        expected_status="confirmed",
    )

    with pytest.raises(MemoryConfirmationError) as caught:
        service.confirm(
            PROFILE_ID, proposal.proposal_id, actor_id="mp-user-1"
        )

    assert caught.value.code == "confirmation_audit_inconsistent"
    assert repository.load_preference_memory(PROFILE_ID).memory_revision == 1


def test_multiple_changes_from_one_proposal_increment_one_revision():
    """同一提案的多项不同偏好原子写入且 revision 只增加一次。"""
    repository = AgentRankRepository(FakePlugin())
    event = _event(repository, "event-1", "tmdb:tv:1")
    proposal = _proposal(
        repository,
        event,
        changes=(
            _change("genre", category="genre", value="科幻"),
            _change("pace", category="pacing", value="快节奏"),
        ),
    )

    result = MemoryProjectionService(
        repository, now_factory=lambda: FIXED_NOW
    ).confirm(PROFILE_ID, proposal.proposal_id, actor_id="mp-user-1")

    assert result.memory.memory_revision == 1
    assert len(result.memory.active_items()) == 2
    assert len(result.proposal.projected_memory_item_ids) == 2


def test_same_proposal_concurrent_confirmation_has_one_applied_result():
    """同一提案并发确认时只有一次真实投影，其余均为幂等回读。"""
    repository = AgentRankRepository(FakePlugin())
    proposal = _proposal(
        repository, _event(repository, "event-1", "tmdb:tv:1")
    )
    services = [
        MemoryProjectionService(repository, now_factory=lambda: FIXED_NOW)
        for _ in range(8)
    ]

    def confirm(index):
        """使用不同服务实例确认同一提案。"""
        return services[index % len(services)].confirm(
            PROFILE_ID, proposal.proposal_id, actor_id="mp-user-1"
        )

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(confirm, range(100)))

    assert sum(result.applied for result in results) == 1
    assert sum(result.reason == "already_confirmed" for result in results) == 99
    assert repository.load_preference_memory(PROFILE_ID).memory_revision == 1


def test_competing_proposals_with_same_revision_cannot_overwrite_winner():
    """两个旧 revision 提案竞争时一个确认，另一个记录为 superseded。"""
    repository = AgentRankRepository(FakePlugin())
    first = _proposal(
        repository,
        _event(repository, "event-1", "tmdb:tv:1"),
        suffix="1",
        changes=(_change("1", value="科幻"),),
    )
    second = _proposal(
        repository,
        _event(repository, "event-2", "tmdb:tv:2"),
        suffix="2",
        changes=(_change("2", value="悬疑"),),
    )
    service = MemoryProjectionService(
        repository, now_factory=lambda: FIXED_NOW
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda item: service.confirm(
                    PROFILE_ID, item.proposal_id, actor_id="mp-user-1"
                ),
                (first, second),
            )
        )

    assert sum(result.applied for result in results) == 1
    assert {result.status for result in results} == {"confirmed", "superseded"}
    superseded = next(result for result in results if not result.applied)
    assert superseded.reason == "memory_revision_conflict"
    assert repository.load_preference_memory(PROFILE_ID).memory_revision == 1


def test_late_old_proposal_is_superseded_without_changing_new_memory():
    """新记忆先落盘后，晚到旧提案只记录冲突且逐字段不覆盖。"""
    repository = AgentRankRepository(FakePlugin())
    old = _proposal(
        repository, _event(repository, "event-old", "tmdb:tv:1")
    )
    _event(repository, "event-padding", "tmdb:tv:2")
    current = repository.project_preference_memory(
        PROFILE_ID,
        [_memory_item("newer-memory", 2, value="悬疑")],
        expected_revision=0,
        source_event_sequence=2,
    ).memory
    before = current.to_dict()

    result = MemoryProjectionService(
        repository, now_factory=lambda: FIXED_NOW
    ).confirm(PROFILE_ID, old.proposal_id, actor_id="mp-user-1")

    assert result.applied is False
    assert result.status == "superseded"
    assert result.reason == "memory_revision_conflict"
    assert repository.load_preference_memory(PROFILE_ID).to_dict() == before
    assert result.proposal.projected_memory_item_ids == ()


def test_restore_supersedes_tombstone_and_reinforce_never_reduces_strength():
    """显式恢复替代墓碑，同向强化不会降低既有强度或确定性。"""
    repository = AgentRankRepository(FakePlugin())
    repository.project_preference_memory(
        PROFILE_ID,
        [_memory_item("active-1", 1, strength=0.9, certainty=0.9)],
        expected_revision=0,
        source_event_sequence=1,
    )
    tombstone = _memory_item(
        "tombstone-2",
        2,
        tombstone=True,
        supersedes=("active-1",),
        strength=0.9,
        certainty=0.9,
    )
    repository.project_preference_memory(
        PROFILE_ID,
        [tombstone],
        expected_revision=1,
        source_event_sequence=2,
    )
    _event(repository, "padding-1", "tmdb:tv:0")
    _event(repository, "padding-2", "tmdb:tv:2")
    restore_event = _event(repository, "restore-event", "tmdb:tv:3")
    restore = _proposal(
        repository,
        restore_event,
        suffix="restore",
        expected_revision=2,
        changes=(
            _change(
                "restore",
                operation="restore",
                certainty=0.4,
                target_ids=("tombstone-2",),
            ),
        ),
    )
    service = MemoryProjectionService(
        repository, now_factory=lambda: FIXED_NOW
    )

    restored = service.confirm(
        PROFILE_ID, restore.proposal_id, actor_id="mp-user-1"
    )
    restored_item = restored.memory.latest_item("genre", "科幻")
    assert restored_item.tombstone is False
    assert restored_item.supersedes == ("tombstone-2",)

    reinforce_event = _event(repository, "reinforce-event", "tmdb:tv:4")
    reinforce = _proposal(
        repository,
        reinforce_event,
        suffix="reinforce",
        expected_revision=3,
        changes=(
            _change(
                "reinforce",
                operation="reinforce",
                certainty=0.2,
                target_ids=(restored_item.item_id,),
            ),
        ),
    )
    reinforced = service.confirm(
        PROFILE_ID, reinforce.proposal_id, actor_id="mp-user-1"
    ).memory.latest_item("genre", "科幻")
    assert reinforced.strength >= restored_item.strength
    assert reinforced.certainty >= restored_item.certainty


def test_projection_and_proposal_status_roll_back_together_on_write_failure():
    """提案状态写失败时回滚已写记忆，重试后再原子成功。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    proposal = _proposal(
        repository, _event(repository, "event-1", "tmdb:tv:1")
    )
    proposal_key = repository._learning_key("memory_proposals", PROFILE_ID)
    before = copy.deepcopy(plugin.data)
    plugin.fail_once_on_key = proposal_key
    service = MemoryProjectionService(
        repository, now_factory=lambda: FIXED_NOW
    )

    with pytest.raises(RuntimeError, match="injected projection save failure"):
        service.confirm(
            PROFILE_ID, proposal.proposal_id, actor_id="mp-user-1"
        )

    assert repository.load_preference_memory(PROFILE_ID).memory_revision == 0
    assert repository.get_memory_proposal(PROFILE_ID, proposal.proposal_id).status == "pending_confirmation"
    assert {
        key: value
        for key, value in plugin.data.items()
        if key != repository.recovery_log_key
    } == before

    recovered = service.confirm(
        PROFILE_ID, proposal.proposal_id, actor_id="mp-user-1"
    )
    assert recovered.applied is True
    assert recovered.memory.memory_revision == 1


def test_expired_or_rejected_proposals_never_project_memory():
    """过期和已拒绝提案均无法通过确认入口写入长期记忆。"""
    repository = AgentRankRepository(FakePlugin())
    expired = _proposal(
        repository,
        _event(repository, "event-expired", "tmdb:tv:1"),
        suffix="expired",
        expires_at=FIXED_NOW + timedelta(seconds=1),
    )
    rejected = _proposal(
        repository,
        _event(repository, "event-rejected", "tmdb:tv:2"),
        suffix="rejected",
    )
    repository.replace_memory_proposal(
        replace(
            rejected,
            status="rejected",
            resolved_at=FIXED_NOW.isoformat(),
        ),
        expected_status="pending_confirmation",
    )
    service = MemoryProjectionService(
        repository, now_factory=lambda: FIXED_NOW + timedelta(seconds=2)
    )

    with pytest.raises(MemoryConfirmationError) as expired_error:
        service.confirm(
            PROFILE_ID, expired.proposal_id, actor_id="mp-user-1"
        )
    with pytest.raises(MemoryConfirmationError) as rejected_error:
        service.confirm(
            PROFILE_ID, rejected.proposal_id, actor_id="mp-user-1"
        )

    assert expired_error.value.code == "proposal_expired"
    assert rejected_error.value.code == "proposal_already_resolved"
    assert repository.load_preference_memory(PROFILE_ID).memory_revision == 0


def test_confirmation_requires_auditable_actor_identity():
    """缺少 MoviePilot 用户身份时不读取或修改提案和长期记忆。"""
    repository = AgentRankRepository(FakePlugin())
    proposal = _proposal(
        repository, _event(repository, "event-1", "tmdb:tv:1")
    )
    service = MemoryProjectionService(repository)

    with pytest.raises(MemoryConfirmationError) as caught:
        service.confirm(PROFILE_ID, proposal.proposal_id, actor_id="")

    assert caught.value.code == "actor_id_invalid"
    assert repository.get_memory_proposal(PROFILE_ID, proposal.proposal_id).status == "pending_confirmation"
    assert repository.load_preference_memory(PROFILE_ID).memory_revision == 0
