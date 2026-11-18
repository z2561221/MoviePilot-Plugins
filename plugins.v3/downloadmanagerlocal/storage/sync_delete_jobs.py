"""删除任务独立存储与摘要索引；旧整份历史保持只读兼容。"""

import logging
from copy import deepcopy
from threading import RLock
from time import time

from ..model.sync_delete import (
    BLOCKS_KEY,
    JOBS_KEY,
    MAX_JOBS,
    TERMINAL_STATES,
    DeleteRejected,
)
from ..model.sync_delete_review import dismissal_rejection, review_revision

JOB_INDEX_KEY = "sync_delete_job_index"
JOB_RECORD_PREFIX = "sync_delete_job_record_"
_LOCK_INIT = RLock()
logger = logging.getLogger(__name__)


class _IndexReadMismatch(DeleteRejected):
    """索引调用正常返回但回读不匹配，携带只用于补偿判定的观察值。"""

    def __init__(self, observed):
        """保存独立回读快照，不把索引正文放入错误消息。"""
        super().__init__("删除意图保存未确认：摘要索引")
        self.observed = deepcopy(observed)


def _unreferenced(index, job_id):
    """只有结构有效且没有目标ID引用的索引才可用于新任务补偿。"""
    return (isinstance(index, dict) and job_id not in index
            and all(isinstance(row, dict) and row.get("id") == key and row.get("state")
                    and row.get("id") != job_id for key, row in index.items()))


def job_record_key(job_id):
    """从任务ID构造当前实例内的持久key，不接受外部存储路径。"""
    if not isinstance(job_id, str) or not job_id or len(job_id) > 64:
        raise DeleteRejected("同步删除任务ID无效")
    return JOB_RECORD_PREFIX + job_id


def _summary(job, *, separate):
    """只保留排序、去重与准入需要的摘要，不复制删除清单。"""
    return {"id": job["id"], "state": job["state"],
            "event_key": job.get("event_key", ""), "updated_at": job.get("updated_at", 0),
            "separate": separate}


