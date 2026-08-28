"""豆瓣中心 V3 生命周期、命名空间与网络合同测试。"""

from app.plugins.doubancenter import DoubanCenter, doubanapi, feed, folio, migration


class _FakeResponse:
    """提供豆瓣接口测试所需的最小响应。"""

    def __init__(self, *, headers=None, payload=None, status_code=200, text=""):
        self.headers = headers or {}
        self._payload = payload or {}
        self.status_code = status_code
        self.text = text

    def json(self):
        """返回预设 JSON 数据。"""
        return self._payload


def test_plugin_imports_through_production_namespace():
    """插件主类只能以生产命名空间加载。"""
    assert DoubanCenter.__module__ == "app.plugins.doubancenter"


def test_init_stops_previous_run_before_config_migration_and_tasks(monkeypatch):
    """重复初始化必须先停止旧资源，再覆盖配置、迁移数据和启动一次性任务。"""
    events = []
    plugin = object.__new__(DoubanCenter)
    plugin.stop_service = lambda: events.append("stop")
    plugin.update_config = lambda config: events.append("config")
    monkeypatch.setattr(
        migration,
        "migrate_plugin_media_identity",
        lambda *args, **kwargs: events.append("migrate"),
    )
    monkeypatch.setattr(
        migration,
        "normalize_legacy_subscribe_usernames",
        lambda: events.append("normalize"),
    )
    monkeypatch.setattr(feed, "run_once", lambda current: events.append("feed"))
    monkeypatch.setattr(folio, "run_wish_scheduled", lambda current: events.append("wish"))

    plugin.init_plugin({"enabled": True, "onlyonce": True, "wish_onlyonce": True})

    assert events[0] == "stop"
    for event in ("config", "migrate", "normalize", "feed", "wish"):
        assert events.index("stop") < events.index(event)


def test_set_ck_uses_moviepilot_request_utils(monkeypatch):
    """豆瓣首页请求必须通过 MoviePilot 网络封装刷新 ck。"""
    captured = {}

    class FakeRequestUtils:
        """记录首页请求参数。"""

        def __init__(self, *, headers=None):
            captured["headers"] = headers

        def get_res(self, url):
            """返回带 ck 的模拟响应。"""
            captured["url"] = url
            return _FakeResponse(headers={"Set-Cookie": "ck=test-token; Path=/"})

    monkeypatch.setattr(doubanapi, "RequestUtils", FakeRequestUtils)
    api = object.__new__(doubanapi.DoubanApi)
    api.headers = {}
    api.cookies = {"dbcl2": "123:token"}

    api.set_ck()

    assert captured["url"] == "https://www.douban.com/"
    assert captured["headers"] is api.headers
    assert api.cookies["ck"] == "test-token"


def test_set_watching_status_uses_moviepilot_request_utils(monkeypatch):
    """豆瓣观看状态写入必须通过 MoviePilot 网络封装提交表单。"""
    captured = {}

    class FakeRequestUtils:
        """记录观看状态请求参数。"""

        def __init__(self, *, headers=None):
            captured["headers"] = headers

        def post_res(self, url, *, data=None):
            """返回成功的豆瓣状态响应。"""
            captured["url"] = url
            captured["data"] = data
            return _FakeResponse(payload={"r": True})

    monkeypatch.setattr(doubanapi, "RequestUtils", FakeRequestUtils)
    api = object.__new__(doubanapi.DoubanApi)
    api.headers = {}
    api.cookies = {"dbcl2": "123:token"}
    api.ck = "test-token"

    assert api.set_watching_status("1295644", status="collect", private=True)
    assert captured["url"] == "https://movie.douban.com/j/subject/1295644/interest"
    assert captured["headers"] is api.headers
    assert captured["data"]["ck"] == "test-token"
    assert captured["data"]["interest"] == "collect"
    assert captured["data"]["private"] == "on"
