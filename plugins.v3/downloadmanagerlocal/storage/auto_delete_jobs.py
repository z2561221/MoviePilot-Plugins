"""自动删除独立任务记录与保护归属；任何未确认写入均停止副作用。"""

import re
from copy import deepcopy
from threading import RLock
from time import time

from ..model.auto_delete import (
    BLOCKS_KEY,
    CONTROL_KEY,
    INDEX_KEY,
    JOB_PREFIX,
    RETIREMENTS_KEY,
    STATUS_KEY,
    TERMINAL_STATES,
    Approval,
    DebugScan,
    Job,
    ScanSummary,
)

_INIT_LOCK = RLock()
_JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class StorageError(RuntimeError):
    """持久化或回读失败后关闭本轮及后续副作用准入。"""


class AutoDeleteStore:
    """实例隔离存储，分页先读摘要，只加载选中的任务详情。"""

    def __init__(self, plugin):
        """复用本实例存储锁，不共享其他模块的保护 key。"""
        self.plugin = plugin
        with _INIT_LOCK:
            if not hasattr(plugin, "_auto_delete_store_lock"):
                plugin._auto_delete_store_lock = RLock()
        self.lock = plugin._auto_delete_store_lock

    def mark_fault(self, message):
        """持久化未知时关闭执行准入，保留最后可核验现场。"""
        self.plugin._auto_delete_storage_fault = message
        runtime = getattr(self.plugin, "_auto_delete_runtime", None)
        if runtime is not None:
            runtime.stop.set()
            runtime.error = message

    def fail(self, message, error=None):
        """为损坏状态设置故障并显式抛出停止执行的异常。"""
        self.mark_fault(message)
        if error is not None:
            raise StorageError(message) from error
        raise StorageError(message)

    def read(self, key, default=None):
        """缺失与损坏分别处理，读取失败不当作空结果。"""
        try:
            value = self.plugin.get_data(key)
        except Exception as error:
            self.mark_fault("自动删除状态读取失败")
            raise StorageError("自动删除状态读取失败（" + type(error).__name__ + "）") from error
        if value is None:
            return deepcopy(default if default is not None else {})
        if not isinstance(value, dict):
            self.fail("自动删除状态损坏：" + key)
        return deepcopy(value)

    def write(self, key, value):
        """持久化后独立回读，失败不放行下载器写入。"""
        try:
            self.plugin.save_data(key, deepcopy(value))
            observed = self.plugin.get_data(key)
        except Exception as error:
            self.mark_fault("自动删除状态写入结果未知")
            raise StorageError("自动删除状态写入结果未知（" + type(error).__name__ + "）") from error
        if observed != value:
            self.fail("自动删除状态写入未确认：" + key)

    def control(self):
        """读取修订、服务端确认和成功调试扫描。"""
        payload = self.read(CONTROL_KEY, {"revision": 0, "approvals": {}, "debug_scans": {}, "config": {}})
        try:
            if type(payload.get("revision")) is not int or payload["revision"] < 0:
                raise ValueError("修订号无效")
            if payload.get("schema_version", 1) != 1 or not isinstance(payload.get("config"), dict):
                raise ValueError("配置状态无效")
            for field, model in (("approvals", Approval), ("debug_scans", DebugScan)):
                if not isinstance(payload.get(field), dict):
                    raise TypeError("确认状态无效")
                payload[field] = {key: model.model_validate(value).model_dump(mode="json")
                                  for key, value in payload[field].items()}
        except (ValueError, TypeError, KeyError) as error:
            self.fail("自动删除配置确认记录损坏", error)
        return payload

    def update_control(self, update):
        """短事务内读改写并回读，避免运行结果覆盖同时保存的用户确认。"""
        with self.lock:
            control = self.control()
            update(control)
            self.write(CONTROL_KEY, control)
            return control

    def blocks(self):
        """保护字典保存逐任务归属，删除一个归属不覆盖其他保护。"""
        payload = self.read(BLOCKS_KEY)
        for key, block in payload.items():
            if (not isinstance(block, dict) or block.get("job_id") != key
                    or not isinstance(block.get("identity"), list) or len(block["identity"]) != 5):
                self.fail("自动删除保护记录损坏")
        return payload

    def index(self):
        """只读摘要索引用于去重、状态统计和筛选。"""
        payload = self.read(INDEX_KEY)
        for key, row in payload.items():
            if (not isinstance(row, dict) or row.get("id") != key or not _JOB_ID.fullmatch(key)
                    or not isinstance(row.get("rule_id"), str) or not isinstance(row.get("downloader"), str)
                    or not isinstance(row.get("state"), str)
                    or not isinstance(row.get("created_at"), (int, float))
                    or not isinstance(row.get("updated_at"), (int, float))):
                self.fail("自动删除任务摘要索引损坏")
        return payload

    def get(self, job_id, *, index=None):
        """只加载已经发布到摘要索引的任务。"""
        if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
            raise ValueError("自动删除任务 ID 无效")
        if job_id not in (self.index() if index is None else index):
            raise ValueError("自动删除任务不存在")
        value = self.read(JOB_PREFIX + job_id)
        try:
            parsed = Job.model_validate(value)
            if parsed.id != job_id:
                raise ValueError("任务身份冲突")
        except (ValueError, TypeError) as error:
            self.fail("自动删除任务详情缺失或损坏", error)
        return parsed.model_dump(mode="json")

    def summary(self, job):
        """摘要保留筛选、去重和活动状态，不复制 Tracker 或文件详情。"""
        return {name: job[name] for name in (
            "id", "state", "rule_id", "downloader", "created_at", "updated_at",
        )}

    def save(self, job):
        """先保存详情再发布摘要；索引未确认则不进入执行队列。"""
        with self.lock:
            job["updated_at"] = time()
            payload = Job.model_validate(job).model_dump(mode="json")
            index = self.index()
            original = self.read(JOB_PREFIX + job["id"], None)
            if original and job["id"] not in index:
                self.fail("存在未确认的孤立任务详情，拒绝覆盖")
            if original and original.get("evidence_fingerprint") and (
                original.get("evidence_fingerprint") != payload["evidence_fingerprint"]
                or original.get("snapshot") != payload["snapshot"]
            ):
                self.fail("任务暂停前证据已变化，拒绝覆盖")
            self.write(JOB_PREFIX + job["id"], payload)
            index[job["id"]] = self.summary(payload)
            self.write(INDEX_KEY, index)

    def protect(self, job):
        """任务详情和摘要确认后才登记保护，并在暂停前回读。"""
        with self.lock:
            if job["id"] not in self.index():
                raise ValueError("未确认任务不能登记保护")
            blocks = self.blocks()
            blocks[job["id"]] = {"identity": job["identity"], "rule_id": job["rule_id"], "job_id": job["id"],
                                  "state": job["state"], "debug_rule_ids": job.get("debug_rule_ids", [])}
            self.write(BLOCKS_KEY, blocks)

    def unprotect(self, job_id):
        """仅撤销本任务的保护归属。"""
        with self.lock:
            blocks = self.blocks()
            blocks.pop(job_id, None)
            self.write(BLOCKS_KEY, blocks)

    def page(self, page=1, page_size=15, rule_id="", downloader="", state=""):
        """按摘要筛选并分页，详情缺失不回退为成功空列表。"""
        index = self.index()
        states = set(state.split(",")) if state else set()
        rows = [row for row in index.values()
                if (not rule_id or row["rule_id"] == rule_id)
                and (not downloader or row["downloader"] == downloader)
                and (not states or row["state"] in states)]
        rows.sort(key=lambda row: row["updated_at"], reverse=True)
        return len(rows), [self.get(row["id"], index=index) for row in rows[(page - 1) * page_size:page * page_size]]

    def prune(self, days):
        """只裁剪已结束且无保护的旧记录，活动任务永久保留。"""
        with self.lock:
            index, blocks = self.index(), self.blocks()
            cutoff = time() - days * 86400
            removed = [key for key, row in index.items() if row["state"] in TERMINAL_STATES
                       and row["updated_at"] < cutoff and key not in blocks]
            if not removed:
                return
            self.write(INDEX_KEY, {key: row for key, row in index.items() if key not in removed})
            for key in removed:
                try:
                    self.plugin.del_data(JOB_PREFIX + key)
                except Exception as error:
                    self.mark_fault("自动删除旧记录裁剪未确认")
                    raise StorageError("自动删除旧记录裁剪未确认") from error

    def status(self):
        """读取最近一轮的只读状态摘要。"""
        payload = self.read(STATUS_KEY)
        try:
            return ScanSummary.model_validate(payload).model_dump(mode="json")
        except (ValueError, TypeError) as error:
            self.fail("自动删除运行摘要损坏", error)

    def retirements(self):
        """读取原转种/辅种的主动退役标记，保留后续新任务的创建身份。"""
        return self.read(RETIREMENTS_KEY)

    def recover_index(self):
        """重载时只收敛已索引详情和已有保护，不扫描或重放孤立记录。"""
        with self.lock:
            index = self.index()
            blocks = self.blocks()
            if any(block["job_id"] not in index for block in blocks.values()):
                self.fail("保护引用没有已确认任务摘要，保持停止")
            updated = {key: self.summary(self.get(key, index=index)) for key in index}
            if updated != index:
                self.write(INDEX_KEY, updated)
            return updated
