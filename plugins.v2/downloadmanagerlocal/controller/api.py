"""下载中心 API 路由声明。"""

from typing import Any, Dict, List


def build_api_routes(plugin) -> List[Dict[str, Any]]:
    """构造插件 API 路由声明，保持前端调用契约不变。"""
    return [
        {
            "path": "/downloaders",
            "endpoint": plugin.api_downloaders,
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取下载器列表",
        },
        {
            "path": "/rename_history",
            "endpoint": plugin.api_rename_history,
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取重命名历史",
        },
        {
            "path": "/overview",
            "endpoint": plugin.api_overview,
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取下载中心总览",
        },
        {
            "path": "/diagnostics",
            "endpoint": plugin.api_diagnostics,
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取诊断信息",
        },
        {
            "path": "/retry_renames",
            "endpoint": plugin.api_retry_renames,
            "auth": "bear",
            "methods": ["POST"],
            "summary": "一键补刀重命名",
        },
        {
            "path": "/retry_rename",
            "endpoint": plugin.api_retry_rename,
            "auth": "bear",
            "methods": ["POST"],
            "summary": "单条补刀重命名",
        },
        {
            "path": "/delete_rename_history",
            "endpoint": plugin.api_delete_rename_history,
            "auth": "bear",
            "methods": ["POST"],
            "summary": "删除重命名历史记录",
        },
        {
            "path": "/rename_archive",
            "endpoint": plugin.api_rename_archive,
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取补刀归档记录",
        },
        {
            "path": "/restore_rename_archive",
            "endpoint": plugin.api_restore_rename_archive,
            "auth": "bear",
            "methods": ["POST"],
            "summary": "恢复补刀归档记录",
        },
        {
            "path": "/delete_rename_archive",
            "endpoint": plugin.api_delete_rename_archive,
            "auth": "bear",
            "methods": ["POST"],
            "summary": "删除补刀归档记录",
        },
        {
            "path": "/recovery_torrent",
            "endpoint": plugin.api_recovery_torrent,
            "auth": "bear",
            "methods": ["POST"],
            "summary": "恢复种子原始名称",
        },
        {
            "path": "/sites",
            "endpoint": plugin.api_sites,
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取站点列表（用于辅种站点选择）",
        },
    ]
