"""种子重命名模块"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from bencode import bdecode

from app.core.meta.metabase import MetaBase
from app.core.metainfo import MetaInfo
from app.log import logger
from app.modules.filemanager.transhandler import TransHandler
from app.schemas.types import MediaType

from ..adapter.moviepilot import get_download_history_by_hash
from ..model.state import IYUU_SOURCE_KEY_PREFIX, RENAME_RECORDS_KEY, iyuu_source_key
from ..utils.name_cleaner import (
    clean_torrent_original_name,
    collect_retry_rename_hashes,
    is_polluted_original_name,
)
from ..utils.torrent_adapter import get_hash, get_label, get_save_path


def _set_meta_attr(meta: MetaBase, attr: str, value: str) -> None:
    try:
        if hasattr(meta, attr):
            setattr(meta, attr, value)
    except Exception:
        pass


def _clean_meta_for_rename(meta: MetaBase) -> None:
    if not meta:
        return
    for attr in ("title", "org_string", "original_name"):
        value = getattr(meta, attr, None)
        if value:
            _set_meta_attr(meta, attr, clean_torrent_original_name(str(value)))
    for attr in ("subtitle", "description"):
        _set_meta_attr(meta, attr, "")


def format_torrent_name(template_string: str, meta: MetaBase, mediainfo) -> Optional[str]:
    """根据 Jinja2 模板格式化种子名称"""
    _clean_meta_for_rename(meta)
    handler = TransHandler()
    rename_dict = handler.get_naming_dict(meta=meta, mediainfo=mediainfo)
    path = handler.get_rename_path(template_string, rename_dict)
    return path.as_posix() if path else None


def save_rename_record(plugin, torrent_hash: str, original_name: str, after_name: str,
                       success: bool, reason: str = ""):
    """保存重命名记录"""
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    records[torrent_hash] = {
        "hash": torrent_hash,
        "original_name": original_name,
        "after_name": after_name,
        "success": success,
        "reason": reason,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    plugin.save_data(RENAME_RECORDS_KEY, records)
    if success:
        clear_state = getattr(plugin, "clear_rename_retry_state", None)
        if callable(clear_state):
            clear_state(torrent_hash)
    elif reason:
        record_failure = getattr(plugin, "record_rename_failure", None)
        if callable(record_failure):
            record_failure(torrent_hash, after_name or original_name, reason=reason)


def get_failed_rename_hashes(plugin) -> set:
    """获取所有需补刀的种子 hash：失败记录 + 已成功但 original_name 被副标题污染的记录"""
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    retry_hashes = collect_retry_rename_hashes(records)
    is_archived = getattr(plugin, "is_rename_archived", None)
    if not callable(is_archived):
        return retry_hashes
    return {torrent_hash for torrent_hash in retry_hashes if not is_archived(torrent_hash)}


def _get_bencoded_value(mapping, key: str):
    """从 bencode 字典中兼容读取 str/bytes 两种键。"""
    if not isinstance(mapping, dict):
        return None
    if key in mapping:
        return mapping.get(key)
    return mapping.get(key.encode("utf-8"))


def _to_text(value) -> str:
    """将 bencode 字段值转换为可用于识别的文本。"""
    if value is None:
        return ""
    if isinstance(value, bytes):
        for encoding in ("utf-8", "gb18030"):
            try:
                return value.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
        return value.decode("utf-8", errors="ignore").strip()
    return str(value).strip()


def _add_original_name_candidate(
    candidates: list,
    seen: set,
    value,
    source: str = "",
    base_score: int = 0,
) -> None:
    """添加去重后的原始名称候选，并保留污染与来源信息。"""
    raw = _to_text(value)
    candidate = clean_torrent_original_name(raw).strip()
    if candidate and candidate not in seen:
        candidates.append({
            "name": candidate,
            "raw": raw,
            "source": source,
            "base_score": base_score,
            "polluted": is_polluted_original_name(raw),
        })
        seen.add(candidate)


def _add_torrent_file_candidates(candidates: list, seen: set, plugin, torrent_hash: str) -> None:
    """从源 .torrent 文件中添加原始发布名候选。"""
    source_dir = str(getattr(plugin, "_fromtorrentpath", "") or "").strip()
    hash_text = str(torrent_hash or "").strip()
    if not source_dir or not hash_text:
        return
    torrent_file = Path(source_dir) / f"{hash_text}.torrent"
    if not torrent_file.exists():
        return
    try:
        torrent_data = bdecode(torrent_file.read_bytes())
        info = _get_bencoded_value(torrent_data, "info")
        _add_original_name_candidate(
            candidates, seen, _get_bencoded_value(info, "name"), "torrent_info", 12
        )

        files = _get_bencoded_value(info, "files") or []
        if isinstance(files, list):
            for file_info in files:
                path_parts = (
                    _get_bencoded_value(file_info, "path.utf-8")
                    or _get_bencoded_value(file_info, "path")
                )
                if isinstance(path_parts, list) and path_parts:
                    if len(path_parts) > 1:
                        _add_original_name_candidate(candidates, seen, path_parts[0], "torrent_folder", 18)
                    _add_original_name_candidate(
                        candidates, seen, Path(_to_text(path_parts[-1])).stem, "torrent_file", 8
                    )
                elif path_parts:
                    _add_original_name_candidate(
                        candidates, seen, Path(_to_text(path_parts)).stem, "torrent_file", 8
                    )
    except Exception as e:
        logger.warning(f"转移后重命名：读取原始种子名失败 hash={hash_text} file={torrent_file}: {e}")


def _add_rename_record_candidates(candidates: list, seen: set, plugin, torrent_hash: str) -> None:
    """从重命名历史中添加原始名候选。"""
    try:
        records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    except Exception:
        return
    record = records.get(str(torrent_hash or ""))
    if not isinstance(record, dict):
        return
    _add_original_name_candidate(candidates, seen, record.get("original_name"), "rename_record_original", 4)
    _add_original_name_candidate(candidates, seen, record.get("after_name"), "rename_record_after", 2)


def _add_download_history_candidates(candidates: list, seen: set, torrent_hash: str) -> None:
    """从下载历史中添加原始种子名候选。"""
    try:
        downloadhis = get_download_history_by_hash(torrent_hash)
    except Exception:
        return
    if not downloadhis:
        return
    _add_original_name_candidate(candidates, seen, downloadhis.torrent_name, "download_history", 6)


def _path_name_candidate(value) -> str:
    """从下载器内容路径中提取适合识别的文件夹名或文件名。"""
    text = _to_text(value).replace("\\", "/").strip().rstrip("/")
    if not text:
        return ""
    name = Path(text).name
    if Path(name).suffix.lower() in {".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".torrent"}:
        return Path(name).stem
    return name


def _get_torrent_content_name(torrent, dl_type: str) -> str:
    """从下载器任务中提取内容根目录名。"""
    if dl_type == "qbittorrent":
        for key in ("content_path", "root_path"):
            candidate = _path_name_candidate(torrent.get(key))
            if candidate:
                return candidate
    candidate = _path_name_candidate(getattr(torrent, "download_dir", ""))
    if candidate and candidate != _to_text(getattr(torrent, "name", "")):
        return candidate
    return ""


def _build_original_name_candidate_items(
    plugin,
    torrent_hash: str,
    current_name: str = "",
    content_name: str = "",
) -> list:
    """收集补刀可用的原始发布名候选。"""
    candidates = []
    seen = set()
    _add_torrent_file_candidates(candidates, seen, plugin, torrent_hash)
    _add_download_history_candidates(candidates, seen, str(torrent_hash or ""))
    _add_rename_record_candidates(candidates, seen, plugin, torrent_hash)
    _add_original_name_candidate(candidates, seen, content_name, "content_path", 20)
    _add_original_name_candidate(candidates, seen, current_name, "current_torrent", 0)
    return candidates


def _get_original_torrent_name_candidates(plugin, torrent_hash: str) -> list:
    """读取源 .torrent 中可用于识别的原始名称候选。"""
    return [item["name"] for item in _build_original_name_candidate_items(plugin, torrent_hash)]


def _score_original_name_candidate(value) -> int:
    """根据发布名特征和污染特征给候选原始名称打分。"""
    if isinstance(value, dict):
        text = str(value.get("name") or "")
        raw = str(value.get("raw") or "")
        score = int(value.get("base_score") or 0)
        polluted = bool(value.get("polluted"))
    else:
        text = str(value or "")
        raw = text
        score = 0
        polluted = is_polluted_original_name(raw)
    upper = text.upper()
    release_tokens = (
        "S0", "S1", "S2", "S3", "2160P", "1080P", "720P", "WEB",
        "BLURAY", "H264", "H265", "HEVC", "AVC", "AAC",
    )
    has_release_marker = any(token in upper for token in release_tokens)
    if has_release_marker:
        score += 10
    candidate_polluted = is_polluted_original_name(text)
    if candidate_polluted:
        score -= 20
    elif polluted and not has_release_marker:
        score -= 12
    elif polluted:
        score -= 2
    score += min(len(text), 120) // 20
    return score


def _get_original_torrent_name(
    plugin,
    torrent_hash: str,
    current_name: str = "",
    content_name: str = "",
) -> str:
    """读取源 .torrent 中最适合用于识别的原始发布名。"""
    candidates = _build_original_name_candidate_items(plugin, torrent_hash, current_name, content_name)
    if not candidates:
        return ""
    best = max(candidates, key=_score_original_name_candidate)
    if _score_original_name_candidate(best) < 8:
        logger.warning(
            f"转移后重命名：原始发布名候选置信度过低，跳过自动补刀 hash={torrent_hash} "
            f"candidate={best.get('name')}"
        )
        return ""
    return str(best.get("name") or "")


def resolve_retry_original_name(
    plugin,
    torrent_hash: str,
    current_name: str,
    content_name: str = "",
) -> str:
    """为补刀解析可信原始发布名，无法确认时返回空字符串。"""
    candidate = _get_original_torrent_name(plugin, torrent_hash, current_name, content_name)
    if candidate:
        return candidate
    if is_polluted_original_name(current_name):
        logger.warning(f"补刀跳过重命名：原始发布名污染且无可信候选 hash={torrent_hash} name={current_name}")
        return ""
    return clean_torrent_original_name(current_name).strip()


def _is_iyuu_seed_tags(plugin, tags: list) -> bool:
    """判断标签是否表示 IYUU 铺种任务。"""
    tag_texts = [str(tag or "").strip() for tag in (tags or []) if str(tag or "").strip()]
    if not tag_texts:
        return False
    configured = [
        tag.strip()
        for tag in str(getattr(plugin, "_iyuu_labelsafterseed", "") or "").split(",")
        if tag.strip()
    ]
    for tag in tag_texts:
        if tag in configured or "铺种" in tag:
            return True
    return False


def _find_iyuu_source_hash_from_files(plugin, torrent_hash: str) -> str:
    """从插件数据文件中反查辅种 hash 对应的母种 hash。"""
    get_data_path = getattr(plugin, "get_data_path", None)
    if not callable(get_data_path):
        return ""
    try:
        data_dir = Path(get_data_path())
    except Exception:
        return ""
    if not data_dir.exists() or not data_dir.is_dir():
        return ""
    for path in data_dir.glob("iyuu_*"):
        if path.name.startswith(IYUU_SOURCE_KEY_PREFIX) or not path.is_file():
            continue
        source_hash = path.stem.replace("iyuu_", "", 1)
        if not source_hash or source_hash == path.stem:
            source_hash = path.name.replace("iyuu_", "", 1)
        if not source_hash:
            continue
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in history or []:
            if isinstance(item, dict) and torrent_hash in (item.get("torrents") or []):
                return source_hash
    return ""


def _find_iyuu_source_hash(plugin, torrent_hash: str) -> str:
    """查找辅种任务对应的母种 hash。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return ""
    try:
        source_hash = plugin.get_data(iyuu_source_key(hash_text))
        if source_hash:
            return str(source_hash)
    except Exception:
        pass
    return _find_iyuu_source_hash_from_files(plugin, hash_text)


