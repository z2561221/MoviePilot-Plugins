"""种子重命名 legacy 兼容 shim，业务实现位于 service.rename。"""

from ..service.rename import (
    format_torrent_name,
    get_failed_rename_hashes,
    rename_iyuu_torrent_by_source_record,
    rename_torrent,
    retry_failed_renames,
    retry_rename_by_hash,
    save_rename_record,
)

__all__ = (
    "format_torrent_name",
    "get_failed_rename_hashes",
    "rename_iyuu_torrent_by_source_record",
    "rename_torrent",
    "retry_failed_renames",
    "retry_rename_by_hash",
    "save_rename_record",
)
