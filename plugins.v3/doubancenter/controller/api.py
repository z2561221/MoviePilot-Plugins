"""DoubanCenter V3 API 路由与统一响应控制层。"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from app import schemas
from app.sdk.logging import logger
from app.sdk.media import resolve_media_identity
from fastapi import HTTPException

from ..service import dashboard as dash
from ..service import folio, folio_repair
from ..service import rank_pipeline as feed
from . import schemas as api_schemas


def _response_model(path: str):
    """返回指定路由的具体 V3 响应模型。"""
    return schemas.Response[api_schemas.API_RESPONSE_MODELS[path]]


def get_api(plugin) -> List[Dict[str, Any]]:
    """返回 MoviePilot V3 插件 API 路由声明。"""
    definitions = [
        ("/folio_data", plugin.api_folio_data, ["GET"], "获取豆瓣时间数据"),
        ("/overview", plugin.api_overview, ["GET"], "获取运行总览"),
        ("/config", plugin.api_config, ["GET"], "获取插件配置"),
        ("/rank_history", plugin.api_rank_history, ["GET"], "获取榜单历史"),
        ("/resolve_media", plugin.api_resolve_media, ["GET"], "识别榜单媒体"),
        ("/subscribe", plugin.api_subscribe, ["GET", "POST"], "一键订阅"),
        ("/refresh_rss", plugin.api_refresh_rss, ["POST"], "刷新 RSS 榜单数据"),
        ("/stats", plugin.api_stats, ["GET"], "获取订阅统计"),
        ("/subscribe_history", plugin.api_subscribe_history, ["GET"], "获取订阅历史"),
        ("/pending_observations", plugin.api_pending_observations, ["GET"], "获取观察期待订阅条目"),
        ("/anti_cheat_logs", plugin.api_anti_cheat_logs, ["GET"], "获取观察日志"),
        ("/delete_subscribe_history", plugin.api_delete_subscribe_history, ["POST"], "删除订阅历史记录"),
        ("/delete_observation", plugin.api_delete_observation, ["POST"], "删除观察队列条目"),
        ("/delete_anti_cheat_log", plugin.api_delete_anti_cheat_log, ["POST"], "删除观察日志"),
        ("/archive_records", plugin.api_archive_records, ["GET"], "获取归档记录"),
        ("/restore_archive", plugin.api_restore_archive, ["POST"], "恢复归档记录"),
        ("/delete_archive", plugin.api_delete_archive, ["POST"], "彻底删除归档记录"),
        ("/repair_folio_posters", plugin.api_repair_folio_posters, ["POST"], "修复豆瓣时间线海报"),
        ("/folio_repair/preview", plugin.api_folio_repair_preview, ["POST"], "预览观影档案分季修正"),
        ("/folio_repair/apply", plugin.api_folio_repair_apply, ["POST"], "应用已核验的观影档案修正"),
    ]
    return [
        {
            "path": path,
            "endpoint": endpoint,
            "methods": methods,
            "auth": "bear",
            "summary": summary,
            "response_model": _response_model(path),
        }
        for path, endpoint, methods, summary in definitions
    ]


def _to_response(result: Any, data_model, *, default_message: str = ""):
    """把现有业务 service 结果转换为单层 V3 响应。"""
    if isinstance(result, schemas.Response):
        return result
    if isinstance(result, dict):
        success = bool(result.get("success", result.get("code") != 1))
        message = str(result.get("message") or result.get("msg") or default_message or "")
        if "data" in result:
            payload = result.get("data")
        else:
            payload = {
                key: value
                for key, value in result.items()
                if key not in {"success", "message", "msg", "code"}
            }
            if not payload:
                payload = None
    else:
        success = True
        message = default_message
        payload = result
    data = data_model.model_validate(payload) if payload is not None else None
    return schemas.Response(success=success, message=message, data=data)


def _invoke(data_model, callback: Callable, *, error_message: str, **kwargs):
    """执行业务函数并将未预期异常交给 V3 HTTP 错误层。"""
    try:
        return _to_response(callback(**kwargs), data_model)
    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"豆瓣中心 V3 API 异常：{err}", exc_info=True)
        raise HTTPException(status_code=500, detail=error_message) from err


def _normalize_request_identity(media_source: Any, media_id: Any):
    """校验并规范化请求中的媒体身份对。"""
    if media_source is None and media_id is None:
        return None, None
    source, normalized_id = resolve_media_identity(
        media_source=media_source,
        media_id=media_id,
    )
    if not source or not normalized_id:
        raise HTTPException(status_code=400, detail="媒体来源和媒体 ID 必须同时提供且有效")
    return source, normalized_id


def api_folio_data(plugin, raw: bool = False):
    """返回豆瓣时间数据。"""
    return _invoke(api_schemas.FolioData, dash.api_folio_data, error_message="获取豆瓣时间数据失败", self=plugin, raw=raw)


def api_folio_repair_preview(plugin, request: api_schemas.FolioRepairPreviewRequest):
    """规范化源身份并返回只读修正预览。"""
    targets = []
    for item in request.items:
        source, media_id = _normalize_request_identity(item.media_source, item.media_id)
        targets.append({**item.model_dump(), "media_source": source.value, "media_id": media_id})
    try:
        result = folio_repair.preview(plugin, targets, refresh_posters=request.refresh_posters)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return _to_response(result, api_schemas.FolioRepairPreviewData)


def api_folio_repair_apply(plugin, request: api_schemas.FolioRepairApplyRequest):
    """在并发校验和备份通过后应用修复。"""
    try:
        result = folio_repair.apply(plugin, request.plan_id)
    except ValueError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    return _to_response(result, api_schemas.FolioRepairApplyData)


def api_overview(plugin):
    """返回前端运行总览。"""
    return _invoke(api_schemas.OverviewData, dash.api_overview, error_message="获取运行总览失败", self=plugin)


def api_config(plugin):
    """返回前端配置页所需数据。"""
    return _invoke(api_schemas.ConfigData, dash.api_config, error_message="获取插件配置失败", self=plugin)


def api_rank_history(plugin):
    """返回仪表盘榜单历史。"""
    return _invoke(api_schemas.RankHistoryData, dash.api_rank_history, error_message="获取榜单历史失败", self=plugin)


def api_resolve_media(
    plugin,
    media_type=None,
    title="",
    year="",
    tmdb_id=None,
    bangumi_id=None,
    media_source=None,
    media_id=None,
    season=None,
):
    """将榜单条目识别为 V3 媒体身份。"""
    media_source, media_id = _normalize_request_identity(media_source, media_id)
    if not title and not media_id and not tmdb_id and not bangumi_id:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    return _invoke(
        api_schemas.ResolveMediaData,
        dash.api_resolve_media_from_rank,
        error_message="识别媒体失败",
        self=plugin,
        media_type=media_type,
        title=title,
        year=year,
        tmdb_id=tmdb_id,
        bangumi_id=bangumi_id,
        media_source=media_source,
        media_id=media_id,
        season=season,
    )


def api_subscribe(
    plugin,
    tmdb_id=None,
    media_type=None,
    title="",
    year="",
    bangumi_id=None,
    media_source=None,
    media_id=None,
    rank_key="",
    rank_name="",
    source_link="",
    season=None,
):
    """根据榜单条目创建 V3 媒体订阅。"""
    media_source, media_id = _normalize_request_identity(media_source, media_id)
    if not title and not media_id and not tmdb_id and not bangumi_id:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    return _invoke(
        api_schemas.SubscribeData,
        dash.api_subscribe_from_rank,
        error_message="创建订阅失败",
        self=plugin,
        tmdb_id=tmdb_id,
        media_type=media_type,
        title=title,
        year=year,
        bangumi_id=bangumi_id,
        media_source=media_source,
        media_id=media_id,
        rank_key=rank_key,
        rank_name=rank_name,
        source_link=source_link,
        season=season,
    )


def api_refresh_rss(plugin):
    """刷新 RSS 榜单数据但不主动创建订阅。"""
    def _refresh():
        rank_keys = plugin._dashboard_rank_keys or None
        return {"data": feed.refresh_rank_data(plugin, rank_keys=rank_keys)}

    return _invoke(api_schemas.RefreshRssData, _refresh, error_message="刷新 RSS 失败")


def api_stats(plugin):
    """返回订阅统计数据。"""
    return _invoke(api_schemas.StatsData, dash.api_stats, error_message="获取统计失败", self=plugin)


def api_subscribe_history(plugin, page=1, page_size=20):
    """分页返回订阅历史。"""
    return _invoke(
        api_schemas.SubscribeHistoryData,
        dash.api_subscribe_history,
        error_message="获取订阅历史失败",
        self=plugin,
        page=int(page),
        page_size=int(page_size),
    )


def api_pending_observations(plugin):
    """返回仍处于观察期的榜单条目。"""
    return _invoke(api_schemas.PendingObservationsData, dash.api_pending_observations, error_message="获取观察期条目失败", self=plugin)


def api_anti_cheat_logs(plugin):
    """返回观察日志。"""
    return _invoke(api_schemas.AntiCheatLogsData, dash.api_anti_cheat_logs, error_message="获取观察日志失败", self=plugin)


def api_delete_subscribe_history(plugin, time="", title="", tmdbid=None, media_source=None, media_id=None):
    """删除并归档一条订阅历史。"""
    return _invoke(
        api_schemas.DeleteSubscribeHistoryData,
        dash.api_delete_subscribe_history,
        error_message="删除订阅历史失败",
        self=plugin,
        time=time,
        title=title,
        tmdbid=tmdbid,
        media_source=media_source,
        media_id=media_id,
    )


def api_delete_observation(plugin, unique="", rank_key="", title=""):
    """删除并归档一条观察队列记录。"""
    return _invoke(
        api_schemas.DeleteObservationData,
        dash.api_delete_observation,
        error_message="删除观察条目失败",
        self=plugin,
        unique=unique,
        rank_key=rank_key,
        title=title,
    )


def api_delete_anti_cheat_log(plugin, time="", title="", reason=""):
    """删除并归档一条观察日志。"""
    return _invoke(
        api_schemas.DeleteAntiCheatLogData,
        dash.api_delete_anti_cheat_log,
        error_message="删除观察日志失败",
        self=plugin,
        time=time,
        title=title,
        reason=reason,
    )


def api_archive_records(plugin, page=1, page_size=20):
    """分页返回归档记录。"""
    return _invoke(
        api_schemas.ArchiveRecordsData,
        dash.api_archive_records,
        error_message="获取归档记录失败",
        self=plugin,
        page=int(page),
        page_size=int(page_size),
    )


def api_restore_archive(plugin, archive_id=""):
    """恢复一条归档记录。"""
    return _invoke(
        api_schemas.RestoreArchiveData,
        dash.api_restore_archive,
        error_message="恢复归档记录失败",
        self=plugin,
        archive_id=archive_id,
    )


def api_delete_archive(plugin, archive_id=""):
    """彻底删除一条归档记录。"""
    return _invoke(
        api_schemas.DeleteArchiveData,
        dash.api_delete_archive,
        error_message="删除归档记录失败",
        self=plugin,
        archive_id=archive_id,
    )


def api_repair_folio_posters(plugin):
    """修复历史豆瓣时间线中的失效豆瓣海报。"""
    def repair():
        """与播放同步及身份修复使用同一把锁。"""
        with plugin._sync_lock:
            return {"updated": folio.repair_folio_history(plugin)}

    return _invoke(
        api_schemas.RepairFolioPostersData,
        repair,
        error_message="修复豆瓣时间线海报失败",
    )
