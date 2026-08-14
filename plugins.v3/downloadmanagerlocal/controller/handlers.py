"""下载管理插件 - API 路由实现"""

from datetime import datetime
from typing import TypeVar

from fastapi import HTTPException
from pydantic import BaseModel

from app import schemas
from app.sdk.logging import logger

from ..adapter.moviepilot import get_downloader_config, list_builtin_sites
from ..model.api import (
    ApiBusinessModel,
    DiagnosticsResult,
    EmptyRequest,
    HashActionResult,
    OverviewResult,
    RenamePageResult,
    ResetBaselineRequest,
    ResetBaselineResult,
    RetryRenamesResult,
    SelectionItem,
    TagCleanupExecuteRequest,
    TagCleanupExecuteResult,
    TagCleanupScanRequest,
    TagCleanupScanResult,
    UploadLimitDisableResult,
    UploadLimitReallocateResult,
    UploadLimitRulesRequest,
    UploadLimitRulesResult,
    UploadLimitSiteTagsRequest,
    UploadLimitSiteTagsResult,
    UploadLimitStatusResult,
)
from ..model.state import (
    RENAME_RECORDS_KEY,
    RENAME_RETRY_STATE_KEY,
    count_unique_cache_items,
    load_transfer_stats,
)
from ..service.site_tag import execute_tag_cleanup, scan_and_clean_tags
from ..service.speed_baseline import suggest_thresholds
from ..service.speed_decision import resolve_reference_speed
from ..service.speed_monitor import (
    SESSION_ACTIVE,
    load_speed_monitor_runtime_snapshot,
    reset_speed_monitor_baseline,
)
from ..service.upload_limiter import (
    get_upload_limit_status,
    persist_upload_limit_site_rules,
    restore_upload_limits,
    run_upload_limit_cycle,
    scan_upload_limit_site_tags,
)
from ..service.upload_limit_worker import stop_upload_limit_worker
from ..utils.config import is_speed_monitor_active


BusinessModelT = TypeVar("BusinessModelT", bound=ApiBusinessModel)


def _request_dict(payload: BaseModel | dict | None) -> dict:
    """把具体 Pydantic 请求模型转换为领域服务使用的普通字典。"""
    if isinstance(payload, BaseModel):
        return payload.model_dump()
    return dict(payload) if isinstance(payload, dict) else {}


def _operation_response(
    payload: dict,
    model_type: type[BusinessModelT],
) -> schemas.Response[BusinessModelT]:
    """把旧版 code 结果转换为单层 MoviePilot V3 业务响应。"""
    data = model_type.model_validate(payload)
    code = int(getattr(data, "code", 0) or 0)
    message = str(getattr(data, "msg", "") or "")
    return schemas.Response[model_type](
        success=code != 1,
        message=message,
        data=data,
    )


def _raise_query_error(summary: str, error: Exception) -> None:
    """把查询端点异常转换为明确的 HTTP 500。"""
    logger.error(f"{summary}: {error}")
    raise HTTPException(status_code=500, detail=str(error)) from error


