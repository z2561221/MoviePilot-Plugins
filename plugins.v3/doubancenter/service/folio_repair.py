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

from ..adapter import folio_media
from ..model import folio_record
from ..storage import records as storage

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
        "display_title": match["subject_name"],
        "media_source": "douban", "media_id": str(match["subject_id"]),
        "type": "电视剧", "origin": dict(origin),
        "poster_path": match.get("poster_path") or record.get("poster_path") or "",
        "identity_status": "verified", "identity_scope": match["identity_scope"],
        "season_facts": match.get("facts") or {},
        "season_label": f"第{origin['season']}季",
    }


def preview(plugin, targets: list[dict]) -> dict:
    """只读核验指定记录，返回可审阅的逐条修正对照。"""
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
        if (record.get("identity_status") == "verified"
                and folio_record.origin_key(record.get("origin") or {}) == origin_id):
            item.update(status="unchanged", after=record)
            continue
        if any(other_key != key and isinstance(other, dict)
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
        changed = replacement != record
        item.update(status="ready" if changed else "unchanged", changed=changed, after=replacement)
        projected[key] = replacement
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
            return {**plan["receipt"], "updated": 0, "already_applied": True,
                    "raw_count": len(current), "timeline_count": len(folio_record.timeline_records(current))}
        target_keys = {item["key"] for item in plan["items"]}
        for item in plan["items"]:
            key = item["key"]
            if key not in current or folio_record.fingerprint(current[key]) != folio_record.fingerprint(item["before"]):
                raise ValueError(f"记录已在预览后变化：{key}，请重新预览")
            origin = folio_record.origin_key(item["after"].get("origin") or {})
            if any(other_key not in target_keys and isinstance(other, dict)
                   and folio_record.origin_key(other.get("origin") or {}) == origin
                   for other_key, other in current.items()):
                raise ValueError(f"预览后出现相同播放身份的新记录：{key}，请重新预览")
        changed_items = [item for item in plan["items"] if item["changed"]]
        backup_path = _backup(plugin, plan_id, current) if changed_items else ""
        for item in changed_items:
            current[item["key"]] = copy.deepcopy(item["after"])
        if changed_items:
            storage.save_folio_data(plugin, current)
            persisted = storage.read_folio_data(plugin)
            if folio_record.fingerprint(persisted) != folio_record.fingerprint(current):
                raise RuntimeError("修复写入后的档案回读不一致")
        receipt = {
            "updated": len(changed_items), "backup_path": backup_path, "already_applied": False,
            "raw_count": len(current), "timeline_count": len(folio_record.timeline_records(current)),
        }
        plan["receipt"] = receipt
        return receipt
