"""Agent榜单中心 bearer API 控制器与稳定响应契约。"""

from typing import Any, Dict, List, Mapping

from ..model.config import default_config
from ..service.archive import ArchiveService


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
    """验证参与用户并协调只读与状态变更 API。"""

    def __init__(self, plugin: Any):
        """绑定运行中插件实例。"""
        self.plugin = plugin

    @staticmethod
    def _success(data: Any) -> Dict[str, Any]:
        """包装稳定成功响应。"""
        return {"success": True, "data": data}

    def _username(self, value: Any) -> str:
        """要求显式用户名且必须属于参与用户。"""
        username = str(value or "").strip()
        if not username:
            raise ApiContractError(422, "username_required", "必须指定参与推荐的用户名")
        users = list(self.plugin._config.get("users") or [])
        if username not in users:
            raise ApiContractError(404, "unknown_user", "用户不在 Agent 榜单参与列表中")
        return username

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

    def status(self) -> Dict[str, Any]:
        """返回插件全局运行状态。"""
        runtime = getattr(self.plugin, "_runtime", None)
        return self._success(
            {
                "enabled": bool(self.plugin.get_state()),
                "state": "ready" if runtime is not None else "stopped",
                "plugin_version": self.plugin.plugin_version,
                "validation_errors": list(
                    self.plugin._config.get("_validation_errors") or []
                ),
            }
        )

    def config_options(self) -> Dict[str, Any]:
        """返回 Config 与用户切换器需要的选项和生效配置。"""
        return self._success(
            {
                "users": list(self.plugin._config.get("users") or []),
                "default_user": str(self.plugin._config.get("default_user") or ""),
                "config": dict(self.plugin._config),
                "defaults": default_config(),
            }
        )

    def overview(self, username: Any) -> Dict[str, Any]:
        """返回一个用户的画像、榜单和最近运行摘要。"""
        target = self._username(username)
        repository = self._repository()
        profile = repository.load_profile(target)
        board = repository.load_board(target)
        history = repository.load_run_history(target)
        return self._success(
            {
                "username": target,
                "profile": profile.to_dict() if profile else None,
                "board": board.to_dict() if board else None,
                "latest_run": history[0].to_dict() if history else None,
            }
        )

    def board(self, username: Any) -> Dict[str, Any]:
        """返回用户当前榜单或显式空榜单。"""
        target = self._username(username)
        board = self._repository().load_board(target)
        if board:
            return self._success(board.to_dict())
        return self._success(
            {
                "username": target,
                "run_id": "",
                "status": "idle",
                "recommendations": [],
                "generated_at": "",
                "message": "尚未生成榜单",
            }
        )

    def profile(self, username: Any) -> Dict[str, Any]:
        """返回用户当前画像或显式空画像。"""
        target = self._username(username)
        profile = self._repository().load_profile(target)
        if profile:
            return self._success(profile.to_dict())
        return self._success(
            {
                "username": target,
                "summary": "",
                "tags": [],
                "negative_tags": [],
                "subscription_count": 0,
                "run_id": "",
                "generated_at": "",
            }
        )

    def run_history(self, username: Any) -> Dict[str, Any]:
        """返回用户有界运行历史。"""
        target = self._username(username)
        items = self._repository().load_run_history(target)
        return self._success(
            {"username": target, "items": [item.to_dict() for item in items]}
        )

    async def refresh(self, payload: Any) -> Dict[str, Any]:
        """触发一次手动推荐并映射运行结果。"""
        body = self._payload(payload)
        target = self._username(body.get("username"))
        runtime = getattr(self.plugin, "_runtime", None)
        if runtime is None:
            raise ApiContractError(503, "runtime_unavailable", "插件运行时尚未就绪")
        try:
            result = await runtime.refresh(target)
        except Exception as error:
            raise ApiContractError(502, "refresh_failed", f"榜单刷新失败：{error}") from error
        return self._success(
            {
                "username": target,
                "status": result.status,
                "message": getattr(result, "message", ""),
                "run_id": getattr(result, "run_id", ""),
                "final_count": int(getattr(result, "final_count", 0) or 0),
            }
        )

    def archive(self, payload: Any) -> Dict[str, Any]:
        """忽略当前榜单中的一个推荐。"""
        body = self._payload(payload)
        target = self._username(body.get("username"))
        candidate_id = self._candidate_id(body)
        result = ArchiveService(self._repository()).ignore(target, candidate_id)
        return self._success(result.__dict__)

    def restore(self, payload: Any) -> Dict[str, Any]:
        """恢复一个已忽略推荐。"""
        body = self._payload(payload)
        target = self._username(body.get("username"))
        candidate_id = self._candidate_id(body)
        result = ArchiveService(self._repository()).restore(target, candidate_id)
        return self._success(result.__dict__)

    def delete_archive(self, payload: Any) -> Dict[str, Any]:
        """永久删除一条归档反馈但不恢复榜单。"""
        body = self._payload(payload)
        target = self._username(body.get("username"))
        candidate_id = self._candidate_id(body)
        result = ArchiveService(self._repository()).delete_archive(target, candidate_id)
        return self._success(result.__dict__)

    def clear_profile(self, payload: Any) -> Dict[str, Any]:
        """经明确确认后原子清除用户画像和榜单。"""
        body = self._payload(payload)
        target = self._username(body.get("username"))
        if body.get("confirm") is not True:
            raise ApiContractError(409, "confirmation_required", "清除画像需要明确确认")
        result = ArchiveService(self._repository()).clear_profile(target)
        return self._success(result.__dict__)

    def subscribe(self, payload: Any) -> Dict[str, Any]:
        """保留手动订阅路由，具体安全链由后续任务接入。"""
        body = self._payload(payload)
        self._username(body.get("username"))
        self._candidate_id(body)
        raise ApiContractError(409, "subscription_not_ready", "手动订阅安全链尚未就绪")

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

    def endpoint_overview(self, username: str = "") -> Dict[str, Any]:
        """FastAPI 总览入口。"""
        return self._endpoint(self.overview, username)

    def endpoint_board(self, username: str = "") -> Dict[str, Any]:
        """FastAPI 榜单入口。"""
        return self._endpoint(self.board, username)

    def endpoint_profile(self, username: str = "") -> Dict[str, Any]:
        """FastAPI 画像入口。"""
        return self._endpoint(self.profile, username)

    def endpoint_run_history(self, username: str = "") -> Dict[str, Any]:
        """FastAPI 运行历史入口。"""
        return self._endpoint(self.run_history, username)

    async def endpoint_refresh(self, payload: dict) -> Dict[str, Any]:
        """FastAPI 手动刷新入口。"""
        return await self._endpoint_async(self.refresh, payload)

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
        ("/archive", controller.endpoint_archive, ["POST"], "忽略推荐"),
        ("/restore", controller.endpoint_restore, ["POST"], "恢复推荐"),
        ("/archive/delete", controller.endpoint_delete_archive, ["POST"], "删除归档"),
        ("/profile/clear", controller.endpoint_clear_profile, ["POST"], "清除画像"),
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
