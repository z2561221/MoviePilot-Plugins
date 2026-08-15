"""持久异步反馈队列的顺序、并发、恢复与失败边界测试。"""

import copy
import importlib
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"
PACKAGE_NAME = "agentrank_feedback_queue_test"
PROFILE_ID = "emby:home:user-1"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

feedback_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback")
queue_service_module = importlib.import_module(f"{PACKAGE_NAME}.service.feedback_queue")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")

FeedbackEvent = feedback_module.FeedbackEvent
FeedbackQueueService = queue_service_module.FeedbackQueueService
FeedbackQueueError = queue_service_module.FeedbackQueueError
AgentRankRepository = repository_module.AgentRankRepository


class FakePlugin:
    """用内存字典模拟 MoviePilot 插件数据接口。"""

    def __init__(self, data=None):
        self.data = copy.deepcopy(dict(data or {}))

    def get_data(self, key=None):
        """返回指定键的独立副本。"""
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """保存指定键的独立副本。"""
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除指定键。"""
        self.data.pop(key, None)


def _event(key, *, profile_id=PROFILE_ID, index=1):
    """构造一条待持久化的反馈事件。"""
    return FeedbackEvent(
        profile_id=profile_id,
        kind="like",
        candidate_id=f"tmdb:tv:{100 + index}",
        run_id=f"run-{index}",
        analysis_id=f"analysis-{index}",
        idempotency_key=key,
        created_by_mp_user_id="7",
    )


def _stored(repository, key, *, profile_id=PROFILE_ID, index=1):
    """把测试事件写入反馈账本并返回已持久化事件。"""
    return repository.append_feedback_event(
        _event(key, profile_id=profile_id, index=index)
    ).event


def _wait_until(predicate, timeout=2.0):
    """等待异步条件满足，超时提供明确测试失败。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    assert predicate(), "异步队列未在限定时间内达到预期状态"


def test_enqueue_is_idempotent_and_never_evicts_unfinished_jobs():
    """重复入队只保留一项，容量满时不删除未完成任务。"""
    repository = AgentRankRepository(FakePlugin())
    queue = FeedbackQueueService(
        repository, profile_ids=[PROFILE_ID], queue_limit=2, poll_seconds=0.01
    )
    first = _stored(repository, "queue-1", index=1)
    second = _stored(repository, "queue-2", index=2)
    third = _stored(repository, "queue-3", index=3)

    first_job = queue.enqueue_event(first)
    duplicate = queue.enqueue_event(first)
    queue.enqueue_event(second)

    assert duplicate == first_job
    assert [job.event_sequence for job in repository.load_feedback_queue(PROFILE_ID)] == [
        1,
        2,
    ]
    with pytest.raises(FeedbackQueueError, match="入队失败"):
        queue.enqueue_event(third)
    assert [job.event_sequence for job in repository.load_feedback_queue(PROFILE_ID)] == [
        1,
        2,
    ]

    claimed = repository.claim_next_feedback_job(
        PROFILE_ID, lease_id="lease-terminal", now=datetime.now(timezone.utc)
    )
    assert claimed is not None
    assert repository.replace_feedback_job(
        claimed.complete(), expected_lease_id="lease-terminal"
    )
    queue.enqueue_event(third)
    jobs = repository.load_feedback_queue(PROFILE_ID)
    assert [job.event_sequence for job in jobs] == [2, 3]


def test_profile_debounce_moves_all_unclaimed_feedback_to_last_action_deadline():
    """同一画像的新赞踩会把全部未认领任务推迟到最后操作后30秒。"""
    repository = AgentRankRepository(FakePlugin())
    clock = [datetime.now(timezone.utc)]
    queue = FeedbackQueueService(
        repository,
        profile_ids=[PROFILE_ID],
        now_factory=lambda: clock[0],
    )
    first = _stored(repository, "debounce-1", index=1)
    second = _stored(repository, "debounce-2", index=2)

    first_job = queue.enqueue_event(
        first, delay_seconds=30, debounce_profile=True
    )
    first_deadline = datetime.fromisoformat(first_job.next_attempt_at)
    clock[0] += timedelta(seconds=10)
    second_job = queue.enqueue_event(
        second, delay_seconds=30, debounce_profile=True
    )
    jobs = repository.load_feedback_queue(PROFILE_ID)
    final_deadline = datetime.fromisoformat(second_job.next_attempt_at)

    assert final_deadline == clock[0] + timedelta(seconds=30)
    assert datetime.fromisoformat(jobs[0].next_attempt_at) == final_deadline
    assert final_deadline > first_deadline
    assert repository.claim_next_feedback_job(
        PROFILE_ID, lease_id="too-early", now=first_deadline
    ) is None
    assert repository.claim_next_feedback_job(
        PROFILE_ID, lease_id="ready", now=final_deadline
    ).event_id == first.event_id


