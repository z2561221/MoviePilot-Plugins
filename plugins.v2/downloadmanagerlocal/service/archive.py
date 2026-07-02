"""补刀归档服务边界，兼容委托到 legacy modules 实现。"""

from ..modules.rename_archive import (
    clear_rename_retry_state,
    delete_rename_archive,
    is_rename_archived,
    list_rename_archive,
    record_rename_failure,
    rename_archive_stats,
    restore_rename_archive,
)

