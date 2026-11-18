"""命中后的暂停、正式删除和显式恢复，逐阶段保存可核验证据。"""

from contextlib import contextmanager
from copy import deepcopy
from time import time
from uuid import uuid4

from ..adapter.auto_delete import public_snapshot, safe_error
from ..model.auto_delete import Snapshot, digest
from ..storage.auto_delete_jobs import StorageError
from .auto_delete_matcher import match_rule
from .auto_delete_relations import capture_relations, retire_relations
from .coordination import operation_lock


@contextmanager
def operation_guard(runtime, *, recovery=False):
    """等锁期间也检查停止，取消请求不能在新周期继续执行。"""
    check = runtime.check_recovery if recovery else runtime.check
    guard = operation_lock(runtime.plugin)
    check()
    while not guard.acquire(timeout=0.2):
        check()
    try:
        check()
        yield
    finally:
        guard.release()


def other_protection(runtime, identity, job, *, coowners=True):
    """单任务确认只能越过自己的保护，不能接管其他调试或同步删除。"""
    from ..model.sync_delete import BLOCKS_KEY as SYNC_BLOCKS_KEY

    for key, block in runtime.store.blocks().items():
        if key != job["id"] and block["identity"] == identity:
            return True
    for rule_id in job.get("debug_rule_ids", []) if coowners else []:
        if rule_id != job["rule_id"] and any(rule.id == rule_id and rule.enabled and rule.mode == "debug"
                                             for rule in runtime.settings.rules):
            return True
    blocks = runtime.plugin.get_data(SYNC_BLOCKS_KEY) or {}
    if not isinstance(blocks, dict):
        raise TypeError("同步删除保护数据无法核验")
    for block in blocks.values():
        original = block.get("identity", [])
        if (block.get("downloader") == identity[0] and len(original) == 3
                and original[0] == identity[2] and original[1] == identity[3]):
            return True
    return False


def create_job(rule, snapshot, matches, now):
    """先记录原始命中状态，完整证据指纹在调用方附加采样后固定。"""
    return {"id": uuid4().hex, "state": "prepared", "stage": "prepared", "rule_id": rule.id,
            "rule_name": rule.name, "revision": rule.revision, "downloader": snapshot.downloader,
            "torrent_hash": snapshot.hash, "name": snapshot.name, "identity": snapshot.identity,
            "action": rule.action, "mode": rule.mode, "evidence": matches.reasons,
            "snapshot": public_snapshot(snapshot), "was_running": not snapshot.paused,
            "created_at": now, "updated_at": now, "error": "", "files": []}


def refetch(runtime, snapshot, rules):
    """操作前定向读取原任务的全部相关字段，锁前扫描不能代替它。"""
    need_trackers = any(rule.conditions.tracker_include or rule.conditions.tracker_exclude
                        or rule.conditions.tracker_error for rule in rules)
    items = runtime.adapter.poll(snapshot.downloader, ids=[snapshot.hash], need_trackers=need_trackers,
                                 need_seed_time=any(rule.conditions.seed_hours_min is not None for rule in rules),
                                 need_category=any(rule.conditions.category for rule in rules))
    if not items:
        return None
    if len(items) != 1 or items[0].identity != snapshot.identity:
        raise ValueError("原任务已重建、移动或下载器绑定变化")
    return items[0]


def validate_live_match(runtime, job, rule, current, *, existing):
    """新任务复核全部条件，旧暂停任务只沿用用户接受的动态历史依据。"""
    from .auto_delete import evidence_digest

    if evidence_digest(job) != job["evidence_fingerprint"]:
        raise ValueError("暂停前证据不完整或已变化")
    if existing:
        if (not current.paused or job.get("interfered") or not job.get("accepted_at")
                or job.get("accepted_fingerprint") != job["evidence_fingerprint"]):
            raise ValueError("暂停任务状态或历史确认已变化，需要重新观察")
        evaluated = rule.model_copy(deep=True)
        evaluated.conditions.upload_kib_max = None
        evaluated.conditions.tracker_error = ""
    else:
        evaluated = rule
    judgment = match_rule(evaluated, current, time())
    if judgment.status != "match":
        raise ValueError("操作前规则复核未通过：" + "；".join(judgment.reasons[-2:]))
    if rule.mode == "delete":
        for other in runtime.settings.rules:
            if not other.enabled or other.mode != "debug" or current.downloader not in other.downloaders:
                continue
            if match_rule(other, current, time()).status != "no_match":
                raise ValueError("另一个调试规则匹配或无法判断，保留任务")


def capture_queue(plugin, snapshot):
    """只保存原校验项用于结束后精确清理，不覆盖事件后来写入的新项。"""
    from .recheck import load_seed_recheck_queue

    return {key: deepcopy(item) for key, item in load_seed_recheck_queue(plugin).items()
            if item.get("downloader") == snapshot.downloader and item.get("hash") == snapshot.hash}


