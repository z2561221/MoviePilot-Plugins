"""站点标签写入、临时标签回收与人工清理服务。"""

from typing import Dict, Iterable, List, Optional
from urllib.parse import urlsplit

from app.sdk.config import settings
from app.sdk.logging import logger

from ..adapter.moviepilot import generate_random_tag, get_site_indexer, list_site_dicts
from ..model.state import iyuu_history_key, iyuu_source_key
from ..utils.tag_cleanup import (
    TEMP_TAG_PREFIX,
    classify_tag,
    is_auto_removable,
    normalize_tags,
)
from ..utils.torrent_adapter import get_hash, get_label, get_tracker_urls
from .activity import observed


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


def cleanup_temporary_tags_for_event(plugin, event) -> dict:
    """按下载新增事件清理来源或目标下载器当前任务上的新临时标签。"""
    event_data = getattr(event, "event_data", None)
    if not isinstance(event_data, dict):
        return {"handled": False, "reason": "invalid_event"}

    downloader_name = str(
        event_data.get("downloader")
        or event_data.get("downloader_name")
        or ""
    ).strip()
    selected_downloaders = normalize_tags((
        getattr(plugin, "_fromdownloader", ""),
        getattr(plugin, "_todownloader", ""),
    ))
    if not downloader_name or downloader_name not in selected_downloaders:
        return {
            "handled": False,
            "downloader": downloader_name,
            "reason": "downloader_not_selected",
        }

    torrent_hash = str(
        event_data.get("hash")
        or event_data.get("torrent_hash")
        or event_data.get("download_hash")
        or ""
    ).strip()
    if not torrent_hash:
        return {"handled": False, "downloader": downloader_name, "reason": "hash_missing"}

    service = plugin.service_info(downloader_name)
    if not service or str(getattr(service, "type", "")).lower() != "qbittorrent":
        return {
            "handled": False,
            "downloader": downloader_name,
            "hash": torrent_hash,
            "reason": "unsupported_downloader",
        }

    try:
        response = service.instance.get_torrents(ids=[torrent_hash])
        if isinstance(response, tuple) and len(response) == 2:
            torrents, error = response
        else:
            torrents, error = response, None
    except Exception as err:
        logger.warning(f"下载新增事件：读取任务失败 downloader={downloader_name} hash={torrent_hash}: {err}")
        return {
            "handled": True,
            "downloader": downloader_name,
            "hash": torrent_hash,
            "reason": "torrent_read_failed",
        }

    if error or not torrents:
        return {
            "handled": True,
            "downloader": downloader_name,
            "hash": torrent_hash,
            "reason": "torrent_not_found" if not error else "torrent_read_failed",
        }

    torrent = next(
        (
            item for item in torrents
            if str(get_hash(item, "qbittorrent") or "").lower() == torrent_hash.lower()
        ),
        torrents[0],
    )
    current_hash = get_hash(torrent, "qbittorrent") or torrent_hash
    current_tags = normalize_tags(get_label(torrent, "qbittorrent"))
    if not current_tags:
        return {
            "handled": True,
            "downloader": downloader_name,
            "hash": current_hash,
            "removed": [],
            "reason": "no_tags",
        }

    managed_tags = _managed_tag_anchors(plugin)
    active_tags = _active_temporary_tags(plugin)
    event_tags_by_hash = {current_hash: current_tags}
    grouped_tags = None
    grouped_tags_by_hash = event_tags_by_hash
    removed = []
    failed = []
    for tag in sorted(current_tags, key=str.casefold):
        kind = classify_tag(
            tag=tag,
            hashes=[current_hash],
            torrent_tags_by_hash=event_tags_by_hash,
            managed_tags=managed_tags,
            active_tags=active_tags,
            site_prefix=str(getattr(plugin, "_tag_siteprefix", "") or ""),
        )

        # 旧式随机标签必须先确认不是多个任务共用的普通标签。
        if kind in {"legacy_temporary", "legacy_candidate"} and grouped_tags is None:
            all_torrents, all_error = _read_qb_torrents(service)
            if all_error:
                failed.append({"tag": tag, "kind": kind, "reason": all_error})
                grouped_tags = {}
                grouped_tags_by_hash = {}
                continue
            grouped_tags, grouped_tags_by_hash = _group_tags(all_torrents)

        if grouped_tags is not None and kind in {"legacy_temporary", "legacy_candidate"}:
            snapshot = grouped_tags.get(tag, {})
            kind = classify_tag(
                tag=tag,
                hashes=snapshot.get("hashes", []),
                torrent_tags_by_hash=grouped_tags_by_hash,
                managed_tags=managed_tags,
                active_tags=active_tags,
                site_prefix=str(getattr(plugin, "_tag_siteprefix", "") or ""),
            )

        if not is_auto_removable(kind):
            continue

        if release_temporary_tag(plugin, service.instance, current_hash, tag, "下载新增事件"):
            removed.append(tag)
        else:
            failed.append({"tag": tag, "kind": kind})

    if removed:
        logger.info(
            "下载新增事件：自动移除临时标签 downloader=%s hash=%s tags=%s",
            downloader_name,
            current_hash,
            ",".join(removed),
        )
    return {
        "handled": True,
        "downloader": downloader_name,
        "hash": current_hash,
        "removed": removed,
        "failed": failed,
    }


