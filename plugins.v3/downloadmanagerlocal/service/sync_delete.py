"""Emby 同步删除编排：读取本实例关系，逐目标执行，保留失败与重试证据。

流程参考 DDSRem-Dev/SaMediaSyncDel 与 p115strmhelper 的媒体同步删除功能；
这里使用下载中心自己的转种/辅种记录，不依赖独立 TorrentTransfer/IYUUAutoSeed。
"""

from __future__ import annotations

from copy import deepcopy
from queue import Empty, Full, Queue
from threading import Event, RLock, Thread
from time import time
from uuid import uuid4

from app.schemas.types import MessageType
from app.sdk.logging import logger

from ..adapter.sync_delete import SyncDeleteAdapter
from ..model.source_paths import SourcePaths
from ..model.sync_delete import (
    MAX_PENDING,
    PLAN_VERSION,
    TERMINAL_STATES,
    DeleteRejected,
    config_for,
    event_key,
    event_snapshot,
    fingerprint,
    mappings,
    text,
    within,
)
from ..storage.sync_delete_jobs import DeleteJobStore
from .coordination import (
    coordinated as coordinated,
)
from .coordination import (
    operation_lock as operation_lock,
)
from .coordination import (
    operation_stopped as operation_stopped,
)
from .coordination import (
    task_blocked as task_blocked,
)
from .sync_delete_executor import (
    DeleteExecutor,
)
from .sync_delete_executor import (
    _log_result as _log_result,
)
from .sync_delete_executor import (
    _log_target as _log_target,
)
from .sync_delete_executor import (
    retire_relations as retire_relations,
)
from .sync_delete_planner import (
    _snapshot_file as _snapshot_file,
)
from .sync_delete_planner import (
    build_plan as build_plan,
)
from .sync_delete_planner import (
    check_source_download_references as check_source_download_references,
)
from .sync_delete_planner import (
    related_nodes as related_nodes,
)
from .sync_delete_planner import (
    relation_records as relation_records,
)

_INIT_LOCK = RLock()


