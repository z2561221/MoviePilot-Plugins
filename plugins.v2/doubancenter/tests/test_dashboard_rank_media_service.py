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
    def __init__(self, title="测试剧集", year="2026", tmdb_id=24680, bangumi_id=None):
        self.title = title
        self.year = year
        self.type = _MediaType.TV
        self.tmdb_id = tmdb_id
        self.douban_id = None
        self.bangumi_id = bangumi_id
        self.overview = "简介"

    def get_poster_image(self):
        return "poster.jpg"


def _install_stubs(media_chain_cls=None):
    app = types.ModuleType("app")
    app.__path__ = []
    chain = types.ModuleType("app.chain")
    chain.__path__ = []
    media = types.ModuleType("app.chain.media")
    media.MediaChain = media_chain_cls or type("MediaChain", (), {})
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
            "app.core": core,
            "app.core.metainfo": metainfo,
            "app.schemas": schemas,
            "app.schemas.types": schema_types,
            "doubancenter": package,
            "doubancenter.service": service_package,
        }
    )


def _load_service(media_chain_cls=None):
    _install_stubs(media_chain_cls=media_chain_cls)
    module_name = "doubancenter.service.dashboard_rank_media"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_DIR / "service" / "dashboard_rank_media.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DashboardRankMediaServiceTest(unittest.TestCase):
    def test_resolve_media_from_rank_uses_media_chain_result(self):
        calls = []

        class MediaChain:
            def recognize_media(self, meta, mtype):
                calls.append((meta.title, meta.year, mtype))
                return _MediaInfo(title=meta.title, year=meta.year, tmdb_id=24680)

        service = _load_service(media_chain_cls=MediaChain)

        result = service.resolve_media_from_rank(object(), "tv", "手动剧集", "2026")

        self.assertTrue(result["success"])
        self.assertEqual(calls, [("手动剧集", "2026", _MediaType.TV)])
        self.assertEqual(result["data"]["title"], "手动剧集")
        self.assertEqual(result["data"]["type"], "电视剧")
        self.assertEqual(result["data"]["tmdb_id"], 24680)
        self.assertEqual(result["data"]["poster_path"], "poster.jpg")
        self.assertEqual(result["data"]["source"], "themoviedb")

    def test_resolve_media_from_rank_falls_back_to_tmdb_id(self):
        class MediaChain:
            def recognize_media(self, meta, mtype):
                return None

        service = _load_service(media_chain_cls=MediaChain)

        result = service.resolve_media_from_rank(object(), "tv", "Japanese Anime", "", tmdb_id=67890)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["title"], "Japanese Anime")
        self.assertEqual(result["data"]["tmdb_id"], 67890)
        self.assertEqual(result["data"]["mediaid_prefix"], "tmdb")
        self.assertEqual(result["data"]["media_id"], 67890)
        self.assertEqual(result["data"]["source"], "themoviedb")

    def test_resolve_media_from_rank_uses_bangumi_subject_when_chain_misses(self):
        class MediaChain:
            def recognize_media(self, meta, mtype, bangumiid=None):
                return None

        service = _load_service(media_chain_cls=MediaChain)

        result = service.resolve_media_from_rank(
            object(),
            "tv",
            "Japanese Anime",
            "",
            bangumi_id=547888,
            bangumi_subject_fetcher=lambda plugin, bangumiid: {"id": int(bangumiid), "name_cn": "中文动画"},
            bangumi_subject_converter=lambda subject, media_type_name, fallback_title="", bangumiid=None: {
                "title": subject["name_cn"],
                "name": subject["name_cn"],
                "year": "2026",
                "type": media_type_name,
                "bangumi_id": bangumiid,
                "bangumiid": bangumiid,
                "mediaid_prefix": "bangumi",
                "media_id": bangumiid,
                "poster_path": "bangumi.jpg",
                "source": "bangumi",
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["title"], "中文动画")
        self.assertEqual(result["data"]["type"], "电视剧")
        self.assertEqual(result["data"]["bangumi_id"], 547888)
        self.assertEqual(result["data"]["mediaid_prefix"], "bangumi")


if __name__ == "__main__":
    unittest.main()
