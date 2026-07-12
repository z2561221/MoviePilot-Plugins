"""AgentRank 运行时依赖组装、周期服务与停止管理。"""

import asyncio
from typing import Any, Callable, Dict, List, Mapping


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
    ):
        """组装真实依赖或接受测试注入。"""
        self.plugin = plugin
        self.config = config
        self.orchestrator = orchestrator or self._build_orchestrator(plugin, config)
        self._trigger_factory = trigger_factory or self._default_trigger_factory
        if orchestrator is None:
            from .notification import NotificationService
            from .subscription import SubscriptionService

            subscription_service = subscription_service or SubscriptionService(
                plugin._repository
            )
            notification_service = notification_service or NotificationService(plugin)
        self.subscription_service = subscription_service
        self.notification_service = notification_service
        self._stopped = False
        self._active_tasks: set[asyncio.Task] = set()

    @staticmethod
    def _build_orchestrator(plugin: Any, config: Mapping[str, Any]) -> Any:
        """延迟导入 MoviePilot 宿主依赖并创建推荐编排器。"""
        from ..adapter.agent import AgentRankAgentAdapter
        from ..adapter.discovery import DiscoveryAdapter
        from ..adapter.subscription import SubscriptionAdapter
        from ..storage.repository import AgentRankRepository
        from .candidate import CandidateCollectionService
        from .profile_input import ProfileInputService
        from .recommendation import RecommendationOrchestrator

        repository = AgentRankRepository(
            plugin, history_limit=int(config.get("history_limit") or 50)
        )
        plugin._repository = repository
        return RecommendationOrchestrator(
            repository=repository,
            profile_service=ProfileInputService(SubscriptionAdapter()),
            candidate_service=CandidateCollectionService(
                DiscoveryAdapter(), repository
            ),
            agent_adapter=AgentRankAgentAdapter(),
        )

    @staticmethod
    def _default_trigger_factory(cron: str) -> Any:
        """通过 APScheduler 解析标准五段 Cron。"""
        from apscheduler.triggers.cron import CronTrigger

        return CronTrigger.from_crontab(cron)

    def _config_errors(self) -> List[str]:
        """返回可原地追加的配置错误列表。"""
        errors = self.config.get("_validation_errors")
        if not isinstance(errors, list):
            errors = []
            self.config["_validation_errors"] = errors
        return errors

    def get_services(self) -> List[Dict[str, Any]]:
        """按启用状态返回一个宿主管理的稳定周期服务。"""
        if self._stopped:
            return []
        if not self.config.get("enabled") or not self.config.get("schedule_enabled"):
            return []
        cron = str(self.config.get("cron") or "").strip()
        try:
            trigger = self._trigger_factory(cron)
        except Exception as error:
            message = f"cron invalid: {error}"
            errors = self._config_errors()
            if message not in errors:
                errors.append(message)
            return []
        return [
            {
                "id": "AgentRank.Recommendation",
                "name": "Agent榜单中心周期生成",
                "trigger": trigger,
                "func": self.run_scheduled,
                "kwargs": {},
            }
        ]

    async def refresh(self, username: str) -> Any:
        """执行一次手动用户刷新；停止后拒绝新任务。"""
        if self._stopped:
            raise RuntimeError("AgentRank runtime is stopped")
        result = await self.orchestrator.run(username, self.config)
        self._send_notification_if_needed(username, result)
        return result

    def _send_notification_if_needed(self, username: str, result: Any) -> None:
        """通知确认模式只发送榜单摘要，不执行订阅。"""
        if self.notification_service is None:
            return
        if self.config.get("action_mode") != "notify":
            return
        if getattr(result, "status", "") not in {"success", "recommendation_incomplete"}:
            return
        board = getattr(result, "board", None)
        if board is not None:
            self.notification_service.send_confirmation(username, board)

    async def run_scheduled(self) -> List[Dict[str, Any]]:
        """顺序处理参与用户，单用户异常不阻断后续用户。"""
        if self._stopped:
            return []
        task = asyncio.current_task()
        if task is not None:
            self._active_tasks.add(task)
        results: List[Dict[str, Any]] = []
        try:
            for username in list(self.config.get("users") or []):
                if self._stopped:
                    break
                try:
                    result = await self.orchestrator.run(username, self.config)
                    self._send_notification_if_needed(username, result)
                    results.append(
                        {
                            "username": username,
                            "status": getattr(result, "status", "unknown"),
                        }
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    results.append(
                        {
                            "username": username,
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
        current = None
        try:
            current = asyncio.current_task()
        except RuntimeError:
            pass
        for task in list(self._active_tasks):
            if task is not current and not task.done():
                task.cancel()
        self._active_tasks.clear()