class DeleteRuntime:
    """单实例串行执行队列；重启后的未决任务保留为待重试，不自动重放。"""

    def __init__(self, plugin):
        """创建当前实例专属的锁、停止信号与有界队列。"""
        self.plugin = plugin
        self.store = DeleteJobStore(plugin)
        self.lock = RLock()
        self.stop = Event()
        self.queue = Queue(MAX_PENDING)
        self.thread = None

    def jobs(self):
        """读取持久任务，损坏的数据不解释为空历史。"""
        return self.store.all()

    def save(self, job, *, new_task=False):
        """持久化任务；存储失败立即关闭准入，避免连续产生未索引详情。"""
        with self.lock:
            try:
                self.store.save(job, new_task=new_task)
            except Exception:
                self.stop.set()
                raise

    def check(self, config):
        """写入前确认当前实例、开关和执行配置仍然有效。"""
        if (self.stop.is_set() or not getattr(self.plugin, "_enabled", False)
                or not getattr(self.plugin, "_sync_delete_enabled", False)
                or fingerprint(config_for(self.plugin)) != fingerprint(config)):
            raise DeleteRejected("同步删除已停止或配置发生变化")

    def submit(self, event, *, job_id=None, plan=None):
        """先记录删除意图，再将新事件或可重试任务加入队列。"""
        with self.lock:
            config = config_for(self.plugin)
            self.check(config)
            jobs = self.store.summaries()
            if job_id:
                job = self.store.get(job_id)
                if not job or job["state"] in {"queued", "running"} | TERMINAL_STATES:
                    raise DeleteRejected("该记录不能重试")
                if job.get("plan") and job["plan"].get("version") != PLAN_VERSION:
                    raise DeleteRejected("旧版本删除计划需人工核验，不能直接重试")
                if job.get("plan") and job["plan"]["config_fingerprint"] != fingerprint(config):
                    raise DeleteRejected("配置已变化，旧任务不能直接重试")
                if not job.get("plan") and (job["event"].get("plan_version") != PLAN_VERSION
                        or job["event"].get("config_fingerprint") != fingerprint(config)):
                    raise DeleteRejected("旧事件缺少当前版本或配置快照，不能直接重试")
            else:
                event = dict(event)
                event.setdefault("plan_version", PLAN_VERSION)
                event.setdefault("config_fingerprint", fingerprint(config))
                if (event["plan_version"] != PLAN_VERSION or event["config_fingerprint"] != fingerprint(config)
                        or (plan and plan.get("config_fingerprint") != fingerprint(config))):
                    raise DeleteRejected("事件受理期间配置或计划版本发生变化")
                key = event_key(event)
                for row in jobs.values():
                    if row["event_key"] == key and (row["state"] not in TERMINAL_STATES or time() - row["updated_at"] < 120):
                        return row["id"]
                if sum(row["state"] not in TERMINAL_STATES for row in jobs.values()) >= MAX_PENDING:
                    raise DeleteRejected("未完成记录已达上限，请先处理失败任务")
                job = {"id": uuid4().hex, "event_key": key, "event": event, "plan": deepcopy(plan),
                       "created_at": time(), "records_done": [], "sources_marked": []}
            job.update(state="queued", error="", updated_at=time())
            self.save(job, new_task=not bool(job_id))
            try:
                self.queue.put_nowait(job["id"])
            except Full as error:
                job.update(state="failed", error="执行队列已满")
                self.save(job)
                raise DeleteRejected("执行队列已满") from error
            action = "重试已受理" if job_id else "已受理"
            logger.info(f"同步删除{action} {_log_target(job)}：路径 {len(job['event']['paths'])} 项，等待执行")
            return job["id"]

    def execute(self, job, adapter=None):
        """把已受理任务交给分阶段执行器，队列层保留失败结算职责。"""
        config = config_for(self.plugin)
        adapter = adapter or SyncDeleteAdapter(self.plugin, config)
        return DeleteExecutor(self, job, config, adapter, build_plan, logger).run()

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
                    job = self.store.get(job_id)
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
                        logger.error(f"同步删除状态保存失败 [{job_id}]：{type(storage_error).__name__}")
                    logger.warning(f"同步删除未完成 {_log_target(job)}：{message}")
            finally:
                self.queue.task_done()
            if job and not self.stop.is_set() and getattr(self.plugin, "_sync_delete_notify", False):
                try:
                    title = {"completed": "同步删除完成", "skipped": "同步删除无需处理"}.get(job["state"], "同步删除待处理")
                    self.plugin.post_message(mtype=MessageType.Plugin, title=title,
                                             text=f"{job['event'].get('name') or '媒体'}\n{job.get('error') or (job.get('plan') or {}).get('skip_reason') or '关联清理完成，可在下载中心查看明细'}")
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
        for job in runtime.store.reconcile().values():
            if job["state"] in {"queued", "running"}:
                job.update(state="failed", error="重载后保留未决任务，请核验后重试", updated_at=time())
                runtime.save(job)
        if getattr(plugin, "_enabled", False) and getattr(plugin, "_sync_delete_enabled", False):
            mappings(config_for(plugin))
            SourcePaths(config_for(plugin))
            runtime.thread = Thread(target=runtime.run, name=f"{plugin.__class__.__name__}-sync-delete", daemon=True)
            runtime.thread.start()
            logger.info(f"同步删除执行器已启动：保留 {len(runtime.store.summaries())} 条历史，等待 Emby 删除通知")


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
        configured = mappings(config_for(plugin))
        if not any(within(path, item["emby"]) for path in snapshot["paths"] for item in configured):
            return {"accepted": False, "reason": "path_not_mapped"}
        runtime = getattr(plugin, "_sync_delete_runtime", None)
        if runtime is None or runtime.stop.is_set():
            raise DeleteRejected("同步删除执行器未运行")
        return {"accepted": True, "job_id": runtime.submit(snapshot)}
    except DeleteRejected as error:
        logger.warning(f"同步删除未受理：{error}")
        return {"accepted": False, "reason": str(error)}
