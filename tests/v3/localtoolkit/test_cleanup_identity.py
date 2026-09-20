"""真实适配器必须拒绝宿主对失效用户名的管理员回退。"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.plugins.localtoolkit.adapter.media_server import MediaServerCleanupAdapter

from .test_cleanup_run import build_module
from .test_cleanup_verification import Response


def make_adapter(users):
    instance = SimpleNamespace(_host="http://media.invalid/", _apikey="test-only",
                               get_user=Mock(return_value="admin-id"))
    service = SimpleNamespace(instance=instance, type="emby")
    helper = SimpleNamespace(get_service=lambda **_kw: service,
                             get_services=lambda **_kw: {"emby": service})
    chain = SimpleNamespace(librarys=Mock())
    adapter = MediaServerCleanupAdapter(helper=helper, chain=chain)
    calls = []

    def request(url, _params):
        calls.append(url)
        if url.endswith("/Users"):
            if isinstance(users, Exception):
                raise users
            return users
        if url.endswith("/Views"):
            return Response(200, {"Items": [{"Id": "movies", "Name": "Movies"}], "TotalRecordCount": 1})
        return Response(200, {"Id": "a", "ParentId": "movies", "DateCreated": "2020-01-01",
                              "UserData": {"Played": True, "IsFavorite": False}})

    adapter._request_utils = lambda **_kw: SimpleNamespace(get_res=request)
    adapter.delete_item = Mock(return_value=True)
    return adapter, instance, calls


@pytest.mark.parametrize("users", [
    Response(200, [{"Name": "admin", "Id": "admin-id"}]),
    Response(200, [{"Name": "renamed", "Id": "viewer-id"}]),
    Response(200, [{"Name": "viewer", "Id": "one"}, {"Name": "viewer", "Id": "two"}]),
    Response(403), TimeoutError("user list unavailable"),
])
def test_invalid_explicit_user_keeps_scan_plan_and_cannot_delete(users):
    module, plugin, _fake = build_module({"a": [False]}, selected_user="viewer", cycle_cooldown_minutes=0)
    adapter, instance, calls = make_adapter(users)
    module.adapter = adapter
    original = deepcopy(plugin.data["library_cleanup_plan"])
    assert module.scan_plan()["success"] is False
    assert plugin.data["library_cleanup_plan"] == original
    assert module.run_once()["unknown_count"] == 1
    assert len(plugin.data["library_cleanup_plan"]["items"]) == 1
    adapter.delete_item.assert_not_called()
    instance.get_user.assert_not_called()
    assert all(url.endswith("/Users") for url in calls)


def test_library_query_uses_exact_user_id_without_fallback_capable_chain():
    adapter, instance, calls = make_adapter(Response(200, [{"Name": "viewer", "Id": "viewer-id"}]))
    service = adapter.helper.get_service(name="emby")
    assert adapter._libraries("emby", service, "viewer", strict=True)[0]["Id"] == "movies"
    assert calls[-1].endswith("/Users/viewer-id/Views")
    adapter.chain.librarys.assert_not_called()
    instance.get_user.assert_not_called()


def test_same_username_cannot_change_user_id_mid_operation():
    adapter, _instance, _calls = make_adapter(Response(200, []))
    users = iter(["first", "replacement", "replacement"])
    adapter._users_by_http = lambda *_args: [{"Name": "viewer", "Id": next(users)}]
    instance = adapter.helper.get_service().instance
    with adapter.user_scope():
        assert adapter._resolve_user_id(instance, "viewer", "emby") == "first"
        assert adapter._resolve_user_id(instance, "viewer", "emby") is None
    with adapter.user_scope():
        assert adapter._resolve_user_id(instance, "viewer", "emby") == "replacement"


def test_unselected_user_preserves_host_default_resolution():
    adapter, instance, calls = make_adapter(Response(200, []))
    assert adapter._resolve_user_id(instance) == "admin-id"
    instance.get_user.assert_called_once_with(None)
    assert not calls
