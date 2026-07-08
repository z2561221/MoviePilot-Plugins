"""工具中心自持的清理库存服务。"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import List, Optional

from apscheduler.triggers.cron import CronTrigger
from app.log import logger

from ..adapter.media_server import MediaServerCleanupAdapter
from ..model.library_cleanup import CleanupCandidate, CleanupResult, filter_cleanup_candidates
from .base import BaseToolModule


_options_cache = {"data": None, "expire": 0}


class LibraryCleanupModule(BaseToolModule):
    """清理库存模块，负责分析媒体候选项并按配置通知或删除。"""

    module_key = "library_cleanup"
    module_name = "清理库存"
    last_error = ""

    def __init__(self, plugin, adapter: Optional[MediaServerCleanupAdapter] = None):
        """初始化清理库存模块。"""
        super().__init__(plugin)
        self.adapter = adapter or MediaServerCleanupAdapter()

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

    def get_service(self):
        """返回清理库存定时服务配置。"""
        cron = self.config.get("cron")
        if not self.config.get("enabled") or not cron:
            return []
        try:
            trigger = CronTrigger.from_crontab(cron)
        except Exception as err:
            logger.warning(f"本地工具集：清理库存 cron 配置无效，已跳过定时服务：{cron}，错误：{err}")
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

    def get_options(self):
        """返回清理库存模块的媒体服务器、媒体库和用户选项。"""
        global _options_cache
        now = time.time()
        if now < _options_cache["expire"] and _options_cache["data"] is not None:
            return _options_cache["data"]

        options = {"servers": [], "libraries": [], "users": []}
        try:
            selected_server = self.config.get("selected_server") or ""
            selected_user = self.config.get("selected_user") or ""
            options["servers"] = self.adapter.list_servers()
            options["libraries"] = self.adapter.list_libraries(selected_server, selected_user)
            options["users"] = self.adapter.list_users(selected_server)
        except Exception as err:
            logger.error(f"本地工具集：获取清理库存媒体服务器选项失败：{err}")
            options["error"] = str(err)

        _options_cache["data"] = options
        _options_cache["expire"] = now + 300
        return options

    def invalidate_options_cache(self):
        """手动清除选项缓存。"""
        global _options_cache
        _options_cache = {"data": None, "expire": 0}

    def run_once(self):
        """执行一次清理库存检查和可选自动删除。"""
        start = time.time()
        self.last_error = ""
        auto_delete = bool(self.config.get("auto_delete", False))
        try:
            candidates = list(self.adapter.iter_candidates(self.config))
            checked_at = datetime.now(timezone.utc)
            result = filter_cleanup_candidates(candidates, self.config, now=checked_at)
        except Exception as err:
            self.last_error = str(err)
            message = f"清理库存模块执行失败：{err}"
            logger.error(f"本地工具集：{message}")
            self.add_history("failed", message, time.time() - start)
            return {"success": False, "message": message}

        qualified = result.qualified_count
        if qualified == 0:
            summary = "媒体库很干净，没有需要清理的电影。"
            self._save_result(result, checked_at, summary=summary)
            self.add_history("success", summary, time.time() - start)
            self._send_report("清理库存检查报告", result, summary, checked_at)
            return {"success": True, "summary": summary}

        if auto_delete:
            limit_response = self._guard_auto_delete_limit(result, checked_at, start)
            if limit_response:
                return limit_response
            dry_run_response = self._guard_dry_run(result, checked_at, start)
            if dry_run_response:
                return dry_run_response
            self._send_report("清理库存检查报告", result, "即将开始自动删除...", checked_at)

        success_count, fail_count = self._delete_candidates(result.qualified_movies) if auto_delete else (0, 0)
        summary = f"符合条件 {qualified} 部，删除成功 {success_count} 部，失败 {fail_count} 部"
        self._save_result(
            result,
            checked_at,
            summary=summary,
            deletion={"success_count": success_count, "fail_count": fail_count},
        )
        self.add_history("success", summary, time.time() - start)
        if not auto_delete:
            self._send_report("清理库存检查报告", result, summary, checked_at)
        return {"success": True, "summary": summary}

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
            if self.adapter.delete_item(item):
                success_count += 1
            else:
                fail_count += 1
            if index < len(movies) and delay > 0:
                time.sleep(delay)
        return success_count, fail_count

    def _save_result(
        self,
        result: CleanupResult,
        checked_at: datetime,
        summary: str = "",
        deletion: Optional[dict] = None,
    ) -> None:
        """保存本次清理库存结果。"""
        payload = result.to_dict(checked_at)
        payload["summary"] = summary
        payload["checked_at"] = checked_at.isoformat()
        if deletion:
            payload["deletion"] = deletion
        self.plugin.save_data(key="library_cleanup_result", value=payload)

    def _send_report(self, title: str, result: CleanupResult, summary: str, checked_at: datetime) -> None:
        """发送清理库存通知报告。"""
        text = self._build_report_text(result, summary, checked_at)
        self.send_notification(title, text)

    def _build_report_text(self, result: CleanupResult, summary: str, checked_at: datetime) -> str:
        """生成清理库存通知正文。"""
        lines = [
            f"符合条件：{result.condition_label}",
            f"符合数量：{result.qualified_count} 部",
            summary,
        ]
        movies = result.qualified_movies
        if movies:
            lines.append("")
            lines.append("待处理列表")
            for index, movie in enumerate(movies[:20], start=1):
                date_text = movie.date_created[:10] if movie.date_created else "未知"
                age = movie.age_days(checked_at)
                age_text = f"{age}天" if age is not None else "未知"
                code = movie.code or movie.movie_id or "未知"
                lines.append(f"  {index}. {code} | {age_text} | {date_text}")
            if len(movies) > 20:
                lines.append(f"  ... 还有{len(movies) - 20}部")
        return "\n".join(lines)
