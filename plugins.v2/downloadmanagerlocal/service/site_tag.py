"""站点标签写入、临时标签回收与人工清理服务。"""

from typing import Dict, Iterable, List, Optional

from app.log import logger

from ..adapter.moviepilot import generate_random_tag, get_site_indexer, get_url_domain, get_user_sites
from ..utils.tag_cleanup import (
    TEMP_TAG_PREFIX,
    classify_tag,
    is_auto_removable,
    normalize_tags,
)
from ..utils.torrent_adapter import get_hash, get_label


def _active_temporary_tags(plugin) -> set:
    """返回当前进程仍用于确认任务的临时标签集合。"""
    active_tags = getattr(plugin, "_active_temporary_tags", None)
    if not isinstance(active_tags, set):
        active_tags = set()
        plugin._active_temporary_tags = active_tags
    return active_tags


def create_temporary_tag(plugin, length: int = 10) -> str:
    """生成带下载中心归属前缀的临时标签并登记为活动状态。"""
    tag = f"{TEMP_TAG_PREFIX}{generate_random_tag(length)}"
    _active_temporary_tags(plugin).add(tag)
    return tag


def forget_temporary_tag(plugin, tag: str) -> None:
    """结束临时标签的活动状态，不修改下载器标签。"""
    _active_temporary_tags(plugin).discard(str(tag or ""))


def release_temporary_tag(plugin, dl, torrent_hash: str, tag: str, source: str) -> bool:
    """从已确认的 qBittorrent 任务移除临时标签并删除空标签定义。"""
    success = False
    try:
        if not torrent_hash or not tag:
            return False
        success = bool(dl.remove_torrents_tag(ids=torrent_hash, tag=tag))
        if success:
            dl.delete_torrents_tag(ids=torrent_hash, tag=tag)
        else:
            logger.warning(f"{source}：临时标签回收失败 hash={torrent_hash} tag={tag}")
        return success
    except Exception as err:
        logger.warning(f"{source}：临时标签回收异常 hash={torrent_hash} tag={tag}: {err}")
        return False
    finally:
        forget_temporary_tag(plugin, tag)


def _managed_tag_anchors(plugin) -> set:
    """返回可证明旧随机标签来自下载中心的业务锚点标签。"""
    managed = normalize_tags(getattr(plugin, "_torrent_tags", []) or [])
    iyuu_tags = str(getattr(plugin, "_iyuu_labelsafterseed", "") or "").split(",")
    managed.update(normalize_tags(iyuu_tags))
    return managed


def _read_qb_torrents(service) -> tuple:
    """读取 qBittorrent 全量任务并统一错误结果。"""
    torrents, error = service.instance.get_torrents()
    if error:
        return [], "下载器任务读取失败"
    return torrents or [], ""


def _group_tags(torrents: Iterable[dict]) -> tuple:
    """按标签聚合任务 hash、计数和名称样本。"""
    grouped: Dict[str, dict] = {}
    torrent_tags_by_hash: Dict[str, set] = {}
    for torrent in torrents or []:
        torrent_hash = get_hash(torrent, "qbittorrent")
        if not torrent_hash:
            continue
        tags = normalize_tags(get_label(torrent, "qbittorrent"))
        torrent_tags_by_hash[torrent_hash] = tags
        torrent_name = str(torrent.get("name", "") or torrent_hash)
        for tag in tags:
            item = grouped.setdefault(tag, {"hashes": [], "samples": []})
            item["hashes"].append(torrent_hash)
            if torrent_name not in item["samples"] and len(item["samples"]) < 3:
                item["samples"].append(torrent_name)
    return grouped, torrent_tags_by_hash


def _delete_empty_tag_definition(dl, tag: str, known_hashes: List[str]) -> bool:
    """仅在复查确认标签无人使用后删除 qBittorrent 全局标签定义。"""
    torrents, error = dl.get_torrents()
    if error:
        return False
    still_used = any(tag in normalize_tags(get_label(torrent, "qbittorrent")) for torrent in torrents or [])
    if still_used:
        return False
    return bool(dl.delete_torrents_tag(ids=known_hashes, tag=tag))


