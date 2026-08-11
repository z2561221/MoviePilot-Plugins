"""上传限速领域模型与版本化状态结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


UPLOAD_LIMIT_SCHEMA_VERSION = 1
UPLOAD_LIMIT_INTERVAL_SECONDS = 30
UPLOAD_LIMIT_FAILURE_NOTIFY_THRESHOLD = 3

DEFAULT_SITE_KEY = "__default__"
DEFAULT_SITE_NAME = "默认组"

PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"
PRIORITY_WEIGHTS = {
    PRIORITY_HIGH: 4,
    PRIORITY_MEDIUM: 2,
    PRIORITY_LOW: 1,
}


@dataclass(frozen=True)
class GlobalUploadSettings:
    """下载器全局上传限速快照，数值单位为 B/s。"""

    downloader_type: str
    upload_limit_bps: int
    upload_enabled: bool
    alternate_upload_limit_bps: Optional[int] = None
    alternate_upload_enabled: Optional[bool] = None


@dataclass(frozen=True)
class TorrentUploadSettings:
    """单种上传限速快照，数值单位为 B/s。"""

    limit_bps: int
    enabled: bool


@dataclass(frozen=True)
class UploadTorrentSnapshot:
    """下载器无关的已完成任务上传快照。"""

    downloader_id: str
    downloader_type: str
    torrent_hash: str
    name: str
    labels: tuple[str, ...]
    state: str
    completed: bool
    added_at: float
    completed_at: float
    upload_rate_bps: int
    upload_settings: TorrentUploadSettings

    @property
    def key(self) -> str:
        """返回跨下载器唯一的任务状态键。"""
        return torrent_state_key(self.downloader_id, self.torrent_hash)


@dataclass(frozen=True)
class UploadPool:
    """同一下载器内按站点聚合的待分配做种池。"""

    key: str
    downloader_id: str
    site_key: str
    priority: str
    task_keys: tuple[str, ...]
    current_rate_bps: int
    demand_kib: Optional[int]

    @property
    def weight(self) -> int:
        """返回优先级对应的稳定整数权重。"""
        return PRIORITY_WEIGHTS[normalize_priority(self.priority)]


def normalize_priority(value: Any) -> str:
    """把任意优先级值收敛为 high、medium 或 low。"""
    normalized = str(value or "").strip().lower()
    return normalized if normalized in PRIORITY_WEIGHTS else PRIORITY_MEDIUM


def torrent_state_key(downloader_id: str, torrent_hash: str) -> str:
    """构造跨下载器唯一的任务状态键。"""
    return f"{str(downloader_id or '').strip()}:{str(torrent_hash or '').strip().lower()}"


def pool_state_key(downloader_id: str, site_key: str) -> str:
    """构造下载器与站点组合的分配池键。"""
    return f"{str(downloader_id or '').strip()}\0{str(site_key or DEFAULT_SITE_KEY).strip()}"


def empty_upload_limit_state() -> dict:
    """返回当前 schema 的空上传限速运行态。"""
    return {
        "schema_version": UPLOAD_LIMIT_SCHEMA_VERSION,
        "management_active": False,
        "activated_at": 0.0,
        "cycle": 0,
        "last_run_at": 0.0,
        "downloaders": {},
        "torrents": {},
        "failures": {},
        "last_summary": {},
    }


def migrate_upload_limit_state(value: Any) -> dict:
    """把缺失版本或旧版上传限速状态迁移到当前 schema。"""
    if value in (None, {}):
        return empty_upload_limit_state()
    if not isinstance(value, dict):
        raise ValueError("upload limit state must be a dict")
    version = value.get("schema_version")
    if version not in {None, 0, UPLOAD_LIMIT_SCHEMA_VERSION}:
        raise ValueError(f"unsupported upload limit schema version: {version}")
    result = empty_upload_limit_state()
    result.update({
        "management_active": bool(value.get("management_active", False)),
        "activated_at": _number(value.get("activated_at")),
        "cycle": _integer(value.get("cycle")),
        "last_run_at": _number(value.get("last_run_at")),
        "downloaders": _dict(value.get("downloaders")),
        "torrents": _dict(value.get("torrents")),
        "failures": _dict(value.get("failures")),
        "last_summary": _dict(value.get("last_summary")),
    })
    return result


def _dict(value: Any) -> dict:
    """把非字典持久化字段安全回退为空字典。"""
    return dict(value) if isinstance(value, dict) else {}


def _number(value: Any) -> float:
    """把持久化数值安全转换为非负浮点数。"""
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _integer(value: Any) -> int:
    """把持久化数值安全转换为非负整数。"""
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


__all__ = (
    "DEFAULT_SITE_KEY",
    "DEFAULT_SITE_NAME",
    "GlobalUploadSettings",
    "PRIORITY_HIGH",
    "PRIORITY_LOW",
    "PRIORITY_MEDIUM",
    "PRIORITY_WEIGHTS",
    "TorrentUploadSettings",
    "UPLOAD_LIMIT_FAILURE_NOTIFY_THRESHOLD",
    "UPLOAD_LIMIT_INTERVAL_SECONDS",
    "UPLOAD_LIMIT_SCHEMA_VERSION",
    "UploadPool",
    "UploadTorrentSnapshot",
    "empty_upload_limit_state",
    "migrate_upload_limit_state",
    "normalize_priority",
    "pool_state_key",
    "torrent_state_key",
)