def _speed_monitor_overview(plugin):
    """根据持久化运行态生成速度监控总览。"""
    runtime = load_speed_monitor_runtime_snapshot(plugin)
    mode = str(getattr(plugin, "_speed_monitor_mode", "auto") or "auto")
    selected = list(getattr(plugin, "_speed_monitor_downloaders", []) or [])
    manual_speeds = getattr(plugin, "_speed_monitor_manual_speed_bps", {}) or {}
    floor_speeds = getattr(plugin, "_speed_monitor_floor_speed_bps", {}) or {}
    baselines = []
    for downloader_id in selected:
        baseline = runtime.baselines.get(downloader_id, {})
        reference_speed, reference_source = resolve_reference_speed(
            mode=mode,
            downloader_id=downloader_id,
            baseline=baseline,
            manual_speeds=manual_speeds,
            floor_speeds=floor_speeds,
        )
        baselines.append({
            "downloader_id": downloader_id,
            "status": str(baseline.get("status") or "provisional"),
            "sample_count": int(baseline.get("sample_count") or 0),
            "min_samples": int(
                baseline.get("min_samples")
                or getattr(plugin, "_speed_monitor_min_samples", 5)
                or 5
            ),
            "provisional_speed_bps": float(
                baseline.get("provisional_speed_bps") or 0
            ),
            "trusted_speed_bps": float(baseline.get("trusted_speed_bps") or 0),
            "floor_speed_bps": float(floor_speeds.get(downloader_id) or 0),
            "reference_speed_bps": float(reference_speed or 0),
            "reference_source": reference_source,
            "relative_only": bool(baseline.get("relative_only", not bool(
                floor_speeds.get(downloader_id)
            ))),
            "threshold_suggestion": suggest_thresholds(
                baseline.get("samples") or [],
                trusted_speed_bps=baseline.get("trusted_speed_bps") or 0,
                min_samples=baseline.get("min_samples")
                or getattr(plugin, "_speed_monitor_min_samples", 5)
                or 5,
            ),
        })

    alert_counts = {"pending": 0, "notified": 0, "confirming": 0}
    dispositions = []
    for alert in runtime.alerts.values():
        if not isinstance(alert, dict):
            continue
        status = str(alert.get("status") or "")
        if status in alert_counts:
            alert_counts[status] += 1
        if alert.get("last_action") or alert.get("handled_at"):
            timestamp = max(
                float(alert.get("handled_at") or 0),
                float(alert.get("updated_at") or 0),
                float(alert.get("notified_at") or 0),
            )
            dispositions.append((timestamp, alert))
    last_disposition = None
    if dispositions:
        timestamp, alert = max(dispositions, key=lambda item: item[0])
        deletion_result = alert.get("deletion_result") or {}
        last_disposition = {
            "downloader_id": str(alert.get("downloader_id") or ""),
            "torrent_hash": str(alert.get("torrent_hash") or ""),
            "name": str(alert.get("name") or ""),
            "status": str(alert.get("status") or ""),
            "action": str(alert.get("last_action") or alert.get("status") or ""),
            "success": deletion_result.get("success"),
            "error": str(deletion_result.get("error") or ""),
            "updated_at": timestamp,
        }

    state_error = str(runtime.state_error or getattr(
        plugin, "_speed_monitor_state_error", ""
    ) or "")
    active_sessions = sum(
        session.status == SESSION_ACTIVE for session in runtime.sessions.values()
    )
    configured = bool(is_speed_monitor_active(plugin) and not state_error)
    active = bool(configured and active_sessions > 0)
    if state_error:
        service_status = "error"
    elif not configured:
        service_status = "disabled"
    elif active:
        service_status = "running"
    else:
        service_status = "idle"
    return {
        "enabled": bool(getattr(plugin, "_speed_monitor_enabled", False)),
        "active": active,
        "service_status": service_status,
        "state_error": state_error,
        "mode": mode,
        "selected_downloaders": selected,
        "active_sessions": active_sessions,
        "pending_alerts": sum(alert_counts.values()),
        "alert_counts": alert_counts,
        "baselines": baselines,
        "last_disposition": last_disposition,
    }


def api_retry_renames(plugin):
    """手动触发失败历史和脏名称种子的批量补刮。"""
    try:
        return _operation_response(plugin._retry_pending_renames(), RetryRenamesResult)
    except Exception as e:
        logger.error(f"一键补刀失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"补刀失败: {e}", "history": 0, "dirty": 0, "total": 0},
            RetryRenamesResult,
        )


def api_retry_rename(plugin, hash: str = ""):
    """对指定种子 hash 手动重试重命名和站点标签。"""
    try:
        return _operation_response(plugin._retry_rename(hash), HashActionResult)
    except Exception as e:
        logger.error(f"单条补刀失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"补刀失败: {e}", "hash": hash or ""},
            HashActionResult,
        )


def api_diagnostics(plugin):
    """返回详情页使用的只读诊断摘要。"""
    try:
        return DiagnosticsResult.model_validate(plugin._diagnostics())
    except Exception as e:
        _raise_query_error("诊断信息生成失败", e)


