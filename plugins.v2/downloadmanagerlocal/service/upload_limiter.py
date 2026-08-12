"""上传限速扫描、分配、持久化与恢复服务。"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any, Iterable

from ..adapter.upload_limit import (
    expected_global_upload_settings,
    expected_torrent_upload_settings,
    global_settings_equal,
    global_settings_from_dict,
    global_settings_to_dict,
    list_upload_torrents,
    read_global_upload_settings,
    restore_global_upload_settings,
    restore_torrent_upload_settings,
    settings_from_dict,
    settings_to_dict,
    torrent_settings_equal,
    write_global_upload_limit,
    write_torrent_upload_limit,
)
from ..model.state import UPLOAD_LIMIT_STATE_KEY
from ..model.upload_limit import (
    DEFAULT_SITE_KEY,
    DEFAULT_SITE_NAME,
    PRIORITY_MEDIUM,
    UPLOAD_LIMIT_FAILURE_NOTIFY_THRESHOLD,
    UploadPool,
    migrate_upload_limit_state,
    normalize_priority,
    pool_state_key,
)
from ..utils.config import is_upload_limit_active, normalize_upload_limit_config
from .upload_allocator import (
    aggregate_pool_demand_kib,
    allocate_task_limits,
    allocate_weighted_pools,
    estimate_task_demand_kib,
    is_task_probe_candidate,
)


logger = logging.getLogger(__name__)
_LOCK_GUARD = threading.RLock()


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
    if raw_value != state:
        plugin.save_data(UPLOAD_LIMIT_STATE_KEY, state)
    return state


def save_upload_limit_state(plugin: Any, state: dict) -> None:
    """保存当前上传限速运行态并更新插件实例缓存。"""
    state["schema_version"] = 1
    plugin._upload_limit_state = state
    plugin.save_data(UPLOAD_LIMIT_STATE_KEY, state)


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
    with _cycle_lock(plugin):
        state = load_upload_limit_state(plugin)
        selected = _selected_downloaders(plugin)
        caps = _downloader_caps(plugin, selected)
        site_rules = _site_rules(plugin)
        site_policy_enabled = bool(site_rules)
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

        contexts: dict[str, dict] = {}
        regular_tasks: dict[str, Any] = {}
        grace_tasks: dict[str, Any] = {}
        torrent_state = state.setdefault("torrents", {})
        downloader_state = state.setdefault("downloaders", {})

        for downloader_id in selected:
            try:
                service = plugin.service_info(downloader_id)
                if not service or not getattr(service, "instance", None):
                    raise RuntimeError("下载器不可用")
                downloader_type = _downloader_type(service)
                if downloader_type not in {"qbittorrent", "transmission"}:
                    raise RuntimeError(f"不支持的下载器类型：{downloader_type or 'unknown'}")
                current_global = read_global_upload_settings(
                    service.instance, downloader_type
                )
                entry = downloader_state.setdefault(downloader_id, {
                    "downloader_type": downloader_type,
                    "first_managed_at": timestamp,
                    "initial_scan_complete": False,
                })
                initial_scan_pending = not bool(entry.get("initial_scan_complete"))
                entry["downloader_type"] = downloader_type
                if "original_global" not in entry:
                    entry["original_global"] = global_settings_to_dict(current_global)
                last_global = entry.get("last_written_global")
                if last_global:
                    expected_last = global_settings_from_dict(last_global, downloader_type)
                    if not global_settings_equal(current_global, expected_last):
                        entry["original_global"] = global_settings_to_dict(current_global)
                desired_global = expected_global_upload_settings(
                    downloader_type, caps[downloader_id]
                )
                if not global_settings_equal(current_global, desired_global):
                    desired_global = write_global_upload_limit(
                        service.instance, downloader_type, caps[downloader_id]
                    )
                entry["last_written_global"] = global_settings_to_dict(desired_global)
                entry["total_limit_kib"] = caps[downloader_id]
                entry["last_seen_at"] = timestamp

                snapshots, poll_error = list_upload_torrents(
                    service.instance, downloader_id, downloader_type
                )
                if poll_error:
                    raise RuntimeError(poll_error)
                all_snapshots = {
                    snapshot.key: snapshot
                    for snapshot in snapshots
                    if snapshot.torrent_hash
                }
                completed = {
                    snapshot.key: snapshot
                    for snapshot in snapshots
                    if snapshot.completed and snapshot.torrent_hash
                }
                contexts[downloader_id] = {
                    "service": service,
                    "type": downloader_type,
                    "snapshots": completed,
                    "initial_scan_pending": initial_scan_pending,
                }
                if not site_policy_enabled:
                    release_result = _release_downloader_torrent_limits(
                        state=state,
                        downloader_id=downloader_id,
                        instance=service.instance,
                        downloader_type=downloader_type,
                        snapshots=all_snapshots,
                    )
                    if release_result["errors"]:
                        errors[downloader_id].extend(release_result["errors"])
                    entry["initial_scan_complete"] = True
                    entry["per_torrent_management_active"] = False
                    continue
                _drop_missing_torrent_state(torrent_state, downloader_id, set(completed))
                stock_scan = bool(first_activation or initial_scan_pending)
                for task_key, snapshot in completed.items():
                    record = torrent_state.get(task_key)
                    if not isinstance(record, dict):
                        completion_reference = max(
                            float(snapshot.completed_at or 0),
                            float(snapshot.added_at or 0),
                        ) or timestamp
                        grace_until = 0.0 if stock_scan else (
                            completion_reference
                            + max(0, int(getattr(
                                plugin, "_upload_limit_grace_minutes", 30
                            ) or 0)) * 60
                        )
                        record = {
                            "downloader_id": downloader_id,
                            "downloader_type": downloader_type,
                            "torrent_hash": snapshot.torrent_hash,
                            "first_seen_at": timestamp,
                            "completion_reference": completion_reference,
                            "grace_until": grace_until,
                            "original_settings": settings_to_dict(
                                snapshot.upload_settings
                            ),
                        }
                        torrent_state[task_key] = record
                    else:
                        last_written = record.get("last_written_settings")
                        if not last_written or not torrent_settings_equal(
                            snapshot.upload_settings,
                            settings_from_dict(last_written),
                        ):
                            record["original_settings"] = settings_to_dict(
                                snapshot.upload_settings
                            )
                    site_key, priority = _resolve_site_group(
                        snapshot.labels, site_rules, tag_prefix
                    )
                    record.update({
                        "downloader_id": downloader_id,
                        "downloader_type": downloader_type,
                        "torrent_hash": snapshot.torrent_hash,
                        "name": snapshot.name,
                        "labels": list(snapshot.labels),
                        "site_key": site_key,
                        "priority": priority,
                        "upload_rate_bps": snapshot.upload_rate_bps,
                        "upload_demand_peers": snapshot.upload_demand_peers,
                        "last_seen_at": timestamp,
                    })
                    if float(record.get("grace_until") or 0) > timestamp:
                        grace_tasks[task_key] = snapshot
                    else:
                        regular_tasks[task_key] = snapshot
                entry["initial_scan_complete"] = True
                entry["per_torrent_management_active"] = True
            except Exception as error:
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

        pools, task_demands, probe_keys = _build_pools(
            regular_tasks, torrent_state, site_rules
        )
        site_caps = {
            site_name: int(rule.get("limit_kib") or 0)
            for site_name, rule in site_rules.items()
            if int(rule.get("limit_kib") or 0) > 0
        }
        pool_allocations = allocate_weighted_pools(pools, caps, site_caps)
        desired_task_limits: dict[str, int] = {}
        for pool in pools:
            demands = {
                task_key: task_demands[task_key]
                for task_key in pool.task_keys
            }
            desired_task_limits.update(allocate_task_limits(
                pool_allocations.get(pool.key, 0),
                demands,
                cycle=cycle,
                probe_keys=set(pool.task_keys).intersection(probe_keys),
            ))
        probing_task_keys = {
            task_key for task_key in probe_keys
            if int(desired_task_limits.get(task_key, 0) or 0) > 0
        }

        for task_key, snapshot in regular_tasks.items():
            context = contexts.get(snapshot.downloader_id)
            if not context:
                continue
            desired_kib = max(0, int(desired_task_limits.get(task_key, 0)))
            expected = expected_torrent_upload_settings(
                snapshot.downloader_type, desired_kib
            )
            try:
                applied = expected
                if not torrent_settings_equal(snapshot.upload_settings, expected):
                    applied = write_torrent_upload_limit(
                        context["service"].instance,
                        snapshot.downloader_type,
                        snapshot.torrent_hash,
                        desired_kib,
                    )
                record = torrent_state[task_key]
                record["last_allocation_kib"] = desired_kib
                record["last_written_settings"] = settings_to_dict(applied)
                record["last_applied_at"] = timestamp
            except Exception as error:
                errors[snapshot.downloader_id].append(
                    f"{snapshot.torrent_hash}: {error}"
                )
                logger.exception(
                    "上传限速写入任务 %s/%s 失败",
                    snapshot.downloader_id,
                    snapshot.torrent_hash,
                )

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
            pool_allocations=pool_allocations,
            site_rules=site_rules,
            probing_task_keys=probing_task_keys,
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
        except Exception as error:
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
    return clean_rules


def get_upload_limit_status(plugin: Any, *, state: dict | None = None) -> dict:
    """返回配置页可展示的上传限速持久化状态。"""
    runtime = state if isinstance(state, dict) else load_upload_limit_state(plugin)
    last_summary = runtime.get("last_summary")
    summary = dict(last_summary) if isinstance(last_summary, dict) else {}
    configured = is_upload_limit_active(plugin)
    enabled = bool(getattr(plugin, "_upload_limit_enabled", False))
    selected = _selected_downloaders(plugin) if enabled else []
    if not summary:
        summary = {
            "service_status": "starting" if configured else "disabled",
            "downloaders": [],
            "sites": [],
            "errors": [],
            "managed_torrents": 0,
            "grace_torrents": 0,
            "upload_rate_bps": 0,
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
        summary["service_status"] = "disabled"
        summary["downloaders"] = []
        summary["sites"] = []
    return summary


def _build_pools(
    regular_tasks: dict[str, Any],
    torrent_state: dict,
    site_rules: dict[str, dict],
) -> tuple[list[UploadPool], dict[str, int | None], set[str]]:
    """把常规做种任务聚合为下载器/站点池并计算弹性需求。"""
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    demands: dict[str, int | None] = {}
    probe_keys: set[str] = set()
    for task_key, snapshot in regular_tasks.items():
        record = torrent_state[task_key]
        site_key = str(record.get("site_key") or DEFAULT_SITE_KEY)
        grouped[(snapshot.downloader_id, site_key)].append(task_key)
        previous = record.get("last_allocation_kib")
        demands[task_key] = estimate_task_demand_kib(
            snapshot.upload_rate_bps,
            None if previous is None else int(previous or 0),
            snapshot.upload_demand_peers,
        )
        if is_task_probe_candidate(
            snapshot.upload_rate_bps,
            None if previous is None else int(previous or 0),
            snapshot.upload_demand_peers,
        ):
            probe_keys.add(task_key)
    pools = []
    for (downloader_id, site_key), task_keys in sorted(grouped.items()):
        rule = site_rules.get(site_key) or {}
        priority = normalize_priority(rule.get("priority") or PRIORITY_MEDIUM)
        pools.append(UploadPool(
            key=pool_state_key(downloader_id, site_key),
            downloader_id=downloader_id,
            site_key=site_key,
            priority=priority,
            task_keys=tuple(sorted(task_keys)),
            current_rate_bps=sum(
                int(regular_tasks[key].upload_rate_bps or 0) for key in task_keys
            ),
            demand_kib=aggregate_pool_demand_kib(
                (demands[key] for key in task_keys if key not in probe_keys),
                probe_candidates=sum(key in probe_keys for key in task_keys),
            ),
        ))
    return pools, demands, probe_keys


def _build_downloader_only_summary(
    *,
    state: dict,
    selected: list[str],
    caps: dict[str, int],
    contexts: dict[str, dict],
    errors: dict[str, list[str]],
    reason: str,
) -> dict:
    """构造仅由下载器总上限接管时的运行摘要。"""
    downloader_items = []
    total_rate_bps = 0
    total_torrents = 0
    allocated_kib = 0
    default_downloaders = []
    for downloader_id in selected:
        context = contexts.get(downloader_id) or {}
        snapshots = list((context.get("snapshots") or {}).values())
        upload_rate_bps = sum(
            int(snapshot.upload_rate_bps or 0) for snapshot in snapshots
        )
        has_context = bool(context)
        item_allocated_kib = int(caps.get(downloader_id, 0) or 0) if has_context else 0
        if has_context:
            default_downloaders.append(downloader_id)
        total_rate_bps += upload_rate_bps
        total_torrents += len(snapshots)
        allocated_kib += item_allocated_kib
        downloader_items.append({
            "id": downloader_id,
            "type": str(context.get("type") or (
                (state.get("downloaders") or {}).get(downloader_id, {}).get("downloader_type")
                or ""
            )),
            "total_limit_kib": int(caps.get(downloader_id, 0) or 0),
            "upload_rate_bps": upload_rate_bps,
            "managed_torrents": len(snapshots),
            "grace_torrents": 0,
            "uploading_torrents": sum(
                1 for snapshot in snapshots
                if int(snapshot.upload_rate_bps or 0) > 0
            ),
            "probing_torrents": 0,
            "protected_torrents": 0,
            "allocated_kib": item_allocated_kib,
            "error": "; ".join(errors.get(downloader_id) or []),
        })

    flat_errors = [
        f"{downloader_id}: {message}"
        for downloader_id, messages in errors.items()
        for message in messages
    ]
    if flat_errors and len(contexts) < len(selected):
        service_status = "error" if not contexts else "degraded"
    elif flat_errors:
        service_status = "degraded"
    else:
        service_status = "running"
    sites = []
    if total_torrents:
        sites.append({
            "key": DEFAULT_SITE_KEY,
            "name": DEFAULT_SITE_NAME,
            "priority": PRIORITY_MEDIUM,
            "hard_limit_kib": 0,
            "allocated_kib": allocated_kib,
            "upload_rate_bps": total_rate_bps,
            "torrent_count": total_torrents,
            "downloaders": sorted(default_downloaders),
        })
    return {
        "enabled": True,
        "active": True,
        "mode": "downloader_only",
        "service_status": service_status,
        "reason": str(reason or "scheduled"),
        "selected_downloaders": list(selected),
        "downloaders": downloader_items,
        "sites": sites,
        "managed_torrents": total_torrents,
        "grace_torrents": 0,
        "uploading_torrents": sum(
            int(item.get("uploading_torrents") or 0)
            for item in downloader_items
        ),
        "probing_torrents": 0,
        "protected_torrents": 0,
        "upload_rate_bps": total_rate_bps,
        "allocated_kib": allocated_kib,
        "errors": flat_errors,
        "last_run_at": float(state.get("last_run_at") or 0),
        "cycle": int(state.get("cycle") or 0),
    }


def _build_summary(
    *,
    plugin: Any,
    state: dict,
    selected: list[str],
    caps: dict[str, int],
    contexts: dict[str, dict],
    regular_tasks: dict[str, Any],
    grace_tasks: dict[str, Any],
    pool_allocations: dict[str, int],
    site_rules: dict[str, dict],
    probing_task_keys: set[str],
    errors: dict[str, list[str]],
    reason: str,
) -> dict:
    """构造状态 UI 使用的下载器和站点实时摘要。"""
    torrent_state = state.get("torrents") or {}
    downloader_items = []
    for downloader_id in selected:
        context = contexts.get(downloader_id) or {}
        downloader_regular = [
            snapshot for snapshot in regular_tasks.values()
            if snapshot.downloader_id == downloader_id
        ]
        downloader_grace = [
            snapshot for snapshot in grace_tasks.values()
            if snapshot.downloader_id == downloader_id
        ]
        downloader_items.append({
            "id": downloader_id,
            "type": str(context.get("type") or (
                (state.get("downloaders") or {}).get(downloader_id, {}).get("downloader_type")
                or ""
            )),
            "total_limit_kib": int(caps.get(downloader_id, 0) or 0),
            "upload_rate_bps": sum(
                int(snapshot.upload_rate_bps or 0)
                for snapshot in downloader_regular + downloader_grace
            ),
            "managed_torrents": len(downloader_regular),
            "grace_torrents": len(downloader_grace),
            "uploading_torrents": sum(
                1 for snapshot in downloader_regular + downloader_grace
                if int(snapshot.upload_rate_bps or 0) > 0
            ),
            "probing_torrents": sum(
                1 for task_key in probing_task_keys
                if regular_tasks[task_key].downloader_id == downloader_id
            ),
            "protected_torrents": sum(
                1 for task_key, snapshot in regular_tasks.items()
                if snapshot.downloader_id == downloader_id
                and int((torrent_state.get(task_key) or {}).get("last_allocation_kib") or 0) == 0
            ),
            "allocated_kib": sum(
                int(record.get("last_allocation_kib") or 0)
                for record in torrent_state.values()
                if isinstance(record, dict)
                and record.get("downloader_id") == downloader_id
                and float(record.get("grace_until") or 0) <= float(state.get("last_run_at") or 0)
            ),
            "error": "; ".join(errors.get(downloader_id) or []),
        })

    site_items: dict[str, dict] = {}
    for task_key, snapshot in regular_tasks.items():
        record = torrent_state.get(task_key) or {}
        site_key = str(record.get("site_key") or DEFAULT_SITE_KEY)
        rule = site_rules.get(site_key) or {}
        item = site_items.setdefault(site_key, {
            "key": site_key,
            "name": DEFAULT_SITE_NAME if site_key == DEFAULT_SITE_KEY else site_key,
            "priority": normalize_priority(rule.get("priority") or PRIORITY_MEDIUM),
            "hard_limit_kib": int(rule.get("limit_kib") or 0),
            "allocated_kib": 0,
            "upload_rate_bps": 0,
            "torrent_count": 0,
            "uploading_torrents": 0,
            "probing_torrents": 0,
            "protected_torrents": 0,
            "downloaders": set(),
        })
        item["allocated_kib"] += int(record.get("last_allocation_kib") or 0)
        item["upload_rate_bps"] += int(snapshot.upload_rate_bps or 0)
        item["torrent_count"] += 1
        item["uploading_torrents"] += int(snapshot.upload_rate_bps or 0) > 0
        item["probing_torrents"] += task_key in probing_task_keys
        item["protected_torrents"] += int(record.get("last_allocation_kib") or 0) == 0
        item["downloaders"].add(snapshot.downloader_id)
    sites = []
    for item in sorted(
        site_items.values(),
        key=lambda value: (value["key"] == DEFAULT_SITE_KEY, value["name"].lower()),
    ):
        sites.append({**item, "downloaders": sorted(item["downloaders"])})

    flat_errors = [
        f"{downloader_id}: {message}"
        for downloader_id, messages in errors.items()
        for message in messages
    ]
    if flat_errors and len(contexts) < len(selected):
        service_status = "error" if not contexts else "degraded"
    elif flat_errors:
        service_status = "degraded"
    else:
        service_status = "running"
    return {
        "enabled": True,
        "active": True,
        "mode": "site_policy",
        "service_status": service_status,
        "reason": str(reason or "scheduled"),
        "selected_downloaders": list(selected),
        "downloaders": downloader_items,
        "sites": sites,
        "managed_torrents": len(regular_tasks),
        "grace_torrents": len(grace_tasks),
        "uploading_torrents": sum(
            1 for snapshot in list(regular_tasks.values()) + list(grace_tasks.values())
            if int(snapshot.upload_rate_bps or 0) > 0
        ),
        "probing_torrents": len(probing_task_keys),
        "protected_torrents": sum(
            1 for task_key in regular_tasks
            if int((torrent_state.get(task_key) or {}).get("last_allocation_kib") or 0) == 0
        ),
        "upload_rate_bps": sum(
            int(snapshot.upload_rate_bps or 0)
            for snapshot in list(regular_tasks.values()) + list(grace_tasks.values())
        ),
        "allocated_kib": sum(int(value or 0) for value in pool_allocations.values()),
        "errors": flat_errors,
        "last_run_at": float(state.get("last_run_at") or 0),
        "cycle": int(state.get("cycle") or 0),
    }


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
        last_written = record.get("last_written_settings")
        original = record.get("original_settings")
        try:
            if last_written and original and torrent_settings_equal(
                snapshot.upload_settings,
                settings_from_dict(last_written),
            ):
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
        except Exception as error:
            report["errors"].append(f"{snapshot.torrent_hash}: {error}")
            logger.exception(
                "释放上传限速任务 %s/%s 失败",
                downloader_id,
                snapshot.torrent_hash,
            )
    return report


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
            last_written = record.get("last_written_settings")
            original = record.get("original_settings")
            if last_written and original and torrent_settings_equal(
                snapshot.upload_settings,
                settings_from_dict(last_written),
            ):
                restore_torrent_upload_settings(
                    service.instance,
                    downloader_type,
                    snapshot.torrent_hash,
                    settings_from_dict(original),
                )
                report["torrent_restored"] += 1
            else:
                report["preserved_manual"] += 1
    except Exception as error:
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
        from app.schemas import NotificationType

        plugin.post_message(
            mtype=NotificationType.Plugin,
            title="下载中心上传限速异常",
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


def _resolve_site_group(
    labels: Iterable[str],
    site_rules: dict[str, dict],
    prefix: str,
) -> tuple[str, str]:
    """仅在恰好一个有效站点标签命中规则时返回该站点，否则进入默认组。"""
    site_names = [
        site_name for site_name in (
            _site_name_from_label(label, prefix) for label in labels
        ) if site_name
    ]
    if len(site_names) != 1 or site_names[0] not in site_rules:
        return DEFAULT_SITE_KEY, PRIORITY_MEDIUM
    site_name = site_names[0]
    return site_name, normalize_priority(site_rules[site_name].get("priority"))


def _site_name_from_label(label: Any, prefix: str) -> str:
    """从标签中提取不含前缀的站点名。"""
    text = str(label or "").strip()
    clean_prefix = str(prefix or "🏠")
    if not text.startswith(clean_prefix):
        return ""
    return text[len(clean_prefix):].strip()


def _drop_missing_torrent_state(
    torrent_state: dict,
    downloader_id: str,
    current_keys: set[str],
) -> None:
    """下载器成功轮询后移除已经不存在的历史任务状态。"""
    for task_key, record in list(torrent_state.items()):
        if (
            isinstance(record, dict)
            and record.get("downloader_id") == downloader_id
            and task_key not in current_keys
        ):
            torrent_state.pop(task_key, None)


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


def _downloader_type(service: Any) -> str:
    """从 MoviePilot ServiceInfo 解析下载器类型。"""
    value = getattr(service, "type", "")
    return str(getattr(value, "value", None) or value or "").strip().lower()


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
