"""自动删种后的原关系退役，防止同一旧母种把目标重新添加。"""

from copy import deepcopy
from time import time

from ..model.auto_delete import RETIREMENTS_KEY, digest
from ..model.state import IYUU_PENDING_KEY


def hashes_of(value):
    """兼容旧辅种历史的单 hash 字符串和列表。"""
    return [value] if isinstance(value, str) else list(value or [])


def capture_relations(runtime, snapshot):
    """实际处置批次只读取一次关联索引，随后按精确 key 回读原记录。"""
    from .sync_delete_planner import relation_records

    if runtime.relations is None:
        runtime.relations = relation_records(runtime.plugin)
    result = {}
    for key, value in runtime.relations.items():
        if isinstance(value, dict) and value.get("to_download") == snapshot.downloader and value.get("to_download_id") == snapshot.hash:
            current = runtime.plugin.get_data(key)
            if isinstance(current, dict) and all(current.get(field) == value.get(field) for field in value):
                result[key] = deepcopy(current)
        elif key.startswith("iyuu_") and isinstance(value, list):
            if any(row["downloader"] == snapshot.downloader and snapshot.hash in hashes_of(row["torrents"]) for row in value):
                current = runtime.plugin.get_data(key)
                if isinstance(current, list) and [{"downloader": row["downloader"], "torrents": row["torrents"]} for row in current] == value:
                    result[key] = deepcopy(current)
    return result


def retire_relations(runtime, snapshot, job, originals):
    """仅退出被本任务实际移除的原关系，保留其它下载器和新的并发记录。"""
    plugin = runtime.plugin
    store = runtime.store
    retirement = {"job_id": job["id"], "identity": snapshot.identity,
                  "retired_at": time(), "source_before": snapshot.added_at,
                  "links": []}
    for key, original in originals.items():
        if plugin.get_data(key) != original:
            raise ValueError("原转种/辅种关系已变化，保留新关系待复核")
        if isinstance(original, dict):
            source_name, source_hash = key.rsplit("-", 1)
            value = deepcopy(original)
            value["auto_delete_retired"] = {"job_id": job["id"], "target_identity": snapshot.identity}
            store.write(key, value)
            retirement["links"].append({"kind": "transfer", "source_downloader": source_name,
                                         "source_hash": source_hash, "target_downloader": snapshot.downloader,
                                         "target_hash": snapshot.hash})
        elif key.startswith("iyuu_") and isinstance(original, list):
            remaining = []
            for row in original:
                hashes = [value for value in hashes_of(row["torrents"]) if row["downloader"] != snapshot.downloader or value != snapshot.hash]
                if hashes:
                    remaining.append({**row, "torrents": hashes})
            store.write(key, remaining)
            retirement["links"].append({"kind": "iyuu", "source_downloader": "", "source_hash": key[5:],
                                         "target_downloader": snapshot.downloader, "target_hash": snapshot.hash})
    with store.lock:
        records = store.retirements()
        records[digest(snapshot.identity)] = retirement
        store.write(RETIREMENTS_KEY, records)
    pending = plugin.get_data(IYUU_PENDING_KEY)
    if isinstance(pending, dict):
        kept = {key: value for key, value in pending.items() if not (
            value.get("downloader") == snapshot.downloader
            and snapshot.hash in {value.get("download_id"), value.get("expected_hash")})}
        if kept != pending:
            store.write(IYUU_PENDING_KEY, kept)


def target_retired(plugin, target_downloader, target_hash, source_hash, source_added_at=None,
                   source_downloader=""):
    """旧母种不能重新添加已退役目标，创建时间较新的母种按新任务处理。"""
    from ..storage.auto_delete_jobs import AutoDeleteStore

    index = getattr(plugin, "_auto_delete_retirement_index", None)
    if index is not None:
        protected_at = index["protected"].get((target_downloader, target_hash))
        if protected_at is not None and (source_added_at is None or source_added_at <= protected_at):
            return True
        for source_name in (source_downloader, ""):
            before = index["links"].get((target_downloader, target_hash, source_hash, source_name))
            if before is not None and (source_added_at is None or source_added_at <= before):
                return True
        return False
    records = getattr(plugin, "_auto_delete_retirement_snapshot", None)
    blocks = getattr(plugin, "_auto_delete_protection_snapshot", None)
    if blocks is None:
        blocks = AutoDeleteStore(plugin).blocks()
    for block in blocks.values():
        identity = block["identity"]
        if (identity[0] == target_downloader and identity[2] == target_hash
                and (source_added_at is None or source_added_at <= identity[3])):
            return True
    if records is None:
        records = AutoDeleteStore(plugin).retirements()
    for record in records.values():
        for link in record.get("links", []):
            if (link["target_downloader"] == target_downloader and link["target_hash"] == target_hash
                    and link["source_hash"] == source_hash
                    and (not link["source_downloader"] or link["source_downloader"] == source_downloader)
                    and (source_added_at is None or source_added_at <= record["source_before"])):
                return True
    return False


def retirement_index(records, blocks):
    """每个协调批次一次建立来源索引，普通种子循环不反复扫描全量历史。"""
    if not isinstance(records, dict) or not isinstance(blocks, dict):
        raise TypeError("退役关系索引状态无效")
    protected, links = {}, {}
    for block in blocks.values():
        identity = block["identity"]
        key = (identity[0], identity[2])
        protected[key] = max(protected.get(key, 0), identity[3])
    for record in records.values():
        for link in record.get("links", []):
            key = (link["target_downloader"], link["target_hash"], link["source_hash"], link["source_downloader"])
            links[key] = max(links.get(key, 0), record["source_before"])
    return {"protected": protected, "links": links}
