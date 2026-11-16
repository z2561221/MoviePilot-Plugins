"""同步删除只读规划：路径、文件身份、整理历史和转种辅种关系关联。"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import PurePosixPath

from ..adapter.sync_delete import SyncDeleteAdapter
from ..model.source_paths import SourcePaths
from ..model.sync_delete import (
    MAX_TARGETS,
    MEDIA_EXTENSIONS,
    PLAN_VERSION,
    SIDECAR_EXTENSIONS,
    DeleteRejected,
    fingerprint,
    mapped_scope,
    path_text,
    text,
    within,
)


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


def check_source_download_references(plan, adapter):
    """下载历史的同路径新引用不能被吸收为本次待删除对象。"""
    nodes = {tuple(node) for node in plan.get("related_nodes", [])}
    for target in plan["source_files"]:
        if adapter.lookup("local", target["path"], target["root"]) is None:
            continue
        for row in adapter.download_files(path=target["path"]):
            if row.get("state") != 0 and (text(row.get("downloader")), text(row.get("download_hash"))) not in nodes:
                raise DeleteRejected("源文件已被其它下载引用，保留新下载")


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


def _bridge_file(adapter, row, scope, *, cloud_enabled=True):
    """按明确目录和历史核验副本，仅开启网盘处理时读取云端实体。"""
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
    cloud_file = _snapshot_file(adapter, scope["storage"], cloud_path, scope["target"]) if cloud_enabled else None
    sizes = []
    if cloud_file is not None and cloud_file["status"] != "absent":
        sizes.append(cloud_file.get("size"))
    if local_file["status"] != "absent":
        sizes.append(local_file.get("size"))
    historical_size = (row.get("dest_fileitem") or {}).get("size")
    if historical_size is not None:
        sizes.append(historical_size)
    source_size = (row.get("src_fileitem") or {}).get("size")
    if source_size is not None:
        sizes.append(source_size)
    no_current_file = local_file["status"] == "absent" and (cloud_file is None or cloud_file["status"] == "absent")
    if (len(sizes) < 2 or (no_current_file and historical_size is None)
            or any(not isinstance(size, int) or size <= 0 for size in sizes) or len(set(sizes)) != 1):
        label = "网盘与本地整理副本" if cloud_enabled else "本地整理副本与历史"
        raise DeleteRejected(f"{label}大小无法一致核验，保留关联待确认")
    return local_file, cloud_path, cloud_file


def build_plan(plugin, event: dict, config: dict, adapter=None, *, preview=False) -> dict:
    """只读解析完整目标，任何歧义在执行文件操作之前返回。"""
    if event.get("channel") == "download":
        from .source_delete import build_source_plan
        return build_source_plan(plugin, event, config, adapter)
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
        bridge_targets, bridge_paths = {}, {}
        if scope.get("library"):
            bridged = _matching_histories(adapter, scope["library_path"], "local", event, file_scope)
            if not found and not bridged:
                raise DeleteRejected("显式映射的本地整理目录没有对应记录")
            for row in bridged:
                local_file, cloud_path, cloud_file = _bridge_file(
                    adapter, row, scope, cloud_enabled=config["sync_delete_cloud"],
                )
                if config["sync_delete_source"]:
                    library_files[local_file["path"]] = local_file
                bridge_paths[row["id"]] = cloud_path
                if cloud_file is not None:
                    bridge_targets[row["id"]] = cloud_file
            found.extend(bridged)
        targets_by_record = {row["id"]: bridge_paths.get(row["id"], row["dest"]) for row in found}
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
    paths = SourcePaths(config)
    source_paths, roots, known_roots, source_nodes = {}, set(), {}, {}
    source_record_snapshots = {}
    relationships = relation_records(plugin)
    if config["sync_delete_source"] or config["sync_delete_torrents"]:
        for row in plan["records"]:
            src = text(row.get("src"))
            if not src:
                continue
            if text(row.get("src_storage") or "local") != "local":
                raise DeleteRejected("非本地下载源需要单独核验存储映射")
            src = paths.checked(src)
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
            entries = adapter.download_files(path=src)
            for entry in entries:
                if row.get("download_hash") and text(entry.get("download_hash")) != text(row["download_hash"]):
                    continue
                if row.get("downloader") and text(entry.get("downloader")) != text(row["downloader"]):
                    continue
                if entry.get("downloader") and entry.get("download_hash"):
                    node = (text(entry["downloader"]), text(entry["download_hash"]))
                    row_roots.add(node)
                    if entry.get("savepath"):
                        known_roots[node] = paths.checked(entry["savepath"])
            if config["sync_delete_source"]:
                captured = source_record_snapshots.setdefault(src, {})
                for entry in entries:
                    if (entry.get("state") == 1
                            and (text(entry.get("downloader")), text(entry.get("download_hash"))) in row_roots):
                        captured[entry["id"]] = dict(entry)
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
                                known_roots[node] = paths.checked(entry["savepath"])
                if not any(node[1] == torrent_hash for node in row_roots):
                    raise DeleteRejected("有下载 hash 但无法确认源下载器，保留关联待核验")
            roots.update(row_roots)
            source_nodes.setdefault(src, set()).update(row_roots)
    if roots:
        nodes = related_nodes(relationships, roots)
        plan["related_nodes"] = [list(node) for node in sorted(nodes)]
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
    plan["source_record_snapshots"] = {path: list(rows.values()) for path, rows in source_record_snapshots.items()}
    check_source_download_references(plan, adapter)
    if len(plan["cloud_files"]) + len(plan["source_files"]) > MAX_TARGETS:
        raise DeleteRejected("待删除文件超过单次上限")
    return plan