class DeleteJobStore:
    """使用插件基类持久化单任务，实例锁覆盖完整读改写及回读确认。"""

    def __init__(self, plugin):
        """为写入器和只读控制器共享本实例存储锁。"""
        self.plugin = plugin
        with _LOCK_INIT:
            if getattr(plugin, "_sync_delete_store_lock", None) is None:
                plugin._sync_delete_store_lock = RLock()
        self.lock = plugin._sync_delete_store_lock

    def _legacy(self):
        """完整读取旧格式，仅在索引首次建立或旧任务被访问时使用。"""
        raw = self.plugin.get_data(JOBS_KEY)
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise DeleteRejected("同步删除历史损坏，停止执行")
        return raw

    def _index(self):
        """没有新索引时只生成兼容视图，不因只读查询迁移或覆盖旧历史。"""
        raw = self.plugin.get_data(JOB_INDEX_KEY)
        if raw is None:
            return {key: _summary(value, separate=False) for key, value in self._legacy().items()}
        if (not isinstance(raw, dict) or raw.get("schema_version") != 1
                or not isinstance(raw.get("items"), dict)):
            raise DeleteRejected("同步删除任务索引损坏，停止执行")
        return raw["items"]

    def summaries(self):
        """返回独立摘要，用于排序和事件准入，不加载每个任务的计划。"""
        with self.lock:
            return deepcopy(self._index())

    def _get_many(self, ids, index, origins=None):
        """只加载指定任务，旧格式在一次调用中至多读取一遍。"""
        legacy = None
        result = {}
        for job_id in ids:
            row = index.get(job_id)
            if row is None:
                continue
            if row.get("separate"):
                job = self.plugin.get_data(job_record_key(job_id))
                separate = True
                if job is None and row.get("legacy_fallback"):
                    if legacy is None:
                        legacy = self._legacy()
                    job = legacy.get(job_id)
                    separate = False
            else:
                if legacy is None:
                    legacy = self._legacy()
                job = legacy.get(job_id)
                separate = False
            if not isinstance(job, dict) or job.get("id") != job_id or not job.get("state"):
                raise DeleteRejected("同步删除任务详情缺失或损坏，停止执行")
            result[job_id] = deepcopy(job)
            if origins is not None:
                origins[job_id] = separate
        return result

    def get(self, job_id):
        """按任务ID读取权威记录，新索引缺失详情时不回退到陈旧历史。"""
        with self.lock:
            return self._get_many([job_id], self._index()).get(job_id)

    def all(self):
        """完整加载供启动收敛、兼容调用和人工恢复导出使用。"""
        with self.lock:
            index = self._index()
            return self._get_many(index, index)

    def page(self, page, page_size, *, pending_only=False):
        """先排序摘要，再读取当前页的完整清单。"""
        with self.lock:
            index = self._index()
            rows = sorted(index.values(), key=lambda row: row.get("updated_at", 0), reverse=True)
            if pending_only:
                rows = [row for row in rows if row["state"] not in TERMINAL_STATES | {"queued", "running"}]
            selected = rows[(page - 1) * page_size:page * page_size]
            jobs = self._get_many([row["id"] for row in selected], index)
            return len(rows), [jobs[row["id"]] for row in selected]

    def dismiss(self, job_id, expected_revision, reason, actor):
        """保留失败证据，仅忽略未开始的记录；调用方须持有操作及队列互斥锁。"""
        with self.lock:
            job = self.get(job_id)
            if not job:
                raise DeleteRejected("记录不存在，请刷新")
            if review_revision(job) != expected_revision:
                raise DeleteRejected("记录已变化，请刷新后重新确认")
            blocks = self.plugin.get_data(BLOCKS_KEY)
            rejection = dismissal_rejection(job, {} if blocks is None else blocks)
            if rejection:
                raise DeleteRejected(rejection)
            note = str(reason).strip()
            if not note:
                raise DeleteRejected("忽略说明无效，请刷新后重试")
            job.update(state="dismissed", updated_at=time())
            job["resolution"] = {"action": "dismiss", "reason": note, "actor": actor,
                                 "reviewed_revision": expected_revision, "resolved_at": job["updated_at"]}
            self.save(job)
            return job

    def _save_index(self, index):
        """独立确认摘要发布成功，失败不能放行删除队列或完成日志。"""
        payload = {"schema_version": 1, "items": index}
        try:
            self.plugin.save_data(JOB_INDEX_KEY, payload)
            observed = self.plugin.get_data(JOB_INDEX_KEY)
        except Exception as error:
            raise DeleteRejected(f"删除意图保存未确认：摘要索引结果未知（{type(error).__name__}）") from error
        if observed != payload:
            raise _IndexReadMismatch(observed)

    def _require_missing_detail(self, key, conflict):
        """写前读取失败不代表不存在，已存在的详情不允许覆盖。"""
        try:
            existing = self.plugin.get_data(key)
        except Exception as error:
            raise DeleteRejected(f"删除意图保存未确认：写前详情结果未知（{type(error).__name__}）") from error
        if existing is not None:
            raise DeleteRejected(conflict)

    def _compensate_new_detail(self, job_id, key, saved, observed):
        """仅撤回未受理的新详情，任何结果未知或新引用都保留现场。"""
        if observed is not None and (not isinstance(observed, dict)
                                     or type(observed.get("schema_version")) is not int
                                     or observed.get("schema_version") != 1
                                     or not _unreferenced(observed.get("items"), job_id)):
            return "未补偿：索引可能已发布或回读无效"
        try:
            if not _unreferenced(self._index(), job_id):
                return "未补偿：索引已有引用"
            blocks = self.plugin.get_data(BLOCKS_KEY)
            if blocks is not None and (not isinstance(blocks, dict)
                                      or any(not isinstance(value, dict) for value in blocks.values())):
                return "未补偿：避让引用无法确认"
            if any(value.get("job_id") == job_id for value in (blocks or {}).values()):
                return "未补偿：任务已有避让引用"
            if self.plugin.get_data(key) != saved:
                return "未补偿：详情内容已变化"
        except Exception as error:  # noqa: BLE001 -- 无法重新核实补偿边界时必须保留数据。
            return f"未补偿：条件回读结果未知（{type(error).__name__}）"
        remove = getattr(self.plugin, "del_data", None)
        if remove is None:
            return "补偿未确认：当前宿主不提供移除接口"
        try:
            remove(key)
        except Exception as error:  # noqa: BLE001 -- 删除可能已提交，不盲重试或扩大清理。
            return f"补偿未确认：移除结果未知（{type(error).__name__}）"
        try:
            remaining = self.plugin.get_data(key)
        except Exception as error:  # noqa: BLE001 -- 删除回读失败不能记为成功。
            return f"补偿未确认：移除回读失败（{type(error).__name__}）"
        return "新任务失败写入已撤回" if remaining is None else "补偿未确认：详情仍存在"

    def save(self, job, *, new_task=False):
        """每检查点只保存当前任务，摘要变化时才更新索引并裁剪完成历史。"""
        with self.lock:
            try:
                index = deepcopy(self._index())
            except DeleteRejected:
                raise
            except Exception as error:
                raise DeleteRejected(f"删除意图保存未确认：写前索引结果未知（{type(error).__name__}）") from error
            key = job_record_key(job["id"])
            saved = deepcopy(job)
            if new_task:
                if job.get("state") != "queued" or not _unreferenced(index, job["id"]):
                    raise DeleteRejected("新任务ID已有数据或引用，拒绝覆盖")
                self._require_missing_detail(key, "新任务ID已有数据或引用，拒绝覆盖")
            previous = index.get(job["id"])
            if previous is not None and not previous.get("separate"):
                self._require_missing_detail(key, "旧任务已有未确认独立详情，保留数据待核验")
                # 先登记可回退的已知旧ID；失败重启不会覆盖已经写入的新进度。
                transition = deepcopy(index)
                transition[job["id"]] = {**previous, "separate": True, "legacy_fallback": True}
                self._save_index(transition)
                index = transition
            try:
                self.plugin.save_data(key, saved)
                observed = self.plugin.get_data(key)
            except Exception as error:
                raise DeleteRejected(f"删除意图保存未确认：任务详情结果未知（{type(error).__name__}）") from error
            if observed != saved:
                raise DeleteRejected("删除意图保存未确认：任务详情")
            row = _summary(job, separate=True)
            if index.get(job["id"]) == row:
                return
            index[job["id"]] = row
            removed = []
            completed = sorted((row for row in index.values() if row["state"] in TERMINAL_STATES),
                               key=lambda row: row.get("updated_at", 0))
            for old in completed:
                if len(index) <= MAX_JOBS and time() - old.get("updated_at", 0) <= 30 * 86400:
                    continue
                index.pop(old["id"], None)
                if old.get("separate"):
                    removed.append(old["id"])
            try:
                self._save_index(index)
            except _IndexReadMismatch as error:
                if new_task:
                    outcome = self._compensate_new_detail(job["id"], key, saved, error.observed)
                    raise DeleteRejected(f"删除意图保存未确认：摘要索引；{outcome}") from error
                raise
            # 先发布裁剪索引再删除详情；失败只留下不可见副本，不丢失未决任务。
            for old_id in removed:
                remove = getattr(self.plugin, "del_data", None)
                if remove:
                    try:
                        remove(job_record_key(old_id))
                    except Exception as error:  # noqa: BLE001 -- SDK裁剪失败只保留副本，不改已确认任务状态。
                        logger.warning("已完成删除任务详情裁剪失败，保留副本：%s", type(error).__name__)

    def reconcile(self):
        """启动时加载一次完整状态，修复中断于详情与索引之间的摘要差异。"""
        with self.lock:
            index = self._index()
            origins = {}
            jobs = self._get_many(index, index, origins)
            updated = {job_id: _summary(job, separate=origins[job_id])
                       for job_id, job in jobs.items()}
            if updated != index:
                self._save_index(updated)
            return jobs
