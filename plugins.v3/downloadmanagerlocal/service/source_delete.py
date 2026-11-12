"""源文件删除事件按持久关系规划，不依赖已经删除的整理记录。"""

from pathlib import PurePosixPath
from time import time

from app.sdk.logging import logger

from ..adapter.sync_delete import SyncDeleteAdapter
from ..model.sync_delete import (
    MAX_TARGETS,
    MEDIA_EXTENSIONS,
    PLAN_VERSION,
    DeleteRejected,
    config_for,
    fingerprint,
    path_text,
    text,
    within,
)
from .sync_delete import _snapshot_file, related_nodes, relation_records


def check_download_references(adapter, path, nodes):
    """旧任务不能删除被另一条下载记录引用的同路径文件。"""
    hashes = {node[1] for node in nodes}
    for row in adapter.download_files(path=path):
        # 宿主保留已删除记录（state=0）；它们不再构成文件占用。
        if row.get("state") == 0:
            continue
        torrent_hash = text(row.get("download_hash"))
        downloader = text(row.get("downloader"))
        if (torrent_hash not in hashes or
                (downloader and (downloader, torrent_hash) not in nodes)):
            raise DeleteRejected("关联文件已被其它下载引用，保留新下载")


def build_source_plan(plugin, event, config, adapter=None):
    """只展开已知转种/辅种关系，按文件范围保留合集剩余内容。"""
    adapter = adapter or SyncDeleteAdapter(plugin, config)
    source = path_text(event["paths"][0])
    root = adapter.source_root(source)
    if PurePosixPath(source).suffix.lower() not in MEDIA_EXTENSIONS:
        raise DeleteRejected("源删除事件必须指向具体媒体文件")
    if adapter.lookup("local", source, root) is not None:
        raise DeleteRejected("源文件仍存在或已被新下载重新创建")
    relationships = relation_records(plugin)
    source_hash = text(event.get("source_hash"))
    entries = [row for row in adapter.download_files(path=source)
               if text(row.get("download_hash")) == source_hash]
    owners = {text(row.get("downloader")) for row in entries if row.get("downloader")}
    relation_owners = {key[:-(len(source_hash) + 1)] for key, value in relationships.items()
                       if isinstance(value, dict) and value.get("to_download")
                       and key.endswith("-" + source_hash)}
    requested = text(event.get("source_downloader"))
    if requested:
        if owners and requested not in owners:
            raise DeleteRejected("源删除事件下载器与下载记录不一致")
        owners = {requested}
    elif not owners:
        owners = relation_owners
    if len(owners) != 1:
        raise DeleteRejected("无法唯一确认源下载器，保留关联种子")
    initial = {(next(iter(owners)), source_hash)}
    nodes = related_nodes(relationships, initial)
    if nodes == initial:
        raise DeleteRejected("没有可核验的转种或辅种关联")
    hashes = {node[1] for node in nodes}
    relations = {key: value for key, value in relationships.items()
                 if (key.startswith("iyuu_") and key[5:] in hashes)
                 or (key.startswith("iyuu_source_") and key[12:] in hashes)
                 or (isinstance(value, dict) and
                     (text(value.get("to_download")), text(value.get("to_download_id"))) in nodes)}
    relative = set()
    for row in entries:
        if row.get("savepath"):
            save_root = path_text(text(row["savepath"]).removeprefix("local:"))
            if within(source, save_root, strict=True):
                relative.add(str(PurePosixPath(source).relative_to(save_root)))
    plan = {"version": PLAN_VERSION, "channel": "download", "event": event,
            "config_fingerprint": fingerprint(config), "cloud_files": [],
            "source_files": [], "tasks": [], "records": [], "sources": [],
            "relations": relations, "source_guards": [{"path": source, "root": root}]}
    plan["related_nodes"] = [list(node) for node in sorted(nodes)]
    targets = {}
    guarded_paths = {source}
    for name, torrent_id in sorted(nodes):
        task = adapter.torrent(name, torrent_id)
        if task is None:
            continue
        # 秒级创建时间与事件同秒时不能证明是旧对象，宁可保留。
        if task["identity"][1] >= int(event["observed_at"]):
            raise DeleteRejected("关联任务在删除事件后创建，不能清理新任务")
        matching = {path for path in task["files"] if path == source or
                    str(PurePosixPath(path).relative_to(task["save_path"])) in relative}
        if not matching:
            raise DeleteRejected("关联种子的文件无法对应本次源删除路径")
        remaining = 0
        for path in task["files"]:
            allowed_root = adapter.source_root(path)
            current = adapter.lookup("local", path, allowed_root)
            if path in matching:
                if adapter.histories(source=path):
                    raise DeleteRejected("关联文件仍被整理记录引用，保留新版本")
                check_download_references(adapter, path, nodes)
                if config["sync_delete_source"]:
                    targets[path] = _snapshot_file(adapter, "local", path, allowed_root)
                elif current is not None:
                    remaining += 1
            elif PurePosixPath(path).suffix.lower() in MEDIA_EXTENSIONS:
                if current is not None:
                    remaining += 1
                else:
                    if path not in guarded_paths:
                        plan["source_guards"].append({"path": path, "root": allowed_root})
                        guarded_paths.add(path)
            if len(guarded_paths | targets.keys()) > MAX_TARGETS:
                raise DeleteRejected("源删除关联文件超过单次上限")
        task.update(action="pause" if remaining or not config["sync_delete_torrents"] else "remove",
                    status="pending", remaining=remaining)
        plan["tasks"].append(task)
    if not plan["tasks"]:
        raise DeleteRejected("关联任务已不存在，无需删除")
    plan["source_files"] = list(targets.values())
    return plan


