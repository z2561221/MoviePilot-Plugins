"""API controller facade for DoubanCenter."""

from typing import Any, Dict, List

from app.log import logger

from .. import dashboard as dash
from .. import feed


def get_api(plugin) -> List[Dict[str, Any]]:
    """Return MoviePilot plugin API route declarations."""
    return [
        {"path": "/folio_data", "endpoint": plugin.api_folio_data, "methods": ["GET"], "auth": "bear", "summary": "获取豆瓣时间数据"},
        {"path": "/overview", "endpoint": plugin.api_overview, "methods": ["GET"], "auth": "bear", "summary": "获取运行总览"},
        {"path": "/config", "endpoint": plugin.api_config, "methods": ["GET"], "auth": "bear", "summary": "获取插件配置"},
        {"path": "/rank_history", "endpoint": plugin.api_rank_history, "methods": ["GET"], "auth": "bear", "summary": "获取榜单历史"},
        {"path": "/resolve_media", "endpoint": plugin.api_resolve_media, "methods": ["GET"], "auth": "bear", "summary": "识别榜单媒体"},
        {"path": "/subscribe", "endpoint": plugin.api_subscribe, "methods": ["GET", "POST"], "auth": "bear", "summary": "一键订阅"},
        {"path": "/refresh_rss", "endpoint": plugin.api_refresh_rss, "methods": ["POST"], "auth": "bear", "summary": "刷新 RSS 榜单数据"},
        {"path": "/stats", "endpoint": plugin.api_stats, "methods": ["GET"], "auth": "bear", "summary": "获取订阅统计"},
        {"path": "/subscribe_history", "endpoint": plugin.api_subscribe_history, "methods": ["GET"], "auth": "bear", "summary": "获取订阅历史"},
        {"path": "/pending_observations", "endpoint": plugin.api_pending_observations, "methods": ["GET"], "auth": "bear", "summary": "获取观察期待订阅条目"},
        {"path": "/anti_cheat_logs", "endpoint": plugin.api_anti_cheat_logs, "methods": ["GET"], "auth": "bear", "summary": "获取观察日志"},
        {"path": "/delete_subscribe_history", "endpoint": plugin.api_delete_subscribe_history, "methods": ["POST"], "auth": "bear", "summary": "删除订阅历史记录"},
        {"path": "/delete_observation", "endpoint": plugin.api_delete_observation, "methods": ["POST"], "auth": "bear", "summary": "删除观察队列条目"},
        {"path": "/delete_anti_cheat_log", "endpoint": plugin.api_delete_anti_cheat_log, "methods": ["POST"], "auth": "bear", "summary": "删除观察日志"},
        {"path": "/archive_records", "endpoint": plugin.api_archive_records, "methods": ["GET"], "auth": "bear", "summary": "获取归档记录"},
        {"path": "/restore_archive", "endpoint": plugin.api_restore_archive, "methods": ["POST"], "auth": "bear", "summary": "恢复归档记录"},
        {"path": "/delete_archive", "endpoint": plugin.api_delete_archive, "methods": ["POST"], "auth": "bear", "summary": "删除归档记录"},
    ]


def api_folio_data(plugin):
    return dash.api_folio_data(plugin)


def api_overview(plugin):
    """Return settings page overview data."""
    try:
        return dash.api_overview(plugin)
    except Exception as err:
        logger.error(f"豆瓣中心：api_overview 异常：{err}", exc_info=True)
        return {"code": 1, "msg": f"获取运行总览失败：{err}"}


def api_config(plugin):
    return dash.api_config(plugin)


def api_rank_history(plugin):
    return dash.api_rank_history(plugin)


def api_resolve_media(plugin, media_type=None, title="", year="", tmdb_id=None, bangumi_id=None):
    """Resolve a rank item to media metadata."""
    try:
        if not title and not tmdb_id and not bangumi_id:
            return {"success": False, "message": "缺少必要参数"}
        return dash.api_resolve_media_from_rank(
            plugin,
            media_type,
            title,
            year,
            tmdb_id=tmdb_id,
            bangumi_id=bangumi_id,
        )
    except Exception as err:
        logger.error(f"豆瓣中心：api_resolve_media 异常：{err}", exc_info=True)
        return {"success": False, "message": f"识别失败：{err}"}


def api_subscribe(plugin, tmdb_id=None, media_type=None, title="", year="", bangumi_id=None):
    """Create a subscription from a rank item."""
    try:
        if not title and not tmdb_id and not bangumi_id:
            return {"success": False, "message": "缺少必要参数"}
        return dash.api_subscribe_from_rank(
            plugin,
            tmdb_id,
            media_type,
            title,
            year,
            bangumi_id=bangumi_id,
        )
    except Exception as err:
        logger.error(f"豆瓣中心：api_subscribe 异常：{err}", exc_info=True)
        return {"success": False, "message": f"订阅失败：{err}"}


