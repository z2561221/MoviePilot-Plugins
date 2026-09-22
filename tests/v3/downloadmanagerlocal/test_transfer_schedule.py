"""验证事件转种的最早到期时间、后续接续与停止代次隔离。"""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from app.plugins.downloadmanagerlocal import DownloadManagerLocal
from app.plugins.downloadmanagerlocal.model.state import TRANSFER_SCHEDULE_KEY
from app.plugins.downloadmanagerlocal.service import events, lifecycle


@pytest.fixture
def schedule_case(monkeypatch):
    """使用暂停的真实调度器和可控时间，回调只记录调用，不连接下载器。"""
    timezone = pytz.timezone("Asia/Shanghai")
    start = timezone.localize(datetime(2026, 9, 22, 18, 0))
    clock = SimpleNamespace(now=start)
    schedulers = []

    class Clock:
        """为事件模块提供可控时钟。"""

        @classmethod
        def now(cls, tz=None):
            """保持所有到期时间带时区。"""
            return clock.now.astimezone(tz) if tz else clock.now

    def new_scheduler():
        """创建暂停调度器，禁止真实后台执行任何测试回调。"""
        scheduler = BackgroundScheduler(timezone=timezone)
        scheduler.start(paused=True)
        schedulers.append(scheduler)
        return scheduler

    data = {}
    plugin = SimpleNamespace(
        _scheduler=new_scheduler(), _event=threading.Event(),
        _transfer_active=True, _transfer_stop_generation=0,
        _transfer_schedule_lock=threading.RLock(), _transfer_pending_runs={},
        _transfer_scheduled_run=None, _transfer_running_generation=None,
        _fromdownloader="QB1", _delay_minutes=30, _delayed_transfer=Mock(),
        get_data=lambda key=None: data.get(key),
        save_data=lambda key, value: data.__setitem__(key, value),
    )
    monkeypatch.setattr(events, "datetime", Clock)
    for name in (
        "stop_seed_recheck_worker", "stop_upload_limit_worker",
        "stop_speed_monitor_worker", "stop_speed_monitor_runtime",
    ):
        monkeypatch.setattr(lifecycle, name, lambda *args: None)

    def emit(torrent_hash="a", downloader="QB1"):
        """投递整理完成事件，允许构造旧宿主的无 hash 输入。"""
        payload = {"downloader": downloader}
        if torrent_hash is not None:
            payload["download_hash"] = torrent_hash
        events.handle_transfer_complete_event(plugin, SimpleNamespace(event_data=payload))

    def current_job():
        """返回唯一已预约任务，同时约束不会登记多个并行扫描。"""
        jobs = plugin._scheduler.get_jobs()
        assert len(jobs) == 1
        return jobs[0]

    def fire():
        """模拟调度器取走到期任务后执行其生产回调。"""
        job = current_job()
        clock.now = max(clock.now, job.next_run_time)
        plugin._scheduler.remove_job(job.id)
        job.func(**job.kwargs)
        return job

    yield SimpleNamespace(
        plugin=plugin, data=data, clock=clock, start=start, emit=emit, job=current_job,
        fire=fire, new_scheduler=new_scheduler,
    )
    plugin._event.set()
    for scheduler in schedulers:
        if scheduler.running:
            scheduler.shutdown()


def test_continuous_events_keep_first_deadline_and_later_batches(schedule_case):
    """新种子不推迟最早时间，各自的后续到期批次仍会执行。"""
    case = schedule_case
    case.emit("a")
    first = case.job()
    case.clock.now += timedelta(minutes=10)
    case.emit("b")
    case.clock.now += timedelta(minutes=10)
    case.emit("c")
    assert case.job().id == first.id
    assert case.job().next_run_time == case.start + timedelta(minutes=30)

    case.fire()
    assert case.plugin._delayed_transfer.call_count == 1
    assert case.job().next_run_time == case.start + timedelta(minutes=40)
    case.fire()
    assert case.job().next_run_time == case.start + timedelta(minutes=50)
    case.fire()
    assert case.plugin._delayed_transfer.call_count == 3
    assert case.plugin._transfer_pending_runs == {}
    assert case.plugin._scheduler.get_jobs() == []


