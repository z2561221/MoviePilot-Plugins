"""同步删除配置选项、只读预览、历史与受管理权限保护的重试入口。"""

from functools import partial
from typing import Annotated, Any

from app import schemas
from app.schemas.common import JsonData
from app.sdk.security import verify_token
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..adapter.sync_delete import SyncDeleteAdapter
from ..model.sync_delete import JOBS_KEY, DeleteRejected, config_for, event_snapshot
from ..service.sync_delete import build_plan


class PreviewRequest(BaseModel):
    """只预览指定媒体路径，不接受前端下发删除文件清单。"""
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=4096)
    server: str = ""
    media_source: str = ""
    media_id: str = ""


class RetryRequest(BaseModel):
    """重试只能引用当前实例已保存的任务。"""
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(min_length=1, max_length=64)


class PlanResult(BaseModel):
    """只读规划或任务受理回执，accepted 不代表执行完成。"""
    plan: dict[str, JsonData] = Field(default_factory=dict)
    job_id: str = ""
    accepted: bool = False


class HistoryResult(BaseModel):
    """分页返回当前实例的同步删除记录。"""
    items: list[dict[str, JsonData]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 15
    enabled: bool = False
    worker_running: bool = False


class OptionsResult(BaseModel):
    """供配置界面选择的非敏感服务名称。"""
    servers: list[str] = Field(default_factory=list)
    storages: list[str] = Field(default_factory=lambda: ["115网盘Plus"])


def _require_admin(token):
    """涉及全局媒体路径预览/破坏性重试，仅允许超管或宿主 API key 身份。"""
    if not getattr(token, "super_user", False):
        raise HTTPException(status_code=403, detail="同步删除预览和重试需要管理员权限")


def options(plugin) -> OptionsResult:
    """读取可用 Emby 服务，不回传服务器连接凭据。"""
    return OptionsResult(servers=SyncDeleteAdapter(plugin, config_for(plugin)).servers())


def preview(plugin, payload: PreviewRequest, token: Annotated[schemas.TokenPayload, Depends(verify_token)]):
    """配置预览允许媒体仍存在，不执行删除、标记或队列写入。"""
    _require_admin(token)
    try:
        event = event_snapshot({"event": "deep.delete", "channel": "emby", "item_path": payload.path,
                                "server_name": payload.server, "media_source": payload.media_source,
                                "media_id": payload.media_id})
        plan = build_plan(plugin, event, config_for(plugin), preview=True)
        return schemas.Response[PlanResult](success=True, data=PlanResult(plan=plan))
    except DeleteRejected as error:
        return schemas.Response[PlanResult](success=False, message=str(error), data=PlanResult())


def history(plugin, page: int = 1, page_size: int = 15) -> HistoryResult:
    """只读历史不初始化执行器，也不恢复未决任务。"""
    page, page_size = max(1, page), max(1, min(50, page_size))
    jobs = plugin.get_data(JOBS_KEY) or {}
    rows = sorted(jobs.values(), key=lambda row: row.get("updated_at", 0), reverse=True)
    offset = (page - 1) * page_size
    runtime = getattr(plugin, "_sync_delete_runtime", None)
    return HistoryResult(items=rows[offset:offset + page_size], total=len(rows), page=page, page_size=page_size,
                         enabled=bool(getattr(plugin, "_enabled", False) and getattr(plugin, "_sync_delete_enabled", False)),
                         worker_running=bool(runtime and not runtime.stop.is_set() and runtime.thread and runtime.thread.is_alive()))


def retry(plugin, payload: RetryRequest, token: Annotated[schemas.TokenPayload, Depends(verify_token)]):
    """只重试服务端快照，队列执行前再次验证配置与文件/任务身份。"""
    _require_admin(token)
    try:
        runtime = getattr(plugin, "_sync_delete_runtime", None)
        if runtime is None:
            raise DeleteRejected("同步删除执行器未运行")
        job_id = runtime.submit(None, job_id=payload.job_id)
        return schemas.Response[PlanResult](success=True, data=PlanResult(job_id=job_id, accepted=True))
    except DeleteRejected as error:
        return schemas.Response[PlanResult](success=False, message=str(error), data=PlanResult())


def routes(plugin) -> list[dict[str, Any]]:
    """沿用插件实例认证 API，所有响应显式声明模型。"""
    return [
        {"path": "/sync_delete/options", "endpoint": partial(options, plugin), "auth": "bear", "methods": ["GET"],
         "summary": "获取同步删除服务选项", "response_model": OptionsResult},
        {"path": "/sync_delete/preview", "endpoint": partial(preview, plugin), "auth": "bear", "methods": ["POST"],
         "summary": "只读预览同步删除关联", "response_model": schemas.Response[PlanResult]},
        {"path": "/sync_delete/history", "endpoint": partial(history, plugin), "auth": "bear", "methods": ["GET"],
         "summary": "获取同步删除历史", "response_model": HistoryResult},
        {"path": "/sync_delete/retry", "endpoint": partial(retry, plugin), "auth": "bear", "methods": ["POST"],
         "summary": "重试未完成的同步删除任务", "response_model": schemas.Response[PlanResult]},
    ]
