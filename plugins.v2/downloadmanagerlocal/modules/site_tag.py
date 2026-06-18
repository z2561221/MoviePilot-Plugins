"""站点标签模块"""

from typing import Optional

from app.db.systemconfig_oper import SystemConfigOper
from app.helper.sites import SitesHelper
from app.log import logger
from app.schemas.types import SystemConfigKey
from app.utils.string import StringUtils


def find_site_by_domain(domain: str) -> Optional[str]:
    """通过域名从系统站点配置中查找站点名称（优先 SystemConfigOper，fallback SitesHelper）"""
    # 方式1：SystemConfigOper（无需认证，调度器环境可用）
    try:
        sites = SystemConfigOper().get(SystemConfigKey.UserSite) or {}
        if sites:
            for site_info in sites.values():
                if not isinstance(site_info, dict):
                    continue
                site_domain = site_info.get("domain", "")
                if not site_domain:
                    continue
                site_domain_clean = StringUtils.get_url_domain(site_domain)
                if site_domain_clean and site_domain_clean in domain:
                    return site_info.get("name")
                if domain in site_domain:
                    return site_info.get("name")
    except Exception:
        pass

    # 方式2：SitesHelper（需要用户认证，作为 fallback）
    try:
        sh = SitesHelper()
        site_info = sh.get_indexer(domain)
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
                domain = StringUtils.get_url_domain(tracker)
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
