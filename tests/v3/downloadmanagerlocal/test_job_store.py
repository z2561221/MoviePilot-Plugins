"""任务存储的旧格式兼容、独立检查点、分页、故障及实例隔离。"""

import json
import sqlite3
from collections import Counter
from queue import Full
from time import time

import pytest
from app.plugins.downloadmanagerlocal.model.sync_delete import (
    BLOCKS_KEY,
    DEFAULTS,
    JOBS_KEY,
    DeleteRejected,
    event_snapshot,
)
from app.plugins.downloadmanagerlocal.service import sync_delete as runtime_service
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
    """真实SQLite独立事务验证保存与补偿删除都限定本实例，不碰同ID副本。"""
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

        def del_data(self, key):
            """提交仅本实例/本键的删除，保留其他实例同名记录。"""
            db.execute("delete from data where plugin=? and key=?", (self.instance, key))
            db.commit()

    try:
        first, second = DeleteJobStore(SqliteStore("A")), DeleteJobStore(SqliteStore("B"))
        first.save(job("same", "running"))
        second.save(job("same", "failed"))
        assert first.get("same")["state"] == "running"
        assert second.get("same")["state"] == "failed"
        second.save(job("unpublished", "queued"), new_task=True)
        save = first.plugin.save_data

        def lose_index(key, value):
            """详情为已提交SQL行，独立索引事务没有发布。"""
            if key != JOB_INDEX_KEY:
                save(key, value)

        first.plugin.save_data = lose_index
        with pytest.raises(DeleteRejected, match="已撤回"):
            first.save(job("unpublished", "queued"), new_task=True)
        assert first.plugin.get_data(job_record_key("unpublished")) is None
        assert second.get("unpublished")["state"] == "queued"
        assert first.get("same")["state"] == "running"

        def unknown_index(key, value):
            """索引SQL行实际已提交但确认抛错，详情必须保留。"""
            save(key, value)
            if key == JOB_INDEX_KEY:
                raise OSError("isolated SQL acknowledgement failure")

        first.plugin.save_data = unknown_index
        with pytest.raises(DeleteRejected, match="结果未知"):
            first.save(job("unknown", "queued"), new_task=True)
        first.plugin.save_data = save
        assert first.reconcile()["unknown"]["state"] == "queued"
        assert second.get("unpublished")["state"] == "queued"
    finally:
        db.close()


def test_unindexed_new_task_is_never_admitted_or_resumed_after_restart():
    """全新详情成功但索引明确失败时撤回本次写入，拒绝准入及重启重放。"""
    plugin = JsonStore()
    for key, value in DEFAULTS.items():
        setattr(plugin, "_" + key, value)
    plugin._enabled = plugin._sync_delete_enabled = True
    original = plugin.save_data

    def lose_index(key, value):
        """模拟独立详情写入成功而索引静默失败。"""
        if key != JOB_INDEX_KEY:
            original(key, value)

    plugin.save_data = lose_index
    runtime = runtime_service.DeleteRuntime(plugin)
    event = event_snapshot({"event": "deep.delete", "channel": "emby", "item_path": "/emby/A.strm"})
    with pytest.raises(DeleteRejected, match="摘要索引"):
        runtime.submit(event)
    assert runtime.queue.empty() and runtime.stop.is_set()
    record_keys = [key for key in plugin.writes if key.startswith("sync_delete_job_record_")]
    assert len(record_keys) == 1 and record_keys[0] not in plugin.values
    plugin.save_data = original
    plugin._enabled = plugin._sync_delete_enabled = False
    runtime_service.start_runtime(plugin)
    restarted = plugin._sync_delete_runtime
    assert restarted.queue.empty() and restarted.thread is None and restarted.jobs() == {}
    assert restarted.store.get(record_keys[0].removeprefix("sync_delete_job_record_")) is None