def test_repeated_torrent_events_coalesce_without_postponement(schedule_case):
    """同种逐文件事件和重复投递合并到最早一次预约。"""
    case = schedule_case
    case.emit("ABCD")
    first = case.job()
    for _ in range(20):
        case.clock.now += timedelta(seconds=30)
        case.emit("abcd")
    assert case.job().next_run_time == first.next_run_time
    assert len(case.plugin._transfer_pending_runs) == 1
    case.fire()
    case.plugin._delayed_transfer.assert_called_once_with()
    assert case.plugin._scheduler.get_jobs() == []


def test_hashless_events_keep_their_later_deadlines(schedule_case):
    """缺少下载 hash 的兼容事件也不能覆盖或吞掉后续到期项。"""
    case = schedule_case
    case.emit(None)
    case.clock.now += timedelta(minutes=10)
    case.emit(None)
    case.fire()
    assert case.job().next_run_time == case.start + timedelta(minutes=40)
    case.fire()
    assert case.plugin._delayed_transfer.call_count == 2


def test_events_during_execution_wait_for_current_batch(schedule_case):
    """扫描期间到达的新事件先保存，当前批次结束后才排定接续。"""
    case = schedule_case
    case.emit("a")

    def during_transfer():
        """在已开始的扫描中模拟另一个整理完成事件。"""
        case.clock.now += timedelta(minutes=5)
        case.emit("b")
        assert case.plugin._scheduler.get_jobs() == []

    case.plugin._delayed_transfer.side_effect = during_transfer
    case.fire()
    assert case.job().next_run_time == case.start + timedelta(minutes=65)
    case.plugin._delayed_transfer.side_effect = None
    case.fire()
    assert case.plugin._delayed_transfer.call_count == 2


def test_slow_batch_preserves_overdue_followup_without_misfire_loss(schedule_case):
    """长扫描结束后立即接续已到期事件，合并同批到期项。"""
    case = schedule_case
    case.emit("a")
    first_id = case.job().id
    case.clock.now += timedelta(minutes=10)
    case.emit("b")
    case.clock.now += timedelta(minutes=10)
    case.emit("c")

    def slow_transfer():
        """仅推进时间来模拟长批次，不执行等待。"""
        case.clock.now += timedelta(hours=1)

    case.plugin._delayed_transfer.side_effect = slow_transfer
    case.fire()
    followup = case.job()
    assert followup.id != first_id
    assert followup.next_run_time < case.clock.now
    assert followup.misfire_grace_time is None
    case.plugin._delayed_transfer.side_effect = None
    case.fire()
    assert case.plugin._delayed_transfer.call_count == 2
    assert case.plugin._scheduler.get_jobs() == []


def test_exception_still_schedules_later_events(schedule_case):
    """一轮扫描抛出异常时保留其他种子的后续预约。"""
    case = schedule_case
    case.emit("a")
    case.clock.now += timedelta(minutes=10)
    case.emit("b")
    case.plugin._delayed_transfer.side_effect = RuntimeError("scan failed")
    with pytest.raises(RuntimeError, match="scan failed"):
        case.fire()
    assert case.job().next_run_time == case.start + timedelta(minutes=40)
    assert case.plugin._transfer_running_generation is None


def test_stop_during_batch_does_not_rearm_pending_events(schedule_case):
    """停止期间退出的旧回调不能重新登记已清空的后续任务。"""
    case = schedule_case
    case.emit("a")
    case.clock.now += timedelta(minutes=10)
    case.emit("b")
    case.plugin._delayed_transfer.side_effect = lambda: lifecycle.stop_plugin_service(case.plugin)
    case.fire()
    assert case.plugin._scheduler is None
    assert case.plugin._transfer_pending_runs == {}
    assert case.plugin._transfer_scheduled_run is None
    assert case.plugin._transfer_running_generation is None
    case.emit("c")
    assert case.plugin._scheduler is None


def test_old_callback_cannot_touch_new_generation(schedule_case):
    """重新初始化后清除停止信号，也不能复活旧预约或清掉新预约。"""
    case = schedule_case
    case.emit("a")
    old_job = case.job()
    lifecycle.stop_plugin_service(case.plugin)
    case.plugin._scheduler = case.new_scheduler()
    case.plugin._event.clear()
    case.emit("b")
    new_job = case.job()
    old_job.func(**old_job.kwargs)
    case.plugin._delayed_transfer.assert_not_called()
    assert case.job().id == new_job.id
    assert list(case.plugin._transfer_pending_runs) == ["hash:b"]


