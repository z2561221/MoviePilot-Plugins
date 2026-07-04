import importlib
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]


class _Logger:
    def info(self, *args, **kwargs):
        """测试桩记录普通日志时不执行任何输出。"""
        pass

    def warning(self, *args, **kwargs):
        """测试桩记录警告日志时不执行任何输出。"""
        pass

    def error(self, *args, **kwargs):
        """测试桩记录错误日志时不执行任何输出。"""
        pass


def _install_stubs():
    app = types.ModuleType("app")
    app.__path__ = []

    log = types.ModuleType("app.log")
    log.logger = _Logger()

    sys.modules.update({"app": app, "app.log": log})


def _prepare_imports():
    _install_stubs()
    for name in list(sys.modules):
        if name == "downloadmanagerlocal" or name.startswith("downloadmanagerlocal."):
            sys.modules.pop(name)
    package = types.ModuleType("downloadmanagerlocal")
    package.__path__ = [str(PLUGIN_DIR)]
    sys.modules["downloadmanagerlocal"] = package


class DownloadManagerSafetyTest(unittest.TestCase):
    """验证下载中心插件的安全兜底工具行为。"""

    def test_state_is_true_for_iyuu_only_mode(self):
        """仅启用 IYUU 辅种能力时插件应保持启用状态。"""
        _prepare_imports()
        config = importlib.import_module("downloadmanagerlocal.utils.config")
        plugin = types.SimpleNamespace(
            _enabled=True,
            _transfer_enabled=False,
            _fromdownloader="",
            _todownloader="",
            _fromtorrentpath="",
            _iyuu_enabled=True,
            _iyuu_token="token",
            _iyuu_downloaders=["qb"],
        )

        self.assertTrue(config.is_plugin_active(plugin))

    def test_state_is_false_without_any_active_capability(self):
        """没有转移或 IYUU 可运行能力时插件应视为未启用。"""
        _prepare_imports()
        config = importlib.import_module("downloadmanagerlocal.utils.config")
        plugin = types.SimpleNamespace(
            _enabled=True,
            _transfer_enabled=False,
            _fromdownloader="",
            _todownloader="",
            _fromtorrentpath="",
            _iyuu_enabled=False,
            _iyuu_token="",
            _iyuu_downloaders=[],
        )

        self.assertFalse(config.is_plugin_active(plugin))

    def test_mask_sensitive_url_hides_private_query_values(self):
        """敏感 URL 参数应被脱敏但普通参数保留。"""
        _prepare_imports()
        sensitive = importlib.import_module("downloadmanagerlocal.utils.sensitive")
        url = "https://pt.example/download.php?id=1&passkey=abc&authkey=def&uid=42&token=xyz"

        masked = sensitive.mask_sensitive_url(url)

        self.assertIn("id=1", masked)
        self.assertNotIn("abc", masked)
        self.assertNotIn("def", masked)
        self.assertNotIn("42", masked)
        self.assertNotIn("xyz", masked)
        self.assertIn("passkey=***", masked)

    def test_recheck_marks_last_check_update_as_changed(self):
        """种子复查更新 last_check 后应返回队列已变化。"""
        _prepare_imports()
        recheck = importlib.import_module("downloadmanagerlocal.modules.recheck")

        class _Service:
            type = "qbittorrent"

            class instance:
                """模拟下载器实例提供种子查询接口。"""

                @staticmethod
                def get_torrents(ids=None):
                    """返回一条可继续做种的测试种子。"""
                    return ([{"hash": "abc", "state": "stalledUP"}], None)

        plugin = types.SimpleNamespace(
            service_info=lambda name: _Service(),
            get_hash=lambda torrent, dl_type: torrent.get("hash"),
            _seed_max_wait_minutes=120,
        )
        queue = {
            "abc": {
                "hash": "abc",
                "downloader": "qb",
                "created_at": 9999999999,
                "attempts": 0,
                "last_check": 0,
            }
        }

        changed = recheck.process_seed_recheck_once(plugin, queue)

        self.assertTrue(changed)
        self.assertGreater(queue["abc"]["last_check"], 0)


if __name__ == "__main__":
    unittest.main()