def test_runtime_storage_failure_stops_further_admission_without_more_orphans():
    """第一次索引失败关闭执行器，随后20次通知不再写新详情。"""
    plugin = JsonStore()
    for key, value in DEFAULTS.items():
        setattr(plugin, "_" + key, value)
    plugin._enabled = plugin._sync_delete_enabled = True
    original = plugin.save_data

    def lose_index(key, value):
        """只拒绝摘要存储，保留详情存储成功的现场。"""
        if key != JOB_INDEX_KEY:
            original(key, value)

    plugin.save_data = lose_index
    runtime = runtime_service.DeleteRuntime(plugin)
    event = event_snapshot({"event": "deep.delete", "channel": "emby", "item_path": "/emby/A.strm"})
    with pytest.raises(DeleteRejected, match="摘要索引"):
        runtime.submit(event)
    for _ in range(20):
        with pytest.raises(DeleteRejected, match="已停止"):
            runtime.submit(event)
    assert runtime.queue.empty()
    assert not [key for key in plugin.values if key.startswith("sync_delete_job_record_")]
    assert sum(count for key, count in plugin.writes.items() if key.startswith("sync_delete_job_record_")) == 1


def test_repeated_new_task_index_failures_should_not_accumulate_unindexed_details():
    """逐次恢复执行器后索引仍明确失败，20次均撤回且不累计孤立详情。"""
    plugin = JsonStore()
    for key, value in DEFAULTS.items():
        setattr(plugin, "_" + key, value)
    plugin._enabled = plugin._sync_delete_enabled = True
    original = plugin.save_data

    def lose_index(key, value):
        """详情存储正常，索引持续不可写。"""
        if key != JOB_INDEX_KEY:
            original(key, value)

    plugin.save_data = lose_index
    for number in range(20):
        runtime = runtime_service.DeleteRuntime(plugin)
        event = event_snapshot({"channel": "emby", "item_path": f"/emby/{number}.strm"})
        with pytest.raises(DeleteRejected, match="新任务失败写入已撤回"):
            runtime.submit(event)
        assert runtime.stop.is_set() and runtime.queue.empty()
    orphan_keys = [key for key in plugin.values if key.startswith("sync_delete_job_record_")]
    retained_bytes = sum(len(plugin.values[key]) for key in orphan_keys)
    plugin.save_data = original
    assert DeleteJobStore(plugin).reconcile() == {}
    assert not orphan_keys, f"20次失败保留{len(orphan_keys)}条孤立详情，共{retained_bytes}字节"


@pytest.mark.parametrize("failure", ["write_before", "write_after", "read_without_publish",
                                    "read_after_publish", "corrupt_index", "referenced_index"])
def test_unknown_or_referenced_index_failure_preserves_new_detail(failure):
    """写入/回读未知以及已有引用均保留详情，不把失败误报为已撤回。"""
    plugin = JsonStore()
    save, read = plugin.save_data, plugin.get_data
    attempted = False
    removed = []

    def fail_index(key, value):
        """覆盖未提交和已提交但确认失败的两类索引结果。"""
        nonlocal attempted
        if key != JOB_INDEX_KEY:
            return save(key, value)
        attempted = True
        if failure == "write_before":
            raise OSError("isolated write failure")
        if failure not in {"read_without_publish", "corrupt_index", "referenced_index"}:
            save(key, value)
        if failure == "write_after":
            raise OSError("isolated acknowledgement failure")
        if failure == "corrupt_index":
            save(key, {"schema_version": 99, "items": {}})
        if failure == "referenced_index":
            value = json.loads(json.dumps(value))
            value["items"]["one"]["updated_at"] += 1
            save(key, value)

    def uncertain_read(key):
        """在保存后独立回读时注入故障，写前读取仍可靠。"""
        if attempted and key == JOB_INDEX_KEY and failure.startswith("read_"):
            raise OSError("isolated read failure")
        return read(key)

    plugin.save_data, plugin.get_data = fail_index, uncertain_read
    plugin.del_data = removed.append
    runtime = runtime_service.DeleteRuntime(plugin)
    with pytest.raises(DeleteRejected, match="摘要索引") as caught:
        runtime.save(job("one", "queued"), new_task=True)
    assert runtime.stop.is_set() and runtime.queue.empty()
    assert read(job_record_key("one"))["state"] == "queued" and not removed
    assert "已撤回" not in str(caught.value)
    if failure.startswith(("write_", "read_")):
        assert "结果未知" in str(caught.value)


@pytest.mark.parametrize("condition", ["index_reference", "index_read_failure", "blocks_reference",
                                      "blocks_invalid", "blocks_row_invalid", "blocks_read_failure",
                                      "detail_changed", "detail_missing", "detail_read_failure"])
