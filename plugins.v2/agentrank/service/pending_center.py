"""统一待处理中心与确认式响应编排服务。"""

import logging

from typing import Any, Dict, Iterable, List, Optional

from ..model.conversation import ConversationCommand
from ..model.feedback_decision import MemoryProposal, PendingQuestion
from ..model.pending_center import PendingCenterItem, PendingNotice
from ..storage.repository import AgentRankRepository
from .critic_skills import style_agent_message, style_clarification_question
from .prompt import AGENT_DISPLAY_NAME_DEFAULT, configured_agent_display_name


logger = logging.getLogger(__name__)


class PendingCenterError(RuntimeError):
    """表示统一待处理请求不完整或类型不受支持。"""

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
        persona_prompt: str = "",
        agent_name: str = AGENT_DISPLAY_NAME_DEFAULT,
        resolution_handler: Any = None,
        pending_handler: Any = None,
    ):
        """绑定仓储与三个既有受控状态机。"""
        if not isinstance(repository, AgentRankRepository):
            raise TypeError("repository must be AgentRankRepository")
        self._repository = repository
        self._feedback_response = feedback_response
        self._memory_projection = memory_projection
        self._conversation = conversation
        self._persona_prompt = str(persona_prompt or "").strip()
        self._agent_name = configured_agent_display_name(agent_name)
        self._resolution_handler = resolution_handler
        self._pending_handler = pending_handler

    def set_resolution_handler(self, handler: Any = None) -> None:
        """设置待办终态后的非阻断跨端收束回调。"""
        self._resolution_handler = handler

    def set_pending_handler(self, handler: Any = None) -> None:
        """设置事项重新打开后的非阻断通知回调。"""
        self._pending_handler = handler

    @staticmethod
    def _profile_id(value: Any) -> str:
        """校验并返回稳定画像身份。"""
        target = str(value or "").strip()
        if not target:
            raise PendingCenterError(
                "pending_profile_required", "必须指定待处理画像", 422
            )
        return target

    @staticmethod
    def _record_type(value: Any) -> str:
        """校验统一待处理类型。"""
        target = str(value or "").strip().casefold()
        if target not in {"proposal", "question", "command"}:
            raise PendingCenterError(
                "pending_type_invalid", "待处理类型不受支持", 422
            )
        return target

    def _proposal_item(self, record: MemoryProposal) -> PendingCenterItem:
        """把记忆提案投影为不含证据身份的安全展示项。"""
        result_message = (
            "已写入长期画像"
            if record.status == "confirmed"
            else "已拒绝采纳"
            if record.status == "rejected"
            else ""
        )
        return PendingCenterItem(
            item_type="proposal",
            item_id=record.proposal_id,
            profile_id=record.profile_id,
            title=f"确认 {self._agent_name} 的新理解",
            summary=record.restatement,
            candidate_id=record.candidate_id,
            detail_lines=record.impact_preview,
            created_at=record.created_at,
            expires_at=record.expires_at,
            status=record.status,
            resolved_at=record.resolved_at,
            result_code=record.resolution_reason,
            result_message=style_agent_message(
                result_message,
                self._persona_prompt,
            ),
        )

    def _question_item(self, record: PendingQuestion) -> PendingCenterItem:
        """把歧义问询投影为安全选项与自定义回答能力。"""
        return PendingCenterItem(
            item_type="question",
            item_id=record.question_id,
            profile_id=record.profile_id,
            title=f"{self._agent_name} 需要你的回答",
            summary=style_clarification_question(
                record.question,
                self._persona_prompt,
            ),
            candidate_id=record.candidate_id,
            detail_lines=record.uncertainties,
            options=tuple(item.to_dict() for item in record.options),
            allow_custom_answer=record.allow_custom_answer,
            created_at=record.created_at,
            expires_at=record.expires_at,
            status=record.status,
            selected_option_id=record.selected_option_id,
            answer_text=record.answer_text,
            resolved_at=record.resolved_at,
            editable=record.status in {"answered", "dismissed"},
            reversible=record.status in {"answered", "dismissed"},
        )

    def _command_item(self, record: ConversationCommand) -> PendingCenterItem:
        """把对话命令投影为待处理预览，不公开命令载荷。"""
        return PendingCenterItem(
            item_type="command",
            item_id=record.command_id,
            profile_id=record.profile_id,
            title=record.title,
            summary=record.preview,
            created_at=record.created_at,
            status=record.status,
            requires_superuser=record.requires_superuser,
            resolved_at=record.resolved_at,
            result_code=record.execution_code,
            result_message=style_agent_message(
                record.execution_message,
                self._persona_prompt,
            ),
            reversible=(
                record.status == "confirmed"
                and record.kind in {"profile_tag", "weight"}
            ),
        )

    def _actor_for_event(self, profile_id: str, event_id: str) -> str:
        """读取待处理来源事件的审计用户身份。"""
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
        return self.list_items(
            profile_id,
            view="pending",
            actor_id=actor_id,
            is_superuser=is_superuser,
        )

    def list_items(
        self,
        profile_id: Any,
        *,
        view: str = "pending",
        actor_id: str = "",
        is_superuser: bool = False,
    ) -> Dict[str, Any]:
        """按待办、处理记录或全部返回当前用户可见项目。"""
        target = self._profile_id(profile_id)
        self._feedback_response.expire_due(target)
        scope = str(view or "pending").strip().casefold()
        if scope not in {"pending", "resolved", "all"}:
            raise PendingCenterError(
                "pending_view_invalid", "待处理视图不受支持", 422
            )

        def visible(status: str, pending_status: str) -> bool:
            """判断当前视图是否应展示指定状态。"""
            if scope == "all":
                return True
            return (
                status == pending_status
                if scope == "pending"
                else status != pending_status
            )

        items: List[PendingCenterItem] = []
        items.extend(
            self._proposal_item(item)
            for item in self._repository.load_memory_proposals(target)
            if visible(item.status, "pending_confirmation")
        )
        items.extend(
            self._question_item(item)
            for item in self._repository.load_pending_questions(target)
            if visible(item.status, "pending")
        )
        requester = str(actor_id or "").strip()
        items.extend(
            self._command_item(item)
            for item in self._command_records(target)
            if visible(item.status, "pending_confirmation")
            and (is_superuser or item.requested_by_mp_user_id == requester)
        )
        items.sort(
            key=lambda item: (item.resolved_at or item.created_at, item.item_type, item.item_id),
            reverse=scope == "resolved",
        )
        counts = {
            item_type: sum(1 for item in items if item.item_type == item_type)
            for item_type in ("proposal", "question", "command")
        }
        return {
            "profile_id": target,
            "view": scope,
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
        """读取一个统一待处理项目的安全展示。"""
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
                "pending_item_not_found", "待处理项目不存在或已清理", 404
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
                "pending_item_required", "必须指定待处理项目", 422
            )
        if not actor:
            raise PendingCenterError(
                "pending_actor_required", "无法确认当前操作用户", 403
            )
        changed = True
        queue_status = ""
        memory_revision = None
        if decision == "reject":
            if target_type == "command":
                self._conversation.respond_command(
                    profile_id=target,
                    command_id=target_id,
                    action="reject",
                    actor_id=actor,
                    is_superuser=is_superuser,
                )
            elif target_type == "proposal":
                self._feedback_response.reject(target, target_type, target_id)
            else:
                raise PendingCenterError(
                    "pending_action_invalid", "问询请使用关闭问询", 422
                )
        elif decision == "close" and target_type == "question":
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
        elif decision == "reopen" and target_type == "question":
            before = self._repository.get_pending_question(target, target_id)
            result = self._feedback_response.reopen_question(target, target_id)
            changed = before is None or before.status != result.status
        else:
            raise PendingCenterError(
                "pending_action_invalid", "该待处理项目不支持此操作", 422
            )
        item = self.item(target, target_type, target_id)
        if decision == "reopen" and changed and callable(self._pending_handler):
            try:
                self._pending_handler(PendingNotice(item, actor))
            except Exception:
                logger.exception(
                    "AgentRank 待办重新通知失败 type=%s item_id=%s",
                    target_type,
                    target_id,
                )
        elif decision != "reopen" and callable(self._resolution_handler):
            try:
                self._resolution_handler(item)
            except Exception:
                logger.exception(
                    "AgentRank 待办跨端收束失败 type=%s item_id=%s",
                    target_type,
                    target_id,
                )
        return {
            "action": decision,
            "changed": changed,
            "item": item.to_dict(),
            "queue_status": queue_status,
            "memory_revision": memory_revision,
        }

    def visible_notices(
        self, values: Iterable[PendingNotice]
    ) -> List[Dict[str, Any]]:
        """返回测试与调度日志可用的公开通知摘要。"""
        return [item.to_public_dict() for item in values]
