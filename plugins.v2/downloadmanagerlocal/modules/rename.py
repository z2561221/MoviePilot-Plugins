"""种子重命名模块"""

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

from ..utils.name_cleaner import clean_torrent_original_name, collect_retry_rename_hashes
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
    records = plugin.get_data("rename_records") or {}
    records[torrent_hash] = {
        "hash": torrent_hash,
        "original_name": original_name,
        "after_name": after_name,
        "success": success,
        "reason": reason,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    plugin.save_data("rename_records", records)


def get_failed_rename_hashes(plugin) -> set:
    """获取所有需补刀的种子 hash：失败记录 + 已成功但 original_name 被副标题污染的记录"""
    records = plugin.get_data("rename_records") or {}
    return collect_retry_rename_hashes(records)


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


def _get_original_torrent_name(plugin, torrent_hash: str) -> str:
    """读取源 .torrent 元信息中的原始发布名。"""
    source_dir = str(getattr(plugin, "_fromtorrentpath", "") or "").strip()
    hash_text = str(torrent_hash or "").strip()
    if not source_dir or not hash_text:
        return ""
    torrent_file = Path(source_dir) / f"{hash_text}.torrent"
    if not torrent_file.exists():
        return ""
    try:
        torrent_data = bdecode(torrent_file.read_bytes())
        info = _get_bencoded_value(torrent_data, "info")
        original_name = _to_text(_get_bencoded_value(info, "name"))
        return clean_torrent_original_name(original_name)
    except Exception as e:
        logger.warning(f"转移后重命名：读取原始种子名失败 hash={hash_text} file={torrent_file}: {e}")
        return ""


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
        from app.db.downloadhistory_oper import DownloadHistoryOper
        downloadhis = DownloadHistoryOper().get_by_hash(torrent_hash)
        if downloadhis:
            logger.info(f"转移后重命名：找到下载历史记录，使用历史名称识别: {downloadhis.torrent_name}")
            meta = MetaInfo(title=downloadhis.torrent_name, subtitle=downloadhis.torrent_description)
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
        meta = MetaInfo(torrent_name)
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
            tn = torrent.get("name", "") if dl_type == "qbittorrent" else torrent.name
            sp = torrent.get("save_path", "") if dl_type == "qbittorrent" else torrent.download_dir
            tags = [str(t).strip() for t in torrent.get("tags", "").split(",") if t.strip()] if dl_type == "qbittorrent" and torrent.get("tags") else (torrent.labels or [])
            trackers = [t.get("url") for t in (torrent.trackers or []) if t.get("tier", -1) >= 0 and t.get("url")] if dl_type == "qbittorrent" else [t.announce for t in (torrent.trackers or []) if t.tier >= 0 and t.announce]
            logger.info(f"补刀处理: hash={th} name={tn}")
            if plugin._rename_enabled:
                rename_torrent(plugin, dl, dl_type, th, _get_original_torrent_name(plugin, th) or tn, sp)
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
        return {"code": 1, "msg": "目标下载器不可用，已跳过补刀", "hash": hash_text}

    dl = to_service.instance
    dl_type = to_service.type
    try:
        torrents, _ = dl.get_torrents(ids=[hash_text])
        if not torrents:
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
                plugin._rename_torrent(
                    dl, dl_type, hash_text,
                    _get_original_torrent_name(plugin, hash_text) or torrent_name,
                    save_path
                )
            if plugin._tag_enabled:
                plugin._tag_torrent(dl, dl_type, hash_text, torrent_tags, trackers)

            return {"code": 0, "msg": "补刀完成", "hash": hash_text}

        return {"code": 1, "msg": "未在目标下载器找到该种子", "hash": hash_text}
    except Exception as e:
        logger.error(f"单条补刀失败 hash={hash_text}: {e}")
        return {"code": 1, "msg": f"补刀失败: {e}", "hash": hash_text}


def rename_iyuu_torrent_by_source_record(plugin, dl, dl_type, torrent_hash, torrent_name, source_hash):
    """IYUU 铺种复用母种重命名前缀"""
    records = plugin.get_data("rename_records") or {}
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
    # 保留新种原始发布名
    new_name = f"[{prefix}] - {torrent_name}"

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
