"""IYUU 辅种服务实现。"""

import os
import re
import time
from typing import Optional, Dict
from urllib.parse import urljoin

from bencode import bdecode
from lxml import etree

from app.core.config import settings
from app.log import logger
from app.schemas import NotificationType, ServiceInfo

from ..adapter.moviepilot import (
    check_site,
    download_torrent_content,
    generate_random_tag,
    get_downloader_service,
    get_downloader_services,
    get_plugin_config,
    get_site_indexer,
    get_url_domain,
    is_downloader_type,
    list_custom_site_dicts,
    request_get_res,
    request_post_res,
)
from ..model.state import iyuu_history_key, iyuu_source_key
from ..utils.sensitive import mask_sensitive_url


IYUU_QUERY_CHUNK_SIZE = 100
IYUU_QUERY_BATCH_DELAY_SECONDS = 6
IYUU_SCAN_PROGRESS_INTERVAL = 500
IYUU_TRANSIENT_ERROR_LIMIT = 2
IYUU_TRANSIENT_ERROR_KEYWORDS = (
    "Server internal error",
    "OOM command not allowed",
    "未获取到返回信息",
    "访问频率过快",
    "Too Many Requests",
    "timeout",
    "Timeout",
    "Connection",
    "连接",
)
IYUU_CONFIG_ERROR_KEYWORDS = (
    "未配置 IYUU Token",
    "token未注册",
    "请求缺少token",
    "未绑定推荐站点",
    "缺少sid_list",
    "站点哈希值 require",
    "站点哈希刷新失败",
    "未获取到 IYUU 支持站点列表",
)


def _is_iyuu_transient_error(message: str) -> bool:
    """判断 IYUU 查询失败是否属于临时服务端异常或限流。"""
    return bool(message and any(keyword in message for keyword in IYUU_TRANSIENT_ERROR_KEYWORDS))


def _is_iyuu_config_error(message: str) -> bool:
    """判断 IYUU 查询失败是否属于 Token 或站点绑定配置异常。"""
    return bool(message and any(keyword in message for keyword in IYUU_CONFIG_ERROR_KEYWORDS))


def is_torrent_content(content: bytes) -> bool:
    """确认下载内容是 bencode torrent，而不是登录页/错误页 HTML。"""
    if not content or not isinstance(content, (bytes, bytearray)):
        return False
    head = bytes(content[:4096]).lstrip()
    if not head or head.startswith((b"<", b"{")):
        return False
    try:
        data = bdecode(content)
    except Exception:
        return False
    return isinstance(data, dict) and (b"info" in data or "info" in data)


def iyuu_service_infos(plugin) -> Optional[Dict[str, ServiceInfo]]:
    """IYUU 辅种下载器服务信息"""
    if not plugin._iyuu_downloaders:
        logger.warning("IYUU辅种：尚未配置下载器")
        return None
    services = get_downloader_services(name_filters=plugin._iyuu_downloaders)
    if not services:
        logger.warning("IYUU辅种：获取下载器实例失败")
        return None
    active = {}
    for name, info in services.items():
        if info.instance.is_inactive():
            logger.warning(f"IYUU辅种：下载器 {name} 未连接")
        else:
            active[name] = info
    return active if active else None


def iyuu_auto_service_info(plugin) -> Optional[ServiceInfo]:
    """IYUU 主辅分离下载器"""
    if not plugin._iyuu_auto_downloader:
        return None
    service = get_downloader_service(plugin._iyuu_auto_downloader)
    if not service or service.instance.is_inactive():
        logger.warning(f"IYUU辅种：主辅分离下载器 {plugin._iyuu_auto_downloader} 不可用")
        return None
    return service


def iyuu_auto_seed(plugin):
    """IYUU 自动辅种主逻辑"""
    try:
        return _iyuu_auto_seed(plugin)
    except Exception as e:
        logger.error(f"IYUU辅种任务执行失败: {e}", exc_info=True)
        try:
            update_iyuu_config(plugin)
        except Exception as save_err:
            logger.error(f"IYUU辅种：异常后保存缓存失败: {save_err}", exc_info=True)


