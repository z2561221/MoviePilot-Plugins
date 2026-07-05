import unittest

from pathlib import Path
import importlib.util
import sys
import types


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
parse_wish_items = doubanapi.parse_wish_items


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200, url: str = ""):
        self.text = text
        self.status_code = status_code
        self.url = url


class DoubanWishApiTest(unittest.TestCase):
    def test_parse_wish_items_extracts_subject_fields(self):
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

    def test_get_wish_items_uses_first_page_by_default(self):
        requested_urls = []
        html = """
        <div class="item">
          <a href="https://movie.douban.com/subject/7654321/">测试剧集</a>
          <span class="date">2026-07-05</span>
        </div>
        """
        api = object.__new__(DoubanApi)
        api.headers = {"User-Agent": "test"}

        def fake_get(url):
            requested_urls.append(url)
            return FakeResponse(html, url=url)

        items = api.get_wish_items(user_id="tester", request_get=fake_get)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["subject_id"], "7654321")
        self.assertEqual(requested_urls, ["https://movie.douban.com/people/tester/wish?start=0&sort=time&mode=list"])

    def test_get_wish_items_uses_cookie_current_account_headers(self):
        requested_urls = []
        html = """
        <div class="item">
          <a href="https://movie.douban.com/subject/1357246/">Cookie user wish</a>
        </div>
        """
        api = object.__new__(DoubanApi)
        api.cookies = {"dbcl2": "user-token", "ck": "cookie-token"}
        api.headers = {"User-Agent": "test"}

        def fake_get(url):
            requested_urls.append(url)
            return FakeResponse(html, url=url)

        items = api.get_wish_items(request_get=fake_get)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["subject_id"], "1357246")
        self.assertEqual(requested_urls, ["https://movie.douban.com/mine?status=wish&start=0&sort=time&mode=list"])
        self.assertEqual(api.headers["Host"], "movie.douban.com")
        self.assertEqual(api.headers["Cookie"], "dbcl2=user-token;ck=cookie-token")


if __name__ == "__main__":
    unittest.main()
