"""单轮下载器扫描结果，不属于持久化配置或数据库状态。"""

from dataclasses import dataclass
from typing import Any

from .upload_limit import UploadTorrentSnapshot


@dataclass(frozen=True)
class UploadDownloaderContext:
    """明确扫描边界内的服务、下载器类型和两组任务快照。"""

    downloader_id: str
    service: Any
    downloader_type: str
    all_snapshots: dict[str, UploadTorrentSnapshot]
    snapshots: dict[str, UploadTorrentSnapshot]
    initial_scan_pending: bool
