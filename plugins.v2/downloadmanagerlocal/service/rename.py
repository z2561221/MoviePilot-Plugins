"""重命名服务边界，兼容委托到 legacy modules 实现。"""

from ..modules.rename import (
    format_torrent_name,
    get_failed_rename_hashes,
    rename_iyuu_torrent_by_source_record,
    rename_torrent,
    retry_failed_renames,
    retry_rename_by_hash,
    save_rename_record,
)

