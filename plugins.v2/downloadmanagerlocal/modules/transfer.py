"""转移做种 legacy 兼容 shim，业务实现位于 service.transfer。"""

from ..service.transfer import (
    delayed_transfer,
    download_torrent,
    fallback_transfer,
    post_transfer_process,
    retry_pending_renames,
    transfer,
    validate_config,
)

__all__ = (
    "delayed_transfer",
    "download_torrent",
    "fallback_transfer",
    "post_transfer_process",
    "retry_pending_renames",
    "transfer",
    "validate_config",
)
