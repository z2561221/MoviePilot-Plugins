"""验证下载器补全标签的后台任务接口和状态管理。"""

from __future__ import annotations

import importlib
import threading
from pathlib import Path

from app.sdk import scheduler

tag_completion = importlib.import_module("app.plugins.downloadmanagerlocal.service.tag_completion")


class FakeTagCompletionPlugin:
    """模拟标签任务所需的插件持久化与实例接口。"""

    def __init__(self, data_path: Path):
        """初始化隔离的数据目录和实例锁。"""
        self.data_path = data_path
        self.saved = {}
        self._tag_completion_lock = threading.RLock()
        self._tag_completion_stop_event = None
        self._tag_completion_job_id = None

    def get_data(self, key=None):
        """读取插件键值状态。"""
        if key is None:
            return dict(self.saved)
        return self.saved.get(key)

    def save_data(self, key, value):
        """保存插件键值状态。"""
        self.saved[key] = value

    def get_data_path(self):
        """返回隔离的插件数据目录。"""
        self.data_path.mkdir(parents=True, exist_ok=True)
        return self.data_path

    def _run_tag_completion_task(self, task_id):
        """调用真实任务入口以验证调度器绑定方法。"""
        tag_completion.run_tag_completion_task(self, task_id)


def _capture_scheduler(monkeypatch):
    """替换宿主调度器并返回待运行任务列表。"""
    jobs = []

    def add_job(*args, **kwargs):
        jobs.append((args[0], args[1], args[2], kwargs.get("func_kwargs") or {}))
        return True

    monkeypatch.setattr(scheduler, "add_plugin_once_job", add_job)
    monkeypatch.setattr(scheduler, "remove_plugin_once_job", lambda *_args: None)
    return jobs


def test_scan_submission_is_fast_idempotent_and_result_is_separate(tmp_path, monkeypatch):
    """提交只登记任务，状态轻量，重复请求复用同一个扫描。"""
    plugin = FakeTagCompletionPlugin(tmp_path)
    jobs = _capture_scheduler(monkeypatch)
    scans = []

    def scan(_plugin, downloaders, *, stop_event, progress_callback):
        assert not stop_event.is_set()
        scans.append(downloaders)
        progress_callback("扫描 QB", 1, 1)
        return {
            "code": 0,
            "msg": "扫描完成",
            "downloaders": [{"name": "QB", "tags": []}],
            "errors": [],
        }

    monkeypatch.setattr(tag_completion, "scan_tag_completion", scan)

    accepted = tag_completion.submit_tag_completion_scan(plugin, ["QB"], "request-a")
    assert accepted["status"] == "queued"
    assert not scans
    assert len(jobs) == 1
    assert jobs[0][2].__self__ is plugin

    jobs[0][2](**jobs[0][3])
    status = tag_completion.get_tag_completion_status(plugin, task_id=accepted["task_id"])
    result = tag_completion.get_tag_completion_result(plugin, accepted["task_id"])
    repeated = tag_completion.submit_tag_completion_scan(plugin, ["QB"], "request-a")
    reused = tag_completion.submit_tag_completion_scan(plugin, ["QB-OTHER"], "request-a")

    assert status["status"] == "completed"
    assert "downloaders" not in status
    assert result["result"]["downloaders"][0]["name"] == "QB"
    assert repeated["task_id"] == accepted["task_id"]
    assert reused["code"] == 1
    assert "payload" not in reused
    assert len(jobs) == 1
    assert scans == [["QB"]]


def test_scan_forwards_selected_hashes_to_background_task(tmp_path, monkeypatch):
    """指定 hash 限定保存在任务请求中，后台扫描沿用同一范围。"""
    plugin = FakeTagCompletionPlugin(tmp_path)
    jobs = _capture_scheduler(monkeypatch)
    received = []

    def scan(_plugin, _downloaders, **options):
        received.extend(options["torrent_hashes"])
        return {"code": 0, "msg": "扫描完成", "downloaders": [], "errors": []}

    monkeypatch.setattr(tag_completion, "scan_tag_completion", scan)
    task = tag_completion.submit_tag_completion_scan(plugin, ["QB"], "selected", torrent_hashes=["target"])
    jobs[0][2](**jobs[0][3])
    assert received == ["target"]
    assert tag_completion.get_tag_completion_status(plugin, task_id=task["task_id"])["status"] == "completed"


