"""下载中心 API 路由声明。"""

from functools import partial
from typing import Any, Dict, List

from .handlers import (
    api_reset_speed_monitor_baseline,
    api_tag_cleanup_execute,
    api_tag_cleanup_scan,
    api_upload_limit_disable_restore,
    api_upload_limit_reallocate,
    api_upload_limit_site_tags,
    api_upload_limit_status,
)


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
            "path": "/reset_speed_monitor_baseline",
            "endpoint": partial(api_reset_speed_monitor_baseline, plugin),
            "auth": "bear",
            "methods": ["POST"],
            "summary": "重置下载速度基准",
        },
        {
            "path": "/upload_limit_status",
            "endpoint": partial(api_upload_limit_status, plugin),
            "auth": "bear",
            "methods": ["GET"],
            "summary": "获取上传限速状态",
        },
        {
            "path": "/upload_limit_reallocate",
            "endpoint": partial(api_upload_limit_reallocate, plugin),
            "auth": "bear",
            "methods": ["POST"],
            "summary": "立即重新分配上传额度",
        },
        {
            "path": "/upload_limit_site_tags",
            "endpoint": partial(api_upload_limit_site_tags, plugin),
            "auth": "bear",
            "methods": ["POST"],
            "summary": "扫描上传限速站点标签",
        },
        {
            "path": "/upload_limit_disable_restore",
            "endpoint": partial(api_upload_limit_disable_restore, plugin),
            "auth": "bear",
            "methods": ["POST"],
            "summary": "停用上传限速并恢复原值",
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
        {
            "path": "/tag_cleanup_scan",
            "endpoint": partial(api_tag_cleanup_scan, plugin),
            "auth": "bear",
            "methods": ["POST"],
            "summary": "扫描下载器标签并清理临时标签",
        },
        {
            "path": "/tag_cleanup_execute",
            "endpoint": partial(api_tag_cleanup_execute, plugin),
            "auth": "bear",
            "methods": ["POST"],
            "summary": "按扫描快照清理标签",
        },
    ]
