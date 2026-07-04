"""下载中心插件生命周期初始化服务。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.log import logger
from app.plugins.downloadmanagerlocal.iyuu_helper import IyuuHelper

from .config import initialize_runtime_config
from .transfer import validate_config


def initialize_plugin(plugin, config: dict = None) -> None:
    """初始化插件运行时配置，并按当前配置登记一次性后台任务。"""
    config = initialize_runtime_config(plugin, config)
    plugin.stop_service()

    if plugin._transfer_active or plugin._onlyonce:
        if not validate_config(plugin):
            _disable_invalid_transfer_config(plugin, config)
            return

        plugin._scheduler = BackgroundScheduler(timezone=settings.TZ)
        _schedule_transfer_once(plugin, config)
        _start_scheduler_if_needed(plugin, print_jobs=True)

    if plugin._iyuu_enabled and plugin._iyuu_token and plugin._iyuu_downloaders:
        plugin.iyuu_helper = IyuuHelper(token=plugin._iyuu_token)
        if not plugin._scheduler:
            plugin._scheduler = BackgroundScheduler(timezone=settings.TZ)

        _schedule_iyuu_once(plugin, config)
        _start_scheduler_if_needed(plugin)


def _disable_invalid_transfer_config(plugin, config: dict) -> None:
    """在转移配置无效时按旧逻辑关闭转移开关并持久化。"""
    plugin._enabled = False
    plugin._onlyonce = False
    config["enabled"] = plugin._enabled
    config["onlyonce"] = plugin._onlyonce
    plugin.update_config(config=config)


def _schedule_transfer_once(plugin, config: dict) -> None:
    """根据 onlyonce 配置登记立即执行一次的转移做种任务。"""
    if not plugin._onlyonce:
        return
    logger.info("转移做种服务启动，立即运行一次")
    plugin._scheduler.add_job(
        plugin.transfer,
        "date",
        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
    )
    plugin._onlyonce = False
    config["onlyonce"] = plugin._onlyonce
    plugin.update_config(config=config)


def _schedule_iyuu_once(plugin, config: dict) -> None:
    """根据 iyuu_onlyonce 配置登记立即执行一次的 IYUU 辅种任务。"""
    if not plugin._iyuu_onlyonce:
        return
    logger.info("IYUU辅种服务启动，立即运行一次")
    plugin._scheduler.add_job(
        plugin.iyuu_auto_seed,
        "date",
        run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=5),
    )
    plugin._iyuu_onlyonce = False
    config["iyuu_onlyonce"] = plugin._iyuu_onlyonce
    plugin.update_config(config=config)


def _start_scheduler_if_needed(plugin, print_jobs: bool = False) -> None:
    """在 scheduler 已有任务且尚未运行时启动后台调度器。"""
    if not plugin._scheduler.get_jobs():
        return
    if print_jobs:
        plugin._scheduler.print_jobs()
    if not plugin._scheduler.running:
        plugin._scheduler.start()


__all__ = ("initialize_plugin",)
