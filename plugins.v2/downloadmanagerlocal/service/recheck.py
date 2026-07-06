"""做种校验服务边界，承载入口层以外的做种校验运行时逻辑。"""

from __future__ import annotations

import threading
import time
from typing import Any

from app.log import logger

from ..adapter.moviepilot import get_downloader_service
from ..model.state import SEED_RECHECK_QUEUE_KEY
from ..utils.torrent_adapter import get_hash, get_label


def load_seed_recheck_queue(plugin):
    """读取持久化做种校验队列。"""
    return plugin.get_data(SEED_RECHECK_QUEUE_KEY) or {}


def save_seed_recheck_queue(plugin, queue):
    """保存持久化做种校验队列。"""
    plugin.save_data(SEED_RECHECK_QUEUE_KEY, queue)


def register_seed_recheck(plugin, downloader, hashes, source):
    """注册一批待校验完成后自动开始做种的任务。"""
    if not hashes:
        return
    queue = load_seed_recheck_queue(plugin)
    for hash_text in hashes:
        existing = queue.get(hash_text, {})
        queue[hash_text] = {
            "hash": hash_text,
            "downloader": downloader,
            "source": source,
            "created_at": existing.get("created_at") or time.time(),
            "updated_at": time.time(),
            "attempts": existing.get("attempts", 0),
            "last_check": existing.get("last_check", 0),
            "max_wait_minutes": plugin._seed_max_wait_minutes,
        }
    save_seed_recheck_queue(plugin, queue)
    logger.info(f"做种校验：注册 {len(hashes)} 个待校验任务，来源={source}，下载器={downloader}")
    ensure_seed_recheck_worker(plugin)


def ensure_seed_recheck_worker(plugin):
    """确保按需做种校验 worker 已启动。"""
    with plugin._seed_recheck_lock:
        if plugin._seed_recheck_running:
            return
        plugin._seed_recheck_running = True
    thread = threading.Thread(
        target=seed_recheck_loop,
        args=(plugin,),
        name="DownloadManagerSeedRecheck",
        daemon=True,
    )
    thread.start()
    logger.info("做种校验：按需 worker 已启动")


def seed_recheck_loop(plugin):
    """持续处理做种校验队列，直到队列清空或插件停用。"""
    try:
        while plugin._enabled:
            queue = load_seed_recheck_queue(plugin)
            if not queue:
                logger.info("做种校验：队列已清空，worker 退出")
                break
            changed = process_seed_recheck_once(plugin, queue)
            if changed:
                save_seed_recheck_queue(plugin, queue)
            time.sleep(plugin._seed_check_interval)
    finally:
        with plugin._seed_recheck_lock:
            plugin._seed_recheck_running = False


def process_seed_recheck_once(plugin, queue):
    """处理一次做种校验队列并返回队列是否发生变化。"""
    changed = False
    grouped = {}
    for hash_text, item in queue.items():
        downloader_name = item.get("downloader", "")
        grouped.setdefault(downloader_name, []).append(item)
    for downloader_name, items in grouped.items():
        service = plugin.service_info(downloader_name)
        if not service:
            continue
        downloader = service.instance
        downloader_type = service.type
        hashes = [item["hash"] for item in items]
        try:
            torrents, _ = downloader.get_torrents(ids=hashes)
        except Exception as exc:
            logger.error(f"做种校验：查询下载器 {downloader_name} 失败: {exc}")
            continue
        if not torrents:
            continue
        task_map = {}
        for torrent in torrents:
            hash_text = plugin.get_hash(torrent, downloader_type)
            if hash_text:
                task_map[hash_text] = torrent
        for item in items:
            hash_text = item["hash"]
            task = task_map.get(hash_text)
            if not task:
                if seed_should_remove_missing(item):
                    queue.pop(hash_text, None)
                    changed = True
                    logger.info(f"做种校验：{hash_text} 在下载器中未找到，已移出队列")
                continue
            state = task.get("state") if downloader_type == "qbittorrent" else task.status
            if seed_is_checking(state, downloader_type):
                continue
            if seed_is_ready(state, downloader_type, task):
                try:
                    downloader.start_torrents(ids=[hash_text])
                    logger.info(f"做种校验：{hash_text} 校验完成，已自动开始做种，来源={item.get('source')}")
                    queue.pop(hash_text, None)
                    changed = True
                except Exception as exc:
                    logger.error(f"做种校验：{hash_text} 开始做种失败: {exc}")
                continue
            if seed_is_error(state, downloader_type):
                item["attempts"] = item.get("attempts", 0) + 1
                if item["attempts"] >= 5:
                    queue.pop(hash_text, None)
                    changed = True
                    logger.info(f"做种校验：{hash_text} 多次错误，已移出队列")
                continue
            if seed_is_timeout(item, plugin._seed_max_wait_minutes):
                queue.pop(hash_text, None)
                changed = True
                logger.info(f"做种校验：{hash_text} 等待超时（{plugin._seed_max_wait_minutes}分钟），已移出队列")
                continue
            item["last_check"] = time.time()
            changed = True
    return changed


