"""下载中心事件服务，承载入口层以外的事件调度逻辑。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.log import logger


def handle_transfer_complete_event(plugin, event) -> None:
    """处理 TransferComplete 事件并登记延迟转移做种任务。"""
    if not plugin._transfer_active:
        return

    event_data = event.event_data or {}
    downloader_name = event_data.get("downloader") or event_data.get("downloader_name", "")
    if downloader_name and downloader_name != plugin._fromdownloader:
        return

    delay = _coerce_delay_minutes(plugin._delay_minutes)
    logger.info(f"收到 TransferComplete 事件（来源: {downloader_name}），将在 {delay} 分钟后执行转移做种")

    _ensure_scheduler(plugin)
    run_time = datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(minutes=delay)
    job_id = f"delayed_transfer_{plugin._fromdownloader or 'default'}"
    plugin._scheduler.add_job(
        plugin._delayed_transfer,
        "date",
        run_date=run_time,
        id=job_id,
        replace_existing=True,
    )


def _coerce_delay_minutes(value) -> int:
    """按旧逻辑把延迟配置收敛为至少一分钟。"""
    return max(1, int(value or 25))


def _ensure_scheduler(plugin) -> None:
    """确保插件持有已启动的后台 scheduler。"""
    if plugin._scheduler:
        return
    plugin._scheduler = BackgroundScheduler(timezone=settings.TZ)
    plugin._scheduler.start()


__all__ = ("handle_transfer_complete_event",)