def _remove_tag_snapshot(dl, tag: str, hashes: Iterable[str]) -> dict:
    """只从扫描快照中的任务移除标签，并按需清除空标签定义。"""
    unique_hashes = sorted(normalize_tags(hashes))
    if not tag or not unique_hashes:
        return {"ok": False, "removed": 0, "definition_deleted": False}
    try:
        ok = bool(dl.remove_torrents_tag(ids=unique_hashes, tag=tag))
        definition_deleted = _delete_empty_tag_definition(dl, tag, unique_hashes) if ok else False
        return {
            "ok": ok,
            "removed": len(unique_hashes) if ok else 0,
            "definition_deleted": definition_deleted,
        }
    except Exception as err:
        logger.warning(f"标签清理失败 tag={tag} count={len(unique_hashes)}: {err}")
        return {"ok": False, "removed": 0, "definition_deleted": False, "error": str(err)}


def scan_and_clean_tags(plugin, downloader_names: Iterable[str]) -> dict:
    """扫描所选下载器，自动移除明确的临时标签并返回其余标签快照。"""
    names = list(dict.fromkeys(normalize_tags(downloader_names)))
    if not names:
        return {"code": 1, "msg": "请至少选择一个下载器", "downloaders": [], "auto_removed": []}

    active_tags = set(_active_temporary_tags(plugin))
    managed_tags = _managed_tag_anchors(plugin)
    site_prefix = str(getattr(plugin, "_tag_siteprefix", "") or "")
    downloader_results = []
    auto_removed = []
    errors = []

    for downloader_name in names:
        service = plugin.service_info(downloader_name)
        if not service:
            errors.append({"downloader": downloader_name, "message": "下载器不可用"})
            continue
        if service.type != "qbittorrent":
            errors.append({"downloader": downloader_name, "message": "仅支持 qBittorrent 标签清理"})
            continue

        torrents, error_message = _read_qb_torrents(service)
        if error_message:
            errors.append({"downloader": downloader_name, "message": error_message})
            continue

        grouped, torrent_tags_by_hash = _group_tags(torrents)
        remaining = []
        for tag in sorted(grouped, key=str.casefold):
            snapshot = grouped[tag]
            kind = classify_tag(
                tag=tag,
                hashes=snapshot["hashes"],
                torrent_tags_by_hash=torrent_tags_by_hash,
                managed_tags=managed_tags,
                active_tags=active_tags,
                site_prefix=site_prefix,
            )
            item = {
                "tag": tag,
                "kind": kind,
                "count": len(set(snapshot["hashes"])),
                "hashes": sorted(set(snapshot["hashes"])),
                "samples": snapshot["samples"],
            }
            if is_auto_removable(kind):
                cleanup = _remove_tag_snapshot(service.instance, tag, item["hashes"])
                if cleanup["ok"]:
                    auto_removed.append({"downloader": downloader_name, **item, **cleanup})
                    continue
                item["cleanup_error"] = cleanup.get("error") or "自动清理失败"
            remaining.append(item)

        downloader_results.append({
            "name": downloader_name,
            "type": service.type,
            "task_count": len(torrents),
            "tags": remaining,
        })

    if auto_removed:
        logger.info(
            "标签清理扫描：自动移除临时标签 %s 个，任务关联 %s 条",
            len(auto_removed),
            sum(item["removed"] for item in auto_removed),
        )
    code = 0 if downloader_results else 1
    return {
        "code": code,
        "msg": "扫描完成" if code == 0 else "未能扫描所选下载器",
        "downloaders": downloader_results,
        "auto_removed": auto_removed,
        "errors": errors,
    }