def _managed_tag_anchors(plugin) -> set:
    """返回可证明旧随机标签来自下载中心的业务锚点标签。"""
    managed = normalize_tags(getattr(plugin, "_torrent_tags", []) or [])
    iyuu_tags = str(getattr(plugin, "_iyuu_labelsafterseed", "") or "").split(",")
    managed.update(normalize_tags(iyuu_tags))
    managed.update(normalize_tags(getattr(settings, "TORRENT_TAG", "") or ""))
    return managed


def _read_download_torrents(instance, ids=None) -> tuple:
    """读取 QB/TR 任务，区分成功空结果与连接/查询失败。"""
    try:
        response = instance.get_torrents(ids=ids) if ids is not None else instance.get_torrents()
    except Exception:
        return [], "下载器任务读取失败"
    torrents, error = response if isinstance(response, tuple) and len(response) == 2 else (response, None)
    if error or torrents is None:
        return [], "下载器任务读取失败"
    return torrents or [], ""


def _read_qb_torrents(service) -> tuple:
    """兼容下载新增事件中的 qB 全量任务检查。"""
    return _read_download_torrents(service.instance)


def _torrent_name(torrent, fallback: str) -> str:
    """读取 QB 字典或 Transmission 对象上的任务名称。"""
    if isinstance(torrent, dict):
        return str(torrent.get("name") or fallback)
    return str(getattr(torrent, "name", "") or fallback)


def _label_list(values) -> list[str]:
    """按原顺序去重标签，兼容 QB 逗号字符串和 TR 标签列表。"""
    if isinstance(values, str):
        values = values.split(",")
    return list(dict.fromkeys(str(value).strip() for value in values or [] if str(value).strip()))


def _write_transmission_labels(dl, torrent_hash: str, labels: list[str]) -> bool:
    """Transmission 整组覆盖 labels；空列表需绕过只接受非空标签的宿主包装。"""
    if labels:
        return dl.set_torrent_tag(ids=torrent_hash, tags=labels) is not False
    client = getattr(dl, "trc", None)
    if not client:
        return False
    try:
        return client.change_torrent(ids=torrent_hash, labels=[]) is not False
    except Exception:
        return False


def _read_tracker_domain(value: str) -> str:
    """从完整 tracker URL、裸域名或 host:port 中提取规范主机名。"""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = urlsplit(text if "://" in text else "//" + text)
        host = parsed.hostname or ""
        return host.rstrip(".").encode("idna").decode("ascii").lower() if host else ""
    except (UnicodeError, ValueError):
        return ""


def _mapped_tracker_domain(tracker: str, mappings: dict[str, str]) -> str:
    """先精确命中显式映射，再允许 tracker 子域命中最长映射域。"""
    host = _read_tracker_domain(tracker)
    candidates = []
    for source, target in (mappings or {}).items():
        source_host = _read_tracker_domain(source)
        target_host = _read_tracker_domain(target)
        if source_host and target_host and (host == source_host or host.endswith("." + source_host)):
            candidates.append((len(source_host), target_host))
    return max(candidates, default=(0, host))[1]


