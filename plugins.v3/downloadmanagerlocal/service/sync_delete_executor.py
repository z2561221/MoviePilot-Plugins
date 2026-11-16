"""同步删除分阶段执行器，保留逐目标复核、保存检查点与失败恢复。"""

from pathlib import PurePosixPath
from time import time

from ..model.sync_delete import (
    BLOCKS_KEY,
    PLAN_VERSION,
    DeleteRejected,
    fingerprint,
    mapped_scope,
    text,
)
from .sync_delete_planner import check_source_download_references, relation_records


class DeleteExecutor:
    """只执行已受理任务；准入、排队和失败结算仍由运行队列负责。"""

    def __init__(self, runtime, job, config, adapter, plan_builder, log):
        """固定本轮配置和适配器，复用运行队列的持久化与停止检查。"""
        self.runtime = runtime
        self.plugin = runtime.plugin
        self.job = job
        self.config = config
        self.adapter = adapter
        self.plan_builder = plan_builder
        self.log = log
        self.plan = None
        self.record_ids = set()
        self.source_validator = None

    def _check(self):
        """每个原检查点都复验本轮配置及停止信号。"""
        self.runtime.check(self.config)

    def _save(self):
        """每个原保存点都确认当前任务状态持久化。"""
        self.runtime.save(self.job)

    def _source_check(self, *, required=False):
        """源删除通道复核任务和文件，下载记录不能绕过此通道验证。"""
        if self.source_validator is not None:
            self.source_validator(self.plugin, self.plan, self.adapter)
        elif required:
            raise DeleteRejected("下载记录清单缺少源删除通道验证")

    def _prepare(self):
        """开始处理，复验或生成计划，并在执行实体前保存关联清单。"""
        self._check()
        self.job.update(state="running", updated_at=time())
        self.log.info(f"同步删除开始处理 {_log_target(self.job)}")
        if not self.job.get("plan"):
            if (self.job["event"].get("plan_version") != PLAN_VERSION
                    or self.job["event"].get("config_fingerprint") != fingerprint(self.config)):
                raise DeleteRejected("旧事件缺少当前版本或配置快照，不能直接重试")
            self.job["plan"] = self.plan_builder(self.plugin, self.job["event"], self.config, self.adapter)
        self.plan = self.job["plan"]
        if self.plan.get("version") != PLAN_VERSION:
            raise DeleteRejected("旧版本删除计划需人工核验，不能直接重试")
        if self.plan["config_fingerprint"] != fingerprint(self.config):
            raise DeleteRejected("任务配置快照与当前配置不同")
        self._save()
        self.log.info(f"同步删除关联完成 {_log_target(self.job)}：网盘 {len(self.plan['cloud_files'])} 项、"
                      f"本地 {len(self.plan['source_files'])} 项、种子 {len(self.plan['tasks'])} 个、"
                      f"整理记录 {len(self.plan['records'])} 条")

    def _verify_resume(self):
        """断点执行前复验已处理路径、下载任务身份和新增引用。"""
        for scope_path in self.job["event"]["paths"]:
            if self.plan.get("channel") == "download":
                continue
            scope = mapped_scope(scope_path, self.config)
            if self.adapter.lookup("local", scope["local_path"], scope["local"]) is not None:
                raise DeleteRejected("媒体库路径重新出现，停止旧删除任务")
        for target in self.plan["cloud_files"] + self.plan["source_files"]:
            current = self.adapter.lookup(target["storage"], target["path"], target["root"])
            if target["status"] in {"deleted", "absent"} and current is not None:
                raise DeleteRejected("已处理路径出现新文件，停止旧任务重试")
            if current is not None and current.get("identity") != target.get("identity"):
                raise DeleteRejected("文件身份已变化，停止旧删除任务")
        self.record_ids = {record["id"] for record in self.plan["records"]}
        for target in self.plan["source_files"]:
            if any(row["id"] not in self.record_ids for row in self.adapter.histories(source=target["path"])):
                raise DeleteRejected("源文件已有其它整理记录引用，停止旧任务重试")
        check_source_download_references(self.plan, self.adapter)
        for task in self.plan["tasks"]:
            if task["status"] == "removed" and self.adapter.torrent(task["downloader"], task["id"]) is not None:
                raise DeleteRejected("已移除的下载任务被重建，停止旧任务重试")
        if self.plan.get("channel") == "download":
            from .source_delete import check_source_plan

            self.source_validator = check_source_plan
            self._source_check()

    def _pause_tasks(self):
        """先确认自动任务避让标记，再暂停尚未移除的下载任务。"""
        blocks = self.plugin.get_data(BLOCKS_KEY) or {}
        for task in self.plan["tasks"]:
            blocks[task["downloader"] + "::" + task["id"]] = {
                "downloader": task["downloader"], "identity": task["identity"], "job_id": self.job["id"],
            }
        self.plugin.save_data(BLOCKS_KEY, blocks)
        if self.plugin.get_data(BLOCKS_KEY) != blocks:
            raise DeleteRejected("自动任务避让标记保存失败")
        for task in self.plan["tasks"]:
            self._check()
            if task["status"] != "removed":
                self.adapter.pause(task)

    def _delete_files(self):
        """按原网盘/本地顺序逐文件复核并保存，不合并删除检查点。"""
        for key in ("cloud_files", "source_files"):
            for target in self.plan[key]:
                self._check()
                if target["status"] not in {"deleted", "absent"}:
                    if key == "source_files" and any(
                            row["id"] not in self.record_ids for row in self.adapter.histories(source=target["path"])):
                        raise DeleteRejected("源文件已有其它整理记录引用，停止删除")
                    if key == "source_files":
                        check_source_download_references(self.plan, self.adapter)
                    self._source_check()
                    self.adapter.delete_file(target)
                    target["status"] = "deleted"
                    self._save()

    def _prune_parents(self):
        """实体处理后按原条件清理空父目录。"""
        for target in self.plan["source_files"]:
            self._check()
            prune = getattr(self.adapter, "prune_local_parents", None)
            if prune:
                prune(target)

    def _settle_torrents(self):
        """逐种子移除或暂停保留，再保存实体处理完成标记。"""
        for task in self.plan["tasks"]:
            self._check()
            if task["status"] == "removed":
                continue
            if task["action"] == "remove":
                self._source_check()
                self.adapter.remove(task)
                task["status"] = "removed"
            else:
                task["status"] = "paused"
            self._save()
        self.job["entities_complete"] = True
        self._save()

    def _mark_download_records(self):
        """按已捕获主键处理下载记录，不重新捕获后来下载的行。"""
        for record in self.plan.get("download_records", []):
            self._check()
            self._source_check(required=True)
            done = self.job.setdefault("download_records_done", [])
            if record["id"] not in done:
                self.adapter.mark_download_record_deleted(record)
                done.append(record["id"])
                self._save()

    def _mark_sources(self):
        """旧源路径仍未重现时更新捕获的下载文件记录。"""
        for src in self.plan["sources"]:
            self._check()
            if src not in self.job["sources_marked"]:
                for record in self.plan["source_record_snapshots"].get(src, []):
                    if self.adapter.lookup("local", src, self.adapter.source_root(src)) is not None:
                        raise DeleteRejected("已删除源路径出现新文件，保留新下载记录")
                    self.adapter.mark_download_record_deleted(record)
                self.job["sources_marked"].append(src)
                self._save()

    def _delete_history(self):
        """仅启用记录清理时逐条删除整理记录并保存进度。"""
        if self.config["sync_delete_records"]:
            for record in self.plan["records"]:
                self._check()
                if record["id"] not in self.job["records_done"]:
                    self.adapter.delete_record(record)
                    self.job["records_done"].append(record["id"])
                    self._save()

    def _finish(self):
        """退休已处理关联和避让标记，确认完成状态后输出结果。"""
        self._check()
        retire_relations(self.plugin, self.plan)
        blocks = self.plugin.get_data(BLOCKS_KEY) or {}
        for task in self.plan["tasks"]:
            key = task["downloader"] + "::" + task["id"]
            if task["status"] == "removed" and blocks.get(key, {}).get("job_id") == self.job["id"]:
                blocks.pop(key, None)
        self.plugin.save_data(BLOCKS_KEY, blocks)
        self.job.update(state="skipped" if self.plan.get("skip_reason") else "completed", updated_at=time(), error="")
        self._save()
        self.log.info(f"同步删除{'无需处理' if self.job['state'] == 'skipped' else '完成'} {_log_target(self.job)}："
                      f"{self.plan.get('skip_reason') or _log_result(self.job)}")

    def run(self):
        """按原顺序推进阶段，任何失败交还运行队列结算。"""
        self._prepare()
        self._verify_resume()
        self._pause_tasks()
        self._delete_files()
        self._prune_parents()
        self._settle_torrents()
        self._mark_download_records()
        self._mark_sources()
        self._delete_history()
        self._finish()


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


def _log_target(job: dict) -> str:
    """日志只记录任务和媒体标识，不输出 Webhook 原文或播放链接。"""
    event = job.get("event") or {}
    name = text(event.get("name"))
    if not name:
        paths = event.get("paths") or []
        name = PurePosixPath(paths[0]).name if paths else "媒体"
    name = " ".join(name.split())[:240]
    return f"[{job['id']}] {name}"


def _log_result(job: dict) -> str:
    """区分实际删除、原已不存在和合集保留，不能把跳过项记作删除。"""
    plan = job["plan"]
    cloud, local, tasks = plan["cloud_files"], plan["source_files"], plan["tasks"]
    return (f"网盘已删除 {sum(item['status'] == 'deleted' for item in cloud)}、"
            f"已不存在 {sum(item['status'] == 'absent' for item in cloud)}；"
            f"本地已删除 {sum(item['status'] == 'deleted' for item in local)}、"
            f"已不存在 {sum(item['status'] == 'absent' for item in local)}；"
            f"种子已移除 {sum(item['status'] == 'removed' for item in tasks)}、"
            f"保留并暂停 {sum(item['status'] == 'paused' for item in tasks)}；"
            f"整理记录已清理 {len(job['records_done'])}/{len(plan['records'])}")

