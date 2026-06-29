"""按需做种校验模块"""

import time
import threading

from app.log import logger


def load_seed_recheck_queue(plugin):
    return plugin.get_data(plugin._seed_recheck_queue_key) or {}


def save_seed_recheck_queue(plugin, queue):
    plugin.save_data(plugin._seed_recheck_queue_key, queue)


def register_seed_recheck(plugin, downloader, hashes, source):
    if not hashes:
        return
    queue = load_seed_recheck_queue(plugin)
    for h in hashes:
        existing = queue.get(h, {})
        queue[h] = {
            "hash": h,
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
    with plugin._seed_recheck_lock:
        if plugin._seed_recheck_running:
            return
        plugin._seed_recheck_running = True
    thread = threading.Thread(
        target=seed_recheck_loop,
        args=(plugin,),
        name="DownloadManagerSeedRecheck",
        daemon=True
    )
    thread.start()
    logger.info("做种校验：按需 worker 已启动")


def seed_recheck_loop(plugin):
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
    changed = False
    grouped = {}
    for h, item in queue.items():
        dl = item.get("downloader", "")
        grouped.setdefault(dl, []).append(item)
    for downloader_name, items in grouped.items():
        svc = plugin.service_info(downloader_name)
        if not svc:
            continue
        dl = svc.instance
        dl_type = svc.type
        hashes = [it["hash"] for it in items]
        try:
            torrents, _ = dl.get_torrents(ids=hashes)
        except Exception as e:
            logger.error(f"做种校验：查询下载器 {downloader_name} 失败: {e}")
            continue
        if not torrents:
            continue
        task_map = {}
        for t in torrents:
            h = plugin.get_hash(t, dl_type)
            if h:
                task_map[h] = t
        for item in items:
            h = item["hash"]
            task = task_map.get(h)
            if not task:
                if seed_should_remove_missing(item):
                    queue.pop(h, None)
                    changed = True
                    logger.info(f"做种校验：{h} 在下载器中未找到，已移出队列")
                continue
            state = task.get("state") if dl_type == "qbittorrent" else task.status
            if seed_is_checking(state, dl_type):
                continue
            if seed_is_ready(state, dl_type, task):
                try:
                    dl.start_torrents(ids=[h])
                    logger.info(f"做种校验：{h} 校验完成，已自动开始做种，来源={item.get('source')}")
                    queue.pop(h, None)
                    changed = True
                except Exception as e:
                    logger.error(f"做种校验：{h} 开始做种失败: {e}")
                continue
            if seed_is_error(state, dl_type):
                item["attempts"] = item.get("attempts", 0) + 1
                if item["attempts"] >= 5:
                    queue.pop(h, None)
                    changed = True
                    logger.info(f"做种校验：{h} 多次错误，已移出队列")
                continue
            if seed_is_timeout(item, plugin._seed_max_wait_minutes):
                queue.pop(h, None)
                changed = True
                logger.info(f"做种校验：{h} 等待超时（{plugin._seed_max_wait_minutes}分钟），已移出队列")
                continue
            item["last_check"] = time.time()
            changed = True
    return changed


def seed_should_remove_missing(item):
    elapsed = (time.time() - item.get("created_at", 0)) / 60
    return elapsed > max(item.get("max_wait_minutes", 120), 30)


def seed_is_checking(state, dl_type):
    if dl_type == "qbittorrent":
        return state in ["checkingUP", "checkingDL", "checkingResumeData", "checking", "queuedUP", "queuedDL", "moving"]
    return hasattr(state, 'checking') and state.checking


def seed_is_ready(state, dl_type, torrent=None):
    if dl_type == "qbittorrent":
        return state in ["pausedUP", "stoppedUP", "completed"]
    percent_done = getattr(torrent, 'percent_done', getattr(state, 'percent_done', 0))
    return hasattr(state, 'stopped') and state.stopped and percent_done == 1


def seed_is_error(state, dl_type):
    if dl_type == "qbittorrent":
        return state in ["missingFiles", "error", "unknown"]
    return False


def seed_is_timeout(item, max_wait_minutes):
    elapsed = (time.time() - item.get("created_at", 0)) / 60
    return elapsed > item.get("max_wait_minutes", max_wait_minutes)
