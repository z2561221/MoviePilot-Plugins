"""统一待确认中心、响应编排与提醒领取服务。"""

from typing import Any, Dict, Iterable, List, Optional

from ..model.conversation import ConversationCommand
from ..model.feedback_decision import MemoryProposal, PendingQuestion
from ..model.pending_center import PendingCenterItem, PendingNotice
from ..storage.repository import AgentRankRepository


class PendingCenterError(RuntimeError):
    """表示统一待确认请求不完整或类型不受支持。"""

    def __init__(self, code: str, message: str, status_code: int = 409):
        """保存稳定错误码、用户文案与 HTTP 状态码。"""
        self.code = str(code)
        self.message = str(message)
        self.status_code = int(status_code)
        super().__init__(self.message)


class PendingCenterService:
    """汇聚提案、问询和对话命令，且不复制各自写入逻辑。"""

    def __init__(
        self,
        repository: AgentRankRepository,
        *,
        feedback_response: Any,
        memory_projection: Any,
        conversation: Any,
    ):
        """绑定仓储与三个既有受控状态机。"""
        if not isinstance(repository, AgentRankRepository):
            raise TypeError("repository must be AgentRankRepository")
        self._repository = repository
        self._feedback_response = feedback_response
        self._memory_projection = memory_projection
        self._conversation = conversation

    @staticmethod
    def _profile_id(value: Any) -> str:
        """校验并返回稳定画像身份。"""
        target = str(value or "").strip()
        if not target:
            raise PendingCenterError(
                "pending_profile_required", "必须指定待确认画像", 422
            )
        return target

    @staticmethod
    def _record_type(value: Any) -> str:
        """校验统一待确认类型。"""
        target = str(value or "").strip().casefold()
        if target not in {"proposal", "question", "command"}:
            raise PendingCenterError(
                "pending_type_invalid", "待确认类型不受支持", 422
            )
        return target

    @staticmethod
    def _proposal_item(record: MemoryProposal) -> PendingCenterItem:
        """把记忆提案投影为不含证据身份的安全展示项。"""
        return PendingCenterItem(
            item_type="proposal",
            item_id=record.proposal_id,
            profile_id=record.profile_id,
            title="确认专属影评师的新理解",
            summary=record.restatement,
            candidate_id=record.candidate_id,
            detail_lines=record.impact_preview,
            created_at=record.created_at,
            expires_at=record.expires_at,
            status=record.status,
            reminder_policy=record.reminder_policy,
            next_remind_at=record.next_remind_at,
            last_reminded_at=record.last_reminded_at,
        )

    @staticmethod
    def _question_item(record: PendingQuestion) -> PendingCenterItem:
        """把歧义问询投影为安全选项与自定义回答能力。"""
        return PendingCenterItem(
            item_type="question",
            item_id=record.question_id,
            profile_id=record.profile_id,
            title="专属影评师需要你确认",
            summary=record.question,
            candidate_id=record.candidate_id,
            detail_lines=record.uncertainties,
            options=tuple(item.to_dict() for item in record.options),
            allow_custom_answer=record.allow_custom_answer,
            created_at=record.created_at,
            expires_at=record.expires_at,
            status=record.status,
            reminder_policy=record.reminder_policy,
            next_remind_at=record.next_remind_at,
            last_reminded_at=record.last_reminded_at,
        )

    @staticmethod
    def _command_item(record: ConversationCommand) -> PendingCenterItem:
        """把对话命令投影为待确认预览，不公开命令载荷。"""
        return PendingCenterItem(
            item_type="command",
            item_id=record.command_id,
            profile_id=record.profile_id,
            title=record.title,
            summary=record.preview,
            created_at=record.created_at,
            status=record.status,
            reminder_policy=record.reminder_policy,
            next_remind_at=record.next_remind_at,
            last_reminded_at=record.last_reminded_at,
            requires_superuser=record.requires_superuser,
        )

    def _actor_for_event(self, profile_id: str, event_id: str) -> str:
        """读取待确认来源事件的审计用户身份。"""
        event = next(
            (
                item
                for item in self._repository.load_feedback_events(profile_id)
                if item.event_id == event_id
            ),
            None,
        )
        return str(getattr(event, "created_by_mp_user_id", "") or "")[:128]

    def _command_records(self, profile_id: str) -> List[ConversationCommand]:
        """读取指定画像的对话命令，损坏数据按严格模式拒绝。"""
        _, commands = self._repository.load_conversation_records(
            profile_id, strict=True
        )
        return commands

    def _command(
        self, profile_id: str, command_id: str
    ) -> Optional[ConversationCommand]:
        """读取指定对话命令。"""
        target_id = str(command_id or "").strip()
        return next(
            (
                item
                for item in self._command_records(profile_id)
                if item.command_id == target_id
            ),
            None,
        )

    def list_pending(
        self,
        profile_id: Any,
        *,
        actor_id: str = "",
        is_superuser: bool = False,
    ) -> Dict[str, Any]:
        """返回当前用户可见的三类未完成项目。"""
        target = self._profile_id(profile_id)
        self._feedback_response.expire_due(target)
        items: List[PendingCenterItem] = []
        items.extend(
            self._proposal_item(item)
            for item in self._repository.load_memory_proposals(target)
            if item.status == "pending_confirmation"
        )
        items.extend(
            self._question_item(item)
            for item in self._repository.load_pending_questions(target)
            if item.status == "pending"
        )
        requester = str(actor_id or "").strip()
        items.extend(
            self._command_item(item)
            for item in self._command_records(target)
            if item.status == "pending_confirmation"
            and (is_superuser or item.requested_by_mp_user_id == requester)
        )
        items.sort(key=lambda item: (item.created_at, item.item_type, item.item_id))
        counts = {
            item_type: sum(1 for item in items if item.item_type == item_type)
            for item_type in ("proposal", "question", "command")
        }
        return {
            "profile_id": target,
            "items": [item.to_dict() for item in items],
            "counts": counts,
            "total": len(items),
        }

    def item(
        self,
        profile_id: Any,
        item_type: Any,
        item_id: Any,
    ) -> PendingCenterItem:
        """读取一个统一待确认项目的安全展示。"""
        target = self._profile_id(profile_id)
        target_type = self._record_type(item_type)
        target_id = str(item_id or "").strip()
        record: Any = None
        if target_type == "proposal":
            record = self._repository.get_memory_proposal(target, target_id)
        elif target_type == "question":
            record = self._repository.get_pending_question(target, target_id)
        else:
            record = self._command(target, target_id)
        if record is None:
            raise PendingCenterError(
                "pending_item_not_found", "待确认项目不存在或已清理", 404
            )
        if isinstance(record, MemoryProposal):
            return self._proposal_item(record)
        if isinstance(record, PendingQuestion):
            return self._question_item(record)
        return self._command_item(record)

    def notice_for_event(
        self, profile_id: str, event_id: str
    ) -> Optional[PendingNotice]:
        """返回反馈事件新生成的提案或问询通知。"""
        target = self._profile_id(profile_id)
        proposal = self._repository.load_memory_proposal(target, event_id)
        if proposal is not None and proposal.status == "pending_confirmation":
            return PendingNotice(
                self._proposal_item(proposal),
                self._actor_for_event(target, event_id),
            )
        question = self._repository.load_pending_question(target, event_id)
        if question is not None and question.status == "pending":
            return PendingNotice(
                self._question_item(question),
                self._actor_for_event(target, event_id),
            )
        return None

    def notice_for_command(self, command: ConversationCommand) -> PendingNotice:
        """返回对话新命令的安全通知与请求者审计身份。"""
        if not isinstance(command, ConversationCommand):
            raise TypeError("command must be ConversationCommand")
        return PendingNotice(
            self._command_item(command), command.requested_by_mp_user_id
        )

    def respond(
        self,
        *,
        profile_id: Any,
        item_type: Any,
        item_id: Any,
        action: Any,
        actor_id: str,
        is_superuser: bool = False,
        reminder_policy: str = "",
        idempotency_key: str = "",
        option_id: str = "",
        custom_answer: str = "",
    ) -> Dict[str, Any]:
        """把统一动作委托给原状态机并返回脱敏结果。"""
        target = self._profile_id(profile_id)
        target_type = self._record_type(item_type)
        target_id = str(item_id or "").strip()
        decision = str(action or "").strip().casefold()
        actor = str(actor_id or "").strip()
        if not target_id:
            raise PendingCenterError(
                "pending_item_required", "必须指定待确认项目", 422
            )
        if not actor:
            raise PendingCenterError(
                "pending_actor_required", "无法确认当前操作用户", 403
            )
        changed = True
        queue_status = ""
        memory_revision = None
        if decision == "remind":
            policy = str(reminder_policy or "").strip().casefold()
            if target_type == "command":
                self._conversation.set_command_reminder(
                    profile_id=target,
                    command_id=target_id,
                    reminder_policy=policy,
                    actor_id=actor,
                    is_superuser=is_superuser,
                )
            else:
                self._feedback_response.set_reminder(
                    target, target_type, target_id, policy
                )
        elif decision == "reject":
            if target_type == "command":
                self._conversation.respond_command(
                    profile_id=target,
                    command_id=target_id,
                    action="reject",
                    actor_id=actor,
                    is_superuser=is_superuser,
                )
            else:
                self._feedback_response.reject(target, target_type, target_id)
        elif decision == "confirm" and target_type == "proposal":
            result = self._memory_projection.confirm(
                target, target_id, actor_id=actor
            )
            changed = bool(result.applied)
            memory_revision = result.memory.memory_revision
        elif decision == "confirm" and target_type == "command":
            result = self._conversation.respond_command(
                profile_id=target,
                command_id=target_id,
                action="confirm",
                actor_id=actor,
                is_superuser=is_superuser,
            )
            changed = not bool(result.get("idempotent"))
        elif decision == "answer" and target_type == "question":
            result = self._feedback_response.answer_question(
                target,
                target_id,
                idempotency_key=idempotency_key,
                actor_id=actor,
                option_id=option_id,
                custom_answer=custom_answer,
            )
            changed = bool(result.event_created)
            queue_status = result.queue_status
        else:
            raise PendingCenterError(
                "pending_action_invalid", "该待确认项目不支持此操作", 422
            )
        item = self.item(target, target_type, target_id)
        return {
            "action": decision,
            "changed": changed,
            "item": item.to_dict(),
            "queue_status": queue_status,
            "memory_revision": memory_revision,
        }

    def claim_due_notices(self, profile_id: Any) -> List[PendingNotice]:
        """原子领取三类到期提醒并返回安全通知，不投影记忆。"""
        target = self._profile_id(profile_id)
        notices: List[PendingNotice] = []
        for reminder in self._feedback_response.claim_due_reminders(target):
            item = self.item(target, reminder.decision_type, reminder.decision_id)
            record = (
                self._repository.get_memory_proposal(target, reminder.decision_id)
                if reminder.decision_type == "proposal"
                else self._repository.get_pending_question(target, reminder.decision_id)
            )
            notices.append(
                PendingNotice(
                    item,
                    self._actor_for_event(target, getattr(record, "event_id", "")),
                )
            )
        for command in self._conversation.claim_due_command_reminders(target):
            notices.append(self.notice_for_command(command))
        return notices

    def visible_notices(
        self, values: Iterable[PendingNotice]
    ) -> List[Dict[str, Any]]:
        """返回测试与调度日志可用的公开通知摘要。"""
        return [item.to_public_dict() for item in values]
