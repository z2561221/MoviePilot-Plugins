"""下载器种子字段适配工具（qBittorrent / Transmission 兼容）"""

from typing import Any


def get_hash(torrent: Any, dl_type: str) -> str:
    """获取种子 hash。"""
    if dl_type == "qbittorrent":
        return torrent.get("hash", "")
    return torrent.hashString


def get_label(torrent: Any, dl_type: str) -> str:
    """获取种子标签/分类。"""
    if dl_type == "qbittorrent":
        return torrent.get("category", "")
    return torrent.labels or ""


def get_category(torrent: Any, dl_type: str) -> str:
    """获取种子分类（qB category / TR group）。"""
    if dl_type == "qbittorrent":
        return torrent.get("category", "")
    return torrent.group or ""


def get_save_path(torrent: Any, dl_type: str) -> str:
    """获取种子保存路径。"""
    if dl_type == "qbittorrent":
        return torrent.get("save_path", "")
    return torrent.download_dir


def get_torrent_size(torrent: Any, dl_type: str) -> int:
    """获取种子总大小（字节）。"""
    if dl_type == "qbittorrent":
        return torrent.get("size", 0) or torrent.get("total_size", 0) or 0
    return torrent.total_size or 0
