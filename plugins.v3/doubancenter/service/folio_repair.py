"""观影档案身份修复：只读预览、原始备份和并发保护。"""

from __future__ import annotations

import copy
import datetime
import json
import os
import time
import uuid
from pathlib import Path

from app.chain.media import MediaChain
from app.sdk.logging import logger

from ..adapter import folio_library, folio_media
from ..model import folio_record
from ..storage import records as storage
from . import folio_watch

PLAN_TTL_SECONDS = 15 * 60


def _plans(plugin) -> dict:
    """返回实例内有效的短期预览，不将预览写入永久配置。"""
    plans = getattr(plugin, "_folio_repair_plans", {})
    now = time.monotonic()
    plans = {key: plan for key, plan in plans.items() if plan["expires_at"] > now}
    plugin._folio_repair_plans = plans
    return plans


def _replacement(record: dict, origin: dict, match: dict) -> dict:
    """替换已核验身份和季海报，保留观看时间及未知扩展字段。"""
    return {
        **record,
        "subject_id": str(match["subject_id"]),
        "subject_name": match["subject_name"],
        "display_title": (folio_record.library_title(match["subject_name"])
                          if match["identity_scope"] == "library_season" else match["subject_name"]),
        "media_source": "douban", "media_id": str(match["subject_id"]),
        "type": "电视剧", "origin": dict(origin),
        "poster_path": match.get("poster_path") or record.get("poster_path") or "",
        "identity_status": "verified", "identity_scope": match["identity_scope"],
        "season_facts": match.get("facts") or {},
        "related_subjects": match.get("related_subjects") or [],
        "season_label": f"第{origin['season']}季",
    }


def _merge_library_aliases(snapshot: dict, record: dict, keys: list[str]) -> tuple[dict, dict]:
    """仅合并明确指定且已核实属于同一库内季的旧键，完整保留原记录。"""
    if not keys:
        return record, {}
    origin = record.get("origin") or {}
    if not folio_record.library_key(origin) or record.get("identity_scope") != "library_season":
        raise ValueError("合并旧记录必须先核验实际媒体库季")
    result = copy.deepcopy(record)
    archived = result.setdefault("merged_aliases", {})
    subjects = {str(record["subject_id"]),
                *(str(item["subject_id"]) for item in record.get("related_subjects") or [])}
    aliases = {}
    for key in keys:
        alias = snapshot.get(key)
        if alias is None and key in archived:
            continue
        if (not isinstance(alias, dict) or alias.get("identity_status") != "verified"
                or not folio_record.same_native_season(origin, alias.get("origin") or {})
                or str(alias.get("subject_id") or "") not in subjects):
            raise ValueError(f"旧记录不属于已核验的同一媒体库季：{key}")
        aliases[key] = copy.deepcopy(alias)
        archived[key] = copy.deepcopy(alias)
        for field in ("last_synced_at", "last_played_at", "last_marked_at"):
            if alias.get(field):
                result[field] = max(result.get(field) or alias[field], alias[field])
        # 旧 Part 的看过状态不能推断整季看完；同一主条目的在看状态可接续。
        if (not result.get("watch_status") and alias.get("watch_status") == "do"
                and str(alias["subject_id"]) == str(record["subject_id"])):
            result["watch_status"] = "do"
    return result, aliases


def _project_replacement(snapshot, projected, item, replacement, merge_keys):
    """将替换及精确合并范围一起纳入预览，应用前逐条检查并发变化。"""
    replacement, aliases = _merge_library_aliases(snapshot, replacement, merge_keys)
    changed = replacement != item["before"] or bool(aliases)
    item.update(status="ready" if changed else "unchanged", changed=changed,
                after=replacement, merge_before=aliases)
    projected[item["key"]] = replacement
    for key in aliases:
        projected.pop(key)


