"""下载器补全标签的后台任务管理服务。"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.sdk.logging import logger

from .site_tag import execute_tag_completion, scan_tag_completion

TAG_COMPLETION_TASK_KEY = "tag_completion_task_v1"
ACTIVE_STATUSES = {"queued", "running", "cancelling"}
TERMINAL_STATUSES = {"completed", "partial", "failed", "cancelled", "interrupted"}
MAX_REQUEST_HISTORY = 20
RESULT_PAGE_SIZE = 200


def submit_tag_completion_scan(
    plugin,
    downloader_names: list[str],
    request_id: str,
    *, torrent_hashes: list[str] | None = None,
) -> dict[str, Any]:
    """登记一个标签扫描任务并立即返回任务标识。"""
    payload = {"downloaders": list(downloader_names or [])}
    if torrent_hashes:
        payload["torrent_hashes"] = list(torrent_hashes)
    return _submit_task(plugin, "scan", payload, request_id)


def submit_tag_completion_execute(
    plugin,
    scan_task_id: str,
    selections: list[dict[str, Any]],
    request_id: str,
) -> dict[str, Any]:
    """登记一个按扫描快照执行的标签补全任务。"""
    return _submit_task(
        plugin,
        "execute",
        {"scan_task_id": str(scan_task_id or ""), "selections": list(selections or [])},
        request_id,
    )


def _submit_task(
    plugin,
    operation: str,
    payload: dict[str, Any],
    request_id: str,
) -> dict[str, Any]:
    """保存任务请求并提交至宿主一次性调度器。"""
    request_id = str(request_id or "").strip()
    if not request_id:
        return {"code": 1, "msg": "缺少任务请求标识", "found": False}
    fingerprint = _request_fingerprint(operation, payload)

    with _task_lock(plugin):
        state = _load_task_state(plugin)
        existing = _find_request(state, request_id)
        if existing:
            if existing.get("fingerprint") != fingerprint:
                return {"code": 1, "msg": "请求标识已被另一份任务使用，请刷新后重试", "found": False}
            return {
                "code": 0,
                "msg": existing.get("message", "任务已提交"),
                "found": True,
                **_task_view(existing, state),
            }

        current = state.get("current_task")
        if isinstance(current, dict) and current.get("status") in ACTIVE_STATUSES:
            return {
                "code": 2,
                "msg": "已有标签补全任务正在运行，请先查看任务状态",
                "found": True,
                **_task_view(current),
            }

        if operation == "execute":
            validation_error = _validate_scan_selection(plugin, state, payload)
            if validation_error:
                return {"code": 1, "msg": validation_error, "found": False}

        task = _build_task(operation, payload, request_id, fingerprint)
        if operation == "scan":
            state["last_scan_task_id"] = ""
        state["current_task"] = task
        _remember_request(state, task)
        return _register_task(plugin, state, task)


def _build_task(
    operation: str,
    payload: dict[str, Any],
    request_id: str,
    fingerprint: str,
) -> dict[str, Any]:
    """创建可持久化的标签补全任务记录。"""
    now = _timestamp()
    return {
        "task_id": uuid4().hex,
        "request_id": request_id,
        "fingerprint": fingerprint,
        "operation": operation,
        "status": "queued",
        "phase": "等待后台任务",
        "current": 0,
        "total": 0,
        "message": "任务已提交",
        "created_at": now,
        "updated_at": now,
        "payload": payload,
        "result_available": False,
    }


def _register_task(plugin, state: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    """保存任务并将绑定插件实例的回调提交给宿主调度器。"""
    _save_task_state(plugin, state)
    task_id = task["task_id"]
    stop_event = threading.Event()
    job_id = f"tag_completion_{task_id}"
    plugin._tag_completion_stop_event = stop_event
    plugin._tag_completion_job_id = job_id

    try:
        from app.sdk.scheduler import add_plugin_once_job

        registered = add_plugin_once_job(
            plugin.__class__.__name__,
            job_id,
            plugin._run_tag_completion_task,
            "下载器标签补全",
            delay_seconds=0,
            func_kwargs={"task_id": task_id},
        )
    except Exception as error:
        logger.error(f"标签补全任务提交失败：{type(error).__name__}")
        registered = False

    if not registered:
        task.update(
            status="failed",
            phase="提交失败",
            message="后台调度器未接受任务，请稍后重试",
            updated_at=_timestamp(),
        )
        _remember_request(state, task)
        _save_task_state(plugin, state)
        return {"code": 1, "msg": task["message"], "found": True, **_task_view(task)}

    return {"code": 0, "msg": task["message"], "found": True, **_task_view(task)}


def _validate_scan_selection(plugin, state: dict[str, Any], payload: dict[str, Any]) -> str:
    """确认执行选择只引用最近一次完整扫描的标签组。"""
    scan_task_id = payload.get("scan_task_id")
    if not scan_task_id or scan_task_id != state.get("last_scan_task_id"):
        return "扫描预览已失效，请重新扫描后再确认"
    scan = _load_result(plugin, "scan", scan_task_id)
    if not scan:
        return "扫描结果已失效，请重新扫描后再确认"
    available = _scan_group_index(scan)
    selections = payload.get("selections") or []
    if not selections:
        return "请至少选择一个待补全标签"
    for selection in selections:
        key = _selection_key(selection)
        if key not in available:
            return "所选标签不属于当前扫描结果，请重新扫描"
    return ""


def _selection_key(selection: dict[str, Any]) -> tuple[str, str, str]:
    """生成扫描结果中的标签组唯一键。"""
    return (
        str(selection.get("downloader") or ""),
        str(selection.get("kind") or ""),
        str(selection.get("tag") or ""),
    )


def _scan_group_index(scan: dict[str, Any]) -> dict[tuple[str, str, str], list[str]]:
    """将扫描结果转换为按下载器和标签类别索引的种子清单。"""
    groups = {}
    for downloader in scan.get("downloaders") or []:
        if not isinstance(downloader, dict):
            continue
        downloader_name = str(downloader.get("name") or "")
        for tag_group in downloader.get("tags") or []:
            if not isinstance(tag_group, dict):
                continue
            key = (
                downloader_name,
                str(tag_group.get("kind") or ""),
                str(tag_group.get("tag") or ""),
            )
            hashes = (str(value) for value in tag_group.get("hashes") or [] if value)
            groups[key] = list(dict.fromkeys(hashes))
    return groups


def _build_repairs(plugin, task: dict[str, Any]) -> list[dict[str, Any]]:
    """根据服务端保存的扫描结果构造执行清单。"""
    scan_task_id = task.get("payload", {}).get("scan_task_id")
    scan = _load_result(plugin, "scan", scan_task_id)
    if not scan:
        raise ValueError("扫描结果已失效，请重新扫描后再确认")
    groups = _scan_group_index(scan)
    repairs = []
    seen = set()
    for selection in task.get("payload", {}).get("selections") or []:
        key = _selection_key(selection)
        hashes = groups.get(key)
        if not hashes or key in seen:
            continue
        seen.add(key)
        repairs.append({"downloader": key[0], "kind": key[1], "tag": key[2], "hashes": hashes})
    return repairs


def run_tag_completion_task(plugin, task_id: str) -> None:
    """运行一个已登记的标签扫描或执行任务。"""
    with _task_lock(plugin):
        state = _load_task_state(plugin)
        task = state.get("current_task")
        if (
            not isinstance(task, dict)
            or task.get("task_id") != task_id
            or task.get("status") != "queued"
        ):
            return
        task.update(status="running", phase="准备任务", message="后台任务运行中", updated_at=_timestamp())
        _remember_request(state, task)
        _save_task_state(plugin, state)

    stop_event = getattr(plugin, "_tag_completion_stop_event", None) or threading.Event()
    operation = task.get("operation")

    def progress_callback(phase: str, current: int, total: int) -> None:
        """持久化服务层报告的阶段进度。"""
        _update_progress(plugin, task_id, phase, current, total)

    try:
        if operation == "scan":
            scan_options = {}
            if task.get("payload", {}).get("torrent_hashes"):
                scan_options["torrent_hashes"] = task["payload"]["torrent_hashes"]
            result = scan_tag_completion(
                plugin,
                task.get("payload", {}).get("downloaders") or [],
                stop_event=stop_event,
                progress_callback=progress_callback,
                **scan_options,
            )
        elif operation == "execute":
            repairs = _build_repairs(plugin, task)
            result = execute_tag_completion(
                plugin,
                repairs,
                stop_event=stop_event,
                progress_callback=progress_callback,
            )
        else:
            raise ValueError("未知的标签补全任务类型")
        with _task_lock(plugin):
            current = _load_task_state(plugin).get("current_task")
            if not isinstance(current, dict) or current.get("task_id") != task_id:
                return
            result_saved = current.get("status") != "interrupted"
            if result_saved:
                _save_result(plugin, operation, task_id, result)
            _finish_task(plugin, task_id, result, stop_event, result_saved=result_saved)
    except Exception as error:
        logger.error(f"标签补全后台任务失败：{type(error).__name__}")
        _finish_task(
            plugin,
            task_id,
            {"code": 1, "msg": f"后台任务失败：{type(error).__name__}"},
            stop_event,
        )


def _update_progress(plugin, task_id: str, phase: str, current: int, total: int) -> None:
    """更新轻量任务进度并持久化。"""
    with _task_lock(plugin):
        state = _load_task_state(plugin)
        task = state.get("current_task")
        if not isinstance(task, dict) or task.get("task_id") != task_id:
            return
        if task.get("status") not in {"running", "queued"}:
            return
        task.update(
            phase=str(phase or "后台任务运行中"),
            current=max(0, int(current or 0)),
            total=max(0, int(total or 0)),
            updated_at=_timestamp(),
        )
        _remember_request(state, task)
        _save_task_state(plugin, state)


def _finish_task(
    plugin,
    task_id: str,
    result: dict[str, Any],
    stop_event,
    *,
    result_saved: bool = False,
) -> None:
    """保存任务终态，并保留停止或 reload 已标记的状态。"""
    with _task_lock(plugin):
        state = _load_task_state(plugin)
        task = state.get("current_task")
        if not isinstance(task, dict) or task.get("task_id") != task_id:
            return
        operation = task.get("operation")
        prior_status = task.get("status")
        if prior_status == "interrupted":
            status = "interrupted"
            message = ("插件已重载或停止；已完成的写入结果可供核对，不会自动重放" if result_saved
                       else "插件已重载或停止；在途请求可能已完成，请重新扫描核对，不会自动重放")
        elif prior_status in {"cancelling", "cancelled"} or stop_event.is_set():
            status = "cancelled"
            message = "任务已停止；在途下载器请求可能已完成，请重新扫描核对"
        else:
            status, message = _result_status(operation, result)
        task.update(
            status=status,
            phase=status,
            message=message or result.get("msg", "后台任务已结束"),
            result_available=result_saved,
            updated_at=_timestamp(),
        )
        if operation == "scan" and status in {"completed", "partial"}:
            state["last_scan_task_id"] = task_id
        _remember_request(state, task)
        _save_task_state(plugin, state)
        if getattr(plugin, "_tag_completion_stop_event", None) is stop_event:
            plugin._tag_completion_stop_event = None
            plugin._tag_completion_job_id = None


def _result_status(operation: str, result: dict[str, Any]) -> tuple[str, str]:
    """依据业务结果选择任务终态。"""
    code = int(result.get("code", 1) or 0)
    if code == 0:
        if operation == "scan" and result.get("errors"):
            return "partial", result.get("msg", "扫描部分完成")
        return "completed", result.get("msg", "任务完成")
    if code == 2:
        return "partial", result.get("msg", "任务部分完成")
    return "failed", result.get("msg", "任务失败")


def get_tag_completion_status(
    plugin,
    task_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """读取轻量任务状态，不访问下载器或加载完整扫描结果。"""
    state = _load_task_state(plugin)
    task = state.get("current_task")
    if request_id:
        task = _find_request(state, request_id)
    elif task_id and (not isinstance(task, dict) or task.get("task_id") != task_id):
        task = next((
            item
            for item in reversed(state.get("requests") or [])
            if item.get("task_id") == task_id
        ), None)
    if not isinstance(task, dict):
        return {"code": 0, "msg": "没有可查询的标签补全任务", "found": False}
    return {"code": 0, "msg": task.get("message", ""), "found": True, **_task_view(task, state)}


def get_tag_completion_result(
    plugin,
    task_id: str,
    offset: int = 0,
    limit: int = RESULT_PAGE_SIZE,
) -> dict[str, Any]:
    """按游标分页读取指定标签补全任务结果。"""
    state = _load_task_state(plugin)
    task = state.get("current_task") or {}
    operation = None
    if task.get("task_id") == task_id and task.get("status") in TERMINAL_STATUSES:
        operation = task.get("operation")
    elif state.get("last_scan_task_id") == task_id:
        operation = "scan"
    if not operation:
        return {"code": 1, "msg": "任务结果不存在或已过期", "result": {}}
    result = _load_result(plugin, operation, task_id)
    if result is None:
        return {"code": 1, "msg": "任务结果暂不可用，请重新扫描", "result": {}}
    page, total = _page_result(operation, result, offset, limit)
    page_offset = max(0, int(offset or 0))
    page_limit = max(1, min(int(limit or RESULT_PAGE_SIZE), 500))
    next_offset = min(total, page_offset + page_limit)
    return {
        "code": 0,
        "msg": "任务结果已读取",
        "result": page,
        "offset": page_offset,
        "next_offset": next_offset,
        "total": total,
        "complete": next_offset >= total,
    }


def _page_result(
    operation: str,
    result: dict[str, Any],
    offset: int,
    limit: int,
) -> tuple[dict[str, Any], int]:
    """按固定上限裁切扫描标签关联或执行明细。"""
    page_offset = max(0, int(offset or 0))
    page_limit = max(1, min(int(limit or RESULT_PAGE_SIZE), 500))
    if operation == "scan":
        return _page_scan_result(result, page_offset, page_limit)
    return _page_execute_result(result, page_offset, page_limit)


def _page_scan_result(
    page: dict[str, Any],
    offset: int,
    limit: int,
) -> tuple[dict[str, Any], int]:
    """保留轻量组信息，仅复制本页 hash，不展开全部关联。"""
    result = deepcopy({key: value for key, value in page.items() if key != "downloaders"})
    result["downloaders"] = []
    total = 0
    for downloader in page.get("downloaders") or []:
        downloader_page = deepcopy({key: value for key, value in downloader.items() if key != "tags"})
        downloader_page["tags"] = []
        for tag_group in downloader.get("tags") or []:
            hashes = tag_group.get("hashes") or []
            count = len(hashes)
            start = max(0, offset - total)
            end = min(count, offset + limit - total)
            group_page = deepcopy({key: value for key, value in tag_group.items() if key != "hashes"})
            group_page["hashes"] = list(hashes[start:end]) if end > start else []
            downloader_page["tags"].append(group_page)
            total += count
        result["downloaders"].append(downloader_page)
    return result, total


def _page_execute_result(
    page: dict[str, Any],
    offset: int,
    limit: int,
) -> tuple[dict[str, Any], int]:
    """只复制本页新增、跳过和失败明细，保留列表之间的游标。"""
    keys = ("added", "skipped", "failed")
    result = deepcopy({key: value for key, value in page.items() if key not in keys})
    total = 0
    for key in keys:
        values = page.get(key) or []
        count = len(values)
        start = max(0, offset - total)
        end = min(count, offset + limit - total)
        result[key] = deepcopy(values[start:end]) if end > start else []
        total += count
    return result, total


def cancel_tag_completion_task(plugin, task_id: str) -> dict[str, Any]:
    """请求停止当前任务并阻止后续下载器写入。"""
    with _task_lock(plugin):
        state = _load_task_state(plugin)
        task = state.get("current_task")
        if not isinstance(task, dict) or task.get("task_id") != task_id:
            return {"code": 1, "msg": "任务不存在或已被新任务替代", "found": False}
        if task.get("status") not in ACTIVE_STATUSES:
            return {
                "code": 0,
                "msg": task.get("message", "任务已结束"),
                "found": True,
                **_task_view(task),
            }
        stop_event = getattr(plugin, "_tag_completion_stop_event", None)
        if stop_event is not None:
            stop_event.set()
        if task.get("status") == "queued":
            _remove_scheduled_task(plugin, task_id)
            task.update(
                status="cancelled",
                phase="cancelled",
                message="任务已取消",
                updated_at=_timestamp(),
            )
        else:
            task.update(
                status="cancelling",
                phase="等待当前请求结束",
                message="已请求停止，正在等待当前下载器请求结束",
                updated_at=_timestamp(),
            )
        _remember_request(state, task)
        _save_task_state(plugin, state)
        return {"code": 0, "msg": task["message"], "found": True, **_task_view(task)}


def stop_tag_completion_task(plugin) -> None:
    """在插件停止或 reload 时取消待执行任务并阻止旧批次继续写入。"""
    with _task_lock(plugin):
        state = _load_task_state(plugin)
        task = state.get("current_task")
        if not isinstance(task, dict) or task.get("status") not in ACTIVE_STATUSES:
            return
        stop_event = getattr(plugin, "_tag_completion_stop_event", None)
        if stop_event is not None:
            stop_event.set()
        if task.get("status") == "queued":
            _remove_scheduled_task(plugin, task.get("task_id"))
        task.update(
            status="interrupted",
            phase="interrupted",
            message="插件已停止或重载；已完成的写入结果需重新扫描核对",
            updated_at=_timestamp(),
        )
        _remember_request(state, task)
        _save_task_state(plugin, state)


def recover_tag_completion_task(plugin) -> None:
    """把上次进程遗留的活动任务标记为中断，不自动重放。"""
    with _task_lock(plugin):
        state = _load_task_state(plugin)
        task = state.get("current_task")
        if not isinstance(task, dict) or task.get("status") not in ACTIVE_STATUSES:
            return
        task.update(
            status="interrupted",
            phase="interrupted",
            message="上次标签补全任务未正常结束；请重新扫描核对，不会自动重放",
            updated_at=_timestamp(),
        )
        _remember_request(state, task)
        _save_task_state(plugin, state)


def _remove_scheduled_task(plugin, task_id: str | None) -> None:
    """移除尚未启动的宿主一次性任务。"""
    if not task_id:
        return
    try:
        from app.sdk.scheduler import remove_plugin_once_job

        remove_plugin_once_job(plugin.__class__.__name__, f"tag_completion_{task_id}")
    except Exception as error:
        logger.warning(f"取消标签补全调度任务失败：{type(error).__name__}")


def _task_lock(plugin):
    """返回插件实例级任务锁。"""
    lock = getattr(plugin, "_tag_completion_lock", None)
    if lock is None:
        lock = threading.RLock()
        plugin._tag_completion_lock = lock
    return lock


def _load_task_state(plugin) -> dict[str, Any]:
    """读取轻量持久任务状态。"""
    get_data = getattr(plugin, "get_data", None)
    value = get_data(TAG_COMPLETION_TASK_KEY) if callable(get_data) else None
    if value is not None and not isinstance(value, dict):
        raise ValueError("标签补全任务状态格式错误，原记录已保留")
    if isinstance(value, dict):
        current = value.get("current_task")
        requests = value.get("requests")
        if current is not None and not isinstance(current, dict):
            raise ValueError("标签补全当前任务格式错误，原记录已保留")
        if isinstance(current, dict) and "status" in current and not isinstance(current["status"], str):
            raise ValueError("标签补全任务状态字段无效，原记录已保留")
        if requests is not None and (not isinstance(requests, list) or any(not isinstance(item, dict) for item in requests)):
            raise ValueError("标签补全请求记录格式错误，原记录已保留")
    return value if isinstance(value, dict) else {
        "current_task": None,
        "last_scan_task_id": "",
        "requests": [],
    }


def _save_task_state(plugin, state: dict[str, Any]) -> None:
    """保存任务状态、请求去重记录和进度。"""
    save_data = getattr(plugin, "save_data", None)
    if callable(save_data):
        save_data(TAG_COMPLETION_TASK_KEY, state)


def _remember_request(state: dict[str, Any], task: dict[str, Any]) -> None:
    """更新有限长度的请求去重记录。"""
    record = _task_view(task)
    record["request_id"] = task.get("request_id", "")
    record["message"] = task.get("message", "")
    record["fingerprint"] = task.get("fingerprint", "")
    requests = [
        item for item in state.get("requests") or []
        if item.get("request_id") != record["request_id"]
    ]
    requests.append(record)
    state["requests"] = requests[-MAX_REQUEST_HISTORY:]


def _find_request(state: dict[str, Any], request_id: str) -> dict[str, Any] | None:
    """按客户端请求标识查找当前任务或最近任务快照。"""
    current = state.get("current_task")
    if isinstance(current, dict) and current.get("request_id") == request_id:
        return current
    return next((
        item
        for item in reversed(state.get("requests") or [])
        if item.get("request_id") == request_id
    ), None)


def _task_view(task: dict[str, Any], state: dict[str, Any] | None = None) -> dict[str, Any]:
    """生成不包含业务结果和提交载荷的任务状态。"""
    total = max(0, int(task.get("total", 0) or 0))
    current = max(0, int(task.get("current", 0) or 0))
    progress = min(100, int(current * 100 / total)) if total else 0
    result_available = bool(task.get("result_available"))
    if state is not None:
        current_task = state.get("current_task") or {}
        accessible = {current_task.get("task_id"), state.get("last_scan_task_id")}
        result_available = result_available and task.get("task_id") in accessible
    return {
        "task_id": task.get("task_id", ""),
        "request_id": task.get("request_id", ""),
        "operation": task.get("operation", ""),
        "status": task.get("status", ""),
        "phase": task.get("phase", ""),
        "current": current,
        "total": total,
        "progress": progress,
        "can_cancel": task.get("status") in ACTIVE_STATUSES,
        "result_available": result_available,
    }


def _result_file_path(plugin, operation: str) -> Path:
    """获取插件数据目录中的标签补全结果文件路径。"""
    directory = Path(plugin.get_data_path()) / "tag_completion"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{operation}_result.json"


def _save_result(plugin, operation: str, task_id: str, result: dict[str, Any]) -> None:
    """原子写入大结果文件，避免将种子清单塞进状态数据。"""
    path = _result_file_path(plugin, operation)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps({"task_id": task_id, "result": result}, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def _load_result(plugin, operation: str, task_id: str) -> dict[str, Any] | None:
    """读取并校验对应任务的扫描或执行结果。"""
    try:
        content = json.loads(_result_file_path(plugin, operation).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(content, dict) or content.get("task_id") != task_id:
        return None
    result = content.get("result")
    return result if isinstance(result, dict) else None


def _timestamp() -> str:
    """返回可持久化的 UTC 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


def _request_fingerprint(operation: str, payload: dict[str, Any]) -> str:
    """生成同一请求标识的内容校验摘要。"""
    encoded = json.dumps(
        {"operation": operation, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = (
    "cancel_tag_completion_task",
    "get_tag_completion_result",
    "get_tag_completion_status",
    "recover_tag_completion_task",
    "run_tag_completion_task",
    "stop_tag_completion_task",
    "submit_tag_completion_execute",
    "submit_tag_completion_scan",
)
