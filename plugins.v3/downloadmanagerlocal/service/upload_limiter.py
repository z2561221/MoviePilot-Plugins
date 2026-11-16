"""上传限速扫描、分配、持久化与恢复服务。"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Any, Iterable

from ..adapter.upload_limit import (
    global_settings_equal,
    global_settings_from_dict,
    list_upload_torrents,
    read_global_upload_settings,
    restore_global_upload_settings,
    restore_torrent_upload_settings,
    settings_from_dict,
)
from ..model.state import UPLOAD_LIMIT_STATE_KEY
from ..model.upload_limit import (
    UPLOAD_LIMIT_FAILURE_NOTIFY_THRESHOLD,
    UploadPool,
    migrate_upload_limit_state,
)
from ..model.upload_scan import UploadDownloaderContext
from ..utils.config import is_upload_limit_active, normalize_upload_limit_config
from .upload_allocator import select_probe_keys
from .upload_limit_apply import apply_torrent_limits, matches_managed_settings
from .upload_limit_plan import (
    allocate_upload_plan,
    next_probe_budget,
    prepare_pool_inputs,
    resolve_pool_demands,
    task_upload_rates,
)
from .upload_limit_scan import classify_upload_tasks, scan_downloader
from .upload_limit_scan import downloader_type as _downloader_type
from .upload_limit_summary import (
    build_downloader_only_summary as _build_downloader_only_summary,
)
from .upload_limit_summary import build_site_summary

logger = logging.getLogger(__name__)
_LOCK_GUARD = threading.RLock()
_CURRENT_CYCLE = ContextVar("downloadmanager_upload_cycle", default=None)


class UploadCycleStopped(RuntimeError):
    """上传限速轮次所属代次已停止。"""


def _cycle_checkpoint() -> None:
    """拒绝旧代次后续读写，重新启用不能复活已经停止的轮次。"""
    current = _CURRENT_CYCLE.get()
    if current is None:
        return
    plugin, generation, stop_event = current
    if (generation != int(getattr(plugin, "_transfer_stop_generation", 0) or 0)
            or (stop_event is not None and stop_event.is_set())
            or not is_upload_limit_active(plugin)):
        raise UploadCycleStopped("上传限速轮次已停止")


def _cancellable_cycle(callback):
    """绑定轮次的停止信号并将正常取消转换为状态回执。"""
    @wraps(callback)
    def run(plugin, *args, **kwargs):
        """执行一个能够在外部调用之间停止的限速轮次。"""
        token = _CURRENT_CYCLE.set((
            plugin,
            int(getattr(plugin, "_transfer_stop_generation", 0) or 0),
            getattr(plugin, "_upload_limit_stop_event", None),
        ))
        try:
            return callback(plugin, *args, **kwargs)
        except UploadCycleStopped:
            return {**get_upload_limit_status(plugin), "service_status": "stopped"}
        finally:
            _CURRENT_CYCLE.reset(token)
    return run


@contextmanager
def _active_cycle_lock(plugin):
    """等锁期间响应停止，获得锁后再次核对代次。"""
    lock = _cycle_lock(plugin)
    while True:
        _cycle_checkpoint()
        if lock.acquire(timeout=0.1):
            break
    try:
        _cycle_checkpoint()
        yield
    finally:
        lock.release()


def load_upload_limit_state(plugin: Any) -> dict:
    """读取并迁移上传限速运行态，迁移异常时进入安全空状态。"""
    cached = getattr(plugin, "_upload_limit_state", None)
    if isinstance(cached, dict):
        return cached
    raw_value = plugin.get_data(UPLOAD_LIMIT_STATE_KEY)
    try:
        state = migrate_upload_limit_state(raw_value)
        plugin._upload_limit_state_error = ""
    except ValueError as error:
        state = migrate_upload_limit_state(None)
        plugin._upload_limit_state_error = str(error)
        logger.error("上传限速状态迁移失败：%s", error)
    plugin._upload_limit_state = state
    if raw_value != state and not getattr(plugin, "_upload_limit_state_error", ""):
        plugin.save_data(UPLOAD_LIMIT_STATE_KEY, state)
    return state


def save_upload_limit_state(plugin: Any, state: dict) -> None:
    """保存当前上传限速运行态并更新插件实例缓存。"""
    _cycle_checkpoint()
    state["schema_version"] = 1
    plugin._upload_limit_state = state
    if getattr(plugin, "_upload_limit_state_error", ""):
        logger.error("上传限速状态存在迁移错误，拒绝覆盖原始持久化数据")
        return
    plugin.save_data(UPLOAD_LIMIT_STATE_KEY, state)


@_cancellable_cycle
def run_upload_limit_cycle(
    plugin: Any,
    *,
    now: float | None = None,
    reason: str = "scheduled",
) -> dict:
    """执行一轮全局限速、宽限识别、站点分配与单种限速协调。"""
    timestamp = float(now if now is not None else time.time())
    if not is_upload_limit_active(plugin):
        return get_upload_limit_status(plugin)
    with _active_cycle_lock(plugin):
        if not is_upload_limit_active(plugin):
            return get_upload_limit_status(plugin)
        state = load_upload_limit_state(plugin)
        if getattr(plugin, "_upload_limit_state_error", ""):
            status = get_upload_limit_status(plugin, state=state)
            status["service_status"] = "error"
            status["errors"] = [str(plugin._upload_limit_state_error)]
            return status
        selected = _selected_downloaders(plugin)
        caps = _downloader_caps(plugin, selected)
        site_rules = _site_rules(plugin)
        limited_site_rules = {
            site_name: rule
            for site_name, rule in site_rules.items()
            if int(rule.get("limit_kib") or 0) > 0
        }
        site_policy_enabled = bool(limited_site_rules)
        tag_prefix = str(getattr(plugin, "_tag_siteprefix", "🏠") or "🏠")
        first_activation = not bool(state.get("management_active"))
        if first_activation:
            state["management_active"] = True
            state["activated_at"] = timestamp
        state["cycle"] = int(state.get("cycle") or 0) + 1
        state["last_run_at"] = timestamp
        cycle = int(state["cycle"])
        errors: dict[str, list[str]] = defaultdict(list)

        removed = sorted(set((state.get("downloaders") or {})) - set(selected))
        for downloader_id in removed:
            restore_result = _restore_one_downloader(plugin, state, downloader_id)
            if restore_result["errors"]:
                errors[downloader_id].extend(restore_result["errors"])

        contexts: dict[str, UploadDownloaderContext] = {}
        regular_tasks: dict[str, Any] = {}
        grace_tasks: dict[str, Any] = {}
        torrent_state = state.setdefault("torrents", {})
        downloader_state = state.setdefault("downloaders", {})

        for downloader_id in selected:
            _cycle_checkpoint()
            try:
                context = scan_downloader(plugin, downloader_id, caps[downloader_id],
                                          downloader_state, timestamp, _cycle_checkpoint)
                contexts[downloader_id] = context
                entry = downloader_state[downloader_id]
                if not site_policy_enabled:
                    release_result = _release_downloader_torrent_limits(
                        state=state, downloader_id=downloader_id,
                        instance=context.service.instance, downloader_type=context.downloader_type,
                        snapshots=context.all_snapshots,
                    )
                    if release_result["errors"]:
                        errors[downloader_id].extend(release_result["errors"])
                    # 保留“待重新启用时全量扫描”的标志，避免清空策略期间新增任务获得宽限。
                    entry["initial_scan_complete"] = False
                    entry["per_torrent_management_active"] = False
                    continue
                classify_upload_tasks(
                    plugin, context, torrent_state, limited_site_rules, tag_prefix,
                    timestamp, first_activation, _resolve_limited_site, _release_torrent_record,
                    regular_tasks, grace_tasks, errors[downloader_id],
                )
                entry["initial_scan_complete"] = True
                entry["per_torrent_management_active"] = True
            except UploadCycleStopped:
                raise
            except Exception as error:
                _cycle_checkpoint()
                errors[downloader_id].append(str(error))
                logger.exception("上传限速扫描下载器 %s 失败", downloader_id)

        if not site_policy_enabled:
            for downloader_id in selected:
                if errors.get(downloader_id):
                    _record_downloader_failure(
                        plugin, state, downloader_id, "; ".join(errors[downloader_id])
                    )
                else:
                    _clear_downloader_failure(state, downloader_id)
            summary = _build_downloader_only_summary(
                state=state,
                selected=selected,
                caps=caps,
                contexts=contexts,
                errors=errors,
                reason=reason,
            )
            state["last_summary"] = summary
            save_upload_limit_state(plugin, state)
            return summary

        upload_rates_bps = task_upload_rates(regular_tasks, grace_tasks, selected)
        pools, task_demands, probe_keys = _build_pools(
            regular_tasks,
            torrent_state,
            limited_site_rules,
            downloader_state=downloader_state,
            downloader_caps_kib=caps,
            upload_rates_bps=upload_rates_bps,
            cycle=cycle,
        )
        allocation = allocate_upload_plan(
            pools, task_demands, probe_keys, caps, limited_site_rules, cycle=cycle,
        )

        apply_torrent_limits(regular_tasks, contexts, torrent_state, allocation.task_limits,
                             timestamp, _cycle_checkpoint, errors)

        for downloader_id in selected:
            if errors.get(downloader_id):
                _record_downloader_failure(
                    plugin, state, downloader_id, "; ".join(errors[downloader_id])
                )
            else:
                _clear_downloader_failure(state, downloader_id)

        summary = _build_summary(
            plugin=plugin,
            state=state,
            selected=selected,
            caps=caps,
            contexts=contexts,
            regular_tasks=regular_tasks,
            grace_tasks=grace_tasks,
            pool_allocations=allocation.pool_allocations,
            site_rules=limited_site_rules,
            probing_task_keys=allocation.probing_task_keys,
            errors=errors,
            reason=reason,
        )
        state["last_summary"] = summary
        save_upload_limit_state(plugin, state)
        return summary


def restore_upload_limits(
    plugin: Any,
    downloader_ids: Iterable[str] | None = None,
) -> dict:
    """按 compare-and-set 恢复接管前限速，用户后改值保持不动。"""
    with _cycle_lock(plugin):
        state = load_upload_limit_state(plugin)
        if getattr(plugin, "_upload_limit_state_error", ""):
            return {
                "code": 1,
                "msg": "上传限速状态无法安全恢复，已保留原始数据",
                "downloaders": [],
                "errors": [str(plugin._upload_limit_state_error)],
            }
        available = set((state.get("downloaders") or {}).keys())
        targets = available if downloader_ids is None else {
            str(value or "").strip() for value in downloader_ids
        } & available
        reports = []
        for downloader_id in sorted(targets):
            reports.append(_restore_one_downloader(plugin, state, downloader_id))
        if not (state.get("downloaders") or {}):
            state["management_active"] = False
            state["activated_at"] = 0.0
        errors = [
            f"{item['downloader_id']}: {error}"
            for item in reports
            for error in item["errors"]
        ]
        result = {
            "code": 0 if not errors else 2,
            "msg": "上传限速已恢复" if not errors else "部分限速恢复失败",
            "downloaders": reports,
            "errors": errors,
        }
        state["last_summary"] = {
            **get_upload_limit_status(plugin, state=state),
            "service_status": "disabled" if not errors else "degraded",
            "errors": errors,
        }
        save_upload_limit_state(plugin, state)
        return result


def scan_upload_limit_site_tags(
    plugin: Any,
    downloader_ids: Iterable[str] | None = None,
) -> dict:
    """只读扫描所选下载器中可用于站点规则的唯一前缀标签。"""
    selected = list(downloader_ids or _selected_downloaders(plugin))
    tag_prefix = str(getattr(plugin, "_tag_siteprefix", "🏠") or "🏠")
    sites: dict[str, dict] = {}
    errors = []
    for downloader_id in selected:
        clean_id = str(downloader_id or "").strip()
        if not clean_id:
            continue
        try:
            service = plugin.service_info(clean_id)
            if not service or not getattr(service, "instance", None):
                raise RuntimeError("下载器不可用")
            downloader_type = _downloader_type(service)
            snapshots, poll_error = list_upload_torrents(
                service.instance, clean_id, downloader_type
            )
            if poll_error:
                raise RuntimeError(poll_error)
            for snapshot in snapshots:
                if not snapshot.completed:
                    continue
                for label in snapshot.labels:
                    site_name = _site_name_from_label(label, tag_prefix)
                    if not site_name:
                        continue
                    item = sites.setdefault(site_name, {
                        "name": site_name,
                        "label": f"{tag_prefix}{site_name}",
                        "task_count": 0,
                        "downloaders": set(),
                    })
                    item["task_count"] += 1
                    item["downloaders"].add(clean_id)
        except UploadCycleStopped:
            raise
        except Exception as error:
            _cycle_checkpoint()
            errors.append({"downloader": clean_id, "message": str(error)})
    items = []
    for item in sorted(sites.values(), key=lambda value: value["name"].lower()):
        items.append({
            **item,
            "downloaders": sorted(item["downloaders"]),
        })
    return {
        "code": 0 if not errors else (2 if items else 1),
        "msg": "站点标签扫描完成" if items or not errors else "站点标签扫描失败",
        "items": items,
        "errors": errors,
    }


def persist_upload_limit_site_rules(plugin: Any, site_rules: Any) -> dict[str, dict]:
    """立即持久化站点策略并同步当前运行态。"""
    config = dict(plugin.get_config() or {})
    config["upload_limit_site_rules"] = site_rules if isinstance(site_rules, dict) else {}
    normalized = normalize_upload_limit_config(config)
    clean_rules = normalized["upload_limit_site_rules"]
    config["upload_limit_site_rules"] = clean_rules
    if plugin.update_config(config=config) is False:
        raise RuntimeError("站点策略保存失败")
    plugin._upload_limit_site_rules = clean_rules
    if not any(int(rule.get("limit_kib") or 0) > 0 for rule in clean_rules.values()):
        state = load_upload_limit_state(plugin)
        for entry in (state.get("downloaders") or {}).values():
            if not isinstance(entry, dict):
                continue
            entry["initial_scan_complete"] = False
            entry["per_torrent_management_active"] = False
            for key in (
                "auto_probe_count",
                "probe_low_utilization_cycles",
                "probe_reduction_pending",
                "last_probe_keys",
            ):
                entry.pop(key, None)
        save_upload_limit_state(plugin, state)
    return clean_rules


def get_upload_limit_status(plugin: Any, *, state: dict | None = None) -> dict:
    """返回配置页可展示的上传限速持久化状态。"""
    runtime = state if isinstance(state, dict) else load_upload_limit_state(plugin)
    last_summary = runtime.get("last_summary")
    summary = dict(last_summary) if isinstance(last_summary, dict) else {}
    configured = is_upload_limit_active(plugin)
    enabled = bool(getattr(plugin, "_upload_limit_enabled", False))
    selected = _selected_downloaders(plugin) if enabled else []
    empty_metrics = {
        "downloaders": [],
        "sites": [],
        "errors": [],
        "managed_torrents": 0,
        "grace_torrents": 0,
        "uploading_torrents": 0,
        "probing_torrents": 0,
        "protected_torrents": 0,
        "upload_rate_bps": 0,
        "allocated_kib": 0,
    }
    if not summary:
        summary = {
            **empty_metrics,
            "service_status": "starting" if configured else "disabled",
        }
    summary.update({
        "enabled": enabled,
        "active": bool(configured and runtime.get("management_active")),
        "selected_downloaders": selected,
        "cycle": int(runtime.get("cycle") or 0),
        "last_run_at": float(runtime.get("last_run_at") or 0),
        "state_error": str(getattr(plugin, "_upload_limit_state_error", "") or ""),
    })
    if not configured:
        summary.update(empty_metrics)
        summary["service_status"] = "disabled"
    return summary


def _build_pools(
    regular_tasks: dict[str, Any], torrent_state: dict, site_rules: dict[str, dict], *,
    downloader_state: dict[str, dict], downloader_caps_kib: dict[str, int],
    upload_rates_bps: dict[str, int], cycle: int,
) -> tuple[list[UploadPool], dict[str, int | None], set[str]]:
    """协调探测状态的更新顺序，池/额度计算不接触持久化或下载器。"""
    inputs = prepare_pool_inputs(regular_tasks, torrent_state)
    target_counts = {}
    for downloader_id in sorted(downloader_caps_kib):
        entry = downloader_state.setdefault(downloader_id, {})
        budget = next_probe_budget(
            entry, cap_kib=downloader_caps_kib.get(downloader_id, 0),
            candidates=int(inputs.candidate_counts.get(downloader_id, 0)),
            upload_rate_bps=upload_rates_bps.get(downloader_id, 0), cycle=cycle,
        )
        entry["auto_probe_count"] = budget.count
        entry["probe_low_utilization_cycles"] = budget.low_utilization_cycles
        entry["probe_reduction_pending"] = budget.reduction_pending
        target_counts[downloader_id] = budget.count
    probe_keys = select_probe_keys(
        inputs.pools, inputs.probe_candidates, cycle=cycle, target_counts=target_counts,
    )
    for downloader_id in downloader_caps_kib:
        downloader_state.setdefault(downloader_id, {})["last_probe_keys"] = sorted(
            key for key in probe_keys if regular_tasks[key].downloader_id == downloader_id
        )
    return resolve_pool_demands(inputs, probe_keys), inputs.demands, probe_keys




def _build_summary(*, plugin: Any, **inputs) -> dict:
    """兼容旧私有入口；摘要投影不读取插件或下载器。"""
    return build_site_summary(**inputs)


def _release_downloader_torrent_limits(
    *,
    state: dict,
    downloader_id: str,
    instance: Any,
    downloader_type: str,
    snapshots: dict[str, Any],
) -> dict:
    """退出站点策略模式时按 compare-and-set 释放该下载器单种限速。"""
    report = {"restored": 0, "preserved_manual": 0, "errors": []}
    task_records = {
        key: value for key, value in (state.get("torrents") or {}).items()
        if isinstance(value, dict) and value.get("downloader_id") == downloader_id
    }
    for task_key, record in task_records.items():
        snapshot = snapshots.get(task_key)
        if not snapshot:
            state.get("torrents", {}).pop(task_key, None)
            continue
        original = record.get("original_settings")
        try:
            if original and matches_managed_settings(record, snapshot.upload_settings):
                _cycle_checkpoint()
                restore_torrent_upload_settings(
                    instance,
                    downloader_type,
                    snapshot.torrent_hash,
                    settings_from_dict(original),
                )
                report["restored"] += 1
            else:
                report["preserved_manual"] += 1
            state.get("torrents", {}).pop(task_key, None)
        except UploadCycleStopped:
            raise
        except Exception as error:
            _cycle_checkpoint()
            report["errors"].append(f"{snapshot.torrent_hash}: {error}")
            logger.exception(
                "释放上传限速任务 %s/%s 失败",
                downloader_id,
                snapshot.torrent_hash,
            )
    return report


def _release_torrent_record(
    *,
    state: dict,
    task_key: str,
    record: dict,
    snapshot: Any,
    instance: Any,
    downloader_type: str,
) -> str:
    """任务退出受限站点时按 compare-and-set 恢复其原始单种设置。"""
    original = record.get("original_settings")
    try:
        if original and matches_managed_settings(record, snapshot.upload_settings):
            _cycle_checkpoint()
            restore_torrent_upload_settings(
                instance,
                downloader_type,
                snapshot.torrent_hash,
                settings_from_dict(original),
            )
        state.get("torrents", {}).pop(task_key, None)
        return ""
    except UploadCycleStopped:
        raise
    except Exception as error:
        _cycle_checkpoint()
        logger.exception(
            "释放上传限速任务 %s/%s 失败",
            snapshot.downloader_id,
            snapshot.torrent_hash,
        )
        return f"{snapshot.torrent_hash}: {error}"


def _restore_one_downloader(plugin: Any, state: dict, downloader_id: str) -> dict:
    """恢复一个下载器及其仍存在任务的接管前上传设置。"""
    entry = (state.get("downloaders") or {}).get(downloader_id)
    report = {
        "downloader_id": downloader_id,
        "global_restored": False,
        "torrent_restored": 0,
        "preserved_manual": 0,
        "errors": [],
    }
    if not isinstance(entry, dict):
        return report
    try:
        service = plugin.service_info(downloader_id)
        if not service or not getattr(service, "instance", None):
            raise RuntimeError("下载器不可用")
        downloader_type = str(entry.get("downloader_type") or _downloader_type(service))
        current_global = read_global_upload_settings(service.instance, downloader_type)
        last_global = entry.get("last_written_global")
        original_global = entry.get("original_global")
        if last_global and original_global and global_settings_equal(
            current_global,
            global_settings_from_dict(last_global, downloader_type),
        ):
            _cycle_checkpoint()
            restore_global_upload_settings(
                service.instance,
                downloader_type,
                global_settings_from_dict(original_global, downloader_type),
            )
            report["global_restored"] = True
        else:
            report["preserved_manual"] += 1

        snapshots, poll_error = list_upload_torrents(
            service.instance, downloader_id, downloader_type
        )
        if poll_error:
            raise RuntimeError(poll_error)
        current = {snapshot.key: snapshot for snapshot in snapshots}
        task_records = {
            key: value for key, value in (state.get("torrents") or {}).items()
            if isinstance(value, dict) and value.get("downloader_id") == downloader_id
        }
        for task_key, record in task_records.items():
            snapshot = current.get(task_key)
            if not snapshot:
                continue
            original = record.get("original_settings")
            if original and matches_managed_settings(record, snapshot.upload_settings):
                _cycle_checkpoint()
                restore_torrent_upload_settings(
                    service.instance,
                    downloader_type,
                    snapshot.torrent_hash,
                    settings_from_dict(original),
                )
                report["torrent_restored"] += 1
            else:
                report["preserved_manual"] += 1
    except UploadCycleStopped:
        raise
    except Exception as error:
        _cycle_checkpoint()
        report["errors"].append(str(error))
        logger.exception("恢复上传限速下载器 %s 失败", downloader_id)
        return report

    state.get("downloaders", {}).pop(downloader_id, None)
    for task_key, record in list((state.get("torrents") or {}).items()):
        if isinstance(record, dict) and record.get("downloader_id") == downloader_id:
            state["torrents"].pop(task_key, None)
    state.get("failures", {}).pop(downloader_id, None)
    return report


def _record_downloader_failure(
    plugin: Any,
    state: dict,
    downloader_id: str,
    error: str,
) -> None:
    """累计下载器连续失败，并在首次达到阈值时发送异常通知。"""
    failures = state.setdefault("failures", {})
    item = failures.setdefault(downloader_id, {})
    item["count"] = int(item.get("count") or 0) + 1
    item["last_error"] = str(error or "unknown error")
    item["updated_at"] = time.time()
    if item["count"] < UPLOAD_LIMIT_FAILURE_NOTIFY_THRESHOLD or item.get("notified"):
        return
    item["notified"] = True
    try:
        from app.schemas.types import MessageType

        plugin.post_message(
            mtype=MessageType.Plugin,
            title="下载中心上传限速异常",
            parse_mode="plain",
            text=(
                f"下载器：{downloader_id}\n"
                f"连续失败：{item['count']} 次\n"
                f"原因：{item['last_error']}"
            ),
        )
    except Exception:
        logger.exception("发送上传限速异常通知失败")


def _clear_downloader_failure(state: dict, downloader_id: str) -> None:
    """下载器本轮成功后清除连续失败和已通知标记。"""
    state.setdefault("failures", {}).pop(downloader_id, None)


def _resolve_limited_site(
    labels: Iterable[str],
    site_rules: dict[str, dict],
    prefix: str,
) -> str:
    """仅在恰好一个标签命中正数站点上限时返回站点名。"""
    site_names = [
        site_name for site_name in (
            _site_name_from_label(label, prefix) for label in labels
        ) if site_name
    ]
    if len(site_names) != 1 or site_names[0] not in site_rules:
        return ""
    return site_names[0]


def _site_name_from_label(label: Any, prefix: str) -> str:
    """从标签中提取不含前缀的站点名。"""
    text = str(label or "").strip()
    clean_prefix = str(prefix or "🏠")
    if not text.startswith(clean_prefix):
        return ""
    return text[len(clean_prefix):].strip()


def _selected_downloaders(plugin: Any) -> list[str]:
    """返回去重后的上传限速下载器列表。"""
    result = []
    for value in getattr(plugin, "_upload_limit_downloaders", []) or []:
        clean = str(value or "").strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def _downloader_caps(plugin: Any, selected: Iterable[str]) -> dict[str, int]:
    """读取所选下载器的正整数总上传上限。"""
    values = getattr(plugin, "_upload_limit_downloader_limits_kib", {}) or {}
    return {
        downloader_id: max(1, int(values.get(downloader_id) or 0))
        for downloader_id in selected
    }


def _site_rules(plugin: Any) -> dict[str, dict]:
    """读取并复制当前站点规则，避免协调过程修改配置对象。"""
    values = getattr(plugin, "_upload_limit_site_rules", {}) or {}
    return {
        str(site_name): dict(rule)
        for site_name, rule in values.items()
        if str(site_name or "").strip() and isinstance(rule, dict)
    }


def _cycle_lock(plugin: Any) -> threading.RLock:
    """获取插件实例独享的上传限速协调锁。"""
    lock = getattr(plugin, "_upload_limit_cycle_lock", None)
    if lock is None:
        with _LOCK_GUARD:
            lock = getattr(plugin, "_upload_limit_cycle_lock", None)
            if lock is None:
                lock = threading.RLock()
                plugin._upload_limit_cycle_lock = lock
    return lock


__all__ = (
    "get_upload_limit_status",
    "load_upload_limit_state",
    "restore_upload_limits",
    "run_upload_limit_cycle",
    "save_upload_limit_state",
    "scan_upload_limit_site_tags",
)