def test_compensation_rechecks_references_and_detail_before_removal(condition):
    """索引未发布后出现新引用、内容变化或边界回读失败时不删除详情。"""
    plugin = JsonStore()
    save, read = plugin.save_data, plugin.get_data
    attempted = None
    index_reads, detail_reads = 0, 0
    removed = []
    record_key = job_record_key("one")

    def lose_index(key, value):
        """索引明确未发布，但后续补偿边界可能变化。"""
        nonlocal attempted
        if key != JOB_INDEX_KEY:
            return save(key, value)
        attempted = json.loads(json.dumps(value))
        if condition == "blocks_reference":
            save(BLOCKS_KEY, {"block": {"job_id": "one"}})
        elif condition == "blocks_invalid":
            save(BLOCKS_KEY, [])
        elif condition == "blocks_row_invalid":
            save(BLOCKS_KEY, {"block": None})

    def changed_read(key):
        """在明确失败的首次观察之后再改变补偿条件。"""
        nonlocal index_reads, detail_reads
        if attempted is not None and key == JOB_INDEX_KEY:
            index_reads += 1
            if index_reads == 2:
                if condition == "index_read_failure":
                    raise OSError("isolated index read failure")
                if condition == "index_reference":
                    save(JOB_INDEX_KEY, attempted)
        if attempted is not None and key == BLOCKS_KEY and condition == "blocks_read_failure":
            raise OSError("isolated blocks read failure")
        if key == record_key:
            detail_reads += 1
            if detail_reads == 3:
                if condition == "detail_changed":
                    changed = read(key)
                    changed["state"] = "failed"
                    save(key, changed)
                elif condition == "detail_missing":
                    plugin.values.pop(key)
                elif condition == "detail_read_failure":
                    raise OSError("isolated detail read failure")
        return read(key)

    plugin.save_data, plugin.get_data = lose_index, changed_read
    plugin.del_data = removed.append
    with pytest.raises(DeleteRejected, match="未补偿"):
        DeleteJobStore(plugin).save(job("one", "queued"), new_task=True)
    assert not removed
    if condition == "detail_changed":
        assert read(record_key)["state"] == "failed"
    else:
        assert (read(record_key) is None) == (condition == "detail_missing")


@pytest.mark.parametrize("failure", ["remove_before", "remove_after", "remove_dropped",
                                    "remove_read", "unsupported"])
def test_failed_compensation_is_not_confirmed_or_retried(failure):
    """补偿自身的删除/确认失败只执行一次，并与成功撤回明确区分。"""
    plugin = JsonStore()
    save, read, remove = plugin.save_data, plugin.get_data, plugin.del_data
    removed = []

    def lose_index(key, value):
        """只丢失索引，使本次新详情满足补偿条件。"""
        if key != JOB_INDEX_KEY:
            save(key, value)

    def uncertain_remove(key):
        """模拟删除提交前/后抛错和静默丢删。"""
        removed.append(key)
        if failure == "remove_before":
            raise OSError("isolated remove failure")
        if failure != "remove_dropped":
            remove(key)
        if failure == "remove_after":
            raise OSError("isolated remove acknowledgement failure")

    def uncertain_read(key):
        """删除已提交，但确认读取失败仍不能输出成功。"""
        if removed and key == job_record_key("one") and failure == "remove_read":
            raise OSError("isolated remove verification failure")
        return read(key)

    plugin.save_data, plugin.get_data = lose_index, uncertain_read
    plugin.del_data = None if failure == "unsupported" else uncertain_remove
    with pytest.raises(DeleteRejected, match="补偿未确认"):
        DeleteJobStore(plugin).save(job("one", "queued"), new_task=True)
    assert len(removed) == (0 if failure == "unsupported" else 1)
    assert (read(job_record_key("one")) is None) == (failure in {"remove_after", "remove_read"})
    assert read(JOB_INDEX_KEY) is None


@pytest.mark.parametrize("existing", ["indexed", "unindexed", "read_failure", "non_queued"])
def test_new_task_requires_confirmed_empty_identity_before_writing(existing):
    """新任务补偿语境不能覆盖已有ID，也不把写前读取失败当作空记录。"""
    plugin = JsonStore()
    store = DeleteJobStore(plugin)
    current = job("one", "queued")
    if existing == "indexed":
        store.save(current)
    elif existing == "unindexed":
        plugin.save_data(job_record_key("one"), current)
    elif existing == "read_failure":
        read = plugin.get_data

        def fail_read(key):
            """详情写前状态无法确认，必须在写入前退出。"""
            if key == job_record_key("one"):
                raise OSError("isolated initial read failure")
            return read(key)

        plugin.get_data = fail_read
    else:
        current["state"] = "running"
    before = dict(plugin.values)
    plugin.writes.clear()
    with pytest.raises(DeleteRejected):
        store.save(current, new_task=True)
    assert plugin.values == before and not plugin.writes


