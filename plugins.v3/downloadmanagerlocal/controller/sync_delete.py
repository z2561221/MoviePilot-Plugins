"""同步删除配置选项、只读预览、历史与受管理权限保护的重试入口。"""

from contextlib import nullcontext
from functools import partial
from typing import Annotated, Any

from app import schemas
from app.schemas.common import JsonData
from app.sdk.security import verify_token
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..adapter.sync_delete import SyncDeleteAdapter
from ..model.sync_delete import BLOCKS_KEY, DeleteRejected, config_for, event_snapshot
from ..model.sync_delete_review import (
    dismissal_rejection,
    retry_rejection,
    review_revision,
)
from ..service.coordination import operation_lock
from ..service.sync_delete_planner import build_plan
from ..storage.sync_delete_jobs import DeleteJobStore


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


class DismissRequest(RetryRequest):
    """忽略绑定已读取的记录修订，兼容旧界面传入的原因。"""
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(default="用户忽略", min_length=1, max_length=300)


class DismissResult(BaseModel):
    """仅记录忽略状态，不表示媒体删除成功。"""
    job_id: str = ""
    state: str = ""


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


def history(plugin, page: int = 1, page_size: int = 15, pending_only: bool = False) -> HistoryResult:
    """只读历史不初始化执行器，也不恢复未决任务。"""
    page, page_size = max(1, page), max(1, min(50, page_size))
    total, rows = DeleteJobStore(plugin).page(page, page_size, pending_only=pending_only)
    runtime = getattr(plugin, "_sync_delete_runtime", None)
    enabled = bool(getattr(plugin, "_enabled", False) and getattr(plugin, "_sync_delete_enabled", False))
    config = config_for(plugin)
    blocks = plugin.get_data(BLOCKS_KEY)
    for job in rows:
        retry_reason = retry_rejection(job, config)
        if not retry_reason and (not enabled or not runtime or runtime.stop.is_set()):
            retry_reason = "同步删除执行器未运行，请先启用同步删除"
        dismiss_reason = dismissal_rejection(job, {} if blocks is None else blocks)
        job["review"] = {"revision": review_revision(job), "retry_allowed": not retry_reason,
                         "retry_reason": retry_reason, "dismiss_allowed": not dismiss_reason,
                         "dismiss_reason": dismiss_reason}
    return HistoryResult(items=rows, total=total, page=page, page_size=page_size,
                         enabled=enabled,
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


def dismiss(plugin, payload: DismissRequest, token: Annotated[schemas.TokenPayload, Depends(verify_token)]):
    """管理员忽略未开始的旧告警；不会调用执行器或解除任务保护。"""
    _require_admin(token)
    guard = operation_lock(plugin)
    if not guard.acquire(blocking=False):
        return schemas.Response[DismissResult](success=False, message="有任务正在处理，请稍后刷新", data=DismissResult())
    try:
        runtime = getattr(plugin, "_sync_delete_runtime", None)
        with runtime.lock if runtime else nullcontext():
            job = DeleteJobStore(plugin).dismiss(payload.job_id, payload.expected_revision,
                                                payload.reason, str(getattr(token, "username", "") or "管理员"))
        return schemas.Response[DismissResult](success=True, data=DismissResult(job_id=job["id"], state=job["state"]))
    except DeleteRejected as error:
        return schemas.Response[DismissResult](success=False, message=str(error), data=DismissResult())
    finally:
        guard.release()


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
        {"path": "/sync_delete/dismiss", "endpoint": partial(dismiss, plugin), "auth": "bear", "methods": ["POST"],
         "summary": "忽略未开始的同步删除记录并保留历史", "response_model": schemas.Response[DismissResult]},
    ]
