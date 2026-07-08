import datetime
import importlib.util
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def load_doubanapi():
    """加载 doubanapi 模块并替换 MoviePilot 宿主依赖。"""
    app_module = types.ModuleType("app")
    app_core = types.ModuleType("app.core")
    app_core_config = types.ModuleType("app.core.config")
    app_core_config.settings = types.SimpleNamespace(USER_AGENT="test-agent")
    app_core_meta = types.ModuleType("app.core.meta")
    app_core_meta.MetaBase = object
    app_helper = types.ModuleType("app.helper")
    app_helper_cookiecloud = types.ModuleType("app.helper.cookiecloud")
    app_helper_cookiecloud.CookieCloudHelper = object
    app_log = types.ModuleType("app.log")
    app_log.logger = types.SimpleNamespace(error=lambda *args, **kwargs: None, warn=lambda *args, **kwargs: None)
    app_utils = types.ModuleType("app.utils")
    app_utils_http = types.ModuleType("app.utils.http")
    app_utils_http.RequestUtils = object
    requests_module = types.ModuleType("requests")
    requests_module.get = lambda *args, **kwargs: None
    requests_module.post = lambda *args, **kwargs: None
    bs4_module = types.ModuleType("bs4")
    bs4_module.BeautifulSoup = object
    sys.modules.update(
        {
            "app": app_module,
            "app.core": app_core,
            "app.core.config": app_core_config,
            "app.core.meta": app_core_meta,
            "app.helper": app_helper,
            "app.helper.cookiecloud": app_helper_cookiecloud,
            "app.log": app_log,
            "app.utils": app_utils,
            "app.utils.http": app_utils_http,
            "requests": requests_module,
            "bs4": bs4_module,
        }
    )
    spec = importlib.util.spec_from_file_location("doubancenter_doubanapi", PLUGIN_DIR / "doubanapi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


doubanapi = load_doubanapi()
DoubanApi = doubanapi.DoubanApi
DoubanCookieError = doubanapi.DoubanCookieError
parse_wish_items = doubanapi.parse_wish_items
parse_interest_feed_items = doubanapi.parse_interest_feed_items


class FakeResponse:
    """用于替代 RequestUtils 返回值的测试响应。"""

    def __init__(self, text: str, status_code: int = 200, url: str = ""):
        """保存响应文本、状态码和 URL。"""
        self.text = text
        self.status_code = status_code
        self.url = url


class DoubanWishApiTest(unittest.TestCase):
    def test_parse_wish_items_extracts_subject_fields(self):
        """解析豆瓣想看页中的条目字段，供 Cookie 主路径复用。"""
        html = """
        <div class="grid-view">
          <div class="item">
            <div class="pic">
              <a href="https://movie.douban.com/subject/1234567/">
                <img src="https://img.example/poster.jpg" />
              </a>
            </div>
            <div class="info">
              <ul>
                <li class="title"><a href="https://movie.douban.com/subject/1234567/">测试电影</a></li>
                <li class="intro">2026-07-01 / 中国大陆 / 剧情</li>
              </ul>
              <span class="date">2026-07-05</span>
            </div>
          </div>
        </div>
        """

        items = parse_wish_items(html)

        self.assertEqual(
            items,
            [
                {
                    "subject_id": "1234567",
                    "title": "测试电影",
                    "year": "2026",
                    "link": "https://movie.douban.com/subject/1234567/",
                    "poster": "https://img.example/poster.jpg",
                    "wish_time": "2026-07-05",
                }
            ],
        )

    def test_parse_interest_feed_items_keeps_recent_wish_only(self):
        """feed 解析只保留最近天数内的想看条目。"""
        feed = """
        <rss><channel>
          <item>
            <title><![CDATA[想看小城日常]]></title>
            <link>https://movie.douban.com/subject/37054059/</link>
            <pubDate>Mon, 06 Jul 2026 01:00:00 GMT</pubDate>
          </item>
          <item>
            <title><![CDATA[在看重症外伤中心]]></title>
            <link>https://movie.douban.com/subject/36098554/</link>
            <pubDate>Mon, 06 Jul 2026 02:00:00 GMT</pubDate>
          </item>
          <item>
            <title><![CDATA[想看旧电影]]></title>
            <link>https://movie.douban.com/subject/1111111/</link>
            <pubDate>Mon, 29 Jun 2026 01:00:00 GMT</pubDate>
          </item>
        </channel></rss>
        """

        items = parse_interest_feed_items(
            feed,
            days=3,
            now=datetime.datetime(2026, 7, 6, 12, 0, tzinfo=datetime.timezone.utc),
        )

        self.assertEqual(
            items,
            [
                {
                    "subject_id": "37054059",
                    "title": "小城日常",
                    "year": "",
                    "link": "https://movie.douban.com/subject/37054059/",
                    "poster": "",
                    "wish_time": "2026-07-06 01:00:00",
                }
            ],
        )

    def test_get_wish_items_uses_interest_feed_with_days(self):
        """想看同步读取豆瓣动态 feed，并按最近天数过滤。"""
        requested_urls = []
        feed = """
        <rss><channel>
          <item>
            <title>想看小城日常</title>
            <link>https://movie.douban.com/subject/37054059/</link>
            <pubDate>Mon, 06 Jul 2026 01:00:00 GMT</pubDate>
          </item>
        </channel></rss>
        """
        api = object.__new__(DoubanApi)
        api.headers = {"User-Agent": "test"}

        def fake_get(url):
            requested_urls.append(url)
            return FakeResponse(feed, url=url)

        items = api.get_wish_items(
            user_id="tester",
            days=7,
            request_get=fake_get,
            now=datetime.datetime(2026, 7, 6, 12, 0, tzinfo=datetime.timezone.utc),
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["subject_id"], "37054059")
        self.assertEqual(requested_urls, ["https://www.douban.com/feed/people/tester/interests"])

    def test_get_wish_items_prefers_cookie_user_page_over_config_user(self):
        """存在登录 Cookie 时优先读取当前账号想看页。"""
        requested_urls = []
        html = """
        <div class="grid-view">
          <div class="item">
            <div class="pic">
              <a href="https://movie.douban.com/subject/37054059/">
                <img src="https://img.example/poster.jpg" />
              </a>
            </div>
            <div class="info">
              <ul>
                <li class="title"><a href="https://movie.douban.com/subject/37054059/">小城日常</a></li>
                <li class="intro">2026 / 中国大陆 / 剧情</li>
              </ul>
              <span class="date">2026-07-06</span>
            </div>
          </div>
        </div>
        """
        api = object.__new__(DoubanApi)
        api.headers = {"User-Agent": "test"}
        api.cookies = {"dbcl2": "123456:token", "bid": "abc"}

        def fake_get(url):
            requested_urls.append(url)
            return FakeResponse(html, url=url)

        items = api.get_wish_items(user_id="fallback-user", request_get=fake_get)

        self.assertEqual(items[0]["subject_id"], "37054059")
        self.assertEqual(
            requested_urls,
            [
                "https://movie.douban.com/people/123456/wish"
                "?start=0&sort=time&rating=all&filter=all&mode=grid"
            ],
        )

    def test_get_wish_items_falls_back_to_feed_when_cookie_has_no_user_id(self):
        """Cookie 中没有 dbcl2 时才回退到配置的用户 ID feed。"""
        requested_urls = []
        feed = """
        <rss><channel>
          <item>
            <title>想看小城日常</title>
            <link>https://movie.douban.com/subject/37054059/</link>
            <pubDate>Mon, 06 Jul 2026 01:00:00 GMT</pubDate>
          </item>
        </channel></rss>
        """
        api = object.__new__(DoubanApi)
        api.headers = {"User-Agent": "test"}
        api.cookies = {"bid": "abc"}

        def fake_get(url):
            requested_urls.append(url)
            return FakeResponse(feed, url=url)

        items = api.get_wish_items(user_id="tester", request_get=fake_get)

        self.assertEqual(items[0]["subject_id"], "37054059")
        self.assertEqual(requested_urls, ["https://www.douban.com/feed/people/tester/interests"])

    def test_get_wish_items_reports_missing_cookie_and_user_id(self):
        """Cookie 和配置都无法定位账号时报告 Cookie/配置异常。"""
        api = object.__new__(DoubanApi)
        api.headers = {"User-Agent": "test"}
        api.cookies = {"bid": "abc"}

        with self.assertRaisesRegex(DoubanCookieError, "缺少.*dbcl2"):
            api.get_wish_items(request_get=lambda url: FakeResponse(""))

    def test_get_wish_items_reports_cookie_page_forbidden(self):
        """登录 Cookie 想看页被拒绝时报告 Cookie 失效或风控。"""
        api = object.__new__(DoubanApi)
        api.headers = {"User-Agent": "test"}
        api.cookies = {"dbcl2": "123456:token"}

        with self.assertRaisesRegex(DoubanCookieError, "HTTP 403"):
            api.get_wish_items(request_get=lambda url: FakeResponse("forbidden", status_code=403))

    def test_get_wish_items_raises_when_feed_has_no_response(self):
        """feed 请求无响应时抛错，避免把同步失败伪装成空结果。"""
        api = object.__new__(DoubanApi)
        api.headers = {"User-Agent": "test"}

        with self.assertRaisesRegex(RuntimeError, "无响应"):
            api.get_wish_items(user_id="tester", request_get=lambda url: None)

    def test_get_wish_items_raises_when_feed_status_is_not_ok(self):
        """feed 请求返回非 200 时抛错并暴露状态码。"""
        api = object.__new__(DoubanApi)
        api.headers = {"User-Agent": "test"}

        with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
            api.get_wish_items(user_id="tester", request_get=lambda url: FakeResponse("forbidden", status_code=403))


if __name__ == "__main__":
    unittest.main()
