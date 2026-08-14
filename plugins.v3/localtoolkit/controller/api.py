"""工具中心 V3 API 路由与响应组装。"""

from typing import Any, Dict, Optional

from fastapi import HTTPException

from app import schemas
from app.log import logger

from ..model.api import (
    ToolkitHistoryData,
    ToolkitHistoryItem,
    ToolkitLibraryCleanupOptions,
    ToolkitModulesStatus,
    ToolkitModuleStatus,
    ToolkitOptionsData,
    ToolkitRunData,
    ToolkitStatusData,
)
from ..security import redact_sensitive_text, safe_error_text


def build_api_routes(plugin) -> list[dict]:
    """构建工具中心 V3 API 路由声明。"""
    return [
        {
            "path": "/local_toolkit/status",
            "endpoint": plugin.api_status,
            "auth": "bear",
            "methods": ["GET"],
            "summary": "本地工具中心状态",
            "response_model": ToolkitStatusData,
        },
        {
            "path": "/local_toolkit/run/{module}",
            "endpoint": plugin.api_run,
            "auth": "bear",
            "methods": ["POST"],
            "summary": "运行本地工具模块",
            "response_model": schemas.Response[ToolkitRunData],
            "response_model_exclude_none": True,
        },
        {
            "path": "/local_toolkit/history",
            "endpoint": plugin.api_history,
            "auth": "bear",
            "methods": ["GET"],
            "summary": "本地工具中心历史",
            "response_model": ToolkitHistoryData,
        },
        {
            "path": "/local_toolkit/options",
            "endpoint": plugin.api_options,
            "auth": "bear",
            "methods": ["GET"],
            "summary": "本地工具中心配置选项",
            "response_model": ToolkitOptionsData,
            "response_model_exclude_none": True,
        },
        {
            "path": "/local_toolkit/invalidate_cache",
            "endpoint": plugin.api_invalidate_cache,
            "auth": "bear",
            "methods": ["POST"],
            "summary": "清除选项缓存",
            "response_model": schemas.Response[None],
        },
    ]


def module_map(plugin) -> Dict[str, Any]:
    """返回工具中心模块映射。"""
    return {
        "tmdb_cache": plugin.tmdb_cache,
        "check_missing": plugin.check_missing,
        "library_cleanup": plugin.library_cleanup,
    }


def safe_int(value: Any, default: int, min_value: int | None = None, max_value: int | None = None) -> int:
    """安全解析分页整数。"""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None and parsed < min_value:
        parsed = default
    if max_value is not None and parsed > max_value:
        parsed = max_value
    return parsed


def safe_float(value: Any, default: float = 0) -> float:
    """安全解析运行耗时。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_status(key: str, module) -> ToolkitModuleStatus:
    """安全读取单个模块状态并转换为业务模型。"""
    name = getattr(module, "module_name", key)
    try:
        status = module.get_status()
        if not isinstance(status, dict):
            return ToolkitModuleStatus(success=True, module_name=name)
        return ToolkitModuleStatus.model_validate(status)
    except Exception as err:
        logger.error(f"本地工具集：获取{name}状态失败：{redact_sensitive_text(err)}")
        return ToolkitModuleStatus(success=False, module_name=name, error="模块状态读取失败")


def status_response(plugin) -> ToolkitStatusData:
    """返回工具中心状态业务数据。"""
    modules = module_map(plugin)
    return ToolkitStatusData(
        enabled=plugin._enabled,
        modules=ToolkitModulesStatus(
            library_cleanup=safe_status("library_cleanup", modules["library_cleanup"]),
            check_missing=safe_status("check_missing", modules["check_missing"]),
            tmdb_cache=safe_status("tmdb_cache", modules["tmdb_cache"]),
        ),
    )


def _normalize_run_result(result: Any) -> schemas.Response[ToolkitRunData]:
    """把模块结果转换为单层 V3 业务响应。"""
    if isinstance(result, dict):
        payload = dict(result)
    else:
        payload = {"summary": "" if result is None else str(result)}
    success = bool(payload.pop("success", True))
    message = str(payload.pop("message", "") or "")
    if not message and not success:
        message = str(payload.get("summary") or "模块运行失败")
    data = ToolkitRunData.model_validate(payload) if payload else None
    return schemas.Response[ToolkitRunData](success=success, message=message, data=data)


def run_module(plugin, module: str) -> schemas.Response[ToolkitRunData]:
    """运行指定工具模块并返回单层 V3 响应。"""
    module_key = str(module or "").strip()
    selected = module_map(plugin).get(module_key)
    if not selected:
        raise HTTPException(status_code=404, detail=f"未知模块：{module_key or 'empty'}")
    try:
        return _normalize_run_result(selected.run_once())
    except Exception as err:
        name = getattr(selected, "module_name", module_key)
        logger.error(f"本地工具集：运行{name}失败：{redact_sensitive_text(err)}")
        try:
            if hasattr(selected, "add_history"):
                selected.add_history("failed", safe_error_text(name), 0)
        except Exception as history_error:
            logger.warning(f"本地工具集：记录{name}失败历史失败：{redact_sensitive_text(history_error)}")
        return schemas.Response[ToolkitRunData](
            success=False,
            message=safe_error_text(f"{name}运行"),
            data=None,
        )


def _history_item(value: Any) -> Optional[ToolkitHistoryItem]:
    """把历史存储项安全转换为业务模型。"""
    if not isinstance(value, dict):
        return None
    return ToolkitHistoryItem(
        time=str(value.get("time") or ""),
        module=str(value.get("module") or ""),
        module_name=str(value.get("module_name") or ""),
        status=str(value.get("status") or ""),
        summary=str(value.get("summary") or ""),
        duration=safe_float(value.get("duration")),
    )


def history_response(plugin, page: Any = 1, page_size: Any = 15) -> ToolkitHistoryData:
    """返回工具中心历史分页业务数据。"""
    current_page = safe_int(page, 1, min_value=1)
    current_page_size = safe_int(page_size, 15, min_value=1, max_value=100)
    all_data = plugin.get_data(key="tool_history") or []
    if not isinstance(all_data, list):
        logger.warning("本地工具集：历史记录格式异常，已忽略")
        all_data = []
    normalized = [item for value in all_data if (item := _history_item(value)) is not None]
    total = len(normalized)
    total_pages = max(1, -(-total // current_page_size))
    if current_page > total_pages:
        current_page = total_pages
    start = (current_page - 1) * current_page_size
    end = start + current_page_size
    return ToolkitHistoryData(
        total=total,
        page=current_page,
        page_size=current_page_size,
        total_pages=total_pages,
        items=normalized[start:end],
    )


def options_response(
    plugin,
    selected_server: Optional[str] = None,
    selected_user: Optional[str] = None,
) -> ToolkitOptionsData:
    """返回工具中心配置选项业务数据。"""
    raw_options = plugin.library_cleanup.get_options(selected_server, selected_user)
    if not isinstance(raw_options, dict):
        raw_options = {"error": "媒体服务器选项格式异常"}
    return ToolkitOptionsData(
        library_cleanup=ToolkitLibraryCleanupOptions.model_validate(raw_options)
    )


def invalidate_cache_response(plugin) -> schemas.Response[None]:
    """清除工具中心选项缓存并返回单层 V3 响应。"""
    plugin.library_cleanup.invalidate_options_cache()
    return schemas.Response[None](success=True, message="缓存已清除", data=None)
