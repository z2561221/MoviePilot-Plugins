"""工具中心自持的清理库存服务。"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.sdk.logging import logger
from apscheduler.triggers.cron import CronTrigger

from ..adapter.cleanup_notification import CleanupReportNotifier
from ..adapter.media_server import MediaServerCleanupAdapter
from ..model.cleanup_config import default_cleanup_config, normalize_cleanup_config
from ..model.library_cleanup import (
    CleanupCandidate,
    CleanupResult,
    CleanupVerification,
    build_cleanup_conditions,
    candidate_from_plan_item,
    cleanup_plan_key,
    evaluate_cleanup_candidate,
    filter_cleanup_candidates,
    parse_datetime,
)
from ..security import redact_sensitive_text, safe_error_text
from .base import BaseToolModule
from .cleanup_alerts import CleanupAlerts
from .cleanup_execution import CleanupCancelled, CleanupExecution
from .cleanup_report import REPORT_TITLE, build_report

_options_cache = {}
PLAN_DATA_KEY = "library_cleanup_plan"
PLAN_VERSION = 1
DEFAULT_BATCH_SIZE = 10
DEFAULT_COOLDOWN_MINUTES = 60


class LibraryCleanupModule(BaseToolModule):
    """清理库存模块，负责分析媒体候选项并按配置通知或删除。"""

    module_key = "library_cleanup"
    module_name = "清理库存"
    last_error = ""
    verification_attempts = 3
    verification_delay = 2

    def __init__(
        self,
        plugin,
        adapter: Optional[MediaServerCleanupAdapter] = None,
        notifier_factory=CleanupReportNotifier,
    ):
        """初始化清理库存模块。"""
        super().__init__(plugin)
        self.adapter = adapter or MediaServerCleanupAdapter()
        self._notifier_factory = notifier_factory
        self._run_lock = CleanupExecution(plugin.get_data_path())

    def stop(self):
        """取消尚未发起的请求，旧批次持有文件锁完成已处理项收尾。"""
        self.config["scan_enabled"] = False
        self.config["cleanup_enabled"] = False
        self._run_lock.cancel()

    def _stopped_result(self, operation):
        return {"success": True, "summary": "任务已停止，未处理条目保留", "operation": operation, "stopped": True}

    def get_default_config(self):
        """返回清理库存默认配置。"""
        return default_cleanup_config()

    def load_config(self, config):
        """迁移旧周期和通知字段，并保留用户明确设置的新值。"""
        self.config = normalize_cleanup_config(config)

    def _alerts(self):
        """使用插件持久化状态管理两个操作的独立异常。"""
        return CleanupAlerts(self.plugin, self.config, self._notify)

    def _notify(self, operation: str, title: str, text: str) -> bool:
        """发送单次最终通知，返回成功状态供异常去重使用。"""
        if not self.config.get(f"{operation}_notify", True):
            return False
        try:
            return bool(self._notifier_factory(self.plugin).finish(title, text))
        except Exception as err:  # noqa: BLE001 - 通知渠道失败不能改变清理结果
            logger.warning(f"工具中心：发送{operation}报告失败：{redact_sensitive_text(err)}")
            return False

    def send_notification(self, title: str, text: str) -> None:
        """发送不需要后续更新的 HTML 清理报告。"""
        self._notify("cleanup", title, text)

    def get_service(self):
        """分别注册扫描与清理；一个周期无效不影响另一个。"""
        services = []
        for operation, label, callback in (
            ("scan", "扫描清理计划", self.scan_plan),
            ("cleanup", "执行清理计划", self.run_once),
        ):
            cron = self.config.get(f"{operation}_cron")
            if not self.config.get(f"{operation}_enabled") or not cron:
                continue
            try:
                trigger = CronTrigger.from_crontab(cron)
            except (TypeError, ValueError) as err:
                logger.warning(f"工具中心：{label}周期无效：{redact_sensitive_text(err)}")
                continue
            services.append({
                "id": f"{self.plugin.__class__.__name__}.LibraryCleanup.{operation}",
                "name": f"工具中心 - {label}", "trigger": trigger,
                "func": callback, "kwargs": {"scheduled": True},
            })
        return services

    def get_options(
        self,
        selected_server: Optional[str] = None,
        selected_user: Optional[str] = None,
    ):
        """返回清理库存模块的媒体服务器、媒体库和用户选项。"""
        global _options_cache
        server = (self.config.get("selected_server") or "") if selected_server is None else selected_server
        user = (self.config.get("selected_user") or "") if selected_user is None else selected_user
        cache_key = (str(server), str(user))
        now = time.time()
        cached = _options_cache.get(cache_key)
        if cached and now < cached["expire"]:
            return cached["data"]

        options = {"servers": [], "libraries": [], "users": []}
        try:
            options["servers"] = self.adapter.list_servers()
            options["users"] = self.adapter.list_users(str(server))
            options["libraries"] = self.adapter.list_libraries(str(server), str(user))
        except Exception as err:
            logger.error(f"本地工具集：获取清理库存媒体服务器选项失败：{redact_sensitive_text(err)}")
            options["error"] = "媒体服务器选项读取失败"

        _options_cache[cache_key] = {"data": options, "expire": now + 300}
        return options

    def invalidate_options_cache(self):
        """手动清除选项缓存。"""
        global _options_cache
        _options_cache = {}

    def get_cleanup_plan(self, page=1, page_size=50):
        """返回持久化清理计划及其周期状态。"""
        plan = self._load_plan()
        try:
            current_page = max(1, int(page))
        except (TypeError, ValueError):
            current_page = 1
        try:
            current_page_size = min(100, max(1, int(page_size)))
        except (TypeError, ValueError):
            current_page_size = 50
        items = plan["items"]
        total = len(items)
        total_pages = max(1, -(-total // current_page_size))
        current_page = min(current_page, total_pages)
        start = (current_page - 1) * current_page_size
        end = start + current_page_size
        return {
            "total": total,
            "page": current_page,
            "page_size": current_page_size,
            "total_pages": total_pages,
            "items": items[start:end],
            "last_scan_at": plan.get("last_scan_at", ""),
            "last_cycle_at": plan.get("last_cycle_at", ""),
            "last_cycle": plan.get("last_cycle", {}),
            "last_scan": plan.get("last_scan", {}),
            "next_cycle_at": self._next_cycle_at(plan),
            "cooldown_minutes": self._cooldown_minutes(),
            "batch_size": self._cycle_limit(),
        }

    def scan_plan(self, scheduled=False):
        """独立扫描并更新计划，仅计划成员变化或异常时通知。"""
        if self._run_lock.stopped:
            return self._stopped_result("scan")
        if scheduled and not self.config.get("scan_enabled"):
            return {"success": True, "summary": "周期扫描已关闭", "operation": "scan"}
        if not self._run_lock.acquire(blocking=scheduled):
            return self._stopped_result("scan") if self._run_lock.stopped else self._busy_result("scan")
        start = time.time()
        try:
            if scheduled and not self.config.get("scan_enabled"):
                return {"success": True, "summary": "周期扫描已关闭", "operation": "scan"}
            with self.adapter.user_scope(self._run_lock.check):
                result, checked_at, plan, added, removed = self._scan_and_queue()
            queue_count = len(plan["items"])
            summary = f"扫描完成，新增入队 {added} 部，失效移出 {removed} 部，待清理 {queue_count} 部"
            self._save_result(result, checked_at, summary=summary, queue=plan, operation="scan")
            self.add_history("success", summary, time.time() - start)
            self._alerts().recover("scan")
            self.last_error = ""
            if added or removed:
                text = (f"<b>清理计划更新</b>\n新增入队：{added} 部｜失效移出：{removed} 部\n"
                        f"当前待清理：{queue_count} 部\n完整名单请查看清理计划页。")
                if self.config.get("scan_notify", True) and not self._notify("scan", "清理计划更新", text):
                    self.last_error = "扫描通知发送失败"
                    summary += "；扫描通知发送失败"
                    self.add_history("failed", "扫描通知发送失败，计划已保存", 0)
            return {
                "success": True, "summary": summary, "operation": "scan",
                "scanned_count": plan.get("last_scanned_total", 0),
                "qualified_count": result.qualified_count, "queued_added": added,
                "queued_removed": removed, "queue_count": queue_count,
            }
        except CleanupCancelled:
            return self._stopped_result("scan")
        except Exception as err:
            return self._operation_failed("scan", err, start)
        finally:
            self._run_lock.release()

    def _busy_result(self, operation: str) -> dict:
        """并行触发时只返回可读回执，不修改计划或发送通知。"""
        return {"success": True, "summary": "已有扫描或清理任务正在运行，本次跳过",
                "operation": operation, "busy": True}

    def _operation_failed(self, operation: str, error: Exception, start: float) -> dict:
        """将任务失败写入历史，并按对应通知开关去重提醒。"""
        label = "清理计划扫描" if operation == "scan" else "周期清理"
        self.last_error = f"{label}失败"
        message = safe_error_text(label)
        logger.error(f"工具中心：{label}失败：{redact_sensitive_text(error)}")
        self.add_history("failed", message, time.time() - start)
        category = f"{type(error).__name__}:{redact_sensitive_text(error)}"
        self._alerts().fail(operation, category, message, datetime.now(timezone.utc))
        return {"success": False, "message": message, "operation": operation}

    def clear_cleanup_plan(self):
        """清空持久化清理计划，不触碰媒体库条目。"""
        if self._run_lock.stopped:
            return self._stopped_result("cleanup")
        if not self._run_lock.acquire(blocking=False):
            return {"success": False, "message": "本轮清理仍在进行，请等待当前报告更新"}
        try:
            plan = self._load_plan()
            cleared = len(plan["items"])
            plan["items"] = []
            plan["last_cleared_at"] = datetime.now(timezone.utc).isoformat()
            self._save_plan(plan)
            summary = f"已清空清理计划，共移除 {cleared} 部待处理记录"
            self.add_history("success", summary, 0)
            return {"success": True, "summary": summary, "cleared_count": cleared, "queue_count": 0}
        finally:
            self._run_lock.release()

    def run_once(self, scheduled=False):
        """仅消费已有计划；定时与手动清理共用互斥和冷却。"""
        if self._run_lock.stopped:
            return self._stopped_result("cleanup")
        if scheduled and not self.config.get("cleanup_enabled"):
            return {"success": True, "summary": "周期清理已关闭", "operation": "cleanup"}
        if not self._run_lock.acquire(blocking=scheduled):
            return self._stopped_result("cleanup") if self._run_lock.stopped else self._busy_result("cleanup")
        start = time.time()
        try:
            if scheduled and not self.config.get("cleanup_enabled"):
                return {"success": True, "summary": "周期清理已关闭", "operation": "cleanup"}
            with self.adapter.user_scope(self._run_lock.check):
                return self._run_once(start)
        except CleanupCancelled:
            return self._stopped_result("cleanup")
        except Exception as err:
            return self._operation_failed("cleanup", err, start)
        finally:
            self._run_lock.release()

    def _run_once(self, start):
        """检查清理门禁后，只按 ID 复核并处理本批次对象。"""
        checked_at = datetime.now(timezone.utc)
        self._run_lock.check()
        plan = self._load_plan()
        queue_count = len(plan["items"])
        summary = ""
        cooldown = self._cooldown_remaining(plan, checked_at)
        if not queue_count:
            summary = "清理计划为空，本次跳过；请先生成清理计划"
        elif not self.config.get("auto_delete", False):
            summary = f"计划共 {queue_count} 部，自动删除未开启，本次跳过"
        elif cooldown > 0:
            summary = f"清理冷却中，约剩 {max(1, int((cooldown + 59) // 60))} 分钟"
        elif self.config.get("dry_run", False):
            summary = f"演练模式：计划共 {queue_count} 部，本批最多 {self._cycle_limit()} 部，未执行删除"
        if summary:
            self.add_history("skipped", summary, time.time() - start)
            return {"success": True, "summary": summary, "operation": "cleanup",
                    "scanned_count": 0, "queue_count": queue_count, "cooldown": cooldown > 0}

        selected_items = list(reversed(plan["items"]))[:self._cycle_limit()]
        selected_movies = [candidate_from_plan_item(item) for item in selected_items]
        result = CleanupResult(conditions=build_cleanup_conditions(self.config), qualified_movies=selected_movies)
        plan["last_cycle_at"] = checked_at.isoformat()
        plan["last_cycle"] = {"status": "running", "processed_count": len(selected_movies), "scanned_count": 0}
        self._save_plan(plan)
        batch = self._process_batch(selected_movies, result, checked_at)
        notifier = batch["notifier"]
        if notifier:
            notifier.update(REPORT_TITLE, self._build_report_text(result, "", checked_at, phase="verifying"))
        verification = self._verify_deleted_candidates(batch["attempted"])
        reconciled = CleanupVerification(
            removed=verification.removed + batch["skipped"] + batch["absent"],
            remaining=verification.remaining, unknown=verification.unknown + batch["unknown"],
        )
        processed_items = [item for item in selected_items if item["queue_key"] in batch["processed_keys"]]
        plan = self._reconcile_plan(plan, processed_items, reconciled, checked_at)
        for item in plan["items"]:
            if item["queue_key"] in batch["errors"]:
                item["last_error"] = batch["errors"][item["queue_key"]]
        counts = {
            "processed_count": len(processed_items), "success_count": len(verification.removed),
            "fail_count": batch["fail_count"], "remaining_count": len(verification.remaining),
            "unknown_count": len(reconciled.unknown), "skipped_count": len(batch["skipped"]),
            "already_absent_count": len(batch["absent"]), "queue_count": len(plan["items"]),
            "scanned_count": 0,
            "stopped": batch["stopped"] or self._run_lock.stopped,
            "unprocessed_count": len(selected_items) - len(processed_items),
        }
        complete = not reconciled.remaining and not reconciled.unknown and not counts["stopped"]
        status = "cancelled" if counts["stopped"] else "success" if complete else "failed"
        plan["last_cycle"] = {"status": status, **counts}
        self._save_plan(plan)
        summary = (
            f"计划清理：本轮检查 {len(processed_items)} 部，确认移除 {counts['success_count']} 部，"
            f"条件变化跳过 {counts['skipped_count']} 部，已不存在 {counts['already_absent_count']} 部，"
            f"仍然存在 {counts['remaining_count']} 部，无法核验 {counts['unknown_count']} 部，"
            f"剩余 {counts['queue_count']} 部"
        )
        if counts["stopped"]:
            summary += f"；任务已停止，未处理 {counts['unprocessed_count']} 部保留"
        self.last_error = "" if complete else "本轮清理未全部完成"
        final_text = self._build_report_text(
            result, "", checked_at, phase="finished", verification=verification, cycle_stats=counts,
            precheck_errors=[(movie, batch["errors"].get(cleanup_plan_key(movie), "删除前状态无法核验"))
                             for movie in batch["unknown"]],
        )
        all_unknown = len(batch["unknown"]) == len(selected_movies)
        report_updated = True
        notification_state = "disabled"
        if all_unknown and not counts["stopped"]:
            sent = self._alerts().fail("cleanup", "precheck_unavailable", final_text, checked_at)
            report_updated = sent is not False
            notification_state = "suppressed" if sent is None else "sent" if sent else "failed"
        else:
            if not reconciled.unknown and not counts["stopped"]:
                self._alerts().recover("cleanup")
            if self.config.get("cleanup_notify", True):
                if notifier:
                    report_updated = bool(notifier.finish(REPORT_TITLE, final_text))
                else:
                    report_updated = self._notify("cleanup", REPORT_TITLE, final_text)
                notification_state = "sent" if report_updated else "failed"
        if not report_updated or batch["notification_error"]:
            self.last_error = "；".join(filter(None, [self.last_error, "清理报告更新失败"]))
            summary += "；清理报告更新失败"
        self._save_result(
            result, checked_at, summary=summary, queue=plan,
            deletion={**counts, "verification": verification.to_dict(checked_at)},
            report={"title": REPORT_TITLE, "text": final_text,
                    "updated": report_updated and notification_state == "sent",
                    "notification_state": notification_state,
                    **(notifier.to_dict() if notifier else {})},
        )
        self.add_history(status, summary, time.time() - start)
        return {"success": complete, "summary": summary, "operation": "cleanup", **counts}

    def _precheck_candidate(self, movie, conditions, now):
        """复核当前范围及实时筛选条件，未知状态一律保留且不删除。"""
        server = str(self.config.get("selected_server") or "")
        library = str(self.config.get("selected_library") or "")
        if (server and movie.server != server) or (library and movie.library_id != library):
            return "skipped", movie, "已不在当前配置范围"
        try:
            exists, fresh = self.adapter.refresh_candidate(movie, str(self.config.get("selected_user") or ""))
        except Exception as err:
            logger.warning(f"工具中心：删除前复核失败：{redact_sensitive_text(err)}")
            return "unknown", movie, "删除前状态无法核验"
        if exists is False:
            return "absent", movie, ""
        if exists is not True or fresh is None:
            return "unknown", movie, "删除前状态无法核验"
        if cleanup_plan_key(fresh) != cleanup_plan_key(movie):
            return "unknown", movie, "删除前条目身份不一致"
        if library and fresh.library_id != library:
            return "skipped", fresh, "条目已移出当前媒体库"
        eligible = evaluate_cleanup_candidate(fresh, conditions, now)
        if eligible is None:
            return "unknown", fresh, "删除前筛选字段不完整"
        return ("eligible" if eligible else "skipped"), fresh, ""

    def _process_batch(self, movies, result, checked_at):
        """每次删除前即时查询；删除间隔内的状态变化也能被发现。"""
        batch = {"attempted": [], "skipped": [], "absent": [], "unknown": [],
                 "errors": {}, "fail_count": 0, "notifier": None, "notification_error": False,
                 "processed_keys": set(), "stopped": False}
        try:
            delay = max(0, int(self.config.get("auto_delete_delay", 60)))
        except (TypeError, ValueError):
            delay = 60
        last_delete = None
        for movie in movies:
            if self._run_lock.stopped:
                batch["stopped"] = True
                break
            if last_delete is not None:
                remaining = delay - (time.monotonic() - last_delete)
                if remaining > 0 and self._run_lock.wait(remaining):
                    batch["stopped"] = True
                    break
            state, fresh, error = self._precheck_candidate(movie, result.conditions, datetime.now(timezone.utc))
            if self._run_lock.stopped:
                batch["stopped"] = True
                break
            if state != "eligible":
                batch["processed_keys"].add(cleanup_plan_key(movie))
                batch[state].append(fresh)
                if error:
                    batch["errors"][cleanup_plan_key(movie)] = error
                continue
            if self.config.get("cleanup_notify", True) and not batch["attempted"]:
                try:
                    batch["notifier"] = self._notifier_factory(self.plugin)
                    batch["notifier"].start(
                        REPORT_TITLE, self._build_report_text(result, "", checked_at, phase="deleting"),
                    )
                except Exception as err:
                    batch["notification_error"] = True
                    logger.warning(f"工具中心：清理开始通知失败：{redact_sensitive_text(err)}")
            if self._run_lock.stopped:
                batch["stopped"] = True
                break
            batch["processed_keys"].add(cleanup_plan_key(movie))
            batch["attempted"].append(fresh)
            _success, failed = self._delete_candidates([fresh])
            batch["fail_count"] += failed
            last_delete = time.monotonic()
        return batch

    def get_status(self):
        """返回清理库存模块状态。"""
        plan = self._load_plan()
        status = {
            "enabled": bool(self.config.get("scan_enabled") or self.config.get("cleanup_enabled")),
            "auto_delete": self.config.get("auto_delete", False),
            "cron": self.config.get("cleanup_cron", ""),
            **{key: self.config.get(key) for key in (
                "scan_enabled", "scan_cron", "scan_notify", "cleanup_enabled", "cleanup_cron", "cleanup_notify",
            )},
            "run_mode": "independent",
            "plan_count": len(plan["items"]),
            "last_scan_at": plan.get("last_scan_at", ""),
            "last_cycle_at": plan.get("last_cycle_at", ""),
            "next_cycle_at": self._next_cycle_at(plan),
            "cooldown_minutes": self._cooldown_minutes(),
            "cycle_batch_size": self._cycle_limit(),
        }
        errors = self._alerts().errors()
        status["scan_error"] = errors.get("scan", "")
        pending_error = "计划中仍有清理失败或待复核条目" if any(item.get("last_error") for item in plan["items"]) else ""
        status["cleanup_error"] = errors.get("cleanup", "") or pending_error
        status["last_error"] = "；".join(dict.fromkeys(filter(None, [
            self.last_error, status["scan_error"], status["cleanup_error"],
        ])))
        return status

    def _cycle_limit(self) -> int:
        """返回设置页配置的本周期删除数量。"""
        try:
            max_count = int(self.config.get("auto_delete_max_count") or 0)
        except (TypeError, ValueError):
            max_count = DEFAULT_BATCH_SIZE
        return max_count if max_count > 0 else DEFAULT_BATCH_SIZE

    def _cooldown_minutes(self) -> int:
        """返回归一化后的周期冷却分钟数。"""
        try:
            return max(0, int(self.config.get("cycle_cooldown_minutes") or 0))
        except (TypeError, ValueError):
            return DEFAULT_COOLDOWN_MINUTES

    def _cooldown_remaining(self, plan: dict, now: datetime) -> float:
        """返回当前周期冷却剩余秒数。"""
        cooldown = self._cooldown_minutes()
        last_cycle = parse_datetime(plan.get("last_cycle_at"))
        if cooldown <= 0 or last_cycle is None:
            return 0
        return max(0, (last_cycle + timedelta(minutes=cooldown) - now).total_seconds())

    def _next_cycle_at(self, plan: dict) -> str:
        """返回下一次允许清理的时间。"""
        last_cycle = parse_datetime(plan.get("last_cycle_at"))
        cooldown = self._cooldown_minutes()
        if last_cycle is None or cooldown <= 0:
            return ""
        until = last_cycle + timedelta(minutes=cooldown)
        return until.isoformat() if until > datetime.now(timezone.utc) else ""

    def _scan_and_queue(self):
        """完整收集成功后才更新计划；未知条件保留，失败不提交半份扫描。"""
        candidates = list(self.adapter.iter_candidates(self.config))
        checked_at = datetime.now(timezone.utc)
        result = filter_cleanup_candidates(candidates, self.config, now=checked_at)
        self._run_lock.check()
        plan = self._load_plan()
        plan, added = self._merge_plan(plan, result.qualified_movies, checked_at)
        valid_keys = {cleanup_plan_key(movie) for movie in result.qualified_movies}
        unknown_keys = {cleanup_plan_key(movie) for movie in candidates
                        if evaluate_cleanup_candidate(movie, result.conditions, checked_at) is None}
        retained = [item for item in plan["items"] if item["queue_key"] in valid_keys | unknown_keys]
        removed = len(plan["items"]) - len(retained)
        plan["items"] = retained
        plan["last_scan_at"] = checked_at.isoformat()
        plan["last_scan_count"] = result.qualified_count
        plan["last_scanned_total"] = len(candidates)
        plan["last_scan"] = {"queued_added": added, "queued_removed": removed, "queue_count": len(retained)}
        self._save_plan(plan)
        return result, checked_at, plan, added, removed

    def _load_plan(self) -> dict:
        """读取并归一化持久化清理计划。"""
        raw = self.plugin.get_data(key=PLAN_DATA_KEY)
        if isinstance(raw, dict):
            raw_items = raw.get("items", [])
        elif isinstance(raw, list):
            raw_items = raw
            raw = {}
        else:
            raw_items = []
            raw = {}
        items = []
        seen = set()
        for raw_item in raw_items if isinstance(raw_items, list) else []:
            if not isinstance(raw_item, dict):
                continue
            candidate = candidate_from_plan_item(raw_item)
            key = str(raw_item.get("queue_key") or cleanup_plan_key(candidate))
            if key in seen:
                continue
            normalized = dict(raw_item)
            normalized.update(candidate.to_dict())
            normalized["queue_key"] = key
            try:
                normalized["attempts"] = max(0, int(raw_item.get("attempts") or 0))
            except (TypeError, ValueError):
                normalized["attempts"] = 0
            normalized["queued_at"] = str(raw_item.get("queued_at") or "")
            normalized["last_attempt_at"] = str(raw_item.get("last_attempt_at") or "")
            normalized["last_error"] = str(raw_item.get("last_error") or "")
            items.append(normalized)
            seen.add(key)
        try:
            last_scan_count = max(0, int(raw.get("last_scan_count") or 0))
        except (TypeError, ValueError):
            last_scan_count = 0
        return {
            "version": PLAN_VERSION,
            "items": items,
            "last_scan_at": str(raw.get("last_scan_at") or ""),
            "last_scan_count": last_scan_count,
            "last_scanned_total": raw.get("last_scanned_total", 0),
            "last_scan": raw.get("last_scan") if isinstance(raw.get("last_scan"), dict) else {},
            "last_cycle_at": str(raw.get("last_cycle_at") or ""),
            "last_cycle": raw.get("last_cycle") if isinstance(raw.get("last_cycle"), dict) else {},
            "last_cleared_at": str(raw.get("last_cleared_at") or ""),
        }

    def _save_plan(self, plan: dict) -> None:
        """保存清理计划及其运行元数据。"""
        self.plugin.save_data(key=PLAN_DATA_KEY, value=plan)

    def _merge_plan(
        self,
        plan: dict,
        candidates: List[CleanupCandidate],
        queued_at: datetime,
    ) -> tuple[dict, int]:
        """按稳定身份把扫描候选合并到清理计划。"""
        by_key = {item["queue_key"]: item for item in plan["items"]}
        added = 0
        for candidate in candidates:
            key = cleanup_plan_key(candidate)
            snapshot = candidate.to_dict(queued_at)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = {
                    **snapshot,
                    "queue_key": key,
                    "queued_at": queued_at.isoformat(),
                    "attempts": 0,
                    "last_attempt_at": "",
                    "last_error": "",
                }
                plan["items"].append(by_key[key])
                added += 1
                continue
            existing.update(snapshot)
        return plan, added

    def _reconcile_plan(
        self,
        plan: dict,
        selected_items: List[dict],
        verification: CleanupVerification,
        checked_at: datetime,
    ) -> dict:
        """按删除后复核结果移除成功项并保留失败项。"""
        removed_keys = {cleanup_plan_key(movie) for movie in verification.removed}
        remaining_keys = {cleanup_plan_key(movie) for movie in verification.remaining}
        selected_keys = {
            str(item.get("queue_key") or cleanup_plan_key(candidate_from_plan_item(item)))
            for item in selected_items
        }
        retry_items = []
        retained_items = []
        for item in plan["items"]:
            key = str(item.get("queue_key") or "")
            if key in removed_keys:
                continue
            if key in selected_keys:
                updated = dict(item)
                updated["attempts"] = int(updated.get("attempts") or 0) + 1
                updated["last_attempt_at"] = checked_at.isoformat()
                updated["last_error"] = "媒体条目仍然存在" if key in remaining_keys else "媒体条目状态无法核验"
                retry_items.append(updated)
            else:
                retained_items.append(item)
        plan["items"] = retry_items + retained_items
        return plan

    def _delete_candidates(self, movies: List[CleanupCandidate]) -> tuple[int, int]:
        """按配置逐个删除候选项。"""
        delay = self.config.get("auto_delete_delay", 60)
        try:
            delay = max(0, int(delay))
        except (TypeError, ValueError):
            delay = 60
        success_count = 0
        fail_count = 0
        for index, item in enumerate(list(movies), start=1):
            code = item.code or item.movie_id or "未知"
            logger.info(f"本地工具集：自动删除 [{index}/{len(movies)}]: {code}")
            try:
                deleted = self.adapter.delete_item(item)
            except Exception as err:
                deleted = False
                logger.warning(f"本地工具集：删除候选项异常：{redact_sensitive_text(err)}")
            if deleted:
                success_count += 1
            else:
                fail_count += 1
            if index < len(movies) and delay > 0:
                time.sleep(delay)
        return success_count, fail_count

    def _verify_deleted_candidates(self, movies: List[CleanupCandidate]) -> CleanupVerification:
        states: list[Optional[bool]] = [None] * len(movies)
        pending = list(range(len(movies)))
        for _attempt in range(self.verification_attempts):
            if not pending or self._run_lock.stopped:
                break
            if self.verification_delay > 0 and self._run_lock.wait(self.verification_delay):
                break
            for index in pending:
                if self._run_lock.stopped:
                    break
                try:
                    state = self.adapter.item_exists(
                        movies[index], str(self.config.get("selected_user") or ""),
                    )
                    states[index] = state if isinstance(state, bool) else None
                except Exception as err:
                    states[index] = None
                    logger.warning(f"本地工具集：复核候选项异常：{redact_sensitive_text(err)}")
            pending = [index for index in pending if states[index] is not False]
        return CleanupVerification(
            removed=[movie for movie, state in zip(movies, states) if state is False],
            remaining=[movie for movie, state in zip(movies, states) if state is True],
            unknown=[movie for movie, state in zip(movies, states) if state is None],
        )

    def _save_result(
        self,
        result: CleanupResult,
        checked_at: datetime,
        summary: str = "",
        deletion: Optional[dict] = None,
        report: Optional[dict] = None,
        queue: Optional[dict] = None,
        operation: str = "cleanup",
    ) -> None:
        """保存本次清理库存结果。"""
        payload = result.to_dict(checked_at)
        payload["summary"] = summary
        payload["checked_at"] = checked_at.isoformat()
        payload["operation"] = operation
        if deletion:
            payload["deletion"] = deletion
        if report:
            payload["report"] = report
        if queue is not None:
            payload["queue"] = {
                "count": len(queue.get("items", [])),
                "last_scan_at": queue.get("last_scan_at", ""),
                "last_cycle_at": queue.get("last_cycle_at", ""),
                "next_cycle_at": self._next_cycle_at(queue),
            }
        self.plugin.save_data(key="library_cleanup_result", value=payload)
        self.plugin.save_data(key=f"library_cleanup_{operation}_result", value=payload)

    def _send_report(self, title: str, result: CleanupResult, summary: str, checked_at: datetime) -> None:
        """发送清理库存通知报告。"""
        text = self._build_report_text(result, summary, checked_at)
        self.send_notification(title, text)

    def _build_report_text(
        self, result: CleanupResult, summary: str, checked_at: datetime, *,
        phase: str = "", verification: CleanupVerification | None = None,
        cycle_stats: dict | None = None,
        precheck_errors: list[tuple[CleanupCandidate, str]] | None = None,
    ) -> str:
        """生成单条 HTML 报告，上方名单保持不变，仅更新末尾结果。"""
        return build_report(
            self.config, result, summary, checked_at, phase=phase, verification=verification,
            cycle_stats=cycle_stats,
            precheck_errors=precheck_errors,
        )