def _iyuu_auto_seed(plugin):
    """IYUU 自动辅种主逻辑"""
    services = iyuu_service_infos(plugin)
    if not plugin.iyuu_helper or not services:
        return
    ready, ready_msg = plugin.iyuu_helper.ensure_ready()
    if not ready:
        logger.warning(f"IYUU辅种：预检失败，本轮跳过：{ready_msg}")
        return
    logger.info("开始 IYUU 辅种任务 ...")

    plugin._iyuu_total = 0
    plugin._iyuu_realtotal = 0
    plugin._iyuu_success = 0
    plugin._iyuu_exist = 0
    plugin._iyuu_fail = 0
    plugin._iyuu_cached = 0

    transient_error_count = 0
    stop_reason = ""

    for service in services.values():
        downloader = service.name
        downloader_obj = service.instance
        logger.info(f"IYUU辅种：扫描下载器 {downloader} ...")
        torrents = downloader_obj.get_completed_torrents()
        if not torrents:
            logger.info(f"IYUU辅种：下载器 {downloader} 没有已完成种子")
            continue
        logger.info(f"IYUU辅种：下载器 {downloader} 已完成种子数：{len(torrents)}")

        hash_strs = []
        for index, torrent in enumerate(torrents, 1):
            if plugin._event.is_set():
                logger.info("IYUU辅种服务停止")
                return
            if index % IYUU_SCAN_PROGRESS_INTERVAL == 0:
                logger.info(f"IYUU辅种：下载器 {downloader} 已扫描 {index}/{len(torrents)} 个已完成种子")
            hash_str = plugin.get_hash(torrent, service.type)
            if hash_str in plugin._iyuu_error_caches or hash_str in plugin._iyuu_permanent_error_caches:
                continue
            save_path = plugin.get_save_path(torrent, service.type)
            if plugin._iyuu_nopaths and save_path:
                skip = False
                for nopath in plugin._iyuu_nopaths.split('\n'):
                    if os.path.normpath(save_path).startswith(os.path.normpath(nopath)):
                        skip = True
                        break
                if skip:
                    continue
            torrent_labels = plugin.get_label(torrent, service.type)
            if torrent_labels and plugin._iyuu_nolabels:
                skip = False
                for label in plugin._iyuu_nolabels.split(','):
                    if label in torrent_labels:
                        skip = True
                        break
                if skip:
                    continue
            torrent_size = plugin.get_torrent_size(torrent, service.type) / 1024 / 1024 / 1024
            if plugin._iyuu_size and torrent_size < plugin._iyuu_size:
                continue
            category = plugin.get_category(torrent, service.type) if plugin._iyuu_auto_category else None
            hash_strs.append({
                "hash": hash_str,
                "save_path": save_path,
                "category": category or plugin._iyuu_categoryafterseed
            })

        if hash_strs:
            logger.info(f"IYUU辅种：需要辅种的种子数：{len(hash_strs)}")
            for i in range(0, len(hash_strs), IYUU_QUERY_CHUNK_SIZE):
                if i and IYUU_QUERY_BATCH_DELAY_SECONDS > 0:
                    logger.info(
                        f"IYUU辅种：等待 {IYUU_QUERY_BATCH_DELAY_SECONDS} 秒后继续下一批，避免请求过快"
                    )
                    if plugin._event.wait(IYUU_QUERY_BATCH_DELAY_SECONDS):
                        logger.info("IYUU辅种服务停止")
                        return
                chunk = hash_strs[i:i + IYUU_QUERY_CHUNK_SIZE]
                query_error = iyuu_seed_torrents(plugin, hash_strs=chunk, service=service)
                if not query_error:
                    transient_error_count = 0
                    continue
                if _is_iyuu_config_error(query_error):
                    stop_reason = f"IYUU 配置或站点绑定异常：{query_error}"
                    break
                if _is_iyuu_transient_error(query_error):
                    transient_error_count += 1
                    logger.warning(
                        f"IYUU辅种：检测到临时异常 {transient_error_count}/{IYUU_TRANSIENT_ERROR_LIMIT}：{query_error}"
                    )
                    if transient_error_count >= IYUU_TRANSIENT_ERROR_LIMIT:
                        stop_reason = f"IYUU 临时异常连续达到 {IYUU_TRANSIENT_ERROR_LIMIT} 次，停止本轮辅种"
                        break
                else:
                    transient_error_count = 0
            if stop_reason:
                break
        else:
            logger.info(f"IYUU辅种：下载器 {downloader} 没有需要辅种的种子")
        if stop_reason:
            break

    if stop_reason:
        logger.warning(f"IYUU辅种：{stop_reason}")

    update_iyuu_config(plugin)
    if plugin._notify and (plugin._iyuu_success or plugin._iyuu_fail):
        plugin.post_message(
            mtype=NotificationType.SiteMessage,
            title="【IYUU自动辅种任务完成】",
            text=f"服务器返回可辅种总数：{plugin._iyuu_total}\n"
                 f"实际可辅种数：{plugin._iyuu_realtotal}\n"
                 f"已存在：{plugin._iyuu_exist}\n"
                 f"成功：{plugin._iyuu_success}\n"
                 f"失败：{plugin._iyuu_fail}\n"
                 f"缓存跳过：{plugin._iyuu_cached}"
        )
    logger.info("IYUU 辅种任务执行完成")


