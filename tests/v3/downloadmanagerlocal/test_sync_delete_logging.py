"""同步删除日志须与持久任务和实际阶段一致，不依赖通知开关。"""

import runpy
from pathlib import Path
from queue import Empty
from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.model.sync_delete import JOBS_KEY, DeleteRejected
from app.plugins.downloadmanagerlocal.service import sync_delete as service

_fixtures = runpy.run_path(str(Path(__file__).with_name("test_sync_delete_local_bridge.py")))
Plugin, Adapter, event, queued, bridge_case = (
    _fixtures[name] for name in ("Plugin", "Adapter", "event", "queued", "bridge_case")
)


def capture_logs(monkeypatch, plugin):
    """捕获真实调用点，完成日志出现前必须已经持久化完成状态。"""
    messages = []

    def info(message):
        if message.startswith("同步删除完成 "):
            assert any(job["state"] == "completed" for job in plugin.get_data(JOBS_KEY).values())
        messages.append(("info", message))

    logger = SimpleNamespace(info=info, warning=lambda msg: messages.append(("warning", msg)),
                             error=lambda msg: messages.append(("error", msg)))
    monkeypatch.setattr(service, "logger", logger)
    return messages


def run_one_job(monkeypatch, runtime, adapter):
    """运行实际 worker 一轮，退出只截断下一轮等待，不跳过通知判断。"""
    take = runtime.queue.get

    def get_once(*args, **kwargs):
        try:
            return take(block=False)
        except Empty:
            runtime.stop.set()
            raise

    monkeypatch.setattr(service, "SyncDeleteAdapter", lambda *_: adapter)
    monkeypatch.setattr(runtime.queue, "get", get_once)
    monkeypatch.setattr(runtime.stop, "wait", lambda _: runtime.stop.is_set())
    runtime.run()


def test_success_logs_when_notifications_are_off_and_keeps_absent_counts(monkeypatch):
    """关闭通知仍写完整过程，已移走副本单独计数、合集仍记为暂停。"""
    plugin, adapter = bridge_case()
    plugin._sync_delete_notify = False
    plugin._sync_delete_cloud = False
    adapter.items.pop(("local", "/library/A.mkv"))
    adapter.records[0]["src_fileitem"] = {"size": 100}
    adapter.put("local", "/downloads/B.mkv")
    for task in adapter.tasks.values():
        task["files"].append("/downloads/B.mkv")
    notifications = []
    plugin.post_message = lambda **kwargs: notifications.append(kwargs)
    messages = capture_logs(monkeypatch, plugin)
    runtime = service.DeleteRuntime(plugin)
    snapshot = dict(event(), name="测试剧 S1E22\n第22集", raw_token="not-for-logs")
    job_id = runtime.submit(snapshot)
    run_one_job(monkeypatch, runtime, adapter)
    assert runtime.jobs()[job_id]["state"] == "completed" and not notifications
    info = [msg for level, msg in messages if level == "info"]
    assert len(info) == 4
    assert [msg.split(" ")[0] for msg in info] == ["同步删除已受理", "同步删除开始处理", "同步删除关联完成", "同步删除完成"]
    assert all(job_id in msg and "测试剧 S1E22 第22集" in msg for msg in info)
    assert all("\n" not in msg and "not-for-logs" not in msg for msg in info)
    assert "网盘已删除 0、已不存在 0" in info[-1]
    assert "本地已删除 1、已不存在 1" in info[-1]
    assert "种子已移除 0、保留并暂停 2" in info[-1]
    assert "整理记录已清理 1/1" in info[-1]


def test_failure_is_logged_with_identity_and_never_claims_success(monkeypatch):
    """失败任务保留可检索的媒体名和ID，未完成不得输出完成摘要。"""
    plugin, adapter = Plugin(), Adapter()
    plugin._sync_delete_notify = False
    adapter.delete_file = lambda _: (_ for _ in ()).throw(DeleteRejected("存储不可用"))
    messages = capture_logs(monkeypatch, plugin)
    runtime, job = queued(plugin)
    run_one_job(monkeypatch, runtime, adapter)
    assert runtime.jobs()[job["id"]]["state"] == "failed"
    warnings = [msg for level, msg in messages if level == "warning"]
    assert len(warnings) == 1 and job["id"] in warnings[0] and " A：存储不可用" in warnings[0]
    assert not any(msg.startswith("同步删除完成 ") for _, msg in messages)


def test_duplicate_events_do_not_repeat_acceptance_but_retry_is_explicit(monkeypatch):
    """重复通知共用任务，不刷受理日志；人工重试保留同ID并标记重试。"""
    plugin = Plugin()
    messages = capture_logs(monkeypatch, plugin)
    runtime, job = queued(plugin)
    assert runtime.submit(event()) == job["id"]
    assert len(messages) == 1
    job["state"] = "failed"
    runtime.save(job)
    assert runtime.submit(None, job_id=job["id"]) == job["id"]
    assert len(messages) == 2 and messages[-1][1].startswith("同步删除重试已受理 ")


def test_completed_state_must_persist_before_success_log(monkeypatch):
    """即使文件操作完成，持久化完成状态失败也不能记录任务成功。"""
    plugin, adapter = Plugin(), Adapter()
    messages = capture_logs(monkeypatch, plugin)
    runtime, job = queued(plugin)
    save = plugin.save_data

    def fail_completion(key, value):
        if key == JOBS_KEY and value.get(job["id"], {}).get("state") == "completed":
            return
        save(key, value)

    plugin.save_data = fail_completion
    with pytest.raises(DeleteRejected, match="保存未确认"):
        runtime.execute(job, adapter)
    assert not any(msg.startswith("同步删除完成 ") for _, msg in messages)