def cleanup_queue(plugin, originals):
    """锁内 compare-and-set 移除旧队列，新建队列项继续保留。"""
    from .recheck import _queue_lock, load_seed_recheck_queue, save_seed_recheck_queue

    with _queue_lock(plugin):
        queue = load_seed_recheck_queue(plugin)
        changed = False
        for key, original in originals.items():
            if queue.get(key) == original:
                queue.pop(key)
                changed = True
        if changed:
            save_seed_recheck_queue(plugin, queue)
            if load_seed_recheck_queue(plugin) != queue:
                raise StorageError("旧校验队列清理结果未确认")


def execute_job(runtime, job, rule, snapshot, *, existing=False):
    """暂停与每个删除阶段先存意图，结果未知时绝不重放。"""
    store, adapter = runtime.store, runtime.adapter
    try:
        runtime.check()
        store.save(job)
        store.protect(job)
        with operation_guard(runtime):
            if other_protection(runtime, snapshot.identity, job, coowners=rule.mode == "delete"):
                raise ValueError("该任务仍受其他调试规则或同步删除保护")
            related = [item for item in runtime.settings.rules if item.enabled and snapshot.downloader in item.downloaders]
            current = refetch(runtime, snapshot, related)
            if current is None:
                job["state"] = "absent"
            else:
                validate_live_match(runtime, job, rule, current, existing=existing)
                if rule.mode == "delete":
                    runtime.check_rule(rule)
                if not existing:
                    job["was_running"] = not current.paused
                    job["before_pause"] = public_snapshot(current)
                    job["recheck_snapshot"] = capture_queue(runtime.plugin, snapshot)
                job.update(state="pausing", stage="pausing")
                store.save(job)
                paused = adapter.pause(snapshot)
                if paused is None:
                    job["state"] = "absent"
                else:
                    job.update(state="paused", stage="paused")
                    store.save(job)
                    store.protect(job)
                    if rule.mode == "delete":
                        runtime.check_rule(rule)
                        originals = capture_relations(runtime, snapshot)
                        job["relation_keys"] = list(originals)
                        if rule.action == "data":
                            prepared = adapter.prepare_files(snapshot, runtime.settings)
                            if job.get("file_list_fingerprint") and digest(prepared) != job["file_list_fingerprint"]:
                                raise ValueError("旧文件清单已变化，不能直接重放")
                            job.update(files=prepared, file_list_fingerprint=digest(prepared), state="deleting", stage="deleting")
                            store.save(job)
                            for file_item in job["files"]:
                                runtime.check_rule(rule)
                                if adapter.current(snapshot) is None:
                                    raise ValueError("原种子任务已消失，停止后续文件删除")
                                adapter.check_shared_references(snapshot, [file_item["path"]])
                                adapter.delete_file(file_item)
                                file_item["deleted"] = True
                                store.save(job)
                            job["data_deleted"] = True
                        runtime.check_rule(rule)
                        job.update(state="removing", stage="removing")
                        store.save(job)
                        adapter.remove(snapshot)
                        job["task_removed"] = True
                        job.update(state="deleted" if rule.action == "data" else "removed", stage="settling")
                        store.save(job)
                        retire_relations(runtime, snapshot, job, originals)
                        cleanup_queue(runtime.plugin, job.get("recheck_snapshot", {}))
            job["stage"] = "finished" if job["state"] != "paused" else "paused"
            store.save(job)
            if job["state"] in {"removed", "deleted", "absent"}:
                store.unprotect(job["id"])
    except StorageError:
        runtime.stop.set()
        raise
    except (ValueError, RuntimeError, TypeError, OSError, KeyError, AttributeError) as error:
        job.update(state="review", error=safe_error(error))
        store.save(job)
        store.protect(job)
    return job


def release_jobs(runtime, job_ids, restore=False):
    """管理员可明确恢复原运行状态；多条任务保留逐项结果，不整批重试。"""
    originals = [runtime.store.get(job_id) for job_id in dict.fromkeys(job_ids)]
    results = []
    for original in originals:
        job = original
        try:
            with operation_guard(runtime, recovery=True):
                job = runtime.store.get(original["id"])
                snapshot = Snapshot.model_validate(job["snapshot"])
                if job["id"] not in runtime.store.blocks():
                    raise ValueError("任务没有本模块活动保护")
                if restore and (job["task_removed"] or any(item["deleted"] for item in job["files"])):
                    raise ValueError("任务或部分数据已移除，不能自动恢复做种")
                if restore and job.get("was_running"):
                    if other_protection(runtime, snapshot.identity, job):
                        raise ValueError("其他规则仍保护此任务，不能恢复")
                    runtime.adapter.current(snapshot)
                    job.update(state="restoring", stage="restoring")
                    runtime.store.save(job)
                    runtime.adapter.restore(snapshot, check=runtime.check_recovery)
                job.update(state="released", stage="finished", error="")
                runtime.store.save(job)
                runtime.store.unprotect(job["id"])
                runtime.samples = {key: value for key, value in runtime.samples.items()
                                   if value.get("identity") != snapshot.identity}
        except StorageError:
            raise
        except (ValueError, RuntimeError, TypeError, OSError, KeyError, AttributeError) as error:
            job.update(state="review", error=safe_error(error))
            runtime.store.save(job)
        results.append(job)
    return results
