"""工具中心 API 路由与响应组装。"""

from typing import Any, Dict

from app.log import logger


def build_api_routes(plugin) -> list[dict]:
    """构建工具中心 API 路由声明。"""
    return [
        {
            "path": "/local_toolkit/status",
            "endpoint": plugin.api_status,
            "auth": "bear",
            "methods": ["GET"],
            "summary": "本地工具中心状态",
        },
        {
            "path": "/local_toolkit/run/{module}",
            "endpoint": plugin.api_run,
            "auth": "bear",
            "methods": ["POST"],
            "summary": "运行本地工具模块",
        },
        {
            "path": "/local_toolkit/history",
            "endpoint": plugin.api_history,
            "auth": "bear",
            "methods": ["GET"],
            "summary": "本地工具中心历史",
        },
        {
            "path": "/local_toolkit/options",
            "endpoint": plugin.api_options,
            "auth": "bear",
            "methods": ["GET"],
            "summary": "本地工具中心配置选项",
        },
        {
            "path": "/local_toolkit/invalidate_cache",
            "endpoint": plugin.api_invalidate_cache,
            "auth": "bear",
            "methods": ["POST"],
            "summary": "清除选项缓存",
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


def safe_status(key: str, module) -> dict:
    """安全读取单个模块状态。"""
    try:
        status = module.get_status()
        return status if isinstance(status, dict) else {"success": True, "value": status}
    except Exception as err:
        name = getattr(module, "module_name", key)
        logger.error(f"本地工具集：获取{name}状态失败：{err}")
        return {"success": False, "module_name": name, "error": str(err)}


def status_response(plugin) -> dict:
    """返回工具中心状态响应。"""
    return {
        "enabled": plugin._enabled,
        "modules": {
            key: safe_status(key, module)
            for key, module in module_map(plugin).items()
        },
    }


def run_module(plugin, module: str) -> dict:
    """运行指定工具模块并返回结构化结果。"""
    module_key = str(module or "").strip()
    selected = module_map(plugin).get(module_key)
    if not selected:
        return {"success": False, "message": f"未知模块：{module_key or 'empty'}"}
    try:
        result = selected.run_once()
        return result if isinstance(result, dict) else {"success": True, "result": result}
    except Exception as err:
        name = getattr(selected, "module_name", module_key)
        logger.error(f"本地工具集：运行{name}失败：{err}")
        try:
            if hasattr(selected, "add_history"):
                selected.add_history("failed", f"运行异常：{err}", 0)
        except Exception as history_error:
            logger.warning(f"本地工具集：记录{name}失败历史失败：{history_error}")
        return {"success": False, "message": f"{name}运行失败：{err}"}


def history_response(plugin, page: Any = 1, page_size: Any = 15) -> dict:
    """返回工具中心历史分页响应。"""
    current_page = safe_int(page, 1, min_value=1)
    current_page_size = safe_int(page_size, 15, min_value=1, max_value=100)
    all_data = plugin.get_data(key="tool_history") or []
    if not isinstance(all_data, list):
        logger.warning("本地工具集：历史记录格式异常，已忽略")
        all_data = []
    total = len(all_data)
    total_pages = max(1, -(-total // current_page_size))
    if current_page > total_pages:
        current_page = total_pages
    start = (current_page - 1) * current_page_size
    end = start + current_page_size
    return {
        "total": total,
        "page": current_page,
        "page_size": current_page_size,
        "total_pages": total_pages,
        "items": all_data[start:end],
    }


def options_response(plugin) -> dict:
    """返回工具中心配置选项响应。"""
    return {
        "success": True,
        "library_cleanup": plugin.library_cleanup.get_options(),
    }


def invalidate_cache_response(plugin) -> dict:
    """清除工具中心选项缓存并返回响应。"""
    plugin.library_cleanup.invalidate_options_cache()
    return {"success": True, "message": "缓存已清除"}

