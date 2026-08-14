"""下载器种子字段适配工具（qBittorrent / Transmission 兼容）。"""

from dataclasses import dataclass
from typing import Any, List


TORRENT_ACTIVE = "active"
TORRENT_PAUSED = "paused"
TORRENT_QUEUED = "queued"
TORRENT_CHECKING = "checking"
TORRENT_COMPLETED = "completed"
TORRENT_ERROR = "error"


@dataclass(frozen=True)
class TorrentSnapshot:
    """下载器无关的种子采样快照。"""

    downloader_id: str
    downloader_type: str
    torrent_hash: str
    name: str
    total_bytes: int
    downloaded_bytes: int
    added_at: float
    state: str
    state_category: str
    save_path: str
    download_speed_bps: float


@dataclass(frozen=True)
class DownloaderPollResult:
    """区分成功结果、成功空列表与下载器错误的轮询结果。"""

    success: bool
    items: tuple[TorrentSnapshot, ...] = ()
    error: str = ""


def poll_success(items: List[TorrentSnapshot] | tuple[TorrentSnapshot, ...]) -> DownloaderPollResult:
    """构造成功轮询结果，允许显式表示成功空列表。"""
    return DownloaderPollResult(success=True, items=tuple(items), error="")


def poll_error(cause: Any) -> DownloaderPollResult:
    """构造下载器轮询失败结果。"""
    return DownloaderPollResult(success=False, items=(), error=str(cause or "unknown error"))


def _read(torrent: Any, *names: str, default: Any = None) -> Any:
    """兼容字典、snake_case 对象与 camelCase 对象读取字段。"""
    for name in names:
        if isinstance(torrent, dict) and name in torrent:
            return torrent.get(name)
        if hasattr(torrent, name):
            return getattr(torrent, name)
    return default


def _number(value: Any, default: float = 0) -> float:
    """将下载器数值字段安全转换为非负浮点数。"""
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return float(default)


def _timestamp(value: Any) -> float:
    """将时间戳或 datetime 风格对象转换为 Unix 秒。"""
    if hasattr(value, "timestamp"):
        try:
            return _number(value.timestamp())
        except (TypeError, ValueError, OSError):
            return 0.0
    return _number(value)


def classify_torrent_state(state: Any, downloaded_bytes: int, total_bytes: int) -> str:
    """把 qBittorrent/Transmission 状态归一为监控状态类别。"""
    raw_state = getattr(state, "name", None) or getattr(state, "value", None) or state or ""
    normalized = str(raw_state).replace("_", "").replace(" ", "").lower()

    if total_bytes > 0 and downloaded_bytes >= total_bytes:
        return TORRENT_COMPLETED
    if normalized in {
        "uploading", "forcedup", "stalledup", "seeding", "completed",
    }:
        return TORRENT_COMPLETED
    if normalized in {
        "pauseddl", "pausedup", "stoppeddl", "stoppedup", "stopped", "paused",
    }:
        return TORRENT_PAUSED
    if normalized in {
        "queueddl", "queuedup", "downloadpending", "seedpending", "queued",
    }:
        return TORRENT_QUEUED
    if normalized in {
        "checkingdl", "checkingup", "checkingresumedata", "checkpending", "checking",
    }:
        return TORRENT_CHECKING
    if normalized in {"error", "missingfiles", "unknown", "isolated"}:
        return TORRENT_ERROR
    return TORRENT_ACTIVE


