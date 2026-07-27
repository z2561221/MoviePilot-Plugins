"""Agent榜单中心 bearer API 控制器与稳定响应契约。"""

import asyncio
from typing import Any, Dict, List, Mapping

from fastapi import Depends

from app import schemas
from app.core.security import verify_token

from ..model.config import configured_identities, default_config
from ..model.identity import EmbyIdentity
from ..service.archive import ArchiveService
from ..service.data_lifecycle import DataLifecycleError, DataLifecycleService
from ..service.profile_preferences import ProfilePreferenceService


class ApiContractError(Exception):
    """表示可映射为稳定 HTTP 错误的控制器异常。"""

    def __init__(self, status_code: int, code: str, message: str):
        """保存状态码、机器码和用户可读消息。"""
        self.status_code = int(status_code)
        self.code = str(code)
        self.message = str(message)
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """返回前端稳定错误对象。"""
        return {
            "success": False,
            "error": {"code": self.code, "message": self.message},
        }


def _http_error(error: ApiContractError) -> None:
    """在真实 FastAPI endpoint 边界惰性转换控制器错误。"""
    from fastapi import HTTPException

    raise HTTPException(status_code=error.status_code, detail=error.to_dict())


class AgentRankApiController:
    """验证 Emby 画像身份并协调只读与状态变更 API。"""

    def __init__(self, plugin: Any):
        """绑定运行中插件实例。"""
        self.plugin = plugin

    @staticmethod
    def _success(data: Any) -> Dict[str, Any]:
        """包装稳定成功响应。"""
        return {"success": True, "data": data}

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

    def _allowed_profile_ids(
        self, token_payload: schemas.TokenPayload
    ) -> List[str]:
        """返回当前 MP 用户显式允许访问的已配置画像身份。"""
        configured = list(self._identity_map())
        if self._is_superuser(token_payload):
            return configured
        user_id = self._token_user_id(token_payload)
        if not user_id:
            return []
        access_map = self.plugin._config.get("profile_access_map")
        raw_allowed = access_map.get(user_id) if isinstance(access_map, Mapping) else []
        return [
            profile_id
            for profile_id in raw_allowed or []
            if profile_id in configured
        ]

    def _authorize_profile(
        self, token_payload: schemas.TokenPayload, value: Any
    ) -> str:
        """校验当前 MP 用户对显式 profile_id 的访问权限。"""
        profile_id = str(value or "").strip()
        if not profile_id:
            raise ApiContractError(422, "profile_id_required", "必须指定 profile_id")
        if not self._is_superuser(token_payload):
            if profile_id not in self._allowed_profile_ids(token_payload):
                raise ApiContractError(403, "profile_forbidden", "无权访问该画像身份")
        return self._profile_id(profile_id)

    def _require_superuser(self, token_payload: schemas.TokenPayload) -> None:
        """限制包含完整插件配置和全部身份的接口只对超级用户开放。"""
        if not self._is_superuser(token_payload):
            raise ApiContractError(403, "superuser_required", "仅管理员可访问插件配置")

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

    def _data_lifecycle(self) -> DataLifecycleService:
        """返回绑定当前仓储和规范化配置的数据生命周期服务。"""
        return DataLifecycleService(self._repository(), self.plugin._config)

    def _repository(self) -> Any:
        """返回运行时仓库或抛出可见不可用错误。"""
        repository = getattr(self.plugin, "_repository", None)
        if repository is None:
            raise ApiContractError(503, "runtime_unavailable", "插件运行时尚未就绪")
        return repository

    def _board_data(self, board: Any) -> Dict[str, Any]:
        """返回海报已收敛为轻量 URL 的榜单响应。"""
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
                "archived_profile_tags": preferences.archived_entries(),
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
        self, token_payload: schemas.TokenPayload
    ) -> Dict[str, Any]:
        """按当前 MP 用户授权范围过滤状态中的画像身份信息。"""
        response = self.status()
        data = response["data"]
        allowed_ids = self._allowed_profile_ids(token_payload)
        identities = self._identity_map()
        data["profiles"] = [
            {
                "profile_id": profile_id,
                "username": identities[profile_id].username,
            }
            for profile_id in allowed_ids
        ]
        default_profile_id = str(data.get("default_profile_id") or "")
        if default_profile_id not in allowed_ids:
            data["default_profile_id"] = ""
            data["playback"] = None
        data["migration"] = self._migration_data(allowed_ids)
        data["data_lifecycle"] = self._data_lifecycle_data(allowed_ids)
        return response

    def config_options(self) -> Dict[str, Any]:
        """返回 Config 与 Emby 身份切换器需要的安全选项。"""
        from ..adapter.discovery import DiscoveryAdapter

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
                "source_options": DiscoveryAdapter.source_options(),
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

    async def refresh(self, payload: Any) -> Dict[str, Any]:
        """触发一次手动推荐并映射运行结果。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        self._require_enabled()
        runtime = getattr(self.plugin, "_runtime", None)
        if runtime is None:
            raise ApiContractError(503, "runtime_unavailable", "插件运行时尚未就绪")
        try:
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

    def archive(self, payload: Any) -> Dict[str, Any]:
        """忽略当前榜单中的一个推荐。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        candidate_id = self._candidate_id(body)
        result = ArchiveService(self._repository()).ignore(target, candidate_id)
        return self._success(result.__dict__)

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
            raise ApiContractError(409, "confirmation_required", "清除画像需要明确确认")
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
                500, "learning_reset_failed", "学习重置失败，旧数据已保留"
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
                500, "full_reset_prepare_failed", "无法生成彻底重置确认"
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
                500, "full_reset_failed", "彻底重置失败，旧数据已保留"
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

    async def playback_sync(self, payload: Any) -> Dict[str, Any]:
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
        return self._success(snapshot.to_dict())

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
        return self._success(result.__dict__)

    def _endpoint(self, method: Any, *args: Any) -> Any:
        """把纯控制器错误转换为 FastAPI HTTPException。"""
        try:
            return method(*args)
        except ApiContractError as error:
            _http_error(error)

    async def _endpoint_async(self, method: Any, *args: Any) -> Any:
        """异步执行纯控制器方法并转换 HTTP 错误。"""
        try:
            return await method(*args)
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
        """FastAPI 配置选项入口。"""
        self._endpoint(self._require_superuser, token_payload)
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
        return await self._endpoint_async(self.playback_sync, payload)

    def endpoint_archive(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 忽略入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return self._endpoint(self.archive, payload)

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

    def endpoint_subscribe(
        self,
        payload: dict,
        token_payload: schemas.TokenPayload = Depends(verify_token),
    ) -> Dict[str, Any]:
        """FastAPI 手动订阅入口。"""
        self._endpoint(self._authorize_payload_profile, token_payload, payload)
        return self._endpoint(self.subscribe, payload)


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
        ("/refresh", controller.endpoint_refresh, ["POST"], "刷新推荐榜单"),
        ("/playback/sync", controller.endpoint_playback_sync, ["POST"], "同步播放画像"),
        ("/archive", controller.endpoint_archive, ["POST"], "忽略推荐"),
        ("/restore", controller.endpoint_restore, ["POST"], "恢复推荐"),
        ("/archive/delete", controller.endpoint_delete_archive, ["POST"], "删除归档"),
        ("/profile/clear", controller.endpoint_clear_profile, ["POST"], "清除画像"),
        (
            "/profile/tags",
            controller.endpoint_update_profile_tag,
            ["POST"],
            "更新人工画像标签",
        ),
        ("/run-history", controller.endpoint_run_history, ["GET"], "获取运行历史"),
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
            "准备彻底重置",
        ),
        (
            "/data/reset/full",
            controller.endpoint_reset_full,
            ["POST"],
            "执行彻底重置",
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
        }
        for path, endpoint, methods, summary in specs
    ]


def status_response(plugin: Any) -> Dict[str, Any]:
    """兼容入口薄委托的状态响应。"""
    return AgentRankApiController(plugin).status()


def config_response(plugin: Any) -> Dict[str, Any]:
    """兼容入口薄委托的配置响应。"""
    return AgentRankApiController(plugin).config_options()
