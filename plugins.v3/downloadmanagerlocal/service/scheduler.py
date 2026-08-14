"""下载中心调度服务注册构造。"""

from typing import Any, Dict, List

from apscheduler.triggers.cron import CronTrigger


def build_plugin_services(plugin) -> List[Dict[str, Any]]:
    """根据插件运行状态构造 MoviePilot 调度服务声明。"""
    services = []

    if plugin._transfer_active and plugin._transfer_fallback_enabled:
        services.append({
            "id": "TorrentTransferFallback",
            "name": "转移做种兜底服务",
            "trigger": "interval",
            "func": plugin._fallback_transfer,
            "kwargs": {"minutes": plugin._transfer_fallback_interval_minutes}
        })

    if plugin._iyuu_enabled and plugin._iyuu_cron and plugin._iyuu_token and plugin._iyuu_downloaders:
        services.append({
            "id": "IYUUAutoSeed",
            "name": "IYUU自动辅种服务",
            "trigger": CronTrigger.from_crontab(plugin._iyuu_cron),
            "func": plugin.iyuu_auto_seed,
            "kwargs": {}
        })

    return services
