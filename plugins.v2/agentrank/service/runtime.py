"""AgentRank 运行时依赖组装、周期服务与停止管理。"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Mapping

from ..model.config import configured_identities


logger = logging.getLogger(__name__)


class AgentRankRuntime:
    """持有插件运行期领域服务并管理宿主调度入口。"""

    def __init__(
        self,
        plugin: Any,
        config: Dict[str, Any],
        orchestrator: Any = None,
        trigger_factory: Callable[[str], Any] = None,
        subscription_service: Any = None,
        notification_service: Any = None,
        interaction_service: Any = None,
        date_trigger_factory: Callable[[], Any] = None,
        feedback_queue: Any = None,
        feedback_handler: Callable[[Any], Any] = None,
        feedback_understanding_service: Any = None,
        feedback_response_service: Any = None,
        memory_projection_service: Any = None,
        conversation_service: Any = None,
        pending_center_service: Any = None,
        reminder_trigger_factory: Callable[[], Any] = None,
        attribution_service: Any = None,
        attribution_trigger_factory: Callable[[], Any] = None,
    ):
        """组装真实依赖或接受测试注入。"""
        self.plugin = plugin
        self.config = config
        self.orchestrator = orchestrator or self._build_orchestrator(plugin, config)
        self._trigger_factory = trigger_factory or self._default_trigger_factory
        self._date_trigger_factory = (
            date_trigger_factory or self._default_date_trigger_factory
        )
        self._reminder_trigger_factory = (
            reminder_trigger_factory or self._default_reminder_trigger_factory
        )
        self._attribution_trigger_factory = (
            attribution_trigger_factory or self._default_attribution_trigger_factory
        )
        attribution_service = attribution_service or getattr(
            plugin, "_attribution_service", None
        )
        if orchestrator is None:
            from .notification import NotificationService
            from .subscription import SubscriptionService
            from .telegram_interaction import TelegramSelectionService
            from ..adapter.subscription import SubscriptionAdapter

            subscription_service = subscription_service or SubscriptionService(
                plugin._repository,
                subscription_adapter=SubscriptionAdapter(),
                attribution_service=attribution_service,
            )
            interaction_service = interaction_service or TelegramSelectionService(
                plugin=plugin,
                repository=plugin._repository,
                subscription_service=subscription_service,
                config=config,
            )
            notification_service = notification_service or NotificationService(
                plugin, interaction_service
            )
        self.subscription_service = subscription_service
        self.notification_service = notification_service
        self.interaction_service = interaction_service
        self.attribution_service = attribution_service
        plugin._attribution_service = attribution_service
        repository = getattr(plugin, "_repository", None)
        if (
            feedback_handler is None
            and feedback_understanding_service is None
            and repository is not None
        ):
            from ..adapter.agent import AgentRankAgentAdapter
            from .feedback_understanding import FeedbackUnderstandingService

            feedback_understanding_service = FeedbackUnderstandingService(
                repository,
                AgentRankAgentAdapter(),
                analysis_limit=int(config.get("analysis_record_limit") or 500),
                critic_prompt=str(config.get("critic_prompt") or ""),
            )
        if feedback_handler is None and feedback_understanding_service is not None:
            feedback_handler = getattr(
                feedback_understanding_service, "handle_job", None
            )
        self.feedback_understanding_service = feedback_understanding_service
        plugin._feedback_understanding = feedback_understanding_service
        if feedback_queue is None and repository is not None:
            from .feedback_queue import FeedbackQueueService

            feedback_queue = FeedbackQueueService(
                repository,
                handler=feedback_handler,
                attention_handler=self._notify_feedback_attention,
                profile_ids=(
                    identity.profile_id for identity in configured_identities(config)
                ),
                max_workers=2,
                queue_limit=int(config.get("feedback_queue_limit") or 200),
                max_attempts=3,
            )
        elif feedback_queue is not None and feedback_handler is not None:
            set_handler = getattr(feedback_queue, "set_handler", None)
            if callable(set_handler):
                set_handler(feedback_handler)
        self.feedback_queue = feedback_queue
        plugin._feedback_queue = feedback_queue
        if feedback_response_service is None and repository is not None:
            from .feedback_response import FeedbackResponseService

            feedback_response_service = FeedbackResponseService(
                repository, feedback_queue=feedback_queue
            )
        self.feedback_response_service = feedback_response_service
        plugin._feedback_response = feedback_response_service
        if memory_projection_service is None and repository is not None:
            from .memory_projection import MemoryProjectionService

            memory_projection_service = MemoryProjectionService(repository)
        self.memory_projection_service = memory_projection_service
        plugin._memory_projection = memory_projection_service
        if conversation_service is None and repository is not None:
            from ..adapter.agent import AgentRankAgentAdapter
            from .conversation import ConversationService

            conversation_service = ConversationService(
                repository,
                AgentRankAgentAdapter(),
                plugin=plugin,
                message_limit=int(config.get("conversation_message_limit") or 200),
                critic_prompt=str(config.get("critic_prompt") or ""),
            )
        self.conversation_service = conversation_service
        plugin._conversation = conversation_service
        if (
            pending_center_service is None
            and repository is not None
            and feedback_response_service is not None
            and memory_projection_service is not None
            and conversation_service is not None
        ):
            from .pending_center import PendingCenterService

            pending_center_service = PendingCenterService(
                repository,
                feedback_response=feedback_response_service,
                memory_projection=memory_projection_service,
                conversation=conversation_service,
            )
        self.pending_center_service = pending_center_service
        plugin._pending_center = pending_center_service
        if interaction_service is not None and pending_center_service is not None:
            set_pending_center = getattr(interaction_service, "set_pending_center", None)
            if callable(set_pending_center):
                set_pending_center(pending_center_service)
        if conversation_service is not None:
            set_pending_handler = getattr(
                conversation_service, "set_pending_handler", None
            )
            if callable(set_pending_handler):
                set_pending_handler(self._notify_conversation_command)
        if feedback_queue is not None:
            set_completion_handler = getattr(
                feedback_queue, "set_completion_handler", None
            )
            if callable(set_completion_handler):
                set_completion_handler(self._notify_feedback_decision)
        self._stopped = False
        self._active_tasks: set[asyncio.Task] = set()

    def start_background(self) -> None:
        """在插件硬门禁通过后启动可恢复后台队列。"""
        queue = self.feedback_queue
        if queue is not None and hasattr(queue, "start"):
            queue.start()

    @staticmethod
    def _build_orchestrator(plugin: Any, config: Mapping[str, Any]) -> Any:
        """延迟导入 MoviePilot 宿主依赖并创建推荐编排器。"""
        from ..adapter.agent import AgentRankAgentAdapter
        from ..adapter.discovery import DiscoveryAdapter
        from ..adapter.library import LibraryAdapter
        from ..adapter.media import MediaRecognitionAdapter
        from ..adapter.subscription import SubscriptionAdapter
        from ..adapter.tmdb_keyword import TmdbKeywordAdapter
        from ..adapter.emby import EmbyServiceAccess
        from ..adapter.playback_reporting import PlaybackReportingAdapter
        from ..storage.repository import AgentRankRepository
        from .candidate import CandidateCollectionService
        from .data_lifecycle import DataLifecycleService
        from .keyword_resolution import ControlledRetrievalPlanResolver
        from .poster import (
            BoardPosterRepairService,
            BoardSourceRepairService,
            PosterImageService,
        )
        from .playback_profile import PlaybackProfileService
        from .attribution import OutcomeAttributionService
        from .recommendation import RecommendationOrchestrator
        from .storage_migration import AgentRankStorageMigrationService

        repository = AgentRankRepository(
            plugin,
            history_limit=int(config.get("history_limit") or 50),
            candidate_snapshot_limit=int(
                config.get("candidate_snapshot_limit") or 20
            ),
            feedback_event_limit=int(config.get("feedback_event_limit") or 1000),
        )
        plugin._repository = repository
        plugin._poster_service = PosterImageService()
        subscription_adapter = SubscriptionAdapter()
        library_adapter = LibraryAdapter()
        attribution_service = OutcomeAttributionService(
            repository,
            subscription_adapter=subscription_adapter,
            library_adapter=library_adapter,
            record_limit=int(config.get("attribution_record_limit") or 500),
        )
        plugin._attribution_service = attribution_service
        playback_access = EmbyServiceAccess()
        plugin._emby_access = playback_access
        playback_service = PlaybackProfileService(
            repository=repository,
            reporting_adapter=PlaybackReportingAdapter(playback_access),
            attribution_service=attribution_service,
        )
        plugin._playback_service = playback_service
        media_adapter = MediaRecognitionAdapter()
        profile_ids = [
            identity.profile_id for identity in configured_identities(config)
        ]
        plugin._migration_status = AgentRankStorageMigrationService(
            repository
        ).migrate_profiles(profile_ids).to_dict()
        BoardPosterRepairService(repository, media_adapter).repair_profiles(profile_ids)
        BoardSourceRepairService(repository, media_adapter).repair_profiles(profile_ids)
        lifecycle_service = DataLifecycleService(repository, config)
        plugin._data_lifecycle = lifecycle_service
        lifecycle_profiles = []
        for profile_id in profile_ids:
            try:
                pruned = lifecycle_service.prune_profile(profile_id)
                lifecycle_profiles.append(
                    {"profile_id": profile_id, "status": "ready", "pruned": pruned}
                )
            except Exception:
                lifecycle_profiles.append(
                    {
                        "profile_id": profile_id,
                        "status": "failed",
                        "pruned": {},
                        "message": "数据保留维护失败，已保留现有数据",
                    }
                )
        plugin._data_lifecycle_status = {
            "status": (
                "partial_failed"
                if any(item["status"] == "failed" for item in lifecycle_profiles)
                else "ready"
            ),
            "profiles": lifecycle_profiles,
            "retention_policy": lifecycle_service.policy.to_dict(),
        }
        return RecommendationOrchestrator(
            repository=repository,
            candidate_service=CandidateCollectionService(
                DiscoveryAdapter(),
                repository,
                media_adapter,
                library_adapter=library_adapter,
                subscription_adapter=subscription_adapter,
            ),
            agent_adapter=AgentRankAgentAdapter(),
            playback_service=playback_service,
            retrieval_plan_resolver=ControlledRetrievalPlanResolver(
                keyword_searcher=TmdbKeywordAdapter().search
            ),
        )

    @staticmethod
    def _default_trigger_factory(cron: str) -> Any:
        """通过 APScheduler 解析标准五段 Cron。"""
        from apscheduler.triggers.cron import CronTrigger

        return CronTrigger.from_crontab(cron)

    @staticmethod
    def _default_date_trigger_factory() -> Any:
        """创建延迟三秒执行的一次性调度触发器。"""
        from datetime import datetime, timedelta

        from apscheduler.triggers.date import DateTrigger

        return DateTrigger(run_date=datetime.now() + timedelta(seconds=3))

    @staticmethod
    def _default_reminder_trigger_factory() -> Any:
        """创建每五分钟领取一次待确认提醒的稳定触发器。"""
        from apscheduler.triggers.interval import IntervalTrigger

        return IntervalTrigger(minutes=5)

    @staticmethod
    def _default_attribution_trigger_factory() -> Any:
        """创建每十分钟复查一次结果归因的稳定触发器。"""
        from apscheduler.triggers.interval import IntervalTrigger

        return IntervalTrigger(minutes=10)

    def _config_errors(self) -> List[str]:
        """返回可原地追加的配置错误列表。"""
        errors = self.config.get("_validation_errors")
        if not isinstance(errors, list):
            errors = []
            self.config["_validation_errors"] = errors
        return errors

    def get_services(self) -> List[Dict[str, Any]]:
        """按启用状态返回一次性任务与稳定周期服务。"""
        if self._stopped:
            return []
        if not self.config.get("enabled"):
            return []
        services: List[Dict[str, Any]] = []
        run_once_requested = bool(self.config.get("onlyonce"))
        self.config["onlyonce"] = False
        if run_once_requested:
            try:
                services.append(
                    {
                        "id": "AgentRank.Recommendation.Once",
                        "name": "Agent榜单中心立即生成",
                        "trigger": self._date_trigger_factory(),
                        "func": self.run_scheduled,
                        "kwargs": {},
                    }
                )
            except Exception as error:
                message = f"date trigger invalid: {error}"
                errors = self._config_errors()
                if message not in errors:
                    errors.append(message)
        if self.config.get("schedule_enabled"):
            cron = str(self.config.get("cron") or "").strip()
            try:
                trigger = self._trigger_factory(cron)
            except Exception as error:
                message = f"cron invalid: {error}"
                errors = self._config_errors()
                if message not in errors:
                    errors.append(message)
            else:
                services.append(
                    {
                        "id": "AgentRank.Recommendation",
                        "name": "Agent榜单中心周期生成",
                        "trigger": trigger,
                        "func": self.run_scheduled,
                        "kwargs": {},
                    }
                )
        if self.pending_center_service is not None and self.notification_service is not None:
            try:
                reminder_trigger = self._reminder_trigger_factory()
            except Exception as error:
                message = f"pending reminder trigger invalid: {error}"
                errors = self._config_errors()
                if message not in errors:
                    errors.append(message)
            else:
                services.append(
                    {
                        "id": "AgentRank.PendingReminders",
                        "name": "Agent榜单中心待确认提醒",
                        "trigger": reminder_trigger,
                        "func": self.send_pending_reminders,
                        "kwargs": {},
                    }
                )
        if self.attribution_service is not None:
            try:
                attribution_trigger = self._attribution_trigger_factory()
            except Exception as error:
                message = f"outcome attribution trigger invalid: {error}"
                errors = self._config_errors()
                if message not in errors:
                    errors.append(message)
            else:
                services.append(
                    {
                        "id": "AgentRank.OutcomeAttribution",
                        "name": "Agent榜单中心结果归因复查",
                        "trigger": attribution_trigger,
                        "func": self.verify_outcomes,
                        "kwargs": {},
                    }
                )
        return services

    @staticmethod
    def _display_name(profile_id: str, config: Mapping[str, Any]) -> str:
        """返回稳定画像身份对应的 Emby 显示名。"""
        for identity in configured_identities(config):
            if identity.profile_id == profile_id:
                return identity.username
        return ""

    async def refresh(self, profile_id: str) -> Any:
        """执行一次手动身份刷新；停止后拒绝新任务。"""
        if self._stopped:
            raise RuntimeError("AgentRank runtime is stopped")
        get_state = getattr(self.plugin, "get_state", None)
        if callable(get_state) and not get_state():
            enablement = getattr(self.plugin, "_enablement", {}) or {}
            raise RuntimeError(
                str(enablement.get("message") or "AgentRank 插件当前不可用")
            )
        try:
            result = await self.orchestrator.run(profile_id, self.config)
        except Exception as error:
            logger.exception("AgentRank 手动运行异常 profile_id=%s", profile_id)
            self._notify_exception(profile_id, "manual_refresh", error)
            raise
        self._apply_post_action(profile_id, result)
        return result

    def _apply_post_action(self, profile_id: str, result: Any) -> None:
        """按动作模式执行通知或自动订阅后处理。"""
        status = getattr(result, "status", "")
        if status not in {"success", "recommendation_incomplete"}:
            if status not in {"", "running"}:
                self._notify_result_failure(profile_id, result)
            return
        mode = self.config.get("action_mode")
        board = getattr(result, "board", None)
        if mode == "notify":
            if self.notification_service is not None and board is not None:
                self.notification_service.send_confirmation(
                    getattr(board, "username", "")
                    or self._display_name(profile_id, self.config),
                    board,
                )
            return
        if mode != "auto_subscribe" or self.subscription_service is None:
            return
        batch = self.subscription_service.subscribe_top_n(
            profile_id=profile_id,
            top_n=int(self.config.get("auto_subscribe_top_n") or 0),
            configured_limit=int(self.config.get("auto_subscribe_limit") or 0),
            confidence_threshold=float(
                self.config.get("confidence_threshold") or 0.0
            ),
        )
        result.subscription_result = batch
        repository = getattr(self.plugin, "_repository", None)
        failures = [
            f"{item_index}: {item.message}"
            for item_index, item in (
                (
                    getattr(board.recommendations[index], "candidate_id", str(index + 1))
                    if board is not None and index < len(board.recommendations)
                    else str(index + 1),
                    item,
                )
                for index, item in enumerate(batch.items)
            )
            if not item.success
        ]
        if batch.failure_count and not failures:
            failures.append(f"auto subscription: {batch.status}")
        if batch.status not in {"success", "disabled"}:
            result.status = "subscription_partial_failed"
            result.message = f"自动订阅部分失败：{batch.failure_count} 项"
            if board is not None:
                board.status = "subscription_partial_failed"
                board.message = result.message
                if repository is not None:
                    repository.save_board(board)
        if repository is not None and getattr(result, "run_id", ""):
            repository.annotate_run(
                profile_id=profile_id,
                run_id=result.run_id,
                status=result.status,
                metrics={
                    "subscription_success_count": batch.success_count,
                    "subscription_failure_count": batch.failure_count,
                },
                errors=failures,
            )

    def _notifications_enabled(self) -> bool:
        """返回当前配置是否允许发送 AgentRank 通知。"""
        return bool(self.config.get("notify", True))

    def _notify_result_failure(self, profile_id: str, result: Any) -> None:
        """发送一次结构化运行失败通知。"""
        if not self._notifications_enabled() or self.notification_service is None:
            return
        self.notification_service.send_failure(
            username=self._display_name(profile_id, self.config),
            status=str(getattr(result, "status", "failed") or "failed"),
            run_id=str(getattr(result, "run_id", "") or ""),
            message=str(getattr(result, "message", "") or "运行失败"),
            old_board_preserved=getattr(result, "board", None) is not None,
        )

    def _notify_exception(self, profile_id: str, stage: str, error: Exception) -> None:
        """发送未捕获运行异常通知。"""
        if not self._notifications_enabled() or self.notification_service is None:
            return
        self.notification_service.send_failure(
            username=self._display_name(profile_id, self.config),
            status="runtime_exception",
            run_id="",
            message=f"{stage}: {error}",
            old_board_preserved=True,
        )

    def _notify_feedback_attention(self, job: Any) -> None:
        """在反馈任务达到重试上限后发送不含事件载荷的通知。"""
        if not self._notifications_enabled() or self.notification_service is None:
            return
        self.notification_service.send_failure(
            username=self._display_name(job.profile_id, self.config),
            status="feedback_needs_attention",
            run_id="",
            message="反馈理解多次失败，请稍后在插件详情页重试",
            old_board_preserved=True,
        )

    def _notify_feedback_decision(self, job: Any, result: Any = None) -> None:
        """在反馈理解成功后发送一次新提案或问询通知。"""
        del result
        if (
            not self._notifications_enabled()
            or self.notification_service is None
            or self.pending_center_service is None
        ):
            return
        notice = self.pending_center_service.notice_for_event(
            job.profile_id, job.event_id
        )
        if notice is None:
            return
        self.notification_service.send_pending(
            self._display_name(job.profile_id, self.config), notice
        )

    def _notify_conversation_command(self, command: Any) -> None:
        """发送对话新建命令的安全待确认通知。"""
        if (
            not self._notifications_enabled()
            or self.notification_service is None
            or self.pending_center_service is None
        ):
            return
        notice = self.pending_center_service.notice_for_command(command)
        self.notification_service.send_pending(
            self._display_name(command.profile_id, self.config), notice
        )

    def send_pending_reminders(self) -> List[Dict[str, Any]]:
        """领取全部画像的到期提醒并逐条安全发送。"""
        if (
            self._stopped
            or not self.config.get("enabled")
            or not self._notifications_enabled()
            or self.pending_center_service is None
            or self.notification_service is None
        ):
            return []
        results: List[Dict[str, Any]] = []
        for identity in configured_identities(self.config):
            notices = self.pending_center_service.claim_due_notices(
                identity.profile_id
            )
            for notice in notices:
                try:
                    interactive = self.notification_service.send_pending(
                        identity.username, notice, reminder=True
                    )
                    results.append(
                        {
                            "profile_id": identity.profile_id,
                            "item_type": notice.item.item_type,
                            "item_id": notice.item.item_id,
                            "status": "sent",
                            "interactive": bool(interactive),
                        }
                    )
                except Exception:
                    logger.exception(
                        "AgentRank 待确认提醒发送失败 profile_id=%s type=%s",
                        identity.profile_id,
                        notice.item.item_type,
                    )
                    results.append(
                        {
                            "profile_id": identity.profile_id,
                            "item_type": notice.item.item_type,
                            "item_id": notice.item.item_id,
                            "status": "failed",
                            "interactive": False,
                        }
                    )
        return results

    def verify_outcomes(self) -> List[Dict[str, Any]]:
        """复查全部配置画像的订阅、入库和播放归因。"""
        if (
            self._stopped
            or not self.config.get("enabled")
            or self.attribution_service is None
        ):
            return []
        results: List[Dict[str, Any]] = []
        for identity in configured_identities(self.config):
            try:
                result = self.attribution_service.verify_profile(identity.profile_id)
                results.append(result.to_dict())
            except Exception:
                logger.exception(
                    "AgentRank 结果归因复查失败 profile_id=%s",
                    identity.profile_id,
                )
                results.append(
                    {
                        "profile_id": identity.profile_id,
                        "checked": 0,
                        "advanced": 0,
                        "pending": 0,
                        "status": "verification_failed",
                    }
                )
        return results

    async def run_scheduled(self) -> List[Dict[str, Any]]:
        """顺序处理画像身份，单个身份异常不阻断后续身份。"""
        if self._stopped or not self.config.get("enabled"):
            return []
        task = asyncio.current_task()
        if task is not None:
            self._active_tasks.add(task)
        results: List[Dict[str, Any]] = []
        try:
            for identity in configured_identities(self.config):
                if self._stopped:
                    break
                profile_id = identity.profile_id
                try:
                    result = await self.orchestrator.run(profile_id, self.config)
                    self._apply_post_action(profile_id, result)
                    results.append(
                        {
                            "profile_id": profile_id,
                            "username": identity.username,
                            "status": getattr(result, "status", "unknown"),
                        }
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    logger.exception(
                        "AgentRank 定时运行异常 profile_id=%s", profile_id
                    )
                    self._notify_exception(profile_id, "scheduled_run", error)
                    results.append(
                        {
                            "profile_id": profile_id,
                            "username": identity.username,
                            "status": "failed",
                            "message": str(error),
                        }
                    )
            return results
        finally:
            if task is not None:
                self._active_tasks.discard(task)

    def stop(self) -> None:
        """幂等停止运行时并取消所有进行中的调度任务。"""
        if self._stopped:
            return
        self._stopped = True
        if self.feedback_queue is not None and hasattr(self.feedback_queue, "stop"):
            self.feedback_queue.stop()
        current = None
        try:
            current = asyncio.current_task()
        except RuntimeError:
            pass
        for task in list(self._active_tasks):
            if task is not current and not task.done():
                task.cancel()
        self._active_tasks.clear()
