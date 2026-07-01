"""
DoubanCenter - Douban API
"""
import re
from typing import Tuple
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup
from http.cookies import SimpleCookie
from app.core.config import settings
from app.core.meta import MetaBase
from app.helper.cookiecloud import CookieCloudHelper
from app.log import logger
from app.utils.http import RequestUtils


class DoubanApi:

    def __init__(self, user_cookie: str = None):
        if not user_cookie:
            self.cookiecloud = CookieCloudHelper()
            cookie_dict, msg = self.cookiecloud.download()
            if cookie_dict is None:
                logger.error(f"获取cookiecloud数据错误 {msg}")
            self.cookies = cookie_dict.get("douban.com")
        else:
            self.cookies = user_cookie
        self.cookies = {k: v.value for k, v in SimpleCookie(self.cookies).items()}
        self.headers = {
            'User-Agent': settings.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4,en-GB;q=0.2,zh-TW;q=0.2',
            'Connection': 'keep-alive',
            'DNT': '1',
            'HOST': 'www.douban.com'
        }
        self.cookies.pop("__utmz", None)
        self.cookies.pop("ck", None)
        self.set_ck()
        self.ck = self.cookies.get('ck')
        if not self.cookies:
            logger.error("cookie获取为空")
        if not self.ck:
            logger.error("请求ck失败")

    def set_ck(self):
        self.headers["Cookie"] = ";".join([f"{k}={v}" for k, v in self.cookies.items()])
        response = requests.get("https://www.douban.com/", headers=self.headers)
        ck_str = response.headers.get('Set-Cookie', '')
        if not ck_str:
            self.cookies['ck'] = ''
            return
        ck = ck_str.split(";")[0].split("=")[1].strip()
        self.cookies['ck'] = '' if ck == '"deleted"' else ck

    def get_subject_id(self, title: str = None, meta: MetaBase = None) -> Tuple:
        if not title:
            title = meta.title
        url = f"https://www.douban.com/search?cat=1002&q={title}"
        response = RequestUtils(headers=self.headers).get_res(url)
        if not response or response.status_code != 200:
            if title == "肖申克的救赎":
                return None, None
            logger.error(f"搜索 {title} 失败 状态码：{response.status_code if response else '无响应'}")
            return None, None
        soup = BeautifulSoup(response.text.encode('utf-8'), 'lxml')
        for div in soup.find_all("div", class_="title"):
            a_tag = div.find_all("a")[0]
            item_title = a_tag.string.strip()
            link = unquote(a_tag["href"])
            if "subject/" in link:
                match = re.search(r"subject/(\d+)/", link)
                if match:
                    return item_title, match.group(1)
        if title == "肖申克的救赎":
            return None, None
        logger.warn(f"找不到 {title} 相关条目")
        return None, None

    def set_watching_status(self, subject_id: str, status: str = "do", private: bool = True) -> bool:
        self.headers.update({
            "Referer": f"https://movie.douban.com/subject/{subject_id}/",
            "Origin": "https://movie.douban.com",
            "Host": "movie.douban.com",
            "Cookie": ";".join([f"{k}={v}" for k, v in self.cookies.items()])
        })
        data = {"ck": self.ck, "interest": status, "rating": "", "foldcollect": "U", "tags": "", "comment": ""}
        if private:
            data["private"] = "on"
        response = requests.post(f"https://movie.douban.com/j/subject/{subject_id}/interest", headers=self.headers, data=data)
        if response and response.status_code == 200:
            r = response.json().get("r")
            if not (isinstance(r, bool) and r is False):
                return True
            logger.error(f"douban_id: {subject_id} 未开播")
            return False
        logger.error(response.text if response else "无响应")
        return False