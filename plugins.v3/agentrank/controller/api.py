"""Agent榜单中心 bearer API 控制器与稳定响应契约。"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping

from fastapi import Depends

from app import schemas
from app.core.security import verify_token

from .schemas import API_RESPONSE_MODELS
from ..model.config import configured_identities, default_config
from ..model.feedback import ShortTermSignal
from ..model.identity import EmbyIdentity
from ..service.archive import ArchiveService
from ..service.analysis_comment import AnalysisCommentError, AnalysisCommentService
from ..service.conversation import ConversationError, ConversationService
from ..service.data_lifecycle import DataLifecycleError, DataLifecycleService
from ..service.feedback_action import FeedbackActionError, FeedbackActionService
from ..service.feedback_queue import FeedbackQueueError, FeedbackQueueService
from ..service.feedback_proposal import FeedbackProposalService
from ..service.profile_preferences import ProfilePreferenceService
from ..service.prompt import configured_agent_display_name, effective_persona_prompt


class ApiContractError(Exception):
    """表示可映射为稳定 HTTP 错误的控制器异常。"""

    def __init__(self, status_code: int, code: str, message: str):
        """保存状态码、机器码和用户可读消息。"""
        self.status_code = int(status_code)
        self.code = str(code)
        self.message = str(message)
        super().__init__(self.message)

def _http_error(error: ApiContractError) -> None:
    """在真实 FastAPI endpoint 边界惰性转换控制器错误。"""
    from fastapi import HTTPException

    raise HTTPException(
        status_code=error.status_code,
        detail=error.message,
        headers={"X-AgentRank-Error-Code": error.code},
    )


class AgentRankApiController:
    """验证 Emby 画像身份并协调只读与状态变更 API。"""

    def __init__(self, plugin: Any):
        """绑定运行中插件实例。"""
        self.plugin = plugin

    @staticmethod
    def _success(data: Any) -> Dict[str, Any]:
        """保留纯控制器测试合同；FastAPI 边界会返回其中的业务对象。"""
        return {"success": True, "data": data}

    @staticmethod
    def _business_data(value: Any) -> Any:
        """从内部控制器结果提取 V3 endpoint 应直接返回的业务对象。"""
        if (
            isinstance(value, Mapping)
            and value.get("success") is True
            and "data" in value
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

    def status(self) -> Dict[str, Any]:
        """返回插件全局运行状态。"""
        runtime = getattr(self.plugin, "_runtime", None)
        default_profile_id = str(
            self.plugin._config.get("default_profile_id") or ""
        )
        enablement = self._enablement_data()
        state = (
            "ready"
            if self.plugin.get_state()
            else "blocked"
            if enablement.get("status") not in {"disabled", "stopped"}
            else "stopped"
        )
        if runtime is None and state != "blocked":
            state = "stopped"
        return self._success(
            {
                "enabled": bool(self.plugin.get_state()),
                "state": state,
                "plugin_version": self.plugin.plugin_version,
                "validation_errors": list(
                    self.plugin._config.get("_validation_errors") or []
                ),
                "default_profile_id": default_profile_id,
                "playback": self._playback_data(default_profile_id),
                "enablement": enablement,
                "migration": self._migration_data(),
                "data_lifecycle": self._data_lifecycle_data(),
            }
        )

    def status_for_token(
        self, _token_payload: schemas.TokenPayload
    ) -> Dict[str, Any]:
        """向任一已登录 MP 用户返回完整插件状态。"""
        response = self.status()
        data = response["data"]
        identities = self._identity_map()
        profile_ids = list(identities)
        data["profiles"] = [
            {
                "profile_id": profile_id,
                "username": identities[profile_id].username,
            }
            for profile_id in profile_ids
        ]
        data["migration"] = self._migration_data(profile_ids)
        data["data_lifecycle"] = self._data_lifecycle_data(profile_ids)
        return response

    def config_options(self) -> Dict[str, Any]:
        """返回 Config 与 Emby 身份切换器需要的安全选项。"""
        from ..service.notification_type import notification_type_options

        selected_identities = [
            identity.to_dict()
            for identity in configured_identities(self.plugin._config)
        ]
        identity_map = {
            identity["profile_id"]: identity for identity in selected_identities
        }
        access = getattr(self.plugin, "_emby_access", None)
        if access is not None and hasattr(access, "enumerate_identities"):
            try:
                for identity in access.enumerate_identities() or []:
                    identity_map[identity.profile_id] = identity.to_dict()
            except Exception:
                pass
        identities = list(identity_map.values())
        libraries = {}
        if access is not None and hasattr(access, "enumerate_libraries"):
            for identity_data in identities:
                try:
                    identity = EmbyIdentity.from_dict(identity_data)
                    libraries[identity.profile_id] = access.enumerate_libraries(identity)
                except Exception:
                    libraries[identity_data["profile_id"]] = []
        return self._success(
            {
                "emby_identities": identities,
                "emby_libraries": libraries,
                "default_profile_id": str(
                    self.plugin._config.get("default_profile_id") or ""
                ),
                "config": dict(self.plugin._config),
                "defaults": default_config(),
                "notification_type_options": notification_type_options(),
                "enablement": self._enablement_data(),
                "playback_status": {
                    identity["profile_id"]: self._playback_data(identity["profile_id"])
                    for identity in selected_identities
                    if getattr(self.plugin, "_playback_service", None) is not None
                },
            }
        )

    def overview(self, profile_id: Any) -> Dict[str, Any]:
        """返回一个 Emby 画像身份的画像、榜单和最近运行摘要。"""
        target = self._profile_id(profile_id)
        repository = self._repository()
        profile = repository.load_profile(target)
        board = repository.load_board(target)
        archive = repository.load_archive(target)
        history = repository.load_run_history(target)
        return self._success(
            {
                "profile_id": target,
                "username": self._display_name(target),
                "profile": self._profile_data(target, profile),
                "board": self._board_data(board) if board else None,
                "archive": archive.to_dict(),
                "latest_run": history[0].to_dict() if history else None,
                "history": [item.to_dict() for item in history[:15]],
                "history_total": len(history),
                "learning_health": repository.build_learning_health(target).to_dict(),
                "agent_display_name": configured_agent_display_name(
                    self.plugin._config.get("agent_display_name")
                ),
                "playback": self._playback_data(target),
                "enablement": self._enablement_data(),
                "migration": self._migration_data([target]),
                "data_lifecycle": self._data_lifecycle_data([target]),
            }
        )

    def board(self, profile_id: Any) -> Dict[str, Any]:
        """返回画像身份当前榜单或显式空榜单。"""
        target = self._profile_id(profile_id)
        board = self._repository().load_board(target)
        if board:
            return self._success(self._board_data(board))
        return self._success(
            {
                "profile_id": target,
                "username": self._display_name(target),
                "run_id": "",
                "status": "idle",
                "recommendations": [],
                "generated_at": "",
                "revision": 0,
                "message": "尚未生成榜单",
            }
        )

    def profile(self, profile_id: Any) -> Dict[str, Any]:
        """返回画像身份当前画像或显式空画像。"""
        target = self._profile_id(profile_id)
        profile = self._repository().load_profile(target)
        return self._success(self._profile_data(target, profile))

    def run_history(
        self, profile_id: Any, page: int = 1, page_size: int = 15
    ) -> Dict[str, Any]:
        """返回用户有界运行历史。"""
        target = self._profile_id(profile_id)
        items = self._repository().load_run_history(target)
        current_page = max(1, int(page or 1))
        current_page_size = max(1, min(int(page_size or 15), 50))
        start = (current_page - 1) * current_page_size
        paged_items = items[start : start + current_page_size]
        return self._success(
            {
                "profile_id": target,
                "username": self._display_name(target),
                "items": [item.to_dict() for item in paged_items],
                "total": len(items),
                "page": current_page,
                "page_size": current_page_size,
            }
        )

    def board_history(
        self, profile_id: Any, page: int = 1, page_size: int = 10
    ) -> Dict[str, Any]:
        """返回只读的历史榜单快照及相邻轮次变化摘要。"""
        target = self._profile_id(profile_id)
        repository = self._repository()
        boards = list(repository.load_board_history(target))
        legacy_fallback = False
        notice = ""
        if not boards:
            current = repository.load_board(target)
            if current is not None and current.recommendations:
                # 历史功能上线前没有快照时，至少让用户看到当前榜单，并明确标记起点。
                boards = [current]
                legacy_fallback = True
                notice = "历史榜单从本次开始记录，当前榜单为上线前的最后一轮。"
            else:
                notice = "榜单生成后，这里会记录每一轮的完整榜单。"
        runs = {
            run.run_id: run
            for run in repository.load_run_history(target)
            if str(run.run_id or "").strip()
        }
        board_by_run_id = {
            board.run_id: board
            for board in boards
            if str(board.run_id or "").strip()
        }
        def board_ids(value: Any) -> set[str]:
            """提取一轮榜单中非空且去重的候选标识。"""
            return {
                str(item.candidate_id or "").strip()
                for item in (value.recommendations if value else ())
                if str(item.candidate_id or "").strip()
            }

        def overlap_rate(current_ids: set[str], previous_ids: set[str]) -> float:
            """计算当前榜单与参照榜单的候选重合率。"""
            if not current_ids or not previous_ids:
                return 0.0
            return round(len(current_ids & previous_ids) / max(1, len(current_ids)), 4)

        items: List[Dict[str, Any]] = []
        for index, board in enumerate(boards):
            current_ids = board_ids(board)
            previous = board_by_run_id.get(str(board.previous_run_id or "").strip())
            if previous is None and index + 1 < len(boards):
                previous = boards[index + 1]
            previous_ids = board_ids(previous)
            older_ids = set().union(*(board_ids(value) for value in boards[index + 1 :]))
            return_count = len((current_ids & older_ids) - previous_ids)
            recent_rates = []
            for recent_index in range(index, min(len(boards) - 1, index + 5)):
                recent_current = board_ids(boards[recent_index])
                recent_previous = board_ids(boards[recent_index + 1])
                recent_rates.append(overlap_rate(recent_current, recent_previous))
            run = runs.get(board.run_id)
            metrics = dict(run.metrics or {}) if run is not None else {}
            consumption = repository.load_board_consumption(
                target, board.run_id, board.revision
            )
            board_data = self._board_snapshot_data(board)
            for item in board_data.get("recommendations") or []:
                candidate_id = str(item.get("candidate_id") or "").strip()
                item["history_state"] = (
                    "repeat" if candidate_id in previous_ids else "new"
                )
            items.append(
                {
                    "board": board_data,
                    "run": run.to_dict() if run is not None else None,
                    "new_count": len(current_ids - previous_ids),
                    "overlap_count": len(current_ids & previous_ids),
                    "previous_overlap_rate": overlap_rate(current_ids, previous_ids),
                    "return_count": return_count,
                    "returning_count": return_count,
                    "recent_average_overlap_rate": round(
                        sum(recent_rates) / len(recent_rates), 4
                    ) if recent_rates else 0.0,
                    "trigger_reason": str(
                        metrics.get("trigger_reason") or (
                            "legacy_snapshot" if legacy_fallback else "unknown"
                        )
                    ),
                    "exposed": bool(consumption.exposed) if consumption else False,
                    "exposure_count": int(consumption.exposure_count or 0) if consumption else 0,
                    "interacted": bool(consumption.interacted) if consumption else False,
                    "legacy_fallback": legacy_fallback,
                }
            )
        current_page = max(1, int(page or 1))
        current_page_size = max(1, min(int(page_size or 10), 50))
        start = (current_page - 1) * current_page_size
        return self._success(
            {
                "profile_id": target,
                "username": self._display_name(target),
                "items": items[start : start + current_page_size],
                "total": len(items),
                "page": current_page,
                "page_size": current_page_size,
                "notice": notice,
                "legacy_fallback": legacy_fallback,
            }
        )

    async def refresh(self, payload: Any) -> Dict[str, Any]:
        """立即受理一次后台手动推荐。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        self._require_enabled()
        runtime = getattr(self.plugin, "_runtime", None)
        if runtime is None:
            raise ApiContractError(503, "runtime_unavailable", "插件运行时尚未就绪")
        try:
            starter = getattr(runtime, "start_refresh", None)
            if callable(starter):
                progress = starter(target)
                return self._success(dict(progress or {}))
            result = await runtime.refresh(target)
        except Exception as error:
            raise ApiContractError(502, "refresh_failed", f"榜单刷新失败：{error}") from error
        return self._success(
            {
                "profile_id": target,
                "username": self._display_name(target),
                "status": result.status,
                "message": getattr(result, "message", ""),
                "run_id": getattr(result, "run_id", ""),
                "final_count": int(getattr(result, "final_count", 0) or 0),
            }
        )

    def run_progress(self, profile_id: Any) -> Dict[str, Any]:
        """返回页面刷新后仍可读取的榜单生成进度。"""
        target = self._profile_id(profile_id)
        runtime = getattr(self.plugin, "_runtime", None)
        if runtime is None or not callable(getattr(runtime, "run_progress", None)):
            raise ApiContractError(503, "runtime_unavailable", "插件运行时尚未就绪")
        return self._success(runtime.run_progress(target))

    def feedback(self, payload: Any, actor_id: str = "") -> Dict[str, Any]:
        """通过统一事实入口记录喜欢、不喜欢或忽略。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        candidate_id = self._candidate_id(body)
        try:
            result = FeedbackActionService(
                self._repository(),
                analysis_limit=int(
                    self.plugin._config.get("analysis_record_limit") or 500
                ),
            ).act(
                profile_id=target,
                candidate_id=candidate_id,
                kind=str(body.get("kind") or ""),
                idempotency_key=str(body.get("idempotency_key") or ""),
                actor_id=actor_id,
                analysis_id=str(body.get("analysis_id") or ""),
                expected_board_revision=body.get("board_revision"),
                expected_run_id=str(body.get("run_id") or ""),
                defer_polarity_side_effects=True,
            )
        except FeedbackActionError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "feedback_failed", "反馈保存失败，榜单与归档已恢复"
            ) from error
        try:
            queue_job = (
                None
                if result.event.kind == "neutral"
                else self._feedback_queue().enqueue_event(
                    result.event,
                    delay_seconds=(
                        float(
                            self.plugin._config.get(
                                "feedback_debounce_seconds", 30.0
                            )
                        )
                        if result.event.kind in {"like", "dislike"}
                        else 0.0
                    ),
                    debounce_profile=result.event.kind in {"like", "dislike"},
                )
            )
        except FeedbackQueueError as error:
            raise ApiContractError(
                503,
                "feedback_queue_failed",
                "反馈已保存，但理解任务入队失败；可使用原操作重试",
            ) from error
        data = result.to_dict()
        data["queue_status"] = queue_job.status if queue_job is not None else "cancelled"
        data["queue_job"] = queue_job.to_public_dict() if queue_job is not None else None
        short_term = None
        try:
            # FeedbackActionResult 已在同一事务中返回动作后的真实榜单上下文；
            # 不要再使用客户端可能携带的旧 revision，避免把学习投影写入错误版本。
            result_board_run_id = str(
                getattr(result, "board_run_id", "")
                or result.event.run_id
                or ""
            )
            result_board_revision = max(
                1,
                int(
                    getattr(result, "board_revision", 0)
                    or 1
                ),
            )
            if result.event.kind in {"like", "dislike"}:
                self._repository().record_board_interaction(
                    target,
                    result_board_run_id,
                    result_board_revision,
                    result.event.kind,
                    datetime.now(timezone.utc).isoformat(),
                )
                short_term = self._append_short_term_signal(
                    profile_id=target,
                    kind=result.event.kind,
                    idempotency_key=f"feedback:{result.event.idempotency_key}",
                    candidate_id=result.event.candidate_id,
                    run_id=result_board_run_id,
                    board_revision=result_board_revision,
                    source="structured_feedback",
                    strength=0.95 if result.event.kind == "like" else -1.0,
                    decay_days=60,
                )
            elif result.event.kind == "ignore":
                self._repository().record_board_interaction(
                    target,
                    result_board_run_id,
                    result_board_revision,
                    "ignore",
                    datetime.now(timezone.utc).isoformat(),
                )
        except Exception as error:
            # 反馈事实已经成功落账；把学习投影错误留在响应中，避免重复提交写入。
            short_term = {
                "created": False,
                "error": "short_term_signal_failed",
                "message": str(error)[:160],
            }
        data["short_term"] = short_term
        return self._success(data)

    def analysis_comment(self, payload: Any, actor_id: str = "") -> Dict[str, Any]:
        """记录一条绑定当前结构化分析的用户评论并异步修订。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        candidate_id = self._candidate_id(body)
        try:
            result = AnalysisCommentService(
                self._repository(),
                analysis_limit=int(
                    self.plugin._config.get("analysis_record_limit") or 500
                ),
            ).submit(
                profile_id=target,
                candidate_id=candidate_id,
                analysis_id=str(body.get("analysis_id") or ""),
                comment=str(body.get("comment") or ""),
                idempotency_key=str(body.get("idempotency_key") or ""),
                actor_id=actor_id,
                expected_board_revision=body.get("board_revision"),
                expected_run_id=str(body.get("run_id") or ""),
            )
        except AnalysisCommentError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "analysis_comment_failed", "评论保存失败，请刷新后重试"
            ) from error
        try:
            queue_job = self._feedback_queue().enqueue_event(result.event)
        except FeedbackQueueError as error:
            raise ApiContractError(
                503,
                "analysis_comment_queue_failed",
                "评论已保存，但分析修订任务入队失败；可使用原操作重试",
            ) from error
        data = result.to_dict()
        data["queue_status"] = queue_job.status
        data["queue_job"] = queue_job.to_public_dict()
        return self._success(data)

    def analysis(
        self,
        profile_id: Any,
        candidate_id: Any,
        analysis_id: Any,
    ) -> Dict[str, Any]:
        """返回当前榜单候选绑定的结构化分析，拒绝读取过期版本。"""
        target = self._profile_id(profile_id)
        candidate = str(candidate_id or "").strip()
        requested_analysis = str(analysis_id or "").strip()
        if not candidate or not requested_analysis:
            raise ApiContractError(
                422,
                "analysis_identity_required",
                "缺少推荐分析标识，请刷新榜单后重试",
            )
        board = self._repository().load_board(target)
        if board is None:
            raise ApiContractError(409, "board_unavailable", "当前没有可读取的推荐榜单")
        item = next(
            (
                value
                for value in board.recommendations
                if value.candidate_id == candidate
            ),
            None,
        )
        if item is None or item.analysis_id != requested_analysis:
            raise ApiContractError(
                409,
                "analysis_revision_conflict",
                "推荐分析已更新，请刷新榜单后重试",
            )
        record = next(
            (
                value
                for value in self._repository().load_recommendation_analyses(
                    target, board.run_id
                )
                if value.analysis_id == requested_analysis
                and value.candidate_id == candidate
                and value.status == "active"
            ),
            None,
        )
        if record is None:
            raise ApiContractError(
                404,
                "analysis_unavailable",
                "当前推荐分析不可用，请刷新榜单后重试",
            )
        return self._success(record.to_dict())

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
            if all(hasattr(error, name) for name in ("status_code", "code", "message")):
                raise ApiContractError(
                    error.status_code, error.code, error.message
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
            if all(hasattr(error, name) for name in ("status_code", "code", "message")):
                raise ApiContractError(
                    error.status_code, error.code, error.message
                ) from error
            raise ApiContractError(
                500, "pending_center_write_failed", "待确认操作失败，原状态已保留"
            ) from error
        return self._success(data)

    def archive(self, payload: Any, actor_id: str = "") -> Dict[str, Any]:
        """兼容旧忽略入口，并把动作接入统一反馈事实。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        candidate_id = self._candidate_id(body)
        board = self._repository().load_board(target)
        if board is None:
            raise ApiContractError(409, "board_unavailable", "当前没有可操作的推荐榜单")
        idempotency_key = str(body.get("idempotency_key") or "").strip()
        if not idempotency_key:
            idempotency_key = (
                f"legacy-ignore:{target}:{board.run_id}:{board.revision}:{candidate_id}"
            )
        request = dict(body)
        request.update(
            {
                "kind": "ignore",
                "idempotency_key": idempotency_key,
                "run_id": str(body.get("run_id") or board.run_id),
            }
        )
        return self.feedback(request, actor_id)

    def restore(self, payload: Any) -> Dict[str, Any]:
        """恢复一个已忽略推荐。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        candidate_id = self._candidate_id(body)
        result = ArchiveService(self._repository()).restore(target, candidate_id)
        return self._success(result.__dict__)

    def delete_archive(self, payload: Any) -> Dict[str, Any]:
        """永久删除一条归档反馈但不恢复榜单。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        candidate_id = self._candidate_id(body)
        result = ArchiveService(self._repository()).delete_archive(target, candidate_id)
        return self._success(result.__dict__)

    def clear_profile(self, payload: Any) -> Dict[str, Any]:
        """经明确确认后原子清除用户画像和榜单。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        if body.get("confirm") is not True:
            raise ApiContractError(409, "confirmation_required", "重建画像需要明确确认")
        result = ArchiveService(self._repository()).clear_profile(target)
        return self._success(result.__dict__)

    def data_export(self, profile_id: Any) -> Dict[str, Any]:
        """返回当前 profile 的字段白名单脱敏导出。"""
        target = self._profile_id(profile_id)
        try:
            data = self._data_lifecycle().export_profile(target)
        except DataLifecycleError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "data_export_failed", "数据导出失败，旧数据未被修改"
            ) from error
        return self._success(data)

    def reset_learning(self, payload: Any) -> Dict[str, Any]:
        """经明确确认后仅重置 AgentRank 学习数据。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            data = self._data_lifecycle().reset_learning(
                target, body.get("confirm") is True
            )
        except DataLifecycleError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "learning_reset_failed", "重置交互学习失败，旧数据已保留"
            ) from error
        return self._success(data)

    def prepare_full_reset(
        self, payload: Any, requester_id: str
    ) -> Dict[str, Any]:
        """为彻底重置签发绑定当前 MP 用户的短时确认令牌。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            data = self._data_lifecycle().prepare_full_reset(target, requester_id)
        except DataLifecycleError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "full_reset_prepare_failed", "无法生成清空全部数据确认"
            ) from error
        return self._success(data)

    def reset_full(self, payload: Any, requester_id: str) -> Dict[str, Any]:
        """校验一次性令牌后彻底删除 AgentRank 自有 profile 数据。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            data = self._data_lifecycle().reset_full(
                target,
                requester_id,
                str(body.get("confirmation_token") or ""),
            )
        except DataLifecycleError as error:
            raise ApiContractError(
                error.status_code, error.code, error.message
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "full_reset_failed", "清空全部数据失败，旧数据已保留"
            ) from error
        return self._success(data)

    def update_profile_tag(self, payload: Any) -> Dict[str, Any]:
        """添加或删除当前用户的人工偏好或避雷标签。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            result = ProfilePreferenceService(self._repository()).update(
                profile_id=target,
                kind=str(body.get("kind") or "").strip(),
                action=str(body.get("action") or "").strip(),
                raw_tag=body.get("tag"),
            )
        except ValueError as error:
            raise ApiContractError(422, "invalid_profile_tag", str(error)) from error
        profile = self._repository().load_profile(target)
        return self._success(
            {
                "changed": result.changed,
                "action": result.action,
                "kind": result.kind,
                "tag": result.tag,
                "profile": self._profile_data(target, profile),
            }
        )

    async def playback_sync(self, payload: Any, actor_id: str = "") -> Dict[str, Any]:
        """立即同步指定用户播放画像并返回数据源状态。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        service = getattr(self.plugin, "_playback_service", None)
        if service is None:
            raise ApiContractError(503, "playback_unavailable", "播放画像服务尚未就绪")
        try:
            snapshot = await asyncio.to_thread(service.collect, target, self.plugin._config)
        except Exception as error:
            raise ApiContractError(502, "playback_sync_failed", "播放画像同步失败") from error
        calibration_event = None
        calibration_created = False
        try:
            calibration_event, calibration_created = FeedbackProposalService(
                self._repository(),
                record_limit=int(
                    self.plugin._config.get("analysis_record_limit") or 500
                ),
                persona_prompt=effective_persona_prompt(
                    self.plugin._config.get("persona_preset"),
                    self.plugin._config.get("persona_prompt"),
                ),
                interaction_mode=str(
                    self.plugin._config.get("interaction_mode") or "auto"
                ),
            ).create_playback_calibration(
                target,
                snapshot,
                actor_id=actor_id,
            )
        except Exception:
            calibration_event = None
            calibration_created = False
        if calibration_event is not None and calibration_created:
            try:
                self._feedback_queue().enqueue_event(calibration_event)
            except Exception:
                calibration_created = False
        data = snapshot.to_dict()
        data["calibration_created"] = calibration_created
        data["calibration_event_id"] = (
            calibration_event.event_id if calibration_event is not None else ""
        )
        data["calibration_question_id"] = ""
        data["learning_health"] = self._repository().build_learning_health(target).to_dict()
        return self._success(data)

    def start_pending_interview(
        self, payload: Any, actor_id: str = ""
    ) -> Dict[str, Any]:
        """启动由反馈 Agent 逐题生成的待办中心问询验收。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        request_key = str(body.get("idempotency_key") or "").strip()
        if not request_key or len(request_key) > 256:
            raise ApiContractError(
                422, "idempotency_key_invalid", "问询验收缺少有效幂等标识"
            )
        try:
            total = int(body.get("total") or 10)
        except (TypeError, ValueError) as error:
            raise ApiContractError(
                422, "interview_total_invalid", "问询题数必须是整数"
            ) from error
        if not 1 <= total <= 10:
            raise ApiContractError(
                422, "interview_total_invalid", "问询题数必须介于 1 到 10"
            )
        snapshot = self._repository().load_playback_snapshot(target)
        if snapshot is None:
            raise ApiContractError(
                409, "playback_unavailable", "当前没有可用于动态问询的播放画像"
            )
        event, created = FeedbackProposalService(
            self._repository(),
            record_limit=int(
                self.plugin._config.get("analysis_record_limit") or 500
            ),
            persona_prompt=effective_persona_prompt(
                self.plugin._config.get("persona_preset"),
                self.plugin._config.get("persona_prompt"),
            ),
            interaction_mode=str(
                self.plugin._config.get("interaction_mode") or "auto"
            ),
        ).create_pending_interview(
            target,
            snapshot,
            self._repository().load_board(target),
            actor_id=actor_id,
            idempotency_key=request_key,
            total=total,
        )
        if event is None:
            raise ApiContractError(
                409,
                "pending_question_exists",
                "请先回答或关闭当前待办问题，再启动问询验收",
            )
        try:
            job = self._feedback_queue().enqueue_event(event)
        except FeedbackQueueError as error:
            raise ApiContractError(
                503,
                "feedback_queue_failed",
                "问询事件已保存，但 Agent 任务入队失败；可使用原请求重试",
            ) from error
        return self._success(
            {
                "profile_id": target,
                "event_id": event.event_id,
                "created": created,
                "total": total,
                "queue_status": job.status,
                "memory_delta": {},
            }
        )

    def subscribe(self, payload: Any) -> Dict[str, Any]:
        """通过运行时安全链创建单项手动订阅。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        self._require_enabled()
        candidate_id = self._candidate_id(body)
        runtime = getattr(self.plugin, "_runtime", None)
        service = getattr(runtime, "subscription_service", None) if runtime else None
        if service is None:
            raise ApiContractError(409, "subscription_not_ready", "手动订阅安全链尚未就绪")
        result = service.subscribe(
            target,
            candidate_id,
            float(self.plugin._config.get("confidence_threshold") or 0.0),
        )
        if not result.success:
            raise ApiContractError(409, result.code, result.message)
        short_term = None
        board = self._repository().load_board(target)
        if board is not None and any(
            item.candidate_id == candidate_id for item in board.recommendations
        ):
            observed_at = datetime.now(timezone.utc).isoformat()
            try:
                self._repository().record_board_interaction(
                    target,
                    board.run_id,
                    board.revision,
                    "subscribe",
                    observed_at,
                )
                short_term = self._append_short_term_signal(
                    profile_id=target,
                    kind="subscribe",
                    idempotency_key=(
                        str(body.get("idempotency_key") or "").strip()
                        or f"subscribe:{board.run_id}:{board.revision}:{candidate_id}"
                    ),
                    candidate_id=candidate_id,
                    run_id=board.run_id,
                    board_revision=board.revision,
                    source="moviepilot_subscription",
                    strength=0.8,
                    decay_days=90,
                )
            except Exception as error:
                short_term = {
                    "created": False,
                    "error": "short_term_signal_failed",
                    "message": str(error)[:160],
                }
        data = dict(result.__dict__)
        data["short_term"] = short_term
        return self._success(data)

    def attribution(self, profile_id: Any) -> Dict[str, Any]:
        """返回指定 profile 的安全结果归因记录。"""
        target = self._profile_id(profile_id)
        try:
            records = self._attribution_service().public_records(target)
        except ApiContractError:
            raise
        except Exception as error:
            raise ApiContractError(
                500, "attribution_read_failed", "结果归因读取失败"
            ) from error
        return self._success({"profile_id": target, "records": records})

    def record_native_drawer_opened(self, payload: Any) -> Dict[str, Any]:
        """仅记录原生订阅抽屉已打开，不把返回值解释为订阅成功。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        candidate_id = self._candidate_id(body)
        try:
            record = self._attribution_service().record_native_drawer_opened(
                target, candidate_id
            )
        except ApiContractError:
            raise
        except ValueError as error:
            raise ApiContractError(
                409,
                "attribution_candidate_unavailable",
                "当前推荐已变化，请刷新榜单后重试",
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "attribution_record_failed", "原生订阅交互记录失败"
            ) from error
        return self._success(record.to_public_dict())

    def verify_attribution(self, payload: Any) -> Dict[str, Any]:
        """立即复查指定 profile 的订阅、入库和播放事实。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            result = self._attribution_service().verify_profile(target)
        except ApiContractError:
            raise
        except Exception as error:
            raise ApiContractError(
                500,
                "attribution_verification_failed",
                "结果归因暂时无法复查，已保留上次可信状态",
            ) from error
        return self._success(result.to_dict())

    def learning_health(self, profile_id: Any) -> Dict[str, Any]:
        """返回当前 profile 的短期学习、确认记忆和归因覆盖摘要。"""
        target = self._profile_id(profile_id)
        return self._success(self._repository().build_learning_health(target).to_dict())

    def record_exposure(self, payload: Any) -> Dict[str, Any]:
        """记录当前榜单实际进入页面可见区的一次曝光。"""
        body = self._payload(payload)
        target, board, revision = self._board_context(body)
        raw_ids = body.get("candidate_ids")
        if raw_ids is None:
            candidate_ids = [item.candidate_id for item in board.recommendations]
        elif isinstance(raw_ids, (list, tuple, set)):
            candidate_ids = [str(item or "").strip() for item in raw_ids]
        else:
            candidate_ids = None
        if candidate_ids is None or any(not item for item in candidate_ids):
            raise ApiContractError(422, "candidate_ids_invalid", "candidate_ids 必须是候选标识数组")
        allowed = {item.candidate_id for item in board.recommendations}
        if any(item not in allowed for item in candidate_ids):
            raise ApiContractError(409, "candidate_not_on_board", "曝光候选不属于当前榜单")
        try:
            consumption = self._repository().record_board_exposure(
                target,
                board.run_id,
                revision,
                candidate_ids,
                datetime.now(timezone.utc).isoformat(),
            )
            health = self._repository().build_learning_health(target)
        except Exception as error:
            raise ApiContractError(500, "exposure_record_failed", "榜单曝光记录失败") from error
        return self._success(
            {
                "consumption": consumption.to_dict(),
                "learning_health": health.to_dict(),
            }
        )

    def record_detail_opened(self, payload: Any) -> Dict[str, Any]:
        """记录当前榜单候选详情被用户打开，并生成中等强度短期信号。"""
        body = self._payload(payload)
        candidate_id = self._candidate_id(body)
        target, board, revision = self._board_context(body, candidate_id=candidate_id)
        observed_at = datetime.now(timezone.utc).isoformat()
        try:
            consumption = self._repository().record_board_detail_opened(
                target,
                board.run_id,
                revision,
                candidate_id,
                observed_at,
            )
            signal = self._append_short_term_signal(
                profile_id=target,
                kind="detail_opened",
                idempotency_key=f"detail:{board.run_id}:{revision}:{candidate_id}",
                candidate_id=candidate_id,
                run_id=board.run_id,
                board_revision=revision,
                source="agentrank_detail",
                strength=0.3,
                decay_days=30,
            )
        except Exception as error:
            raise ApiContractError(500, "detail_record_failed", "详情打开记录失败") from error
        return self._success(
            {"consumption": consumption.to_dict(), "short_term": signal}
        )

    def record_consumption_interaction(self, payload: Any) -> Dict[str, Any]:
        """记录订阅或播放结果等榜单消费状态，并写入对应短期信号。"""
        body = self._payload(payload)
        candidate_id = self._candidate_id(body)
        kind = str(body.get("kind") or "").strip().casefold()
        signal_config = {
            "subscribe": (0.8, 90, "moviepilot_subscription"),
            "playback_start": (0.45, 30, "playback_reporting"),
            "playback_completed": (0.95, 90, "playback_reporting"),
            "playback_abandoned": (-0.35, 30, "playback_reporting"),
        }
        if kind not in signal_config:
            raise ApiContractError(422, "invalid_consumption_kind", "不支持的榜单消费状态")
        target, board, revision = self._board_context(body, candidate_id=candidate_id)
        observed_at = datetime.now(timezone.utc).isoformat()
        strength, decay_days, source = signal_config[kind]
        idempotency_key = (
            str(body.get("idempotency_key") or "").strip()
            or f"consumption:{kind}:{board.run_id}:{revision}:{candidate_id}"
        )
        try:
            consumption = self._repository().record_board_interaction(
                target, board.run_id, revision, kind, observed_at
            )
            signal = self._append_short_term_signal(
                profile_id=target,
                kind=kind,
                idempotency_key=idempotency_key,
                candidate_id=candidate_id,
                run_id=board.run_id,
                board_revision=revision,
                source=source,
                strength=strength,
                decay_days=decay_days,
            )
        except Exception as error:
            raise ApiContractError(500, "consumption_record_failed", "榜单消费状态记录失败") from error
        return self._success(
            {"consumption": consumption.to_dict(), "short_term": signal}
        )

    def _endpoint(self, method: Any, *args: Any) -> Any:
        """把纯控制器错误转换为 FastAPI HTTPException。"""
        try:
            return self._business_data(method(*args))
        except ApiContractError as error:
            _http_error(error)

    async def _endpoint_async(self, method: Any, *args: Any) -> Any:
        """异步执行纯控制器方法并转换 HTTP 错误。"""
        try:
            return self._business_data(await method(*args))
        except ApiContractError as error:
            _http_error(error)

    def endpoint_status(
        self, token_payload: schemas.TokenPayload = Depends(verify_token)
    ) -> Dict[str, Any]:
        """FastAPI 状态入口。"""
        return self._endpoint(self.status_for_token, token_payload)

    def endpoint_config_options(
        self, token_payload: schemas.TokenPayload = Depends(verify_token)
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


def build_api_routes(plugin: Any) -> List[Dict[str, Any]]:
    """构建全部 bearer 前端 API 路由。"""
    controller = AgentRankApiController(plugin)
    plugin._api_controller = controller
    specs = [
        ("/status", controller.endpoint_status, ["GET"], "获取插件状态"),
        ("/overview", controller.endpoint_overview, ["GET"], "获取用户总览"),
        ("/config/options", controller.endpoint_config_options, ["GET"], "获取配置选项"),
        ("/board", controller.endpoint_board, ["GET"], "获取推荐榜单"),
        ("/profile", controller.endpoint_profile, ["GET"], "获取用户画像"),
        ("/run-progress", controller.endpoint_run_progress, ["GET"], "获取实时运行进度"),
        ("/refresh", controller.endpoint_refresh, ["POST"], "刷新推荐榜单"),
        ("/playback/sync", controller.endpoint_playback_sync, ["POST"], "同步播放画像"),
        ("/attribution", controller.endpoint_attribution, ["GET"], "获取结果归因"),
        (
            "/attribution/native-drawer-opened",
            controller.endpoint_native_drawer_opened,
            ["POST"],
            "记录原生订阅抽屉已打开",
        ),
        (
            "/attribution/verify",
            controller.endpoint_verify_attribution,
            ["POST"],
            "复查订阅入库播放结果",
        ),
        ("/archive", controller.endpoint_archive, ["POST"], "忽略推荐"),
        ("/feedback", controller.endpoint_feedback, ["POST"], "记录三态反馈"),
        ("/analysis", controller.endpoint_analysis, ["GET"], "获取当前结构化推荐分析"),
        (
            "/analysis/comment",
            controller.endpoint_analysis_comment,
            ["POST"],
            "评论并修订 Agent 分析",
        ),
        ("/conversation", controller.endpoint_conversation, ["GET"], "获取 CinePilot Agent 对话"),
        (
            "/conversation/status",
            controller.endpoint_conversation_status,
            ["GET"],
            "获取 CinePilot Agent 未读状态",
        ),
        (
            "/conversation/messages",
            controller.endpoint_conversation_message,
            ["POST"],
            "发送 CinePilot Agent 消息",
        ),
        (
            "/conversation/messages/retry",
            controller.endpoint_retry_conversation_message,
            ["POST"],
            "重试 CinePilot Agent 消息",
        ),
        (
            "/conversation/commands/respond",
            controller.endpoint_respond_conversation_command,
            ["POST"],
            "确认或拒绝 CinePilot Agent 命令",
        ),
        (
            "/pending",
            controller.endpoint_pending_center,
            ["GET"],
            "获取统一待处理中心",
        ),
        (
            "/pending/interview/start",
            controller.endpoint_start_pending_interview,
            ["POST"],
            "启动待办中心动态问询验收",
        ),
        (
            "/pending/respond",
            controller.endpoint_respond_pending,
            ["POST"],
            "回答、拒绝或稍后处理待确认项目",
        ),
        ("/restore", controller.endpoint_restore, ["POST"], "恢复推荐"),
        ("/archive/delete", controller.endpoint_delete_archive, ["POST"], "删除归档"),
        ("/profile/clear", controller.endpoint_clear_profile, ["POST"], "重建画像"),
        (
            "/profile/tags",
            controller.endpoint_update_profile_tag,
            ["POST"],
            "更新人工画像标签",
        ),
        ("/run-history", controller.endpoint_run_history, ["GET"], "获取运行历史"),
        ("/board-history", controller.endpoint_board_history, ["GET"], "获取历史榜单"),
        ("/learning-health", controller.endpoint_learning_health, ["GET"], "获取学习健康度"),
        ("/consumption/exposure", controller.endpoint_record_exposure, ["POST"], "记录榜单真实曝光"),
        ("/consumption/detail-opened", controller.endpoint_record_detail_opened, ["POST"], "记录榜单详情打开"),
        (
            "/consumption/interaction",
            controller.endpoint_record_consumption_interaction,
            ["POST"],
            "记录订阅与播放结果",
        ),
        ("/data/export", controller.endpoint_data_export, ["GET"], "导出脱敏数据"),
        (
            "/data/reset/learning",
            controller.endpoint_reset_learning,
            ["POST"],
            "仅重置学习数据",
        ),
        (
            "/data/reset/full/prepare",
            controller.endpoint_prepare_full_reset,
            ["POST"],
            "准备清空全部数据",
        ),
        (
            "/data/reset/full",
            controller.endpoint_reset_full,
            ["POST"],
            "执行清空全部数据",
        ),
        ("/subscribe", controller.endpoint_subscribe, ["POST"], "手动订阅推荐"),
    ]
    return [
        {
            "path": path,
            "endpoint": endpoint,
            "methods": methods,
            "auth": "bear",
            "summary": summary,
            "response_model": API_RESPONSE_MODELS[path],
        }
        for path, endpoint, methods, summary in specs
    ]


def status_response(plugin: Any) -> Dict[str, Any]:
    """兼容入口薄委托的状态响应。"""
    controller = AgentRankApiController(plugin)
    return controller._business_data(controller.status())


def config_response(plugin: Any) -> Dict[str, Any]:
    """兼容入口薄委托的配置响应。"""
    controller = AgentRankApiController(plugin)
    return controller._business_data(controller.config_options())