def rename_torrent(plugin, dl, dl_type: str, torrent_hash: str, torrent_name: str, save_path: str):
    """重命名单个种子，并记录结果到持久化存储"""
    try:
        # 排除目录检查
        if plugin._rename_exclude_dirs:
            for d in plugin._rename_exclude_dirs.split("\n"):
                if d and d in str(save_path):
                    logger.info(f"转移后重命名：命中排除目录 {d}，跳过 hash={torrent_hash}")
                    save_rename_record(plugin, torrent_hash, torrent_name, torrent_name, False, "命中排除目录")
                    return

        # 优先从下载历史获取识别信息（含完整季集号）
        downloadhis = get_download_history_by_hash(torrent_hash)
        if downloadhis:
            history_name = clean_torrent_original_name(downloadhis.torrent_name).strip()
            logger.info(f"转移后重命名：找到下载历史记录，使用历史名称识别: {history_name or downloadhis.torrent_name}")
            meta = MetaInfo(title=history_name or downloadhis.torrent_name, subtitle="")
            media_info = plugin.chain.recognize_media(
                meta=meta, mtype=MediaType(downloadhis.type), tmdbid=downloadhis.tmdbid
            )
            if media_info:
                template = plugin._rename_movie_format if media_info.type == MediaType.MOVIE else plugin._rename_tv_format
                new_name = format_torrent_name(template, meta, media_info)
                if new_name and str(new_name) != torrent_name:
                    if dl_type == "qbittorrent":
                        dl.qbc.torrents_rename(torrent_hash=torrent_hash, new_torrent_name=str(new_name))
                    else:
                        dl.rename_torrent(torrent_hash, str(new_name))
                    logger.info(f"转移后重命名成功(历史): {torrent_name} → {new_name}")
                    save_rename_record(plugin, torrent_hash, torrent_name, str(new_name), True, "")
                    return
                else:
                    logger.info(f"转移后重命名(历史): 名称未变化或格式化失败，回退到种子名解析")

        # 回退：解析种子名称
        cleaned_torrent_name = clean_torrent_original_name(torrent_name).strip()
        meta = MetaInfo(cleaned_torrent_name or torrent_name)
        if not meta or not meta.title:
            logger.warning(f"转移后重命名：元数据获取失败 hash={torrent_hash} name={torrent_name}")
            save_rename_record(plugin, torrent_hash, torrent_name, torrent_name, False, "元数据获取失败")
            return

        # TMDB 识别
        media_info = plugin.chain.recognize_media(meta=meta)
        if not media_info:
            logger.warning(f"转移后重命名：媒体识别失败 hash={torrent_hash} name={torrent_name}")
            save_rename_record(plugin, torrent_hash, torrent_name, torrent_name, False, "媒体识别失败")
            return

        # 选择模板
        template = plugin._rename_movie_format if media_info.type == MediaType.MOVIE else plugin._rename_tv_format
        new_name = format_torrent_name(template, meta, media_info)
        if not new_name:
            logger.warning(f"转移后重命名：格式化结果为空 hash={torrent_hash}")
            save_rename_record(plugin, torrent_hash, torrent_name, torrent_name, False, "格式化结果为空")
            return
        if str(new_name) == torrent_name:
            logger.info(f"转移后重命名：名称未变化 hash={torrent_hash}")
            save_rename_record(plugin, torrent_hash, torrent_name, str(new_name), True, "名称未变化")
            return

        # 执行重命名
        if dl_type == "qbittorrent":
            dl.qbc.torrents_rename(torrent_hash=torrent_hash, new_torrent_name=str(new_name))
        else:
            dl.rename_torrent(torrent_hash, str(new_name))
        logger.info(f"转移后重命名成功: {torrent_name} → {new_name}")
        save_rename_record(plugin, torrent_hash, torrent_name, str(new_name), True, "")
    except Exception as e:
        logger.error(f"转移后重命名失败 hash={torrent_hash}: {e}")
        save_rename_record(plugin, torrent_hash, torrent_name, torrent_name, False, str(e))


