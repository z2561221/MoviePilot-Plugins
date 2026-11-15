"""上传限速的单轮下载器读取和任务分类，不执行额度分配。"""

from collections.abc import Callable
from typing import Any

from ..adapter.upload_limit import (
    expected_global_upload_settings,
    global_settings_equal,
    global_settings_from_dict,
    global_settings_to_dict,
    list_upload_torrents,
    read_global_upload_settings,
    settings_to_dict,
    write_global_upload_limit,
)
from ..model.upload_scan import UploadDownloaderContext
from .upload_limit_apply import matches_managed_settings


def scan_downloader(plugin, downloader_id, limit_kib, downloader_state, timestamp, checkpoint):
    """读取一次下载器和任务列表，保留全局上限接管与停止检查顺序。"""
    service = plugin.service_info(downloader_id)
    if not service or not getattr(service, "instance", None):
        raise RuntimeError("下载器不可用")
    kind = downloader_type(service)
    if kind not in {"qbittorrent", "transmission"}:
        raise RuntimeError(f"不支持的下载器类型：{kind or 'unknown'}")
    current_global = read_global_upload_settings(service.instance, kind)
    checkpoint()
    entry = downloader_state.setdefault(downloader_id, {
        "downloader_type": kind, "first_managed_at": timestamp, "initial_scan_complete": False,
    })
    initial_scan_pending = not bool(entry.get("initial_scan_complete"))
    entry["downloader_type"] = kind
    if "original_global" not in entry:
        entry["original_global"] = global_settings_to_dict(current_global)
    last_global = entry.get("last_written_global")
    if last_global and not global_settings_equal(current_global, global_settings_from_dict(last_global, kind)):
        entry["original_global"] = global_settings_to_dict(current_global)
    desired_global = expected_global_upload_settings(kind, limit_kib)
    if not global_settings_equal(current_global, desired_global):
        checkpoint()
        desired_global = write_global_upload_limit(service.instance, kind, limit_kib)
    entry["last_written_global"] = global_settings_to_dict(desired_global)
    entry["total_limit_kib"] = limit_kib
    entry["last_seen_at"] = timestamp
    snapshots, error = list_upload_torrents(service.instance, downloader_id, kind)
    checkpoint()
    if error:
        raise RuntimeError(error)
    all_snapshots = {snapshot.key: snapshot for snapshot in snapshots if snapshot.torrent_hash}
    completed = {snapshot.key: snapshot for snapshot in snapshots if snapshot.completed and snapshot.torrent_hash}
    return UploadDownloaderContext(downloader_id, service, kind, all_snapshots, completed, initial_scan_pending)


def _new_record(plugin, snapshot, timestamp, stock_scan):
    """区分存量任务与新任务，保留原绝对宽限截止时间和原始限速。"""
    completion_reference = max(float(snapshot.completed_at or 0), float(snapshot.added_at or 0)) or timestamp
    grace_until = 0.0 if stock_scan else completion_reference + max(
        0, int(getattr(plugin, "_upload_limit_grace_minutes", 30) or 0),
    ) * 60
    return {"downloader_id": snapshot.downloader_id, "downloader_type": snapshot.downloader_type,
            "torrent_hash": snapshot.torrent_hash, "first_seen_at": timestamp,
            "completion_reference": completion_reference, "grace_until": grace_until,
            "original_settings": settings_to_dict(snapshot.upload_settings)}


def classify_upload_tasks(
    plugin: Any, context: UploadDownloaderContext, torrent_state: dict, site_rules: dict,
    tag_prefix: str, timestamp: float, first_activation: bool,
    resolve_site: Callable, release_record: Callable,
    regular: dict, grace: dict, errors: list,
):
    """复用成功扫描的快照，分类宽限/受限任务并恢复退出策略的原设置。"""
    release_args = {"state": {"torrents": torrent_state}, "instance": context.service.instance,
                    "downloader_type": context.downloader_type}
    for key, snapshot in context.all_snapshots.items():
        if snapshot.completed or key not in torrent_state:
            continue
        error = release_record(task_key=key, record=torrent_state[key], snapshot=snapshot, **release_args)
        if error:
            errors.append(error)
    for key, record in list(torrent_state.items()):
        if (isinstance(record, dict) and record.get("downloader_id") == context.downloader_id
                and key not in context.all_snapshots):
            torrent_state.pop(key, None)
    stock_scan = bool(first_activation or context.initial_scan_pending)
    for key, snapshot in context.snapshots.items():
        record = torrent_state.get(key)
        if not isinstance(record, dict):
            record = _new_record(plugin, snapshot, timestamp, stock_scan)
            torrent_state[key] = record
        elif not matches_managed_settings(record, snapshot.upload_settings):
            record["original_settings"] = settings_to_dict(snapshot.upload_settings)
        site = resolve_site(snapshot.labels, site_rules, tag_prefix)
        if not site:
            if record:
                error = release_record(task_key=key, record=record, snapshot=snapshot, **release_args)
                if error:
                    errors.append(error)
            continue
        record.update({"downloader_id": context.downloader_id, "downloader_type": context.downloader_type,
                       "torrent_hash": snapshot.torrent_hash, "name": snapshot.name, "labels": list(snapshot.labels),
                       "site_key": site, "upload_rate_bps": snapshot.upload_rate_bps,
                       "upload_demand_peers": snapshot.upload_demand_peers, "last_seen_at": timestamp})
        if float(record.get("grace_until") or 0) > timestamp:
            grace[key] = snapshot
        else:
            regular[key] = snapshot


def downloader_type(service: Any) -> str:
    """统一读取MoviePilot服务声明的下载器类型。"""
    value = getattr(service, "type", "")
    return str(getattr(value, "value", None) or value or "").strip().lower()
