"""辅助铺种管理接口。"""

from functools import partial

from app.schemas.response import Response
from fastapi import Depends, HTTPException, Query

from ..model.reseed import ResultPage, StopRequest, TaskResult
from ..service import reseed
from .security import require_admin


def status(plugin):
    """读取任务进度。"""
    return TaskResult(**reseed.status(plugin))


def results(plugin, task_id: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)):
    """读取脱敏候选回执。"""
    try:
        return ResultPage(**reseed.results(plugin, task_id, offset, limit))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def stop(plugin, payload: StopRequest):
    """停止指定任务的后续操作。"""
    try:
        return Response[TaskResult](success=True, message="", data=TaskResult(**reseed.stop(plugin, payload.task_id)))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def routes(plugin):
    """注册实例隔离且受管理员权限保护的任务路由。"""
    definitions = [
        ("status", status, "GET", TaskResult),
        ("results", results, "GET", ResultPage),
        ("stop", stop, "POST", Response[TaskResult]),
    ]
    return [{"path": f"/reseed/{name}", "endpoint": partial(endpoint, plugin), "methods": [method],
             "auth": "bear", "summary": f"IYUU铺种 {name}", "response_model": model,
             "dependencies": [Depends(require_admin)]} for name, endpoint, method, model in definitions]