def _group_tags(torrents: Iterable, downloader_type: str = "qbittorrent") -> tuple:
    """按标签聚合任务 hash、计数和名称样本。"""
    grouped: Dict[str, dict] = {}
    torrent_tags_by_hash: Dict[str, set] = {}
    for torrent in torrents or []:
        torrent_hash = get_hash(torrent, downloader_type)
        if not torrent_hash:
            continue
        tags = normalize_tags(get_label(torrent, downloader_type))
        torrent_tags_by_hash[torrent_hash] = tags
        torrent_name = _torrent_name(torrent, torrent_hash)
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


def _remove_tag_snapshot(dl, tag: str, hashes: Iterable[str], downloader_type: str = "qbittorrent") -> dict:
    """只从扫描快照中的任务移除标签，并按需清除空标签定义。"""
    unique_hashes = sorted(normalize_tags(hashes))
    if not tag or not unique_hashes:
        return {"ok": False, "removed": 0, "definition_deleted": False}
    if downloader_type == "transmission":
        torrents, error = _read_download_torrents(dl, ids=unique_hashes)
        if error:
            return {
                "ok": False,
                "removed": 0,
                "removed_hashes": [],
                "skipped_hashes": [],
                "failed_hashes": unique_hashes,
                "definition_deleted": False,
                "error": error,
            }
        requested = {value.lower() for value in unique_hashes}
        requested_names = {value.lower(): value for value in unique_hashes}
        updates = {}
        skipped_hashes = []
        failed = []
        found = set()
        for torrent in torrents:
            torrent_hash = get_hash(torrent, downloader_type)
            normalized_hash = torrent_hash.lower()
            if normalized_hash not in requested:
                continue
            found.add(normalized_hash)
            current = _label_list(get_label(torrent, downloader_type))
            if tag not in current:
                skipped_hashes.append(requested_names[normalized_hash])
                continue
            remaining = [value for value in current if value != tag]
            if _write_transmission_labels(dl, torrent_hash, remaining):
                updates[torrent_hash] = set(remaining)
            else:
                failed.append(torrent_hash)
        skipped_hashes.extend(
            requested_names[torrent_hash]
            for torrent_hash in sorted(requested - found)
        )
        verified_count = 0
        removed_hashes = []
        if updates:
            verified, verify_error = _read_download_torrents(dl, ids=list(updates))
            if verify_error:
                return {
                    "ok": False,
                    "removed": 0,
                    "removed_hashes": [],
                    "skipped_hashes": skipped_hashes,
                    "failed_hashes": list(updates),
                    "definition_deleted": False,
                    "error": verify_error,
                }
            actual = {
                get_hash(torrent, downloader_type).lower(): normalize_tags(get_label(torrent, downloader_type))
                for torrent in verified
            }
            for torrent_hash, expected in updates.items():
                observed = actual.get(torrent_hash.lower())
                if observed is None:
                    skipped_hashes.append(requested_names[torrent_hash.lower()])
                    continue
                if tag in observed or not expected.issubset(observed):
                    failed.append(torrent_hash)
                else:
                    verified_count += 1
                    removed_hashes.append(requested_names[torrent_hash.lower()])
        return {
            "ok": not failed,
            "removed": verified_count,
            "removed_hashes": removed_hashes,
            "skipped_hashes": list(dict.fromkeys(skipped_hashes)),
            "failed_hashes": list(dict.fromkeys(failed)),
            "definition_deleted": False,
            **({"error": "Transmission 标签写入或回读不一致"} if failed else {}),
        }
    if downloader_type != "qbittorrent":
        return {"ok": False, "removed": 0, "definition_deleted": False, "error": "下载器类型不支持"}
    try:
        ok = bool(dl.remove_torrents_tag(ids=unique_hashes, tag=tag))
        definition_deleted = _delete_empty_tag_definition(dl, tag, unique_hashes) if ok else False
        return {
            "ok": ok,
            "removed": len(unique_hashes) if ok else 0,
            "removed_hashes": unique_hashes if ok else [],
            "skipped_hashes": [],
            "failed_hashes": [] if ok else unique_hashes,
            "definition_deleted": definition_deleted,
        }
    except Exception as err:
        logger.warning(f"标签清理失败 tag={tag} count={len(unique_hashes)}: {err}")
        return {
            "ok": False,
            "removed": 0,
            "removed_hashes": [],
            "skipped_hashes": [],
            "failed_hashes": unique_hashes,
            "definition_deleted": False,
            "error": str(err),
        }


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
    skipped = []
    errors = []

    for downloader_name in names:
        service = plugin.service_info(downloader_name)
        if not service:
            errors.append({"downloader": downloader_name, "message": "下载器不可用"})
            continue
        downloader_type = str(service.type or "").lower()
        if downloader_type not in {"qbittorrent", "transmission"}:
            errors.append({"downloader": downloader_name, "message": "下载器类型不支持标签清理"})
            continue

        torrents, error_message = _read_download_torrents(service.instance)
        if error_message:
            errors.append({"downloader": downloader_name, "message": error_message})
            continue

        grouped, torrent_tags_by_hash = _group_tags(torrents, downloader_type)
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
                cleanup = _remove_tag_snapshot(service.instance, tag, item["hashes"], downloader_type)
                if cleanup["ok"]:
                    if cleanup["removed"]:
                        auto_removed.append({"downloader": downloader_name, **item, **cleanup})
                    else:
                        skipped.append({
                            "downloader": downloader_name,
                            **item,
                            "hashes": cleanup.get("skipped_hashes") or item["hashes"],
                            "message": "扫描期间任务或标签已不存在，无需清理",
                        })
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
        "skipped": skipped,
        "errors": errors,
    }