def test_reload_restores_pending_deadline_and_clears_state_after_execution(schedule_case):
    """reload 后恢复原到期时间，执行完成后同步清掉持久化队列。"""
    case = schedule_case
    case.emit("a")
    first = case.job()
    persisted = case.data[TRANSFER_SCHEDULE_KEY]
    assert persisted["items"]["hash:a"] == first.next_run_time.isoformat()

    lifecycle.stop_plugin_service(case.plugin)
    assert case.plugin._transfer_pending_runs == {}
    assert case.data[TRANSFER_SCHEDULE_KEY] == persisted

    case.plugin._scheduler = case.new_scheduler()
    case.plugin._event.clear()
    restored = events.restore_transfer_schedule(case.plugin)
    assert restored == first.next_run_time
    assert case.job().next_run_time == first.next_run_time

    case.fire()
    assert case.plugin._delayed_transfer.call_count == 1
    assert case.data[TRANSFER_SCHEDULE_KEY] == {
        "schema_version": 1,
        "items": {},
    }


def test_reload_resumes_overdue_persisted_event(schedule_case):
    """已过期但未执行的事件在 reload 后立即接续，不会被清理丢失。"""
    case = schedule_case
    overdue = case.start - timedelta(minutes=5)
    case.data[TRANSFER_SCHEDULE_KEY] = {
        "schema_version": 1,
        "items": {"hash:overdue": overdue.isoformat()},
    }
    case.plugin._event.clear()
    restored = events.restore_transfer_schedule(case.plugin)
    assert restored == overdue
    assert case.job().next_run_time == overdue

    case.fire()
    assert case.plugin._delayed_transfer.call_count == 1
    assert case.data[TRANSFER_SCHEDULE_KEY]["items"] == {}


def test_empty_new_instance_stop_does_not_erase_recovered_state(schedule_case):
    """V3 reload 创建的新实例先停服务时，不覆盖旧实例已落盘的队列。"""
    case = schedule_case
    case.emit("a")
    persisted = case.data[TRANSFER_SCHEDULE_KEY]

    case.plugin._transfer_pending_runs.clear()
    events.clear_transfer_schedule(case.plugin)

    assert case.data[TRANSFER_SCHEDULE_KEY] == persisted


def test_new_event_after_empty_batch_starts_new_timer(schedule_case):
    """上一批完全结束后，新事件仍能创建下一轮预约。"""
    case = schedule_case
    case.emit("a")
    case.fire()
    case.clock.now += timedelta(minutes=5)
    case.emit("b")
    assert case.job().next_run_time == case.start + timedelta(minutes=65)


def test_concurrent_events_register_one_earliest_job(schedule_case):
    """并发事件在实例锁内登记，不相互覆盖也不并行创建调度任务。"""
    case = schedule_case
    case.emit("first")
    first_id = case.job().id
    case.clock.now += timedelta(minutes=5)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(case.emit, [str(index) for index in range(24)]))
    assert case.job().id == first_id
    assert len(case.plugin._transfer_pending_runs) == 25


@pytest.mark.parametrize("disabled,downloader", [(True, "QB1"), (False, "QB2")])
def test_disabled_or_other_downloader_events_are_ignored(schedule_case, disabled, downloader):
    """原有开关和下载器过滤继续生效。"""
    case = schedule_case
    case.plugin._transfer_active = not disabled
    case.emit(downloader=downloader)
    assert case.plugin._scheduler.get_jobs() == []
    assert case.plugin._transfer_pending_runs == {}


def test_delay_state_belongs_to_each_plugin_instance(monkeypatch):
    """生产插件实例之间不共享延迟队列或调度锁。"""
    monkeypatch.setattr(DownloadManagerLocal.__mro__[1], "__init__", lambda _self: None)
    first, second = DownloadManagerLocal(), DownloadManagerLocal()
    first._transfer_pending_runs["hash:a"] = datetime.now()
    assert second._transfer_pending_runs == {}
    assert first._transfer_schedule_lock is not second._transfer_schedule_lock