@pytest.mark.parametrize("failure", ["transition_drop", "transition_raise_after", "transition_read", "detail_drop",
                                    "detail_raise_before", "detail_raise_after", "detail_read",
                                    "final_drop", "final_raise_after", "final_read"])
def test_legacy_conversion_uses_recoverable_index_and_preserves_latest_progress(failure):
    """旧任务转存任一阶段失败，恢复时依实际详情来源收敛，旧大对象不变。"""
    old = job("one", "failed")
    plugin = JsonStore({JOBS_KEY: {"one": old}})
    legacy_bytes = plugin.values[JOBS_KEY]
    save, read = plugin.save_data, plugin.get_data
    current = job("one", "running")
    current["plan"]["source_files"][0]["status"] = "deleted"
    index_writes, detail_written = 0, False

    def interrupt(key, value):
        """索引过渡先于详情，分别模拟各事务确认边界。"""
        nonlocal index_writes, detail_written
        if key == JOB_INDEX_KEY:
            index_writes += 1
            stage = "transition" if index_writes == 1 else "final"
            if failure == stage + "_drop":
                return
            save(key, value)
            if failure == stage + "_raise_after":
                raise OSError("isolated index acknowledgement failure")
        else:
            if failure == "detail_drop":
                return
            if failure == "detail_raise_before":
                raise OSError("isolated detail write failure")
            save(key, value)
            detail_written = True
            if failure == "detail_raise_after":
                raise OSError("isolated detail acknowledgement failure")

    def fail_detail_read(key):
        """详情可能已提交，确认读取异常后仍保留过渡索引。"""
        if detail_written and key == job_record_key("one") and failure == "detail_read":
            raise OSError("isolated detail read failure")
        if key == JOB_INDEX_KEY and ((index_writes == 1 and failure == "transition_read")
                                     or (index_writes == 2 and failure == "final_read")):
            raise OSError("isolated index read failure")
        return read(key)

    plugin.save_data, plugin.get_data = interrupt, fail_detail_read
    with pytest.raises(DeleteRejected):
        DeleteJobStore(plugin).save(current)
    if failure.startswith("transition_"):
        assert job_record_key("one") not in plugin.values
    plugin.save_data, plugin.get_data = save, read
    recovered = DeleteJobStore(plugin)
    expected = current if detail_written else old
    assert recovered.get("one") == expected
    assert recovered.reconcile() == {"one": expected}
    summary = recovered.summaries()["one"]
    assert summary["separate"] is detail_written and "legacy_fallback" not in summary
    assert plugin.values[JOBS_KEY] == legacy_bytes


def test_legacy_conversion_does_not_fall_back_after_corrupt_detail():
    """过渡索引只允许缺失详情回退，不用陈旧历史掩盖已写入的坏详情。"""
    plugin = JsonStore({JOBS_KEY: {"one": job("one", "failed")}})
    save = plugin.save_data

    def corrupt_detail(key, value):
        """提交损坏的详情，保留已发布的过渡索引。"""
        save(key, {"id": "other", "state": "running"} if key == job_record_key("one") else value)

    plugin.save_data = corrupt_detail
    with pytest.raises(DeleteRejected, match="任务详情"):
        DeleteJobStore(plugin).save(job("one", "running"))
    plugin.save_data = save
    recovered = DeleteJobStore(plugin)
    with pytest.raises(DeleteRejected, match="详情缺失或损坏"):
        recovered.reconcile()
    assert recovered.summaries()["one"]["legacy_fallback"] is True
    assert plugin.get_data(job_record_key("one"))["id"] == "other"


def test_legacy_unconfirmed_existing_detail_is_preserved_without_overwrite():
    """以前故障留下的未确认旧详情不属于新任务补偿，不覆盖、不主动清理。"""
    plugin = JsonStore({JOBS_KEY: {"one": job("one", "failed")},
                       job_record_key("one"): job("one", "running")})
    before = dict(plugin.values)
    with pytest.raises(DeleteRejected, match="未确认独立详情"):
        DeleteJobStore(plugin).save(job("one", "queued"))
    assert not plugin.writes and plugin.values == before