def iyuu_seed_torrents(plugin, hash_strs: list, service: ServiceInfo):
    """执行一批种子的 IYUU 辅种"""
    if not hash_strs:
        return None
    logger.info(f"IYUU辅种：下载器 {service.name} 查询辅种，数量：{len(hash_strs)}")
    hashs = [item.get("hash") for item in hash_strs]
    save_paths = {item.get("hash"): item.get("save_path") for item in hash_strs}
    save_category = {item.get("hash"): item.get("category") for item in hash_strs}
    unmanaged_sites = {}
    skipped_sites = {}

    def __count(counter: dict, key: str):
        if not key:
            key = "未知站点"
        counter[key] = counter.get(key, 0) + 1

    def __log_counter(title: str, counter: dict, limit: int = 20):
        if not counter:
            return
        total = sum(counter.values())
        top_items = sorted(counter.items(), key=lambda item: item[1], reverse=True)[:limit]
        detail = ", ".join([f"{name}({count})" for name, count in top_items])
        logger.info(f"IYUU辅种：{title} {len(counter)} 个站点，共 {total} 条：{detail}")

    seed_list, msg = plugin.iyuu_helper.get_seed_info(hashs)
    if not isinstance(seed_list, dict):
        if plugin._iyuu_token and msg == '请求缺少token':
            logger.warning(f'IYUU辅种失败，疑似站点未绑定：{msg}')
        else:
            logger.warning(f"IYUU辅种：当前种子列表没有可辅种的站点：{msg}")
        return msg or "IYUU 查询未返回有效数据"
    logger.info(f"IYUU辅种：返回可辅种数：{len(seed_list)}")

    for current_hash, seed_info in seed_list.items():
        if not seed_info:
            continue
        seed_torrents = seed_info.get("torrent")
        if not isinstance(seed_torrents, list):
            seed_torrents = [seed_torrents]

        success_torrents = []
        for seed in seed_torrents:
            if not seed or not isinstance(seed, dict):
                continue
            if not seed.get("sid") or not seed.get("info_hash"):
                continue
            if seed.get("info_hash") in hashs:
                continue
            if seed.get("info_hash") in plugin._iyuu_success_caches:
                continue
            if seed.get("info_hash") in plugin._iyuu_error_caches or seed.get("info_hash") in plugin._iyuu_permanent_error_caches:
                continue

            site_url, _ = plugin.iyuu_helper.get_torrent_url(seed.get("sid"))
            site_domain = get_url_domain(site_url) if site_url else None
            site_info = get_site_indexer(site_domain) if site_domain else None
            if not site_info or not site_info.get('url'):
                __count(unmanaged_sites, site_url or str(seed.get("sid")))
                continue
            if plugin._iyuu_sites and site_info.get('id') not in plugin._iyuu_sites:
                __count(skipped_sites, site_info.get('name') or site_url or str(seed.get("sid")))
                continue

            target_service = iyuu_auto_service_info(plugin) or service
            success = iyuu_download_torrent(plugin, seed=seed, service=target_service,
                                            save_path=save_paths.get(current_hash),
                                            save_category=save_category.get(current_hash),
                                            source_hash=current_hash,
                                            site_info=site_info)
            if success:
                success_torrents.append(seed.get("info_hash"))

        if success_torrents:
            iyuu_save_history(plugin, current_hash=current_hash, downloader=service.name,
                              success_torrents=success_torrents)

    __log_counter("跳过未维护站点", unmanaged_sites)
    __log_counter("跳过未选择站点", skipped_sites)
    logger.info(f"IYUU辅种：下载器 {service.name} 辅种完成")
    return None


