"""Scheduler service helpers for DoubanCenter."""

from typing import Any, Callable, Dict, List

from apscheduler.triggers.cron import CronTrigger

from app.log import logger


def get_services(plugin, run_all: Callable[[], None]) -> List[Dict[str, Any]]:
    """Return scheduled services declared by the plugin."""
    if plugin._enabled and plugin._cron:
        return [
            {
                "id": "DoubanCenter",
                "name": "豆瓣中心定时服务",
                "trigger": CronTrigger.from_crontab(plugin._cron),
                "func": run_all,
                "kwargs": {},
            }
        ]
    return []


def stop_scheduler(plugin) -> None:
    """Stop plugin-owned scheduler instance if one exists."""
    try:
        if plugin._scheduler:
            plugin._scheduler.remove_all_jobs()
            if plugin._scheduler.running:
                plugin._scheduler.shutdown()
            plugin._scheduler = None
    except Exception as err:
        logger.error(str(err))
