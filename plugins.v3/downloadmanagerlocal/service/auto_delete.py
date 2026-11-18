"""规则扫描、可信采样和当前实例的自动删除运行状态。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from threading import Event, Lock
from time import monotonic, time
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.schemas.types import MessageType
from app.sdk.logging import logger
from app.sdk.scheduler import add_plugin_once_job, remove_plugin_once_job
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..adapter.auto_delete import (
    AutoDeleteAdapter,
    binding_of,
    public_snapshot,
    safe_error,
)
from ..model.auto_delete import (
    STATUS_KEY,
    UNSETTLED_STATES,
    Capabilities,
    MatchResult,
    Result,
    ScanEntry,
    ScanSummary,
    Snapshot,
    Status,
    digest,
    settings_from_config,
)
from ..model.upload_limit import torrent_state_key
from ..storage.auto_delete_jobs import AutoDeleteStore, StorageError
from .auto_delete_executor import create_job, execute_job
from .auto_delete_matcher import compile_rule, match_rule
from .coordination import operation_stopped

TZ = ZoneInfo("Asia/Shanghai")
KNOWN_FAILURES = (ValueError, RuntimeError, TypeError, OSError, KeyError, AttributeError)
PREVIEW_MAX_ITEMS = 500


class ApprovalInvalid(ValueError):
    """正式确认与当前规则或下载器绑定不一致。"""


def rule_fingerprint(settings, rule, bindings):
    """规则、优先级、下载器地址与删除范围共同约束正式确认。"""
    payload = rule.model_dump(exclude={"name", "mode", "enabled", "revision"})
    return digest({"rule": payload, "order": [item.id for item in settings.rules],
                   "bindings": {name: bindings[name] for name in rule.downloaders},
                   "source_paths": settings.source_paths if rule.action == "data" else [],
                   "exclude_paths": settings.exclude_paths if rule.action == "data" else []})


def sample_requirement(rule):
    """波动条件需要用户指定的有效采样次数，静态条件一次即可。"""
    return rule.consecutive if rule.conditions.upload_kib_max is not None or rule.conditions.tracker_error else 1


class AutoDeleteRuntime:
    """单实例一次一个扫描，停止后的旧回包不能进入新代次。"""

    def __init__(self, plugin, settings, *, adapter=None, now=None):
        """构造不查询下载器，也不启动线程或调度任务。"""
        self.plugin = plugin
        self.settings = settings
        self.store = AutoDeleteStore(plugin)
        self.stop = Event()
        self.run_lock = Lock()
        self.token = uuid4().hex
        self.samples = {}
        self.started_at = time() if now is None else now
        self.next_due = self.compute_due(self.started_at)
        self.adapter = adapter or AutoDeleteAdapter(plugin, self.check)
        self.error = ""
        self.running = False
        self.once_pending = False
        self.run_id = ""
        self.stage = "idle"
        self.generation = int(getattr(plugin, "_transfer_stop_generation", 0) or 0)
        self.missed_tick = False
        self.last_scan = None
        self.scan_summary = ScanSummary()
        self.debug_health = {}
        self.scan_capabilities = {}
        self.relations = None

    def compute_due(self, now):
        """首次启用等待一个间隔，Cron 严格选择未来时间点。"""
        if self.settings.schedule_type == "interval":
            return now + self.settings.interval_minutes * 60
        if not self.settings.cron:
            return None
        current = datetime.fromtimestamp(now, TZ) + timedelta(microseconds=1)
        due = CronTrigger.from_crontab(self.settings.cron, timezone=TZ).get_next_fire_time(None, current)
        return due.timestamp() if due else None

    def advance_due(self, now):
        """保持固定周期锚点，不因单轮耗时顺延，也不补跑漏掉的轮次。"""
        if self.settings.schedule_type == "interval" and self.next_due is not None:
            interval = self.settings.interval_minutes * 60
            if now >= self.next_due + interval:
                self.missed_tick = True
            self.next_due += max(1, int((now - self.next_due) // interval) + 1) * interval
        else:
            self.next_due = self.compute_due(now)

    def check_config(self):
        """生效模块设置及宿主总开关都从当前配置核对。"""
        config = self.plugin.get_config()
        if not isinstance(config, dict):
            raise TypeError("插件配置无法读取，停止旧任务")
        if digest(settings_from_config(config).model_dump()) != digest(self.settings.model_dump()):
            raise ValueError("自动删除配置已变化，停止旧任务")
        return config

    def check(self):
        """每次副作用前检查退出事件、停止代次、实例和当前总开关。"""
        if (self.stop.is_set() or operation_stopped(self.plugin, self.generation)
                or getattr(self.plugin, "_auto_delete_runtime", self) is not self):
            raise ValueError("自动删除已停止或重载")
        config = self.check_config()
        if not getattr(self.plugin, "_enabled", False) or not config.get("enabled") or not self.settings.enabled:
            raise ValueError("自动删除总开关未开启")
        if getattr(self.plugin, "_auto_delete_storage_fault", ""):
            raise StorageError(self.plugin._auto_delete_storage_fault)

    def check_recovery(self):
        """管理员可在模块关闭时恢复旧任务，停止/换代的旧请求仍无效。"""
        if (self.stop.is_set() or getattr(self.plugin, "_auto_delete_runtime", self) is not self
                or operation_stopped(self.plugin, self.generation)):
            raise ValueError("恢复请求的运行态已经停止或变化")
        self.check_config()
        if getattr(self.plugin, "_auto_delete_storage_fault", ""):
            raise StorageError(self.plugin._auto_delete_storage_fault)

    def bindings(self, rules=None):
        """读取所选下载器的当前配置指纹，不查询任务清单。"""
        selected = self.settings.rules if rules is None else rules
        names = dict.fromkeys(name for rule in selected for name in rule.downloaders)
        return {name: binding_of(self.adapter.service(name)) for name in names}

    def validate_approval(self, rule):
        """合法确认在总开关关闭时保留，身份变化则必须重新调试。"""
        approval = self.store.control()["approvals"].get(rule.id)
        try:
            fingerprint = rule_fingerprint(self.settings, rule, self.bindings([rule]))
        except KNOWN_FAILURES as error:
            raise ApprovalInvalid("下载器配置无法核验，正式确认失效") from error
        if not approval or approval["fingerprint"] != fingerprint or approval["revision"] != rule.revision:
            raise ApprovalInvalid("正式删种确认已失效，请重新暂停调试")
        return fingerprint

    def check_rule(self, rule):
        """只有当前启用的正式规则可以进入删除执行器。"""
        self.check()
        if not rule.enabled or rule.mode != "delete":
            raise ApprovalInvalid("该规则尚未正式启用")
        return self.validate_approval(rule)

    def sample(self, rule, snapshot, match, now, *, clock=None):
        """计数同时受时间间隔与规则修订约束，保存原值用于确认。"""
        key = rule.id + ":" + digest(snapshot.identity)
        if match.status != "match":
            self.samples.pop(key, None)
            return 0
        clock = now if clock is None else clock
        previous = self.samples.get(key)
        interval = self.settings.interval_minutes if self.settings.schedule_type == "interval" else self.settings.sample_minutes
        reset = (previous is None or previous["revision"] != rule.revision
                 or now < previous["last_at"] or clock < previous["last_clock"])
        if reset:
            previous = {"count": 0, "last_at": now - interval * 60,
                        "last_clock": clock - interval * 60, "first_at": now,
                        "identity": snapshot.identity, "revision": rule.revision, "observations": []}
            self.samples[key] = previous
        if now - previous["last_at"] >= interval * 60 and clock - previous["last_clock"] >= interval * 60:
            previous["count"] = min(rule.consecutive, previous["count"] + 1)
            previous.update(last_at=now, last_clock=clock)
            previous["observations"].append({"time": now, "snapshot": public_snapshot(snapshot),
                                             "reasons": list(match.reasons)})
            previous["observations"] = previous["observations"][-max(1, rule.consecutive):]
        return previous["count"]

    def limit_interference(self, snapshot, rules):
        """确认本插件确实写入低額限速后跳过，不用额度代替实际吞吐。"""
        state = getattr(self.plugin, "_upload_limit_state", None) or {}
        record = (state.get("torrents") or {}).get(torrent_state_key(snapshot.downloader, snapshot.hash), {})
        managed = [record.get("last_written_settings"), record.get("pending_write_settings")]
        if not snapshot.upload_limit_bps or not any(isinstance(item, dict) and item.get("enabled")
                and item.get("limit_bps") == snapshot.upload_limit_bps for item in managed):
            return []
        return [rule.id for rule in rules if rule.conditions.upload_kib_max is not None
                and snapshot.upload_limit_bps <= rule.conditions.upload_kib_max * 1024]

    def scan(self, *, preview=False, now=None):
        """基础查询每下载器一次，规则合并后才选择任务及单轮上限。"""
        fixed_now = now
        rules = [rule for rule in self.settings.rules if preview or rule.enabled]
        names = dict.fromkeys(name for rule in rules for name in rule.downloaders)
        compiled = {rule.id: compile_rule(rule) for rule in rules}
        blocks = self.store.blocks()
        protected = {digest(block["identity"]) for block in blocks.values()}
        retirements = self.store.retirements()
        retired = {digest(item["identity"]) for item in retirements.values() if item.get("identity")}
        entries, errors, candidates = [], [], []
        scanned = matched_count = skipped = 0
        self.debug_health = {rule.id: True for rule in rules if rule.mode == "debug"}
        self.rule_match_counts = {rule.id: 0 for rule in rules}
        self.scan_capabilities = {}
        seen_keys = set()
        timed_out_rules = set()
        unknown_errors = {}
        for name in names:
            related = [rule for rule in rules if name in rule.downloaders]
            try:
                snapshots = self.adapter.poll(name, need_category=any(rule.conditions.category for rule in related))
            except KNOWN_FAILURES as error:
                errors.append(safe_error(error))
                self.scan_capabilities[name] = Capabilities(error=safe_error(error))
                for rule in related:
                    self.debug_health[rule.id] = False
                continue
            tracker_results = []
            enrich = getattr(self.adapter, "enrich", None)
            for snapshot in snapshots:
                observed_at = time() if fixed_now is None else fixed_now
                judgments = []
                extra_rules = []
                for rule in related:
                    if rule.id in timed_out_rules:
                        judgment = MatchResult(rule_id=rule.id, rule_name=rule.name, revision=rule.revision,
                                               status="unknown", reasons=["本轮正则已超时，停止重复匹配"])
                    else:
                        conditions = rule.conditions
                        needs_details = bool(conditions.tracker_include or conditions.tracker_exclude
                                             or conditions.tracker_error or conditions.seed_hours_min is not None)
                        judgment = match_rule(rule, snapshot, observed_at, compiled=compiled[rule.id], basic=needs_details)
                        if needs_details and judgment.status == "match":
                            extra_rules.append((len(judgments), rule))
                    judgments.append(judgment)
                if extra_rules:
                    need_trackers = any(rule.conditions.tracker_include or rule.conditions.tracker_exclude
                                        or rule.conditions.tracker_error for _, rule in extra_rules)
                    need_seed_time = snapshot.seed_seconds is None and any(
                        rule.conditions.seed_hours_min is not None for _, rule in extra_rules)
                    if enrich and (need_trackers or need_seed_time):
                        try:
                            enrich(snapshot, need_trackers=bool(need_trackers), need_seed_time=need_seed_time)
                        except KNOWN_FAILURES as error:
                            errors.append(safe_error(error))
                            if need_trackers:
                                snapshot.trackers = None
                            if need_seed_time:
                                snapshot.seed_seconds = None
                    if need_trackers:
                        tracker_results.append(snapshot.trackers is not None)
                    for index, rule in extra_rules:
                        judgments[index] = match_rule(rule, snapshot, observed_at, compiled=compiled[rule.id])
                clock = monotonic() if fixed_now is None else fixed_now
                scanned += 1
                for rule, judgment in zip(related, judgments):
                    if judgment.status == "unknown":
                        unknown_errors.setdefault(rule.id, f"规则 {rule.name}：{judgment.reasons[-1]}")
                        if any("正则匹配超时" in reason for reason in judgment.reasons):
                            timed_out_rules.add(rule.id)
                is_protected = digest(snapshot.identity) in protected or digest(snapshot.identity) in retired
                interference = self.limit_interference(snapshot, related)
                counts = {}
                for rule, judgment in zip(related, judgments):
                    sample_key = rule.id + ":" + digest(snapshot.identity)
                    seen_keys.add(sample_key)
                    if judgment.status == "match":
                        self.rule_match_counts[rule.id] += 1
                    if judgment.status == "unknown" and rule.mode == "debug":
                        self.debug_health[rule.id] = False
                    if not preview and not is_protected:
                        if rule.id in interference:
                            self.samples.pop(sample_key, None)
                        else:
                            counts[rule.id] = self.sample(rule, snapshot, judgment, observed_at, clock=clock)
                    else:
                        counts[rule.id] = self.samples.get(sample_key, {}).get("count", 0)
                matches = [(rule, judgment) for rule, judgment in zip(related, judgments) if judgment.status == "match"]
                if matches:
                    matched_count += 1
                if not matches and not any(judgment.status == "unknown" for judgment in judgments):
                    continue
                unknown_debug = any(rule.mode == "debug" and judgment.status == "unknown"
                                    for rule, judgment in zip(related, judgments))
                debug_matches = [(rule, judgment) for rule, judgment in matches if rule.mode == "debug"]
                first_match = next((index for index, judgment in enumerate(judgments) if judgment.status == "match"), None)
                unknown_priority = first_match is not None and any(judgment.status == "unknown" for judgment in judgments[:first_match])
                chosen = debug_matches[0] if debug_matches else matches[0] if matches and not unknown_debug and not unknown_priority else None
                block_reason = ("任务已有保护或原身份已退役" if is_protected else "相关调试规则无法判断" if unknown_debug
                                else "靠前规则无法判断，不能改变原优先级" if unknown_priority else "")
                entry = ScanEntry(snapshot=public_snapshot(snapshot), rules=judgments,
                                  protected=is_protected, samples=counts,
                                  required_samples={rule.id: sample_requirement(rule) for rule in related},
                                  limit_interference=interference, block_reason=block_reason)
                if len(entries) < PREVIEW_MAX_ITEMS:
                    entries.append(entry)
                if preview or is_protected or chosen is None:
                    skipped += bool(matches)
                    continue
                rule, judgment = chosen
                if rule.id in interference or counts.get(rule.id, 0) < sample_requirement(rule):
                    skipped += 1
                    continue
                sample = self.samples[rule.id + ":" + digest(snapshot.identity)]
                candidates.append((sample["first_at"], rule, snapshot, judgment, entry, sample))
            first = snapshots[0] if snapshots else None
            self.scan_capabilities[name] = Capabilities(
                kind=first.kind if first else "", binding=first.binding if first else "",
                seed_seconds=all(item.seed_seconds is not None for item in snapshots) if snapshots else None,
                category=all(item.category is not None for item in snapshots) if snapshots else None,
                tags=all(item.tags is not None for item in snapshots) if snapshots else None,
                trackers=all(tracker_results) if tracker_results else None,
            )
        if not preview:
            self.samples = {key: value for key, value in self.samples.items() if key in seen_keys}
        candidates.sort(key=lambda item: (item[0], item[2].downloader, item[2].hash))
        errors.extend(unknown_errors.values())
        self.scan_summary = ScanSummary(scanned=scanned, matched=matched_count, skipped=skipped,
                                        errors=errors, capabilities=self.scan_capabilities)
        return entries, errors, candidates

    def run(self, *, now=None, automatic=False, run_id=""):
        """单轮运行，失败保留逐项真实结果；已有任务时不排第二个批次。"""
        if not self.run_lock.acquire(blocking=False):
            if automatic:
                self.missed_tick = True
            return Result(state="running", run_id=self.run_id, message="已有扫描正在运行")
        started = time() if now is None else now
        self.running = True
        self.once_pending = False
        self.run_id = run_id or uuid4().hex
        self.stage = "sampling"
        self.relations = None
        self.error = ""
        self.last_scan = started
        jobs, errors = [], []
        entries = []
        summary = ScanSummary(run_id=self.run_id, state="running", stage=self.stage,
                              last_scan=started, next_run=self.next_due)
        try:
            self.check()
            if automatic:
                self.advance_due(started)
            if self.missed_tick:
                self.samples.clear()
                self.missed_tick = False
            summary.next_run = self.next_due
            self.store.write(STATUS_KEY, summary.model_dump(mode="json"))
            entries, errors, candidates = self.scan(now=now)
            summary = self.scan_summary.model_copy(update={"run_id": self.run_id, "last_scan": started,
                                                            "next_run": self.next_due})
            self.check()
            self.stage = "processing"
            index = self.store.index()
            pending = sorted((row for row in index.values() if row["state"] == "approved"),
                             key=lambda row: (row["created_at"], row["id"]))
            for row in pending:
                if len(jobs) >= self.settings.max_tasks:
                    break
                self.check()
                job = self.store.get(row["id"], index=index)
                rule = next((item for item in self.settings.rules if item.id == job["rule_id"]
                             and item.enabled and item.mode == "delete"), None)
                if rule is None:
                    job.update(state="review", error="规则已停用或需要重新确认")
                    self.store.save(job)
                    self.store.protect(job)
                    continue
                self.check_rule(rule)
                snapshot = snapshot_from_job(job)
                jobs.append(execute_job(self, job, rule, snapshot, existing=True))
            for _, rule, snapshot, judgment, entry, observations in candidates:
                if len(jobs) >= self.settings.max_tasks:
                    break
                self.check()
                if rule.mode == "delete":
                    try:
                        self.check_rule(rule)
                    except ApprovalInvalid as error:
                        errors.append(safe_error(error))
                        continue
                job = create_job(rule, snapshot, judgment, started)
                job["matches"] = [item.model_dump(mode="json") for item in entry.rules]
                job["debug_rule_ids"] = [item.rule_id for item in entry.rules if item.status == "match"
                                         and any(other.id == item.rule_id and other.mode == "debug" for other in self.settings.rules)]
                job["rule_fingerprint"] = rule_fingerprint(self.settings, rule, self.bindings([rule]))
                job["sample_evidence"] = observations["observations"]
                job["evidence_fingerprint"] = evidence_digest(job)
                jobs.append(execute_job(self, job, rule, snapshot))
            self.check()
            self.save_debug_receipts(started, entries, jobs)
            self.store.prune(self.settings.history_days)
            summary.state = "degraded" if errors or any(job["state"] == "review" for job in jobs) else "idle"
            summary.stage = "finished"
            summary.finished_at = time()
            summary.paused = sum(job["state"] == "paused" for job in jobs)
            summary.removed = sum(job["state"] in {"removed", "deleted"} for job in jobs)
            summary.reviewed = sum(job["state"] == "review" for job in jobs)
            summary.errors = errors + [job["error"] for job in jobs if job.get("error")]
            self.store.write(STATUS_KEY, summary.model_dump(mode="json"))
            if self.settings.notify and jobs:
                send_notification(self.plugin, summary)
            return Result(state=summary.state, run_id=self.run_id, items=jobs, errors=summary.errors,
                          summary=summary)
        except KNOWN_FAILURES as error:
            self.error = safe_error(error)
            summary.state = "stopped" if self.stop.is_set() and not isinstance(error, StorageError) else "error"
            summary.stage = "stopped" if self.stop.is_set() else "failed"
            summary.errors = errors + [self.error]
            summary.finished_at = time()
            if not isinstance(error, StorageError):
                self.store.write(STATUS_KEY, summary.model_dump(mode="json"))
            logger.error("自动删除本轮保持现场：" + self.error)
            return Result(state=summary.state, run_id=self.run_id, message=self.error,
                          items=jobs, errors=summary.errors, summary=summary)
        finally:
            self.stage = summary.stage
            self.scan_summary = summary
            self.running = False
            self.run_lock.release()

    def save_debug_receipts(self, now, entries, jobs):
        """仅成功读取且成功完成调试的规则产生确认依据。"""
        updates = {}
        for rule in self.settings.rules:
            if not rule.enabled or rule.mode != "debug" or not self.debug_health.get(rule.id):
                continue
            if any(job["state"] == "review" and rule.id in job.get("debug_rule_ids", []) for job in jobs):
                continue
            matched = self.rule_match_counts.get(rule.id, 0)
            paused = sum(job["state"] == "paused" and rule.id in job.get("debug_rule_ids", []) for job in jobs)
            if matched and not paused and not any(row["rule_id"] == rule.id and row["state"] == "paused"
                                                 for row in self.store.index().values()):
                continue
            updates[rule.id] = {"fingerprint": rule_fingerprint(self.settings, rule, self.bindings([rule])),
                                "revision": rule.revision, "time": now, "matched": matched, "paused": paused}
        if updates:
            self.store.update_control(lambda control: control["debug_scans"].update(updates))


def snapshot_from_job(job):
    """从已经验证的内部记录重建原任务快照。"""
    return Snapshot.model_validate(job["snapshot"])


def evidence_digest(job):
    """命中前证据单独固定，UI 确认时不得用旧响应替代新证据。"""
    from ..model.auto_delete import Job

    payload = Job.model_validate(job).model_dump(mode="json")
    return digest({key: payload[key] for key in ("identity", "snapshot", "evidence", "rule_fingerprint",
                                           "revision", "sample_evidence", "matches", "debug_rule_ids")})


def send_notification(plugin, summary):
    """结果通知失败不改变已经核验完成的种子处置结果。"""
    try:
        plugin.post_message(mtype=MessageType.Plugin, title="下载中心 · 自动删除结果",
                            text=f"暂停 {summary.paused}，移除 {summary.removed}，待复核 {summary.reviewed}。命中依据已留在执行记录，呐，先核对再调整规则。")
    except KNOWN_FAILURES as error:
        logger.error("自动删除结果已保存，通知失败（" + type(error).__name__ + "）")


def runtime_of(plugin):
    """缺少可核验运行状态时拒绝管理操作。"""
    runtime = getattr(plugin, "_auto_delete_runtime", None)
    if runtime is None:
        raise ValueError("自动删除未初始化：" + getattr(plugin, "_auto_delete_error", ""))
    return runtime


def preview(plugin, settings):
    """检查完整规则草稿，既不写配置、计数，也不改变任务。"""
    current = runtime_of(plugin)
    transient = AutoDeleteRuntime(plugin, settings, adapter=current.adapter)
    from .auto_delete_config import condition_signature

    same_rules = {rule.id for rule in settings.rules if any(
        other.id == rule.id and condition_signature(settings, rule) == condition_signature(current.settings, other)
        for other in current.settings.rules)}
    transient.samples = {key: deepcopy(value) for key, value in current.samples.items() if key.split(":", 1)[0] in same_rules}
    entries, errors, _ = transient.scan(preview=True)
    return Result(state="preview", matches=entries, errors=errors,
                  summary=transient.scan_summary, matches_total=transient.scan_summary.matched,
                  truncated=len(entries) >= PREVIEW_MAX_ITEMS)


def request_run(plugin):
    """宿主一次性调度受理，不重建周期任务；重复点击只返回已有批次。"""
    runtime = runtime_of(plugin)
    runtime.check()
    with runtime.store.lock:
        if runtime.running or runtime.once_pending:
            return Result(state="running", run_id=runtime.run_id, message="已有扫描正在运行或等待执行")
        runtime.once_pending = True
        runtime.run_id = uuid4().hex
        try:
            accepted = add_plugin_once_job(plugin.__class__.__name__, "AutoDeleteOnce", plugin._scan_auto_delete,
                                           "自动删除手动扫描", delay_seconds=0,
                                           func_kwargs={"automatic": False, "runtime_token": runtime.token,
                                                        "run_id": runtime.run_id})
        except Exception:
            runtime.once_pending = False
            raise
        if not accepted:
            runtime.once_pending = False
            raise ValueError("宿主调度器未受理扫描，请稍后重试")
    return Result(state="accepted", run_id=runtime.run_id, message="已受理扫描，请查看运行结果")


def stop_runtime(plugin):
    """取消未执行的手动任务，不撤销已有保护或恢复种子。"""
    runtime = getattr(plugin, "_auto_delete_runtime", None)
    if runtime:
        runtime.stop.set()
        runtime.samples.clear()
        if runtime.once_pending:
            remove_plugin_once_job(plugin.__class__.__name__, "AutoDeleteOnce")
            runtime.once_pending = False


def service_declaration(plugin):
    """所有规则共用宿主周期服务，只有满足总门禁才登记。"""
    runtime = getattr(plugin, "_auto_delete_runtime", None)
    if (not runtime or runtime.stop.is_set() or not getattr(plugin, "_enabled", False)
            or not runtime.settings.enabled or not any(rule.enabled for rule in runtime.settings.rules)):
        return []
    trigger = (IntervalTrigger(minutes=runtime.settings.interval_minutes,
                               start_date=datetime.fromtimestamp(runtime.next_due, TZ))
               if runtime.settings.schedule_type == "interval" else CronTrigger.from_crontab(runtime.settings.cron, timezone=TZ))
    return [{"id": "AutoDeleteScan", "name": "自动删除规则扫描", "trigger": trigger,
             "func": plugin._scan_auto_delete,
             "kwargs": {"max_instances": 1, "coalesce": True, "misfire_grace_time": 1}}]


def status_result(plugin):
    """只读投影当前状态及摘要，尚未查询的能力保持未知。"""
    runtime = getattr(plugin, "_auto_delete_runtime", None)
    if runtime is None:
        error = getattr(plugin, "_auto_delete_error", "")
        return Status(state="error" if error else "disabled", error=error).model_dump(mode="json")
    try:
        status = runtime.store.status()
        index = runtime.store.index()
        blocks = runtime.store.blocks()
    except (StorageError, ValueError, TypeError) as error:
        return Status(state="error", enabled=runtime.settings.enabled, error=safe_error(error)).model_dump(mode="json")
    rules = [rule for rule in runtime.settings.rules if rule.enabled]
    active = bool(runtime.settings.enabled and getattr(plugin, "_enabled", False) and rules and not runtime.stop.is_set())
    fault = runtime.error or getattr(plugin, "_auto_delete_storage_fault", "") or getattr(plugin, "_auto_delete_error", "")
    if fault and runtime.stop.is_set():
        state = "error"
    elif not active:
        state = "disabled"
    elif runtime.running:
        state = "running"
    else:
        state = status.get("state", "idle")
    payload = {**status, "state": state, "enabled": runtime.settings.enabled, "active": active,
               "error": fault, "run_id": runtime.run_id or status.get("run_id", ""),
               "stage": runtime.stage if runtime.running else status.get("stage", "idle"),
               "once_pending": runtime.once_pending, "next_run": runtime.next_due if active else None,
               "rules": len(rules), "debug_rules": sum(rule.mode == "debug" for rule in rules),
               "delete_rules": sum(rule.mode == "delete" for rule in rules), "protected": len(blocks),
               "pending": sum(row["state"] in {"paused", "review"} or row["state"] in UNSETTLED_STATES for row in index.values()),
               "paused_total": sum(row["state"] == "paused" for row in index.values()),
               "removed_total": sum(row["state"] in {"removed", "deleted"} for row in index.values()),
               "history_days": runtime.settings.history_days, "schedule_type": runtime.settings.schedule_type,
               "interval_minutes": runtime.settings.interval_minutes, "sample_minutes": runtime.settings.sample_minutes}
    return Status.model_validate(payload).model_dump(mode="json")


from .auto_delete_config import (
    activate_rule,
    apply_settings,
    config_result,
    initialize_runtime,
    save_settings,
    stop_module,
)

__all__ = ["activate_rule", "apply_settings", "config_result", "initialize_runtime", "save_settings", "stop_module"]