@pytest.mark.parametrize("settlement", ["retry", "queue_full"])
def test_admitted_task_update_failure_keeps_detail_and_stops_runtime(settlement):
    """重试和队列满结算是已有任务更新，索引失败不撤回新的权威详情。"""
    plugin = JsonStore()
    for key, value in DEFAULTS.items():
        setattr(plugin, "_" + key, value)
    plugin._enabled = plugin._sync_delete_enabled = True
    runtime = runtime_service.DeleteRuntime(plugin)
    event = event_snapshot({"channel": "emby", "item_path": "/emby/A.strm"})
    if settlement == "retry":
        job_id = runtime.submit(event)
        assert runtime.queue.get_nowait() == job_id
        runtime.queue.task_done()
        current = runtime.store.get(job_id)
        current.update(state="failed")
        runtime.save(current)
    else:
        def full(_job_id):
            """首次索引已确认后队列拒绝受理，进入失败结算。"""
            raise Full

        runtime.queue.put_nowait = full
    save = plugin.save_data
    index_writes = 0

    def lose_settlement_index(key, value):
        """已受理详情的后续索引静默失败，不改变首次发布结果。"""
        nonlocal index_writes
        if key == JOB_INDEX_KEY:
            index_writes += 1
            if settlement == "retry" or index_writes > 1:
                return
        save(key, value)

    plugin.save_data = lose_settlement_index
    with pytest.raises(DeleteRejected, match="摘要索引"):
        runtime.submit(event, job_id=job_id if settlement == "retry" else None)
    assert runtime.stop.is_set() and runtime.queue.empty()
    record_keys = [key for key in plugin.values if key.startswith("sync_delete_job_record_")]
    assert len(record_keys) == 1
    current = plugin.get_data(record_keys[0])
    assert current["state"] == ("queued" if settlement == "retry" else "failed")
    plugin.save_data = save
    assert DeleteJobStore(plugin).reconcile()[current["id"]] == current


@pytest.mark.parametrize("failure", ["write_before", "write_after", "read_after", "write_dropped",
                                    "corrupt", "initial_read", "initial_index_read"])
def test_new_detail_failure_stops_admission_without_unconfirmed_compensation(failure):
    """未确认详情本身或写前状态时，保留未知结果并停止准入，不删除详情。"""
    plugin = JsonStore()
    for key, value in DEFAULTS.items():
        setattr(plugin, "_" + key, value)
    plugin._enabled = plugin._sync_delete_enabled = True
    save, read = plugin.save_data, plugin.get_data
    detail_written, index_reads = False, 0
    removed = []

    def fail_detail(key, value):
        """详情写入前、后故障及坏回读都不能当作已确认快照。"""
        nonlocal detail_written
        if key.startswith("sync_delete_job_record_"):
            if failure == "write_before":
                raise OSError("isolated detail write failure")
            if failure == "write_dropped":
                return
            save(key, {"id": "wrong", "state": "queued"} if failure == "corrupt" else value)
            detail_written = True
            if failure == "write_after":
                raise OSError("isolated detail acknowledgement failure")
        else:
            save(key, value)

    def fail_read(key):
        """写前缺失也需可靠读取；保存后读取失败不触发补偿。"""
        nonlocal index_reads
        if key == JOB_INDEX_KEY:
            index_reads += 1
            if index_reads == 2 and failure == "initial_index_read":
                raise OSError("isolated initial index read failure")
        if key.startswith("sync_delete_job_record_") and (
                failure == "initial_read" or (detail_written and failure == "read_after")):
            raise OSError("isolated detail read failure")
        return read(key)

    plugin.save_data, plugin.get_data, plugin.del_data = fail_detail, fail_read, removed.append
    runtime = runtime_service.DeleteRuntime(plugin)
    event = event_snapshot({"channel": "emby", "item_path": "/emby/A.strm"})
    with pytest.raises(DeleteRejected, match="保存未确认"):
        runtime.submit(event)
    assert runtime.stop.is_set() and runtime.queue.empty() and not removed
    assert JOB_INDEX_KEY not in plugin.values
    assert bool(plugin.values) is (failure in {"write_after", "read_after", "corrupt"})