def api_refresh_rss(plugin):
    """Refresh RSS rank data without creating subscriptions."""
    try:
        logger.info("豆瓣中心：api_refresh_rss 被调用")
        rank_keys = plugin._dashboard_rank_keys or None
        logger.info(f"豆瓣中心：refresh_rss rank_keys={rank_keys}")
        result = feed.refresh_rank_data(plugin, rank_keys=rank_keys)
        return {"success": True, "message": "RSS 刷新完成", "data": result}
    except Exception as err:
        logger.error(f"豆瓣中心：api_refresh_rss 异常：{err}", exc_info=True)
        return {"success": False, "message": f"刷新失败：{err}"}


def api_stats(plugin):
    """Return subscription statistics."""
    try:
        return dash.api_stats(plugin)
    except Exception as err:
        logger.error(f"豆瓣中心：api_stats 异常：{err}", exc_info=True)
        return {"success": False, "message": f"获取统计失败：{err}"}


def api_subscribe_history(plugin, page=1, page_size=20):
    """Return paged subscription history."""
    try:
        return dash.api_subscribe_history(plugin, page=int(page), page_size=int(page_size))
    except Exception as err:
        logger.error(f"豆瓣中心：api_subscribe_history 异常：{err}", exc_info=True)
        return {"success": False, "message": f"获取订阅历史失败：{err}"}


def api_pending_observations(plugin):
    """Return rank items still in observation window."""
    try:
        return dash.api_pending_observations(plugin)
    except Exception as err:
        logger.error(f"豆瓣中心：api_pending_observations 异常：{err}", exc_info=True)
        return {"success": False, "message": f"获取观察期条目失败：{err}"}


def api_anti_cheat_logs(plugin):
    """Return observation logs."""
    try:
        return dash.api_anti_cheat_logs(plugin)
    except Exception as err:
        logger.error(f"豆瓣中心：api_anti_cheat_logs 异常：{err}", exc_info=True)
        return {"success": False, "message": f"获取观察日志失败：{err}"}


def api_delete_subscribe_history(plugin, time="", title="", tmdbid=None):
    """Delete and archive one subscription history item."""
    try:
        return dash.api_delete_subscribe_history(plugin, time=time, title=title, tmdbid=tmdbid)
    except Exception as err:
        logger.error(f"豆瓣中心：api_delete_subscribe_history 异常：{err}", exc_info=True)
        return {"success": False, "message": f"删除订阅历史失败：{err}"}


def api_delete_observation(plugin, unique="", rank_key="", title=""):
    """Delete and archive one observation queue item."""
    try:
        return dash.api_delete_observation(plugin, unique=unique, rank_key=rank_key, title=title)
    except Exception as err:
        logger.error(f"豆瓣中心：api_delete_observation 异常：{err}", exc_info=True)
        return {"success": False, "message": f"删除观察条目失败：{err}"}


def api_delete_anti_cheat_log(plugin, time="", title="", reason=""):
    """Delete and archive one observation log."""
    try:
        return dash.api_delete_anti_cheat_log(plugin, time=time, title=title, reason=reason)
    except Exception as err:
        logger.error(f"豆瓣中心：api_delete_anti_cheat_log 异常：{err}", exc_info=True)
        return {"success": False, "message": f"删除观察日志失败：{err}"}


def api_archive_records(plugin, page=1, page_size=20):
    """Return paged archive records."""
    try:
        return dash.api_archive_records(plugin, page=int(page), page_size=int(page_size))
    except Exception as err:
        logger.error(f"豆瓣中心：api_archive_records 异常：{err}", exc_info=True)
        return {"success": False, "message": f"获取归档记录失败：{err}"}


def api_restore_archive(plugin, archive_id=""):
    """Restore one archive record."""
    try:
        return dash.api_restore_archive(plugin, archive_id=archive_id)
    except Exception as err:
        logger.error(f"豆瓣中心：api_restore_archive 异常：{err}", exc_info=True)
        return {"success": False, "message": f"恢复归档记录失败：{err}"}


def api_delete_archive(plugin, archive_id=""):
    """Permanently delete one archive record."""
    try:
        return dash.api_delete_archive(plugin, archive_id=archive_id)
    except Exception as err:
        logger.error(f"豆瓣中心：api_delete_archive 异常：{err}", exc_info=True)
        return {"success": False, "message": f"删除归档记录失败：{err}"}
