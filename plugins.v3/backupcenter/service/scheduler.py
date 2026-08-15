"""备份中心自动任务服务。"""

import re
from typing import Any, Dict, List

from apscheduler.triggers.cron import CronTrigger
from app.sdk.logging import logger


_WEEKDAY_ALIASES = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}


def _weekday_number(value: str) -> int:
    """将标准 Cron 星期值转换为星期日从零开始的数字。"""
    normalized = str(value).strip().lower()
    if normalized in _WEEKDAY_ALIASES:
        return _WEEKDAY_ALIASES[normalized]
    if not re.fullmatch(r"[0-7]", normalized):
        raise ValueError(f"无效星期值：{value}")
    number = int(normalized)
    return 0 if number == 7 else number


def _standard_weekday_values(field: str) -> List[int]:
    """展开标准 Cron 星期字段，支持列表、范围与步长。"""
    selected = set()
    for segment in str(field).split(","):
        token = segment.strip()
        if not token:
            raise ValueError("星期字段包含空值")
        base, separator, step_text = token.partition("/")
        step = int(step_text) if separator else 1
        if step < 1:
            raise ValueError("星期步长必须大于零")
        if base == "*":
            values = list(range(7))
        elif "-" in base:
            start_text, end_text = base.split("-", 1)
            start = _weekday_number(start_text)
            end = _weekday_number(end_text)
            values = (
                list(range(start, end + 1))
                if start <= end
                else list(range(start, 7)) + list(range(0, end + 1))
            )
        else:
            if separator:
                raise ValueError("单个星期值不能设置步长")
            values = [_weekday_number(base)]
        selected.update(values[::step])
    return sorted(selected)


def _to_apscheduler_crontab(expression: str) -> str:
    """把标准 Cron 的周日零制转换为 APScheduler 的周一零制。"""
    fields = str(expression or "").split()
    if len(fields) != 5:
        raise ValueError("Cron 表达式必须包含五段")
    weekday_field = fields[4]
    if weekday_field == "*":
        return " ".join(fields)
    standard_values = _standard_weekday_values(weekday_field)
    apscheduler_values = sorted({(value - 1) % 7 for value in standard_values})
    fields[4] = "*" if len(apscheduler_values) == 7 else ",".join(
        str(value) for value in apscheduler_values
    )
    return " ".join(fields)


def build_services(plugin) -> List[Dict[str, Any]]:
    """返回按标准五段 Cron 配置执行的自动备份服务。"""
    if not plugin.get_state() or not plugin._config.get("auto_backup_enabled"):
        return []
    cron = str(plugin._config.get("auto_backup_cron") or "0 3 * * 6").strip()
    try:
        trigger = CronTrigger.from_crontab(_to_apscheduler_crontab(cron))
    except Exception as error:
        logger.warning(
            f"备份中心：自动备份 Cron 配置无效，已跳过定时服务：{cron}，错误：{error}"
        )
        return []
    return [
        {
            "id": "BackupCenter.AutomaticBackup",
            "name": "备份中心自动备份",
            "trigger": trigger,
            "func": plugin.run_automatic_backup,
            "kwargs": {},
        }
    ]
