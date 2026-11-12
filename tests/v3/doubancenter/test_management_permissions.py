"""共享归档与维护路由须在副作用前执行管理授权。"""

from copy import deepcopy
from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.plugins.doubancenter import DoubanCenter
from app.plugins.doubancenter.controller.security import require_admin
from app.sdk.security import verify_token


def _app(admin):
    """实际插件路由绑定内存数据，避免真实业务数据被修改。"""
    plugin = object.__new__(DoubanCenter)
    state = {"archive_records": [{"id": "saved", "source": "subscribe_history", "record": {"title": "sample"}}]}
    writes = []
    plugin.get_data = lambda key: deepcopy(state.get(key))
    def save(key, value):
        writes.append(key)
        state[key] = deepcopy(value)
    plugin.save_data = save
    def identity():
        if admin is None:
            raise HTTPException(401, "Not authenticated")
        return SimpleNamespace(super_user=admin)
    app = FastAPI()
    app.dependency_overrides[verify_token] = identity
    routes = plugin.get_api()
    for route in routes:
        app.add_api_route(**{k: v for k, v in route.items() if k != "auth"})
    return app, routes, state, writes


@pytest.mark.parametrize("admin,expected", [(False, 403), (None, 401)])
def test_maintenance_rejects_before_write(admin, expected):
    """所有HTTP维护入口都拒绝普通或未认证身份，原记录完整。"""
    app, routes, state, writes = _app(admin)
    before = deepcopy(state)
    with TestClient(app) as client:
        for route in routes:
            if "POST" not in route["methods"] or route["path"] == "/subscribe":
                continue
            assert any(item.dependency is require_admin for item in route["dependencies"])
            result = client.post(route["path"], params={"archive_id": "saved"}, json={})
            assert result.status_code == expected, (route["path"], result.text)
    assert state == before
    assert writes == []


def test_admin_can_delete_and_permissions_are_truthful():
    """管理员仍可执行真实删除，普通用户只读权限返回false。"""
    app, _, state, writes = _app(True)
    with TestClient(app) as client:
        assert client.get("/permissions").json()["data"]["can_manage"] is True
        result = client.post("/delete_archive", params={"archive_id": "saved"})
    assert result.status_code == 200 and result.json()["success"] is True
    assert state["archive_records"] == [] and writes
    app, _, _, _ = _app(False)
    with TestClient(app) as client:
        assert client.get("/permissions").json()["data"]["can_manage"] is False