def iyuu_download_torrent(plugin, seed: dict, service: ServiceInfo, save_path: str, save_category: str,
                          source_hash: str = None, site_info: dict = None):
    """从站点下载种子并添加到下载器，辅种后打站点标签"""

    def __is_special_site(url):
        if "hdsky.me" in url:
            return False
        return True

    plugin._iyuu_total += 1
    site_url, download_page = plugin.iyuu_helper.get_torrent_url(seed.get("sid"))
    if not site_url or not download_page:
        append_iyuu_cache(plugin._iyuu_error_caches, seed.get("info_hash"))
        plugin._iyuu_fail += 1
        plugin._iyuu_cached += 1
        return False

    site_domain = get_url_domain(site_url)
    if not site_info:
        site_info = get_site_indexer(site_domain)
    if not site_info or not site_info.get('url'):
        return False
    if plugin._iyuu_sites and site_info.get('id') not in plugin._iyuu_sites:
        return False

    plugin._iyuu_realtotal += 1
    downloader_obj = service.instance
    torrent_info, _ = downloader_obj.get_torrents(ids=[seed.get("info_hash")])
    if torrent_info:
        plugin._iyuu_exist += 1
        return False

    check, checkmsg = check_site(site_domain)
    if check:
        logger.warning(checkmsg)
        plugin._iyuu_fail += 1
        return False

    torrent_url = iyuu_get_download_url(plugin, seed=seed, site=site_info, base_url=download_page)
    if not torrent_url:
        append_iyuu_cache(plugin._iyuu_error_caches, seed.get("info_hash"))
        plugin._iyuu_fail += 1
        plugin._iyuu_cached += 1
        return False

    def __with_https_param(url: str) -> str:
        if not url or not __is_special_site(url) or "https=1" in url:
            return url
        return url + ("&https=1" if "?" in url else "?https=1")

    torrent_url = __with_https_param(torrent_url)
    safe_torrent_url = mask_sensitive_url(torrent_url)

    _, content, _, _, error_msg = download_torrent_content(
        url=torrent_url,
        cookie=site_info.get("cookie"),
        ua=site_info.get("ua") or settings.USER_AGENT,
        proxy=site_info.get("proxy"),
    )

    if content and not is_torrent_content(content):
        error_msg = "下载到的内容不是有效 torrent 文件，疑似登录页或错误页"
        content = None

    if not content:
        logger.warning(
            f"IYUU辅种：下载种子文件失败，准备回退详情页获取：站点={site_info.get('name')}，"
            f"info_hash={seed.get('info_hash')}，url={safe_torrent_url}，原因={error_msg or '未知'}"
        )
        fallback_url = iyuu_get_download_url(plugin, seed=seed, site=site_info, base_url=download_page,
                                             force_page=True)
        fallback_url = __with_https_param(fallback_url)
        if fallback_url and fallback_url != torrent_url:
            safe_fallback_url = mask_sensitive_url(fallback_url)
            logger.info(f"IYUU辅种：使用详情页下载链接重试：{safe_fallback_url}")
            _, content, _, _, fallback_error = download_torrent_content(
                url=fallback_url,
                cookie=site_info.get("cookie"),
                ua=site_info.get("ua") or settings.USER_AGENT,
                proxy=site_info.get("proxy"),
            )
            if content and not is_torrent_content(content):
                fallback_error = "下载到的内容不是有效 torrent 文件，疑似登录页或错误页"
                content = None
            if content:
                torrent_url = fallback_url
                safe_torrent_url = safe_fallback_url
                error_msg = ""
            else:
                error_msg = fallback_error or error_msg

    if not content:
        plugin._iyuu_fail += 1
        transient_keywords = ('无法打开链接', '触发站点流控', '403', '401', '429', 'Cloudflare',
                              'cloudflare', 'timeout', 'Timeout', 'Connection', '连接', '登录', 'Cookie')
        if error_msg and any(keyword in error_msg for keyword in transient_keywords):
            append_iyuu_cache(plugin._iyuu_error_caches, seed.get("info_hash"))
        else:
            append_iyuu_cache(plugin._iyuu_permanent_error_caches, seed.get("info_hash"))
        logger.error(
            f"IYUU辅种：下载种子文件失败：站点={site_info.get('name')}，"
            f"info_hash={seed.get('info_hash')}，url={safe_torrent_url}，原因={error_msg or '未知'}"
        )
        return False

    logger.info(f"IYUU辅种：准备添加下载任务：{safe_torrent_url}")
    download_id = iyuu_download(plugin, service=service, content=content,
                                save_path=save_path, save_category=save_category,
                                site_name=site_info.get("name"),
                                expected_hash=seed.get("info_hash"),
                                torrent_url=torrent_url)
    if not download_id:
        plugin._iyuu_fail += 1
        append_iyuu_cache(plugin._iyuu_error_caches, seed.get("info_hash"))
        plugin._iyuu_cached += 1
        return False

    plugin._iyuu_success += 1
    append_iyuu_cache(plugin._iyuu_success_caches, seed.get("info_hash"))
    dl = service.instance
    dl_type = service.type

    if is_downloader_type("qbittorrent", service=service):
        if plugin._seed_skipverify:
            if plugin._seed_autostart:
                logger.info(f"IYUU辅种：{download_id} 跳过校验，自动开始")
                plugin._register_seed_recheck(service.name, [download_id], "iyuu")
            else:
                logger.info(f"IYUU辅种：{download_id} 跳过校验，等待手动开始")
        else:
            logger.info(f"IYUU辅种：qbittorrent 开始校验 {download_id}")
            dl.recheck_torrents(ids=[download_id])
            plugin._register_seed_recheck(service.name, [download_id], "iyuu")
    else:
        plugin._register_seed_recheck(service.name, [download_id], "iyuu")

    if plugin._rename_enabled:
        try:
            torrents, _ = dl.get_torrents(ids=[download_id])
            if torrents:
                t = torrents[0]
                torrent_name = t.get("name", "") if dl_type == "qbittorrent" else t.name
                save_path_t = t.get("save_path", "") if dl_type == "qbittorrent" else t.download_dir
                if torrent_name:
                    reused = plugin._rename_iyuu_torrent_by_source_record(
                        dl=dl, dl_type=dl_type, torrent_hash=download_id,
                        torrent_name=torrent_name, source_hash=source_hash
                    )
                    if not reused:
                        plugin._rename_torrent(dl, dl_type, download_id, torrent_name, save_path_t)
        except Exception as e:
            logger.error(f"IYUU辅种后重命名失败: {e}")

    if plugin._tag_enabled:
        try:
            torrents, _ = dl.get_torrents(ids=[download_id])
            if torrents:
                t = torrents[0]
                tags = [str(x).strip() for x in t.get("tags", "").split(",") if x.strip()] if dl_type == "qbittorrent" and t.get("tags") else (t.labels or [])
                trackers = [tr.get("url") for tr in (t.trackers or []) if tr.get("tier", -1) >= 0 and tr.get("url")] if dl_type == "qbittorrent" else [tr.announce for tr in (t.trackers or []) if tr.tier >= 0 and tr.announce]
                plugin._tag_torrent(dl, dl_type, download_id, tags, trackers)
        except Exception as e:
            logger.error(f"IYUU辅种后打标签失败: {e}")

    return True