def test_feedback_retention_preserves_events_referenced_by_unfinished_jobs():
    """反馈账本裁剪保留未完成任务引用，终态后再恢复正常上限。"""
    repository = AgentRankRepository(FakePlugin(), feedback_event_limit=2)
    queue = FeedbackQueueService(repository, profile_ids=[PROFILE_ID])
    first = _stored(repository, "retention-1", index=1)
    queue.enqueue_event(first)
    for index in range(2, 5):
        _stored(repository, f"retention-{index}", index=index)

    assert [
        event.sequence for event in repository.load_feedback_events(PROFILE_ID)
    ] == [1, 2, 3, 4]

    claimed = repository.claim_next_feedback_job(
        PROFILE_ID, lease_id="retention-lease", now=datetime.now(timezone.utc)
    )
    assert claimed is not None
    assert repository.replace_feedback_job(
        claimed.complete(), expected_lease_id="retention-lease"
    )
    assert repository.prune_feedback_events(PROFILE_ID, 2) == 2
    assert [
        event.sequence for event in repository.load_feedback_events(PROFILE_ID)
    ] == [3, 4]


def test_same_profile_is_fifo_and_duplicate_enqueue_is_not_processed_twice():
    """同一 profile 严格按事件序号处理，重复入队不会重复调用处理器。"""
    repository = AgentRankRepository(FakePlugin())
    calls = []
    lock = threading.Lock()

    def handler(job):
        """记录处理顺序。"""
        with lock:
            calls.append(job.event_sequence)

    queue = FeedbackQueueService(
        repository,
        handler=handler,
        profile_ids=[PROFILE_ID],
        max_workers=2,
        poll_seconds=0.01,
    )
    first = _stored(repository, "fifo-1", index=1)
    second = _stored(repository, "fifo-2", index=2)
    queue.enqueue_event(second)
    queue.enqueue_event(first)
    queue.start()
    try:
        _wait_until(
            lambda: all(
                job.status == "completed"
                for job in repository.load_feedback_queue(PROFILE_ID)
            )
        )
        queue.enqueue_event(first)
        time.sleep(0.05)
    finally:
        queue.stop()

    assert calls == [1, 2]


def test_completion_notification_runs_once_and_failure_never_requeues_job():
    """成功通知回调只执行一次，回调异常不回滚已完成理解任务。"""
    repository = AgentRankRepository(FakePlugin())
    event = _stored(repository, "completion-1")
    completed = []

    def handler(job):
        """返回可交给完成回调的结构化结果。"""
        return {"event_id": job.event_id}

    def failing_completion(job, result):
        """记录一次后模拟通知渠道异常。"""
        completed.append((job.event_id, result))
        raise RuntimeError("notification unavailable")

    queue = FeedbackQueueService(
        repository,
        handler=handler,
        completion_handler=failing_completion,
        profile_ids=[PROFILE_ID],
    )
    queue.enqueue_event(event)
    claimed = repository.claim_next_feedback_job(
        PROFILE_ID,
        lease_id="completion-lease",
        now=datetime.now(timezone.utc),
    )
    assert claimed is not None

    queue._process_job(claimed, handler)

    stored = repository.load_feedback_queue(PROFILE_ID)[0]
    assert stored.status == "completed"
    assert completed == [(event.event_id, {"event_id": event.event_id})]
    assert stored.last_error == ""


