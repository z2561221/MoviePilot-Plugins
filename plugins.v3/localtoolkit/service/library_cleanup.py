"""工具中心自持的清理库存服务。"""

from __future__ import annotations

import time
from datetime import datetime, timezone
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
    filter_cleanup_candidates,
)
from ..security import redact_sensitive_text, safe_error_text
from .base import BaseToolModule
from .cleanup_report import REPORT_TITLE, build_report

_options_cache = {}


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
            "auto_delete_max_count": 20,
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
            candidates = list(self.adapter.iter_candidates(self.config))
            checked_at = datetime.now(timezone.utc)
            result = filter_cleanup_candidates(candidates, self.config, now=checked_at)
        except Exception as err:
            self.last_error = "清理库存执行失败"
            message = safe_error_text("清理库存")
            logger.error(f"本地工具集：清理库存模块执行失败：{redact_sensitive_text(err)}")
            self.add_history("failed", message, time.time() - start)
            return {"success": False, "message": message}

        qualified = result.qualified_count
        if qualified == 0:
            summary = "媒体库很干净，没有需要清理的电影。"
            self._save_result(result, checked_at, summary=summary)
            self.add_history("success", summary, time.time() - start)
            self._send_report("清理库存检查报告", result, summary, checked_at)
            return {"success": True, "summary": summary}

        if not auto_delete:
            summary = f"符合条件 {qualified} 部，未开启自动删除"
            self._save_result(result, checked_at, summary=summary)
            self.add_history("success", summary, time.time() - start)
            self._send_report(REPORT_TITLE, result, summary, checked_at)
            return {"success": True, "summary": summary}

        limit_response = self._guard_auto_delete_limit(result, checked_at, start)
        if limit_response:
            return limit_response
        dry_run_response = self._guard_dry_run(result, checked_at, start)
        if dry_run_response:
            return dry_run_response
        notifier = self._notifier_factory(self.plugin) if self.config.get("notify", True) else None
        if notifier:
            notifier.start(REPORT_TITLE, self._build_report_text(result, "", checked_at, phase="deleting"))
        success_count, fail_count = self._delete_candidates(result.qualified_movies)
        if notifier:
            notifier.update(REPORT_TITLE, self._build_report_text(result, "", checked_at, phase="verifying"))
        verification = self._verify_deleted_candidates(result.qualified_movies)
        summary = f"符合条件 {qualified} 部，{verification.summary}"
        if not verification.complete:
            self.last_error = "本轮清理未全部完成"
        final_text = self._build_report_text(
            result, "", checked_at, phase="finished", verification=verification,
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
                "verification": verification.to_dict(checked_at),
            },
            report={"title": REPORT_TITLE, "text": final_text, **(notifier.to_dict() if notifier else {})},
        )
        self.add_history("success" if verification.complete else "failed", summary, time.time() - start)
        return {"success": verification.complete, "summary": summary}

    def get_status(self):
        """返回清理库存模块状态。"""
        status = {
            "enabled": self.config.get("enabled", False),
            "auto_delete": self.config.get("auto_delete", False),
            "cron": self.config.get("cron", ""),
        }
        if self.last_error:
            status["last_error"] = self.last_error
        return status

    def _guard_auto_delete_limit(self, result: CleanupResult, checked_at: datetime, start: float) -> Optional[dict]:
        """检查自动删除数量上限。"""
        try:
            max_count = int(self.config.get("auto_delete_max_count") or 0)
        except (TypeError, ValueError):
            max_count = 0
        if max_count <= 0 or result.qualified_count <= max_count:
            return None
        summary = f"符合条件 {result.qualified_count} 部，超过自动删除上限 {max_count} 部，已中止删除"
        self._save_result(result, checked_at, summary=summary)
        self.add_history("failed", summary, time.time() - start)
        self._send_report("清理库存检查报告", result, summary, checked_at)
        return {"success": False, "summary": summary}

    def _guard_dry_run(self, result: CleanupResult, checked_at: datetime, start: float) -> Optional[dict]:
        """处理演练模式。"""
        if not self.config.get("dry_run", False):
            return None
        summary = f"演练模式：符合条件 {result.qualified_count} 部，未执行删除"
        self._save_result(result, checked_at, summary=summary)
        self.add_history("success", summary, time.time() - start)
        self._send_report("清理库存检查报告", result, summary, checked_at)
        return {"success": True, "summary": summary}

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
    ) -> None:
        """保存本次清理库存结果。"""
        payload = result.to_dict(checked_at)
        payload["summary"] = summary
        payload["checked_at"] = checked_at.isoformat()
        if deletion:
            payload["deletion"] = deletion
        if report:
            payload["report"] = report
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
