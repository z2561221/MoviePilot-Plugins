"""Agent榜单中心 bearer API 控制器与稳定响应契约。"""

import asyncio
from typing import Any, Dict, List, Mapping

from ..model.config import configured_identities, default_config
from ..service.archive import ArchiveService
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

    def _display_name(self, profile_id: str) -> str:
        """返回 profile_id 对应的安全 Emby 显示名。"""
        identity = self._identity_map().get(str(profile_id or ""))
        return identity.username if identity is not None else ""

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
                "subscription_count": 0,
                "run_id": "",
                "generated_at": "",
            }
        )
        value["profile_id"] = profile_id
        value["username"] = self._display_name(profile_id)
        preferences = self._repository().load_profile_preferences(profile_id)
        agent_tags = list(value.get("tags") or [])
        agent_negative_tags = list(value.get("negative_tags") or [])
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
                "suppressed_tags": list(preferences.suppressed_tags),
                "suppressed_negative_tags": list(
                    preferences.suppressed_negative_tags
                ),
            }
        )
        return value

    def status(self) -> Dict[str, Any]:
        """返回插件全局运行状态。"""
        runtime = getattr(self.plugin, "_runtime", None)
        default_profile_id = str(
            self.plugin._config.get("default_profile_id") or ""
        )
        return self._success(
            {
                "enabled": bool(self.plugin.get_state()),
                "state": "ready" if runtime is not None else "stopped",
                "plugin_version": self.plugin.plugin_version,
                "validation_errors": list(
                    self.plugin._config.get("_validation_errors") or []
                ),
                "default_profile_id": default_profile_id,
                "playback": self._playback_data(default_profile_id),
            }
        )

    def config_options(self) -> Dict[str, Any]:
        """返回 Config 与 Emby 身份切换器需要的安全选项。"""
        identities = [
            identity.to_dict()
            for identity in configured_identities(self.plugin._config)
        ]
        return self._success(
            {
                "emby_identities": identities,
                "default_profile_id": str(
                    self.plugin._config.get("default_profile_id") or ""
                ),
                "config": dict(self.plugin._config),
                "defaults": default_config(),
                "playback_status": {
                    identity["profile_id"]: self._playback_data(identity["profile_id"])
                    for identity in identities
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

    def endpoint_status(self) -> Dict[str, Any]:
        """FastAPI 状态入口。"""
        return self._endpoint(self.status)

    def endpoint_config_options(self) -> Dict[str, Any]:
        """FastAPI 配置选项入口。"""
        return self._endpoint(self.config_options)

    def endpoint_overview(self, profile_id: str = "") -> Dict[str, Any]:
        """FastAPI 总览入口。"""
        return self._endpoint(self.overview, profile_id)

    def endpoint_board(self, profile_id: str = "") -> Dict[str, Any]:
        """FastAPI 榜单入口。"""
        return self._endpoint(self.board, profile_id)

    def endpoint_profile(self, profile_id: str = "") -> Dict[str, Any]:
        """FastAPI 画像入口。"""
        return self._endpoint(self.profile, profile_id)

    def endpoint_run_history(
        self, profile_id: str = "", page: int = 1, page_size: int = 15
    ) -> Dict[str, Any]:
        """FastAPI 运行历史入口。"""
        return self._endpoint(self.run_history, profile_id, page, page_size)

    async def endpoint_refresh(self, payload: dict) -> Dict[str, Any]:
        """FastAPI 手动刷新入口。"""
        return await self._endpoint_async(self.refresh, payload)

    async def endpoint_playback_sync(self, payload: dict) -> Dict[str, Any]:
        """FastAPI 播放画像立即同步入口。"""
        return await self._endpoint_async(self.playback_sync, payload)

    def endpoint_archive(self, payload: dict) -> Dict[str, Any]:
        """FastAPI 忽略入口。"""
        return self._endpoint(self.archive, payload)

    def endpoint_restore(self, payload: dict) -> Dict[str, Any]:
        """FastAPI 恢复入口。"""
        return self._endpoint(self.restore, payload)

    def endpoint_delete_archive(self, payload: dict) -> Dict[str, Any]:
        """FastAPI 删除归档入口。"""
        return self._endpoint(self.delete_archive, payload)

    def endpoint_clear_profile(self, payload: dict) -> Dict[str, Any]:
        """FastAPI 清除画像入口。"""
        return self._endpoint(self.clear_profile, payload)

    def endpoint_update_profile_tag(self, payload: dict) -> Dict[str, Any]:
        """FastAPI 人工画像标签变更入口。"""
        return self._endpoint(self.update_profile_tag, payload)

    def endpoint_subscribe(self, payload: dict) -> Dict[str, Any]:
        """FastAPI 手动订阅入口。"""
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
