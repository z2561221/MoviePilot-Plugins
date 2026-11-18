"""自动删除配置保存、关键条件修订和服务端正式确认。"""

from copy import deepcopy
from time import time

from app.sdk.logging import logger
from app.sdk.scheduler import remove_plugin_once_job, update_plugin_job

from ..model.auto_delete import (
    CONTROL_KEY,
    UNSETTLED_STATES,
    Result,
    Settings,
    config_values,
    settings_from_config,
)
from ..storage.auto_delete_jobs import AutoDeleteStore, StorageError
from .coordination import operation_lock


def condition_signature(settings, rule):
    """关键条件变化使确认失效，名称和总运行周期不改变规则语义。"""
    from ..model.auto_delete import digest

    return digest({"rule": rule.model_dump(exclude={"name", "mode", "enabled", "revision"}),
                   "order": [item.id for item in settings.rules],
                   "source_paths": settings.source_paths if rule.action == "data" else [],
                   "exclude_paths": settings.exclude_paths if rule.action == "data" else []})


def normalize_revisions(settings, previous, control):
    """关键修改产生服务器修订，普通保存永远不能提升正式模式。"""
    old_rules = {rule.id: rule for rule in previous.rules}
    for rule in settings.rules:
        old = old_rules.get(rule.id)
        changed = old is None or condition_signature(settings, rule) != condition_signature(previous, old)
        rule.revision = old.revision + 1 if old and changed else old.revision if old else 1
        if changed or old is None or rule.mode == "delete" and old.mode != "delete":
            rule.mode = "debug"
            control["approvals"].pop(rule.id, None)
            control["debug_scans"].pop(rule.id, None)
    existing_ids = {rule.id for rule in settings.rules}
    for field in ("approvals", "debug_scans"):
        control[field] = {key: value for key, value in control[field].items() if key in existing_ids}


def retained_rule_samples(samples, old_settings, settings):
    """只继承仍启用且同修订、同模式的规则，单条规则的修改不清空其他规则。"""
    previous = {rule.id: rule for rule in old_settings.rules}
    eligible = {rule.id for rule in settings.rules if rule.enabled and rule.id in previous
                and rule.model_dump(exclude={"name"}) == previous[rule.id].model_dump(exclude={"name"})}
    return {key: deepcopy(value) for key, value in samples.items() if key.partition(":")[0] in eligible}


def replace_runtime(plugin, old, settings, *, keep_samples=False):
    """替换实例运行态时不复用旧写入门禁，纯文案保存保留周期和有效样本。"""
    from .auto_delete import AutoDeleteRuntime

    clone_adapter = getattr(old.adapter, "for_runtime", None)
    runtime = AutoDeleteRuntime(plugin, settings, adapter=old.adapter if clone_adapter is None else None)
    if clone_adapter is not None:
        runtime.adapter = clone_adapter(runtime.check)
    schedule_names = ("enabled", "schedule_type", "interval_minutes", "cron", "sample_minutes")
    same_schedule = all(getattr(old.settings, key) == getattr(settings, key) for key in schedule_names)
    same_registration = any(rule.enabled for rule in old.settings.rules) == any(rule.enabled for rule in settings.rules)
    if same_schedule and same_registration:
        runtime.next_due = old.next_due
    if keep_samples and same_schedule and settings.enabled and old.run_lock.acquire(blocking=False):
        try:
            runtime.samples = retained_rule_samples(old.samples, old.settings, settings)
        finally:
            old.run_lock.release()
    plugin._auto_delete_runtime = runtime
    plugin._auto_delete_enabled = settings.enabled
    plugin._auto_delete_error = ""
    if not same_schedule or not same_registration:
        update_plugin_job(plugin.__class__.__name__)
    return runtime


def persist_config(plugin, old, settings, control):
    """先撤销旧执行准入；保存结果未知时保留停止，不能沿用旧确认。"""
    old.stop.set()
    if old.once_pending:
        remove_plugin_once_job(plugin.__class__.__name__, "AutoDeleteOnce")
        old.once_pending = False
    latest = plugin.get_config()
    if not isinstance(latest, dict) or settings_from_config(latest) != old.settings:
        raise ValueError("插件设置已被其他页面修改，请刷新后保存")
    old.store.write(CONTROL_KEY, control)
    payload = deepcopy(latest)
    payload.update(config_values(settings, control["revision"]))
    try:
        result = plugin.update_config(config=payload)
        observed = plugin.get_config()
    except Exception as error:
        old.store.mark_fault("自动删除配置保存结果未知")
        raise StorageError("自动删除配置保存结果未知") from error
    if result is False or not isinstance(observed, dict) or settings_from_config(observed) != settings:
        old.store.fail("自动删除配置保存未确认")


