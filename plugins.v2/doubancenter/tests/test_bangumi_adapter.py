import importlib.util
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _Logger:
    def warning(self, *args, **kwargs):
        pass


def _install_stubs():
    app = types.ModuleType("app")
    app.__path__ = []

    core = types.ModuleType("app.core")
    core.__path__ = []

    config = types.ModuleType("app.core.config")
    config.settings = types.SimpleNamespace(PROXY="http://proxy")

    log = types.ModuleType("app.log")
    log.logger = _Logger()

    utils = types.ModuleType("app.utils")
    utils.__path__ = []

    http = types.ModuleType("app.utils.http")
    http.RequestUtils = type("RequestUtils", (), {})

    sys.modules.update(
        {
            "app": app,
            "app.core": core,
            "app.core.config": config,
            "app.log": log,
            "app.utils": utils,
            "app.utils.http": http,
        }
    )


def _load_bangumi_adapter():
    _install_stubs()
    spec = importlib.util.spec_from_file_location("doubancenter_adapter_bangumi", PLUGIN_DIR / "adapter" / "bangumi.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bangumi = _load_bangumi_adapter()


class BangumiAdapterTest(unittest.TestCase):
    def test_subject_fields_prefer_chinese_title_and_large_poster(self):
        subject = {
            "name": "Original Name",
            "name_cn": "中文名",
            "date": "2023-04-01",
            "images": {"medium": "medium.jpg", "large": "large.jpg"},
        }

        self.assertEqual(bangumi.subject_title(subject, fallback="fallback"), "中文名")
        self.assertEqual(bangumi.subject_year(subject), "2023")
        self.assertEqual(bangumi.subject_poster(subject), "large.jpg")

    def test_apply_subject_updates_entry_and_preserves_original_title(self):
        subject = {"id": 456, "name": "Original", "name_cn": "中文名", "date": "2022-01-01", "images": {"common": "poster.jpg"}}
        entry = {"title": "Original", "year": "", "poster": ""}

        bangumi.apply_subject(subject, entry, title="Original", bangumiid="456")

        self.assertEqual(entry["title"], "中文名")
        self.assertEqual(entry["original_title"], "Original")
        self.assertEqual(entry["year"], "2022")
        self.assertEqual(entry["bangumi_id"], 456)
        self.assertEqual(entry["bangumiid"], 456)
        self.assertEqual(entry["poster"], "poster.jpg")

    def test_subject_to_media_data_uses_bangumi_identity(self):
        subject = {"id": 789, "name": "Original", "summary": "简介", "date": "2021", "images": {"medium": "poster.jpg"}}

        data = bangumi.subject_to_media_data(subject, "电视剧", fallback_title="fallback")

        self.assertEqual(data["title"], "Original")
        self.assertEqual(data["type"], "电视剧")
        self.assertEqual(data["mediaid_prefix"], "bangumi")
        self.assertEqual(data["media_id"], 789)
        self.assertEqual(data["poster_path"], "poster.jpg")
        self.assertEqual(data["overview"], "简介")

    def test_extract_subject_id_supports_fields_and_links(self):
        self.assertEqual(bangumi.extract_subject_id({"bangumi_id": 123}), "123")
        self.assertEqual(bangumi.extract_subject_id({"bangumiid": "234"}), "234")
        self.assertEqual(bangumi.extract_subject_id({"rank_key": "bangumi", "douban_id": "345"}), "345")
        self.assertEqual(bangumi.extract_subject_id({"link": "https://bgm.tv/subject/456"}), "456")
        self.assertEqual(bangumi.extract_subject_id({"link": "https://bangumi.tv/subject/567"}), "567")
        self.assertIsNone(bangumi.extract_subject_id({"link": "https://example.com"}))

    def test_has_cjk_text_detects_chinese_characters(self):
        self.assertTrue(bangumi.has_cjk_text("中文名"))
        self.assertFalse(bangumi.has_cjk_text("Original Name"))

    def test_fetch_subject_uses_injected_request_and_proxy(self):
        calls = []

        class Response:
            def json(self):
                return {"id": 123, "name": "Subject"}

        class Request:
            def __init__(self, headers=None, proxies=None):
                calls.append(("init", headers, proxies))

            def get_res(self, url):
                calls.append(("get", url))
                return Response()

        plugin = types.SimpleNamespace(_proxy=True)

        subject = bangumi.fetch_subject(
            plugin,
            "123",
            request_utils_cls=Request,
            settings_obj=types.SimpleNamespace(PROXY="http://proxy"),
        )

        self.assertEqual(subject, {"id": 123, "name": "Subject"})
        self.assertEqual(calls[0][0], "init")
        self.assertIn("MoviePilot-DoubanCenter", calls[0][1]["User-Agent"])
        self.assertEqual(calls[0][2], "http://proxy")
        self.assertEqual(calls[1], ("get", "https://api.bgm.tv/v0/subjects/123"))


if __name__ == "__main__":
    unittest.main()
