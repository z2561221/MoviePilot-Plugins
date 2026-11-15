"""删除任务独立存储与摘要索引；旧整份历史保持只读兼容。"""

import logging
from copy import deepcopy
from threading import RLock
from time import time

from ..model.sync_delete import JOBS_KEY, MAX_JOBS, TERMINAL_STATES, DeleteRejected

JOB_INDEX_KEY = "sync_delete_job_index"
JOB_RECORD_PREFIX = "sync_delete_job_record_"
_LOCK_INIT = RLock()
logger = logging.getLogger(__name__)


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

    def _get_many(self, ids, index):
        """只加载指定任务，旧格式在一次调用中至多读取一遍。"""
        legacy = None
        result = {}
        for job_id in ids:
            row = index.get(job_id)
            if row is None:
                continue
            if row.get("separate"):
                job = self.plugin.get_data(job_record_key(job_id))
            else:
                if legacy is None:
                    legacy = self._legacy()
                job = legacy.get(job_id)
            if not isinstance(job, dict) or job.get("id") != job_id or not job.get("state"):
                raise DeleteRejected("同步删除任务详情缺失或损坏，停止执行")
            result[job_id] = deepcopy(job)
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

    def page(self, page, page_size):
        """先排序摘要，再读取当前页的完整清单。"""
        with self.lock:
            index = self._index()
            rows = sorted(index.values(), key=lambda row: row.get("updated_at", 0), reverse=True)
            selected = rows[(page - 1) * page_size:page * page_size]
            jobs = self._get_many([row["id"] for row in selected], index)
            return len(rows), [jobs[row["id"]] for row in selected]

    def _save_index(self, index):
        """独立确认摘要发布成功，失败不能放行删除队列或完成日志。"""
        payload = {"schema_version": 1, "items": index}
        self.plugin.save_data(JOB_INDEX_KEY, payload)
        if self.plugin.get_data(JOB_INDEX_KEY) != payload:
            raise DeleteRejected("删除意图保存未确认：摘要索引")

    def save(self, job):
        """每检查点只保存当前任务，摘要变化时才更新索引并裁剪完成历史。"""
        with self.lock:
            index = deepcopy(self._index())
            key = job_record_key(job["id"])
            saved = deepcopy(job)
            self.plugin.save_data(key, saved)
            if self.plugin.get_data(key) != saved:
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
            self._save_index(index)
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
            jobs = self._get_many(index, index)
            updated = {job_id: _summary(job, separate=index[job_id].get("separate", False))
                       for job_id, job in jobs.items()}
            if updated != index:
                self._save_index(updated)
            return jobs