def api_overview(plugin):
    """返回详情页总览数据。"""
    try:
        diagnostics = plugin._diagnostics()
        archive = plugin.rename_archive_stats()
        upload_limit = get_upload_limit_status(plugin)
        transfer_stats = load_transfer_stats(plugin)
        iyuu_success_total = count_unique_cache_items(
            getattr(plugin, "_iyuu_success_caches", []),
        )
        iyuu_fail_total = count_unique_cache_items(
            getattr(plugin, "_iyuu_error_caches", []),
            getattr(plugin, "_iyuu_permanent_error_caches", []),
        )
        rename_history = diagnostics.get("rename_history", {}) if isinstance(diagnostics, dict) else {}
        return OverviewResult.model_validate({
            "code": 0,
            "plugin": diagnostics.get("plugin", {}) if isinstance(diagnostics, dict) else {},
            "config": diagnostics.get("config", {}) if isinstance(diagnostics, dict) else {},
            "downloaders": diagnostics.get("downloaders", {}) if isinstance(diagnostics, dict) else {},
            "rename_history": rename_history,
            "archive": archive,
            "speed_monitor": _speed_monitor_overview(plugin),
            "upload_limit": upload_limit,
            "cards": {
                "upload_limit": {
                    "enabled": bool(getattr(plugin, "_upload_limit_enabled", False)),
                    "active": bool(upload_limit.get("active")),
                    "managed": int(upload_limit.get("managed_torrents") or 0),
                    "grace": int(upload_limit.get("grace_torrents") or 0),
                },
                "transfer": {
                    "enabled": bool(getattr(plugin, "_transfer_enabled", False)),
                    "active": bool(getattr(plugin, "_transfer_active", False)),
                    "fallback_enabled": bool(getattr(plugin, "_transfer_fallback_enabled", False)),
                    "success_total": int(transfer_stats["success_total"]),
                    "fallback_success": int(transfer_stats["fallback_success"]),
                },
                "iyuu": {
                    "enabled": bool(getattr(plugin, "_iyuu_enabled", False)),
                    "success": int(getattr(plugin, "_iyuu_success", 0) or 0),
                    "fail": int(getattr(plugin, "_iyuu_fail", 0) or 0),
                    "cached": int(getattr(plugin, "_iyuu_cached", 0) or 0),
                    "success_total": iyuu_success_total,
                    "fail_total": iyuu_fail_total,
                },
                "rename": {
                    "enabled": bool(getattr(plugin, "_rename_enabled", False)),
                    "failed": int(rename_history.get("failed", 0) or 0),
                    "dirty": int(rename_history.get("dirty", 0) or 0),
                    "archived": int(archive.get("archived", 0) or 0),
                },
                "seed": {
                    "autostart": bool(getattr(plugin, "_seed_autostart", False)),
                    "skipverify": bool(getattr(plugin, "_seed_skipverify", False)),
                },
            },
        })
    except Exception as e:
        _raise_query_error("总览信息生成失败", e)


def api_reset_speed_monitor_baseline(plugin, payload: ResetBaselineRequest):
    """显式重置一个下载器的自动速度基准。"""
    try:
        request = _request_dict(payload)
        result = reset_speed_monitor_baseline(
            plugin, request.get("downloader_id") or ""
        )
        return _operation_response(
            {
                "code": 0 if result.get("success") else 1,
                "msg": "速度基准已重置" if result.get("success") else result.get("error", "重置失败"),
                **result,
            },
            ResetBaselineResult,
        )
    except Exception as e:
        logger.error(f"速度基准重置失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"重置失败: {e}", "success": False},
            ResetBaselineResult,
        )


def api_upload_limit_status(plugin):
    """返回上传限速配置页状态。"""
    try:
        return UploadLimitStatusResult.model_validate(
            {"code": 0, **get_upload_limit_status(plugin)}
        )
    except Exception as e:
        _raise_query_error("上传限速状态读取失败", e)


def api_upload_limit_reallocate(plugin, payload: EmptyRequest | None = None):
    """立即执行一轮上传额度重新分配。"""
    try:
        result = run_upload_limit_cycle(plugin, reason="manual")
        return _operation_response(
            {"code": 0 if not result.get("errors") else 2, "msg": "上传额度已重新分配", **result},
            UploadLimitReallocateResult,
        )
    except Exception as e:
        logger.error(f"上传额度重新分配失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"重新分配失败: {e}"},
            UploadLimitReallocateResult,
        )


