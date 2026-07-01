import importlib.util
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _Logger:
    """用于屏蔽服务日志输出的测试 logger。"""

    def info(self, *args, **kwargs):
        """忽略 info 日志。"""
        pass


class _MemoryPlugin:
    """用于观察队列服务测试的内存版插件存储。"""

    def __init__(self):
        """初始化内存存储和观察期配置。"""
        self.data = {}
        self._observe_days = 2

    def get_data(self, key, **kwargs):
        """读取指定存储键。"""
        return self.data.get(key)

    def save_data(self, key, value):
        """保存指定存储键。"""
        self.data[key] = value


def _install_stubs():
    """安装观察服务测试所需的模块占位。"""
    app = types.ModuleType("app")
    app.__path__ = []
    log = types.ModuleType("app.log")
    log.logger = _Logger()
    package = types.ModuleType("doubancenter")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules.update({
        "app": app,
        "app.log": log,
        "doubancenter": package,
    })


def _load_service():
    """加载观察期服务模块。"""
    _install_stubs()
    module_name = "doubancenter.service.observation"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_DIR / "service" / "observation.py",
        submodule_search_locations=[str(PLUGIN_DIR / "service")],
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "doubancenter.service"
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _rank_history_reader(plugin, rank_key):
    """按榜单 key 读取内存历史。"""
    return plugin.data.get(f"rank_history_{rank_key}", [])


def _archive_record(plugin, source, record, source_name, dedupe=False):
    """把归档记录写入内存存储。"""
    archives = plugin.data.setdefault("archive_records", [])
    item = {
        "id": f"a{len(archives) + 1}",
        "source": source,
        "source_name": source_name,
        "title": record.get("title") or "",
        "record": dict(record),
    }
    archives.append(item)
    return item


observation_service = _load_service()


class _FakeMediaType:
    """用于订阅存在性检查测试的媒体类型枚举。"""

    MOVIE = "movie"
    TV = "tv"


class _FakeMeta:
    """用于订阅存在性检查测试的媒体元信息。"""

    def __init__(self, title):
        """初始化标题并保留后续填充字段。"""
        self.title = title
        self.year = ""
        self.type = None


class _FakeMediaChain:
    """用于记录媒体识别入参的假 MediaChain。"""

    def __init__(self, mediainfo=None, error=None):
        """初始化识别结果或异常。"""
        self.mediainfo = mediainfo
        self.error = error
        self.calls = []

    def recognize_media(self, meta, mtype):
        """记录识别调用并返回预设媒体信息。"""
        self.calls.append((meta, mtype))
        if self.error:
            raise self.error
        return self.mediainfo


class _FakeSubscribeChain:
    """用于记录订阅存在性检查入参的假 SubscribeChain。"""

    def __init__(self, exists_result=False):
        """初始化订阅存在性返回值。"""
        self.exists_result = exists_result
        self.calls = []

    def exists(self, mediainfo, meta):
        """记录订阅检查调用并返回预设结果。"""
        self.calls.append((mediainfo, meta))
        return self.exists_result


