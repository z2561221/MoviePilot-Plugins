"""只读限速摘要投影；每组快照只遍历一次，不持有跨轮次缓存。"""

from itertools import chain

from ..model.upload_limit import UploadTorrentSnapshot
from ..model.upload_scan import UploadDownloaderContext


def _service_status(contexts: dict, selected: list[str], errors: list[str]) -> str:
    """保留全部失败、部分失败及成功的原显示语义。"""
    if errors and len(contexts) < len(selected):
        return "error" if not contexts else "degraded"
    return "degraded" if errors else "running"


def _downloader_item(downloader_id, state, caps, context, errors):
    """初始化一个下载器的输出行，后续只累计数值。"""
    return {
        "id": downloader_id,
        "type": str((context.downloader_type if context else "") or (
            (state.get("downloaders") or {}).get(downloader_id, {}).get("downloader_type") or ""
        )),
        "total_limit_kib": int(caps.get(downloader_id, 0) or 0),
        "upload_rate_bps": 0,
        "managed_torrents": 0,
        "grace_torrents": 0,
        "uploading_torrents": 0,
        "probing_torrents": 0,
        "auto_probe_count": 0,
        "protected_torrents": 0,
        "allocated_kib": 0,
        "error": "; ".join(errors.get(downloader_id) or []),
    }


def build_site_summary(
    *, state: dict, selected: list[str], caps: dict[str, int],
    contexts: dict[str, UploadDownloaderContext],
    regular_tasks: dict[str, UploadTorrentSnapshot], grace_tasks: dict[str, UploadTorrentSnapshot],
    pool_allocations: dict[str, int], site_rules: dict[str, dict],
    probing_task_keys: set[str], errors: dict[str, list[str]], reason: str,
) -> dict:
    """分别保留全局、下载器、站点口径，单轮累计避免按下载器重复扫描任务。"""
    torrent_state = state.get("torrents") or {}
    items = {key: _downloader_item(key, state, caps, contexts.get(key), errors) for key in selected}
    total_rate = 0
    for downloader_id, context in contexts.items():
        item = items.get(downloader_id)
        for snapshot in context.snapshots.values():
            rate = int(snapshot.upload_rate_bps or 0)
            total_rate += rate
            if item is not None:
                item["upload_rate_bps"] += rate
                item["uploading_torrents"] += rate > 0
    if items:
        for key in probing_task_keys:
            item = items.get(regular_tasks[key].downloader_id)
            if item is not None:
                item["probing_torrents"] += 1
    for snapshot in grace_tasks.values():
        item = items.get(snapshot.downloader_id)
        if item is not None:
            item["grace_torrents"] += 1
    site_items: dict[str, dict] = {}
    protected = 0
    for task_key, snapshot in regular_tasks.items():
        record = torrent_state.get(task_key) or {}
        allocation = int(record.get("last_allocation_kib") or 0)
        is_protected = allocation == 0
        protected += is_protected
        downloader = items.get(snapshot.downloader_id)
        if downloader is not None:
            downloader["managed_torrents"] += 1
            downloader["protected_torrents"] += is_protected
        site_key = str(record.get("site_key") or "")
        rule = site_rules.get(site_key) or {}
        site = site_items.setdefault(site_key, {
            "key": site_key, "name": site_key, "limit_kib": int(rule.get("limit_kib") or 0),
            "allocated_kib": 0, "upload_rate_bps": 0, "torrent_count": 0,
            "uploading_torrents": 0, "probing_torrents": 0, "protected_torrents": 0,
            "downloaders": set(),
        })
        rate = int(snapshot.upload_rate_bps or 0)
        site["allocated_kib"] += allocation
        site["upload_rate_bps"] += rate
        site["torrent_count"] += 1
        site["uploading_torrents"] += rate > 0
        site["probing_torrents"] += task_key in probing_task_keys
        site["protected_torrents"] += is_protected
        site["downloaders"].add(snapshot.downloader_id)
    timestamp = float(state.get("last_run_at") or 0)
    for record in torrent_state.values():
        if isinstance(record, dict) and isinstance(record.get("downloader_id"), str):
            item = items.get(record.get("downloader_id"))
            if item is not None and float(record.get("grace_until") or 0) <= timestamp:
                item["allocated_kib"] += int(record.get("last_allocation_kib") or 0)
    for downloader_id, item in items.items():
        item["auto_probe_count"] = int(
            ((state.get("downloaders") or {}).get(downloader_id) or {}).get("auto_probe_count") or 0
        )
    sites = [{**item, "downloaders": sorted(item["downloaders"])} for item in sorted(
        site_items.values(), key=lambda value: value["name"].lower(),
    )]
    flat_errors = [f"{key}: {message}" for key, messages in errors.items() for message in messages]
    return {
        "enabled": True, "active": True, "mode": "site_policy",
        "service_status": _service_status(contexts, selected, flat_errors),
        "reason": str(reason or "scheduled"), "selected_downloaders": list(selected),
        "downloaders": [items[key] for key in selected], "sites": sites,
        "managed_torrents": len(regular_tasks), "grace_torrents": len(grace_tasks),
        "uploading_torrents": sum(int(snapshot.upload_rate_bps or 0) > 0 for snapshot in chain(
            regular_tasks.values(), grace_tasks.values(),
        )),
        "probing_torrents": len(probing_task_keys), "protected_torrents": protected,
        "upload_rate_bps": total_rate,
        "allocated_kib": sum(int(value or 0) for value in pool_allocations.values()),
        "errors": flat_errors, "last_run_at": timestamp, "cycle": int(state.get("cycle") or 0),
    }


def build_downloader_only_summary(
    *,
    state: dict,
    selected: list[str],
    caps: dict[str, int],
    contexts: dict[str, UploadDownloaderContext],
    errors: dict[str, list[str]],
    reason: str,
) -> dict:
    """构造仅由下载器总上限接管时的运行摘要。"""
    downloader_items = []
    total_rate_bps = 0
    total_torrents = 0
    allocated_kib = 0
    for downloader_id in selected:
        context = contexts.get(downloader_id)
        snapshots = context.snapshots.values() if context else ()
        upload_rate_bps = sum(
            int(snapshot.upload_rate_bps or 0) for snapshot in snapshots
        )
        has_context = bool(context)
        item_allocated_kib = int(caps.get(downloader_id, 0) or 0) if has_context else 0
        total_rate_bps += upload_rate_bps
        total_torrents += len(snapshots)
        allocated_kib += item_allocated_kib
        downloader_items.append({
            "id": downloader_id,
            "type": str((context.downloader_type if context else "") or (
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
            "auto_probe_count": 0,
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
    return {
        "enabled": True,
        "active": True,
        "mode": "downloader_only",
        "service_status": service_status,
        "reason": str(reason or "scheduled"),
        "selected_downloaders": list(selected),
        "downloaders": downloader_items,
        "sites": [],
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