def preview(plugin, targets: list[dict], *, refresh_posters: bool = False) -> dict:
    """只读核验指定记录，返回可审阅的逐条修正对照。"""
    target_keys = {target["key"] for target in targets}
    merge_keys = [key for target in targets for key in target.get("merge_keys", [])]
    if (len(merge_keys) != len(set(merge_keys)) or target_keys.intersection(merge_keys)
            or (refresh_posters and merge_keys)):
        raise ValueError("合并旧记录范围重复或与其他修复动作冲突")
    with plugin._sync_lock:
        snapshot = copy.deepcopy(storage.read_folio_data(plugin))
    chain = MediaChain()
    media_cache = {}
    items = []
    seen_keys, seen_origins = set(), set()
    projected = copy.deepcopy(snapshot)
    for target in targets:
        key = target["key"]
        origin = {name: target[name] for name in ("media_source", "media_id", "season", "episode_group")}
        origin["type"] = "tv"
        library_error = ""
        if target.get("library_season"):
            if target.get("mediaserver"):
                origin["mediaserver"] = target["mediaserver"]
            library = folio_library.load_season(plugin, origin, refresh=True)
            if library:
                origin = folio_library.bind_season(origin, library)
            else:
                library_error = "实际媒体库分季不可核验，保留原档案"
        origin_id = folio_record.origin_key(origin)
        if key in seen_keys or not origin_id or origin_id in seen_origins:
            raise ValueError("修复目标包含重复记录或无效播放身份")
        seen_keys.add(key)
        seen_origins.add(origin_id)
        record = snapshot.get(key)
        item = {"key": key, "status": "unresolved", "changed": False, "reason": "",
                "before": record if isinstance(record, dict) else None, "after": None}
        items.append(item)
        if not isinstance(record, dict):
            item["reason"] = "原始记录不存在"
            continue
        if library_error:
            item["reason"] = library_error
            continue
        verified = (record.get("identity_status") == "verified"
                    and folio_record.origin_key(record.get("origin") or {}) == origin_id
                    and (not target.get("library_season")
                         or (record.get("identity_scope") == "library_season"
                             and record.get("origin", {}).get("library_season") == origin.get("library_season"))))
        if refresh_posters:
            if (not verified or record.get("media_source") != "douban"
                    or not record.get("subject_id")
                    or str(record.get("media_id")) != str(record["subject_id"])):
                item["reason"] = "仅可刷新播放身份和豆瓣条目一致的已核验档案海报"
                continue
            try:
                poster = folio_media.load_subject_poster(chain, record["subject_id"])
            except folio_media.FolioLookupError as err:
                item["reason"] = str(err)
                continue
            replacement = {**record, "poster_path": poster}
            changed = replacement != record
            item.update(status="ready" if changed else "unchanged", changed=changed, after=replacement,
                        evidence={"subject_id": record["subject_id"], "poster_path": poster,
                                  "poster_source": "douban"})
            projected[key] = replacement
            continue
        if verified:
            replacement = folio_watch.restore_first_playback(record, target.get("first_played_at"), target.get("time_evidence", ""))
            _project_replacement(snapshot, projected, item, replacement, target.get("merge_keys", []))
            continue
        if any(other_key != key and other_key not in target.get("merge_keys", []) and isinstance(other, dict)
               and folio_record.origin_key(other.get("origin") or {}) == origin_id
               for other_key, other in snapshot.items()):
            item["reason"] = "相同播放身份已有记录，请先核对原始档案"
            continue
        try:
            cache_key = (origin["media_source"], origin["media_id"], origin["episode_group"])
            if cache_key not in media_cache:
                media_cache[cache_key] = folio_media.load_playback_media(chain, origin, key)
            media = media_cache[cache_key]
            match = folio_media.resolve_tv_subject(chain, media, origin) if media else {
                "resolved": False, "reason": "未取得匹配源身份的媒体详情",
            }
        except (folio_media.FolioLookupError, ValueError, TypeError, AttributeError) as err:
            logger.warning(f"观影档案分季核验失败：{key}", exc_info=True)
            match = {"resolved": False, "reason": f"媒体查询失败（{type(err).__name__}），原记录保持不变"}
        item["evidence"] = {"season": match.get("facts") or {}, "candidates": match.get("checks") or []}
        if not match.get("resolved"):
            item["reason"] = match.get("reason") or "分季身份尚未核实"
            continue
        replacement = _replacement(record, origin, match)
        replacement = folio_watch.restore_first_playback(replacement, target.get("first_played_at"), target.get("time_evidence", ""))
        _project_replacement(snapshot, projected, item, replacement, target.get("merge_keys", []))
    ready = bool(items) and all(item["status"] != "unresolved" for item in items)
    plan_id = uuid.uuid4().hex
    with plugin._sync_lock:
        plans = _plans(plugin)
        # 一次只保留少量可审阅预览；已经生成的文件备份不受影响。
        while len(plans) >= 4:
            plans.pop(next(iter(plans)))
        plans[plan_id] = {
            "expires_at": time.monotonic() + PLAN_TTL_SECONDS,
            "items": copy.deepcopy(items), "ready": ready, "receipt": None,
        }
    return {
        "plan_id": plan_id, "ready": ready, "items": items,
        "changed": sum(item["changed"] for item in items),
        "raw_count": len(snapshot),
        "timeline_before": len(folio_record.timeline_records(snapshot)),
        "timeline_after": len(folio_record.timeline_records(projected)),
        "expires_in": PLAN_TTL_SECONDS,
    }


