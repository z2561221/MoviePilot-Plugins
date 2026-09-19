from types import SimpleNamespace

import pytest
from app.plugins.localtoolkit.adapter.media_server import MediaServerCleanupAdapter
from app.plugins.localtoolkit.model.library_cleanup import CleanupCandidate


class Response:
    def __init__(self, status, data=None):
        self.status_code = status
        self.data = data

    def __bool__(self):
        return self.status_code < 400

    def json(self):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data


@pytest.mark.parametrize(("response", "expected"), [
    (Response(200, {"Id": "123"}), True),
    (Response(404), False),
    (Response(401), None),
    (Response(403), None),
    (Response(500), None),
    (Response(200, {"Id": "different"}), None),
    (Response(200, {}), None),
    (Response(200, ValueError("invalid JSON")), None),
    (None, None),
    (TimeoutError("timed out"), None),
])
def test_only_explicit_not_found_confirms_removal(response, expected):
    requests = []
    instance = SimpleNamespace(_host="http://media.invalid/", _apikey="test-only", get_user=lambda _user: "viewer-id")
    helper = SimpleNamespace(get_service=lambda **_kwargs: SimpleNamespace(instance=instance, type="emby"))
    adapter = MediaServerCleanupAdapter(helper=helper, chain=SimpleNamespace())

    def get_res(url, params):
        requests.append((url, params))
        if isinstance(response, Exception):
            raise response
        return response

    adapter._request_utils = lambda **_kwargs: SimpleNamespace(get_res=get_res)
    candidate = CleanupCandidate(movie_id="123", server="media")
    assert adapter.item_exists(candidate, "viewer") is expected
    assert requests == [("http://media.invalid/emby/Users/viewer-id/Items/123", {"api_key": "test-only"})]


def test_missing_server_or_user_is_unknown_without_making_request():
    helper = SimpleNamespace(get_service=lambda **_kwargs: None)
    adapter = MediaServerCleanupAdapter(helper=helper, chain=SimpleNamespace())
    adapter._request_utils = lambda **_kwargs: pytest.fail("must not request an unresolved server")
    assert adapter.item_exists(CleanupCandidate(movie_id="123", server="missing")) is None
    assert adapter.item_exists(CleanupCandidate(movie_id="123")) is None


def test_precheck_reads_fresh_user_data_instead_of_old_candidate_values():
    """删除前复核使用用户原始详情，不回填过时的收藏和观看值。"""
    requests = []
    instance = SimpleNamespace(_host="http://media.invalid/", _apikey="test-only", get_user=lambda user: "viewer-id")
    helper = SimpleNamespace(get_service=lambda **_kwargs: SimpleNamespace(instance=instance, type="jellyfin"))
    adapter = MediaServerCleanupAdapter(helper=helper, chain=SimpleNamespace())

    def get_res(url, params):
        requests.append((url, params))
        return Response(200, {"Id": "123", "Name": "最新名称", "UserData": {"IsFavorite": True}})

    adapter._request_utils = lambda **_kwargs: SimpleNamespace(get_res=get_res)
    original = CleanupCandidate(movie_id="123", server="media", favorite=False, played=True, date_created="2020-01-01")
    exists, fresh = adapter.refresh_candidate(original, "viewer")
    assert exists is True and fresh.favorite is True
    assert fresh.played is None and not fresh.date_created
    assert requests[0][0] == "http://media.invalid/Users/viewer-id/Items/123"
    assert requests[0][1]["Fields"] == "ProviderIds,DateCreated,UserData,ParentId"


