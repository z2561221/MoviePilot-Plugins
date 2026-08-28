"""Agent榜单中心 bearer API 控制器与稳定响应契约。"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping

from app import schemas

from .attribution_api import AttributionApiMixin
from .conversation_api import ConversationApiMixin
from .data_api import DataApiMixin
from .endpoints import AgentRankApiEndpointMixin
from .errors import ApiContractError, http_error
from .feedback_api import FeedbackApiMixin
from .read_api import ReadApiMixin
from .routes import (
    build_api_routes as build_routes,
    config_response as build_config_response,
    status_response as build_status_response,
)
from ..model.config import configured_identities
from ..model.feedback import ShortTermSignal
from ..service.conversation import ConversationService
from ..service.data_lifecycle import DataLifecycleService
from ..service.feedback_action import FeedbackActionService
from ..service.feedback_queue import FeedbackQueueService
from ..service.feedback_proposal import FeedbackProposalService
from ..service.prompt import configured_agent_display_name, effective_persona_prompt


def _http_error(error: ApiContractError) -> None:
    """保留原公开函数名并委托统一 HTTP 错误转换。"""
    http_error(error)


class AgentRankApiController(
    AgentRankApiEndpointMixin,
    ReadApiMixin,
    FeedbackApiMixin,
    ConversationApiMixin,
    DataApiMixin,
    AttributionApiMixin,
):
    """验证 Emby 画像身份并协调只读与状态变更 API。"""

    def __init__(self, plugin: Any):
        """绑定运行中插件实例。"""
        self.plugin = plugin

    @staticmethod
    def _success(data: Any) -> Dict[str, Any]:
        """返回严格三字段的内部成功 envelope。"""
        return {"success": True, "message": "", "data": data}

    @staticmethod
    def _business_data(value: Any) -> Any:
        """从内部控制器结果提取 V3 endpoint 应直接返回的业务对象。"""
        if (
            isinstance(value, Mapping)
            and set(value) == {"success", "message", "data"}
            and value.get("success") is True
        ):
            return value.get("data")
        return value

    def _identity_map(self) -> Dict[str, Any]:
        """返回配置中以 profile_id 索引的受控 Emby identity。"""
        return {
            identity.profile_id: identity
            for identity in configured_identities(self.plugin._config)
        }

    def _profile_id(self, value: Any) -> str:
        """要求显式 profile_id 且必须属于受控 Emby identity。"""
        profile_id = str(value or "").strip()
        if not profile_id:
            raise ApiContractError(422, "profile_id_required", "必须指定 profile_id")
        if profile_id not in self._identity_map():
            raise ApiContractError(404, "unknown_profile", "画像身份不在已选 Emby 用户中")
        return profile_id

    @staticmethod
    def _is_superuser(token_payload: schemas.TokenPayload) -> bool:
        """判断宿主鉴权载荷是否明确声明超级用户。"""
        return bool(getattr(token_payload, "super_user", False))

    @staticmethod
    def _token_user_id(token_payload: schemas.TokenPayload) -> str:
        """返回规范化 MP 用户 ID；普通用户缺少 ID 时默认拒绝。"""
        raw_user_id = getattr(token_payload, "sub", None)
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            return ""
        return str(user_id) if user_id > 0 else ""

    def _requester_id(self, token_payload: schemas.TokenPayload) -> str:
        """生成只用于危险动作确认绑定的稳定 MP 操作者标识。"""
        user_id = self._token_user_id(token_payload)
        if user_id:
            return f"mp-user:{user_id}"
        if self._is_superuser(token_payload):
            username = str(getattr(token_payload, "username", "") or "admin").strip()
            return f"mp-superuser:{username or 'admin'}"
        return ""

    def _feedback_actor_id(self, token_payload: schemas.TokenPayload) -> str:
        """返回反馈事实使用的 MP 用户标识。"""
        user_id = self._token_user_id(token_payload)
        if user_id:
            return user_id
        if self._is_superuser(token_payload):
            return str(getattr(token_payload, "username", "") or "admin").strip()
        return ""

    def _authorize_profile(
        self, _token_payload: schemas.TokenPayload, value: Any
    ) -> str:
        """允许任一已登录 MP 用户访问显式配置的画像身份。"""
        return self._profile_id(value)

    def _authorize_payload_profile(
        self, token_payload: schemas.TokenPayload, payload: Any
    ) -> None:
        """在状态变更前校验请求体中的显式画像身份。"""
        body = self._payload(payload)
        self._authorize_profile(token_payload, body.get("profile_id"))

    def _display_name(self, profile_id: str) -> str:
        """返回 profile_id 对应的安全 Emby 显示名。"""
        identity = self._identity_map().get(str(profile_id or ""))
        return identity.username if identity is not None else ""

    def _enablement_data(self) -> Dict[str, Any]:
        """返回安全的插件启用门禁状态与各 identity 探测结果。"""
        raw = getattr(self.plugin, "_enablement", None)
        if not isinstance(raw, Mapping):
            enabled = bool(self.plugin.get_state())
            return {
                "requested": enabled,
                "allowed": enabled,
                "status": "ready" if enabled else "stopped",
                "message": "" if enabled else "插件当前未运行",
                "capabilities": {},
            }
        value = dict(raw)
        capabilities = value.get("capabilities")
        value["capabilities"] = {
            str(profile_id): dict(capability)
            for profile_id, capability in (capabilities or {}).items()
            if isinstance(capability, Mapping)
        }
        return value

    def _migration_data(self, profile_ids: Any = None) -> Dict[str, Any]:
        """返回只含状态、计数和可授权 profile 的安全迁移摘要。"""
        raw = getattr(self.plugin, "_migration_status", None)
        if not isinstance(raw, Mapping):
            return {
                "status": "not_initialized",
                "profile_count": 0,
                "failure_count": 0,
                "profiles": [],
            }
        allowed = None if profile_ids is None else set(profile_ids)
        profiles: List[Dict[str, Any]] = []
        for item in raw.get("profiles") or []:
            if not isinstance(item, Mapping):
                continue
            profile_id = str(item.get("profile_id") or "").strip()
            if not profile_id or (allowed is not None and profile_id not in allowed):
                continue
            observed = item.get("observed")
            profiles.append(
                {
                    "profile_id": profile_id,
                    "status": str(item.get("status") or "unknown"),
                    "created_keys": [
                        str(key)
                        for key in item.get("created_keys") or []
                        if str(key) in {"feedback_event_index", "preference_memory"}
                    ],
                    "observed": {
                        str(key): value
                        for key, value in dict(observed or {}).items()
                        if isinstance(value, (bool, int))
                    },
                    "error": str(item.get("error") or ""),
                }
            )
        status = str(raw.get("status") or "not_initialized")
        if allowed is not None and status in {"ready", "partial_failed"}:
            status = (
                "partial_failed"
                if any(item["status"] == "failed" for item in profiles)
                else "ready"
            )
        return {
            "status": status,
            "profile_count": len(profiles),
            "failure_count": sum(item["status"] == "failed" for item in profiles),
            "profiles": profiles,
        }

    def _data_lifecycle_data(self, profile_ids: Any = None) -> Dict[str, Any]:
        """返回按授权 profile 过滤的数据保留运行状态。"""
        raw = getattr(self.plugin, "_data_lifecycle_status", None)
        allowed = None if profile_ids is None else set(profile_ids)
        profiles = []
        if isinstance(raw, Mapping):
            for item in raw.get("profiles") or []:
                if not isinstance(item, Mapping):
                    continue
                profile_id = str(item.get("profile_id") or "").strip()
                if not profile_id or (allowed is not None and profile_id not in allowed):
                    continue
                profiles.append(
                    {
                        "profile_id": profile_id,
                        "status": str(item.get("status") or "unknown"),
                        "message": str(item.get("message") or ""),
                        "pruned": {
                            str(key): int(value)
                            for key, value in dict(item.get("pruned") or {}).items()
                            if isinstance(value, int) and value >= 0
                        },
                        "retention_failures": [
                            str(value)
                            for value in item.get("retention_failures") or []
                            if str(value)
                            in {
                                "candidate_snapshots",
                                "feedback_events",
                                "feedback_queue",
                                "conversation_messages",
                                "attribution",
                                "analysis",
                            }
                        ],
                    }
                )
        policy = DataLifecycleService(
            getattr(self.plugin, "_repository", None), self.plugin._config
        ).policy.to_dict()
        status = str(dict(raw or {}).get("status") or "not_initialized")
        if allowed is not None and status in {"ready", "partial_failed"}:
            status = (
                "partial_failed"
                if any(item["status"] == "failed" for item in profiles)
                else "ready"
            )
        return {
            "status": status,
            "profiles": profiles,
            "retention_policy": policy,
        }

    def _require_enabled(self) -> None:
        """拒绝在硬依赖未满足时执行会产生副作用的操作。"""
        if self.plugin.get_state():
            return
        enablement = self._enablement_data()
        raise ApiContractError(
            409,
            "plugin_blocked",
            str(enablement.get("message") or "插件当前不可用"),
        )

    def _payload(self, value: Any) -> Mapping[str, Any]:
        """要求 POST 请求体为对象。"""
        if not isinstance(value, Mapping):
            raise ApiContractError(422, "invalid_payload", "请求体必须是 JSON 对象")
        return value

    def _candidate_id(self, payload: Mapping[str, Any]) -> str:
        """读取必填候选标识。"""
        candidate_id = str(payload.get("candidate_id") or "").strip()
        if not candidate_id:
            raise ApiContractError(422, "candidate_id_required", "必须指定 candidate_id")
        return candidate_id

    def _board_context(
        self, payload: Mapping[str, Any], *, candidate_id: str = ""
    ) -> tuple[str, Any, int]:
        """校验事件是否仍绑定当前榜单的 run_id 与 revision。"""
        target = self._profile_id(payload.get("profile_id"))
        board = self._repository().load_board(target)
        if board is None:
            raise ApiContractError(409, "board_unavailable", "当前没有可记录的推荐榜单")
        run_id = str(payload.get("run_id") or "").strip()
        if not run_id:
            raise ApiContractError(422, "run_id_required", "必须指定榜单 run_id")
        if run_id != board.run_id:
            raise ApiContractError(409, "board_run_conflict", "榜单已刷新，请基于最新榜单重试")
        raw_revision = payload.get("board_revision", payload.get("revision"))
        try:
            revision = int(raw_revision)
        except (TypeError, ValueError) as error:
            raise ApiContractError(422, "invalid_board_revision", "榜单 revision 必须是整数") from error
        if revision != board.revision:
            raise ApiContractError(409, "board_revision_conflict", "榜单状态已变化，请刷新后重试")
        if candidate_id and not any(
            item.candidate_id == candidate_id for item in board.recommendations
        ):
            raise ApiContractError(409, "candidate_not_on_board", "候选已不在当前榜单中")
        return target, board, revision

    def _append_short_term_signal(
        self,
        *,
        profile_id: str,
        kind: str,
        idempotency_key: str,
        candidate_id: str = "",
        run_id: str = "",
        board_revision: int = 0,
        source: str,
        strength: float,
        decay_days: int,
    ) -> Dict[str, Any]:
        """写入一条按行为类型分层衰减的短期信号并刷新健康度。"""
        observed_at = datetime.now(timezone.utc).isoformat()
        signal = ShortTermSignal(
            profile_id=profile_id,
            kind=kind,
            idempotency_key=idempotency_key,
            candidate_id=candidate_id,
            run_id=run_id,
            board_revision=board_revision,
            strength=strength,
            decay_days=decay_days,
            observed_at=observed_at,
            source=source,
        )
        stored, created = self._repository().append_short_term_signal(signal)
        health = self._repository().build_learning_health(profile_id)
        return {
            "signal": stored.to_dict(),
            "created": created,
            "learning_health": health.to_dict(),
        }

    def _data_lifecycle(self) -> DataLifecycleService:
        """返回绑定当前仓储和规范化配置的数据生命周期服务。"""
        return DataLifecycleService(self._repository(), self.plugin._config)

    def _repository(self) -> Any:
        """返回运行时仓库或抛出可见不可用错误。"""
        repository = getattr(self.plugin, "_repository", None)
        if repository is None:
            raise ApiContractError(503, "runtime_unavailable", "插件运行时尚未就绪")
        return repository

    def _feedback_queue(self) -> FeedbackQueueService:
        """返回运行时队列；测试或早期调用时创建仅持久化的队列门面。"""
        queue = getattr(self.plugin, "_feedback_queue", None)
        if queue is None:
            queue = FeedbackQueueService(
                self._repository(),
                profile_ids=self._identity_map(),
                queue_limit=int(
                    self.plugin._config.get("feedback_queue_limit") or 200
                ),
            )
            self.plugin._feedback_queue = queue
        return queue

    def _conversation_service(self) -> ConversationService:
        """返回运行时 CinePilot Agent 对话服务或创建等价门面。"""
        service = getattr(self.plugin, "_conversation", None)
        if service is None:
            from ..adapter.agent import AgentRankAgentAdapter

            service = ConversationService(
                self._repository(),
                AgentRankAgentAdapter(),
                plugin=self.plugin,
                message_limit=int(
                    self.plugin._config.get("conversation_message_limit") or 200
                ),
                agent_name=configured_agent_display_name(
                    self.plugin._config.get("agent_display_name")
                ),
                persona_prompt=effective_persona_prompt(
                    self.plugin._config.get("persona_preset"),
                    self.plugin._config.get("persona_prompt"),
                ),
            )
            self.plugin._conversation = service
        return service

    def _pending_center_service(self) -> Any:
        """返回统一待确认中心或用现有受控服务创建门面。"""
        service = getattr(self.plugin, "_pending_center", None)
        if service is None:
            from ..service.feedback_response import FeedbackResponseService
            from ..service.memory_projection import MemoryProjectionService
            from ..service.pending_center import PendingCenterService

            feedback_response = getattr(self.plugin, "_feedback_response", None)
            if feedback_response is None:
                feedback_response = FeedbackResponseService(
                    self._repository(), feedback_queue=self._feedback_queue()
                )
                self.plugin._feedback_response = feedback_response
            memory_projection = getattr(self.plugin, "_memory_projection", None)
            if memory_projection is None:
                memory_projection = MemoryProjectionService(self._repository())
                self.plugin._memory_projection = memory_projection
            service = PendingCenterService(
                self._repository(),
                feedback_response=feedback_response,
                memory_projection=memory_projection,
                conversation=self._conversation_service(),
                persona_prompt=effective_persona_prompt(
                    self.plugin._config.get("persona_preset"),
                    self.plugin._config.get("persona_prompt"),
                ),
                agent_name=configured_agent_display_name(
                    self.plugin._config.get("agent_display_name")
                ),
            )
            self.plugin._pending_center = service

        runtime = getattr(self.plugin, "_runtime", None)
        interaction = getattr(runtime, "interaction_service", None)
        resolver = getattr(interaction, "resolve_pending_item", None)
        setter = getattr(service, "set_resolution_handler", None)
        if callable(resolver) and callable(setter):
            setter(resolver)
        return service

    def _attribution_service(self) -> Any:
        """返回运行时结果归因服务，未就绪时显式失败。"""
        service = getattr(self.plugin, "_attribution_service", None)
        if service is None:
            runtime = getattr(self.plugin, "_runtime", None)
            service = getattr(runtime, "attribution_service", None)
        if service is None:
            raise ApiContractError(
                503, "attribution_unavailable", "结果归因服务尚未就绪"
            )
        return service

    def _board_data(self, board: Any) -> Dict[str, Any]:
        """返回带最新反馈极性且海报已收敛为轻量 URL 的榜单响应。"""
        value = board.to_dict()
        polarity = FeedbackActionService(self._repository()).active_polarities(
            board.profile_id, board.run_id
        )
        for item in value.get("recommendations") or []:
            item["feedback_kind"] = polarity.get(str(item.get("candidate_id") or ""), "")
        attribution_service = getattr(self.plugin, "_attribution_service", None)
        if attribution_service is not None:
            attributions = {
                item.candidate_id: item.to_public_dict()
                for item in attribution_service.list_records(board.profile_id)
                if item.run_id == board.run_id
            }
            for item in value.get("recommendations") or []:
                item["outcome_attribution"] = attributions.get(
                    str(item.get("candidate_id") or "")
                )
        consumption = self._repository().load_board_consumption(
            board.profile_id, board.run_id, board.revision
        )
        value["consumption"] = consumption.to_dict() if consumption is not None else None
        service = getattr(self.plugin, "_poster_service", None)
        return service.enrich_board(value) if service is not None else value

    def _board_snapshot_data(self, board: Any) -> Dict[str, Any]:
        """返回不绑定当前反馈状态的历史榜单快照。"""
        value = board.to_dict()
        service = getattr(self.plugin, "_poster_service", None)
        return service.enrich_board(value) if service is not None else value

    def _playback_data(self, profile_id: str) -> Any:
        """返回带安全 Emby 显示名的播放状态。"""
        service = getattr(self.plugin, "_playback_service", None)
        if service is None or not profile_id:
            return None
        value = service.status(profile_id).to_dict()
        value["profile_id"] = profile_id
        value["username"] = self._display_name(profile_id)
        return value

    def _profile_data(self, profile_id: str, profile: Any = None) -> Dict[str, Any]:
        """合并 Agent 原始画像与人工标签覆盖层。"""
        value = (
            profile.to_dict()
            if profile is not None
            else {
                "profile_id": profile_id,
                "username": self._display_name(profile_id),
                "summary": "",
                "tags": [],
                "negative_tags": [],
                "playback_count": 0,
                "run_id": "",
                "generated_at": "",
            }
        )
        value["profile_id"] = profile_id
        value["username"] = self._display_name(profile_id)
        preferences = self._repository().load_profile_preferences(profile_id)
        memory = self._repository().load_preference_memory(profile_id)
        agent_tags = preferences.active_agent_tags(value.get("tags") or [])
        agent_negative_tags = preferences.active_agent_negative_tags(
            value.get("negative_tags") or []
        )
        value.update(
            {
                "agent_tags": agent_tags,
                "agent_negative_tags": agent_negative_tags,
                "tags": preferences.effective_tags(agent_tags),
                "negative_tags": preferences.effective_negative_tags(
                    agent_negative_tags
                ),
                "custom_tags": list(preferences.custom_tags),
                "custom_negative_tags": list(preferences.custom_negative_tags),
                "archived_tags": list(preferences.archived_tags),
                "archived_negative_tags": list(
                    preferences.archived_negative_tags
                ),
                "legacy_config_evidence": list(
                    preferences.legacy_config_evidence
                ),
                "archived_profile_tags": preferences.archived_entries(),
                "questioning_state": FeedbackProposalService(
                    self._repository()
                ).questioning_state(profile_id, memory=memory),
            }
        )
        return value
def build_api_routes(plugin: Any) -> List[Dict[str, Any]]:
    """委托独立路由注册模块。"""
    return build_routes(plugin, AgentRankApiController)


def status_response(plugin: Any) -> Dict[str, Any]:
    """兼容入口薄委托的状态响应。"""
    return build_status_response(plugin, AgentRankApiController)


def config_response(plugin: Any) -> Dict[str, Any]:
    """兼容入口薄委托的配置响应。"""
    return build_config_response(plugin, AgentRankApiController)