def config_result(plugin):
    """查询不会刷新运行态或偷偷修订配置。"""
    from .auto_delete import runtime_of

    runtime = runtime_of(plugin)
    control = runtime.store.control()
    return Result(revision=control["revision"], settings=runtime.settings,
                  approvals=control["approvals"], debug_scans=control["debug_scans"])


def save_settings(plugin, request):
    """保存前核对当前修订，规则更改不能继承原正式确认。"""
    from .auto_delete import runtime_of

    old = runtime_of(plugin)
    if request.expected_revision != old.store.control()["revision"]:
        raise ValueError("配置修订已变化，请刷新后保存")
    settings = request.settings.model_copy(deep=True)
    with operation_lock(plugin), old.store.lock:
        if getattr(plugin, "_auto_delete_runtime", None) is not old:
            raise ValueError("页面对应运行态已变化，请刷新后保存")
        control = old.store.control()
        if request.expected_revision != control["revision"]:
            raise ValueError("配置修订已变化，请刷新后保存")
        normalize_revisions(settings, old.settings, control)
        control.update(schema_version=1, revision=control["revision"] + 1,
                       config=settings.model_dump(mode="json"))
        persist_config(plugin, old, settings, control)
        if old.settings.enabled and not settings.enabled:
            mark_pending_review(old.store, approved_only=True)
        replace_runtime(plugin, old, settings, keep_samples=True)
    return config_result(plugin)


def activate_rule(plugin, request):
    """批准未来规则与所选旧暂停任务分别绑定，接口不进行暂停或删除。"""
    from .auto_delete import evidence_digest, rule_fingerprint, runtime_of

    old = runtime_of(plugin)
    with operation_lock(plugin), old.store.lock:
        old.check_config()
        control = old.store.control()
        if request.expected_revision != control["revision"]:
            raise ValueError("规则配置已变化，请刷新后确认")
        settings = old.settings.model_copy(deep=True)
        rule = next((item for item in settings.rules if item.id == request.rule_id), None)
        if rule is None or not rule.enabled:
            raise ValueError("请先保存并启用暂停调试规则")
        fingerprint = rule_fingerprint(settings, rule, old.bindings([rule]))
        scan = control["debug_scans"].get(rule.id)
        if not scan or scan["fingerprint"] != fingerprint or scan["revision"] != rule.revision:
            raise ValueError("当前规则尚未成功完成暂停调试扫描")
        if request.job_ids and not request.accept_history:
            raise ValueError("须明确接受选定任务暂停前的采样证据")
        index = old.store.index()
        jobs = []
        for job_id in dict.fromkeys(request.job_ids):
            job = old.store.get(job_id, index=index)
            if (job["rule_id"] != rule.id or job["revision"] != rule.revision
                    or job["state"] not in {"paused", "review"} or job["interfered"]
                    or job["rule_fingerprint"] != fingerprint
                    or job["stage"] not in {"paused", "approved"}
                    or any(item["deleted"] for item in job["files"])):
                raise ValueError("暂停任务不属于当前规则，或已有操作结果需要另行复核")
            version = evidence_digest(job)
            if (not version or version != job["evidence_fingerprint"]
                    or request.evidence_versions.get(job_id) != version):
                raise ValueError("所选任务证据已变化，请刷新并重新核对")
            jobs.append(job)
        rule.mode = "delete"
        control["approvals"][rule.id] = {"revision": rule.revision, "fingerprint": fingerprint,
                                         "confirmed_at": time()}
        control.update(schema_version=1, revision=control["revision"] + 1, config=settings.model_dump(mode="json"))
        persist_config(plugin, old, settings, control)
        for job in jobs:
            job.update(state="approved", stage="approved", mode="delete", accepted_at=time(),
                       accepted_fingerprint=job["evidence_fingerprint"], error="")
            old.store.save(job)
            old.store.protect(job)
        replace_runtime(plugin, old, settings)
    return config_result(plugin)