def execute_tag_cleanup(plugin, removals: Iterable[dict]) -> dict:
    """按前端确认的标签与任务 hash 快照执行人工清理。"""
    removal_items = [item for item in removals or [] if isinstance(item, dict)]
    if not removal_items:
        return {"code": 1, "msg": "没有需要清理的标签", "removed": [], "failed": []}

    active_tags = set(_active_temporary_tags(plugin))
    removed = []
    skipped = []
    failed = []
    service_cache = {}
    for item in removal_items[:1000]:
        downloader_name = str(item.get("downloader") or "").strip()
        tag = str(item.get("tag") or "").strip()
        requested_hashes = sorted(normalize_tags(item.get("hashes") or []))
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
        downloader_type = str(getattr(service, "type", "") or "").lower() if service else ""
        if downloader_type not in {"qbittorrent", "transmission"}:
            failed.append({"downloader": downloader_name, "tag": tag, "message": "下载器不可用或类型不支持"})
            continue

        if downloader_type == "transmission":
            current, read_error = _read_download_torrents(service.instance, ids=requested_hashes)
            if read_error:
                failed.append({"downloader": downloader_name, "tag": tag, "message": "任务快照复核失败"})
                continue
            requested = {value.lower() for value in requested_hashes}
            current_hashes = [
                get_hash(torrent, downloader_type)
                for torrent in current
                if get_hash(torrent, downloader_type).lower() in requested
                and tag in normalize_tags(get_label(torrent, downloader_type))
            ]
            if not current_hashes:
                skipped.append({
                    "downloader": downloader_name,
                    "tag": tag,
                    "hashes": requested_hashes,
                    "message": "确认任务或目标标签已不存在，无需清理",
                })
                continue
        else:
            current_hashes = requested_hashes
        chunks = [requested_hashes[index:index + 5000] for index in range(0, len(requested_hashes), 5000)]
        removed_hashes = []
        skipped_hashes = []
        definition_deleted = False
        for chunk in chunks:
            if downloader_type == "transmission":
                chunk = [value for value in chunk if value.lower() in {item.lower() for item in current_hashes}]
                if not chunk:
                    continue
            cleanup = _remove_tag_snapshot(service.instance, tag, chunk, downloader_type)
            removed_hashes.extend(cleanup.get("removed_hashes", []))
            skipped_hashes.extend(cleanup.get("skipped_hashes", []))
            definition_deleted = definition_deleted or cleanup.get("definition_deleted", False)
            if not cleanup["ok"]:
                failed.append({
                    "downloader": downloader_name,
                    "tag": tag,
                    "hashes": cleanup.get("failed_hashes") or chunk,
                    "message": cleanup.get("error") or "部分标签未能清理",
                })
        removed_hashes = list(dict.fromkeys(removed_hashes))
        skipped_hashes = list(dict.fromkeys(skipped_hashes))
        if removed_hashes:
            removed.append({
                "downloader": downloader_name,
                "tag": tag,
                "hashes": removed_hashes,
                "ok": True,
                "removed": len(removed_hashes),
                "definition_deleted": definition_deleted,
            })
        if skipped_hashes:
            skipped.append({
                "downloader": downloader_name,
                "tag": tag,
                "hashes": skipped_hashes,
                "message": "确认任务或目标标签已不存在，无需清理",
            })

    logger.info(
        "标签清理执行：成功标签 %s 个，任务关联 %s 条，失败 %s 个",
        len(removed),
        sum(item["removed"] for item in removed),
        len(failed),
    )
    code = 0 if not failed else (2 if removed or skipped else 1)
    if failed:
        message = f"已清理 {len(removed)} 个标签，失败 {len(failed)} 项，跳过 {len(skipped)} 项"
    elif removed:
        message = f"已清理 {len(removed)} 个标签，另有 {len(skipped)} 项无需处理"
    elif skipped:
        message = f"所选任务或标签已不存在，无需清理 {len(skipped)} 项"
    else:
        message = "没有需要清理的标签"
    return {
        "code": code,
        "msg": message,
        "removed": removed,
        "skipped": skipped,
        "failed": failed,
    }