def check_source_plan(plugin, plan, adapter):
    """每次删种前复核消失路径、任务文件清单与尚未退休的关系。"""
    current_relations = relation_records(plugin)
    if any(current_relations.get(key) != value for key, value in plan["relations"].items()):
        raise DeleteRejected("转种或辅种关系已变化，停止旧删除任务")
    for item in plan["source_guards"]:
        if adapter.lookup("local", item["path"], item["root"]) is not None:
            raise DeleteRejected("已删除路径出现新文件，保留新下载")
    for item in plan["source_files"]:
        check_download_references(adapter, item["path"], {tuple(node) for node in plan["related_nodes"]})
        if adapter.histories(source=item["path"]):
            raise DeleteRejected("源文件出现新整理记录，停止旧删除任务")
        if item["status"] in {"absent", "deleted"} and adapter.lookup(
                "local", item["path"], item["root"]) is not None:
            raise DeleteRejected("已删除路径出现新文件，保留新下载")
    for task in plan["tasks"]:
        current = adapter.torrent(task["downloader"], task["id"])
        if current is not None and (current["identity"] != task["identity"] or
                                    current["files"] != task["files"]):
            raise DeleteRejected("关联任务已重建或文件清单变化")


def receive_source_deleted(plugin, event, trigger=""):
    """接住宿主已提交的源删除事件，快照失败也留下可见的失败任务。"""
    if not getattr(plugin, "_enabled", False) or not getattr(plugin, "_sync_delete_enabled", False):
        return {"accepted": False, "reason": "disabled"}
    data = getattr(event, "event_data", None) or {}
    if not isinstance(data, dict) or not data.get("src") or not data.get("hash"):
        logger.info("同步删除保留关联任务：删除事件缺少具体源路径或 hash")
        return {"accepted": False, "reason": "需要具体源路径和 hash", "skipped": True}
    runtime = getattr(plugin, "_sync_delete_runtime", None)
    if runtime is None or runtime.stop.is_set():
        return {"accepted": False, "reason": "同步删除执行器未运行"}
    try:
        source = path_text(data["src"])
        config = config_for(plugin)
        adapter = SyncDeleteAdapter(plugin, config)
        adapter.source_root(source)
        source_hash = text(data["hash"])
        relationships = relation_records(plugin)
        managed = any(
            (isinstance(value, dict) and value.get("to_download") and
             (key.endswith("-" + source_hash) or text(value.get("to_download_id")) == source_hash))
            or key in {"iyuu_" + source_hash, "iyuu_source_" + source_hash}
            for key, value in relationships.items()
        )
        if not managed:
            return {"accepted": False, "reason": "没有本实例转种或辅种关联", "skipped": True}
        snapshot = {"channel": "download", "event": text(trigger), "paths": [source],
                    "source_hash": source_hash, "source_downloader": text(data.get("downloader")),
                    "observed_at": time(), "name": PurePosixPath(source).name, "timestamp": ""}
        plan = None
        try:
            plan = build_source_plan(plugin, snapshot, config, adapter)
        except Exception as error:  # noqa: BLE001 -- 查询异常由 worker 结算，不输出连接信息。
            # 由 worker 保存具体失败；observed_at 限制后续重试不能选中新创建任务。
            logger.debug(f"同步删除源快照待执行器复核：{type(error).__name__}")
        job_id = runtime.submit(snapshot, plan=plan)
        return {"accepted": True, "job_id": job_id}
    except DeleteRejected as error:
        logger.warning(f"同步删除源事件未受理：{error}")
        return {"accepted": False, "reason": str(error)}