def test_terminal_retryable_budget_failure_needs_attention_without_second_attempt():
    """总预算耗尽后直接进入可重试终态，不再自动开启新的完整预算。"""
    class BudgetFailure(RuntimeError):
        terminal_retryable = True

    repository = AgentRankRepository(FakePlugin())
    event = _stored(repository, "budget-terminal")
    attention = []

    def handler(_job):
        raise BudgetFailure("budget exhausted")

    queue = FeedbackQueueService(
        repository,
        handler=handler,
        attention_handler=lambda job: attention.append(job.job_id),
        profile_ids=[PROFILE_ID],
        max_attempts=3,
    )
    queue.enqueue_event(event)
    claimed = repository.claim_next_feedback_job(
        PROFILE_ID,
        lease_id="budget-lease",
        now=datetime.now(timezone.utc),
    )
    queue._process_job(claimed, handler)

    stored = repository.load_feedback_queue(PROFILE_ID)[0]
    assert stored.status == "needs_attention"
    assert stored.attempts == 1
    assert attention == [stored.job_id]


def test_cross_profile_parallelism_is_bounded_by_worker_limit():
    """不同 profile 可以并行，但活跃处理数不超过 max_workers。"""
    profiles = ["emby:home:user-1", "emby:home:user-2", "emby:home:user-3"]
    repository = AgentRankRepository(FakePlugin())
    started = set()
    active = 0
    maximum = 0
    lock = threading.Lock()
    release = threading.Event()

    def handler(job):
        """阻塞处理器以观测跨 profile 并发上限。"""
        nonlocal active, maximum
        with lock:
            started.add(job.profile_id)
            active += 1
            maximum = max(maximum, active)
        release.wait(timeout=2)
        with lock:
            active -= 1

    queue = FeedbackQueueService(
        repository,
        handler=handler,
        profile_ids=profiles,
        max_workers=2,
        poll_seconds=0.01,
    )
    for index, profile_id in enumerate(profiles, 1):
        queue.enqueue_event(_stored(repository, f"parallel-{index}", profile_id=profile_id, index=index))
    queue.start()
    try:
        _wait_until(lambda: len(started) == 2)
        with lock:
            assert maximum == 2
        release.set()
        _wait_until(
            lambda: all(
                job.status == "completed"
                for profile_id in profiles
                for job in repository.load_feedback_queue(profile_id)
            )
        )
    finally:
        release.set()
        queue.stop()

    assert maximum == 2


def test_restart_recovers_running_job_before_dispatch_and_preserves_attempt_count():
    """新队列启动前恢复旧租约，任务只被新 worker 继续一次。"""
    repository = AgentRankRepository(FakePlugin())
    event = _stored(repository, "restart-1")
    first_queue = FeedbackQueueService(repository, profile_ids=[PROFILE_ID])
    first_queue.enqueue_event(event)
    claimed = repository.claim_next_feedback_job(
        PROFILE_ID, lease_id="old-lease", now=datetime.now(timezone.utc)
    )
    assert claimed is not None and claimed.status == "running"

    calls = []

    def handler(job):
        """记录恢复后的唯一处理。"""
        calls.append(job.event_id)

    second_queue = FeedbackQueueService(
        repository, handler=handler, profile_ids=[PROFILE_ID], poll_seconds=0.01
    )
    second_queue.start()
    try:
        _wait_until(
            lambda: repository.load_feedback_queue(PROFILE_ID)[0].status == "completed"
        )
    finally:
        second_queue.stop()

    final = repository.load_feedback_queue(PROFILE_ID)[0]
    assert calls == [event.event_id]
    assert final.attempts == 2
    assert final.lease_id == ""


def test_late_worker_cannot_overwrite_recovered_job():
    """旧 worker 持有的租约在恢复后写回会被拒绝。"""
    repository = AgentRankRepository(FakePlugin())
    event = _stored(repository, "lease-1")
    queue = FeedbackQueueService(repository, profile_ids=[PROFILE_ID])
    queue.enqueue_event(event)
    claimed = repository.claim_next_feedback_job(
        PROFILE_ID, lease_id="stale-lease", now=datetime.now(timezone.utc)
    )
    assert claimed is not None
    assert repository.recover_feedback_queue(PROFILE_ID) == 1

    assert not repository.replace_feedback_job(
        claimed.complete(), expected_lease_id="stale-lease"
    )
    current = repository.load_feedback_queue(PROFILE_ID)[0]
    assert current.status == "queued"
    assert current.lease_id == ""