def find_site_by_domain(domain: str) -> Optional[str]:
    """通过精确域名或边界安全的父域匹配站点名称。"""
    host = _read_tracker_domain(domain)
    if not host:
        return None
    try:
        sites = list_site_dicts()
        exact = []
        parent = []
        for site_info in sites:
            site_domain = site_info.get("domain") or site_info.get("url") or ""
            site_host = _read_tracker_domain(site_domain)
            if not site_host:
                continue
            if host == site_host:
                exact.append((site_host, site_info.get("name")))
            elif host.endswith("." + site_host):
                parent.append((site_host, site_info.get("name")))
        matched = exact or parent
        if matched:
            longest = max(len(site_host) for site_host, _ in matched)
            names = {name for site_host, name in matched if len(site_host) == longest and name}
            return next(iter(names)) if len(names) == 1 else None
    except Exception:
        pass

    try:
        site_info = get_site_indexer(host)
        if site_info:
            return site_info.get("name")
    except Exception:
        pass

    return None


def _site_tag_for_trackers(plugin, trackers: Iterable[str], site_cache: dict) -> str:
    """按 tracker 映射和站点目录计算可恢复的站点标签。"""
    mappings = getattr(plugin, "_tracker_mappings", {}) or {}
    for tracker in trackers or []:
        domain = _mapped_tracker_domain(str(tracker or ""), mappings)
        if not domain:
            continue
        if domain not in site_cache:
            site_cache[domain] = find_site_by_domain(domain)
        site_name = site_cache[domain]
        if site_name:
            prefix = str(getattr(plugin, "_tag_siteprefix", "") or "")
            return f"{prefix}{site_name}"
    return ""


def _has_transfer_history(plugin, downloader_name: str, torrent_hash: str, source_service, cache: dict) -> bool:
    """只接受源、目标和 hash 均匹配的已完成转移记录。"""
    if not source_service or not getattr(source_service, "name", ""):
        return False
    cache_key = (source_service.name, downloader_name, torrent_hash.casefold())
    if cache_key not in cache:
        record = plugin.get_data(key=f"{source_service.name}-{torrent_hash}")
        cache[cache_key] = bool(
            isinstance(record, dict)
            and record.get("transfer_state") == "completed"
            and str(record.get("to_download") or "") == downloader_name
            and str(record.get("to_download_id") or "").casefold() == torrent_hash.casefold()
        )
    return cache[cache_key]