def seed_should_remove_missing(item):
    """判断下载器缺失任务是否应从校验队列移除。"""
    elapsed = (time.time() - item.get("created_at", 0)) / 60
    return elapsed > max(item.get("max_wait_minutes", 120), 30)


def seed_is_checking(state, downloader_type):
    """判断种子是否仍处于校验或移动等不可开始状态。"""
    if downloader_type == "qbittorrent":
        return state in ["checkingUP", "checkingDL", "checkingResumeData", "checking", "queuedUP", "queuedDL", "moving"]
    return hasattr(state, "checking") and state.checking


def seed_is_ready(state, downloader_type, torrent=None):
    """判断种子是否已校验完成并可开始做种。"""
    if downloader_type == "qbittorrent":
        return state in ["pausedUP", "stoppedUP", "completed"]
    percent_done = getattr(torrent, "percent_done", getattr(state, "percent_done", 0))
    return hasattr(state, "stopped") and state.stopped and percent_done == 1


def seed_is_error(state, downloader_type):
    """判断种子是否处于需要计入失败次数的错误状态。"""
    if downloader_type == "qbittorrent":
        return state in ["missingFiles", "error", "unknown"]
    return False


def seed_is_timeout(item, max_wait_minutes):
    """判断校验任务是否已超过最大等待时间。"""
    elapsed = (time.time() - item.get("created_at", 0)) / 60
    return elapsed > item.get("max_wait_minutes", max_wait_minutes)


def run_recheck_cycle(plugin) -> None:
    """执行一次定时做种校验循环并兜底扫描可自动开始的暂停任务。"""
    if plugin._is_recheck_running:
        return

    plugin._is_recheck_running = True
    try:
        check_services = _collect_check_services(plugin)
        if not check_services:
            return

        if plugin._recheck_torrents:
            _process_legacy_recheck_queue(plugin, check_services)

        sweep_paused_seed_tasks(plugin, check_services)
    except Exception as exc:
        logger.error(f"做种校验服务执行失败: {exc}")
    finally:
        plugin._is_recheck_running = False


def sweep_paused_seed_tasks(plugin, check_services: list[Any]) -> None:
    """兜底扫描已完成但暂停的转移或铺种任务，并自动开始做种。"""
    for service in check_services:
        try:
            downloader = service.instance
            torrents, _ = downloader.get_torrents()
            if not torrents:
                continue
            ready_hashes, source_counts = _collect_ready_seed_hashes(
                plugin=plugin,
                torrents=torrents,
                downloader_type=service.type,
                only_tagged_sources=True,
            )
            if ready_hashes:
                source_text = "，".join(
                    f"{source} {count} 个" for source, count in source_counts.items()
                )
                logger.info(
                    f"做种校验服务：兜底发现下载器 {service.name} 中 {source_text} 已校验但未开始，开始做种"
                )
                downloader.start_torrents(ids=ready_hashes)
        except Exception as exc:
            logger.error(f"做种校验服务：兜底扫描下载器 {service.name} 失败: {exc}")


def can_seed_paused_torrent(torrent: Any, downloader_type: str) -> bool:
    """判断种子是否已完成校验并处于可自动开始做种的暂停状态。"""
    try:
        if downloader_type == "qbittorrent":
            return torrent.get("state") in ["pausedUP", "stoppedUP"]
        return torrent.status.stopped and torrent.percent_done == 1
    except Exception as exc:
        logger.error(f"判断种子做种状态失败: {exc}")
        return False


def _collect_check_services(plugin) -> list[Any]:
    """收集本轮需要检查的转移目标和 IYUU 辅种下载器服务。"""
    check_services = []
    seen_services = set()

    def add_check_service(service: Any) -> None:
        """按服务名去重加入本轮做种校验列表。"""
        if not service or not service.instance or service.name in seen_services:
            return
        check_services.append(service)
        seen_services.add(service.name)

    if plugin._todownloader:
        add_check_service(plugin.service_info(plugin._todownloader))

    if plugin._iyuu_enabled and plugin._iyuu_downloaders:
        for name in plugin._iyuu_downloaders:
            service = get_downloader_service(name)
            if service and not service.instance.is_inactive():
                add_check_service(service)

    return check_services


