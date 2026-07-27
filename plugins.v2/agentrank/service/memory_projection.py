"""待确认记忆提案的确定性构造、CAS 投影与幂等确认。"""

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from ..model.feedback_decision import MemoryProposal, MemoryProposalChange
from ..model.memory import PreferenceMemory, PreferenceMemoryItem
from ..storage.repository import AgentRankRepository


class MemoryConfirmationError(RuntimeError):
    """表示记忆提案无法安全确认。"""

    def __init__(self, code: str, message: str, status_code: int = 409):
        """保存稳定错误码、用户文案和 HTTP 状态码。"""
        self.code = str(code)
        self.message = str(message)
        self.status_code = int(status_code)
        super().__init__(self.message)


@dataclass(frozen=True)
class MemoryConfirmationResult:
    """描述一次提案确认、重复确认或冲突淘汰结果。"""

    proposal: MemoryProposal
    memory: PreferenceMemory
    applied: bool
    status: str
    reason: str = ""

    def __post_init__(self) -> None:
        """校验结果状态与提案终态一致。"""
        if not isinstance(self.proposal, MemoryProposal):
            raise ValueError("confirmation result requires MemoryProposal")
        if not isinstance(self.memory, PreferenceMemory):
            raise ValueError("confirmation result requires PreferenceMemory")
        object.__setattr__(self, "applied", bool(self.applied))
        object.__setattr__(self, "status", str(self.status or "").strip())
        object.__setattr__(self, "reason", str(self.reason or "").strip())
        if self.status not in {"confirmed", "superseded"}:
            raise ValueError("confirmation result status is invalid")
        if self.proposal.status != self.status:
            raise ValueError("confirmation result proposal status is inconsistent")
        if self.applied and self.status != "confirmed":
            raise ValueError("only a confirmed proposal can be applied")
        if not self.applied and not self.reason:
            raise ValueError("non-applied confirmation requires a reason")
        if self.applied and self.reason:
            raise ValueError("applied confirmation cannot have a reason")

    def to_dict(self) -> Dict[str, Any]:
        """返回不含完整画像和内部推理的确认摘要。"""
        return {
            "proposal_id": self.proposal.proposal_id,
            "profile_id": self.proposal.profile_id,
            "status": self.status,
            "applied": self.applied,
            "reason": self.reason,
            "memory_revision": self.memory.memory_revision,
            "projected_memory_item_ids": list(
                self.proposal.projected_memory_item_ids
            ),
        }