def _has_iyuu_history(plugin, downloader_name: str, torrent_hash: str, cache: dict) -> bool:
    """通过母种历史反查确认该下载器上的任务确由 IYUU 辅种。"""
    cache_key = (downloader_name, torrent_hash.casefold())
    if cache_key not in cache:
        source_hash = plugin.get_data(key=iyuu_source_key(torrent_hash))
        if not source_hash:
            cache[cache_key] = False
        else:
            history = plugin.get_data(key=iyuu_history_key(str(source_hash))) or []
            cache[cache_key] = any(
                isinstance(item, dict)
                and str(item.get("downloader") or "") == downloader_name
                and torrent_hash.casefold() in {
                    str(value or "").casefold() for value in item.get("torrents") or []
                }
                for item in history
            )
    return cache[cache_key]


def _expected_completion_tags(
    plugin,
    downloader_name: str,
    torrent,
    dl_type: str,
    *,
    source_service,
    site_cache: dict,
    transfer_cache: dict,
    iyuu_cache: dict,
) -> dict[str, set[str]]:
    """返回当前任务有证据可恢复的站点、转移和 IYUU 标签。"""
    torrent_hash = str(get_hash(torrent, dl_type) or "").strip()
    expected = {"site": set(), "transfer": set(), "iyuu": set()}
    site_tag = _site_tag_for_trackers(plugin, get_tracker_urls(torrent, dl_type), site_cache)
    if site_tag:
        expected["site"].add(site_tag)
    transfer_tags = _label_list(getattr(plugin, "_torrent_tags", []) or [])
    if torrent_hash and transfer_tags and _has_transfer_history(
        plugin, downloader_name, torrent_hash, source_service, transfer_cache,
    ):
        expected["transfer"].update(transfer_tags)
    iyuu_tags = _label_list(getattr(plugin, "_iyuu_labelsafterseed", "") or "")
    if torrent_hash and iyuu_tags and _has_iyuu_history(plugin, downloader_name, torrent_hash, iyuu_cache):
        expected["iyuu"].update(iyuu_tags)
    return expected


def scan_tag_completion(plugin, downloader_names: Iterable[str]) -> dict:
    """扫描所选 QB/TR 下载器中可由 tracker 或插件历史确认的缺失标签。"""
    names = list(dict.fromkeys(normalize_tags(downloader_names)))
    if not names:
        return {"code": 1, "msg": "请至少选择一个下载器", "downloaders": [], "errors": []}

    source_name = getattr(plugin, "_fromdownloader", "")
    source_service = plugin.service_info(source_name) if source_name else None
    site_cache = {}
    transfer_cache = {}
    iyuu_cache = {}
    downloaders = []
    errors = []

    for downloader_name in names:
        service = plugin.service_info(downloader_name)
        if not service:
            errors.append({"downloader": downloader_name, "message": "下载器不可用"})
            continue
        dl_type = str(getattr(service, "type", "") or "").lower()
        if dl_type not in {"qbittorrent", "transmission"}:
            errors.append({"downloader": downloader_name, "message": "仅支持 qBittorrent 与 Transmission 标签补全"})
            continue

        torrents, error = _read_download_torrents(service.instance)
        if error:
            errors.append({"downloader": downloader_name, "message": error})
            continue

        grouped = {}
        tracker_unmatched = 0
        for torrent in torrents:
            torrent_hash = str(get_hash(torrent, dl_type) or "").strip()
            if not torrent_hash:
                continue
            current_tags = set(_label_list(get_label(torrent, dl_type)))
            expected = _expected_completion_tags(
                plugin,
                service.name or downloader_name,
                torrent,
                dl_type,
                source_service=source_service,
                site_cache=site_cache,
                transfer_cache=transfer_cache,
                iyuu_cache=iyuu_cache,
            )
            trackers = get_tracker_urls(torrent, dl_type)
            if trackers and not expected["site"]:
                tracker_unmatched += 1
            for kind, tags in expected.items():
                for tag in tags - current_tags:
                    item = grouped.setdefault((kind, tag), {"kind": kind, "tag": tag, "hashes": set(), "samples": []})
                    item["hashes"].add(torrent_hash)
                    name = _torrent_name(torrent, torrent_hash)
                    if name not in item["samples"] and len(item["samples"]) < 3:
                        item["samples"].append(name)

        tag_groups = [
            {
                "kind": item["kind"],
                "tag": item["tag"],
                "hashes": sorted(item["hashes"]),
                "count": len(item["hashes"]),
                "samples": item["samples"],
            }
            for item in sorted(grouped.values(), key=lambda value: (value["kind"], value["tag"].casefold()))
        ]
        downloaders.append({
            "name": downloader_name,
            "type": dl_type,
            "task_count": len(torrents),
            "missing_count": sum(item["count"] for item in tag_groups),
            "unmatched_tracker_count": tracker_unmatched,
            "tags": tag_groups,
        })

    return {
        "code": 0 if downloaders else 1,
        "msg": "扫描完成" if downloaders else "未能扫描所选下载器",
        "downloaders": downloaders,
        "errors": errors,
    }


