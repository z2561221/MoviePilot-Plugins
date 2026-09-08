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
