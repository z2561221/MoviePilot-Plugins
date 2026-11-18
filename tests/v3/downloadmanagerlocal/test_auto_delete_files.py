"""下载数据删除的目录句柄、原身份、共享引用及部分结果验证。"""

from types import SimpleNamespace

import pytest
from app.plugins.downloadmanagerlocal.adapter import auto_delete as native
from app.plugins.downloadmanagerlocal.model.auto_delete import (
    ActivateRequest,
    SaveRequest,
)
from app.plugins.downloadmanagerlocal.service import auto_delete
from app.plugins.downloadmanagerlocal.service.auto_delete_executor import release_jobs

from tests.v3.downloadmanagerlocal.test_auto_delete import setup_runtime, snapshot


def fake_filesystem(*, replaced=False, symlink=False):
    """只模拟 POSIX 目录句柄，永远不访问或删除用户文件。"""
    actions = []
    current = SimpleNamespace(st_dev=1, st_ino=99 if replaced else 2, st_size=3, st_mtime_ns=4, st_mode=0o100644)
    absent = [False]
    def open_directory(name, flags, **kwargs):
        """记录逐级打开目录，不允许追随软链接。"""
        actions.append(("open", name, flags))
        if symlink and name == "Movie":
            raise OSError("软链接被拒绝")
        return len(actions)
    def file_stat(name, **kwargs):
        """返回对应原身份或确认已删除。"""
        if absent[0]:
            raise FileNotFoundError
        return current
    def unlink(name, **kwargs):
        """记录唯一精确删除请求。"""
        actions.append(("unlink", name, kwargs["dir_fd"]))
        absent[0] = True
    fs = SimpleNamespace(name="posix", O_RDONLY=0, O_DIRECTORY=1, O_NOFOLLOW=2,
                         open=open_directory, fstat=lambda _: SimpleNamespace(st_dev=1, st_ino=5),
                         stat=file_stat, unlink=unlink, supports_dir_fd={unlink},
                         close=lambda fd: actions.append(("close", fd)))
    return fs, actions


@pytest.mark.parametrize("replaced,symlink", [(True, False), (False, True)])
def test_replaced_file_or_symlink_is_not_deleted(monkeypatch, replaced, symlink):
    """文件身份变化和中途软链接均在 unlink 之前拒绝。"""
    fs, actions = fake_filesystem(replaced=replaced, symlink=symlink)
    monkeypatch.setattr(native, "os", fs)
    adapter = native.AutoDeleteAdapter(object())
    adapter.check_library_reference = lambda _: None
    with pytest.raises((ValueError, OSError)):
        adapter.delete_file({"path": "/downloads/Movie/example.mkv", "root": "/downloads",
                             "root_identity": [1, 5], "identity": [1, 2, 3, 4]})
    assert not any(item[0] == "unlink" for item in actions)
    assert any(item[0] == "close" for item in actions)


def test_valid_file_is_unlinked_by_exact_name_and_parent_handle(monkeypatch):
    """正确身份仅发一个文件名请求，不递归删目录或扩大范围。"""
    fs, actions = fake_filesystem()
    monkeypatch.setattr(native, "os", fs)
    guards = []
    adapter = native.AutoDeleteAdapter(object(), lambda: guards.append("checked"))
    adapter.check_library_reference = lambda _: None
    adapter.delete_file({"path": "/downloads/Movie/example.mkv", "root": "/downloads",
                         "root_identity": [1, 5], "identity": [1, 2, 3, 4]})
    assert len([item for item in actions if item[0] == "unlink"]) == 1
    assert next(item for item in actions if item[0] == "unlink")[1] == "example.mkv"
    assert guards == ["checked"]


def test_incomplete_downloader_catalog_blocks_shared_file_check(monkeypatch):
    """启用或停用的下载器未出现在可查询实例中，不能证明无共享引用。"""
    from app.plugins.downloadmanagerlocal.adapter import moviepilot

    helper = SimpleNamespace(get_configs=lambda **_: {"QB": object(), "offline": object()})
    monkeypatch.setattr(moviepilot, "create_downloader_helper", lambda: helper)
    monkeypatch.setattr(moviepilot, "get_downloader_services", lambda: {"QB": object()})
    with pytest.raises(ValueError, match="未连接"):
        native.AutoDeleteAdapter(object()).check_shared_references(snapshot(), ["/downloads/example.mkv"])


def test_different_path_aliases_of_same_file_are_shared(monkeypatch):
    """不同下载器的映射路径若解析到同一文件，必须保留下载数据。"""
    from app.plugins.downloadmanagerlocal.adapter import moviepilot

    helper = SimpleNamespace(get_configs=lambda **_: {"QB": object()})
    monkeypatch.setattr(moviepilot, "create_downloader_helper", lambda: helper)
    monkeypatch.setattr(moviepilot, "get_downloader_services", lambda: {"QB": SimpleNamespace(name="QB")})
    monkeypatch.setattr(native, "Path", lambda _: SimpleNamespace(resolve=lambda: "/same/file.mkv"))
    adapter = native.AutoDeleteAdapter(object())
    other = snapshot().model_copy(update={"hash": "b" * 40}, deep=True)
    adapter.poll = lambda *_: [other]
    adapter.file_paths = lambda *_: ["/other-alias/file.mkv"]
    with pytest.raises(ValueError, match="共用"):
        adapter.check_shared_references(snapshot(), ["/downloads/file.mkv"])


