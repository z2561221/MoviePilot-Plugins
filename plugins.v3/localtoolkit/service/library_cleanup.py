"""工具中心自持的清理库存服务。"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import List, Optional

from app.sdk.logging import logger
from apscheduler.triggers.cron import CronTrigger

from ..adapter.cleanup_notification import CleanupReportNotifier
from ..adapter.media_server import MediaServerCleanupAdapter
from ..model.library_cleanup import (
    CleanupCandidate,
    CleanupResult,
    CleanupVerification,
    candidate_from_plan_item,
    cleanup_plan_key,
    filter_cleanup_candidates,
    parse_datetime,
)
from ..security import redact_sensitive_text, safe_error_text
from .base import BaseToolModule
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
        self._run_lock = Lock()

    def get_default_config(self):
        """返回清理库存默认配置。"""
        return {
            "enabled": False,
            "cron": "9 0 * * *",
            "notify": True,
            "days_threshold": 20,
            "selected_library": "",
            "selected_server": "",
            "selected_user": "",
            "filter_played": "played",
            "filter_favorite": "unfav",
            "filter_played_2": "unplayed",
            "filter_favorite_2": "unfav",
            "days_threshold_2": 40,
            "auto_delete": False,
            "auto_delete_delay": 60,
            "dry_run": False,
            "auto_delete_max_count": DEFAULT_BATCH_SIZE,
            "cycle_cooldown_minutes": DEFAULT_COOLDOWN_MINUTES,
        }

    def send_notification(self, title: str, text: str) -> None:
        """发送不需要后续更新的 HTML 清理报告。"""
        if self.config.get("notify", True):
            try:
                self._notifier_factory(self.plugin).finish(title, text)
            except Exception as err:
                logger.warning(f"本地工具集：发送通知失败：{redact_sensitive_text(err)}")

    def get_service(self):
        """返回清理库存定时服务配置。"""
        cron = self.config.get("cron")
        if not self.config.get("enabled") or not cron:
            return []
        try:
            trigger = CronTrigger.from_crontab(cron)
        except Exception as err:
            logger.warning(f"本地工具集：清理库存 cron 配置无效，已跳过定时服务：{cron}，错误：{redact_sensitive_text(err)}")
            return []
        return [
            {
                "id": "LocalToolkit.LibraryCleanup",
                "name": "本地工具集 - 清理库存",
                "trigger": trigger,
                "func": self.run_once,
                "kwargs": {},
            }
        ]

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
            "next_cycle_at": self._next_cycle_at(plan),
            "cooldown_minutes": self._cooldown_minutes(),
            "batch_size": self._cycle_limit(),
        }

    def scan_plan(self):
        """只扫描并合并清理计划，不执行删除。"""
        if not self._run_lock.acquire(blocking=False):
            return {"success": False, "message": "本轮清理仍在进行，请等待当前报告更新"}
        start = time.time()
        self.last_error = ""
        try:
            result, checked_at, plan, added = self._scan_and_queue()
        except Exception as err:
            self.last_error = "清理库存扫描失败"
            message = safe_error_text("清理库存扫描")
            logger.error(f"本地工具集：清理库存扫描失败：{redact_sensitive_text(err)}")
            self.add_history("failed", message, time.time() - start)
            return {"success": False, "message": message}
        finally:
            self._run_lock.release()

        queue_count = len(plan["items"])
        summary = f"扫描完成，新增 {added} 部，清理计划共 {queue_count} 部"
        self._save_result(result, checked_at, summary=summary, queue=plan)
        self.add_history("success", summary, time.time() - start)
        self._send_report(REPORT_TITLE, result, summary, checked_at)
        return {
            "success": True,
            "summary": summary,
            "scanned_count": result.qualified_count,
            "queued_added": added,
            "queue_count": queue_count,
        }

    def clear_cleanup_plan(self):
        """清空持久化清理计划，不触碰媒体库条目。"""
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

    def run_once(self):
        """执行一次清理库存检查和可选自动删除。"""
        if not self._run_lock.acquire(blocking=False):
            return {"success": False, "message": "本轮清理仍在进行，请等待当前报告更新"}
        try:
            return self._run_once()
        finally:
            self._run_lock.release()

    def _run_once(self):
        start = time.time()
        self.last_error = ""
        auto_delete = bool(self.config.get("auto_delete", False))
        try:
            result, checked_at, plan, queued_added = self._scan_and_queue()
        except Exception as err:
            self.last_error = "清理库存扫描失败"
            message = safe_error_text("清理库存")
            logger.error(f"本地工具集：清理库存扫描失败：{redact_sensitive_text(err)}")
            self.add_history("failed", message, time.time() - start)
            return {"success": False, "message": message}

        qualified = result.qualified_count
        queue_count = len(plan["items"])
        if queue_count == 0:
            summary = "扫描完成，媒体库很干净，没有需要清理的电影。"
            self._save_result(result, checked_at, summary=summary, queue=plan)
            self.add_history("success", summary, time.time() - start)
            self._send_report(REPORT_TITLE, result, summary, checked_at)
            return {
                "success": True,
                "summary": summary,
                "scanned_count": qualified,
                "queued_added": queued_added,
                "queue_count": 0,
            }

        if not auto_delete:
            summary = f"扫描完成，清理计划共 {queue_count} 部，未开启自动删除"
            self._save_result(result, checked_at, summary=summary, queue=plan)
            self.add_history("success", summary, time.time() - start)
            self._send_report(REPORT_TITLE, result, summary, checked_at)
            return {
                "success": True,
                "summary": summary,
                "scanned_count": qualified,
                "queued_added": queued_added,
                "queue_count": queue_count,
            }

        dry_run_response = self._guard_dry_run(result, checked_at, start, plan)
        if dry_run_response:
            return dry_run_response

        cooldown_remaining = self._cooldown_remaining(plan, checked_at)
        if cooldown_remaining > 0:
            minutes = max(1, int((cooldown_remaining + 59) // 60))
            summary = f"扫描完成，清理计划共 {queue_count} 部，周期冷却中，约剩 {minutes} 分钟"
            self._save_result(result, checked_at, summary=summary, queue=plan)
            self.add_history("success", summary, time.time() - start)
            return {
                "success": True,
                "summary": summary,
                "scanned_count": qualified,
                "queued_added": queued_added,
                "queue_count": queue_count,
                "cooldown": True,
            }

        limit = self._cycle_limit()
        selected_items = list(reversed(plan["items"]))[:limit]
        selected_movies = [candidate_from_plan_item(item) for item in selected_items]
        selected_result = CleanupResult(
            conditions=result.conditions,
            qualified_movies=selected_movies,
        )
        cycle_started_at = checked_at.isoformat()
        plan["last_cycle_at"] = cycle_started_at
        plan["last_cycle"] = {
            "status": "running",
            "scanned_count": qualified,
            "queued_added": queued_added,
            "processed_count": len(selected_movies),
        }
        self._save_plan(plan)

        notifier = self._notifier_factory(self.plugin) if self.config.get("notify", True) else None
        if notifier:
            notifier.start(
                REPORT_TITLE,
                self._build_report_text(selected_result, "", checked_at, phase="deleting"),
            )
        success_count, fail_count = self._delete_candidates(selected_movies)
        if notifier:
            notifier.update(
                REPORT_TITLE,
                self._build_report_text(selected_result, "", checked_at, phase="verifying"),
            )
        verification = self._verify_deleted_candidates(selected_movies)
        plan = self._reconcile_plan(plan, selected_items, verification, checked_at)
        plan["last_cycle"] = {
            "status": "success" if verification.complete else "failed",
            "scanned_count": qualified,
            "queued_added": queued_added,
            "processed_count": len(selected_movies),
            "success_count": len(verification.removed),
            "fail_count": fail_count,
            "queue_count": len(plan["items"]),
        }
        self._save_plan(plan)

        summary = (
            f"扫描 {qualified} 部，计划 {queue_count} 部，本轮倒序处理 {len(selected_movies)} 部，"
            f"{verification.summary}"
        )
        if not verification.complete:
            self.last_error = "本轮清理未全部完成"
        final_text = self._build_report_text(
            selected_result, "", checked_at, phase="finished", verification=verification,
        )
        if notifier and not notifier.finish(REPORT_TITLE, final_text):
            self.last_error = "；".join(filter(None, [self.last_error, "清理报告更新失败"]))
            summary += "；清理报告更新失败"
        self._save_result(
            result,
            checked_at,
            summary=summary,
            deletion={
                "success_count": success_count,
                "fail_count": fail_count,
                "processed_count": len(selected_movies),
                "queue_count": len(plan["items"]),
                "verification": verification.to_dict(checked_at),
            },
            report={"title": REPORT_TITLE, "text": final_text, **(notifier.to_dict() if notifier else {})},
            queue=plan,
        )
        self.add_history("success" if verification.complete else "failed", summary, time.time() - start)
        return {
            "success": verification.complete,
            "summary": summary,
            "scanned_count": qualified,
            "queued_added": queued_added,
            "processed_count": len(selected_movies),
            "success_count": len(verification.removed),
            "fail_count": fail_count,
            "queue_count": len(plan["items"]),
        }

    def get_status(self):
        """返回清理库存模块状态。"""
        plan = self._load_plan()
        status = {
            "enabled": self.config.get("enabled", False),
            "auto_delete": self.config.get("auto_delete", False),
            "cron": self.config.get("cron", ""),
            "plan_count": len(plan["items"]),
            "last_scan_at": plan.get("last_scan_at", ""),
            "last_cycle_at": plan.get("last_cycle_at", ""),
            "next_cycle_at": self._next_cycle_at(plan),
            "cooldown_minutes": self._cooldown_minutes(),
            "cycle_batch_size": self._cycle_limit(),
        }
        if self.last_error:
            status["last_error"] = self.last_error
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
        return (last_cycle + timedelta(minutes=cooldown)).isoformat()

    def _guard_dry_run(
        self,
        result: CleanupResult,
        checked_at: datetime,
        start: float,
        plan: dict,
    ) -> Optional[dict]:
        """处理演练模式。"""
        if not self.config.get("dry_run", False):
            return None
        queue_count = len(plan["items"])
        summary = f"演练模式：扫描 {result.qualified_count} 部，清理计划共 {queue_count} 部，未执行删除"
        self._save_result(result, checked_at, summary=summary, queue=plan)
        self.add_history("success", summary, time.time() - start)
        self._send_report(REPORT_TITLE, result, summary, checked_at)
        return {
            "success": True,
            "summary": summary,
            "scanned_count": result.qualified_count,
            "queue_count": queue_count,
        }

    def _scan_and_queue(self):
        """完成一次完整扫描，并在扫描结束后合并持久化清理队列。"""
        candidates = list(self.adapter.iter_candidates(self.config))
        checked_at = datetime.now(timezone.utc)
        result = filter_cleanup_candidates(candidates, self.config, now=checked_at)
        plan = self._load_plan()
        plan, added = self._merge_plan(plan, result.qualified_movies, checked_at)
        plan["last_scan_at"] = checked_at.isoformat()
        plan["last_scan_count"] = result.qualified_count
        self._save_plan(plan)
        return result, checked_at, plan, added

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
            if not pending:
                break
            if self.verification_delay > 0:
                time.sleep(self.verification_delay)
            for index in pending:
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
    ) -> None:
        """保存本次清理库存结果。"""
        payload = result.to_dict(checked_at)
        payload["summary"] = summary
        payload["checked_at"] = checked_at.isoformat()
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

    def _send_report(self, title: str, result: CleanupResult, summary: str, checked_at: datetime) -> None:
        """发送清理库存通知报告。"""
        text = self._build_report_text(result, summary, checked_at)
        self.send_notification(title, text)

    def _build_report_text(
        self, result: CleanupResult, summary: str, checked_at: datetime, *,
        phase: str = "", verification: CleanupVerification | None = None,
    ) -> str:
        """生成单条 HTML 报告，上方名单保持不变，仅更新末尾结果。"""
        return build_report(
            self.config, result, summary, checked_at, phase=phase, verification=verification,
        )