class DashboardObservationQueueServiceTest(unittest.TestCase):
    def test_observed_item_subscription_exists_resolves_movie_and_checks_subscription(self):
        """观察条目已有订阅检查会按电影类型识别媒体并调用订阅链。"""
        media_chain = _FakeMediaChain(mediainfo={"tmdb_id": 123})
        subscribe_chain = _FakeSubscribeChain(exists_result=True)

        result = observation_service.observed_item_subscription_exists(
            {"title": "测试电影", "year": 2024, "mtype": "movie"},
            rank_key="movie_weekly",
            media_chain_factory=lambda: media_chain,
            subscribe_chain_factory=lambda: subscribe_chain,
            media_type_enum=_FakeMediaType,
            meta_factory=_FakeMeta,
        )

        self.assertTrue(result)
        meta, media_type = media_chain.calls[0]
        self.assertEqual(meta.title, "测试电影")
        self.assertEqual(meta.year, "2024")
        self.assertEqual(meta.type, _FakeMediaType.MOVIE)
        self.assertEqual(media_type, _FakeMediaType.MOVIE)
        self.assertEqual(subscribe_chain.calls[0][0], {"tmdb_id": 123})

    def test_observed_item_subscription_exists_defaults_to_tv_and_returns_false_without_media(self):
        """观察条目无电影信号时按剧集识别，未识别到媒体则返回 False。"""
        media_chain = _FakeMediaChain(mediainfo=None)
        subscribe_chain = _FakeSubscribeChain(exists_result=True)

        result = observation_service.observed_item_subscription_exists(
            {"title": "测试剧集", "media_type": "tv"},
            media_chain_factory=lambda: media_chain,
            subscribe_chain_factory=lambda: subscribe_chain,
            media_type_enum=_FakeMediaType,
            meta_factory=_FakeMeta,
        )

        self.assertFalse(result)
        self.assertEqual(media_chain.calls[0][1], _FakeMediaType.TV)
        self.assertEqual(subscribe_chain.calls, [])

    def test_observed_item_subscription_exists_ignores_missing_title_and_chain_errors(self):
        """观察条目缺少标题或链路异常时返回 False。"""
        self.assertFalse(observation_service.observed_item_subscription_exists({}, meta_factory=_FakeMeta))

        result = observation_service.observed_item_subscription_exists(
            {"title": "异常条目"},
            media_chain_factory=lambda: _FakeMediaChain(error=RuntimeError("boom")),
            subscribe_chain_factory=lambda: _FakeSubscribeChain(exists_result=True),
            media_type_enum=_FakeMediaType,
            meta_factory=_FakeMeta,
        )

        self.assertFalse(result)

    def test_pending_observations_keeps_latest_items_and_archives_overflow(self):
        """观察队列超出详情上限时保留最新条目并归档旧条目。"""
        plugin = _MemoryPlugin()
        plugin.data["rank_history_tv_global"] = [
            {
                "title": f"观察{i}",
                "unique": f"rank:{i}",
                "first_seen": f"2026-06-2{i} 10:00:00",
                "observing": True,
            }
            for i in range(7)
        ]

        result = observation_service.pending_observations(
            plugin,
            ranks=[{"key": "tv_global", "name": "全球口碑"}],
            rank_history_reader=_rank_history_reader,
            item_existing_subscription_checker=lambda item: False,
            observed_subscription_exists_checker=lambda item, rank_key="": False,
            archive_record_callback=_archive_record,
            now=datetime(2026, 7, 1, 12, 0, 0),
            limit=5,
        )

        self.assertEqual([item["title"] for item in result["data"]], ["观察6", "观察5", "观察4", "观察3", "观察2"])
        self.assertFalse(plugin.data["rank_history_tv_global"][0]["observing"])
        self.assertTrue(plugin.data["rank_history_tv_global"][0]["observe_deleted"])
        self.assertEqual(plugin.data["rank_history_tv_global"][0]["observe_deleted_reason"], "超过详情页显示上限归档")
        archived = plugin.data["archive_records"]
        self.assertEqual([item["title"] for item in archived], ["观察1", "观察0"])
        self.assertEqual({item["source"] for item in archived}, {"observation"})

    def test_pending_observations_marks_existing_subscription_and_saves_history(self):
        """观察条目已有订阅时标记为 existing 并从待观察列表移除。"""
        plugin = _MemoryPlugin()
        plugin.data["rank_history_tv_global"] = [
            {
                "title": "已有订阅",
                "unique": "rank:existing",
                "first_seen": "2026-06-30 10:00:00",
                "observing": True,
            },
            {
                "title": "继续观察",
                "unique": "rank:keep",
                "first_seen": "2026-06-30 11:00:00",
                "observing": True,
            },
        ]

        result = observation_service.pending_observations(
            plugin,
            ranks=[{"key": "tv_global", "name": "全球口碑"}],
            rank_history_reader=_rank_history_reader,
            item_existing_subscription_checker=lambda item: False,
            observed_subscription_exists_checker=lambda item, rank_key="": item.get("unique") == "rank:existing",
            archive_record_callback=_archive_record,
            now=datetime(2026, 7, 1, 12, 0, 0),
            limit=5,
        )

        self.assertEqual([item["title"] for item in result["data"]], ["继续观察"])
        existing = plugin.data["rank_history_tv_global"][0]
        self.assertFalse(existing["observing"])
        self.assertTrue(existing["existing"])
        self.assertEqual(existing["existing_reason"], "subscribe")

    def test_delete_observation_marks_item_deleted_and_archives_record(self):
        """手动删除观察条目时标记忽略并写入归档。"""
        plugin = _MemoryPlugin()
        plugin.data["rank_history_tv_global"] = [
            {"title": "观察条目", "unique": "rank:delete", "observing": True}
        ]

        result = observation_service.delete_observation(
            plugin,
            unique="rank:delete",
            rank_key="tv_global",
            title="观察条目",
            ranks=[{"key": "tv_global", "name": "全球口碑"}],
            rank_history_reader=_rank_history_reader,
            archive_record_callback=_archive_record,
            now=datetime(2026, 7, 1, 12, 0, 0),
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["archive_id"], "a1")
        item = plugin.data["rank_history_tv_global"][0]
        self.assertFalse(item["observing"])
        self.assertTrue(item["observe_deleted"])
        self.assertEqual(plugin.data["archive_records"][0]["title"], "观察条目")


if __name__ == "__main__":
    unittest.main()