def iyuu_download(plugin, service: ServiceInfo, content: bytes,
                  save_path: str, save_category: str, site_name: str,
                  expected_hash: str = None, torrent_url: str = None) -> Optional[str]:
    """添加 IYUU 辅种下载任务，并用 expected_hash + 临时标签多次确认任务入库。"""
    safe_torrent_url = mask_sensitive_url(torrent_url)
    torrent_tags = plugin._iyuu_labelsafterseed.split(',')
    if hasattr(plugin, '_iyuu_addhosttotag') and plugin._iyuu_addhosttotag:
        torrent_tags.append(site_name)

    if service.type == "qbittorrent":
        tag = generate_random_tag(10)
        torrent_tags.append(tag)

        def __find_torrent_hash():
            if expected_hash:
                try:
                    torrents, _ = service.instance.get_torrents(ids=[expected_hash])
                    if torrents:
                        return expected_hash
                except Exception as err:
                    logger.warning(f"IYUU辅种：按 expected_hash 查询任务失败：{expected_hash}，{err}")
            try:
                torrent_hash = service.instance.get_torrent_id_by_tag(tags=tag)
                if torrent_hash:
                    return torrent_hash
            except Exception as err:
                logger.warning(f"IYUU辅种：按临时标签查询任务失败：tag={tag}，{err}")
            return None

        state = service.instance.add_torrent(content=content, download_dir=save_path,
                                             is_paused=True, tag=torrent_tags,
                                             category=save_category,
                                             is_skip_checking=plugin._seed_skipverify)
        if not state:
            logger.error(
                f"IYUU辅种：{service.name} 下载任务添加失败：expected_hash={expected_hash}，"
                f"url={safe_torrent_url}，save_path={save_path}，category={save_category}"
            )
            return None

        for index in range(6):
            torrent_hash = __find_torrent_hash()
            if torrent_hash:
                logger.info(
                    f"IYUU辅种：成功添加下载任务：hash={torrent_hash}，站点={site_name}，"
                    f"确认方式={'expected_hash' if expected_hash and torrent_hash == expected_hash else 'tag'}"
                )
                return torrent_hash
            time.sleep(2)

        logger.error(
            f"IYUU辅种：{service.name} 下载器返回已接收，但未能确认任务入库："
            f"expected_hash={expected_hash}，tag={tag}，url={safe_torrent_url}，"
            f"save_path={save_path}，category={save_category}"
        )
        return None
    elif service.type == "transmission":
        torrent = service.instance.add_torrent(content=content, download_dir=save_path,
                                               is_paused=True, labels=torrent_tags)
        return torrent.hashString if torrent else None

    logger.error(f"IYUU辅种：不支持的下载器类型：{service.type}")
    return None


