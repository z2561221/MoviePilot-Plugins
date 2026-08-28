"""Agent 对话、命令确认与统一待办处理。"""

from typing import Any, Dict

from .errors import ApiContractError
from ..service.conversation import ConversationError


class ConversationApiMixin:
    """Agent 对话、命令确认与统一待办处理。"""

    def conversation(
        self,
        profile_id: Any,
        actor_id: str = "",
        mark_read: bool = False,
    ) -> Dict[str, Any]:
        """返回一个 profile 的 CinePilot Agent 对话线程。"""
        target = self._profile_id(profile_id)
        try:
            service = self._conversation_service()
            data = service.snapshot(target)
            if actor_id:
                data["status"] = service.status(
                    target,
                    actor_id=actor_id,
                    mark_read=bool(mark_read),
                )
        except ConversationError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "conversation_read_failed", "对话读取失败，请稍后重试"
            ) from error
        return self._success(data)

    def conversation_status(
        self, profile_id: Any, actor_id: str = ""
    ) -> Dict[str, Any]:
        """返回当前 MP 用户的 CinePilot Agent 轻量未读状态。"""
        target = self._profile_id(profile_id)
        try:
            data = self._conversation_service().status(
                target, actor_id=actor_id, mark_read=False
            )
        except ConversationError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "conversation_status_failed", "对话状态读取失败，请稍后重试"
            ) from error
        return self._success(data)

    async def conversation_message(
        self, payload: Any, actor_id: str = ""
    ) -> Dict[str, Any]:
        """保存并排队一条 CinePilot Agent 对话消息。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            data = await self._conversation_service().send(
                profile_id=target,
                content=body.get("content"),
                idempotency_key=body.get("idempotency_key"),
                actor_id=actor_id,
            )
        except ConversationError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "conversation_failed", "对话生成失败，草稿已保留，可重试"
            ) from error
        return self._success(data)

    async def retry_conversation_message(
        self, payload: Any, actor_id: str = ""
    ) -> Dict[str, Any]:
        """重试一条由当前 MP 用户创建的失败草稿。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            data = await self._conversation_service().retry(
                profile_id=target,
                message_id=str(body.get("message_id") or ""),
                actor_id=actor_id,
            )
        except ConversationError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "conversation_retry_failed", "消息重试失败，草稿仍已保留"
            ) from error
        return self._success(data)

    def respond_conversation_command(
        self,
        payload: Any,
        actor_id: str = "",
        is_superuser: bool = False,
    ) -> Dict[str, Any]:
        """确认或拒绝一条 CinePilot Agent 待执行命令。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            data = self._conversation_service().respond_command(
                profile_id=target,
                command_id=str(body.get("command_id") or ""),
                action=str(body.get("action") or ""),
                actor_id=actor_id,
                is_superuser=bool(is_superuser),
            )
        except ConversationError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "conversation_command_failed", "命令执行失败，原状态已保留"
            ) from error
        return self._success(data)

    def pending_center(
        self,
        profile_id: Any,
        view: str = "pending",
        actor_id: str = "",
        is_superuser: bool = False,
    ) -> Dict[str, Any]:
        """返回当前 MP 用户可见的统一待确认项目。"""
        target = self._profile_id(profile_id)
        try:
            service = self._pending_center_service()
            method = getattr(service, "list_items", None)
            if callable(method):
                data = method(
                    target,
                    view=view,
                    actor_id=actor_id,
                    is_superuser=bool(is_superuser),
                )
            else:
                data = service.list_pending(
                    target,
                    actor_id=actor_id,
                    is_superuser=bool(is_superuser),
                )
        except Exception as error:
            status_code = getattr(error, "status_code", None)
            code = getattr(error, "code", None)
            message = getattr(error, "message", None)
            if status_code is not None and code is not None and message is not None:
                raise ApiContractError(
                    status_code, code, message
                ) from error
            raise ApiContractError(
                500, "pending_center_read_failed", "待确认中心读取失败，请稍后重试"
            ) from error
        return self._success(data)

    def respond_pending(
        self,
        payload: Any,
        actor_id: str = "",
        is_superuser: bool = False,
    ) -> Dict[str, Any]:
        """响应、拒绝或设置统一待确认项目的提醒。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            data = self._pending_center_service().respond(
                profile_id=target,
                item_type=body.get("item_type"),
                item_id=body.get("item_id"),
                action=body.get("action"),
                actor_id=actor_id,
                is_superuser=bool(is_superuser),
                idempotency_key=str(body.get("idempotency_key") or ""),
                option_id=str(body.get("option_id") or ""),
                custom_answer=str(body.get("custom_answer") or ""),
            )
        except Exception as error:
            status_code = getattr(error, "status_code", None)
            code = getattr(error, "code", None)
            message = getattr(error, "message", None)
            if status_code is not None and code is not None and message is not None:
                raise ApiContractError(
                    status_code, code, message
                ) from error
            raise ApiContractError(
                500, "pending_center_write_failed", "待确认操作失败，原状态已保留"
            ) from error
        return self._success(data)