def api_upload_limit_site_tags(plugin, payload: UploadLimitSiteTagsRequest):
    """扫描指定下载器中的站点前缀标签。"""
    try:
        request = _request_dict(payload)
        result = scan_upload_limit_site_tags(
            plugin, request.get("downloaders")
        )
        request_rules = request.get("rules")
        rules = dict(
            request_rules
            if isinstance(request_rules, dict)
            else (getattr(plugin, "_upload_limit_site_rules", {}) or {})
        )
        for item in result.get("items") or []:
            name = str(item.get("name") or "").strip()
            if name:
                rules.setdefault(name, {"limit_kib": 0})
        result["rules"] = persist_upload_limit_site_rules(plugin, rules)
        result["msg"] = "站点标签扫描完成，策略已立即生效" if result.get("code") == 0 else result.get("msg")
        return _operation_response(result, UploadLimitSiteTagsResult)
    except Exception as e:
        logger.error(f"上传限速站点标签扫描失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"扫描失败: {e}", "items": [], "errors": [], "rules": {}},
            UploadLimitSiteTagsResult,
        )


def api_upload_limit_site_rules_update(plugin, payload: UploadLimitRulesRequest):
    """立即保存上传限速站点策略，不触发重新分配。"""
    try:
        request = _request_dict(payload)
        rules = persist_upload_limit_site_rules(plugin, request.get("rules"))
        return _operation_response(
            {
                "code": 0,
                "msg": "站点策略已清空并立即生效" if not rules else "站点策略已立即生效",
                "rules": rules,
            },
            UploadLimitRulesResult,
        )
    except Exception as e:
        logger.error(f"上传限速站点策略保存失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"站点策略保存失败: {e}", "rules": {}},
            UploadLimitRulesResult,
        )


def api_upload_limit_disable_restore(plugin, payload: EmptyRequest | None = None):
    """停用上传限速、停止协调 worker 并恢复接管前设置。"""
    try:
        config = dict(plugin.get_config() or {})
        config["upload_limit_enabled"] = False
        plugin._upload_limit_enabled = False
        stop_upload_limit_worker(plugin)
        plugin.update_config(config=config)
        result = restore_upload_limits(plugin)
        return _operation_response(result, UploadLimitDisableResult)
    except Exception as e:
        logger.error(f"停用并恢复上传限速失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"停用恢复失败: {e}", "errors": [str(e)]},
            UploadLimitDisableResult,
        )


def api_downloaders(plugin):
    """返回可用下载器列表"""
    try:
        services = plugin.downloader_helper.get_services()
        result = []
        if services:
            for name, info in services.items():
                result.append({
                    "title": name,
                    "value": name,
                    "type": info.type,
                })
        return [SelectionItem.model_validate(item) for item in result]
    except Exception as e:
        _raise_query_error("获取下载器列表失败", e)


def api_sites(plugin):
    """返回 V3 站点数据库中的可用站点列表。"""
    try:
        custom_sites = plugin._custom_sites()
        result = [{"title": site.name, "value": site.id}
                  for site in list_builtin_sites()]
        result += [{"title": site.get("name"), "value": site.get("id")}
                   for site in custom_sites]
        return [SelectionItem.model_validate(item) for item in result]
    except Exception as e:
        _raise_query_error("获取站点列表失败", e)


def api_tag_cleanup_scan(plugin, payload: TagCleanupScanRequest):
    """扫描所选 qBittorrent 下载器并自动清理明确的临时标签。"""
    try:
        request = _request_dict(payload)
        result = scan_and_clean_tags(plugin, request.get("downloaders") or [])
        return _operation_response(result, TagCleanupScanResult)
    except Exception as e:
        logger.error(f"标签清理扫描失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"扫描失败: {e}", "downloaders": [], "auto_removed": [], "errors": []},
            TagCleanupScanResult,
        )


