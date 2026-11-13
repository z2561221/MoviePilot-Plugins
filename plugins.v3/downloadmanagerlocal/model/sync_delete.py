"""同步删除配置、路径范围与事件快照；本模块不访问外部服务。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import PurePosixPath

DEFAULTS = {
    "sync_delete_enabled": False,
    "sync_delete_servers": [],
    "sync_delete_local_paths": "",
    "sync_delete_cloud_paths": "",
    "sync_delete_storage": "115网盘Plus",
    "sync_delete_source_paths": "",
    "sync_delete_exclude_paths": "",
    "sync_delete_source": True,
    "sync_delete_torrents": True,
    "sync_delete_cloud": True,
    "sync_delete_records": True,
    "sync_delete_force_cloud": False,
    "sync_delete_notify": True,
    "sync_delete_library_deleted": False,
}
JOBS_KEY = "sync_delete_jobs"
BLOCKS_KEY = "sync_delete_blocks"
MAX_TARGETS = 5000
MAX_JOBS = 1000
MAX_PENDING = 100
PLAN_VERSION = 3
TERMINAL_STATES = {"completed", "skipped"}
MEDIA_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".mov", ".wmv", ".iso",
    ".mpg", ".mpeg", ".flv", ".webm", ".m4v", ".rmvb", ".strm",
}
SIDECAR_EXTENSIONS = {".srt", ".ass", ".ssa", ".sub", ".idx", ".nfo"}


class DeleteRejected(ValueError):
    """无法确认删除范围或目标身份，保持原对象供用户核对。"""


def text(value) -> str:
    """规范化可选字符串，兼容媒体来源枚举。"""
    return str(getattr(value, "value", value) or "").strip()


def path_text(value) -> str:
    """规范化容器绝对路径，拒绝相对路径、URI、越界段与控制字符。"""
    raw = text(value).replace("\\", "/")
    if not raw.startswith("/") or raw.startswith("//") or any(ord(c) < 32 for c in raw):
        raise DeleteRejected("必须填写有效的容器绝对路径")
    if ".." in raw.split("/"):
        raise DeleteRejected("路径包含越界段")
    return str(PurePosixPath(raw))


def within(path: str, root: str, *, strict: bool = False) -> bool:
    """按目录边界比较路径，strm 与 strm-9kg 不互相命中。"""
    left, right = PurePosixPath(path), PurePosixPath(root)
    return left.is_relative_to(right) and (not strict or left != right)


def lines(value) -> list[str]:
    """读取多行配置中的非空行。"""
    return [line.strip() for line in text(value).splitlines() if line.strip()]


def config_for(plugin) -> dict:
    """只读取本功能的实例字段，避免泄露其它能力的凭据。"""
    return {key: getattr(plugin, "_" + key, value) for key, value in DEFAULTS.items()}


def fingerprint(config: dict) -> str:
    """把影响执行范围的配置绑定到任务，修改配置后不重放旧删除。"""
    values = {key: value for key, value in config.items() if key != "sync_delete_notify"}
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def mappings(config: dict) -> list[dict]:
    """解析本地两段、网盘三段或带整理目录的四段映射。"""
    result = []
    for field, count in (("sync_delete_local_paths", 2), ("sync_delete_cloud_paths", 3)):
        for line in lines(config.get(field)):
            parts = line.split("#")
            library = ""
            if count == 3 and len(parts) == 4:
                optional_root = text(parts.pop())
                library = path_text(optional_root) if optional_root else ""
            if len(parts) != count:
                raise DeleteRejected(f"路径映射需要 {count} 段，以 # 分隔")
            parts = [path_text(part) for part in parts]
            if any(part == "/" for part in parts) or library == "/":
                raise DeleteRejected("映射不能使用存储根目录")
            if any(item["emby"] == parts[0] for item in result):
                raise DeleteRejected("同一 Emby 路径有重复映射")
            result.append({"emby": parts[0], "local": parts[1],
                           "storage": text(config.get("sync_delete_storage")) if count == 3 else "local",
                           "target": parts[-1], "cloud": count == 3, "library": library})
    return sorted(result, key=lambda item: len(item["emby"]), reverse=True)


def mapped_scope(path: str, config: dict) -> dict:
    """用最长目录边界映射事件路径，不允许删除映射根。"""
    path = path_text(path)
    for item in mappings(config):
        if within(path, item["emby"]):
            if path == item["emby"]:
                raise DeleteRejected("不能删除映射根目录")
            relative = PurePosixPath(path).relative_to(item["emby"])
            result = dict(item, emby_path=path)
            result["local_path"] = str(PurePosixPath(item["local"]) / relative)
            result["target_path"] = str(PurePosixPath(item["target"]) / relative)
            if item["library"]:
                result["library_path"] = str(PurePosixPath(item["library"]) / relative)
            for excluded in lines(config.get("sync_delete_exclude_paths")):
                excluded = path_text(excluded)
                if any(within(result[key], excluded) for key in ("emby_path", "local_path", "target_path", "library_path") if key in result):
                    raise DeleteRejected("目标位于排除目录")
            return result
    raise DeleteRejected("事件路径没有匹配到配置的媒体库映射")


def event_snapshot(data) -> dict:
    """保留删除所需字段，不持久化含会话或凭据的完整 Webhook 报文。"""
    def get(key, default=None):
        """兼容宿主字典与事件对象的字段读取。"""
        return data.get(key, default) if isinstance(data, dict) else getattr(data, key, default)
    raw = get("json_object") or {}
    item = raw.get("Item") or {}
    paths = []
    if get("item_path") or get("path"):
        paths.append(path_text(get("item_path") or get("path")))
    # 神医的 Item Path 区段可能包含多行版本路径，遇下一字段结束。
    description_paths, in_paths = [], False
    for line in text(raw.get("Description")).splitlines():
        line = line.strip()
        match = re.match(r"Item Path\s*[:：]\s*(.*)", line, re.IGNORECASE)
        if match:
            in_paths = True
            line = match.group(1).strip()
        elif in_paths and re.match(r"(?:Mount Paths|Item Name|Description|Other Info)\s*:", line):
            in_paths = False
        if in_paths and line.startswith(("/", "\\")):
            description_paths.append(path_text(line))
    # 有明确版本清单时不用泛化的父目录路径，以免扩大到其它版本。
    if description_paths:
        paths = description_paths
    if not paths:
        raise DeleteRejected("删除通知缺少媒体路径")
    if len(paths) > 500:
        raise DeleteRejected("单次通知路径过多")
    kind = text(get("media_type") or item.get("Type") or get("item_type")).lower()
    season, episode = get("season_id"), get("episode_id")
    if kind == "season" and season in (None, ""):
        season, episode = episode, None
    if kind == "season" and season in (None, ""):
        raise DeleteRejected("季删除通知缺少季号")
    if kind == "season" and not str(season).isdigit():
        raise DeleteRejected("季删除通知季号无效")
    return {"event": text(get("event")).lower(), "channel": text(get("channel")).lower(),
            "server": text(get("server_name")), "paths": sorted(set(paths)),
            "name": text(get("item_name")), "kind": kind, "item_id": text(get("item_id")),
            "season": season, "episode": episode, "media_source": text(get("media_source")),
            "media_id": text(get("media_id")), "container": text(item.get("Container")),
            "timestamp": text(raw.get("Date") or raw.get("DateCreated"))}


def event_key(event: dict) -> str:
    """相同资源的重复通知共用键，不按整包 hash 吞掉其它集。"""
    value = {key: event.get(key) for key in ("server", "paths", "timestamp")}
    if event.get("channel") == "download":
        value.update(channel="download", source_hash=event.get("source_hash"),
                     source_downloader=event.get("source_downloader"))
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