def retry_failed_renames(plugin, to_service):
    """对目标下载器中之前重命名失败的种子进行补刀（重命名+站点标签）"""
    if not plugin._rename_enabled and not plugin._tag_enabled:
        return 0
    failed_hashes = get_failed_rename_hashes(plugin)
    if not failed_hashes:
        return 0

    dl = to_service.instance
    dl_type = to_service.type
    try:
        torrents, _ = dl.get_torrents(ids=list(failed_hashes))
        if not torrents:
            return 0
        retry_count = 0
        for torrent in torrents:
            th = torrent.get("hash") if dl_type == "qbittorrent" else torrent.hashString
            if th not in failed_hashes:
                continue
            is_archived = getattr(plugin, "is_rename_archived", None)
            if callable(is_archived) and is_archived(th):
                logger.info(f"补刀跳过归档记录 hash={th}")
                continue
            tn = torrent.get("name", "") if dl_type == "qbittorrent" else torrent.name
            sp = torrent.get("save_path", "") if dl_type == "qbittorrent" else torrent.download_dir
            tags = [str(t).strip() for t in torrent.get("tags", "").split(",") if t.strip()] if dl_type == "qbittorrent" and torrent.get("tags") else (torrent.labels or [])
            trackers = [t.get("url") for t in (torrent.trackers or []) if t.get("tier", -1) >= 0 and t.get("url")] if dl_type == "qbittorrent" else [t.announce for t in (torrent.trackers or []) if t.tier >= 0 and t.announce]
            logger.info(f"补刀处理: hash={th} name={tn}")
            if plugin._rename_enabled:
                retry_name = resolve_retry_original_name(plugin, th, tn, _get_torrent_content_name(torrent, dl_type))
                source_hash = _find_iyuu_source_hash(plugin, th) if _is_iyuu_seed_tags(plugin, tags) else ""
                if source_hash and rename_iyuu_torrent_by_source_record(plugin, dl, dl_type, th, retry_name or tn, source_hash):
                    pass
                elif retry_name:
                    rename_torrent(plugin, dl, dl_type, th, retry_name, sp)
                else:
                    save_rename_record(plugin, th, tn, tn, False, "原始发布名污染，无法可靠补刀")
            if plugin._tag_enabled:
                from .site_tag import tag_torrent
                tag_torrent(plugin, dl, dl_type, th, tags, trackers)
            retry_count += 1
        if retry_count > 0:
            logger.info(f"补刀完成，处理 {retry_count} 个种子")
        return retry_count
    except Exception as e:
        logger.error(f"补刀失败: {e}")
        return 0