def test_failures_use_bounded_exponential_backoff_and_safe_error_text():
    """失败按 2 的幂退避，错误持久化只保留安全类型文案。"""
    current = [datetime(2026, 7, 28, tzinfo=timezone.utc)]
    repository = AgentRankRepository(FakePlugin())
    event = _stored(repository, "retry-1")

    def clock():
        """返回可控的 UTC 时钟。"""
        return current[0]

    def failing_handler(_job):
        """模拟带秘密片段的供应商异常。"""
        raise RuntimeError("provider_token=secret-value")

    queue = FeedbackQueueService(
        repository,
        profile_ids=[PROFILE_ID],
        max_attempts=3,
        retry_base_seconds=2,
        retry_max_seconds=10,
        now_factory=clock,
    )
    queue.enqueue_event(event)
    first = repository.claim_next_feedback_job(
        PROFILE_ID, lease_id="retry-lease-1", now=current[0]
    )
    assert first is not None
    queue._process_job(first, failing_handler)
    after_first = repository.load_feedback_queue(PROFILE_ID)[0]
    assert after_first.status == "retry_wait"
    assert after_first.next_attempt_at == (current[0] + timedelta(seconds=2)).isoformat()
    assert "secret-value" not in after_first.last_error
    assert after_first.last_error.startswith("RuntimeError:")

    current[0] += timedelta(seconds=2)
    second = repository.claim_next_feedback_job(
        PROFILE_ID, lease_id="retry-lease-2", now=current[0]
    )
    assert second is not None
    queue._process_job(second, failing_handler)
    after_second = repository.load_feedback_queue(PROFILE_ID)[0]
    assert after_second.status == "retry_wait"
    assert after_second.next_attempt_at == (current[0] + timedelta(seconds=4)).isoformat()


def test_retry_limit_moves_job_to_needs_attention_and_notifies_once():
    """达到失败上限后进入死信状态并只触发一次人工关注通知。"""
    current = [datetime(2026, 7, 28, tzinfo=timezone.utc)]
    repository = AgentRankRepository(FakePlugin())
    event = _stored(repository, "dead-letter-1")
    attention = []

    def clock():
        """返回可控的 UTC 时钟。"""
        return current[0]

    def failing_handler(_job):
        """模拟持续失败的理解处理器。"""
        raise TimeoutError("供应商响应超时")

    queue = FeedbackQueueService(
        repository,
        profile_ids=[PROFILE_ID],
        attention_handler=attention.append,
        max_attempts=2,
        retry_base_seconds=1,
        now_factory=clock,
    )
    queue.enqueue_event(event)
    first = repository.claim_next_feedback_job(
        PROFILE_ID, lease_id="dead-lease-1", now=current[0]
    )
    assert first is not None
    queue._process_job(first, failing_handler)
    current[0] += timedelta(seconds=1)
    second = repository.claim_next_feedback_job(
        PROFILE_ID, lease_id="dead-lease-2", now=current[0]
    )
    assert second is not None
    queue._process_job(second, failing_handler)

    final = repository.load_feedback_queue(PROFILE_ID)[0]
    assert final.status == "needs_attention"
    assert final.attempts == 2
    assert len(attention) == 1
    assert "供应商" not in final.last_error


def test_export_contains_only_safe_queue_metadata_and_pruning_keeps_pending_jobs():
    """导出不暴露租约，生命周期裁剪不会删除未完成任务。"""
    data_lifecycle_module = importlib.import_module(
        f"{PACKAGE_NAME}.service.data_lifecycle"
    )
    repository = AgentRankRepository(FakePlugin())
    event = _stored(repository, "export-1")
    queue = FeedbackQueueService(repository, profile_ids=[PROFILE_ID])
    queue.enqueue_event(event)
    claimed = repository.claim_next_feedback_job(
        PROFILE_ID, lease_id="private-lease", now=datetime.now(timezone.utc)
    )
    assert claimed is not None

    exported = data_lifecycle_module.DataLifecycleService(repository).export_profile(
        PROFILE_ID
    )
    item = exported["feedback_queue"][0]
    assert item["status"] == "running"
    assert "lease_id" not in item
    assert "last_error" not in item
    assert repository.prune_feedback_queue(PROFILE_ID, 1) == 0
    assert repository.load_feedback_queue(PROFILE_ID)[0].status == "running"