def api_tag_cleanup_execute(plugin, payload: TagCleanupExecuteRequest):
    """按用户确认的扫描快照清理其余标签。"""
    try:
        request = _request_dict(payload)
        result = execute_tag_cleanup(plugin, request.get("removals") or [])
        return _operation_response(result, TagCleanupExecuteResult)
    except Exception as e:
        logger.error(f"标签清理执行失败: {e}")
        return _operation_response(
            {"code": 1, "msg": f"清理失败: {e}", "removed": [], "failed": []},
            TagCleanupExecuteResult,
        )


def api_rename_history(plugin, page: int = 1, page_size: int = 15):
    """返回重命名历史记录（支持分页）"""
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 15)))
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    retry_state = plugin.get_data(RENAME_RETRY_STATE_KEY) or {}
    archived_hashes = {
        record_hash
        for record_hash, state in retry_state.items()
        if isinstance(state, dict) and state.get("archived")
    } if isinstance(retry_state, dict) else set()
    items = []
    for record_hash, record in records.items():
        if not isinstance(record, dict):
            continue
        if record_hash in archived_hashes:
            continue
        item = dict(record)
        item["hash"] = item.get("hash") or record_hash
        items.append(item)
    all_items = sorted(items, key=lambda x: x.get("time", ""), reverse=True)
    total = len(all_items)
    start = (page - 1) * page_size
    end = start + page_size
    return RenamePageResult.model_validate({
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "items": all_items[start:end]
    })


def api_delete_rename_history(plugin, hash: str = ""):
    """删除指定 hash 的重命名记录"""
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    if hash in records:
        del records[hash]
        plugin.save_data(RENAME_RECORDS_KEY, records)
        return _operation_response(
            {"code": 0, "msg": "已删除", "hash": hash},
            HashActionResult,
        )
    return _operation_response(
        {"code": 1, "msg": "记录不存在", "hash": hash},
        HashActionResult,
    )


def api_rename_archive(plugin, page: int = 1, page_size: int = 15):
    """返回补刀归档记录（支持分页）。"""
    return RenamePageResult.model_validate(plugin.list_rename_archive(page, page_size))


def api_restore_rename_archive(plugin, hash: str = ""):
    """恢复归档记录，使其继续参与补刀。"""
    return _operation_response(plugin.restore_rename_archive(hash), HashActionResult)


def api_delete_rename_archive(plugin, hash: str = ""):
    """删除归档状态记录。"""
    return _operation_response(plugin.delete_rename_archive(hash), HashActionResult)


def api_recovery_torrent(plugin, hash: str = ""):
    """恢复种子原始名称"""
    if not hash:
        return _operation_response(
            {"code": 1, "msg": "缺少 hash 参数", "hash": ""},
            HashActionResult,
        )
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    record = records.get(hash)
    if not record or not record.get("success"):
        return _operation_response(
            {"code": 1, "msg": "未找到成功的重命名记录", "hash": hash},
            HashActionResult,
        )
    original_name = record.get("original_name")
    if not original_name:
        return _operation_response(
            {"code": 1, "msg": "原始名称为空", "hash": hash},
            HashActionResult,
        )

    # 在目标下载器中查找并恢复
    try:
        to_config = get_downloader_config(plugin._todownloader)
        if not to_config:
            return _operation_response(
                {"code": 1, "msg": f"下载器 {plugin._todownloader} 不存在", "hash": hash},
                HashActionResult,
            )
        dl = to_config.instance
        dl_type = to_config.type

        if dl_type == "qbittorrent":
            dl.qbc.torrents_rename(torrent_hash=hash, new_torrent_name=original_name)
        else:
            dl.rename_torrent(hash, original_name)

        # 更新记录
        record["after_name"] = original_name
        record["success"] = True
        record["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        records[hash] = record
        plugin.save_data(RENAME_RECORDS_KEY, records)
        logger.info(f"种子恢复成功: {hash} → {original_name}")
        return _operation_response(
            {"code": 0, "msg": f"已恢复为: {original_name}", "hash": hash},
            HashActionResult,
        )
    except Exception as e:
        logger.error(f"种子恢复失败: {e}")
        return _operation_response(
            {"code": 1, "msg": str(e), "hash": hash},
            HashActionResult,
        )