def _get_torrent_name(torrent, dl_type):
    if dl_type == "qbittorrent":
        return torrent.get("name", "")
    return torrent.name


def _get_tracker_urls(torrent, dl_type):
    trackers = getattr(torrent, "trackers", None) or []
    if dl_type == "qbittorrent":
        return [
            tracker.get("url")
            for tracker in trackers
            if tracker.get("tier", -1) >= 0 and tracker.get("url")
        ]
    return [
        tracker.announce
        for tracker in trackers
        if tracker.tier >= 0 and tracker.announce
    ]


def retry_rename_by_hash(plugin, to_service, torrent_hash: str):
    """对目标下载器中的单个种子执行补刀（重命名+站点标签）。"""
    hash_text = str(torrent_hash or "").strip()
    if not hash_text:
        return {"code": 1, "msg": "缺少 hash 参数", "hash": ""}
    if not plugin._rename_enabled and not plugin._tag_enabled:
        return {"code": 1, "msg": "重命名和站点标签均未启用，已跳过补刀", "hash": hash_text}
    if not to_service or not to_service.instance:
        record_failure = getattr(plugin, "record_rename_failure", None)
        if callable(record_failure):
            record_failure(hash_text, "", "DOWNLOADER_UNAVAILABLE", "目标下载器不可用")
        return {"code": 1, "msg": "目标下载器不可用，已跳过补刀", "hash": hash_text}

    dl = to_service.instance
    dl_type = to_service.type
    try:
        torrents, _ = dl.get_torrents(ids=[hash_text])
        if not torrents:
            record_failure = getattr(plugin, "record_rename_failure", None)
            if callable(record_failure):
                record_failure(hash_text, "", "TASK_NOT_FOUND", "未在目标下载器找到该种子")
            return {"code": 1, "msg": "未在目标下载器找到该种子", "hash": hash_text}

        for torrent in torrents:
            current_hash = get_hash(torrent, dl_type)
            if current_hash != hash_text:
                continue

            torrent_name = _get_torrent_name(torrent, dl_type)
            if not torrent_name:
                return {"code": 1, "msg": "种子名称为空，无法补刀", "hash": hash_text}

            save_path = get_save_path(torrent, dl_type)
            torrent_tags = get_label(torrent, dl_type)
            trackers = _get_tracker_urls(torrent, dl_type)
            logger.info(f"单条补刀处理: hash={hash_text} name={torrent_name}")

            if plugin._rename_enabled:
                retry_name = resolve_retry_original_name(
                    plugin,
                    hash_text,
                    torrent_name,
                    _get_torrent_content_name(torrent, dl_type),
                )
                if not retry_name:
                    record_failure = getattr(plugin, "record_rename_failure", None)
                    if callable(record_failure):
                        record_failure(hash_text, torrent_name, "NO_TRUSTED_SOURCE", "原始发布名污染，无法可靠补刀")
                    return {"code": 1, "msg": "原始发布名污染，无法可靠补刀", "hash": hash_text}
                source_hash = _find_iyuu_source_hash(plugin, hash_text) if _is_iyuu_seed_tags(plugin, torrent_tags) else ""
                if source_hash and rename_iyuu_torrent_by_source_record(
                    plugin, dl, dl_type, hash_text, retry_name, source_hash
                ):
                    pass
                else:
                    plugin._rename_torrent(
                        dl, dl_type, hash_text,
                        retry_name,
                        save_path
                    )
            if plugin._tag_enabled:
                plugin._tag_torrent(dl, dl_type, hash_text, torrent_tags, trackers)

            clear_state = getattr(plugin, "clear_rename_retry_state", None)
            if callable(clear_state):
                clear_state(hash_text)
            return {"code": 0, "msg": "补刀完成", "hash": hash_text}

        record_failure = getattr(plugin, "record_rename_failure", None)
        if callable(record_failure):
            record_failure(hash_text, "", "TASK_NOT_FOUND", "未在目标下载器找到该种子")
        return {"code": 1, "msg": "未在目标下载器找到该种子", "hash": hash_text}
    except Exception as e:
        logger.error(f"单条补刀失败 hash={hash_text}: {e}")
        record_failure = getattr(plugin, "record_rename_failure", None)
        if callable(record_failure):
            record_failure(hash_text, "", "UNKNOWN_ERROR", str(e))
        return {"code": 1, "msg": f"补刀失败: {e}", "hash": hash_text}


