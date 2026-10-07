"""通过真正注册的 HTTP 入口核对季号，不只测试内部 service。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.plugins.doubancenter import DoubanCenter
from app.plugins.doubancenter.controller import api


@pytest.mark.parametrize("season", [0, 6])
@pytest.mark.parametrize("endpoint,method,callback", [
    ("/resolve_media", "GET", "api_resolve_media_from_rank"),
    ("/subscribe", "POST", "api_subscribe_from_rank"),
])
def test_registered_endpoints_forward_season(monkeypatch, season, endpoint, method, callback):
    """普通续季和特别篇季号都应原样传到业务层。"""
    received = []

    def capture(**kwargs):
        """捕获业务参数，禁止真实识别或订阅。"""
        received.append(kwargs["season"])
        return {"success": True, "data": {"title": "HTTP季号测试", "season": kwargs["season"]}}

    monkeypatch.setattr(api.dash, callback, capture)
    plugin = object.__new__(DoubanCenter)
    application = FastAPI()
    route = next(route for route in plugin.get_api() if route["path"] == endpoint)
    application.add_api_route(endpoint, route["endpoint"], methods=route["methods"], response_model=route["response_model"])
    with TestClient(application) as client:
        response = client.request(method, endpoint, params={"title": "HTTP季号测试", "media_type": "tv", "season": season})
        assert response.status_code == 200
        assert response.json()["data"]["season"] == season
        assert received == [season]
        invalid = client.request(method, endpoint, params={"title": "HTTP季号测试", "season": "bad"})
        assert invalid.status_code == 422
        assert received == [season]
