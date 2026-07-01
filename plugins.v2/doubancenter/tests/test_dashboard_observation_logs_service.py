import importlib.util
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _Logger:
    def info(self, *args, **kwargs):
        pass


class _MemoryPlugin:
    """用于观察日志服务测试的内存版插件存储。"""

    def __init__(self, data=None):
        """初始化内存存储。"""
        self.data = data or {}

    def get_data(self, key, **kwargs):
        """读取指定存储键。"""
        return self.data.get(key)

    def save_data(self, key, value):
        """保存指定存储键。"""
        self.data[key] = value


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


def _install_stubs():
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


observation_service = _load_service()


class DashboardObservationLogsServiceTest(unittest.TestCase):
    def test_list_anti_cheat_logs_reconciles_archives_overflow_and_saves_logs(self):
        """观察日志列表会修正完成项、归档溢出并保存治理结果。"""
        plugin = _MemoryPlugin({
            "subscribe_records": [
                {"title": "done", "status": "success", "time": "2026-07-01 09:30:00"},
            ],
            "anti_cheat_logs": [
                {"title": "done", "reason": "观察期未满", "detail": "old", "time": "2026-07-01 09:00:00"},
                {"title": "黑旧", "reason": "黑名单关键词", "detail": "hit", "time": "2026-07-01 10:00:00"},
                {"title": "黑新", "reason": "黑名单关键词", "detail": "hit", "time": "2026-07-01 11:00:00"},
                {"title": "观察旧", "reason": "观察期未满", "detail": "wait", "time": "2026-07-01 12:00:00"},
                {"title": "观察新", "reason": "观察期未满", "detail": "wait", "time": "2026-07-01 13:00:00"},
            ]
        })

        result = observation_service.list_anti_cheat_logs(
            plugin,
            ranks=[],
            existing_subscription_checker=lambda item: False,
            limit=1,
        )

        logs = result["data"]
        self.assertEqual(
            [(item["reason"], item["title"]) for item in logs],
            [("黑名单关键词", "黑新"), ("观察期未满", "观察新")],
        )
        self.assertEqual(plugin.data["anti_cheat_logs"], logs)
        archives = [(item["source_name"], item["title"]) for item in plugin.data["archive_records"]]
        self.assertIn(("黑名拦截", "黑旧"), archives)
        self.assertIn(("观察日志", "观察旧"), archives)

    def test_delete_anti_cheat_log_archives_matching_log_and_saves_kept_logs(self):
        """删除观察日志时归档匹配记录并保存剩余日志。"""
        plugin = _MemoryPlugin({
            "anti_cheat_logs": [
                {"title": "保留", "reason": "TMDB评分过低", "time": "2026-06-21 10:00:00"},
                {"title": "删除", "reason": "观察期未满", "time": "2026-06-22 10:00:00"},
            ]
        })

        result = observation_service.delete_anti_cheat_log(
            plugin,
            time="2026-06-22 10:00:00",
            title="删除",
            reason="观察期未满",
            archive_record_callback=_archive_record,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["archive_id"], "a1")
        self.assertEqual([item["title"] for item in plugin.data["anti_cheat_logs"]], ["保留"])
        self.assertEqual(plugin.data["archive_records"][0]["source"], "anti_cheat_log")

    def test_dedupe_anti_cheat_logs_merges_counts_and_keeps_latest_time(self):
        logs = [
            {"title": "same", "reason": "observe", "detail": "d", "time": "2026-07-01 10:00:00"},
            {"title": "same", "reason": "observe", "detail": "d", "time": "2026-07-01 11:00:00", "count": 3},
            {"title": "other", "reason": "observe", "detail": "d", "time": "2026-07-01 12:00:00"},
            "bad",
        ]

        merged, changed = observation_service.dedupe_anti_cheat_logs(logs)

        self.assertTrue(changed)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["title"], "same")
        self.assertEqual(merged[0]["count"], 4)
        self.assertEqual(merged[0]["time"], "2026-07-01 11:00:00")

    def test_observation_completion_log_builds_record_from_subscribed_rank_item(self):
        item = {
            "title": "done",
            "first_seen": "2026-07-01 10:00:00",
            "subscribed": True,
            "subscribed_at": "2026-07-03 10:00:00",
            "link": "https://example.com/done",
        }
        rank = {"key": "tv_global", "name": "全球口碑"}

        record = observation_service.observation_completion_log(item, rank)

        self.assertEqual(record["title"], "done")
        self.assertEqual(record["reason"], "观察期完成")
        self.assertEqual(record["time"], "2026-07-03 10:00:00")
        self.assertEqual(record["rank_key"], "tv_global")
        self.assertIn("2026-07-01 10:00:00", record["detail"])

    def test_reconcile_anti_cheat_logs_removes_finished_wait_logs_and_appends_completion(self):
        logs = [
            {"title": "done", "reason": "观察期未满", "detail": "old", "time": "2026-07-01 10:00:00"},
            {"title": "keep", "reason": "观察期未满", "detail": "wait", "time": "2026-07-01 11:00:00"},
        ]
        ranks = [
            {
                "key": "tv_global",
                "name": "全球口碑",
                "history": [
                    {
                        "title": "done",
                        "first_seen": "2026-07-01 10:00:00",
                        "subscribed": True,
                        "subscribed_at": "2026-07-03 10:00:00",
                    }
                ],
            }
        ]

        reconciled, changed = observation_service.reconcile_anti_cheat_logs(
            logs,
            subscribe_records=[],
            ranks=ranks,
            archived_completion_titles=set(),
            existing_subscription_checker=lambda item: False,
        )

        self.assertTrue(changed)
        self.assertEqual([item["title"] for item in reconciled], ["keep", "done"])
        self.assertEqual(reconciled[-1]["reason"], "观察期完成")


if __name__ == "__main__":
    unittest.main()
