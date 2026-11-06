"""Emby 同步删除编排：读取本实例关系，逐目标执行，保留失败与重试证据。

流程参考 DDSRem-Dev/SaMediaSyncDel 与 p115strmhelper 的媒体同步删除功能；
这里使用下载中心自己的转种/辅种记录，不依赖独立 TorrentTransfer/IYUUAutoSeed。
"""

from __future__ import annotations

import re
from copy import deepcopy
from functools import wraps
from pathlib import PurePosixPath
from queue import Empty, Full, Queue
from threading import Event, RLock, Thread
from time import time
from uuid import uuid4

from app.schemas.types import MessageType
from app.sdk.logging import logger

from ..adapter.sync_delete import SyncDeleteAdapter
from ..model.sync_delete import (
    BLOCKS_KEY,
    JOBS_KEY,
    MAX_JOBS,
    MAX_PENDING,
    MAX_TARGETS,
    MEDIA_EXTENSIONS,
    PLAN_VERSION,
    SIDECAR_EXTENSIONS,
    DeleteRejected,
    config_for,
    event_key,
    event_snapshot,
    fingerprint,
    mapped_scope,
    mappings,
    path_text,
    text,
    within,
)
from ..utils.torrent_adapter import normalize_torrent

_INIT_LOCK = RLock()


def operation_lock(plugin):
    """下载、辅种、校验与删除共用实例锁，避免扫描后又重新创建目标。"""
    with _INIT_LOCK:
        if not hasattr(plugin, "_sync_delete_operation_lock"):
            plugin._sync_delete_operation_lock = RLock()
        return plugin._sync_delete_operation_lock


def operation_stopped(plugin, generation: int) -> bool:
    """共享停止判定用于在途查询回包后的写入门禁。"""
    event = getattr(plugin, "_event", None)
    return (int(getattr(plugin, "_transfer_stop_generation", 0) or 0) != generation
            or (event is not None and event.is_set()))


def coordinated(function):
    """为已有批次入口提供同实例互斥，不改变普通执行结果。"""
    @wraps(function)
    def wrapper(plugin, *args, **kwargs):
        """等锁前固定停止代次，取消后不进入业务，嵌套调用恢复外层快照。"""
        generation = int(getattr(plugin, "_transfer_stop_generation", 0) or 0)
        guard = operation_lock(plugin)
        while not operation_stopped(plugin, generation):
            if guard.acquire(timeout=0.2):
                break
        else:
            return None
        previous = getattr(plugin, "_sync_delete_block_snapshot", None)
        try:
            if operation_stopped(plugin, generation):
                return None
            plugin._sync_delete_block_snapshot = (plugin.get_data(BLOCKS_KEY) or {}) if hasattr(plugin, "get_data") else {}
            return function(plugin, *args, **kwargs)
        finally:
            plugin._sync_delete_block_snapshot = previous
            guard.release()
    return wrapper


def task_blocked(plugin, downloader: str, torrent, kind: str) -> bool:
    """仅阻止同一创建时间/路径的旧任务；重新下载后的新任务不被永久封锁。"""
    if not hasattr(plugin, "get_data"):
        return False
    blocks = getattr(plugin, "_sync_delete_block_snapshot", None)
    if blocks is None:
        blocks = plugin.get_data(BLOCKS_KEY) or {}
    if not isinstance(blocks, dict) or not blocks:
        return False
    current = normalize_torrent(torrent, downloader, kind)
    for block in blocks.values():
        identity = block.get("identity", [])
        if (block.get("downloader") == downloader and len(identity) == 3
                and identity[0] == current.torrent_hash and identity[1] == current.added_at):
            return True
    return False


def relation_records(plugin) -> dict:
    """快照当前实例数据，丢弃无关 key；不读取其它插件的命名空间。"""
    raw = plugin.get_data() or []
    if isinstance(raw, dict):
        values = raw.items()
    else:
        values = [(getattr(row, "key", ""), getattr(row, "value", None)) for row in raw]
    result = {}
    for key, value in values:
        if not isinstance(key, str):
            continue
        if isinstance(value, dict) and value.get("to_download"):
            result[key] = {field: value.get(field) for field in
                           ("to_download", "to_download_id", "delete_source", "delete_duplicate", "transfer_state")
                           if field in value}
        elif key.startswith("iyuu_source_") and isinstance(value, str):
            result[key] = value
        elif key.startswith("iyuu_") and isinstance(value, list) and all(
                isinstance(row, dict) and row.get("downloader") and "torrents" in row for row in value):
            result[key] = [{"downloader": row["downloader"], "torrents": deepcopy(row["torrents"])} for row in value]
    return result


