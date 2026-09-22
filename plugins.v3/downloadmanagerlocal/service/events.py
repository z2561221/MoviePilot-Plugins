"""下载中心事件服务，承载入口层以外的事件调度逻辑。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytz
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler

from app.sdk.config import settings
from app.sdk.logging import logger

from ..model.state import (
    TRANSFER_SCHEDULE_KEY,
    TRANSFER_SCHEDULE_SCHEMA_VERSION,
)
from .site_tag import cleanup_temporary_tags_for_event
from .speed_monitor import handle_download_added_event as create_speed_monitor_session
from .speed_worker import start_speed_monitor_worker
from .upload_limit_worker import wake_upload_limit_worker

DateTime = datetime


def handle_transfer_complete_event(plugin, event) -> None:
    """保留最早转种时间，同种重复事件合并，后续种子的到期时间接续执行。"""
    if not plugin._transfer_active:
        return

    event_data = event.event_data or {}
    downloader_name = event_data.get("downloader") or event_data.get("downloader_name", "")
    if downloader_name and downloader_name != plugin._fromdownloader:
        return

    delay = _coerce_delay_minutes(plugin._delay_minutes)
    run_time = _transfer_now() + timedelta(minutes=delay)
    torrent_hash = str(event_data.get("download_hash") or "").strip().lower()
    event_key = f"hash:{torrent_hash}" if torrent_hash else f"time:{run_time.isoformat()}"
    with plugin._transfer_schedule_lock:
        generation = int(getattr(plugin, "_transfer_stop_generation", 0) or 0)
        if not _transfer_schedule_active(plugin, generation):
            return
        previous = plugin._transfer_pending_runs.get(event_key)
        plugin._transfer_pending_runs[event_key] = min(previous, run_time) if previous else run_time
        _save_transfer_schedule(plugin, plugin._transfer_pending_runs)
        next_run = _schedule_next_transfer(plugin, generation)
    if next_run:
        logger.info(f"收到 TransferComplete 事件（来源: {downloader_name}），转移做种保持最早执行时间：{next_run:%Y-%m-%d %H:%M:%S}")
    else:
        logger.info(f"收到 TransferComplete 事件（来源: {downloader_name}），本轮执行后接续待到期转移")


def _transfer_schedule_active(plugin, generation: int) -> bool:
    """核对调度所属代次与停止信号，阻止旧回调恢复任务。"""
    event = getattr(plugin, "_event", None)
    return (
        plugin._transfer_active
        and generation == int(getattr(plugin, "_transfer_stop_generation", 0) or 0)
        and (event is None or not event.is_set())
    )


def _transfer_job_id(plugin, generation: int, run_time: datetime) -> str:
    """为每个到期批次生成独立标识，避免接续任务与刚结束的批次争用运行名额。"""
    return f"delayed_transfer_{plugin._fromdownloader or 'default'}_{generation}_{run_time.isoformat()}"


def _transfer_timezone():
    """返回延迟队列使用的宿主时区。"""
    return pytz.timezone(settings.TZ)


def _transfer_now():
    """返回带宿主时区的当前时间，便于测试替换时钟。"""
    return datetime.now(tz=_transfer_timezone())


def _normalize_transfer_deadline(value):
    """把持久化或内存中的到期时间规范为宿主时区。"""
    timezone = _transfer_timezone()
    if getattr(value, "tzinfo", None) is None:
        return timezone.localize(value)
    return value.astimezone(timezone)


def _parse_transfer_deadline(value):
    """解析 ISO 到期时间，非法值返回 None。"""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return _normalize_transfer_deadline(DateTime.fromisoformat(value.strip()))
    except (TypeError, ValueError, OverflowError):
        return None


def _serialize_transfer_schedule(pending_runs: dict) -> dict:
    """将内存队列编码为插件数据可安全持久化的 JSON 结构。"""
    items = {}
    for event_key, run_time in pending_runs.items():
        if not isinstance(event_key, str) or not event_key:
            continue
        try:
            items[event_key] = _normalize_transfer_deadline(run_time).isoformat()
        except (TypeError, ValueError, OverflowError):
            continue
    return {
        "schema_version": TRANSFER_SCHEDULE_SCHEMA_VERSION,
        "items": items,
    }


def _save_transfer_schedule(plugin, pending_runs: dict) -> None:
    """保存当前延迟队列；持久化异常不能阻断事件处理。"""
    save_data = getattr(plugin, "save_data", None)
    if not callable(save_data):
        return
    try:
        save_data(TRANSFER_SCHEDULE_KEY, _serialize_transfer_schedule(pending_runs))
    except Exception as error:  # noqa: BLE001  # 由宿主存储实现决定
        logger.warning(f"保存延迟转种队列失败：{error}")


def _load_transfer_schedule(plugin) -> dict:
    """读取并清理延迟队列，保留已到期项目以便 reload 后立即接续。"""
    get_data = getattr(plugin, "get_data", None)
    if not callable(get_data):
        return {}
    try:
        payload = get_data(TRANSFER_SCHEDULE_KEY)
    except Exception as error:  # noqa: BLE001  # 由宿主存储实现决定
        logger.warning(f"读取延迟转种队列失败：{error}")
        return {}
    if not isinstance(payload, dict):
        return {}
    version = payload.get("schema_version")
    if version not in (None, TRANSFER_SCHEDULE_SCHEMA_VERSION):
        logger.warning(f"忽略未知延迟转种队列版本：{version}")
        return {}
    items = payload.get("items")
    if not isinstance(items, dict):
        return {}
    pending_runs = {}
    for event_key, raw_deadline in items.items():
        deadline = _parse_transfer_deadline(raw_deadline)
        if isinstance(event_key, str) and event_key and deadline is not None:
            pending_runs[event_key] = deadline
    normalized = _serialize_transfer_schedule(pending_runs)
    if payload != normalized:
        _save_transfer_schedule(plugin, pending_runs)
    return pending_runs


def restore_transfer_schedule(plugin):
    """在新生命周期中恢复持久化队列并登记最早到期任务。"""
    lock = getattr(plugin, "_transfer_schedule_lock", None)
    if lock is None:
        return None
    pending_runs = _load_transfer_schedule(plugin)
    with lock:
        generation = int(getattr(plugin, "_transfer_stop_generation", 0) or 0)
        if not _transfer_schedule_active(plugin, generation):
            return None
        for event_key, run_time in pending_runs.items():
            previous = plugin._transfer_pending_runs.get(event_key)
            plugin._transfer_pending_runs[event_key] = min(previous, run_time) if previous else run_time
        return _schedule_next_transfer(plugin, generation)


def _schedule_next_transfer(plugin, generation: int):
    """持有实例调度锁时，仅为最早到期项登记一个任务。"""
    if plugin._transfer_running_generation is not None or not plugin._transfer_pending_runs:
        return None
    run_time = min(plugin._transfer_pending_runs.values())
    previous = plugin._transfer_scheduled_run
    if previous is not None and previous <= run_time:
        return previous
    _ensure_scheduler(plugin)
    if previous is not None:
        try:
            plugin._scheduler.remove_job(_transfer_job_id(plugin, generation, previous))
        except JobLookupError:
            pass
    plugin._scheduler.add_job(
        _run_scheduled_transfer,
        "date",
        run_date=run_time,
        id=_transfer_job_id(plugin, generation, run_time),
        kwargs={"plugin": plugin, "generation": generation, "run_time": run_time},
        replace_existing=True,
        misfire_grace_time=None,
    )
    plugin._transfer_scheduled_run = run_time
    return run_time


def _run_scheduled_transfer(plugin, generation: int, run_time: datetime) -> None:
    """串行处理已到期批次，结束后继续登记尚未到期的事件。"""
    with plugin._transfer_schedule_lock:
        if not _transfer_schedule_active(plugin, generation) or plugin._transfer_scheduled_run != run_time:
            return
        plugin._transfer_scheduled_run = None
        plugin._transfer_running_generation = generation
        now = max(run_time, _transfer_now())
        plugin._transfer_pending_runs = {
            key: deadline for key, deadline in plugin._transfer_pending_runs.items()
            if deadline > now
        }
        _save_transfer_schedule(plugin, plugin._transfer_pending_runs)
    try:
        plugin._delayed_transfer()
    finally:
        with plugin._transfer_schedule_lock:
            if _transfer_schedule_active(plugin, generation):
                plugin._transfer_running_generation = None
                _schedule_next_transfer(plugin, generation)


def clear_transfer_schedule(plugin) -> None:
    """停止前保存当前延迟状态，再清空实例内存队列。"""
    lock = getattr(plugin, "_transfer_schedule_lock", None)
    if lock is None:
        return
    with lock:
        pending_runs = getattr(plugin, "_transfer_pending_runs", {})
        if pending_runs:
            _save_transfer_schedule(plugin, pending_runs)
        plugin._transfer_pending_runs.clear()
        plugin._transfer_scheduled_run = None
        plugin._transfer_running_generation = None


def handle_download_added_event(plugin, event) -> dict:
    """处理 DownloadAdded 事件、回收临时标签并唤醒监控 worker。"""
    cleanup_temporary_tags_for_event(plugin, event)
    result = create_speed_monitor_session(plugin, event)
    if isinstance(result, dict) and int(result.get("active_sessions") or 0) > 0:
        start_speed_monitor_worker(plugin)
    wake_upload_limit_worker(plugin)
    return result


def _coerce_delay_minutes(value) -> int:
    """按旧逻辑把延迟配置收敛为至少一分钟。"""
    return max(1, int(value or 25))


def _ensure_scheduler(plugin) -> None:
    """确保插件持有已启动的后台 scheduler。"""
    scheduler = plugin._scheduler
    if not scheduler:
        scheduler = BackgroundScheduler(timezone=settings.TZ)
        plugin._scheduler = scheduler
    if not scheduler.running:
        scheduler.start()


__all__ = (
    "clear_transfer_schedule",
    "handle_download_added_event",
    "handle_transfer_complete_event",
    "restore_transfer_schedule",
)
