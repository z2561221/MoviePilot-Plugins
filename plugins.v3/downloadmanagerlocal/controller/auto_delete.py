"""自动删除接口：认证、管理权限、参数和真实任务状态。"""

from functools import partial

from app import schemas
from fastapi import Depends, HTTPException, Query

from ..model.auto_delete import (
    ActivateRequest,
    PreviewRequest,
    ReleaseRequest,
    Result,
    SaveRequest,
    Status,
)
from ..service import auto_delete
from ..service.auto_delete_executor import release_jobs
from .security import require_admin


def call_service(function, *args):
    """明确区分参数冲突与服务失败，不把受理状态伪装成完成。"""
    try:
        return function(*args)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def get_config(plugin):
    """读取模块已生效设置和修订。"""
    return call_service(auto_delete.config_result, plugin)


def save_config(plugin, payload: SaveRequest):
    """保存本模块设置，保留插件其他字段。"""
    return schemas.Response[Result](success=True, message="自动删除设置已保存", data=call_service(auto_delete.save_settings, plugin, payload))


def preview(plugin, payload: PreviewRequest):
    """预览不暂停、不保存采样计数。"""
    return schemas.Response[Result](success=True, message="", data=call_service(auto_delete.preview, plugin, payload.settings))


def run(plugin):
    """立即运行只受理扫描，结果由状态及记录接口回读。"""
    return schemas.Response[Result](success=True, message="", data=call_service(auto_delete.request_run, plugin))


def activate(plugin, payload: ActivateRequest):
    """只确认规则及选定清单，不在接口中直接删除种子。"""
    return schemas.Response[Result](success=True, message="当前规则已确认正式启用", data=call_service(auto_delete.activate_rule, plugin, payload))


def release(plugin, payload: ReleaseRequest):
    """明确人工操作只解除本模块所属的任务保护。"""
    items = call_service(release_jobs, auto_delete.runtime_of(plugin), payload.job_ids, payload.restore)
    complete = all(item["state"] == "released" for item in items)
    return schemas.Response[Result](success=complete, message="选定调试任务已处理" if complete else "部分任务仍需复核",
                                    data=Result(items=items, errors=[item["error"] for item in items if item.get("error")]))


def stop(plugin):
    """关闭自动删除总开关，保留保护及在途结果。"""
    return schemas.Response[Result](success=True, message="自动删除已停止", data=call_service(auto_delete.stop_module, plugin))


def status(plugin):
    """只读投影当前轮次及模块统计。"""
    return Status.model_validate(auto_delete.status_result(plugin))


def history(plugin, page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=100),
            rule_id: str = "", downloader: str = "", state: str = ""):
    """摘要筛选分页，不加载全量任务计划。"""
    total, items = call_service(auto_delete.runtime_of(plugin).store.page, page, page_size, rule_id, downloader, state)
    return Result(total=total, items=items, page=page, page_size=page_size)


def job(plugin, job_id: str = Query(min_length=1, max_length=64)):
    """读取精确任务的暂停前证据和逐文件检查点。"""
    return Result(items=[call_service(auto_delete.runtime_of(plugin).store.get, job_id)])


def routes(plugin):
    """查询使用 bearer，所有管理操作另有服务端管理员门禁。"""
    declarations = [
        ("config", "GET", get_config), ("config", "POST", save_config),
        ("preview", "POST", preview), ("run", "POST", run),
        ("activate", "POST", activate), ("release", "POST", release),
        ("stop", "POST", stop), ("status", "GET", status),
        ("history", "GET", history), ("job", "GET", job),
    ]
    return [{"path": "/auto_delete/" + path, "methods": [method], "endpoint": partial(endpoint, plugin),
             "auth": "bear", "summary": "自动删除 · " + path,
             "response_model": Status if path == "status" else Result if method == "GET" else schemas.Response[Result],
             "dependencies": [Depends(require_admin)] if method == "POST" else []}
            for path, method, endpoint in declarations]
