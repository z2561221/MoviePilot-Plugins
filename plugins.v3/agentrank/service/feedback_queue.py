"""反馈理解任务的持久异步队列与并发调度器。"""

import asyncio
import inspect
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Optional, Set

from ..model.feedback import FeedbackEvent
from ..model.feedback_queue import FeedbackQueueJob
from ..storage.repository import AgentRankRepository


logger = logging.getLogger(__name__)


FeedbackQueueHandler = Callable[[FeedbackQueueJob], Any]
FeedbackQueueAttentionHandler = Callable[[FeedbackQueueJob], Any]
FeedbackQueueCompletionHandler = Callable[[FeedbackQueueJob, Any], Any]


class FeedbackQueueError(Exception):
    """表示反馈任务无法安全入队或恢复。"""


class FeedbackQueueService:
    """按 profile 串行、跨 profile 有界并发且可重启恢复的后台队列。"""

    def __init__(
        self,
        repository: AgentRankRepository,
        *,
        handler: Optional[FeedbackQueueHandler] = None,
        attention_handler: Optional[FeedbackQueueAttentionHandler] = None,
        completion_handler: Optional[FeedbackQueueCompletionHandler] = None,
        profile_ids: Iterable[str] = (),
        max_workers: int = 2,
        queue_limit: int = 200,
        max_attempts: int = 3,
        retry_base_seconds: float = 5.0,
        retry_max_seconds: float = 300.0,
        poll_seconds: float = 0.25,
        now_factory: Callable[[], datetime] = None,
    ):
        """绑定仓储、处理器和可控的并发/退避参数。"""
        if not isinstance(repository, AgentRankRepository):
            raise TypeError("repository must be AgentRankRepository")
        self._repository = repository
        self._handler = handler
        self._attention_handler = attention_handler
        self._completion_handler = completion_handler
        self._profiles: Set[str] = {
            str(profile_id or "").strip()
            for profile_id in profile_ids or ()
            if str(profile_id or "").strip()
        }
        self._max_workers = max(1, min(int(max_workers), 32))
        self._queue_limit = max(1, min(int(queue_limit), 100000))
        self._max_attempts = max(1, min(int(max_attempts), 20))
        self._retry_base_seconds = max(0.0, float(retry_base_seconds))
        self._retry_max_seconds = max(
            self._retry_base_seconds, float(retry_max_seconds)
        )
        self._poll_seconds = max(0.01, float(poll_seconds))
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self._state_lock = threading.RLock()
        self._wake = threading.Event()
        self._stop_event = threading.Event()
        self._dispatcher: Optional[threading.Thread] = None
        self._executor: Optional[ThreadPoolExecutor] = None
        self._active_profiles: Set[str] = set()
        self._started = False

    @property
    def started(self) -> bool:
        """返回后台调度线程是否已启动。"""
        with self._state_lock:
            return self._started

    def register_profiles(self, profile_ids: Iterable[str]) -> None:
        """登记可恢复和可调度的 profile 身份。"""
        with self._state_lock:
            self._profiles.update(
                str(profile_id or "").strip()
                for profile_id in profile_ids or ()
                if str(profile_id or "").strip()
            )
        self._wake.set()

    def set_handler(self, handler: Optional[FeedbackQueueHandler]) -> None:
        """替换后台理解处理器并唤醒已有排队任务。"""
        with self._state_lock:
            self._handler = handler
        self._wake.set()

    def set_attention_handler(
        self, handler: Optional[FeedbackQueueAttentionHandler]
    ) -> None:
        """设置达到死信上限后的可见通知回调。"""
        with self._state_lock:
            self._attention_handler = handler

    def set_completion_handler(
        self, handler: Optional[FeedbackQueueCompletionHandler]
    ) -> None:
        """设置任务成功后的非阻断待确认通知回调。"""
        with self._state_lock:
            self._completion_handler = handler

    def start(self) -> None:
        """启动调度线程，并把重启遗留 running 任务恢复为 queued。"""
        with self._state_lock:
            if self._started:
                return
            self._stop_event.clear()
            self._active_profiles.clear()
            profiles = set(self._profiles)
            for profile_id in profiles:
                try:
                    self._repository.recover_feedback_queue(
                        profile_id, now=self._now()
                    )
                except Exception:
                    logger.exception(
                        "AgentRank 反馈队列恢复失败 profile_id=%s", profile_id
                    )
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="agentrank-feedback",
            )
            self._started = True
            self._dispatcher = threading.Thread(
                target=self._dispatch_loop,
                name="agentrank-feedback-dispatcher",
                daemon=True,
            )
            self._dispatcher.start()
        self._wake.set()

    def stop(self) -> None:
        """停止调度、恢复未完成租约并取消尚未开始的后台任务。"""
        with self._state_lock:
            if not self._started:
                return
            self._stop_event.set()
            dispatcher = self._dispatcher
            executor = self._executor
            profiles = set(self._profiles)
            self._wake.set()
        if dispatcher is not None and dispatcher is not threading.current_thread():
            dispatcher.join(timeout=max(1.0, self._poll_seconds * 4))
        for profile_id in profiles:
            try:
                self._repository.recover_feedback_queue(
                    profile_id, now=self._now()
                )
            except Exception:
                logger.exception("AgentRank 反馈队列停止恢复失败 profile_id=%s", profile_id)
        if executor is not None:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                executor.shutdown(wait=False)
        with self._state_lock:
            self._started = False
            self._dispatcher = None
            self._executor = None
            self._active_profiles.clear()

    def enqueue_event(
        self,
        event: FeedbackEvent,
        *,
        delay_seconds: float = 0.0,
        debounce_profile: bool = False,
    ) -> FeedbackQueueJob:
        """持久入队；可从 profile 最后一次操作起统一延迟处理。"""
        delay = max(0.0, float(delay_seconds))
        available_at = self._now() + timedelta(seconds=delay) if delay else None
        job = FeedbackQueueJob.from_event(
            event,
            max_attempts=self._max_attempts,
            available_at=available_at,
        )
        self.register_profiles([event.profile_id])
        try:
            queued = self._repository.enqueue_feedback_job(
                job,
                limit=self._queue_limit,
                debounce_until=available_at if debounce_profile else None,
            )
        except Exception as error:
            raise FeedbackQueueError("反馈理解任务入队失败") from error
        self._wake.set()
        return queued

    def get_job(self, profile_id: str, job_id: str) -> Optional[FeedbackQueueJob]:
        """读取指定 profile 的单个任务状态。"""
        target = str(profile_id or "").strip()
        key = str(job_id or "").strip()
        if not target or not key:
            return None
        return next(
            (job for job in self._repository.load_feedback_queue(target) if job.job_id == key),
            None,
        )

    def wait_for_status(
        self, profile_id: str, job_id: str, status: str, timeout: float = 5.0
    ) -> Optional[FeedbackQueueJob]:
        """在测试或运行态诊断中等待任务到达指定状态。"""
        deadline = self._monotonic() + max(0.0, float(timeout))
        while self._monotonic() <= deadline:
            job = self.get_job(profile_id, job_id)
            if job is not None and job.status == status:
                return job
            self._wake.wait(timeout=min(0.05, max(0.0, deadline - self._monotonic())))
        return self.get_job(profile_id, job_id)

    def _now(self) -> datetime:
        """读取并规范当前 UTC 时间。"""
        value = self._now_factory()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _monotonic() -> float:
        """返回单调时钟，避免等待逻辑受系统时间回拨影响。"""
        import time

        return time.monotonic()

    def _dispatch_loop(self) -> None:
        """循环寻找每个 profile 的首个就绪任务并提交有限 worker。"""
        while not self._stop_event.is_set():
            dispatched = False
            with self._state_lock:
                handler_ready = self._handler is not None
                available = self._max_workers - len(self._active_profiles)
                profiles = sorted(self._profiles)
            if handler_ready and available > 0:
                for profile_id in profiles:
                    if self._stop_event.is_set() or available <= 0:
                        break
                    with self._state_lock:
                        if profile_id in self._active_profiles:
                            continue
                        handler = self._handler
                        executor = self._executor
                        if handler is None or executor is None:
                            break
                        lease_id = uuid.uuid4().hex
                    try:
                        job = self._repository.claim_next_feedback_job(
                            profile_id, lease_id=lease_id, now=self._now()
                        )
                    except Exception:
                        logger.exception(
                            "AgentRank 反馈任务认领失败 profile_id=%s", profile_id
                        )
                        continue
                    if job is None:
                        continue
                    with self._state_lock:
                        self._active_profiles.add(profile_id)
                    executor.submit(self._process_job, job, handler)
                    available -= 1
                    dispatched = True
            if not dispatched:
                self._wake.wait(timeout=self._poll_seconds)
                self._wake.clear()

    def _process_job(
        self, job: FeedbackQueueJob, handler: FeedbackQueueHandler
    ) -> None:
        """执行单个任务并以租约安全写回完成、退避或死信状态。"""
        attention_job: Optional[FeedbackQueueJob] = None
        try:
            result = handler(job)
            if inspect.isawaitable(result):
                result = asyncio.run(result)
            completed = job.complete(self._now())
            replaced = self._repository.replace_feedback_job(
                completed, expected_lease_id=job.lease_id
            )
            if replaced:
                self._notify_completion(job, result)
        except Exception as error:
            safe_error = self._safe_error(error)
            if getattr(error, "terminal_retryable", False) or job.attempts >= job.max_attempts:
                attention_job = job.needs_attention(error=safe_error, now=self._now())
            else:
                delay = min(
                    self._retry_max_seconds,
                    self._retry_base_seconds * (2 ** max(0, job.attempts - 1)),
                )
                attention_job = job.retry(
                    next_attempt_at=self._now() + timedelta(seconds=delay),
                    error=safe_error,
                    now=self._now(),
                )
            try:
                replaced = self._repository.replace_feedback_job(
                    attention_job, expected_lease_id=job.lease_id
                )
                if replaced and attention_job.status == "needs_attention":
                    self._notify_attention(attention_job)
            except Exception:
                logger.exception(
                    "AgentRank 反馈任务失败状态无法写回 job_id=%s", job.job_id
                )
        finally:
            with self._state_lock:
                self._active_profiles.discard(job.profile_id)
            self._wake.set()

    @staticmethod
    def _safe_error(error: Exception) -> str:
        """只保留异常类型与通用文案，避免令牌和原始响应进入队列。"""
        return f"{type(error).__name__}: 反馈理解任务失败"

    def _notify_attention(self, job: FeedbackQueueJob) -> None:
        """调用死信通知回调，通知失败不影响队列终态。"""
        with self._state_lock:
            callback = self._attention_handler
        if callback is None:
            return
        try:
            result = callback(job)
            if inspect.isawaitable(result):
                asyncio.run(result)
        except Exception:
            logger.exception("AgentRank 反馈死信通知失败 job_id=%s", job.job_id)

    def _notify_completion(self, job: FeedbackQueueJob, result: Any) -> None:
        """调用成功回调，通知异常不得把已完成任务改回重试。"""
        with self._state_lock:
            callback = self._completion_handler
        if callback is None:
            return
        try:
            value = callback(job, result)
            if inspect.isawaitable(value):
                asyncio.run(value)
        except Exception:
            logger.exception("AgentRank 反馈完成通知失败 job_id=%s", job.job_id)
