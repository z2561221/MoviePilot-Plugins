import hashlib
import json
import time
from typing import Tuple, Optional

from app.log import logger

from .adapter.moviepilot import request_get_res, request_post_res


class IyuuHelper(object):
    """
    适配新版本IYUU开发版
    """
    _version = "8.2.0"
    _api_base = "https://2025.iyuu.cn"
    _sites = {}
    _token = None
    _sid_sha1 = None

    def __init__(self, token: str):
        self._token = token
        if self._token:
            self.init_config()

    def init_config(self):
        """保留 IYUU 初始化扩展点，当前版本无需额外加载配置。"""
        pass

    def ensure_ready(self) -> Tuple[bool, str]:
        """
        确认 IYUU Token、站点列表和站点绑定摘要可用于辅种查询。
        """
        if not self._token:
            return False, "未配置 IYUU Token"
        if not self._sites:
            self._sites = self.__get_sites()
        if not self._sites:
            return False, "未获取到 IYUU 支持站点列表"
        if not self._sid_sha1:
            self._sid_sha1 = self.__report_existing()
        if not self._sid_sha1:
            return False, "IYUU 站点汇报失败或未绑定推荐站点"
        return True, ""

    def __request_iyuu(self, url: str, method: str = "get", params: dict = None) -> Tuple[Optional[dict], str]:
        """
        向IYUUApi发送请求
        """
        if method == "post":
            ret = request_post_res(
                f'{self._api_base + url}',
                json=params,
                accept_type="application/json",
                headers={'token': self._token}
            )
        else:
            ret = request_get_res(
                f'{self._api_base + url}',
                params=params,
                accept_type="application/json",
                headers={'token': self._token}
            )
        if ret:
            result = ret.json()
            if result.get('code') == 0:
                return result.get('data'), ""
            else:
                return None, f'请求IYUU失败，状态码：{result.get("code")}，返回信息：{result.get("msg")}'
        elif ret is not None:
            return None, f"请求IYUU失败，状态码：{ret.status_code}，错误原因：{ret.reason}"
        else:
            return None, f"请求IYUU失败，未获取到返回信息"

    def get_torrent_url(self, sid: str) -> Tuple[Optional[str], Optional[str]]:
        """根据 IYUU 站点 id 返回站点基础地址和下载页规则。"""
        if not sid:
            return None, None
        if not self._sites:
            self._sites = self.__get_sites()
        if not self._sites.get(sid):
            return None, None
        site = self._sites.get(sid)
        return site.get('base_url'), site.get('download_page')

    def __get_sites(self) -> dict:
        """
        返回支持辅种的全部站点
        :return: 站点列表、错误信息
        """
        result, msg = self.__request_iyuu(url='/reseed/sites/index')
        if result:
            ret_sites = {}
            sites = result.get('sites')
            for site in sites:
                ret_sites[site.get('id')] = site
            return ret_sites
        else:
            logger.warning(f"IYUU获取站点列表失败：{msg}")
            return {}

    def __report_existing(self) -> Optional[str]:
        """
        汇报辅种的站点
        :return:
        """
        if not self._sites:
            self._sites = self.__get_sites()
        sid_list = list(self._sites.keys())
        if not sid_list:
            logger.warning("IYUU汇报站点失败：站点列表为空，跳过 sid_list 为空的请求")
            return None
        result, msg = self.__request_iyuu(url='/reseed/sites/reportExisting',
                                          method='post',
                                          params={'sid_list': sid_list})
        if result:
            return result.get('sid_sha1')
        logger.warning(f"IYUU汇报站点失败：{msg}")
        return None

    def __reseed_index(self, json_data: str, sha1: str) -> Tuple[Optional[dict], str]:
        """向 IYUU 查询指定 info_hash 列表的可辅种信息。"""
        return self.__request_iyuu(url='/reseed/index/index', method='post', params={
            'hash': json_data,
            'sha1': sha1,
            'sid_sha1': self._sid_sha1,
            'timestamp': int(time.time()),
            'version': self._version
        })

    def get_seed_info(self, info_hashs: list) -> Tuple[Optional[dict], str]:
        """
        返回info_hash对应的站点id、种子id
        :param info_hashs:
        :return:
        """
        if not info_hashs:
            return {}, ""
        ready, msg = self.ensure_ready()
        if not ready:
            return None, msg
        info_hashs.sort()
        json_data = json.dumps(info_hashs, separators=(',', ':'), ensure_ascii=False)
        sha1 = self.get_sha1(json_data)
        result, msg = self.__reseed_index(json_data, sha1)
        if msg and "站点哈希值 require" in msg:
            self._sid_sha1 = self.__report_existing()
            if not self._sid_sha1:
                return None, "IYUU 站点哈希刷新失败"
            result, msg = self.__reseed_index(json_data, sha1)
        return result, msg

    @staticmethod
    def get_sha1(json_str: str) -> str:
        """计算 IYUU 请求签名需要的 SHA1 摘要。"""
        return hashlib.sha1(json_str.encode('utf-8')).hexdigest()
