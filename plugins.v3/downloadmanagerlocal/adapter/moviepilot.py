"""MoviePilot 下载器、站点、HTTP 与系统配置访问适配器。"""

from __future__ import annotations

from typing import Any

from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.site_oper import SiteOper
from app.db.systemconfig_oper import SystemConfigOper
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.sdk.network import RequestUtils
from app.sdk.services import DownloaderHelper
from app.sdk.utilities import StringUtils

try:
    from app.sdk.network import SitesHelper
except ImportError:
    from app.infrastructure.sites import SitesHelper

try:
    from app.application.torrent import TorrentHelper
except ImportError:
    from app.services.torrent import TorrentHelper


DownloaderInstance = Qbittorrent | Transmission


def create_downloader_helper() -> DownloaderHelper:
    """创建 MoviePilot 下载器 helper。"""
    return DownloaderHelper()


def get_downloader_service(name: str):
    """按名称读取下载器服务信息。"""
    return create_downloader_helper().get_service(name)


def get_downloader_config(name: str):
    """按名称读取下载器配置对象。"""
    return create_downloader_helper().get_config(name)


def get_downloader_services(name_filters=None):
    """按名称过滤读取下载器服务信息。"""
    return create_downloader_helper().get_services(name_filters=name_filters)


def is_downloader_type(downloader_type: str, service: Any) -> bool:
    """判断服务是否为指定下载器类型。"""
    return create_downloader_helper().is_downloader(downloader_type, service=service)


def generate_random_tag(length: int = 10) -> str:
    """生成下载器临时标签。"""
    return StringUtils.generate_random_str(length)


def get_url_domain(url: str) -> str:
    """提取 URL 域名。"""
    return StringUtils.get_url_domain(url)


def get_download_history_by_hash(torrent_hash: str):
    """按种子 hash 读取 MoviePilot 下载历史。"""
    return DownloadHistoryOper().get_by_hash(torrent_hash)


def get_download_hash_by_fullpath(fullpath: str) -> str:
    """按媒体文件完整路径反查下载历史 hash。"""
    return DownloadHistoryOper().get_hash_by_fullpath(fullpath)


def list_builtin_sites() -> list:
    """读取 MoviePilot V3 站点数据库中的全部站点。"""
    return SiteOper().list_order_by_pri()


def _site_to_dict(site) -> dict:
    """把 MoviePilot 站点记录转换为插件内部使用的普通字典。"""
    if not site:
        return {}
    result = dict(getattr(site, "note", None) or {})
    for field in (
        "id",
        "name",
        "domain",
        "url",
        "pri",
        "rss",
        "cookie",
        "ua",
        "apikey",
        "token",
        "proxy",
        "render",
        "public",
        "is_active",
        "downloader",
    ):
        value = getattr(site, field, None)
        if value is not None:
            result[field] = value
    return result


def list_site_dicts() -> list[dict]:
    """读取 MoviePilot V3 统一站点记录的字典视图。"""
    return [_site_to_dict(site) for site in list_builtin_sites() if site]


def list_custom_site_dicts() -> list:
    """V3 站点已统一落库，不再返回独立的自定义站点集合。"""
    return []


def _get_site_by_domain(domain: str):
    """按规范域名查找 MoviePilot V3 站点记录。"""
    normalized = get_url_domain(domain) or str(domain or "").strip()
    if not normalized:
        return None
    site = SiteOper().get_by_domain(normalized)
    if site:
        return site
    for candidate in list_builtin_sites():
        candidate_domain = get_url_domain(
            getattr(candidate, "domain", None) or getattr(candidate, "url", None)
        )
        if candidate_domain == normalized:
            return candidate
    return None


def get_site_indexer(domain: str):
    """按域名合并站点索引模板与 V3 站点数据库凭据。"""
    indexer = SitesHelper().get_indexer(domain) or {}
    site = _get_site_by_domain(domain)
    if not site:
        return indexer or None
    return {**indexer, **_site_to_dict(site)}


def check_site(domain: str):
    """调用 MoviePilot 站点检查。"""
    return SitesHelper().check(domain)


def download_torrent_content(url: str, cookie=None, ua=None, proxy=None):
    """通过 MoviePilot TorrentHelper 下载种子内容。"""
    return TorrentHelper().download_torrent(url=url, cookie=cookie, ua=ua, proxy=proxy)


def request_get_res(url: str, params: dict | None = None, **kwargs):
    """通过 MoviePilot RequestUtils 发送 GET 请求。"""
    return RequestUtils(**kwargs).get_res(url=url, params=params)


def request_post_res(url: str, params: dict | None = None, json: dict | None = None, **kwargs):
    """通过 MoviePilot RequestUtils 发送 POST 请求。"""
    return RequestUtils(**kwargs).post_res(url, params=params, json=json)


def get_plugin_config(plugin_class_name: str) -> dict:
    """读取指定插件类名对应的系统配置。"""
    return SystemConfigOper().get(f"plugin.{plugin_class_name}") or {}
