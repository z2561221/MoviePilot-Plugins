"""辅助铺种后台任务、来源路由及分批执行。"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from app.sdk.logging import logger

from ..adapter.auto_delete import binding_of
from ..adapter.moviepilot import (
    SiteDownloadError,
    check_site,
    export_qb_completed_torrent,
    get_downloader_services,
    list_site_dicts,
    pieces_hash_url,
    request_pieces_torrent,
)
from ..utils.config import is_iyuu_active
from ..utils.torrent_adapter import normalize_torrent
from . import iyuu, pieces

TASK_KEY = "reseed_task"
LIMITS_KEY = "reseed_site_limits"
REQUESTS_KEY = "reseed_requests"
PROGRESS_KEY = "reseed_scan_progress"
PAGE_SIZE = 100
QUERY_ATTEMPTS = 3
QUERY_RETRY_DELAYS = (6, 15)
ACTIVE = {"queued", "running", "cancelling"}
_INIT_LOCK = threading.Lock()


def _lock(plugin):
    """获取当前插件实例任务锁。"""
    with _INIT_LOCK:
        if not hasattr(plugin, "_reseed_lock"):
            plugin._reseed_lock = threading.RLock()
        return plugin._reseed_lock


def _load(plugin, key):
    """读取轻量状态，拒绝覆盖格式损坏的数据。"""
    value = plugin.get_data(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("辅助铺种状态数据格式错误")
    return value


def start(plugin, request_id="", preview=False, *,
          addition_limit=None, source_limit=None):
    """登记任务并立即返回编号，调度和手动操作共用此入口。"""
    from app.sdk.scheduler import add_plugin_once_job

    if not getattr(plugin, "_enabled", False):
        raise ValueError("请先启用下载中心")
    if not getattr(plugin, "_iyuu_token", ""):
        raise ValueError("请填写 IYUU Token")
    if not is_iyuu_active(plugin):
        raise ValueError("请启用 IYUU 并选择辅种下载器")
    mode = "auto" if getattr(plugin, "_pieces_site_keys", "").strip() else "iyuu"
    configured_limit = int(getattr(plugin, "_reseed_max_additions", 20))
    addition_limit = min(configured_limit, int(addition_limit or configured_limit))
    source_limit = int(source_limit or 0)
    if addition_limit < 1 or source_limit < 0:
        raise ValueError("任务数量限制无效")
    request_id = request_id or uuid4().hex
    with _lock(plugin):
        event = getattr(plugin, "_event", None)
        if not is_iyuu_active(plugin) or (event is not None and event.is_set()):
            raise ValueError("IYUU 铺种已停止或配置发生变化")
        remembered = _load(plugin, REQUESTS_KEY)
        previous = remembered.get(request_id)
        if previous:
            if (previous["mode"], previous["preview"], previous.get("addition_limit", configured_limit),
                    previous.get("source_limit", 0)) != (mode, preview, addition_limit, source_limit):
                raise ValueError("请求标识已用于另一项任务")
            return status(plugin) if _load(plugin, TASK_KEY).get("task_id") == previous["task_id"] else previous
        current = _load(plugin, TASK_KEY)
        if current.get("status") in ACTIVE or getattr(plugin, "_reseed_worker", None) is not None:
            return status(plugin)
        task_id = uuid4().hex
        task = {"task_id": task_id, "mode": mode, "preview": preview, "status": "queued",
                "phase": "等待执行", "scanned": 0, "matched": 0, "added": 0,
                "failed": 0, "skipped": 0, "result_count": 0, "message": "任务已提交",
                "submission_count": 0, "addition_limit": addition_limit, "source_limit": source_limit,
                "created_at": time.time(), "updated_at": time.time()}
        plugin._reseed_cancel = threading.Event()
        plugin.save_data(TASK_KEY, task)
        remembered[request_id] = dict(task)
        plugin.save_data(REQUESTS_KEY, dict(list(remembered.items())[-20:]))
        try:
            accepted = add_plugin_once_job(
                plugin.__class__.__name__, "auxiliary_reseed", plugin._run_reseed_task,
                "IYUU铺种", delay_seconds=0, func_kwargs={"task_id": task_id},
            )
        except Exception:
            accepted = False
        if not accepted:
            task.update(status="failed", message="后台调度器未接受任务", phase="提交失败")
            plugin.save_data(TASK_KEY, task)
        return task


def status(plugin):
    """读取持久化进度，状态轮询不请求站点或下载器。"""
    with _lock(plugin):
        task = deepcopy(_load(plugin, TASK_KEY))
    return task or {"status": "idle", "phase": "尚未运行"}


def results(plugin, task_id, offset=0, limit=100):
    """按页读取当前任务结果，避免大响应阻塞界面。"""
    task = status(plugin)
    if task.get("task_id") != task_id:
        raise ValueError("任务结果已更新，请刷新")
    offset = max(0, int(offset))
    limit = min(PAGE_SIZE, max(1, int(limit)))
    end = min(offset + limit, task.get("result_count", 0))
    rows = []
    for page in range(offset // PAGE_SIZE, (end + PAGE_SIZE - 1) // PAGE_SIZE):
        payload = _load(plugin, f"reseed_result_{page}")
        if payload.get("task_id") == task_id:
            rows.extend(deepcopy(payload.get("items", [])[max(0, offset - page * PAGE_SIZE):end - page * PAGE_SIZE]))
    verifications = _load(plugin, "reseed_verification")
    for row in rows:
        verification = verifications.get(f"{row.get('downloader', '')}::{row.get('target_hash', '')}")
        if row.get("state") == "added" and verification:
            row.update(state=verification["state"], message=verification["message"])
    return {"task_id": task_id, "items": rows, "total": task.get("result_count", 0)}


def stop(plugin, task_id=None):
    """取消待执行调度并停止当前任务后续请求与写入。"""
    from app.sdk.scheduler import remove_plugin_once_job

    with _lock(plugin):
        task = _load(plugin, TASK_KEY)
        if task_id and task.get("task_id") != task_id:
            raise ValueError("任务已更新，请刷新后再停止")
        cancel = getattr(plugin, "_reseed_cancel", None)
        if cancel is not None:
            cancel.set()
        if task.get("status") in ACTIVE:
            try:
                remove_plugin_once_job(plugin.__class__.__name__, "auxiliary_reseed")
            except RuntimeError:
                logger.warning("辅助铺种：宿主调度器未初始化，已设置任务停止信号")
        if task.get("status") in ACTIVE:
            task.update(status="cancelled" if task["status"] == "queued" else "cancelling", message="已请求停止")
            plugin.save_data(TASK_KEY, task)
        return task or {"status": "idle"}


def recover(plugin):
    """重载后标记中断任务，保留已提交目标的公共待办记录。"""
    with _lock(plugin):
        task = _load(plugin, TASK_KEY)
        if task.get("status") in ACTIVE:
            task.update(status="interrupted", phase="已中断", message="插件已重载，可重新运行并核对已添加任务")
            plugin.save_data(TASK_KEY, task)


class ReseedRun:
    """保存单次运行快照及有限结果缓冲。"""

    def __init__(self, plugin, task):
        """捕获任务、停止代次及当前实例取消事件。"""
        self.plugin = plugin
        self.task = task
        self.generation = int(getattr(plugin, "_transfer_stop_generation", 0) or 0)
        self.cancel = plugin._reseed_cancel
        self.buffer = []
        self.page = 0
        self.counts = {}
        self.seen = set()
        self.existing_targets = {}
        self.metadata = _load(plugin, "reseed_metadata_cache")
        self.empty_matches = {key: expiry for key, expiry in _load(plugin, "reseed_empty_matches").items()
                              if isinstance(expiry, (int, float)) and expiry > time.time()}

    def stopped(self):
        """每个外部回包和写入阶段再次检查任务是否仍有效。"""
        return self.cancel.is_set() or iyuu._transfer_stopped(self.plugin, self.generation)

    def limit_reached(self):
        """未知提交也占用本轮名额，防止回执或后处理失败后超过上限。"""
        return not self.task["preview"] and self.task.get("submission_count", 0) >= self.task["addition_limit"]

    def save(self, phase=None):
        """按当前任务身份写回轻量进度。"""
        with _lock(self.plugin):
            current = _load(self.plugin, TASK_KEY)
            if current.get("task_id") != self.task["task_id"] or current.get("status") == "interrupted":
                return
            if phase:
                self.task["phase"] = phase
            self.task["updated_at"] = time.time()
            self.plugin.save_data(TASK_KEY, self.task)

    def record(self, state, message, source=None, site=None, target_hash="", downloader=""):
        """缓冲脱敏结果，完整页落盘并更新进度。"""
        self.task[state] = self.task.get(state, 0) + 1
        self.buffer.append({"state": state, "message": message,
                            "source_hash": (source or {}).get("hash", ""),
                            "site": (site or {}).get("name", ""), "target_hash": target_hash,
                            "downloader": downloader})
        if len(self.buffer) == PAGE_SIZE:
            self.flush()

    def flush(self):
        """把当前页持久化，状态读取只返回已落盘的记录数。"""
        with _lock(self.plugin):
            current = _load(self.plugin, TASK_KEY)
            if current.get("task_id") != self.task["task_id"] or current.get("status") == "interrupted":
                return
            if self.buffer:
                self.plugin.save_data(f"reseed_result_{self.page}", {"task_id": self.task["task_id"], "items": self.buffer})
                self.task["result_count"] = self.page * PAGE_SIZE + len(self.buffer)
                if len(self.buffer) == PAGE_SIZE:
                    self.page += 1
                    self.buffer = []
            self.save()

    def pieces_failure(self, message, source=None, site=None):
        """仅将正式 Pieces 查询或候选处理的明确失败计入独立统计。"""
        if not self.task["preview"] and not self.stopped():
            pieces.count_result(self.plugin, success=False)
        self.record("failed", message, source, site)

    def wait_budget(self, key, interval):
        """在请求前保存下次允许时间，重载与手动运行共享限额。"""
        limits = _load(self.plugin, LIMITS_KEY)
        delay = max(0, float(limits.get(key, 0)) - time.time())
        if delay > max(interval, 30):
            return False
        if self.cancel.wait(delay) or self.stopped():
            return False
        limits[key] = time.time() + interval
        self.plugin.save_data(LIMITS_KEY, limits)
        return True

    def cooldown(self, key, seconds):
        """保存站点冷却期，失败不会被记录成空命中。"""
        limits = _load(self.plugin, LIMITS_KEY)
        limits[key] = max(float(limits.get(key, 0)), time.time() + seconds)
        self.plugin.save_data(LIMITS_KEY, limits)


def run(plugin, task_id):
    """由宿主后台调度执行整轮任务，页面请求只负责登记。"""
    execution = None
    worker = threading.current_thread()
    with _lock(plugin):
        task = _load(plugin, TASK_KEY)
        if task.get("task_id") != task_id or task.get("status") != "queued":
            return
        plugin._reseed_worker = worker
        task.update(status="running", phase="扫描下载器", message="正在运行")
    try:
        with _lock(plugin):
            execution = ReseedRun(plugin, task)
            plugin._reseed_execution = execution
            execution.save()
        _run_sources(execution)
        task.update(status="cancelled" if execution.stopped() else "completed",
                    phase="已停止" if execution.stopped() else "本轮完成",
                    message="已添加任务由校验队列继续处理" if task["added"] else "本轮任务结束")
        if task["failed"] and task["status"] == "completed":
            task["status"] = "partial"
        if task.get("scan_pending") and not execution.stopped():
            task.update(phase="本轮结束，扫描未完成", message="已保留扫描断点，下轮继续未完成批次")
    except Exception as error:
        message = str(error) if isinstance(error, ValueError) else f"任务执行失败（{type(error).__name__}）"
        task.update(status="failed", phase="运行失败", message=message)
        logger.error(f"辅助铺种：{message}")
    finally:
        try:
            if execution is not None:
                execution.flush()
                if not execution.stopped():
                    plugin.save_data("reseed_metadata_cache", execution.metadata)
                    plugin.save_data("reseed_empty_matches", dict(list(execution.empty_matches.items())[-10000:]))
            else:
                with _lock(plugin):
                    current = _load(plugin, TASK_KEY)
                    if current.get("task_id") == task_id and current.get("status") != "interrupted":
                        plugin.save_data(TASK_KEY, task)
        finally:
            with _lock(plugin):
                if getattr(plugin, "_reseed_worker", None) is worker:
                    plugin._reseed_worker = None
                    plugin._reseed_execution = None


def reserve_submission(plugin, generation):
    """实际提交前登记本轮名额，旧入口和旧实例保留原有调用约定。"""
    execution = getattr(plugin, "_reseed_execution", None)
    if execution is None or getattr(plugin, "_reseed_worker", None) is not threading.current_thread():
        return True
    with _lock(plugin):
        if execution.generation != generation or execution.stopped() or execution.limit_reached():
            return False
        execution.task["submission_count"] += 1
        execution.save()
        return True


def _completed_sources(service):
    """读取完整任务列表并保留已暂停但数据完整的来源。"""
    rows, error = service.instance.get_torrents()
    if error or rows is None:
        raise ValueError("读取下载器任务失败")
    completed = []
    for row in rows:
        progress = row.get("progress") if service.type == "qbittorrent" else getattr(row, "percent_done", None)
        try:
            if float(progress) >= 1:
                completed.append(row)
        except (TypeError, ValueError):
            continue
    return completed


def _scan_progress(execution, services, sites):
    """按配置与下载器绑定隔离断点，预览和小范围试验不推进正式扫描。"""
    if execution.task["preview"] or execution.task.get("source_limit"):
        return None
    plugin = execution.plugin
    fields = ("iyuu_token", "iyuu_sites", "iyuu_auto_downloader", "iyuu_nolabels",
              "iyuu_nopaths", "iyuu_size", "pieces_site_keys", "pieces_torrent_paths")
    context = {name: getattr(plugin, "_" + name, None) for name in fields}
    context["services"] = [(service.name, binding_of(service)) for service in services]
    target_name = getattr(plugin, "_iyuu_auto_downloader", "")
    target = plugin.service_info(target_name) if target_name else None
    context["target"] = binding_of(target) if target else None
    context["sites"] = [(site["id"], site["url"]) for site in sites]
    signature = hashlib.sha256(json.dumps(context, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    progress = _load(plugin, PROGRESS_KEY)
    if progress.get("context") != signature:
        progress = {"context": signature, "services": {}}
    if not isinstance(progress.get("services"), dict):
        raise ValueError("铺种扫描断点格式错误")  # noqa: TRY004 持久数据损坏属于可展示的业务错误。
    return progress


def _save_scan_progress(execution, progress, name, after="", done=False):
    """仅在当前任务仍有效时保存已处理批次，未完成批次保持可重查。"""
    if progress is None:
        return
    with _lock(execution.plugin):
        current = _load(execution.plugin, TASK_KEY)
        if execution.stopped() or current.get("task_id") != execution.task["task_id"]:
            return
        progress["services"][name] = {"after": after, "done": done}
        execution.plugin.save_data(PROGRESS_KEY, progress)
        execution.task["scan_pending"] = True


def _run_sources(execution):
    """自动枚举全部合格下载器，按百颗来源批次查询。"""
    plugin = execution.plugin
    task = execution.task
    sites = pieces.parse_site_keys(plugin._pieces_site_keys, list_site_dicts()) if task["mode"] != "iyuu" else []
    services = get_downloader_services(name_filters=plugin._iyuu_downloaders or None) or {}
    if not services:
        raise ValueError("没有可用的辅种下载器")
    services = sorted(services.values(), key=lambda service: service.name)
    progress = _scan_progress(execution, services, sites)
    if progress and progress["services"]:
        task["scan_pending"] = True
    iyuu._reset_iyuu_run_counters(plugin)
    if not task["preview"]:
        iyuu._resume_iyuu_postprocess(plugin, execution.generation)
    from ..iyuu_helper import IyuuHelper

    budget_key = "iyuu_" + hashlib.sha256(plugin._iyuu_token.encode()).hexdigest()
    if float(_load(plugin, LIMITS_KEY).get(budget_key, 0)) > time.time():
        execution.record("skipped", "IYUU 正在冷却，本轮等待")
        return
    plugin.iyuu_helper = plugin.iyuu_helper or IyuuHelper(plugin._iyuu_token)
    ready, _ = plugin.iyuu_helper.ensure_ready()
    if not ready:
        execution.cooldown(budget_key, max(60, getattr(plugin.iyuu_helper, "retry_after", 300) or 300))
        raise ValueError("IYUU 预检失败，请检查 Token、绑定站点或冷却状态")
    try:
        for service in services:
            if execution.stopped() or execution.limit_reached():
                return
            cursor = progress["services"].get(service.name, {}) if progress else {}
            if not isinstance(cursor, dict) or not isinstance(cursor.get("after", ""), str):
                raise ValueError("铺种扫描断点格式错误")  # noqa: TRY004 保持持久数据校验的业务错误语义。
            if cursor.get("done"):
                task["resumed"] = True
                continue
            if service.instance.is_inactive():
                execution.record("failed", f"下载器 {service.name} 未连接")
                continue
            execution.save(f"扫描 {service.name}")
            try:
                torrents = _completed_sources(service)
                sources = iyuu._iyuu_candidates(plugin, service, torrents, execution.generation,
                                                ignore_caches=task["mode"] != "iyuu") or []
                sources.sort(key=lambda source: source["hash"])
                if cursor.get("after"):
                    sources = [source for source in sources if source["hash"] > cursor["after"]]
                    execution.task["resumed"] = True
                source_rows = {plugin.get_hash(row, service.type): row for row in torrents}
                execution.existing_targets[service.name] = set(source_rows)
            except Exception:
                execution.record("failed", f"读取下载器 {service.name} 失败")
                continue
            _save_scan_progress(execution, progress, service.name, cursor.get("after", ""))
            for offset in range(0, len(sources), PAGE_SIZE):
                if execution.stopped() or execution.limit_reached():
                    return
                chunk = sources[offset:offset + PAGE_SIZE]
                if task.get("source_limit"):
                    remaining = task["source_limit"] - task["scanned"]
                    if remaining <= 0:
                        return
                    chunk = chunk[:remaining]
                task["scanned"] += len(chunk)
                matched_sites = {}
                if not _query_iyuu(execution, service, chunk, matched_sites):
                    return
                if sites:
                    _query_pieces(execution, service, chunk, source_rows, sites, matched_sites)
                execution.flush()
                if execution.stopped() or execution.limit_reached():
                    return
                _save_scan_progress(execution, progress, service.name, chunk[-1]["hash"])
            _save_scan_progress(execution, progress, service.name, done=True)
        if (progress is not None and not execution.stopped()
                and all(progress["services"].get(service.name, {}).get("done") for service in services)):
            with _lock(plugin):
                if not execution.stopped() and _load(plugin, TASK_KEY).get("task_id") == task["task_id"]:
                    plugin.save_data(PROGRESS_KEY, {})
                    task["scan_pending"] = False
    finally:
        if not task["preview"]:
            if not execution.stopped():
                iyuu._save_batch_caches(plugin, execution.generation)
            iyuu._flush_iyuu_stats(plugin)


def _query_iyuu(execution, service, sources, matched_sites):
    """只对成功的 IYUU 响应补缺，错误保留为本轮失败。"""
    plugin = execution.plugin
    key = "iyuu_" + hashlib.sha256(plugin._iyuu_token.encode()).hexdigest()
    if not execution.wait_budget(key, 6):
        execution.record("skipped", "IYUU 正在冷却")
        return False
    execution.save("查询 IYUU")

    def accept(seed, source, source_service, site):
        """统一记录 IYUU 候选并尊重本轮新增限额。"""
        execution.task["matched"] += 1
        if execution.task["preview"]:
            execution.record("skipped", "IYUU 命中，预览未添加", source, site, seed["info_hash"])
            return
        if not _allow_candidate(execution, site, seed.get("torrent_id")):
            return
        try:
            target_name = getattr(plugin, "_iyuu_auto_downloader", "") or source_service.name
            if seed["info_hash"] in execution.existing_targets.get(target_name, set()):
                execution.record("skipped", "目标任务已存在", source, site, seed["info_hash"])
                return
            target, target_path = _target_service(plugin, source_service, source)
            if target_path != source["save_path"]:
                raise ValueError("IYUU 跨下载器路径不同，等待路径映射适配")
            accepted = iyuu.iyuu_download_torrent(
                plugin, seed, target, target_path, source.get("category"), source["hash"], site,
                execution.generation, source_service, source["source_added_at"], source["source_binding"],
            )
            execution.record("added" if accepted else "skipped", "已添加，等待校验" if accepted else "已存在或未提交", source, site, seed["info_hash"])
            if accepted:
                execution.counts[str(site["id"])] = execution.counts.get(str(site["id"]), 0) + 1
        except Exception as error:
            message = str(error) if isinstance(error, ValueError) else "IYUU 候选添加失败"
            execution.record("failed", message, source, site)

    for attempt in range(QUERY_ATTEMPTS):
        error = iyuu.iyuu_seed_torrents(plugin, sources, service, execution.generation,
                                      matched_sites=matched_sites, candidate_handler=accept)
        if execution.stopped():
            return False
        if not error:
            return True
        limited = any(word in error.lower() for word in ("429", "限流", "频率", "too many requests"))
        transient = (iyuu._is_iyuu_transient_error(error)
                     or bool(re.search(r"(?:HTTP|状态码[:：]?)\s*(?:408|5\d\d)\b", error, re.IGNORECASE))
                     or error == "IYUU 响应格式无效")
        if limited or iyuu._is_iyuu_config_error(error) or not transient or attempt + 1 == QUERY_ATTEMPTS:
            execution.cooldown(key, max(60, int(getattr(plugin.iyuu_helper, "retry_after", 300) or 300)))
            message = ("IYUU 查询失败，本轮停止补查" if execution.task["preview"] or execution.task.get("source_limit")
                       else "IYUU 查询失败，保留断点等待下轮续扫")
            execution.record("failed", message)
            return False
        delay = QUERY_RETRY_DELAYS[attempt]
        execution.cooldown(key, delay)
        execution.save(f"IYUU 暂时失败，等待第 {attempt + 2} 次查询")
        if not execution.wait_budget(key, max(delay, 6)):
            return False
        execution.task["query_retries"] = execution.task.get("query_retries", 0) + 1
        execution.save("重试 IYUU 查询")
    return False


def _source_metadata(execution, service, source, row):
    """按下载器绑定与源 hash 缓存元数据，TR 仅使用已配置的可读目录。"""
    key = source["source_binding"] + ":" + source["hash"]
    if key in execution.metadata:
        return execution.metadata[key]
    if service.type == "qbittorrent":
        _, content = export_qb_completed_torrent(service.name, source["hash"])
    elif service.type == "transmission":
        roots = {}
        for line in getattr(execution.plugin, "_pieces_torrent_paths", "").splitlines():
            if "=" in line:
                name, directory = line.split("=", 1)
                roots[name.strip()] = directory.strip()
        directory = roots.get(service.name)
        if not directory or not Path(directory).is_absolute():
            raise ValueError("Transmission 尚未配置可读的种子绝对目录")
        root = Path(directory).resolve(strict=True)
        remote = str(getattr(row, "torrent_file", "") or getattr(row, "torrentFile", ""))
        filename = remote.replace("\\", "/").rsplit("/", 1)[-1]
        candidate = (root / filename).resolve(strict=True)
        if not filename or not candidate.is_relative_to(root) or candidate.stat().st_size > pieces.MAX_TORRENT_BYTES:
            raise ValueError("Transmission 种子路径无效")
        content = candidate.read_bytes()
    else:
        raise ValueError("下载器不支持读取种子元数据")
    metadata = pieces.torrent_metadata(content)
    if metadata["hash"] != source["hash"].lower():
        raise ValueError("导出元数据与来源种子 hash 不符")
    if len(execution.metadata) >= 128:
        execution.metadata.pop(next(iter(execution.metadata)))
    if len(json.dumps(metadata, ensure_ascii=False).encode()) <= 8192:
        execution.metadata[key] = metadata
    return metadata


def _query_pieces(execution, service, sources, source_rows, sites, matched_sites):
    """按配置站点补查来源指纹，单站请求串行并持续保存冷却。"""
    fingerprints = {}
    execution.save(f"读取 {service.name} 种子元数据")
    for source in sources:
        if execution.stopped():
            return
        if all(str(site["id"]) in matched_sites.get(source["hash"], set()) for site in sites):
            continue
        try:
            metadata = _source_metadata(execution, service, source, source_rows[source["hash"]])
            fingerprints.setdefault(metadata["pieces_hash"], []).append((source, metadata))
        except Exception as error:
            message = str(error) if isinstance(error, ValueError) else "来源元数据读取失败"
            execution.record("skipped", message, source)
    for site in sites:
        if execution.stopped():
            return
        requested = [fingerprint for fingerprint, entries in fingerprints.items()
                     if any(str(site["id"]) not in matched_sites.get(source["hash"], set()) for source, _ in entries)]
        cache_prefix = hashlib.sha256(f"{site['id']}:{pieces_hash_url(site)}:{site['passkey']}".encode()).hexdigest()
        requested = [fingerprint for fingerprint in requested
                     if execution.empty_matches.get(cache_prefix + fingerprint, 0) <= time.time()]
        if not requested:
            continue
        current = next((item for item in list_site_dicts() if str(item.get("id")) == str(site["id"])), None)
        if not current or str(current.get("url") or current.get("domain") or "").rstrip("/") != site["url"].rstrip("/") or current.get("is_active") is False:
            execution.pieces_failure("站点绑定已变化，请重新运行", site=site)
            continue
        key = f"pieces_{site['id']}_{hashlib.sha256(site['url'].encode()).hexdigest()}"
        if not execution.wait_budget(key, site["interval"]):
            execution.record("skipped", "站点正在冷却", site=site)
            continue
        execution.save(f"查询 {site['name']}")
        matches, cooldown, error = pieces.query_site(site, requested)
        if execution.stopped():
            return
        if error:
            execution.cooldown(key, cooldown)
            execution.pieces_failure(error, site=site)
            continue
        for fingerprint in requested:
            if fingerprint not in matches:
                execution.empty_matches[cache_prefix + fingerprint] = time.time() + 900
        for fingerprint, torrent_ids in matches.items():
            if execution.stopped() or execution.limit_reached():
                return
            entries = [(source, meta) for source, meta in fingerprints[fingerprint]
                       if str(site["id"]) not in matched_sites.get(source["hash"], set())]
            candidates = torrent_ids if isinstance(torrent_ids, list) else [torrent_ids]
            for torrent_id in candidates:
                if execution.stopped() or execution.limit_reached():
                    return
                execution.task["matched"] += 1
                if not _allow_candidate(execution, site, torrent_id):
                    continue
                for source, metadata in entries:
                    if _pieces_candidate(execution, service, source, metadata, site, torrent_id, key):
                        break


def _allow_candidate(execution, site, torrent_id):
    """按站点种子去重并限制本轮实际新增总数。"""
    identity = (str(site["id"]), str(torrent_id))
    if identity in execution.seen:
        execution.record("skipped", "候选已处理", site=site)
        return False
    if execution.limit_reached():
        execution.record("skipped", "达到本轮新增上限", site=site)
        return False
    execution.seen.add(identity)
    return True


def _target_service(plugin, source_service, source):
    """主辅分离通过目标已有完整源任务确认数据和真实保存路径。"""
    target_name = getattr(plugin, "_iyuu_auto_downloader", "")
    if not target_name or target_name == source_service.name:
        return source_service, source["save_path"]
    target = plugin.service_info(target_name)
    if not target or target.instance.is_inactive():
        raise ValueError("主辅分离下载器不可用")
    rows, error = target.instance.get_torrents(ids=[source["hash"]])
    if error or not rows or len(rows) != 1:
        raise ValueError("目标下载器缺少可核验的完整来源任务，无法确认数据路径")
    row = rows[0]
    progress = row.get("progress") if target.type == "qbittorrent" else getattr(row, "percent_done", 0)
    snapshot = normalize_torrent(row, target.name, target.type)
    if float(progress or 0) < 1 or not snapshot.save_path:
        raise ValueError("目标下载器来源数据未完成")
    return target, snapshot.save_path


def _pieces_candidate(execution, service, source, metadata, site, torrent_id, budget_key):
    """取回目标元数据复核后调用公共添加流程，预览只记录验证结果。"""
    plugin = execution.plugin
    try:
        blocked, _ = check_site(site["url"])
        if blocked:
            raise ValueError("站点暂时不可访问")
        if not execution.wait_budget(budget_key, site["interval"]):
            return False
        execution.save(f"核验 {site['name']} 候选")
        content = request_pieces_torrent(site, torrent_id)
        if execution.stopped():
            return False
        target_meta = pieces.torrent_metadata(content)
        pieces.verify_target(metadata, target_meta)
        verify_data_files(service, source["hash"], metadata)
        target, target_path = _target_service(plugin, service, source)
        if target.name != service.name:
            verify_data_files(target, source["hash"], metadata)
        rows, error = target.instance.get_torrents(ids=[target_meta["hash"]])
        if error or rows is None:
            raise ValueError("无法核对目标下载器是否已有该种子")
        if rows:
            execution.record("skipped", "目标任务已存在", source, site, target_meta["hash"])
            return True
        if execution.task["preview"]:
            execution.record("skipped", "匹配与文件布局核验通过，可添加", source, site, target_meta["hash"])
            return True
        if execution.stopped():
            return False
        execution.save(f"添加 {site['name']} 候选")
        accepted = iyuu.submit_verified_torrent(
            plugin, content, target_meta["hash"], target, target_path, source.get("category"), site,
            source["hash"], service, source["source_added_at"], source["source_binding"],
            execution.generation, provider="pieces", source_path=source["save_path"],
            verified_metadata=metadata,
        )
        execution.record("added" if accepted else "skipped", "已暂停添加并提交校验" if accepted else "已存在或等待核对提交结果",
                         source, site, target_meta["hash"], target.name)
        if accepted:
            execution.counts[str(site["id"])] = execution.counts.get(str(site["id"]), 0) + 1
        return True
    except Exception as error:
        if isinstance(error, SiteDownloadError):
            execution.cooldown(budget_key, error.cooldown)
        message = str(error) if isinstance(error, ValueError) else f"候选处理失败（{type(error).__name__}）"
        execution.pieces_failure(message, source, site)
        return False


def verify_data_files(service, source_hash, metadata):
    """核对下载器的实际文件名和大小，拒绝重命名后的不明确映射。"""
    files = service.instance.get_files(source_hash)
    if isinstance(files, dict):
        files = list(files.values())
    if not files:
        raise ValueError("下载器未返回可核验的文件清单")
    actual = []
    for item in files:
        if isinstance(item, dict):
            name = item.get("name")
            length = item.get("size", item.get("length"))
        else:
            name = getattr(item, "name", None)
            length = getattr(item, "size", getattr(item, "length", None))
        if not name or length is None:
            raise ValueError("下载器文件清单缺少路径或长度")
        actual.append([str(name).replace("\\", "/"), int(length)])
    if sorted(actual) != sorted(metadata["files"]):
        raise ValueError("数据文件已重命名或布局变化，无法复用目标路径")