def rename_iyuu_torrent_by_source_record(plugin, dl, dl_type, torrent_hash, torrent_name, source_hash):
    """IYUU 铺种复用母种重命名前缀"""
    records = plugin.get_data(RENAME_RECORDS_KEY) or {}
    source_record = records.get(source_hash)
    if not source_record or not source_record.get("success"):
        return None

    source_after = source_record.get("after_name", "")
    if not source_after:
        return None

    # 从母种重命名结果中提取前缀（标题+年份部分）
    prefix_match = re.match(r'^\[([^\]]+)\]', source_after)
    if not prefix_match:
        return None

    prefix = prefix_match.group(1).strip()
    release_name = clean_torrent_original_name(torrent_name).strip()
    if not release_name:
        release_name = torrent_name
    # 保留新种原始发布名
    new_name = f"[{prefix}] - {release_name}"

    try:
        if dl_type == "qbittorrent":
            dl.qbc.torrents_rename(torrent_hash=torrent_hash, new_torrent_name=new_name)
        else:
            dl.rename_torrent(torrent_hash, new_name)
        logger.info(f"IYUU铺种重命名成功(复用母种): {torrent_name} → {new_name}")
        save_rename_record(plugin, torrent_hash, torrent_name, new_name, True, "")
        return new_name
    except Exception as e:
        logger.error(f"IYUU铺种重命名失败(复用母种) hash={torrent_hash}: {e}")
        return None