def iyuu_get_download_url(plugin, seed: dict, site: dict, base_url: str, force_page: bool = False) -> Optional[str]:
    """获取站点种子下载链接（移植自原版 IYUU 插件，含特殊站点处理）"""

    def __is_mteam(url: str):
        return "m-team." in url

    def __is_monika(url: str):
        return "monikadesign." in url

    def __is_gpw(url: str):
        return "greatposterwall." in url

    def __is_special_site(url: str):
        spec_params = ["hash=", "authkey="]
        if any(field in base_url for field in spec_params):
            return True
        special_domains = ["hdchina.org", "hdsky.me", "hdcity.in", "totheglory.im"]
        return any(d in url for d in special_domains)

    def __get_mteam_enclosure(tid: str, apikey: str):
        if not apikey:
            logger.warning("IYUU辅种：m-team 站点的 apikey 未配置")
            return None
        api_url = re.sub(r'//[^/]+\.m-team', '//api.m-team', site.get('url'))
        ua = site.get("ua") or settings.USER_AGENT
        res = request_post_res(
            f"{api_url}api/torrent/genDlToken",
            params={'id': tid},
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': ua,
                'Accept': 'application/json, text/plain, */*',
                'x-api-key': apikey
            }
        )
        if not res:
            logger.warning(f"IYUU辅种：m-team 获取种子下载链接失败：{tid}")
            return None
        return res.json().get("data")

    def __get_monika_torrent(tid: str, rssurl: str):
        if not rssurl:
            logger.warning("IYUU辅种：Monika 站点的 rss 链接未配置")
            return None
        rss_match = re.search(r'/rss/\d+\.(\w+)', rssurl)
        if not rss_match:
            logger.warning("IYUU辅种：Monika 站点 rss 链接格式不匹配")
            return None
        rsskey = rss_match.group(1)
        return f"{site.get('url')}torrents/download/{tid}.{rsskey}"

    def __get_torrent_url_from_page(seed: dict, site: dict):
        if not site.get('url'):
            logger.warning(f"IYUU辅种：站点 {site.get('name')} 未获取站点地址")
            return None
        try:
            page_url = f"{site.get('url')}details.php?id={seed.get('torrent_id')}&hit=1"
            logger.info(f"IYUU辅种：正在从详情页获取种子下载链接：{page_url}")
            res = request_get_res(
                page_url,
                cookies=site.get("cookie"),
                ua=site.get("ua") or settings.USER_AGENT,
                proxies=settings.PROXY if site.get("proxy") else None
            )
            if res is not None and res.status_code in (200, 500):
                if "charset=utf-8" in res.text or "charset=UTF-8" in res.text:
                    res.encoding = "UTF-8"
                else:
                    res.encoding = res.apparent_encoding
                if not res.text:
                    logger.warning(f"IYUU辅种：详情页内容为空：{page_url}")
                    return None
                html = etree.HTML(res.text)
                for xpath in plugin._iyuu_torrent_xpaths:
                    download_url = html.xpath(xpath)
                    if download_url:
                        download_url = download_url[0]
                        if not download_url.startswith("http"):
                            download_url = urljoin(site.get('url'), download_url)
                        logger.info(f"IYUU辅种：从详情页获取下载链接成功：{mask_sensitive_url(download_url)}")
                        return download_url
                logger.warning(f"IYUU辅种：详情页 xpath 未匹配到下载链接：{page_url}，站点：{site.get('name')}")
            else:
                logger.warning(f"IYUU辅种：详情页请求失败（HTTP {res.status_code if res else '无响应'}）：{page_url}")
        except Exception as e:
            logger.error(f"IYUU辅种：从详情页获取下载链接异常：{e}")
        return None

    try:
        site_url = site.get('url', '')

        if force_page:
            return __get_torrent_url_from_page(seed=seed, site=site)

        if __is_mteam(site_url):
            return __get_mteam_enclosure(tid=seed.get("torrent_id"), apikey=site.get("apikey"))

        if __is_monika(site_url):
            return __get_monika_torrent(tid=seed.get("torrent_id"), rssurl=site.get("rss"))

        if __is_gpw(site_url) or __is_special_site(site_url):
            return __get_torrent_url_from_page(seed=seed, site=site)

        download_url = base_url.replace(
            "id={}", "id={id}"
        ).replace(
            "/{}", "/{id}"
        ).replace(
            "/{torrent_key}", ""
        ).format(
            **{
                "id": seed.get("torrent_id"),
                "passkey": site.get("passkey") or '',
                "uid": site.get("uid") or '',
            }
        )
        if download_url.count("{"):
            logger.warning(f"IYUU辅种：当前不支持该站点的辅助任务，Url转换失败：{seed}")
            return None
        download_url = re.sub(r"[&?]passkey=", "",
                              re.sub(r"[&?]uid=", "",
                                     download_url,
                                     flags=re.IGNORECASE),
                              flags=re.IGNORECASE)
        return f"{site_url}{download_url}"
    except Exception as e:
        logger.warning(f"IYUU辅种：{site.get('name')} Url转换失败：{e}，回退到详情页获取")
        return __get_torrent_url_from_page(seed=seed, site=site)


