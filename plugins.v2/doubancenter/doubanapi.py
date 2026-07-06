"""
DoubanCenter - Douban API
"""
import datetime
import re
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Tuple
from urllib.parse import unquote, urljoin
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from http.cookies import SimpleCookie
from app.core.config import settings
from app.core.meta import MetaBase
from app.helper.cookiecloud import CookieCloudHelper
from app.log import logger
from app.utils.http import RequestUtils


class _WishListParser(HTMLParser):
    """解析豆瓣想看列表页中的条目字段。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self._item = None
        self._item_depth = 0
        self._capture = ""
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        """处理想看条目的起始标签。"""
        attrs = dict(attrs or [])
        class_name = attrs.get("class") or ""
        if tag == "div" and "item" in class_name.split() and self._item is None:
            self._item = {"subject_id": "", "title": "", "year": "", "link": "", "poster": "", "wish_time": ""}
            self._item_depth = 1
            return
        if self._item is not None and tag == "div":
            self._item_depth += 1
        if self._item is None:
            return
        if tag == "a":
            href = attrs.get("href") or ""
            subject_id = _extract_subject_id(href)
            if subject_id:
                self._item["subject_id"] = self._item.get("subject_id") or subject_id
                self._item["link"] = self._item.get("link") or urljoin("https://movie.douban.com", href)
                self._capture = "title"
                self._buffer = []
        elif tag == "img":
            self._item["poster"] = self._item.get("poster") or attrs.get("src") or attrs.get("data-src") or ""
        elif tag in {"span", "li"}:
            if "date" in class_name.split():
                self._capture = "wish_time"
                self._buffer = []
            elif "intro" in class_name.split():
                self._capture = "intro"
                self._buffer = []

    def handle_data(self, data):
        """收集当前标签中的文本内容。"""
        if self._item is not None and self._capture:
            text = (data or "").strip()
            if text:
                self._buffer.append(text)

    def handle_endtag(self, tag):
        """处理想看条目的结束标签并落盘字段。"""
        if self._item is None:
            return
        if tag == "a" and self._capture == "title":
            title = " ".join(self._buffer).strip()
            if title and not self._item.get("title"):
                self._item["title"] = title
            self._capture = ""
            self._buffer = []
        elif tag == "span" and self._capture == "wish_time":
            self._item["wish_time"] = " ".join(self._buffer).strip()
            self._capture = ""
            self._buffer = []
        elif tag == "li" and self._capture == "intro":
            intro = " ".join(self._buffer).strip()
            year_match = re.search(r"(?:19|20)\d{2}", intro)
            if year_match and not self._item.get("year"):
                self._item["year"] = year_match.group(0)
            self._capture = ""
            self._buffer = []
        if tag == "div":
            self._item_depth -= 1
            if self._item_depth <= 0:
                if self._item.get("subject_id") and self._item.get("title"):
                    self.items.append(dict(self._item))
                self._item = None
                self._item_depth = 0
                self._capture = ""
                self._buffer = []


def _extract_subject_id(value: str = "") -> str:
    """从豆瓣条目链接中提取 subject id。"""
    match = re.search(r"/subject/(\d+)/?", value or "")
    return match.group(1) if match else ""


def parse_wish_items(html: str) -> list:
    """解析豆瓣想看列表 HTML 并返回结构化条目。"""
    parser = _WishListParser()
    parser.feed(html or "")
    return parser.items


def _xml_text(item, name: str) -> str:
    """读取 RSS 条目中的指定文本字段。"""
    element = item.find(name)
    return (element.text or "").strip() if element is not None else ""


def _parse_feed_datetime(value: str = ""):
    """解析豆瓣 feed 的发布时间并统一为 UTC 时间。"""
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def parse_interest_feed_items(feed: str, days: int = 7, now: datetime.datetime = None) -> list:
    """解析豆瓣动态 feed，仅返回最近指定天数内的想看条目。"""
    try:
        root = ElementTree.fromstring(feed or "")
    except ElementTree.ParseError:
        return []
    try:
        normalized_days = max(0, int(days or 0))
    except (TypeError, ValueError):
        normalized_days = 7
    now_dt = now or datetime.datetime.now(datetime.timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=datetime.timezone.utc)
    now_dt = now_dt.astimezone(datetime.timezone.utc)

    items = []
    for item in root.findall(".//item"):
        raw_title = _xml_text(item, "title")
        if not raw_title.startswith("想看"):
            continue
        pubdate = _parse_feed_datetime(_xml_text(item, "pubDate"))
        if pubdate and (now_dt - pubdate).days > normalized_days:
            continue
        link = _xml_text(item, "link")
        subject_id = _extract_subject_id(link)
        title = raw_title[2:].strip()
        if not subject_id or not title:
            continue
        items.append({
            "subject_id": subject_id,
            "title": title,
            "year": "",
            "link": link,
            "poster": "",
            "wish_time": pubdate.strftime("%Y-%m-%d %H:%M:%S") if pubdate else "",
        })
    return items


class DoubanApi:
    """封装豆瓣搜索与观看状态写入接口。"""

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
        """从豆瓣首页响应中刷新 ck cookie。"""
        self.headers["Cookie"] = ";".join([f"{k}={v}" for k, v in self.cookies.items()])
        response = requests.get("https://www.douban.com/", headers=self.headers)
        ck_str = response.headers.get('Set-Cookie', '')
        if not ck_str:
            self.cookies['ck'] = ''
            return
        ck = ck_str.split(";")[0].split("=")[1].strip()
        self.cookies['ck'] = '' if ck == '"deleted"' else ck

    def get_subject_id(self, title: str = None, meta: MetaBase = None) -> Tuple:
        """根据标题或媒体元数据搜索豆瓣条目 ID。"""
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

    def _prepare_movie_headers(self) -> None:
        """为豆瓣电影页请求准备 Cookie 与 Host 头。"""
        self.headers.pop("HOST", None)
        self.headers.update({
            "Host": "movie.douban.com",
            "Cookie": ";".join([f"{k}={v}" for k, v in getattr(self, "cookies", {}).items()])
        })

    def _prepare_feed_headers(self) -> None:
        """为豆瓣动态 feed 请求准备 Cookie 与 Host 头。"""
        self.headers.pop("HOST", None)
        self.headers.update({
            "Host": "www.douban.com",
            "Cookie": ";".join([f"{k}={v}" for k, v in getattr(self, "cookies", {}).items()])
        })

    def get_wish_items(self, user_id: str = "", max_pages: int = 1, days: int = 7, request_get=None, now=None) -> list:
        """从豆瓣动态 feed 读取最近指定天数内的想看条目。"""
        if not user_id:
            raise ValueError("缺少豆瓣用户 ID")
        self._prepare_feed_headers()
        getter = request_get
        if getter is None:
            getter = lambda url: RequestUtils(headers=self.headers).get_res(url)
        response = getter(f"https://www.douban.com/feed/people/{user_id}/interests")
        if not response:
            raise RuntimeError("读取豆瓣想看 feed 失败：无响应")
        status_code = getattr(response, "status_code", 0)
        if status_code != 200:
            raise RuntimeError(f"读取豆瓣想看 feed 失败：HTTP {status_code}")
        return parse_interest_feed_items(getattr(response, "text", "") or "", days=days, now=now)

    def set_watching_status(self, subject_id: str, status: str = "do", private: bool = True) -> bool:
        """设置豆瓣条目的观看状态。"""
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