def data_runtime(monkeypatch):
    """构造真实规则/确认服务及完全虚构的文件适配器。"""
    plugin, runtime, adapter, _ = setup_runtime(monkeypatch, name_include="Example")
    settings = runtime.settings.model_copy(deep=True)
    settings.rules[0].action = "data"
    settings.source_paths = ["/downloads"]
    auto_delete.save_settings(plugin, SaveRequest(expected_revision=1, settings=settings))
    job = plugin._auto_delete_runtime.run(now=1000).items[0]
    auto_delete.activate_rule(plugin, ActivateRequest(expected_revision=2, rule_id="rule", job_ids=[job.id],
                                                     evidence_versions={job.id: job.evidence_fingerprint}, accept_history=True))
    adapter.prepare_files = lambda *_: [{"path": "/downloads/file.mkv", "root": "/downloads",
                                         "identity": [1, 2, 3, 4], "root_identity": [1, 5], "deleted": False}]
    adapter.check_shared_references = lambda *_: None
    adapter.delete_file = lambda item: adapter.actions.append("delete_file")
    return plugin, adapter, job


def test_data_mode_uses_explicit_file_stage_before_removing_torrent(monkeypatch):
    """正式数据动作先核验并逐文件处理，最后仅移除任务。"""
    plugin, adapter, job = data_runtime(monkeypatch)
    result = plugin._auto_delete_runtime.run(now=1300)
    assert result.items[0].state == "deleted"
    assert result.items[0].task_removed and result.items[0].data_deleted
    assert adapter.actions == ["pause", "delete_file", "remove"]
    assert plugin._auto_delete_runtime.store.get(job.id)["files"][0]["deleted"]


def test_shared_file_blocks_all_file_deletes(monkeypatch):
    """共用文件检查失败时只保留暂停，不删除任何文件或种子。"""
    plugin, adapter, job = data_runtime(monkeypatch)
    def shared(*args):
        """模拟另一下载器新加任务引用该文件。"""
        raise ValueError("文件被其他任务共用")
    adapter.check_shared_references = shared
    result = plugin._auto_delete_runtime.run(now=1300)
    assert result.items[0].state == "review"
    assert adapter.actions == ["pause"]
    assert job.id in plugin._auto_delete_runtime.store.blocks()


def test_partial_file_delete_prevents_automatic_restore_or_replay(monkeypatch):
    """第一文件成功、第二文件失败，保留部分检查点且拒绝自动开始做种。"""
    plugin, adapter, job = data_runtime(monkeypatch)
    first = adapter.prepare_files(None)[0]
    second = {**first, "path": "/downloads/second.mkv"}
    adapter.prepare_files = lambda *_: [dict(first), dict(second)]
    def partial(item):
        """第二个文件被替换。"""
        if item["path"].endswith("second.mkv"):
            raise ValueError("文件身份变化")
        adapter.actions.append("delete_file")
    adapter.delete_file = partial
    current = plugin._auto_delete_runtime
    result = current.run(now=1300)
    assert result.items[0].state == "review"
    stored = current.store.get(job.id)
    assert stored["files"][0]["deleted"] and not stored["files"][1]["deleted"]
    current.run(now=1600)
    released = release_jobs(current, [job.id], restore=True)
    assert released[0]["state"] == "review"
    assert adapter.actions == ["pause", "delete_file"]


def test_transmission_bulk_file_lookup_is_fresh_and_detects_new_reference(monkeypatch):
    from app.plugins.downloadmanagerlocal.adapter import moviepilot

    rows, calls = [], []
    def fetch(**kwargs):
        calls.append(kwargs)
        return rows
    service = SimpleNamespace(name="TR", type="transmission", config={}, instance=SimpleNamespace(
        trc=SimpleNamespace(get_torrents=fetch)))
    monkeypatch.setattr(moviepilot, "create_downloader_helper", lambda: SimpleNamespace(get_configs=lambda **_: {"TR": 1}))
    monkeypatch.setattr(moviepilot, "get_downloader_services", lambda: {"TR": service})
    adapter = native.AutoDeleteAdapter(object())
    row = dict(hashString="b" * 40, addedDate=8, downloadDir="/downloads", files=[{"name": "different.mkv"}])
    rows.append(SimpleNamespace(fields=row))
    adapter.check_shared_references(snapshot(), ["/downloads/video.mkv"])
    row["files"][0]["name"] = "video.mkv"
    with pytest.raises(ValueError, match="共用"):
        adapter.check_shared_references(snapshot(), ["/downloads/video.mkv"])
    assert len(calls) == 2 and all("files" in call["arguments"] for call in calls)
