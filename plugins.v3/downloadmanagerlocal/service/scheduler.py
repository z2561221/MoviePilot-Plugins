"""下载中心调度服务注册构造。"""

from typing import Any, Dict, List

from apscheduler.triggers.cron import CronTrigger
from app.sdk.logging import logger

from .auto_delete import service_declaration
from ..utils.config import is_iyuu_active


def build_plugin_services(plugin) -> List[Dict[str, Any]]:
    """根据插件运行状态构造 MoviePilot 调度服务声明。"""
    services = service_declaration(plugin)
    plugin._iyuu_schedule_error = ""

    if plugin._transfer_active and plugin._transfer_fallback_enabled:
        services.append({
            "id": "TorrentTransferFallback",
            "name": "转移做种兜底服务",
            "trigger": "interval",
            "func": plugin._fallback_transfer,
            "kwargs": {"minutes": plugin._transfer_fallback_interval_minutes}
        })

    if is_iyuu_active(plugin) and plugin._iyuu_cron:
        try:
            if not isinstance(plugin._iyuu_cron, str):
                raise TypeError("周期不是文本")
            trigger = CronTrigger.from_crontab(plugin._iyuu_cron)
        except (ValueError, TypeError):
            plugin._iyuu_schedule_error = "IYUU 执行周期无效，请检查五段 Cron；其他模块保持运行"
            logger.warning(plugin._iyuu_schedule_error)
            return services
        services.append({
            "id": "IYUUAutoSeed",
            "name": "IYUU铺种服务",
            "trigger": trigger,
            "func": plugin.iyuu_auto_seed,
            "kwargs": {}
        })

    return services
