"""缓存释放审查只使用内存依赖，不访问真实媒体库或业务队列。"""

from types import SimpleNamespace

import pytest
from app.plugins.doubancenter import DoubanCenter
from app.plugins.doubancenter.adapter import folio_library
from app.plugins.doubancenter.service import lifecycle


@pytest.mark.parametrize("stop_during_read", [False, True])
def test_season_cache_publication_respects_the_started_generation(monkeypatch, stop_during_read):
    plugin = object.__new__(DoubanCenter)
    lifecycle.start(plugin)
    service = SimpleNamespace(name="test", config=SimpleNamespace(config={"host": "http://library.invalid/"}))
    monkeypatch.setattr(folio_library, "MediaServerHelper", lambda: SimpleNamespace(get_services=lambda **kwargs: {"test": service}))

    def find(*args):
        if stop_during_read:
            lifecycle.start(plugin)
        return service, {"Id": "series"}

    monkeypatch.setattr(folio_library, "_find_series", find)
    monkeypatch.setattr(folio_library, "_get_json", lambda *args: {
        "Items": [{"Id": "season", "Type": "Season", "SeriesId": "series", "IndexNumber": 2}], "TotalRecordCount": 1,
    })
    monkeypatch.setattr(folio_library, "_season_episodes", lambda *args: [
        {"IndexNumber": 1, "PremiereDate": "2026-01-01"},
    ])
    result = folio_library.load_season(plugin, {"media_source": "themoviedb", "media_id": "123", "season": 2})
    assert result["season"] == 2
    assert len(plugin._folio_library_season_cache) == (0 if stop_during_read else 1)
