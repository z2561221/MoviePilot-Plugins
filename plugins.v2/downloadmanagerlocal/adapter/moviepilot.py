"""MoviePilot 下载器、站点、HTTP 与系统配置访问适配器。"""

from __future__ import annotations

from typing import Any

from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.site_oper import SiteOper
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.downloader import DownloaderHelper
from app.helper.sites import SitesHelper
from app.helper.torrent import TorrentHelper
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.schemas.types import SystemConfigKey
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


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


def list_builtin_sites() -> list:
    """读取 MoviePilot 内置站点列表。"""
    return SiteOper().list_order_by_pri()


def get_user_sites():
    """读取 MoviePilot 自定义站点配置。"""
    return SystemConfigOper().get(SystemConfigKey.UserSite) or {}


def list_custom_site_dicts() -> list:
    """读取自定义站点字典列表，兼容 dict 与 list 两种存储形态。"""
    sites = get_user_sites()
    values = sites.values() if isinstance(sites, dict) else sites
    return [site for site in values or [] if isinstance(site, dict)]


def get_site_indexer(domain: str):
    """按域名读取站点索引配置。"""
    return SitesHelper().get_indexer(domain)


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