def apply_settings(plugin, settings):
    """兼容内部显式设置入口，使用相同的修订和正式模式门禁。"""
    from ..model.auto_delete import SaveRequest

    return save_settings(plugin, SaveRequest(expected_revision=AutoDeleteStore(plugin).control()["revision"], settings=settings))


def mark_pending_review(store, *, approved_only=False):
    """停止/重载后只标记已索引任务，不恢复孤立意图或触发删种。"""
    index = store.recover_index()
    blocks = store.blocks()
    for key, row in index.items():
        if (row["state"] == "approved" or not approved_only and row["state"] in UNSETTLED_STATES
                or not approved_only and row["state"] in {"removed", "deleted", "released", "absent"} and key in blocks):
            job = store.get(key, index=index)
            job.update(state="review", error="停止或重载前未决任务须重新核对")
            store.save(job)
            store.protect(job)


def stop_module(plugin):
    """停止总闸先取消副作用准入，保存不等待当前网络请求完成。"""
    from .auto_delete import runtime_of

    old = runtime_of(plugin)
    old.stop.set()
    with old.store.lock:
        control = old.store.control()
        settings = old.settings.model_copy(deep=True)
        settings.enabled = False
        control.update(schema_version=1, revision=control["revision"] + 1, config=settings.model_dump(mode="json"))
        persist_config(plugin, old, settings, control)
        mark_pending_review(old.store, approved_only=True)
        replace_runtime(plugin, old, settings)
    return config_result(plugin)


def initialize_runtime(plugin, config, *, retained_samples=None):
    """重载时检查配置及已索引证据，合法确认可保留但旧操作不重放。"""
    from .auto_delete import ApprovalInvalid, AutoDeleteRuntime

    store = AutoDeleteStore(plugin)
    previous_runtime = getattr(plugin, "_auto_delete_runtime", None)
    plugin._auto_delete_storage_fault = ""
    plugin._auto_delete_error = ""
    try:
        settings = settings_from_config(config)
        original_settings = settings.model_copy(deep=True)
        control = store.control()
        previous = Settings.model_validate(control["config"]) if control["config"] else Settings()
        supplied_revision = config.get("auto_delete_config_revision")
        stale = (bool(control["config"]) and bool(config) and settings != previous
                 and supplied_revision != control["revision"])
        if stale:
            settings = previous.model_copy(deep=True)
            if not config.get("enabled"):
                settings.enabled = False
        normalize_revisions(settings, previous, control)
        runtime = AutoDeleteRuntime(plugin, settings)
        if (previous_runtime is not None and not previous_runtime.running
                and all(getattr(previous_runtime.settings, key) == getattr(settings, key)
                        for key in ("enabled", "schedule_type", "interval_minutes", "cron", "sample_minutes"))):
            runtime.next_due = previous_runtime.next_due
            if retained_samples is not None and settings.enabled and config.get('enabled'):
                runtime.samples = retained_rule_samples(retained_samples, previous_runtime.settings, settings)
        plugin._auto_delete_runtime = runtime
        for rule in settings.rules:
            if rule.mode == "delete":
                try:
                    runtime.validate_approval(rule)
                except ApprovalInvalid:
                    rule.mode = "debug"
                    control["approvals"].pop(rule.id, None)
                    control["debug_scans"].pop(rule.id, None)
        if control["config"] != settings.model_dump(mode="json"):
            control.update(schema_version=1, revision=control["revision"] + 1, config=settings.model_dump(mode="json"))
            store.write(CONTROL_KEY, control)
        if settings != original_settings or supplied_revision != control["revision"]:
            current = plugin.get_config()
            if isinstance(current, dict) and settings_from_config(current) != original_settings:
                raise ValueError("初始化期间配置已变化，停止自动删除")
            config.update(config_values(settings, control["revision"]))
            if plugin.update_config(config=config) is False or settings_from_config(plugin.get_config()) != settings:
                store.fail("自动删除规范配置回写未确认")
        mark_pending_review(store)
        plugin._auto_delete_enabled = settings.enabled
        return config
    except (ValueError, RuntimeError, TypeError, OSError, KeyError, AttributeError) as error:
        plugin._auto_delete_enabled = False
        runtime = getattr(plugin, "_auto_delete_runtime", None)
        if runtime:
            runtime.stop.set()
        from ..adapter.auto_delete import safe_error

        plugin._auto_delete_error = safe_error(error)
        logger.error("自动删除配置或持久化状态无法核验，模块保持停止")
        return config