def iyuu_save_history(plugin, current_hash: str, downloader: str, success_torrents: list):
    """保存 IYUU 辅种历史"""
    try:
        seed_history = plugin.get_data(key=iyuu_history_key(current_hash)) or []
        new_history = True
        for history in seed_history:
            if history and isinstance(history, dict) and str(history.get("downloader")) == downloader:
                history["torrents"] = list(set((history.get("torrents") or []) + success_torrents))
                new_history = False
                break
        if new_history:
            seed_history.append({"downloader": downloader, "torrents": list(set(success_torrents))})
        plugin.save_data(key=iyuu_history_key(current_hash), value=seed_history)
        for seed_hash in success_torrents:
            if seed_hash:
                plugin.save_data(key=iyuu_source_key(seed_hash), value=current_hash)
    except Exception as e:
        logger.error(f"IYUU辅种：保存历史失败：{e}")


def append_iyuu_cache(cache_list: list, info_hash: str):
    """追加 IYUU 辅种缓存"""
    if info_hash not in cache_list:
        cache_list.append(info_hash)


def trim_seed_cache(cache_list: list):
    """裁剪辅种缓存"""
    max_items = 10000
    if len(cache_list) > max_items:
        del cache_list[:len(cache_list) - max_items]


def custom_sites() -> list:
    """获取自定义站点"""
    try:
        return list_custom_site_dicts()
    except Exception:
        return []


def update_iyuu_config(plugin, config: dict = None):
    """更新 IYUU 辅种缓存到持久化存储（合并模式，不覆盖其他配置）"""
    if config is None:
        config = get_plugin_config(plugin.__class__.__name__)
    config["iyuu_permanent_error_caches"] = plugin._iyuu_permanent_error_caches
    config["iyuu_error_caches"] = plugin._iyuu_error_caches
    config["iyuu_success_caches"] = plugin._iyuu_success_caches
    plugin.update_config(config=config)


__all__ = (
    "append_iyuu_cache",
    "custom_sites",
    "iyuu_auto_seed",
    "iyuu_auto_service_info",
    "iyuu_download",
    "iyuu_download_torrent",
    "iyuu_get_download_url",
    "iyuu_save_history",
    "iyuu_seed_torrents",
    "iyuu_service_infos",
    "trim_seed_cache",
    "update_iyuu_config",
)
