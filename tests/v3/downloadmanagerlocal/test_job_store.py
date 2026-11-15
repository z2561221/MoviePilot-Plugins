"""任务存储的旧格式兼容、独立检查点、分页、故障及实例隔离。"""

import json
import sqlite3
from collections import Counter
from time import time

import pytest
from app.plugins.downloadmanagerlocal.model.sync_delete import JOBS_KEY, DeleteRejected
from app.plugins.downloadmanagerlocal.storage.sync_delete_jobs import (
    JOB_INDEX_KEY,
    DeleteJobStore,
    job_record_key,
)


class JsonStore:
    """模拟每次持久层调用都序列化和解码，计数读写字节。"""

    def __init__(self, data=None):
        """准备隔离的JSON值。"""
        self.values = {key: json.dumps(value) for key, value in (data or {}).items()}
        self.reads, self.writes = Counter(), Counter()
        self.read_bytes = self.write_bytes = 0

    def get_data(self, key):
        """返回本次独立解码的对象。"""
        self.reads[key] += 1
        raw = self.values.get(key)
        self.read_bytes += len(raw or "")
        return json.loads(raw) if raw is not None else None

    def save_data(self, key, value):
        """记录保存规模并保留JSON副本。"""
        self.writes[key] += 1
        raw = json.dumps(value)
        self.write_bytes += len(raw)
        self.values[key] = raw

    def del_data(self, key):
        """只清理本测试字典里的详情副本。"""
        self.values.pop(key, None)


def job(job_id, state="completed", updated=None, files=20):
    """构造含文件清单的任务记录，不执行文件操作。"""
    return {"id": job_id, "state": state, "updated_at": time() if updated is None else updated,
            "event_key": "event-" + job_id, "plan": {"source_files": [
                {"path": f"/downloads/{job_id}/Episode{n}.mkv", "status": "pending"}
                for n in range(files)]}}


def test_legacy_readonly_and_new_checkpoints_do_not_rewrite_old_history():
    """1000条旧历史兼容读，50个检查点只重写当前任务，不反复读取旧大对象。"""
    old = {str(i): job(str(i)) for i in range(999)}
    plugin = JsonStore({JOBS_KEY: old})
    store = DeleteJobStore(plugin)
    assert len(store.all()) == 999 and not plugin.writes
    current = job("active", "running", files=50)
    store.save(current)
    reads = plugin.reads[JOBS_KEY]
    writes = plugin.writes[JOB_INDEX_KEY]
    before_bytes = plugin.write_bytes
    for n in range(50):
        current["plan"]["source_files"][n]["status"] = "deleted"
        store.save(current)
    assert plugin.reads[JOBS_KEY] == reads
    assert plugin.writes[JOB_INDEX_KEY] == writes
    assert plugin.writes[job_record_key("active")] == 51
    assert plugin.write_bytes - before_bytes < 300_000
    assert plugin.get_data(JOBS_KEY) == old
    assert DeleteJobStore(plugin).get("active") == current


def test_page_loads_only_selected_separate_records():
    """新格式100条详情只加载当前页15条，保持摘要排序。"""
    plugin = JsonStore()
    store = DeleteJobStore(plugin)
    for n in range(100):
        store.save(job(str(n), updated=time() + n))
    plugin.reads.clear()
    total, rows = store.page(2, 15)
    assert total == 100 and [row["id"] for row in rows] == [str(n) for n in range(84, 69, -1)]
    assert sum(count for key, count in plugin.reads.items() if key.startswith("sync_delete_job_record_")) == 15


@pytest.mark.parametrize("failed_key", ["record", "index"])
def test_unconfirmed_persistence_never_reports_saved(failed_key):
    """任务详情或索引静默丢写必须拒绝保存，不返回成功。"""
    plugin = JsonStore()
    store = DeleteJobStore(plugin)
    original = plugin.save_data

    def failing(key, value):
        """只让选定的持久边界静默失败。"""
        if key != (job_record_key("one") if failed_key == "record" else JOB_INDEX_KEY):
            original(key, value)

    plugin.save_data = failing
    with pytest.raises(DeleteRejected, match="保存未确认"):
        store.save(job("one", "queued"))
    assert store.get("one") is None


def test_interrupted_index_update_reconciles_from_latest_detail():
    """详情成功、索引失败后，新进程从权威详情恢复摘要，不丢失完成进度。"""
    plugin = JsonStore()
    store = DeleteJobStore(plugin)
    current = job("one", "running")
    store.save(current)
    original = plugin.save_data

    def failing(key, value):
        """模拟完成状态的索引发布丢失。"""
        if key != JOB_INDEX_KEY:
            original(key, value)

    plugin.save_data = failing
    current.update(state="completed", updated_at=time() + 1)
    with pytest.raises(DeleteRejected):
        store.save(current)
    plugin.save_data = original
    recovered = DeleteJobStore(plugin)
    assert recovered.reconcile()["one"] == current
    assert recovered.summaries()["one"]["state"] == "completed"


def test_missing_or_corrupt_new_detail_never_falls_back_to_old_snapshot():
    """已转为独立详情的任务丢失时拒绝陈旧旧格式，保护后续删除。"""
    plugin = JsonStore({JOBS_KEY: {"one": job("one", "failed")}})
    store = DeleteJobStore(plugin)
    store.save(job("one", "completed"))
    plugin.del_data(job_record_key("one"))
    with pytest.raises(DeleteRejected, match="详情缺失"):
        store.get("one")
    plugin.values[JOB_INDEX_KEY] = json.dumps({"schema_version": 99, "items": {}})
    with pytest.raises(DeleteRejected, match="索引损坏"):
        store.all()


def test_pruning_keeps_pending_and_preserves_original_legacy_bytes():
    """只裁剪已结束索引，长期未决任务及原旧历史受保护。"""
    legacy = {"old": job("old", updated=1), "pending": job("pending", "failed", updated=1)}
    plugin = JsonStore({JOBS_KEY: legacy})
    store = DeleteJobStore(plugin)
    store.save(job("new", "completed"))
    assert set(store.all()) == {"pending", "new"}
    assert plugin.get_data(JOBS_KEY) == legacy


def test_sqlite_roundtrip_isolated_by_plugin_identity():
    """真实SQLite JSON行验证两个实例同任务ID不会串读或覆盖。"""
    db = sqlite3.connect(":memory:")
    db.execute("create table data (plugin text, key text, value text, primary key(plugin,key))")

    class SqliteStore:
        """只替换基类持久边界，存储算法使用真实实现。"""

        def __init__(self, instance):
            """绑定独立的实例命名空间。"""
            self.instance = instance

        def get_data(self, key):
            """单事务读取独立JSON值。"""
            row = db.execute("select value from data where plugin=? and key=?", (self.instance, key)).fetchone()
            return json.loads(row[0]) if row else None

        def save_data(self, key, value):
            """提交当前实例的单键修改。"""
            db.execute("insert or replace into data values (?,?,?)", (self.instance, key, json.dumps(value)))
            db.commit()

    try:
        first, second = DeleteJobStore(SqliteStore("A")), DeleteJobStore(SqliteStore("B"))
        first.save(job("same", "running"))
        second.save(job("same", "failed"))
        assert first.get("same")["state"] == "running"
        assert second.get("same")["state"] == "failed"
    finally:
        db.close()