def normalize_torrent(torrent: Any, downloader_id: str, downloader_type: str) -> TorrentSnapshot:
    """将 qBittorrent 字典或 Transmission 对象归一为快照。"""
    torrent_hash = _read(torrent, "hash", "hashString", "hash_string", default="")
    name = _read(torrent, "name", default="")
    total_bytes = int(_number(_read(
        torrent, "total_size", "size", "totalSize", default=0,
    )))
    downloaded_bytes = int(_number(_read(
        torrent, "downloaded", "downloaded_ever", "downloadedEver", default=0,
    )))
    added_at = _timestamp(_read(
        torrent, "added_on", "added_date", "date_added", "dateAdded", default=0,
    ))
    state = _read(torrent, "state", "status", default="")
    state_text = str(getattr(state, "name", None) or getattr(state, "value", None) or state or "")
    save_path = _read(torrent, "save_path", "download_dir", "downloadDir", default="")
    speed = _number(_read(
        torrent, "dlspeed", "download_speed", "rate_download", "rateDownload", default=0,
    ))
    return TorrentSnapshot(
        downloader_id=str(downloader_id or ""),
        downloader_type=str(downloader_type or "").lower(),
        torrent_hash=str(torrent_hash or "").lower(),
        name=str(name or ""),
        total_bytes=total_bytes,
        downloaded_bytes=min(downloaded_bytes, total_bytes) if total_bytes else downloaded_bytes,
        added_at=added_at,
        state=state_text,
        state_category=classify_torrent_state(state, downloaded_bytes, total_bytes),
        save_path=str(save_path or ""),
        download_speed_bps=speed,
    )


def poll_downloader(instance: Any, downloader_id: str, downloader_type: str) -> DownloaderPollResult:
    """读取并归一化下载器任务，保留成功空列表与错误的差异。"""
    try:
        response = instance.get_torrents()
    except Exception as error:
        return poll_error(error)

    items = response
    cause = None
    if isinstance(response, tuple) and len(response) == 2:
        items, cause = response
    if cause:
        return poll_error(cause)
    if items is None:
        return poll_error("downloader returned no result")
    try:
        return poll_success([
            normalize_torrent(item, downloader_id, downloader_type)
            for item in items
        ])
    except (TypeError, ValueError) as error:
        return poll_error(error)


def delete_torrent_with_files(
    instance: Any,
    torrent_hash: str,
    *,
    delete_file: bool,
) -> Any:
    """仅在调用方显式确认时删除种子及该种子的全部数据。"""
    if delete_file is not True:
        raise ValueError("删除种子及全部数据必须显式传入 delete_file=True")
    if not torrent_hash:
        raise ValueError("删除种子及全部数据需要有效 hash")
    return instance.delete_torrents(ids=[torrent_hash], delete_file=True)


def get_hash(torrent: Any, dl_type: str) -> str:
    """获取种子 hash。"""
    if dl_type == "qbittorrent":
        return torrent.get("hash", "")
    return _read(torrent, "hashString", "hash_string", default="")


def _split_labels(labels: Any) -> List[str]:
    """将下载器返回的标签字段统一拆分为字符串列表。"""
    if not labels:
        return []
    if isinstance(labels, str):
        return [str(label).strip() for label in labels.split(",") if str(label).strip()]
    if isinstance(labels, (list, tuple, set)):
        return [str(label).strip() for label in labels if str(label).strip()]
    return []


def get_label(torrent: Any, dl_type: str) -> List[str]:
    """获取种子标签/分类。"""
    if dl_type == "qbittorrent":
        return _split_labels(torrent.get("tags"))
    return _split_labels(_read(torrent, "labels", default=[]))


def get_category(torrent: Any, dl_type: str) -> str:
    """获取种子分类（qB category / TR group）。"""
    if dl_type == "qbittorrent":
        return torrent.get("category", "")
    return _read(torrent, "group", default="") or ""


def get_save_path(torrent: Any, dl_type: str) -> str:
    """获取种子保存路径。"""
    if dl_type == "qbittorrent":
        return torrent.get("save_path", "")
    return _read(torrent, "download_dir", "downloadDir", default="")


def get_torrent_size(torrent: Any, dl_type: str) -> int:
    """获取种子总大小（字节）。"""
    if dl_type == "qbittorrent":
        return torrent.get("size", 0) or torrent.get("total_size", 0) or 0
    return int(_number(_read(torrent, "total_size", "totalSize", default=0)))