def execute_tag_completion(plugin, repairs: Iterable[dict]) -> dict:
    """重新读取任务并验证来源，只追加确认且仍有效的缺失标签。"""
    requested = {}
    for item in list(repairs or [])[:1000]:
        if not isinstance(item, dict):
            continue
        downloader_name = str(item.get("downloader") or "").strip()
        tag = str(item.get("tag") or "").strip()
        kind = str(item.get("kind") or "").strip()
        hashes = list(dict.fromkeys(
            str(value or "").strip()
            for value in (item.get("hashes") or [])[:5000]
            if str(value or "").strip()
        ))
        if not downloader_name or not tag or kind not in {"site", "transfer", "iyuu"}:
            continue
        for torrent_hash in hashes:
            key = (downloader_name, torrent_hash)
            requested.setdefault(key, {}).setdefault(kind, set()).add(tag)

    if not requested:
        return {"code": 0, "msg": "没有待补全标签", "added": [], "skipped": [], "failed": []}

    source_name = getattr(plugin, "_fromdownloader", "")
    source_service = plugin.service_info(source_name) if source_name else None
    site_cache = {}
    transfer_cache = {}
    iyuu_cache = {}
    service_cache = {}
    added = []
    skipped = []
    failed = []

    for (downloader_name, torrent_hash), by_kind in requested.items():
        if downloader_name not in service_cache:
            service_cache[downloader_name] = plugin.service_info(downloader_name)
        service = service_cache[downloader_name]
        if not service or not getattr(service, "instance", None):
            failed.append({"downloader": downloader_name, "hash": torrent_hash, "message": "下载器不可用"})
            continue
        dl_type = str(getattr(service, "type", "") or "").lower()
        if dl_type not in {"qbittorrent", "transmission"}:
            failed.append({"downloader": downloader_name, "hash": torrent_hash, "message": "下载器类型不支持"})
            continue

        torrents, error = _read_download_torrents(service.instance, ids=[torrent_hash])
        torrent = next((
            value for value in torrents
            if str(get_hash(value, dl_type) or "").casefold() == torrent_hash.casefold()
        ), None)
        if error or torrent is None:
            failed.append({"downloader": downloader_name, "hash": torrent_hash, "message": error or "任务不存在"})
            continue

        try:
            expected = _expected_completion_tags(
                plugin,
                service.name or downloader_name,
                torrent,
                dl_type,
                source_service=source_service,
                site_cache=site_cache,
                transfer_cache=transfer_cache,
                iyuu_cache=iyuu_cache,
            )
        except Exception as err:
            failed.append({"downloader": downloader_name, "hash": torrent_hash, "message": f"核验标签来源失败: {err}"})
            continue

        current_tags = _label_list(get_label(torrent, dl_type))
        current_set = set(current_tags)
        missing = set()
        rejected = []
        for kind, tags in by_kind.items():
            for tag in tags:
                if tag not in expected[kind]:
                    rejected.append(tag)
                elif tag not in current_set:
                    missing.add(tag)
        if rejected:
            skipped.append({
                "downloader": downloader_name,
                "hash": torrent_hash,
                "tags": sorted(rejected),
                "message": "来源记录或 tracker 与扫描时不同，已跳过",
            })
        if not missing:
            if not rejected:
                skipped.append({"downloader": downloader_name, "hash": torrent_hash, "message": "标签已存在"})
            continue

        labels_to_write = _label_list([*current_tags, *sorted(missing)])
        try:
            if dl_type == "qbittorrent":
                result = service.instance.set_torrents_tag(ids=torrent_hash, tags=sorted(missing))
            else:
                result = _write_transmission_labels(service.instance, torrent_hash, labels_to_write)
            if result is False:
                failed.append({"downloader": downloader_name, "hash": torrent_hash, "tags": sorted(missing), "message": "下载器拒绝写入标签"})
                continue
            updated, read_error = _read_download_torrents(service.instance, ids=[torrent_hash])
            latest = next((
                value for value in updated
                if str(get_hash(value, dl_type) or "").casefold() == torrent_hash.casefold()
            ), None)
            observed_tags = set(_label_list(get_label(latest, dl_type))) if latest else set()
            if read_error or latest is None or not missing.issubset(observed_tags):
                failed.append({"downloader": downloader_name, "hash": torrent_hash, "tags": sorted(missing), "message": "写入后回读未确认全部标签"})
                continue
            added.append({
                "downloader": downloader_name,
                "hash": torrent_hash,
                "name": _torrent_name(torrent, torrent_hash),
                "tags": sorted(missing),
            })
        except Exception as err:
            failed.append({"downloader": downloader_name, "hash": torrent_hash, "tags": sorted(missing), "message": str(err)})

    added_count = sum(len(item.get("tags") or []) for item in added)
    code = 0 if not failed else (2 if added else 1)
    return {
        "code": code,
        "msg": f"补全完成：新增 {added_count} 条标签关联，失败 {len(failed)} 个任务",
        "added": added,
        "skipped": skipped,
        "failed": failed,
    }


