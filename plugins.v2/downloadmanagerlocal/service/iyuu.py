"""IYUU 辅种服务边界，兼容委托到 legacy modules 实现。"""

from ..modules.iyuu import (
    append_iyuu_cache,
    custom_sites,
    iyuu_auto_seed,
    iyuu_auto_service_info,
    iyuu_download,
    iyuu_download_torrent,
    iyuu_get_download_url,
    iyuu_save_history,
    iyuu_seed_torrents,
    iyuu_service_infos,
    trim_seed_cache,
    update_iyuu_config,
)

__all__ = (
    "append_iyuu_cache",
    "custom_sites",
    "iyuu_auto_seed",
    "iyuu_auto_service_info",
    "iyuu_download",
    "iyuu_download_torrent",
    "iyuu_get_download_url",
    "iyuu_save_history",
    "iyuu_seed_torrents",
    "iyuu_service_infos",
    "trim_seed_cache",
    "update_iyuu_config",
)
