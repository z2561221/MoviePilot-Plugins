"""转移做种模块"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from bencode import bdecode, bencode

from app.core.config import settings
from app.core.event import eventmanager, Event
from app.helper.downloader import DownloaderHelper
from app.log import logger
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.schemas import NotificationType, ServiceInfo
from app.schemas.types import EventType
from app.utils.string import StringUtils

from ..utils.name_cleaner import is_dirty_renamed_torrent_name


def validate_config(plugin) -> bool:
    """校验转移配置"""
    if plugin._fromtorrentpath and not Path(plugin._fromtorrentpath).exists():
        logger.error(f"源下载器种子文件保存路径不存在：{plugin._fromtorrentpath}")
        plugin.systemmessage.put(f"源下载器种子文件保存路径不存在：{plugin._fromtorrentpath}", title="自动转移做种")
        return False
    if plugin._fromdownloader == plugin._todownloader:
        logger.error(f"源下载器和目的下载器不能相同")
        plugin.systemmessage.put(f"源下载器和目的下载器不能相同", title="自动转移做种")
        return False
    return True


def download_torrent(plugin, service: ServiceInfo, content: bytes,
                     save_path: str, torrent) -> Optional[str]:
    """添加下载任务到目标下载器"""
    if not service or not service.instance:
        return None
    downloader = service.instance
    from_service = plugin.service_info(plugin._fromdownloader)
    downloader_helper = DownloaderHelper()
    if downloader_helper.is_downloader("qbittorrent", service=service):
        tag = StringUtils.generate_random_str(10)
        if plugin._remainoldtag:
            torrent_labels = plugin.get_label(torrent, from_service.type)
            new_tag = list(set(torrent_labels + plugin._torrent_tags + [tag]))
        else:
            new_tag = plugin._torrent_tags + [tag]
        if plugin._remainoldcat:
            torrent_category = plugin.get_category(torrent, from_service.type)
        else:
            torrent_category = None
        state = downloader.add_torrent(content=content,
                                       download_dir=save_path,
                                       is_paused=True,
                                       tag=new_tag,
                                       category=torrent_category,
                                       is_skip_checking=plugin._seed_skipverify)
        if not state:
            return None
        else:
            torrent_hash = downloader.get_torrent_id_by_tag(tags=tag)
            if not torrent_hash:
                logger.error(f"{downloader} 下载任务添加成功，但获取任务信息失败！")
                return None
        return torrent_hash
    elif downloader_helper.is_downloader("transmission", service=service):
        if plugin._remainoldtag:
            torrent_labels = plugin.get_label(torrent, from_service.type)
            new_tag = list(set(torrent_labels + plugin._torrent_tags))
        else:
            new_tag = plugin._torrent_tags
        torrent = downloader.add_torrent(content=content,
                                         download_dir=save_path,
                                         is_paused=True,
                                         labels=new_tag)
        if not torrent:
            return None
        else:
            return torrent.hashString

    logger.error(f"不支持的下载器类型")
    return None


def post_transfer_process(plugin, to_service: ServiceInfo, torrent_hash: str):
    """种子转移到目标下载器后，立即执行重命名 + 打站点标签"""
    if not torrent_hash or not to_service or not to_service.instance:
        return

    dl = to_service.instance
    dl_type = to_service.type

    try:
        if dl_type == "qbittorrent":
            torrents, _ = dl.get_torrents(ids=[torrent_hash])
            if not torrents:
                logger.warning(f"转移后处理：无法获取种子信息 hash={torrent_hash}")
                return
            torrent = torrents[0]
            torrent_name = torrent.get("name", "")
            torrent_tags = [str(t).strip() for t in torrent.get("tags", "").split(",") if t.strip()] if torrent.get("tags") else []
            trackers = [t.get("url") for t in (torrent.trackers or []) if t.get("tier", -1) >= 0 and t.get("url")]
            save_path = torrent.get("save_path", "")
        else:
            torrents, _ = dl.get_torrents(ids=[torrent_hash])
            if not torrents:
                return
            torrent = torrents[0]
            torrent_name = torrent.name
            torrent_tags = torrent.labels or []
            trackers = [t.announce for t in (torrent.trackers or []) if t.tier >= 0 and t.announce]
            save_path = torrent.download_dir
    except Exception as e:
        logger.error(f"转移后处理：获取种子信息失败 hash={torrent_hash}: {e}")
        return

    if not torrent_name:
        return

    if plugin._rename_enabled:
        plugin._rename_torrent(dl, dl_type, torrent_hash, torrent_name, save_path)

    if plugin._tag_enabled:
        plugin._tag_torrent(dl, dl_type, torrent_hash, torrent_tags, trackers)


def transfer(plugin, trigger_source: str = "手动/定时"):
    """开始转移做种"""
    logger.info(f"开始转移做种任务，触发来源：{trigger_source} ...")

    if not validate_config(plugin):
        return

    from_service = plugin.service_info(plugin._fromdownloader)
    from_downloader: Optional[Union[Qbittorrent, Transmission]] = from_service.instance if from_service else None
    to_service = plugin.service_info(plugin._todownloader)
    to_downloader: Optional[Union[Qbittorrent, Transmission]] = to_service.instance if to_service else None

    if not from_downloader or not to_downloader:
        return

    torrents = from_downloader.get_completed_torrents()
    if torrents:
        logger.info(f"下载器 {from_service.name} 已做种的种子数：{len(torrents)}")
    else:
        logger.info(f"下载器 {from_service.name} 没有已做种的种子")
        return

    trans_torrents = []
    for torrent in torrents:
        if plugin._event.is_set():
            logger.info(f"转移服务停止")
            return

        hash_str = plugin.get_hash(torrent, from_service.type)
        save_path = plugin.get_save_path(torrent, from_service.type)

        if plugin._nopaths and save_path:
            nopath_skip = False
            for nopath in plugin._nopaths.split('\n'):
                if os.path.normpath(save_path).startswith(os.path.normpath(nopath)):
                    logger.info(f"种子 {hash_str} 保存路径 {save_path} 不需要转移，跳过 ...")
                    nopath_skip = True
                    break
            if nopath_skip:
                continue

        torrent_labels = plugin.get_label(torrent, from_service.type)
        torrent_category = plugin.get_category(torrent, from_service.type)
        is_torrent_labels_empty = torrent_labels == [''] or torrent_labels == [] or torrent_labels is None
        if is_torrent_labels_empty:
            torrent_labels = []

        if plugin._includecategory:
            if torrent_category not in plugin._includecategory.split(','):
                logger.info(f"种子 {hash_str} 不含有转移分类 {plugin._includecategory}，跳过 ...")
                continue
        if is_torrent_labels_empty:
            if not plugin._transferemptylabel:
                continue
        else:
            if plugin._nolabels:
                is_skip = False
                for label in plugin._nolabels.split(','):
                    if label in torrent_labels:
                        logger.info(f"种子 {hash_str} 含有不转移标签 {label}，跳过 ...")
                        is_skip = True
                        break
                if is_skip:
                    continue
            if plugin._includelabels:
                is_skip = False
                for label in plugin._includelabels.split(','):
                    if label not in torrent_labels:
                        logger.info(f"种子 {hash_str} 不含有转移标签 {label}，跳过 ...")
                        is_skip = True
                        break
                if is_skip:
                    continue

        trans_torrents.append({
            "hash": hash_str,
            "save_path": save_path,
            "torrent": torrent
        })

    if trans_torrents:
        logger.info(f"需要转移的种子数：{len(trans_torrents)}")
        total = len(trans_torrents)
        success = 0
        fail = 0
        skip = 0
        del_dup = 0

        downloader_helper = DownloaderHelper()
        for torrent_item in trans_torrents:
            torrent_file = Path(plugin._fromtorrentpath) / f"{torrent_item.get('hash')}.torrent"
            if not torrent_file.exists():
                logger.error(f"种子文件不存在：{torrent_file}")
                fail += 1
                continue

            torrent_info, _ = to_downloader.get_torrents(ids=[torrent_item.get('hash')])
            if torrent_info:
                if plugin._deleteduplicate:
                    logger.info(f"删除重复的源下载器任务（不含文件）：{torrent_item.get('hash')} ...")
                    from_downloader.delete_torrents(delete_file=False, ids=[torrent_item.get('hash')])
                    del_dup += 1
                else:
                    logger.info(f"{torrent_item.get('hash')} 已在目的下载器中，跳过 ...")
                    skip += 1
                continue

            download_dir = plugin.convert_save_path(torrent_item.get('save_path'),
                                                    plugin._frompath,
                                                    plugin._topath)
            if not download_dir:
                logger.error(f"转换保存路径失败：{torrent_item.get('save_path')}")
                fail += 1
                continue

            if downloader_helper.is_downloader("qbittorrent", service=from_service):
                content = torrent_file.read_bytes()
                if not content:
                    logger.warning(f"读取种子文件失败：{torrent_file}")
                    fail += 1
                    continue
                try:
                    torrent_main = bdecode(content)
                    main_announce = torrent_main.get('announce')
                except Exception as err:
                    logger.warning(f"解析种子文件 {torrent_file} 失败：{str(err)}")
                    fail += 1
                    continue

                if not main_announce:
                    logger.info(f"{torrent_item.get('hash')} 未发现tracker信息，尝试补充tracker信息...")
                    fastresume_file = Path(plugin._fromtorrentpath) / f"{torrent_item.get('hash')}.fastresume"
                    if not fastresume_file.exists():
                        logger.warning(f"fastresume文件不存在：{fastresume_file}")
                        fail += 1
                        continue
                    try:
                        fastresume = fastresume_file.read_bytes()
                        torrent_fastresume = bdecode(fastresume)
                        fastresume_trackers = torrent_fastresume.get('trackers')
                        if isinstance(fastresume_trackers, list) \
                                and len(fastresume_trackers) > 0 \
                                and fastresume_trackers[0]:
                            torrent_main['announce'] = fastresume_trackers[0][0]
                            if len(fastresume_trackers) > 1 or len(fastresume_trackers[0]) > 1:
                                torrent_main['announce-list'] = fastresume_trackers
                            torrent_file = settings.TEMP_PATH / f"{torrent_item.get('hash')}.torrent"
                            torrent_file.write_bytes(bencode(torrent_main))
                    except Exception as err:
                        logger.error(f"解析fastresume文件 {fastresume_file} 出错：{str(err)}")
                        fail += 1
                        continue

            logger.info(f"添加转移做种任务到下载器 {to_service.name}：{torrent_file}")
            download_id = download_torrent(plugin, service=to_service,
                                           content=torrent_file.read_bytes(),
                                           save_path=download_dir,
                                           torrent=torrent_item.get('torrent'))
            if not download_id:
                fail += 1
                logger.error(f"添加下载任务失败：{torrent_file}")
                continue
            else:
                logger.info(f"成功添加转移做种任务，种子文件：{torrent_file}")

                post_transfer_process(plugin, to_service, download_id)

                if downloader_helper.is_downloader("qbittorrent", service=to_service):
                    if plugin._seed_skipverify:
                        if plugin._seed_autostart:
                            logger.info(f"{download_id} 跳过校验，开启自动开始，注意观察种子的完整性")
                            plugin._register_seed_recheck(to_service.name, [download_id], "transfer")
                        else:
                            logger.info(f"{download_id} 跳过校验，请自行检查手动开始任务...")
                    else:
                        logger.info(f"qbittorrent 开始校验 {download_id} ...")
                        to_downloader.recheck_torrents(ids=[download_id])
                        plugin._register_seed_recheck(to_service.name, [download_id], "transfer")
                else:
                    plugin._register_seed_recheck(to_service.name, [download_id], "transfer")

                if plugin._deletesource:
                    logger.info(f"删除源下载器任务（不含文件）：{torrent_item.get('hash')} ...")
                    from_downloader.delete_torrents(delete_file=False, ids=[torrent_item.get('hash')])

                success += 1
                history_key = f"{from_service.name}-{torrent_item.get('hash')}"
                plugin.save_data(key=history_key,
                                 value={
                                     "to_download": to_service.name,
                                     "to_download_id": download_id,
                                     "delete_source": plugin._deletesource,
                                     "delete_duplicate": plugin._deleteduplicate,
                                 })

        if plugin._notify:
            plugin.post_message(
                mtype=NotificationType.SiteMessage,
                title="【转移做种任务执行完成】",
                text=f"总数：{total}，成功：{success}，失败：{fail}，跳过：{skip}，删除重复：{del_dup}"
            )
    else:
        logger.info(f"没有需要转移的种子")

    plugin._retry_failed_renames(to_service)

    logger.info("转移做种任务执行完成")


def retry_pending_renames(plugin):
    """独立补刀重命名，避免转移扫描提前返回时跳过旧污染记录修复。"""
    if not plugin._todownloader:
        return {"code": 1, "msg": "未配置目标下载器", "history": 0, "dirty": 0, "total": 0}
    try:
        to_service = plugin.service_info(plugin._todownloader)
        if not to_service or not to_service.instance:
            logger.warning("转移做种兜底服务：目标下载器不可用，跳过重命名补刀")
            return {"code": 1, "msg": "目标下载器不可用，已跳过补刀", "history": 0, "dirty": 0, "total": 0}
        history_count = int(plugin._retry_failed_renames(to_service) or 0)
        dirty_count = int(retry_dirty_torrent_names(plugin, to_service) or 0)
        total = history_count + dirty_count
        return {
            "code": 0,
            "msg": f"补刀完成：历史记录 {history_count} 个，当前脏名字 {dirty_count} 个",
            "history": history_count,
            "dirty": dirty_count,
            "total": total,
        }
    except Exception as e:
        logger.error(f"转移做种兜底服务：重命名补刀失败: {e}")
        return {"code": 1, "msg": f"补刀失败: {e}", "history": 0, "dirty": 0, "total": 0}


def retry_dirty_torrent_names(plugin, to_service: ServiceInfo):
    """扫描目标下载器当前任务名，补刀不在历史记录里的副标题污染任务。"""
    if not plugin._rename_enabled or not to_service or not to_service.instance:
        return 0
    dl = to_service.instance
    dl_type = to_service.type
    try:
        torrents, _ = dl.get_torrents()
    except Exception as e:
        logger.error(f"转移做种兜底服务：获取目标下载器任务失败: {e}")
        return 0
    if not torrents:
        return 0

    retry_count = 0
    for torrent in torrents:
        torrent_name = torrent.get("name", "") if dl_type == "qbittorrent" else torrent.name
        if not is_dirty_renamed_torrent_name(torrent_name):
            continue
        torrent_hash = plugin.get_hash(torrent, dl_type)
        if not torrent_hash:
            logger.warning(f"转移做种兜底服务：发现副标题污染任务但无 hash，跳过重命名 name={torrent_name}")
            continue
        save_path = plugin.get_save_path(torrent, dl_type)
        logger.info(f"转移做种兜底服务：发现副标题污染重命名，补刀处理 hash={torrent_hash} name={torrent_name}")
        try:
            plugin._rename_torrent(dl, dl_type, torrent_hash, torrent_name, save_path)
            retry_count += 1
        except Exception as e:
            logger.error(f"转移做种兜底服务：副标题污染重命名补刀失败 hash={torrent_hash} name={torrent_name}: {e}")
    if retry_count:
        logger.info(f"转移做种兜底服务：副标题污染重命名补刀完成，处理 {retry_count} 个种子")
    return retry_count


def fallback_transfer(plugin):
    """转移做种兜底扫描包装函数"""
    retry_pending_renames(plugin)
    transfer(plugin, trigger_source="兜底扫描")


def delayed_transfer(plugin):
    """事件延迟转移执行入口"""
    transfer(plugin, trigger_source="事件驱动")