def related_nodes(records: dict, initial: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """转种双向连接，辅种按已有母种记录展开；环与重复节点只处理一次。"""
    edges = {}
    for key, record in records.items():
        if not isinstance(record, dict) or not record.get("to_download") or "-" not in key:
            continue
        source_name, source_hash = key.rsplit("-", 1)
        left = (source_name, source_hash)
        right = (text(record["to_download"]), text(record.get("to_download_id")))
        if not all(left + right):
            continue
        edges.setdefault(left, set()).add(right)
        edges.setdefault(right, set()).add(left)
    pending, seen = list(initial), set()
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        if len(seen) >= MAX_TARGETS:
            raise DeleteRejected("关联种子超过上限")
        seen.add(node)
        pending.extend(edges.get(node, ()))
        parent_hash = records.get("iyuu_source_" + node[1])
        if isinstance(parent_hash, str) and parent_hash:
            parents = {candidate for candidate in set(edges) | initial if candidate[1] == parent_hash}
            if len(parents) == 1:
                pending.extend(parents)
            elif len(parents) > 1:
                raise DeleteRejected("辅种母种存在多个下载器归属，不能猜测")
        history = records.get("iyuu_" + node[1]) or []
        if not isinstance(history, list):
            raise DeleteRejected("辅种历史格式异常")
        for row in history:
            if not isinstance(row, dict) or not row.get("downloader"):
                raise DeleteRejected("辅种历史缺少下载器")
            hashes = row.get("torrents") or []
            if isinstance(hashes, str):
                hashes = [hashes]
            pending.extend((text(row["downloader"]), text(value)) for value in hashes if text(value))
    return seen


def _dest_matches(dest: str, target: str, file_scope: bool) -> bool:
    """仅匹配明确文件或目录边界内的实体，不按名称模糊扩展。"""
    if not file_scope:
        return within(dest, target, strict=True)
    if dest == target:
        return True
    if target.lower().endswith(".strm"):
        base = target[:-5]
        return dest == base or str(PurePosixPath(dest).with_suffix("")) == base
    return False


def _snapshot_file(adapter, storage, path, root):
    """保存精确文件身份或已核验不存在状态。"""
    item = adapter.lookup(storage, path, root)
    if item is None:
        return {"storage": storage, "path": path, "root": root, "identity": None,
                "type": "file", "status": "absent"}
    if item["type"] != "file":
        raise DeleteRejected("文件记录实际指向目录，不能按文件处理")
    return dict(item, root=root, status="pending")


def _matching_histories(adapter, target, storage, event, file_scope):
    """只按明确存储、目标路径和媒体身份匹配整理记录。"""
    search = target[:-5] if target.lower().endswith(".strm") else target
    result = []
    for row in adapter.histories(search=search):
        dest = path_text(row.get("dest"))
        if text(row.get("dest_storage") or "local") != storage or not _dest_matches(dest, target, file_scope):
            continue
        if not file_scope and (text(row.get("media_id")) != event["media_id"]
                               or text(row.get("media_source")) != event["media_source"]):
            continue
        if event.get("media_id") and row.get("media_id") and (
                text(row["media_id"]) != event["media_id"] or text(row.get("media_source")) != event["media_source"]):
            continue
        if event.get("kind") == "season" and f"S{int(event['season']):02d}" not in re.findall(r"S\d+", text(row.get("seasons"))):
            continue
        result.append(row)
    return result


def _bridge_file(adapter, row, scope):
    """通过明确整理目录映射云端实体，并以双方及历史大小验证内容身份。"""
    local_path = path_text(row["dest"])
    if not within(local_path, scope["library"], strict=True):
        raise DeleteRejected("本地整理副本越过映射范围")
    relative = PurePosixPath(local_path).relative_to(scope["library"])
    cloud_path = str(PurePosixPath(scope["target"]) / relative)
    library_root = scope["library"]
    parent_root = str(PurePosixPath(library_root).parent)
    root_item = adapter.lookup("local", library_root, parent_root)
    if root_item is None:
        local_file = {"storage": "local", "path": local_path, "root": parent_root,
                      "type": "file", "identity": None, "status": "absent"}
    else:
        local_file = _snapshot_file(adapter, "local", local_path, library_root)
    cloud_file = _snapshot_file(adapter, scope["storage"], cloud_path, scope["target"])
    sizes = [cloud_file.get("size")]
    if local_file["status"] != "absent":
        sizes.append(local_file.get("size"))
    historical_size = (row.get("dest_fileitem") or {}).get("size")
    if historical_size is not None:
        sizes.append(historical_size)
    if len(sizes) < 2 or any(not isinstance(size, int) or size <= 0 for size in sizes) or len(set(sizes)) != 1:
        raise DeleteRejected("网盘与本地整理副本大小无法一致核验，保留关联待确认")
    return local_file, cloud_file


def build_plan(plugin, event: dict, config: dict, adapter=None, *, preview=False) -> dict:
    """只读解析完整目标，任何歧义在执行文件操作之前返回。"""
    adapter = adapter or SyncDeleteAdapter(plugin, config)
    selected = config.get("sync_delete_servers") or []
    available = adapter.servers()
    server = event.get("server")
    if not server:
        if len(available) != 1:
            raise DeleteRejected("通知未标明服务器，且当前存在多个 Emby 服务")
        server = available[0]
    if not selected or server not in selected or server not in available:
        raise DeleteRejected("通知来源未在同步删除服务器范围内")
    scopes = [mapped_scope(path, config) for path in event["paths"]]
    plan = {"version": PLAN_VERSION, "server": server, "event": event, "config_fingerprint": fingerprint(config),
            "cloud_files": [], "source_files": [], "tasks": [], "records": [], "sources": []}
    records, cloud, library_files = {}, {}, {}
    for scope in scopes:
        if not preview and adapter.lookup("local", scope["local_path"], scope["local"]) is not None:
            raise DeleteRejected("媒体库文件尚未删除或已重新生成")
        target = scope["target_path"]
        file_scope = PurePosixPath(target).suffix.lower() in MEDIA_EXTENSIONS
        if not file_scope and not (event.get("media_source") and event.get("media_id")):
            raise DeleteRejected("目录删除通知缺少完整媒体身份")
        found = _matching_histories(adapter, target, scope["storage"], event, file_scope)
        bridge_targets = {}
        if scope.get("library"):
            bridged = _matching_histories(adapter, scope["library_path"], "local", event, file_scope)
            if not found and not bridged:
                raise DeleteRejected("显式映射的本地整理目录没有对应记录")
            for row in bridged:
                local_file, cloud_file = _bridge_file(adapter, row, scope)
                if config["sync_delete_source"]:
                    library_files[local_file["path"]] = local_file
                bridge_targets[row["id"]] = cloud_file
            found.extend(bridged)
        targets_by_record = {row["id"]: bridge_targets[row["id"]]["path"] if row["id"] in bridge_targets else row["dest"] for row in found}
        if file_scope and len(set(targets_by_record.values())) > 1:
            raise DeleteRejected("删除路径对应多个版本，需明确具体目标")
        for row in found:
            records[row["id"]] = row
        if scope["cloud"] and config["sync_delete_cloud"]:
            if not found and not config["sync_delete_force_cloud"]:
                raise DeleteRejected("没有整理记录，且未开启按映射删除网盘文件")
            if not found and event.get("kind") == "season":
                raise DeleteRejected("无整理记录的季目录需逐集通知，不能扩大到整剧")
            targets = []
            if found:
                for row in found:
                    snap = bridge_targets.get(row["id"]) or _snapshot_file(adapter, scope["storage"], path_text(row["dest"]), scope["target"])
                    old_id = None if row["id"] in bridge_targets else (row.get("dest_fileitem") or {}).get("fileid")
                    if old_id and snap.get("fileid") and text(old_id) != text(snap["fileid"]):
                        raise DeleteRejected("云端文件 ID 与整理记录不同，可能已被替换")
                    targets.append(snap)
            else:
                targets = [dict(item, status="pending") for item in adapter.media_targets(
                    scope["storage"], target, scope["target"], strm=file_scope)]
                if not file_scope:
                    identity_tag = "tmdbid" if event.get("media_source") == "themoviedb" else ""
                    if not identity_tag or not re.search(
                            rf"\[{identity_tag}={re.escape(event['media_id'])}\]", PurePosixPath(target).name):
                        raise DeleteRejected("无整理记录的目录需要明确媒体身份标记，不能扩大清理范围")
                if not targets:
                    raise DeleteRejected("无整理记录且未找到唯一云端实体，保留待确认")
            for item in targets:
                cloud[(item["storage"], item["path"])] = item
        elif not found:
            raise DeleteRejected("没有对应的整理记录")
    plan["records"] = list(records.values())
    plan["cloud_files"] = list(cloud.values())
    source_paths, roots, known_roots, source_nodes = {}, set(), {}, {}
    relationships = relation_records(plugin)
    if config["sync_delete_source"] or config["sync_delete_torrents"]:
        for row in plan["records"]:
            src = text(row.get("src"))
            if not src:
                continue
            if text(row.get("src_storage") or "local") != "local":
                raise DeleteRejected("非本地下载源需要单独核验存储映射")
            src = path_text(src)
            source_root = adapter.source_root(src)
            # 其它保留的媒体库记录仍引用同一源文件时，不破坏其做种源。
            if any(ref["id"] not in records for ref in adapter.histories(source=src)):
                raise DeleteRejected("源文件仍被其它保留的整理记录引用")
            source_paths[src] = _snapshot_file(adapter, "local", src, source_root)
            original_file = row.get("src_fileitem") or {}
            current_file = source_paths[src]
            if current_file["status"] != "absent":
                if original_file.get("size") is not None and current_file.get("size") != original_file["size"]:
                    raise DeleteRejected("源文件大小与整理记录不一致，可能已被替换")
                stamp = original_file.get("modify_time_ns")
                identity = current_file.get("identity") or []
                if stamp and len(identity) == 4 and int(stamp) != identity[3]:
                    raise DeleteRejected("源文件修改时间已变化")
            if config["sync_delete_source"]:
                plan["sources"].append(src)
            row_roots = set()
            if row.get("downloader") and row.get("download_hash"):
                row_roots.add((text(row["downloader"]), text(row["download_hash"])))
            for entry in adapter.download_files(path=src):
                if entry.get("downloader") and entry.get("download_hash"):
                    node = (text(entry["downloader"]), text(entry["download_hash"]))
                    row_roots.add(node)
                    if entry.get("savepath"):
                        known_roots[node] = path_text(entry["savepath"])
            if row.get("download_hash"):
                torrent_hash = text(row["download_hash"])
                for key, value in relationships.items():
                    if isinstance(value, dict) and value.get("to_download") and key.endswith("-" + torrent_hash):
                        row_roots.add((key[:-(len(torrent_hash) + 1)], torrent_hash))
                if not any(node[1] == torrent_hash for node in row_roots):
                    for entry in adapter.download_files(torrent_hash=torrent_hash):
                        if entry.get("downloader"):
                            node = (text(entry["downloader"]), torrent_hash)
                            row_roots.add(node)
                            if entry.get("savepath"):
                                known_roots[node] = path_text(entry["savepath"])
                if not any(node[1] == torrent_hash for node in row_roots):
                    raise DeleteRejected("有下载 hash 但无法确认源下载器，保留关联待核验")
            roots.update(row_roots)
            source_nodes.setdefault(src, set()).update(row_roots)
    if roots:
        nodes = related_nodes(relationships, roots)
        hashes = {node[1] for node in nodes}
        plan["relations"] = {
            key: value for key, value in relationships.items()
            if (key.startswith("iyuu_") and key[5:] in hashes)
            or (key.startswith("iyuu_source_") and key[len("iyuu_source_"):] in hashes)
            or (isinstance(value, dict) and (text(value.get("to_download")), text(value.get("to_download_id"))) in nodes)
        }
        tasks = []
        for name, torrent_id in sorted(nodes):
            task = adapter.torrent(name, torrent_id)
            if task:
                tasks.append(task)
                known_roots[(name, torrent_id)] = task["save_path"]
        relative_paths, exact_paths = {}, {}
        for source, origin_nodes in source_nodes.items():
            group = related_nodes(relationships, origin_nodes)
            relative = set()
            for node in origin_nodes:
                save_root = known_roots.get(node)
                if save_root and within(source, save_root, strict=True):
                    relative.add(str(PurePosixPath(source).relative_to(save_root)))
            for node in group:
                relative_paths.setdefault(node, set()).update(relative)
                exact_paths.setdefault(node, set()).add(source)
        for task in tasks:
            node = (task["downloader"], task["id"])
            matching = {path for path in task["files"] if path in exact_paths.get(node, set())}
            matching.update(path for path in task["files"]
                            if str(PurePosixPath(path).relative_to(task["save_path"])) in relative_paths.get(node, set()))
            if not matching:
                raise DeleteRejected("关联种子的文件路径无法与本次删除对应")
            for path in matching:
                if path not in source_paths:
                    if any(ref["id"] not in records for ref in adapter.histories(source=path)):
                        raise DeleteRejected("转种副本仍被其它整理记录引用")
                    source_paths[path] = _snapshot_file(adapter, "local", path, adapter.source_root(path))
            remaining = []
            for path in task["files"]:
                if (path not in matching and PurePosixPath(path).suffix.lower() in MEDIA_EXTENSIONS
                        and adapter.lookup("local", path, adapter.source_root(path)) is not None):
                    remaining.append(path)
            task.update(action="pause" if remaining or not config["sync_delete_torrents"] else "remove",
                        status="pending", remaining=len(remaining))
            plan["tasks"].append(task)
    for path, item in library_files.items():
        if any(ref["id"] not in records for ref in adapter.histories(source=path)):
            raise DeleteRejected("本地整理副本仍被其它保留记录引用")
        source_paths[path] = item
    # 只删除同名字幕/NFO，保留影片共用海报等无法确定归属的文件。
    for source in list(source_paths) if config["sync_delete_source"] else []:
        parent = adapter.lookup("local", str(PurePosixPath(source).parent), source_paths[source]["root"])
        if parent:
            stem = PurePosixPath(source).stem
            for child in adapter.children(parent):
                child_path = path_text(child["path"])
                if (child["type"] == "file" and PurePosixPath(child_path).suffix.lower() in SIDECAR_EXTENSIONS
                        and PurePosixPath(child_path).stem == stem):
                    source_paths[child_path] = _snapshot_file(adapter, "local", child_path, source_paths[source]["root"])
    plan["source_files"] = list(source_paths.values()) if config["sync_delete_source"] else []
    if len(plan["cloud_files"]) + len(plan["source_files"]) > MAX_TARGETS:
        raise DeleteRejected("待删除文件超过单次上限")
    return plan


def retire_relations(plugin, plan):
    """只退出已核验移除目标的活动关系，保留暂停合集与并发新增关系。"""
    removed = {(task["downloader"], task["id"]) for task in plan["tasks"] if task["status"] == "removed"}
    for key, original in plan.get("relations", {}).items():
        if isinstance(original, dict) and (text(original.get("to_download")), text(original.get("to_download_id"))) in removed:
            if plugin.get_data(key) == original:
                plugin.del_data(key)
        elif key.startswith("iyuu_") and isinstance(original, list):
            current = plugin.get_data(key)
            if current != original:
                continue
            remaining = []
            for row in original:
                values = row.get("torrents") or []
                if isinstance(values, str):
                    values = [values]
                kept = [value for value in values if (text(row.get("downloader")), text(value)) not in removed]
                if kept:
                    remaining.append(dict(row, torrents=kept))
            if remaining != original:
                if remaining:
                    plugin.save_data(key, remaining)
                else:
                    plugin.del_data(key)
    for key, original in plan.get("relations", {}).items():
        if not key.startswith("iyuu_source_") or not isinstance(original, str):
            continue
        seed_hash = key[len("iyuu_source_"):]
        if not any(torrent_id == seed_hash for _, torrent_id in removed):
            continue
        if any(task["id"] == seed_hash and task["status"] != "removed" for task in plan["tasks"]):
            continue
        # 反查按 hash 保存，另一下载器仍保留同 hash 时不能清掉共享反查。
        remaining = relation_records(plugin)
        if any(seed_hash in (row.get("torrents") or [])
               for value in remaining.values() if isinstance(value, list) for row in value):
            continue
        if plugin.get_data(key) == original:
            plugin.del_data(key)


class DeleteRuntime:
    """单实例串行执行队列；重启后的未决任务保留为待重试，不自动重放。"""

    def __init__(self, plugin):
        """创建当前实例专属的锁、停止信号与有界队列。"""
        self.plugin = plugin
        self.lock = RLock()
        self.stop = Event()
        self.queue = Queue(MAX_PENDING)
        self.thread = None

    def jobs(self):
        """读取持久任务，损坏的数据不解释为空历史。"""
        value = self.plugin.get_data(JOBS_KEY) or {}
        if not isinstance(value, dict):
            raise DeleteRejected("同步删除历史损坏，停止执行")
        return value

    def save(self, job):
        """持久化任务并核对回读，只裁剪已经完成的历史。"""
        with self.lock:
            jobs = self.jobs()
            jobs[job["id"]] = deepcopy(job)
            completed = sorted((row for row in jobs.values() if row["state"] == "completed"),
                               key=lambda row: row.get("updated_at", 0))
            for row in completed:
                if len(jobs) <= MAX_JOBS and time() - row.get("updated_at", 0) <= 30 * 86400:
                    continue
                jobs.pop(row["id"], None)
            self.plugin.save_data(JOBS_KEY, jobs)
            if self.plugin.get_data(JOBS_KEY) != jobs:
                raise DeleteRejected("删除意图保存未确认")

    def check(self, config):
        """写入前确认当前实例、开关和执行配置仍然有效。"""
        if (self.stop.is_set() or not getattr(self.plugin, "_enabled", False)
                or not getattr(self.plugin, "_sync_delete_enabled", False)
                or fingerprint(config_for(self.plugin)) != fingerprint(config)):
            raise DeleteRejected("同步删除已停止或配置发生变化")

    def submit(self, event, *, job_id=None):
        """先记录删除意图，再将新事件或可重试任务加入队列。"""
        with self.lock:
            config = config_for(self.plugin)
            self.check(config)
            jobs = self.jobs()
            if job_id:
                job = deepcopy(jobs.get(job_id))
                if not job or job["state"] in {"queued", "running", "completed"}:
                    raise DeleteRejected("该记录不能重试")
                if job.get("plan") and job["plan"].get("version") != PLAN_VERSION:
                    raise DeleteRejected("旧版本删除计划需人工核验，不能直接重试")
                if job.get("plan") and job["plan"]["config_fingerprint"] != fingerprint(config):
                    raise DeleteRejected("配置已变化，旧任务不能直接重试")
            else:
                key = event_key(event)
                for row in jobs.values():
                    if row["event_key"] == key and (row["state"] != "completed" or time() - row["updated_at"] < 120):
                        return row["id"]
                if sum(row["state"] != "completed" for row in jobs.values()) >= MAX_PENDING:
                    raise DeleteRejected("未完成记录已达上限，请先处理失败任务")
                job = {"id": uuid4().hex, "event_key": key, "event": event, "plan": None,
                       "created_at": time(), "records_done": [], "sources_marked": []}
            job.update(state="queued", error="", updated_at=time())
            self.save(job)
            try:
                self.queue.put_nowait(job["id"])
            except Full as error:
                job.update(state="failed", error="执行队列已满")
                self.save(job)
                raise DeleteRejected("执行队列已满") from error
            return job["id"]

    def execute(self, job, adapter=None):
        """按文件和任务快照逐阶段执行，成功后才清理历史关系。"""
        config = config_for(self.plugin)
        adapter = adapter or SyncDeleteAdapter(self.plugin, config)
        self.check(config)
        job.update(state="running", updated_at=time())
        if not job.get("plan"):
            job["plan"] = build_plan(self.plugin, job["event"], config, adapter)
        plan = job["plan"]
        if plan.get("version") != PLAN_VERSION:
            raise DeleteRejected("旧版本删除计划需人工核验，不能直接重试")
        if plan["config_fingerprint"] != fingerprint(config):
            raise DeleteRejected("任务配置快照与当前配置不同")
        self.save(job)
        for scope_path in job["event"]["paths"]:
            scope = mapped_scope(scope_path, config)
            if adapter.lookup("local", scope["local_path"], scope["local"]) is not None:
                raise DeleteRejected("媒体库路径重新出现，停止旧删除任务")
        # 断点恢复时先核查已完成文件没有重现，不借旧快照删除新下载对象的记录。
        for target in plan["cloud_files"] + plan["source_files"]:
            current = adapter.lookup(target["storage"], target["path"], target["root"])
            if target["status"] in {"deleted", "absent"} and current is not None:
                raise DeleteRejected("已处理路径出现新文件，停止旧任务重试")
            if current is not None and current.get("identity") != target.get("identity"):
                raise DeleteRejected("文件身份已变化，停止旧删除任务")
        record_ids = {record["id"] for record in plan["records"]}
        for target in plan["source_files"]:
            if any(row["id"] not in record_ids for row in adapter.histories(source=target["path"])):
                raise DeleteRejected("源文件已有其它整理记录引用，停止旧任务重试")
        for task in plan["tasks"]:
            if task["status"] == "removed" and adapter.torrent(task["downloader"], task["id"]) is not None:
                raise DeleteRejected("已移除的下载任务被重建，停止旧任务重试")
        blocks = self.plugin.get_data(BLOCKS_KEY) or {}
        for task in plan["tasks"]:
            blocks[task["downloader"] + "::" + task["id"]] = {
                "downloader": task["downloader"], "identity": task["identity"], "job_id": job["id"]}
        self.plugin.save_data(BLOCKS_KEY, blocks)
        if self.plugin.get_data(BLOCKS_KEY) != blocks:
            raise DeleteRejected("自动任务避让标记保存失败")
        for task in plan["tasks"]:
            self.check(config)
            if task["status"] != "removed":
                adapter.pause(task)
        for key in ("cloud_files", "source_files"):
            for target in plan[key]:
                self.check(config)
                if target["status"] not in {"deleted", "absent"}:
                    if key == "source_files" and any(
                            row["id"] not in record_ids for row in adapter.histories(source=target["path"])):
                        raise DeleteRejected("源文件已有其它整理记录引用，停止删除")
                    adapter.delete_file(target)
                    target["status"] = "deleted"
                    self.save(job)
        for target in plan["source_files"]:
            self.check(config)
            prune = getattr(adapter, "prune_local_parents", None)
            if prune:
                prune(target)
        for task in plan["tasks"]:
            self.check(config)
            if task["status"] == "removed":
                continue
            if task["action"] == "remove":
                adapter.remove(task)
                task["status"] = "removed"
            else:
                task["status"] = "paused"
            self.save(job)
        job["entities_complete"] = True
        self.save(job)
        for src in plan["sources"]:
            self.check(config)
            if src not in job["sources_marked"]:
                adapter.mark_source_deleted(src)
                job["sources_marked"].append(src)
                self.save(job)
        if config["sync_delete_records"]:
            for record in plan["records"]:
                self.check(config)
                if record["id"] not in job["records_done"]:
                    adapter.delete_record(record)
                    job["records_done"].append(record["id"])
                    self.save(job)
        self.check(config)
        retire_relations(self.plugin, plan)
        blocks = self.plugin.get_data(BLOCKS_KEY) or {}
        for task in plan["tasks"]:
            key = task["downloader"] + "::" + task["id"]
            if task["status"] == "removed" and blocks.get(key, {}).get("job_id") == job["id"]:
                blocks.pop(key, None)
        self.plugin.save_data(BLOCKS_KEY, blocks)
        job.update(state="completed", updated_at=time(), error="")
        self.save(job)

    def run(self):
        """串行消费删除任务并保留故障阶段，停止时退出后续操作。"""
        while not self.stop.is_set():
            try:
                job_id = self.queue.get(timeout=0.5)
            except Empty:
                continue
            job = None
            try:
                # 等待 Emby 完成文件移除，并允许停止即时打断。
                if self.stop.wait(2):
                    continue
                guard = operation_lock(self.plugin)
                acquired = False
                while not self.stop.is_set():
                    acquired = guard.acquire(timeout=0.5)
                    if acquired:
                        break
                if not acquired:
                    continue
                try:
                    job = deepcopy(self.jobs().get(job_id))
                    if job:
                        self.execute(job)
                finally:
                    guard.release()
            except Exception as error:  # noqa: BLE001 -- 外部适配器故障必须结算为可重试任务。
                if job:
                    message = str(error) if isinstance(error, DeleteRejected) else f"外部操作未完成：{type(error).__name__}"
                    job.update(state="failed", error=message, updated_at=time())
                    try:
                        self.save(job)
                    except Exception as storage_error:  # noqa: BLE001 -- 持久化故障保留原记录并停止 worker。
                        self.stop.set()
                        logger.error(f"同步删除状态保存失败：{type(storage_error).__name__}")
                    logger.warning(f"同步删除未完成 [{job_id}]：{message}")
            finally:
                self.queue.task_done()
            if job and not self.stop.is_set() and getattr(self.plugin, "_sync_delete_notify", False):
                try:
                    self.plugin.post_message(mtype=MessageType.Plugin, title="同步删除完成" if job["state"] == "completed" else "同步删除待处理",
                                             text=f"{job['event'].get('name') or '媒体'}\n{job.get('error') or '关联清理完成，可在下载中心查看明细'}")
                except Exception as error:  # noqa: BLE001 -- 通知失败不改变已核验的删除结果。
                    logger.warning(f"同步删除通知失败：{type(error).__name__}")


def start_runtime(plugin):
    """仅启用时启动一个 worker；旧线程未退出则不创建第二个执行器。"""
    with _INIT_LOCK:
        old = getattr(plugin, "_sync_delete_runtime", None)
        if old and old.thread and old.thread.is_alive():
            raise DeleteRejected("旧同步删除线程尚未退出")
        runtime = DeleteRuntime(plugin)
        plugin._sync_delete_runtime = runtime
        for job in list(runtime.jobs().values()):
            if job["state"] in {"queued", "running"}:
                job.update(state="failed", error="重载后保留未决任务，请核验后重试", updated_at=time())
                runtime.save(job)
        if getattr(plugin, "_enabled", False) and getattr(plugin, "_sync_delete_enabled", False):
            mappings(config_for(plugin))
            runtime.thread = Thread(target=runtime.run, name=f"{plugin.__class__.__name__}-sync-delete", daemon=True)
            runtime.thread.start()


def stop_runtime(plugin):
    """关闭准入，当前操作返回后旧 worker 不再继续下一项删除。"""
    runtime = getattr(plugin, "_sync_delete_runtime", None)
    if runtime:
        runtime.stop.set()
        if runtime.thread:
            runtime.thread.join(timeout=5)


def receive_webhook(plugin, event):
    """将允许的 Emby 删除通知投递给当前实例的持久队列。"""
    if not getattr(plugin, "_enabled", False) or not getattr(plugin, "_sync_delete_enabled", False):
        return {"accepted": False, "reason": "disabled"}
    try:
        data = getattr(event, "event_data", None) or {}
        event_type = text(data.get("event") if isinstance(data, dict) else getattr(data, "event", "")).lower()
        allowed = {"deep.delete"}
        if getattr(plugin, "_sync_delete_library_deleted", False):
            allowed.add("library.deleted")
        if event_type not in allowed:
            return {"accepted": False, "reason": "event_not_selected"}
        snapshot = event_snapshot(data)
        if snapshot["channel"] != "emby":
            return {"accepted": False, "reason": "not_emby"}
        runtime = getattr(plugin, "_sync_delete_runtime", None)
        if runtime is None or runtime.stop.is_set():
            raise DeleteRejected("同步删除执行器未运行")
        return {"accepted": True, "job_id": runtime.submit(snapshot)}
    except DeleteRejected as error:
        logger.warning(f"同步删除未受理：{error}")
        return {"accepted": False, "reason": str(error)}
