"""重命名归档 legacy 兼容 shim，业务实现位于 service.archive。"""

from ..service.archive import (
    clear_rename_retry_state,
    delete_rename_archive,
    is_rename_archived,
    list_rename_archive,
    record_rename_failure,
    rename_archive_stats,
    restore_rename_archive,
)

__all__ = (
    "clear_rename_retry_state",
    "delete_rename_archive",
    "is_rename_archived",
    "list_rename_archive",
    "record_rename_failure",
    "rename_archive_stats",
    "restore_rename_archive",
)