@observed("tag")
def tag_torrent(plugin, dl, dl_type: str, torrent_hash: str, torrent_tags: list, trackers: list):
    """给种子打站点标签，并返回是否完成或已满足幂等条件。"""
    try:
        site_tag = _site_tag_for_trackers(plugin, trackers, {})
        if not site_tag:
            logger.info(f"转移后标签：无法识别站点 hash={torrent_hash}")
            return False

        existing_tags = _label_list(torrent_tags)
        if site_tag in existing_tags:
            logger.info(f"转移后标签：标签已存在 hash={torrent_hash}")
            return True

        # 设置标签
        if dl_type == "qbittorrent":
            success = dl.set_torrents_tag(ids=torrent_hash, tags=[site_tag])
        elif dl_type == "transmission":
            current_torrents, read_error = _read_download_torrents(dl, ids=[torrent_hash])
            if read_error:
                return False
            current = next((
                torrent for torrent in current_torrents
                if get_hash(torrent, dl_type).lower() == str(torrent_hash).lower()
            ), None)
            if current is None:
                return False
            current_tags = _label_list(get_label(current, dl_type))
            merged_tags = _label_list([*current_tags, site_tag])
            success = dl.set_torrent_tag(ids=torrent_hash, tags=merged_tags)
            if success is not False:
                torrents, error = _read_download_torrents(dl, ids=[torrent_hash])
                if error:
                    success = False
                else:
                    current = next((
                        torrent for torrent in torrents
                        if get_hash(torrent, dl_type).lower() == str(torrent_hash).lower()
                    ), None)
                    observed_tags = set(get_label(current, dl_type)) if current else set()
                    success = set(merged_tags).issubset(observed_tags)
        else:
            logger.warning(f"转移后标签失败: 不支持下载器类型={dl_type}")
            return False
        # 旧宿主的 qB 接口成功时返回 None，仅明确 False 表示写入失败。
        if success is False:
            logger.warning(f"转移后标签失败: hash={torrent_hash} tag={site_tag}")
            return False
        logger.info(f"转移后标签成功: hash={torrent_hash} tag={site_tag}")
        return True
    except Exception as e:
        logger.error(f"转移后标签失败 hash={torrent_hash}: {e}")
        return False


__all__ = (
    "cleanup_temporary_tags_for_event",
    "create_temporary_tag",
    "execute_tag_cleanup",
    "execute_tag_completion",
    "find_site_by_domain",
    "forget_temporary_tag",
    "release_temporary_tag",
    "scan_and_clean_tags",
    "scan_tag_completion",
    "tag_torrent",
)
