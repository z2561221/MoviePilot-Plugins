"""备份中心运行日志服务。"""

from __future__ import annotations

import re
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, TypeVar

from app.sdk.logging import logger


ResultT = TypeVar("ResultT")


class OperationLogService:
    """持久化脱敏后的备份操作结果并同步写入宿主日志。"""

    _data_key = "operation_logs"
    _limit = 200
    _operation_labels = {
        "automatic_backup": "自动备份",
        "manual_backup": "手动备份",
        "verify_backup": "备份校验",
        "delete_backup": "删除备份",
        "restore_logical": "在线恢复",
    }
    _secret_pattern = re.compile(
        r"(?i)\b(password|token|secret|api[_-]?key|credential|pgpassword)\b\s*[:=]\s*[^\s,，;；]+"
    )
    _path_pattern = re.compile(
        r"(?i)(?:[a-z]:[\\/]|\\\\|/(?:app|config|data|docker|home|mnt|opt|root|tmp|var|vol\d*)/)"
        r"[^\s,，;；]*"
    )

    def __init__(self, plugin: Any) -> None:
        """绑定运行中的备份中心插件实例。"""
        self.plugin = plugin
        self._lock = threading.RLock()

    @classmethod
    def sanitize_message(cls, value: Any) -> str:
        """移除错误消息中的秘密、绝对路径和多余空白。"""
        message = " ".join(str(value or "").split())
        message = cls._secret_pattern.sub(lambda match: f"{match.group(1)}=<已隐藏>", message)
        message = cls._path_pattern.sub("<路径>", message)
        return (message or "未提供错误说明")[:240]

    @classmethod
    def _operation_label(cls, operation: str) -> str:
        """返回固定操作标识对应的中文名称。"""
        return cls._operation_labels.get(operation, "备份中心操作")

    @staticmethod
    def _extract_backup_id(result: Any) -> str | None:
        """从常见业务响应中提取可公开展示的备份 ID。"""
        if not isinstance(result, dict):
            return None
        for key in ("backup_id", "emergency_backup_id"):
            value = result.get(key)
            if value:
                return str(value)
        backup = result.get("backup")
        if isinstance(backup, dict) and backup.get("backup_id"):
            return str(backup["backup_id"])
        manifest = result.get("manifest")
        if isinstance(manifest, dict) and manifest.get("backup_id"):
            return str(manifest["backup_id"])
        return None

    @classmethod
    def _extract_input_backup_id(
        cls, args: tuple[Any, ...], kwargs: Dict[str, Any]
    ) -> str | None:
        """从操作参数或请求模型中提取关联备份 ID。"""
        candidates = [*args, *kwargs.values()]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate:
                return candidate
            if isinstance(candidate, dict) and candidate.get("backup_id"):
                return str(candidate["backup_id"])
            value = getattr(candidate, "backup_id", None)
            if value:
                return str(value)
        return None

    @classmethod
    def _normalize_record(cls, item: Any) -> Dict[str, Any] | None:
        """清洗一条持久化记录并跳过结构损坏的数据。"""
        if not isinstance(item, dict):
            return None
        required = ("log_id", "operation", "status", "started_at", "finished_at")
        if any(not item.get(key) for key in required):
            return None
        operation = str(item["operation"])
        status = str(item["status"])
        if operation not in cls._operation_labels or status not in {"success", "failure"}:
            return None
        try:
            duration_ms = max(0, int(item.get("duration_ms") or 0))
        except (TypeError, ValueError):
            return None
        backup_id = item.get("backup_id")
        return {
            "log_id": str(item["log_id"])[:80],
            "operation": operation,
            "status": status,
            "started_at": str(item["started_at"])[:64],
            "finished_at": str(item["finished_at"])[:64],
            "duration_ms": duration_ms,
            "backup_id": cls.sanitize_message(backup_id)[:120] if backup_id else None,
            "message": cls.sanitize_message(item.get("message")),
        }

    def list_logs(self) -> List[Dict[str, Any]]:
        """返回按完成时间倒序排列的最近运行日志。"""
        with self._lock:
            raw = self.plugin.get_data(self._data_key) or []
            if not isinstance(raw, list):
                return []
            records = [self._normalize_record(item) for item in raw]
            valid_records = [item for item in records if item is not None]
            valid_records.sort(
                key=lambda item: str(item.get("finished_at") or ""), reverse=True
            )
            return valid_records[: self._limit]

    def _save_record(self, record: Dict[str, Any]) -> None:
        """保存单条运行记录且不让日志写入失败中断业务操作。"""
        try:
            with self._lock:
                existing = self.list_logs()
                existing.insert(0, record)
                self.plugin.save_data(self._data_key, existing[: self._limit])
        except Exception as error:
            logger.warning(
                f"备份中心运行日志保存失败：{self.sanitize_message(error)}"
            )

    @staticmethod
    def _write_host_log(record: Dict[str, Any]) -> None:
        """将结构化摘要同步写入 MoviePilot 主日志。"""
        line = (
            "备份中心运行记录："
            f"operation={record['operation']} "
            f"status={record['status']} "
            f"duration_ms={record['duration_ms']} "
            f"backup_id={record.get('backup_id') or '-'} "
            f"message={record['message']}"
        )
        if record["status"] == "failure":
            logger.error(line)
        else:
            logger.info(line)

    def record(
        self,
        operation: str,
        status: str,
        started_at: datetime,
        duration_ms: int,
        message: Any,
        backup_id: Any = None,
    ) -> Dict[str, Any]:
        """生成、持久化并输出一条脱敏运行记录。"""
        finished_at = datetime.now(timezone.utc)
        record = {
            "log_id": f"log-{finished_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}",
            "operation": str(operation),
            "status": str(status),
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_ms": max(0, int(duration_ms)),
            "backup_id": self.sanitize_message(backup_id)[:120] if backup_id else None,
            "message": self.sanitize_message(message),
        }
        self._save_record(record)
        try:
            self._write_host_log(record)
        except Exception as error:
            logger.warning(
                f"备份中心宿主日志写入失败：{self.sanitize_message(error)}"
            )
        return record

    def execute(
        self,
        operation: str,
        callback: Callable[..., ResultT],
        *args: Any,
        **kwargs: Any,
    ) -> ResultT:
        """执行操作并记录成功、失败、耗时和关联备份 ID。"""
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        input_backup_id = self._extract_input_backup_id(args, kwargs)
        try:
            result = callback(*args, **kwargs)
        except Exception as error:
            self.record(
                operation=operation,
                status="failure",
                started_at=started_at,
                duration_ms=round((time.perf_counter() - started) * 1000),
                backup_id=input_backup_id,
                message=error,
            )
            raise
        backup_id = input_backup_id or self._extract_backup_id(result)
        message = f"{self._operation_label(operation)}完成"
        emergency_backup_id = (
            result.get("emergency_backup_id")
            if isinstance(result, dict)
            else None
        )
        if emergency_backup_id:
            message = (
                f"{message}，应急备份 {self.sanitize_message(emergency_backup_id)}"
            )
        self.record(
            operation=operation,
            status="success",
            started_at=started_at,
            duration_ms=round((time.perf_counter() - started) * 1000),
            backup_id=backup_id,
            message=message,
        )
        return result