class MemoryProjectionService:
    """把用户确认的变化预览投影为有谱系的长期偏好记忆。"""

    def __init__(
        self,
        repository: AgentRankRepository,
        *,
        now_factory: Callable[[], datetime] = None,
    ):
        """绑定仓储和可测试时钟。"""
        if not isinstance(repository, AgentRankRepository):
            raise TypeError("repository must be AgentRankRepository")
        self._repository = repository
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        """返回带 UTC 时区的当前时间。"""
        current = self._now_factory()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)

    @staticmethod
    def _profile_id(value: str) -> str:
        """校验并返回稳定 profile 身份。"""
        target = str(value or "").strip()
        if not target:
            raise MemoryConfirmationError(
                "proposal_identity_required", "必须指定待确认提案", 422
            )
        return target

    @staticmethod
    def _actor_id(value: str) -> str:
        """校验确认操作的 MoviePilot 用户身份。"""
        actor = str(value or "").strip()
        if not actor or len(actor) > 128:
            raise MemoryConfirmationError(
                "actor_id_invalid", "确认请求缺少有效用户身份", 422
            )
        return actor

    @staticmethod
    def _stable_item_id(proposal_id: str, change_id: str) -> str:
        """为每项变化生成跨重试稳定且不泄露内容的记忆身份。"""
        digest = hashlib.sha256(
            f"memory-item:{proposal_id}:{change_id}".encode("utf-8")
        ).hexdigest()[:24]
        return f"preference-memory:{digest}"

    @staticmethod
    def _is_expired(proposal: MemoryProposal, now: datetime) -> bool:
        """判断待确认提案是否已经越过过期时间。"""
        expires = datetime.fromisoformat(
            proposal.expires_at.replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        return expires <= now

    @staticmethod
    def _strength_and_certainty(
        change: MemoryProposalChange,
        memory: PreferenceMemory,
    ) -> tuple[float, float]:
        """根据操作和当前目标确定新记忆的有界强度与确定性。"""
        targets = {
            item.item_id: item
            for item in memory.items
            if item.item_id in change.target_memory_item_ids
        }
        certainty = max(0.0, min(float(change.certainty), 1.0))
        strength = certainty
        if change.operation == "reinforce" and targets:
            strength = max(
                [certainty, *(item.strength for item in targets.values())]
            )
            certainty = max(
                [certainty, *(item.certainty for item in targets.values())]
            )
        elif change.operation == "archive" and targets:
            strength = max(item.strength for item in targets.values())
        return strength, certainty

    def _memory_items(
        self,
        proposal: MemoryProposal,
        memory: PreferenceMemory,
        *,
        created_at: str,
    ) -> List[PreferenceMemoryItem]:
        """把用户看过的变化预览确定性转换为确认态记忆项。"""
        items = []
        for change in proposal.changes:
            strength, certainty = self._strength_and_certainty(change, memory)
            tombstone = change.operation == "archive"
            items.append(
                PreferenceMemoryItem(
                    item_id=self._stable_item_id(
                        proposal.proposal_id, change.change_id
                    ),
                    category=change.category,
                    value=change.value,
                    polarity=change.polarity,
                    strength=strength,
                    certainty=certainty,
                    evidence_refs=change.evidence_refs,
                    source_event_sequence=proposal.event_sequence,
                    created_at=created_at,
                    status="archived" if tombstone else "active",
                    tombstone=tombstone,
                    supersedes=change.target_memory_item_ids,
                )
            )
        return items

    @staticmethod
    def _confirmed_result(
        proposal: MemoryProposal, memory: PreferenceMemory
    ) -> MemoryConfirmationResult:
        """校验已确认提案的持久化审计并返回幂等结果。"""
        expected_ids = tuple(
            MemoryProjectionService._stable_item_id(
                proposal.proposal_id, change.change_id
            )
            for change in proposal.changes
        )
        known_items = {item.item_id: item for item in memory.items}
        if (
            proposal.resolved_memory_revision > memory.memory_revision
            or proposal.projected_memory_item_ids != expected_ids
        ):
            raise MemoryConfirmationError(
                "confirmation_audit_inconsistent",
                "已确认提案与长期记忆不一致，请先修复数据",
                409,
            )
        for change, item_id in zip(proposal.changes, expected_ids):
            item = known_items.get(item_id)
            if item is None or any(
                (
                    item.category != change.category,
                    item.value != change.value,
                    item.polarity != change.polarity,
                    item.source_event_sequence != proposal.event_sequence,
                    item.supersedes != change.target_memory_item_ids,
                    item.tombstone != (change.operation == "archive"),
                )
            ):
                raise MemoryConfirmationError(
                    "confirmation_audit_inconsistent",
                    "已确认提案与长期记忆不一致，请先修复数据",
                    409,
                )
        return MemoryConfirmationResult(
            proposal=proposal,
            memory=memory,
            applied=False,
            status="confirmed",
            reason="already_confirmed",
        )

    def confirm(
        self,
        profile_id: str,
        proposal_id: str,
        *,
        actor_id: str,
    ) -> MemoryConfirmationResult:
        """确认一项提案，应用一次 CAS 投影或记录其已被新记忆替代。"""
        target = self._profile_id(profile_id)
        actor = self._actor_id(actor_id)
        target_id = str(proposal_id or "").strip()
        if not target_id:
            raise MemoryConfirmationError(
                "proposal_identity_required", "必须指定待确认提案", 422
            )
        with self._repository.profile_data_guard(target):
            proposal = self._repository.get_memory_proposal(target, target_id)
            if proposal is None:
                raise MemoryConfirmationError(
                    "proposal_not_found", "待确认提案不存在或已清理", 404
                )
            memory = self._repository.load_preference_memory(target)
            if proposal.status == "confirmed":
                return self._confirmed_result(proposal, memory)
            if proposal.status == "superseded":
                return MemoryConfirmationResult(
                    proposal=proposal,
                    memory=memory,
                    applied=False,
                    status="superseded",
                    reason=proposal.resolution_reason,
                )
            if proposal.status != "pending_confirmation":
                raise MemoryConfirmationError(
                    "proposal_already_resolved", "该记忆提案已经处理", 409
                )
            now = self._now()
            if self._is_expired(proposal, now):
                expired = replace(
                    proposal,
                    status="expired",
                    reminder_policy="never",
                    next_remind_at="",
                    resolved_at=now.isoformat(),
                )
                if not self._repository.replace_memory_proposal(
                    expired, expected_status="pending_confirmation"
                ):
                    raise MemoryConfirmationError(
                        "proposal_state_conflict",
                        "提案状态已变化，请刷新后重试",
                        409,
                    )
                raise MemoryConfirmationError(
                    "proposal_expired", "该记忆提案已过期", 409
                )
            items = self._memory_items(
                proposal, memory, created_at=now.isoformat()
            )
            projection, updated = self._repository.project_memory_proposal(
                proposal,
                items,
                confirmed_by_mp_user_id=actor,
                resolved_at=now.isoformat(),
            )
            return MemoryConfirmationResult(
                proposal=updated,
                memory=projection.memory,
                applied=projection.applied,
                status=updated.status,
                reason="" if projection.applied else projection.reason,
            )