@pytest.mark.parametrize("response", [Response(403), Response(500), Response(200, {"Id": "other"}), None])
def test_precheck_never_returns_a_candidate_for_unknown_identity_or_read_errors(response):
    """权限、网络及身份异常不能变成可删除的旧快照。"""
    instance = SimpleNamespace(_host="http://media.invalid/", _apikey="test-only", get_user=lambda _user: "viewer-id")
    helper = SimpleNamespace(get_service=lambda **_kwargs: SimpleNamespace(instance=instance, type="emby"))
    adapter = MediaServerCleanupAdapter(helper=helper, chain=SimpleNamespace())
    adapter._request_utils = lambda **_kwargs: SimpleNamespace(get_res=lambda *_args: response)
    assert adapter.refresh_candidate(CleanupCandidate(movie_id="123", server="media"), "viewer") == (None, None)


def test_full_scan_reads_all_pages_and_propagates_incomplete_page_failures():
    """总量尚未读完时继续分页，后续失败不能返回半份候选。"""
    instance = SimpleNamespace(_host="http://media.invalid/", _apikey="test-only", get_user=lambda _user: "viewer-id")
    helper = SimpleNamespace(get_service=lambda **_kwargs: SimpleNamespace(instance=instance, type="emby"))
    adapter = MediaServerCleanupAdapter(helper=helper, chain=SimpleNamespace())
    calls = []
    responses = [Response(200, {"Items": [{"Id": "1"}], "TotalRecordCount": 2}),
                 Response(200, {"Items": [{"Id": "2"}], "TotalRecordCount": 2})]

    def get_res(_url, params):
        calls.append(params["StartIndex"])
        return responses.pop(0)

    adapter._request_utils = lambda **_kwargs: SimpleNamespace(get_res=get_res)
    assert [item["Id"] for item in adapter._library_items_by_http("media", "library")] == ["1", "2"]
    assert calls == [0, 1]
    responses[:] = [Response(200, {"Items": [{"Id": "1"}], "TotalRecordCount": 2}), Response(503)]
    with pytest.raises(RuntimeError):
        adapter._library_items_by_http("media", "library")


def test_full_scan_rejects_a_repeated_page_instead_of_looping_forever():
    """服务端忽略偏移量时失败并保留原计划。"""
    instance = SimpleNamespace(_host="http://media.invalid/", _apikey="test-only", get_user=lambda _user: "viewer-id")
    helper = SimpleNamespace(get_service=lambda **_kwargs: SimpleNamespace(instance=instance, type="emby"))
    adapter = MediaServerCleanupAdapter(helper=helper, chain=SimpleNamespace())
    adapter._request_utils = lambda **_kwargs: SimpleNamespace(
        get_res=lambda *_args: Response(200, {"Items": [{"Id": "1"}], "TotalRecordCount": 2}),
    )
    with pytest.raises(ValueError, match="重复"):
        adapter._library_items_by_http("media", "library")


@pytest.mark.parametrize(("ancestors", "expected_library"), [
    (Response(200, [{"Id": "library"}]), "library"),
    (Response(200, [{"Id": "other-library"}]), "nested-folder"),
    (Response(403), None),
])
def test_precheck_resolves_nested_or_moved_library_without_listing_inventory(ancestors, expected_library):
    """只读取当前条目的祖先链，嵌套目录保留原归属，移库或无权限分别处理。"""
    instance = SimpleNamespace(_host="http://media.invalid/", _apikey="test-only", get_user=lambda _user: "viewer-id")
    helper = SimpleNamespace(get_service=lambda **_kwargs: SimpleNamespace(instance=instance, type="emby"))
    adapter = MediaServerCleanupAdapter(helper=helper, chain=SimpleNamespace())
    calls = []

    def get_res(url, _params):
        calls.append(url)
        if url.endswith("/Ancestors"):
            return ancestors
        return Response(200, {"Id": "123", "ParentId": "nested-folder"})

    adapter._request_utils = lambda **_kwargs: SimpleNamespace(get_res=get_res)
    exists, fresh = adapter.refresh_candidate(CleanupCandidate(movie_id="123", server="media", library_id="library"), "viewer")
    assert len(calls) == 2 and calls[-1].endswith("/Items/123/Ancestors")
    if expected_library is None:
        assert exists is None and fresh is None
    else:
        assert exists is True and fresh.library_id == expected_library
