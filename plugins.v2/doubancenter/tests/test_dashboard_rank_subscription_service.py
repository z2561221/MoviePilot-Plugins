import importlib.util
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _MediaType:
    MOVIE = "movie"
    TV = "tv"


class _MetaInfo:
    def __init__(self, title):
        self.title = title
        self.year = None
        self.type = None
        self.begin_season = None


class _MediaInfo:
    def __init__(self, title="测试电影", year="2026", mtype=_MediaType.MOVIE, tmdb_id=24680, bangumi_id=None):
        self.title = title
        self.year = year
        self.type = mtype
        self.tmdb_id = tmdb_id
        self.bangumi_id = bangumi_id


def _install_stubs(media_chain_cls=None, subscribe_chain_cls=None):
    app = types.ModuleType("app")
    app.__path__ = []
    chain = types.ModuleType("app.chain")
    chain.__path__ = []
    media = types.ModuleType("app.chain.media")
    media.MediaChain = media_chain_cls or type("MediaChain", (), {})
    subscribe = types.ModuleType("app.chain.subscribe")
    subscribe.SubscribeChain = subscribe_chain_cls or type("SubscribeChain", (), {})
    core = types.ModuleType("app.core")
    core.__path__ = []
    metainfo = types.ModuleType("app.core.metainfo")
    metainfo.MetaInfo = _MetaInfo
    schemas = types.ModuleType("app.schemas")
    schemas.__path__ = []
    schema_types = types.ModuleType("app.schemas.types")
    schema_types.MediaType = _MediaType
    package = types.ModuleType("doubancenter")
    package.__path__ = [str(PLUGIN_DIR)]
    service_package = types.ModuleType("doubancenter.service")
    service_package.__path__ = [str(PLUGIN_DIR / "service")]
    sys.modules.update(
        {
            "app": app,
            "app.chain": chain,
            "app.chain.media": media,
            "app.chain.subscribe": subscribe,
            "app.core": core,
            "app.core.metainfo": metainfo,
            "app.schemas": schemas,
            "app.schemas.types": schema_types,
            "doubancenter": package,
            "doubancenter.service": service_package,
        }
    )


def _load_service(media_chain_cls=None, subscribe_chain_cls=None):
    _install_stubs(media_chain_cls=media_chain_cls, subscribe_chain_cls=subscribe_chain_cls)
    module_name = "doubancenter.service.dashboard_rank_subscription"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_DIR / "service" / "dashboard_rank_subscription.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DashboardRankSubscriptionServiceTest(unittest.TestCase):
    def test_subscribe_from_rank_uses_recognized_media_and_default_add_args(self):
        calls = []
        captured = {}

        class MediaChain:
            def recognize_media(self, meta, mtype, tmdbid=None):
                calls.append((meta.title, meta.year, mtype, tmdbid))
                return _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=tmdbid or 24680)

        class SubscribeChain:
            def exists(self, mediainfo, meta):
                return False

            def add(self, **kwargs):
                captured.update(kwargs)
                return 1, ""

        service = _load_service(media_chain_cls=MediaChain, subscribe_chain_cls=SubscribeChain)

        result = service.subscribe_from_rank(object(), None, "movie", "测试电影", "2026")

        self.assertTrue(result["success"])
        self.assertEqual(calls, [("测试电影", "2026", _MediaType.MOVIE, None)])
        self.assertEqual(captured["title"], "测试电影")
        self.assertEqual(captured["year"], "2026")
        self.assertEqual(captured["mtype"], _MediaType.MOVIE)
        self.assertEqual(captured["tmdbid"], 24680)
        self.assertIsNone(captured["season"])
        self.assertEqual(captured["username"], "豆瓣中心")

    def test_subscribe_from_rank_stops_when_subscription_exists(self):
        add_called = False

        class MediaChain:
            def recognize_media(self, meta, mtype, tmdbid=None):
                return _MediaInfo(title=meta.title, year=meta.year, mtype=mtype, tmdb_id=24680)

        class SubscribeChain:
            def exists(self, mediainfo, meta):
                return True

            def add(self, **kwargs):
                nonlocal add_called
                add_called = True
                return 1, ""

        service = _load_service(media_chain_cls=MediaChain, subscribe_chain_cls=SubscribeChain)

        result = service.subscribe_from_rank(object(), None, "movie", "测试电影", "2026")

        self.assertFalse(result["success"])
        self.assertFalse(add_called)
        self.assertEqual(result["message"], "已订阅")

    def test_subscribe_from_rank_uses_bangumi_subject_without_tmdbid(self):
        captured = {}

        class MediaChain:
            def recognize_media(self, meta, mtype, bangumiid=None):
                return None

        class SubscribeChain:
            def add(self, **kwargs):
                captured.update(kwargs)
                return 1, ""

        service = _load_service(media_chain_cls=MediaChain, subscribe_chain_cls=SubscribeChain)

        result = service.subscribe_from_rank(
            object(),
            None,
            "tv",
            "Japanese Anime",
            "",
            bangumi_id=547888,
            bangumi_subject_fetcher=lambda plugin, bangumiid: {"id": int(bangumiid), "name_cn": "中文动画", "date": "2026-04-08"},
            bangumi_subject_title=lambda subject, fallback="": subject.get("name_cn") or fallback,
            bangumi_subject_year=lambda subject, fallback="": subject.get("date", "")[:4] or fallback,
        )

        self.assertTrue(result["success"])
        self.assertEqual(captured["title"], "中文动画")
        self.assertEqual(captured["year"], "2026")
        self.assertEqual(captured["mtype"], _MediaType.TV)
        self.assertIsNone(captured["tmdbid"])
        self.assertEqual(captured["bangumiid"], 547888)


if __name__ == "__main__":
    unittest.main()