def test_scan_result_paginates_hash_associations(tmp_path):
    """扫描结果按游标分段返回，且保留所有种子关联。"""
    plugin = FakeTagCompletionPlugin(tmp_path)
    task_id = "scan-page-a"
    hashes = [f"hash-{index}" for index in range(450)]
    tag_completion._save_result(plugin, "scan", task_id, {
        "code": 0,
        "msg": "扫描完成",
        "downloaders": [{
            "name": "QB",
            "tags": [{
                "kind": "site",
                "tag": "🏠站点",
                "count": len(hashes),
                "samples": [],
                "hashes": hashes,
            }],
        }],
    })
    state = tag_completion._load_task_state(plugin)
    state["current_task"] = {"task_id": task_id, "operation": "scan", "status": "completed"}
    state["last_scan_task_id"] = task_id
    tag_completion._save_task_state(plugin, state)

    pages = []
    offset = 0
    while True:
        page = tag_completion.get_tag_completion_result(plugin, task_id, offset=offset, limit=200)
        pages.append(page)
        if page["complete"]:
            break
        offset = page["next_offset"]

    restored = [
        torrent_hash
        for page in pages
        for group in page["result"]["downloaders"][0]["tags"]
        for torrent_hash in group["hashes"]
    ]
    assert [page["total"] for page in pages] == [450, 450, 450]
    assert [
        len(page["result"]["downloaders"][0]["tags"][0]["hashes"])
        for page in pages
    ] == [200, 200, 50]
    assert restored == hashes


def test_execute_rebuilds_hashes_only_from_server_scan_result(tmp_path, monkeypatch):
    """执行请求只提交标签组键，实际 hash 来自服务端扫描结果。"""
    plugin = FakeTagCompletionPlugin(tmp_path)
    jobs = _capture_scheduler(monkeypatch)
    scan_task_id = "scan-result-a"
    tag_completion._save_result(plugin, "scan", scan_task_id, {
        "code": 0,
        "msg": "扫描完成",
        "downloaders": [{
            "name": "QB",
            "tags": [{"kind": "site", "tag": "🏠站点", "hashes": ["hash-1", "hash-2"]}],
        }],
    })
    state = tag_completion._load_task_state(plugin)
    state["last_scan_task_id"] = scan_task_id
    tag_completion._save_task_state(plugin, state)
    executions = []

    def execute(_plugin, repairs, *, stop_event, progress_callback):
        assert not stop_event.is_set()
        executions.append(repairs)
        progress_callback("核验 QB", 2, 2)
        return {"code": 0, "msg": "补全完成", "added": [], "skipped": [], "failed": []}

    monkeypatch.setattr(tag_completion, "execute_tag_completion", execute)
    accepted = tag_completion.submit_tag_completion_execute(
        plugin,
        scan_task_id,
        [{"downloader": "QB", "kind": "site", "tag": "🏠站点"}],
        "request-b",
    )
    jobs[0][2](**jobs[0][3])

    assert accepted["status"] == "queued"
    assert executions == [[
        {
            "downloader": "QB",
            "kind": "site",
            "tag": "🏠站点",
            "hashes": ["hash-1", "hash-2"],
        }
    ]]
    assert tag_completion.get_tag_completion_status(plugin)["status"] == "completed"


def test_cancel_or_reload_prevents_queued_task_from_starting(tmp_path, monkeypatch):
    """取消与 reload 都移除排队任务且不自动重放。"""
    plugin = FakeTagCompletionPlugin(tmp_path)
    jobs = _capture_scheduler(monkeypatch)
    removed = []
    monkeypatch.setattr(scheduler, "remove_plugin_once_job", lambda *args: removed.append(args))
    scans = []
    monkeypatch.setattr(
        tag_completion,
        "scan_tag_completion",
        lambda *_args, **_kwargs: scans.append(True) or {"code": 0, "msg": "done"},
    )

    cancelled = tag_completion.submit_tag_completion_scan(plugin, ["QB"], "request-c")
    result = tag_completion.cancel_tag_completion_task(plugin, cancelled["task_id"])
    jobs[0][2](**jobs[0][3])
    assert result["status"] == "cancelled"
    assert tag_completion.get_tag_completion_status(plugin)["status"] == "cancelled"
    assert not scans
    assert removed

    interrupted = tag_completion.submit_tag_completion_scan(plugin, ["QB"], "request-d")
    tag_completion.stop_tag_completion_task(plugin)
    jobs[1][2](**jobs[1][3])
    status = tag_completion.get_tag_completion_status(plugin, task_id=interrupted["task_id"])
    assert status["status"] == "interrupted"
    assert not scans