def _process_legacy_recheck_queue(plugin, check_services: list[Any]) -> None:
    """处理入口层历史内存队列中的待做种校验任务。"""
    for service in check_services:
        recheck_items = plugin._recheck_torrents.get(service.name, {})
        if isinstance(recheck_items, list):
            recheck_items = {hash_id: "历史队列" for hash_id in recheck_items}
            plugin._recheck_torrents[service.name] = recheck_items
        if not recheck_items:
            continue

        recheck_torrents = list(recheck_items.keys())
        logger.info(
            f"做种校验服务：开始检查下载器 {service.name} 的校验任务，共 {len(recheck_torrents)} 个 ..."
        )
        downloader = service.instance
        torrents, _ = downloader.get_torrents(ids=recheck_torrents)
        if torrents:
            ready_hashes, source_counts = _collect_ready_seed_hashes(
                plugin=plugin,
                torrents=torrents,
                downloader_type=service.type,
                recheck_items=recheck_items,
            )
            if ready_hashes:
                source_text = "，".join(
                    f"{source} {count} 个" for source, count in source_counts.items()
                ) or f"{len(ready_hashes)} 个"
                logger.info(f"做种校验服务：下载器 {service.name} 中 {source_text} 任务校验完成，开始做种")
                downloader.start_torrents(ids=ready_hashes)
                for hash_id in ready_hashes:
                    recheck_items.pop(hash_id, None)
                plugin._recheck_torrents[service.name] = recheck_items
            else:
                logger.info("做种校验服务：没有新的任务校验完成，将在下次周期继续检查 ...")
        elif torrents is None:
            logger.info(f"做种校验服务：下载器 {service.name} 查询校验任务失败，将在下次继续查询 ...")
        else:
            logger.info(f"做种校验服务：下载器 {service.name} 中没有需要检查的校验任务，清空待处理列表")
            plugin._recheck_torrents[service.name] = {}


def _collect_ready_seed_hashes(
    plugin,
    torrents: list[Any],
    downloader_type: str,
    recheck_items: dict[str, str] | None = None,
    only_tagged_sources: bool = False,
) -> tuple[list[str], dict[str, int]]:
    """从下载器任务列表中收集已可开始做种的 hash 和来源统计。"""
    ready_hashes = []
    source_counts: dict[str, int] = {}
    for torrent in torrents:
        if not can_seed_paused_torrent(torrent, downloader_type):
            continue
        source = _resolve_seed_source(plugin, torrent, downloader_type, recheck_items, only_tagged_sources)
        if only_tagged_sources and not source:
            continue
        hash_text = get_hash(torrent, downloader_type)
        if not hash_text:
            continue
        ready_hashes.append(hash_text)
        source_counts[source or "未知来源"] = source_counts.get(source or "未知来源", 0) + 1
    return ready_hashes, source_counts


def _resolve_seed_source(
    plugin,
    torrent: Any,
    downloader_type: str,
    recheck_items: dict[str, str] | None,
    only_tagged_sources: bool,
) -> str | None:
    """解析做种校验日志中的任务来源名称。"""
    hash_text = get_hash(torrent, downloader_type)
    if recheck_items is not None:
        return recheck_items.get(hash_text, "未知来源")
    if not only_tagged_sources:
        return "未知来源"

    labels = get_label(torrent, downloader_type) or []
    if plugin._iyuu_labelsafterseed:
        iyuu_labels = [
            label.strip()
            for label in plugin._iyuu_labelsafterseed.split(",")
            if label.strip()
        ]
        if any(label in labels for label in iyuu_labels):
            return "IYUU铺种"
    if plugin._torrent_tags and any(label in labels for label in plugin._torrent_tags):
        return "转移做种"
    return None

__all__ = (
    "ensure_seed_recheck_worker",
    "can_seed_paused_torrent",
    "load_seed_recheck_queue",
    "process_seed_recheck_once",
    "register_seed_recheck",
    "run_recheck_cycle",
    "save_seed_recheck_queue",
    "seed_is_checking",
    "seed_is_error",
    "seed_is_ready",
    "seed_is_timeout",
    "seed_recheck_loop",
    "seed_should_remove_missing",
    "sweep_paused_seed_tasks",
)