def _backup(plugin, plan_id: str, data: dict) -> str:
    """先以独占文件保存完整原始档案，备份失败时禁止修改记录。"""
    folder = Path(plugin.get_data_path()) / "folio-repairs"
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now().astimezone()
    path = folder / f"folio-before-{now.strftime('%Y%m%d-%H%M%S')}-{plan_id}.json"
    payload = {
        "plugin_id": plugin.__class__.__name__,
        "plugin_version": getattr(plugin, "plugin_version", ""),
        "created_at": now.isoformat(), "plan_id": plan_id,
        "data_sha256": folio_record.fingerprint(data), "data": data,
    }
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    return str(path)


def apply(plugin, plan_id: str) -> dict:
    """仅应用未变化的预览目标，不覆盖并发播放记录或重写观看时间。"""
    with plugin._sync_lock:
        plan = _plans(plugin).get(plan_id)
        if not plan:
            raise ValueError("修复预览已过期，请重新预览")
        if not plan["ready"]:
            raise ValueError("仍有未核实的分季身份，不能应用修复")
        current = copy.deepcopy(storage.read_folio_data(plugin))
        if plan["receipt"] is not None:
            return {**plan["receipt"], "updated": 0, "merged": 0, "already_applied": True,
                    "raw_count": len(current), "timeline_count": len(folio_record.timeline_records(current))}
        target_keys = {item["key"] for item in plan["items"]}
        target_keys.update(key for item in plan["items"] for key in item.get("merge_before", {}))
        for item in plan["items"]:
            key = item["key"]
            if key not in current or folio_record.fingerprint(current[key]) != folio_record.fingerprint(item["before"]):
                raise ValueError(f"记录已在预览后变化：{key}，请重新预览")
            for alias_key, alias in item.get("merge_before", {}).items():
                if current.get(alias_key) != alias:
                    raise ValueError(f"合并旧记录已在预览后变化：{alias_key}，请重新预览")
            after_origin = item["after"].get("origin") or {}
            origin = folio_record.origin_key(after_origin)
            if any(other_key not in target_keys and isinstance(other, dict)
                   and (folio_record.origin_key(other.get("origin") or {}) == origin
                        or (folio_record.library_key(after_origin)
                            and folio_record.same_native_season(after_origin, other.get("origin") or {})))
                   for other_key, other in current.items()):
                raise ValueError(f"预览后出现相同播放身份的新记录：{key}，请重新预览")
        changed_items = [item for item in plan["items"] if item["changed"]]
        backup_path = _backup(plugin, plan_id, current) if changed_items else ""
        for item in changed_items:
            current[item["key"]] = copy.deepcopy(item["after"])
            for alias_key in item.get("merge_before", {}):
                del current[alias_key]
        if changed_items:
            storage.save_folio_data(plugin, current)
            persisted = storage.read_folio_data(plugin)
            if folio_record.fingerprint(persisted) != folio_record.fingerprint(current):
                raise RuntimeError("修复写入后的档案回读不一致")
        receipt = {
            "updated": len(changed_items), "backup_path": backup_path, "already_applied": False,
            "merged": sum(len(item.get("merge_before", {})) for item in changed_items),
            "raw_count": len(current), "timeline_count": len(folio_record.timeline_records(current)),
        }
        plan["receipt"] = receipt
        return receipt
