"""下载中心全部模块的只读运行摘要，开关不等于正在执行。"""

from app.sdk.logging import logger

from ..model.state import IYUU_PENDING_KEY, TRANSFER_SCHEDULE_KEY
from ..model.sync_delete import TERMINAL_STATES
from ..storage.sync_delete_jobs import DeleteJobStore
from ..utils.config import is_upload_limit_active
from .activity import activity_snapshot
from .auto_delete import status_result as auto_delete_status
from .recheck import load_seed_recheck_queue


def build_module_overview(plugin, diagnostics, cards, speed, upload):
    """复用本轮诊断/统计，只补队列和删除索引，不拉下载器全量任务。"""
    enabled = bool(getattr(plugin, "_enabled", False))
    activity = activity_snapshot(plugin)
    archive = diagnostics.get("rename_archive", {})
    read_errors = {}

    def read_state(key, loader):
        """单一模块状态错误只影响该模块，不把整个总览变成空页。"""
        try:
            value = loader()
            if not isinstance(value, dict):
                raise TypeError("状态类型不符")
            return value
        except (ValueError, RuntimeError, TypeError, OSError, KeyError, AttributeError) as error:
            read_errors[key] = "模块状态读取失败（" + type(error).__name__ + "）"
            return {}

    queue = read_state("seed", lambda: load_seed_recheck_queue(plugin))
    transfer_schedule = read_state("transfer", lambda: plugin.get_data(TRANSFER_SCHEDULE_KEY) or {})
    iyuu_pending = read_state("iyuu", lambda: plugin.get_data(IYUU_PENDING_KEY) or {})
    modules = []

    def append(key, title, configured, ready, running, detail, metrics, *, error="", pending=0):
        """正常关闭、配置缺项、执行中与待处理分别表示。"""
        error = error or read_errors.get(key, "")
        running = bool(running or activity.get(key))
        state = ("error" if error else "stopping" if running and not enabled
                 else "disabled" if not enabled or not configured else "running" if running
                 else "blocked" if not ready else "attention" if pending else "idle")
        modules.append({"key": key, "title": title, "enabled": configured, "state": state,
                        "detail": error or detail, "metrics": metrics, "pending": pending, "error": error})

    transfer = cards["transfer"]
    pending_runs = getattr(plugin, "_transfer_pending_runs", {}) or {}
    append("transfer", "转移做种", transfer["enabled"], transfer["active"],
           getattr(plugin, "_transfer_running_generation", None) is not None,
           f"整理完成后延迟 {getattr(plugin, '_delay_minutes', 0)} 分钟；兜底扫描{'开启' if transfer['fallback_enabled'] else '关闭'}",
           {"今日成功": transfer["today_success"], "今日兜底": transfer["today_fallback"],
            "截至昨日累计": max(0, transfer["success_total"] - transfer["today_success"]),
            "待到期": len(pending_runs) or len(transfer_schedule.get("items", {}))})
    iyuu = cards["iyuu"]
    from ..utils.config import is_iyuu_active

    ready = is_iyuu_active(plugin)
    append("iyuu", "IYUU铺种", iyuu["enabled"], ready, bool(activity.get("iyuu")) or getattr(plugin, "_reseed_worker", None) is not None,
           "定时辅种已配置" if getattr(plugin, "_iyuu_cron", "") else "等待手动或相关事件触发",
           {"今日成功": iyuu["today_success"], "今日失败": iyuu["today_fail"],
            "截至昨日累计": max(0, iyuu["success_total"] - iyuu["today_success"]), "待后处理": len(iyuu_pending)},
           pending=len(iyuu_pending), error=getattr(plugin, "_iyuu_schedule_error", ""))
    rename = cards["rename"]
    target = diagnostics.get("downloaders", {}).get("to", {})
    downloader_configs = {}
    helper = getattr(plugin, "downloader_helper", None)
    if helper is not None:
        downloader_configs = read_state("tag", lambda: helper.get_configs())
    iyuu_targets = [getattr(plugin, "_iyuu_auto_downloader", "")] if getattr(plugin, "_iyuu_auto_downloader", "") else getattr(plugin, "_iyuu_downloaders", [])
    qb_iyuu = any(getattr(downloader_configs.get(name), "type", None) == "qbittorrent" for name in iyuu_targets)
    rename_ready = bool(target.get("available", False) and target.get("type") == "qbittorrent" or ready and qb_iyuu)
    append("rename", "命名补刀", rename["enabled"], rename_ready, bool(activity.get("rename")),
           "按转种、辅种和补刀触发；仅 qBittorrent 目标支持种子重命名",
           {"待处理": archive.get("active_failed", 0), "脏名称": rename["dirty"], "已归档": rename["archived"]},
           pending=archive.get("active_failed", 0))
    append("tag", "站点标签", bool(getattr(plugin, "_tag_enabled", False)), bool(target.get("available") or ready), bool(activity.get("tag")),
           "按转种、辅种和补刀写入站名；支持人工临时标签清理",
           {"Tracker 映射": len(getattr(plugin, "_tracker_mappings", {}) or {}),
            "标签前缀": getattr(plugin, "_tag_siteprefix", "")})
    seed_thread = getattr(plugin, "_seed_recheck_thread", None)
    queue_running = bool(queue and seed_thread and seed_thread.is_alive())
    append("seed", "做种校验", True, not queue or queue_running, queue_running,
           "自动开始做种" if getattr(plugin, "_seed_autostart", False) else "保留校验，完成后保持暂停",
           {"待校验": len(queue), "检查间隔秒": getattr(plugin, "_seed_check_interval", 60),
            "最大等待分钟": getattr(plugin, "_seed_max_wait_minutes", 120),
            "跳过校验": bool(getattr(plugin, "_seed_skipverify", False))}, pending=len(queue))
    append("archive", "补刀归档", True, True, False, "连续失败归档，可单条补刀或恢复",
           {"已归档": archive.get("archived", 0), "接近阈值": archive.get("near_archive", 0),
            "归档阈值": archive.get("threshold", 3)}, pending=archive.get("near_archive", 0))
    sync_error = ""
    try:
        summaries = DeleteJobStore(plugin).summaries()
    except (ValueError, RuntimeError, TypeError, OSError, KeyError, AttributeError) as error:
        logger.error("总览无法读取同步删除摘要（" + type(error).__name__ + "）")
        summaries, sync_error = {}, "同步删除记录读取失败（" + type(error).__name__ + "）"
    sync_queued = sum(row.get("state") in {"queued", "running"} for row in summaries.values())
    sync_pending = sum(row.get("state") not in TERMINAL_STATES | {"queued", "running"} for row in summaries.values())
    sync_enabled = bool(getattr(plugin, "_sync_delete_enabled", False))
    sync_ready = bool(getattr(plugin, "_sync_delete_source_paths", "")
                      or getattr(plugin, "_sync_delete_local_paths", "") or getattr(plugin, "_sync_delete_cloud_paths", ""))
    append("sync_delete", "同步删除", sync_enabled, sync_ready, bool(activity.get("sync_delete")),
           "接收 Emby/源文件删除事件，按历史关联精确处理",
           {"队列中或处理未完": sync_queued, "待复核": sync_pending,
            "已完成": sum(row.get("state") == "completed" for row in summaries.values())},
           error=sync_error, pending=sync_pending)
    append("monitor", "速度监控", bool(speed.get("enabled")), speed.get("service_status") != "disabled", bool(speed.get("active")),
           "按所选下载器采样，连续异常后给出处置入口",
           {"活跃会话": speed.get("active_sessions", 0), "待处理告警": speed.get("pending_alerts", 0)},
           error=speed.get("state_error", ""), pending=speed.get("pending_alerts", 0))
    upload_errors = list(upload.get("errors", [])) + [str(item["error"]) for item in upload.get("downloaders", []) if item.get("error")]
    append("upload", "上传限速", bool(getattr(plugin, "_upload_limit_enabled", False)), is_upload_limit_active(plugin),
           upload.get("service_status") == "running", "全局上传上限与跨下载器站点合计额度，每 30 秒协调",
           {"受管任务": upload.get("managed_torrents", 0), "宽限任务": upload.get("grace_torrents", 0)},
           error="；".join(dict.fromkeys(upload_errors)))
    try:
        auto = auto_delete_status(plugin)
    except (ValueError, RuntimeError, TypeError, OSError, KeyError, AttributeError) as error:
        logger.error("总览无法读取自动删除摘要（" + type(error).__name__ + "）")
        auto = {"state": "error", "error": "自动删除状态读取失败（" + type(error).__name__ + "）"}
    append("auto_delete", "自动删除", bool(auto.get("enabled")), bool(auto.get("active")), auto.get("state") == "running",
           "暂停调试与正式规则共用周期；正式启用后才删除",
           {"调试规则": auto.get("debug_rules", 0), "正式规则": auto.get("delete_rules", 0),
            "保护任务": auto.get("protected", 0), "待复核": auto.get("pending", 0),
            "最近扫描": auto.get("last_scan"), "下次运行": auto.get("next_run")},
           error=auto.get("error", "") or "；".join(auto.get("errors", [])), pending=auto.get("pending", 0))
    return modules, auto
