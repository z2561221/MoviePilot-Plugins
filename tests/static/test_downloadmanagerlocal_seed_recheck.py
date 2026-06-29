from __future__ import annotations

import ast
import types
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
RECHECK_SOURCE = REPO / "plugins.v2" / "downloadmanagerlocal" / "modules" / "recheck.py"


def _load_recheck_functions():
    source = RECHECK_SOURCE.read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    required_names = {
        "process_seed_recheck_once",
        "seed_should_remove_missing",
        "seed_is_checking",
        "seed_is_ready",
        "seed_is_error",
        "seed_is_timeout",
    }
    funcs = [
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name in required_names
    ]
    present_names = {node.name for node in funcs}
    missing_names = required_names - present_names
    if missing_names:
        raise AssertionError(f"missing recheck functions: {sorted(missing_names)}")

    namespace = {
        "logger": types.SimpleNamespace(
            info=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
        ),
        "time": types.SimpleNamespace(time=lambda: 1000),
    }
    exec(compile(ast.Module(body=funcs, type_ignores=[]), "recheck_functions", "exec"), namespace)
    return namespace


class FakeTransmissionStatus:
    stopped = True
    checking = False


class FakeTransmissionTorrent:
    hashString = "tr-hash"
    status = FakeTransmissionStatus()
    percent_done = 1


class FakeDownloader:
    def __init__(self):
        self.started = []

    def get_torrents(self, ids=None):
        return [FakeTransmissionTorrent()], None

    def start_torrents(self, ids=None):
        self.started.extend(ids or [])


class FakePlugin:
    _seed_max_wait_minutes = 120

    def __init__(self, service):
        self._service = service

    def service_info(self, downloader):
        return self._service

    def get_hash(self, torrent, dl_type):
        return torrent.hashString


class DownloadManagerLocalSeedRecheckTest(unittest.TestCase):
    def test_transmission_ready_task_uses_torrent_percent_done_when_starting_seed(self) -> None:
        recheck = _load_recheck_functions()
        downloader = FakeDownloader()
        service = types.SimpleNamespace(
            type="transmission",
            instance=downloader,
        )
        plugin = FakePlugin(service)
        queue = {
            "tr-hash": {
                "hash": "tr-hash",
                "downloader": "TR",
                "source": "transfer",
                "created_at": 1000,
                "updated_at": 1000,
                "attempts": 0,
                "last_check": 0,
                "max_wait_minutes": 120,
            }
        }

        changed = recheck["process_seed_recheck_once"](plugin, queue)

        self.assertTrue(changed)
        self.assertEqual(downloader.started, ["tr-hash"])
        self.assertEqual(queue, {})


if __name__ == "__main__":
    unittest.main()