def execute_tag_cleanup(plugin, removals: Iterable[dict]) -> dict:
    """按前端确认的标签与任务 hash 快照执行人工清理。"""
    removal_items = [item for item in removals or [] if isinstance(item, dict)]
    if not removal_items:
        return {"code": 1, "msg": "没有需要清理的标签", "removed": [], "failed": []}

    active_tags = set(_active_temporary_tags(plugin))
    removed = []
    failed = []
    service_cache = {}
    for item in removal_items[:1000]:
        downloader_name = str(item.get("downloader") or "").strip()
        tag = str(item.get("tag") or "").strip()
        requested_hashes = sorted(normalize_tags(item.get("hashes") or []))[:5000]
        if not downloader_name or not tag or not requested_hashes:
            failed.append({"downloader": downloader_name, "tag": tag, "message": "清理参数不完整"})
            continue
        if tag in active_tags:
            failed.append({"downloader": downloader_name, "tag": tag, "message": "临时标签仍在使用"})
            continue

        service = service_cache.get(downloader_name)
        if service is None:
            service = plugin.service_info(downloader_name)
            service_cache[downloader_name] = service
        if not service or service.type != "qbittorrent":
            failed.append({"downloader": downloader_name, "tag": tag, "message": "下载器不可用或类型不支持"})
            continue

        torrents, error = service.instance.get_torrents(ids=requested_hashes)
        if error:
            failed.append({"downloader": downloader_name, "tag": tag, "message": "任务快照复核失败"})
            continue
        current_hashes = [
            get_hash(torrent, "qbittorrent")
            for torrent in torrents or []
            if tag in normalize_tags(get_label(torrent, "qbittorrent"))
        ]
        cleanup = _remove_tag_snapshot(service.instance, tag, current_hashes)
        result = {"downloader": downloader_name, "tag": tag, "hashes": current_hashes, **cleanup}
        if cleanup["ok"]:
            removed.append(result)
        else:
            result["message"] = cleanup.get("error") or "标签移除失败"
            failed.append(result)

    logger.info(
        "标签清理执行：成功标签 %s 个，任务关联 %s 条，失败 %s 个",
        len(removed),
        sum(item["removed"] for item in removed),
        len(failed),
    )
    return {
        "code": 0 if removed and not failed else (2 if removed else 1),
        "msg": f"已清理 {len(removed)} 个标签，失败 {len(failed)} 个",
        "removed": removed,
        "failed": failed,
    }


def find_site_by_domain(domain: str) -> Optional[str]:
    """通过域名从系统站点配置中查找站点名称（优先 SystemConfigOper，fallback SitesHelper）"""
    # 方式1：SystemConfigOper（无需认证，调度器环境可用）
    try:
        sites = get_user_sites()
        if sites:
            site_values = sites.values() if isinstance(sites, dict) else sites
            for site_info in site_values:
                if not isinstance(site_info, dict):
                    continue
                site_domain = site_info.get("domain", "")
                if not site_domain:
                    continue
                site_domain_clean = get_url_domain(site_domain)
                if site_domain_clean and site_domain_clean in domain:
                    return site_info.get("name")
                if domain in site_domain:
                    return site_info.get("name")
    except Exception:
        pass

    # 方式2：SitesHelper（需要用户认证，作为 fallback）
    try:
        site_info = get_site_indexer(domain)
        if site_info:
            return site_info.get("name")
    except Exception:
        pass

    return None


def tag_torrent(plugin, dl, dl_type: str, torrent_hash: str, torrent_tags: list, trackers: list):
    """给种子打站点标签（通过 SystemConfigOper 读取站点配置，无需用户认证）"""
    try:
        # 通过 tracker 解析站点
        site_name = None
        for tracker in trackers:
            domain = None
            for key, mapped in plugin._tracker_mappings.items():
                if key in tracker:
                    domain = mapped
                    break
            if not domain:
                domain = get_url_domain(tracker)
            if not domain:
                continue
            # 从系统配置中查找匹配的站点
            site_name = find_site_by_domain(domain)
            if site_name:
                break

        if not site_name:
            logger.info(f"转移后标签：无法识别站点 hash={torrent_hash}")
            return

        # 构造标签
        site_tag = (plugin._tag_siteprefix + site_name) if plugin._tag_siteprefix else site_name
        if site_tag in torrent_tags:
            logger.info(f"转移后标签：标签已存在 hash={torrent_hash}")
            return

        # 设置标签
        if dl_type == "qbittorrent":
            dl.set_torrents_tag(ids=torrent_hash, tags=[site_tag])
        else:
            dl.set_torrent_tag(ids=torrent_hash, tags=[site_tag])
        logger.info(f"转移后标签成功: hash={torrent_hash} tag={site_tag}")
    except Exception as e:
        logger.error(f"转移后标签失败 hash={torrent_hash}: {e}")


__all__ = (
    "create_temporary_tag",
    "execute_tag_cleanup",
    "find_site_by_domain",
    "forget_temporary_tag",
    "release_temporary_tag",
    "scan_and_clean_tags",
    "tag_torrent",
)
