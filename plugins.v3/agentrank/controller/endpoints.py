"""AgentRank FastAPI bearer 端点绑定。"""

from typing import Any, Dict

from fastapi import Depends

from app import schemas
from app.sdk.security import verify_token

from .errors import ApiContractError, http_error


class AgentRankApiEndpointMixin:
    """把鉴权后的 HTTP 参数委托给纯业务控制器方法。"""

    def _endpoint(self, method: Any, *args: Any) -> Any:
        """把纯控制器错误转换为 FastAPI HTTPException。"""
        try:
            return self._business_data(method(*args))
        except ApiContractError as error:
            http_error(error)

    async def _endpoint_async(self, method: Any, *args: Any) -> Any:
        """异步执行纯控制器方法并转换 HTTP 错误。"""
        try:
            return self._business_data(await method(*args))
        except ApiContractError as error:
            http_error(error)

    def endpoint_status(
        self, token_payload: schemas.TokenPayload = Depends(verify_token)
    ) -> Dict[str, Any]:
        """FastAPI 状态入口。"""
        return self._endpoint(self.status_for_token, token_payload)

    def endpoint_config_options(
        self, _token_payload: schemas.TokenPayload = Depends(verify_token)
    ) -> Dict[str, Any]:
        """返回已登录用户可读取的完整配置选项。"""
        return self._endpoint(self.config_options)

    def endpoint_overview(
        self,
        profile_id: str = "",
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 总览入口。"""
        target = self._endpoint(self._authorize_profile, token_payload, profile_id)
        return self._endpoint(self.overview, target)

    def endpoint_board(
        self,
        profile_id: str = "",
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 榜单入口。"""
        target = self._endpoint(self._authorize_profile, token_payload, profile_id)
        return self._endpoint(self.board, target)

    def endpoint_profile(
        self,
        profile_id: str = "",
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 画像入口。"""
        target = self._endpoint(self._authorize_profile, token_payload, profile_id)
        return self._endpoint(self.profile, target)

    def endpoint_run_history(
        self,
        profile_id: str = "",
        page: int = 1,
        page_size: int = 15,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 运行历史入口。"""
        target = self._endpoint(self._authorize_profile, token_payload, profile_id)
        return self._endpoint(self.run_history, target, page, page_size)

    def endpoint_board_history(
        self,
        profile_id: str = "",
        page: int = 1,
        page_size: int = 10,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 历史榜单入口。"""
        target = self._endpoint(self._authorize_profile, token_payload, profile_id)
        return self._endpoint(self.board_history, target, page, page_size)

    def endpoint_run_progress(
        self,
        profile_id: str = "",
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 实时运行进度入口。"""
        target = self._endpoint(self._authorize_profile, token_payload, profile_id)
        return self._endpoint(self.run_progress, target)

    def endpoint_data_export(
        self,
        profile_id: str = "",
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 脱敏数据导出入口。"""
        target = self._endpoint(self._authorize_profile, token_payload, profile_id)
        return self._endpoint(self.data_export, target)

    def endpoint_reset_learning(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 仅学习重置入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return self._endpoint(self.reset_learning, payload)

    def endpoint_prepare_full_reset(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 彻底重置确认令牌入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        requester_id = self._endpoint(self._requester_id, token_payload)
        return self._endpoint(self.prepare_full_reset, payload, requester_id)

    def endpoint_reset_full(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 彻底重置执行入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        requester_id = self._endpoint(self._requester_id, token_payload)
        return self._endpoint(self.reset_full, payload, requester_id)

    async def endpoint_refresh(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 手动刷新入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return await self._endpoint_async(self.refresh, payload)

    async def endpoint_playback_sync(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 播放画像立即同步入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        actor_id = self._endpoint(self._feedback_actor_id, token_payload)
        return await self._endpoint_async(self.playback_sync, payload, actor_id)

    def endpoint_archive(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 忽略入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        actor_id = self._endpoint(self._feedback_actor_id, token_payload)
        return self._endpoint(self.archive, payload, actor_id)

    def endpoint_feedback(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 统一三态反馈入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        actor_id = self._endpoint(self._feedback_actor_id, token_payload)
        return self._endpoint(self.feedback, payload, actor_id)

    def endpoint_analysis_comment(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 逐条 Agent 分析评论入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        actor_id = self._endpoint(self._feedback_actor_id, token_payload)
        return self._endpoint(self.analysis_comment, payload, actor_id)

    def endpoint_analysis(
        self,
        profile_id: str = "",
        candidate_id: str = "",
        analysis_id: str = "",
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 当前结构化推荐分析读取入口。"""
        target = self._endpoint(self._authorize_profile, token_payload, profile_id)
        return self._endpoint(self.analysis, target, candidate_id, analysis_id)

    def endpoint_conversation(
        self,
        profile_id: str = "",
        token_payload: schemas.TokenPayload = Depends(verify_token),
        mark_read: bool = False,
    ) -> Dict[str, Any]:
        """FastAPI CinePilot Agent 对话读取入口。"""
        target = self._endpoint(self._authorize_profile, token_payload, profile_id)
        actor_id = self._endpoint(self._feedback_actor_id, token_payload)
        return self._endpoint(self.conversation, target, actor_id, mark_read)

    def endpoint_conversation_status(
        self,
        profile_id: str = "",
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI CinePilot Agent 未读状态入口。"""
        target = self._endpoint(self._authorize_profile, token_payload, profile_id)
        actor_id = self._endpoint(self._feedback_actor_id, token_payload)
        return self._endpoint(self.conversation_status, target, actor_id)

    async def endpoint_conversation_message(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI CinePilot Agent 消息入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        actor_id = self._endpoint(self._feedback_actor_id, token_payload)
        return await self._endpoint_async(self.conversation_message, payload, actor_id)

    async def endpoint_retry_conversation_message(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI CinePilot Agent 失败草稿重试入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        actor_id = self._endpoint(self._feedback_actor_id, token_payload)
        return await self._endpoint_async(
            self.retry_conversation_message, payload, actor_id
        )

    def endpoint_respond_conversation_command(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI CinePilot Agent 命令确认或拒绝入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        actor_id = self._endpoint(self._feedback_actor_id, token_payload)
        return self._endpoint(
            self.respond_conversation_command,
            payload,
            actor_id,
            self._is_superuser(token_payload),
        )

    def endpoint_pending_center(
        self,
        profile_id: str = "",
        token_payload: schemas.TokenPayload = Depends(verify_token),
        view: str = "pending",
    ) -> Dict[str, Any]:
        """FastAPI 统一待确认中心读取入口。"""
        target = self._endpoint(self._authorize_profile, token_payload, profile_id)
        actor_id = self._endpoint(self._feedback_actor_id, token_payload)
        return self._endpoint(
            self.pending_center,
            target,
            view,
            actor_id,
            self._is_superuser(token_payload),
        )

    def endpoint_start_pending_interview(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 待办中心动态问询验收启动入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        actor_id = self._endpoint(self._feedback_actor_id, token_payload)
        return self._endpoint(self.start_pending_interview, payload, actor_id)

    def endpoint_respond_pending(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 统一待确认回答、拒绝与提醒入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        actor_id = self._endpoint(self._feedback_actor_id, token_payload)
        return self._endpoint(
            self.respond_pending,
            payload,
            actor_id,
            self._is_superuser(token_payload),
        )

    def endpoint_restore(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 恢复入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return self._endpoint(self.restore, payload)

    def endpoint_delete_archive(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 删除归档入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return self._endpoint(self.delete_archive, payload)

    def endpoint_clear_profile(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 清除画像入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return self._endpoint(self.clear_profile, payload)

    def endpoint_update_profile_tag(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 人工画像标签变更入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return self._endpoint(self.update_profile_tag, payload)

    def endpoint_attribution(
        self,
        profile_id: str = "",
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 结果归因读取入口。"""
        target = self._endpoint(self._authorize_profile, token_payload, profile_id)
        return self._endpoint(self.attribution, target)

    def endpoint_native_drawer_opened(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 原生订阅抽屉打开记录入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return self._endpoint(self.record_native_drawer_opened, payload)

    def endpoint_verify_attribution(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 结果归因主动复查入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return self._endpoint(self.verify_attribution, payload)

    def endpoint_subscribe(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 手动订阅入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return self._endpoint(self.subscribe, payload)

    def endpoint_learning_health(
        self,
        profile_id: str = "",
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 学习健康度读取入口。"""
        target = self._endpoint(self._authorize_profile, token_payload, profile_id)
        return self._endpoint(self.learning_health, target)

    def endpoint_record_exposure(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 榜单真实曝光记录入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return self._endpoint(self.record_exposure, payload)

    def endpoint_record_detail_opened(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 榜单详情打开记录入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return self._endpoint(self.record_detail_opened, payload)

    def endpoint_record_consumption_interaction(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 订阅与播放结果记录入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return self._endpoint(self.record_consumption_interaction, payload)
