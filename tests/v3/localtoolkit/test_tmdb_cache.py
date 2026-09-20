"""TMDB 缓存查询失败时的安全结果回归。"""

from types import SimpleNamespace

from app.plugins.localtoolkit.service.tmdb_cache import TmdbCacheModule


class FakePlugin:
    def __init__(self):
        self.data = {}

    def get_data(self, key):
        return self.data.get(key)

    def save_data(self, key, value):
        self.data[key] = value


def test_key_query_failure_is_not_reported_as_zero_success(monkeypatch):
    plugin = FakePlugin()
    module = TmdbCacheModule(plugin)
    module.load_config({"notify": False})
    deleted = []
    client = SimpleNamespace(
        keys=lambda _pattern: (_ for _ in ()).throw(TimeoutError("keys unavailable")),
        delete=lambda *_keys: deleted.append(True),
    )
    monkeypatch.setattr(module, "_redis", lambda: client)
    result = module.run_once()
    assert result["success"] is False
    assert not deleted
    assert plugin.data["tool_history"][0]["status"] == "failed"


def test_cleanup_uses_one_client_for_before_delete_and_after_status(monkeypatch):
    plugin = FakePlugin()
    module = TmdbCacheModule(plugin)
    module.load_config({"notify": False})
    clients = []

    class Client:
        def __init__(self):
            self.calls = []

        def keys(self, pattern):
            self.calls.append(("keys", pattern))
            return [b"a"]

        def dump(self, key):
            self.calls.append(("dump", key))
            return b"data"

        def delete(self, *keys):
            self.calls.append(("delete", keys))
            return len(keys)

    client = Client()
    clients.append(client)
    monkeypatch.setattr(module, "_redis", lambda: client)
    result = module.run_once()
    assert result["success"] is True
    assert [call[0] for call in client.calls].count("delete") == 1
    assert len(clients) == 1
