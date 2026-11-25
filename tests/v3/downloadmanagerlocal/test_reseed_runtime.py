"""通用辅助铺种的协议、任务、文件核验与恢复回归。"""

import hashlib
import threading
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.plugins.downloadmanagerlocal.service import iyuu, pieces, recheck, reseed
from app.plugins.downloadmanagerlocal.utils import torrent_adapter
from app.plugins.downloadmanagerlocal.utils.config import (
    PLUGIN_CONFIG_DEFAULTS,
    is_iyuu_active,
)
from app.sdk import scheduler
from bencode import bencode


def torrent(source=b"source", name=b"movie.mkv", length=5, piece_length=16):
    """构造数据一致但站点来源字段不同的真实 bencode 元数据。"""
    return bencode({b"info": {b"name": name, b"length": length, b"piece length": piece_length,
                               b"pieces": b"a" * 20, b"source": source}})


@pytest.fixture
def environment(monkeypatch):
    """创建隔离的下载器、调度器和持久化插件替身。"""
    stored, jobs, additions = {}, [], []
    contents = {}
    rows = {}
    initial = torrent()
    initial_hash = pieces.torrent_metadata(initial)["hash"]
    contents[initial_hash] = initial
    rows[initial_hash] = {"hash": initial_hash, "name": "movie.mkv", "added_on": 1,
                          "save_path": "/data", "progress": 1, "state": "pausedUP", "size": 5}
    plugin = SimpleNamespace(**{"_" + key: deepcopy(value) for key, value in PLUGIN_CONFIG_DEFAULTS.items()})
    plugin._enabled = True
    plugin._iyuu_enabled = True
    plugin._iyuu_token = "test-token"
    plugin._iyuu_downloaders = ["QB"]
    plugin._pieces_site_keys = "站点A:key-a\n站点B:key-b:3"
    plugin._event = threading.Event()
    plugin._transfer_stop_generation = 0
    plugin._iyuu_success_caches = []
    plugin._iyuu_error_caches = []
    plugin._iyuu_permanent_error_caches = []
    plugin._rename_enabled = False
    plugin._tag_enabled = False
    plugin.iyuu_helper = SimpleNamespace(ensure_ready=lambda: (True, ""))
    plugin.get_data = lambda key=None: deepcopy(stored.get(key))
    plugin.save_data = lambda key, value: stored.__setitem__(key, deepcopy(value))
    plugin.get_config = lambda: {}
    plugin.update_config = Mock()
    for name in ("get_hash", "get_save_path", "get_label", "get_torrent_size", "get_category"):
        setattr(plugin, name, getattr(torrent_adapter, name))
    instance = SimpleNamespace(is_inactive=lambda: False)
    instance.get_torrents = lambda ids=None: ([deepcopy(value) for key, value in rows.items() if ids is None or key in ids], None)
    instance.get_completed_torrents = lambda ids=None: [row for row in instance.get_torrents(ids)[0] if row["progress"] == 1]
    instance.get_files = lambda identity: [{"name": "movie.mkv", "size": 5}]
    instance.recheck_torrents = Mock(return_value=True)

    def add(**kwargs):
        """模拟下载器接收任务，保存真实 hash 并保持暂停。"""
        identity = pieces.torrent_metadata(kwargs["content"])["hash"]
        additions.append(kwargs)
        rows[identity] = {"hash": identity, "name": "movie.mkv", "added_on": 2,
                          "save_path": kwargs["download_dir"], "progress": 0, "state": "stoppedDL", "size": 5}
        return True

    instance.add_torrent = add
    service = SimpleNamespace(name="QB", type="qbittorrent", instance=instance)
    plugin.service_info = lambda name: service if name == "QB" else None
    plugin._register_seed_recheck = lambda *args: recheck.register_seed_recheck(plugin, *args)
    plugin._run_reseed_task = lambda task_id: reseed.run(plugin, task_id)
    sites = [{"id": 1, "name": "站点A", "url": "https://a.invalid/"},
             {"id": 2, "name": "站点B", "url": "https://b.invalid/"}]
    monkeypatch.setattr(reseed, "list_site_dicts", lambda: deepcopy(sites))
    monkeypatch.setattr(reseed, "get_downloader_services", lambda **kwargs: {"QB": service})
    monkeypatch.setattr(reseed, "export_qb_completed_torrent", lambda name, identity: ({}, contents[identity]))
    monkeypatch.setattr(reseed, "check_site", lambda site: (False, ""))
    monkeypatch.setattr(reseed, "request_pieces_torrent", lambda site, identity: torrent(b"target"))
    monkeypatch.setattr(pieces, "query_site", lambda site, hashes: ({hashes[0]: "1"}, 0, ""))
    monkeypatch.setattr(reseed.ReseedRun, "wait_budget", lambda run, *_args: not run.stopped())
    monkeypatch.setattr(recheck, "ensure_seed_recheck_worker", lambda plugin: None)
    monkeypatch.setattr(iyuu, "is_downloader_type", lambda kind, service: kind == service.type)
    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", lambda *args, **kwargs: None)
    monkeypatch.setattr(iyuu, "create_temporary_tag", lambda plugin: "temporary")
    monkeypatch.setattr(iyuu, "release_temporary_tag", lambda *args: None)
    monkeypatch.setattr(iyuu, "forget_temporary_tag", lambda *args: None)
    monkeypatch.setattr(scheduler, "add_plugin_once_job", lambda *args, **kwargs: jobs.append((args, kwargs)) or True)
    monkeypatch.setattr(scheduler, "remove_plugin_once_job", lambda *args: None)
    return SimpleNamespace(plugin=plugin, stored=stored, rows=rows, jobs=jobs, additions=additions,
                           contents=contents, source_hash=initial_hash, service=service, sites=sites)


def execute(environment, preview=False):
    """从正常提交入口执行已登记的绑定回调。"""
    task = reseed.start(environment.plugin, f"request-{len(environment.jobs)}", preview)
    args, kwargs = environment.jobs[-1]
    args[2](**kwargs["func_kwargs"])
    return reseed.status(environment.plugin), reseed.results(environment.plugin, task["task_id"])


def test_pieces_supplements_iyuu_and_forces_verification(environment):
    """两站返回相同目标只添加一次，已有跳校验偏好不会绕过 Pieces 校验。"""
    environment.plugin._seed_skipverify = True
    task, result = execute(environment)
    assert task["status"] == "completed"
    assert task["mode"] == "auto"
    assert task["added"] == 1
    assert len(environment.additions) == 1
    assert environment.additions[0]["is_paused"] is True
    assert environment.additions[0]["is_skip_checking"] is False
    environment.service.instance.recheck_torrents.assert_called_once()
    history = environment.stored[f"iyuu_{environment.source_hash}"][0]
    assert next(iter(history["providers"].values()))["provider"] == "pieces"
    assert all(item["source"] == "pieces" for item in environment.stored["seed_recheck_queue"].values())
    assert result["total"] == 2


def test_actual_run_has_a_total_addition_cap(environment):
    """正式运行的安全上限跨站点累计，避免预览候选被整批写入。"""
    environment.plugin._reseed_max_additions = 1
    task, _ = execute(environment)
    assert task["added"] == 1


def test_multiple_pieces_candidates_use_the_same_safe_addition_and_recheck_pipeline(environment, monkeypatch):
    """多候选保持暂停添加、强制校验与跨站点去重，不另造 Flux 添加流程。"""
    monkeypatch.setattr(pieces, "query_site", lambda site, hashes: ({hashes[0]: ["11", "12"]}, 0, ""))
    monkeypatch.setattr(reseed, "request_pieces_torrent", lambda site, identity: torrent(("target-" + identity).encode()))

    task, _result = execute(environment)

    assert task["matched"] == 4
    assert task["added"] == 2
    assert len(environment.additions) == 2
    assert all(addition["is_paused"] and not addition["is_skip_checking"] for addition in environment.additions)
    assert environment.service.instance.recheck_torrents.call_count == 2


def test_preview_verifies_metadata_without_downloader_writes(environment):
    """预览通过相同文件核验入口，始终保持下载器只读。"""
    task, result = execute(environment, preview=True)
    assert task["matched"] == 2
    assert task["added"] == 0
    assert environment.additions == []
    assert "可添加" in result["items"][0]["message"]
    environment.service.instance.recheck_torrents.assert_not_called()


def test_submission_idempotent_and_reload_interrupts_queued_work(environment):
    """重复请求复用任务，重载后旧回调不能开始查询。"""
    first = reseed.start(environment.plugin, "same", True)
    second = reseed.start(environment.plugin, "same", True)
    assert first["task_id"] == second["task_id"]
    assert len(environment.jobs) == 1
    with pytest.raises(ValueError):
        reseed.start(environment.plugin, "same", False)
    reseed.recover(environment.plugin)
    reseed.run(environment.plugin, first["task_id"])
    assert reseed.status(environment.plugin)["status"] == "interrupted"
    assert environment.additions == []


def test_all_completed_sources_beyond_500_are_scanned(environment, monkeypatch):
    """自动扫描覆盖超过旧工具上限的完整任务，包括暂停任务。"""
    template = dict(environment.rows[environment.source_hash])
    for index in range(510):
        content = torrent(f"source-{index}".encode())
        identity = pieces.torrent_metadata(content)["hash"]
        environment.contents[identity] = content
        environment.rows[identity] = dict(template, hash=identity)
    monkeypatch.setattr(pieces, "query_site", lambda site, hashes: ({}, 0, ""))
    task, _ = execute(environment, preview=True)
    assert task["scanned"] == 511


@pytest.mark.parametrize("change", ["files", "pieces", "layout", "split"])
def test_unverifiable_data_never_adds(environment, monkeypatch, change):
    """实际重命名、元数据差异和主辅分离缺少数据证明均拒绝添加。"""
    if change == "files":
        environment.service.instance.get_files = lambda identity: [{"name": "renamed.mkv", "size": 5}]
    elif change == "pieces":
        monkeypatch.setattr(reseed, "request_pieces_torrent", lambda *_: torrent(b"target").replace(b"a" * 20, b"b" * 20))
    elif change == "layout":
        monkeypatch.setattr(reseed, "request_pieces_torrent", lambda *_: torrent(b"target", name=b"other.mkv"))
    else:
        environment.plugin._iyuu_auto_downloader = "missing-target"
    task, _ = execute(environment)
    assert task["failed"] > 0
    assert environment.additions == []


def test_cancel_after_query_prevents_addition(environment, monkeypatch):
    """查询回包时取消，后续下载和写入均停止。"""
    def query(site, hashes):
        """在模拟外部回包边界请求取消。"""
        reseed.stop(environment.plugin)
        return {hashes[0]: "1"}, 0, ""
    monkeypatch.setattr(pieces, "query_site", query)
    task, _ = execute(environment)
    assert task["status"] == "cancelled"
    assert environment.additions == []


def test_auto_does_not_fan_out_when_iyuu_fails(environment, monkeypatch):
    """IYUU 失败只记错误与冷却，不请求 Pieces 站点。"""
    environment.plugin._reseed_mode = "auto"
    environment.plugin._iyuu_token = "test-token"
    environment.plugin.iyuu_helper = SimpleNamespace(ensure_ready=lambda: (True, ""), retry_after=900)
    query = Mock()
    monkeypatch.setattr(pieces, "query_site", query)
    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", lambda *args, **kwargs: "HTTP 429")
    task, _ = execute(environment)
    assert task["failed"] == 1
    query.assert_not_called()
    assert any(value > 0 for value in environment.stored[reseed.LIMITS_KEY].values())


def test_auto_supplements_only_missing_sites(environment, monkeypatch):
    """IYUU 成功响应已有站点候选时只补查其余站点。"""
    environment.plugin._reseed_mode = "auto"
    environment.plugin._iyuu_token = "test-token"
    environment.plugin.iyuu_helper = SimpleNamespace(ensure_ready=lambda: (True, ""))
    called = []
    def query(*args, **kwargs):
        """记录 IYUU 对站点 A 的成功命中。"""
        kwargs["matched_sites"][environment.source_hash] = {"1"}
    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", query)
    monkeypatch.setattr(pieces, "query_site", lambda site, hashes: (called.append(site["name"]) or {}, 0, ""))
    execute(environment, preview=True)
    assert called == ["站点B"]


def test_status_does_not_query_downloaders(environment):
    """轮询状态及结果只访问本实例存储。"""
    execute(environment, preview=True)
    environment.service.instance.get_torrents = Mock(side_effect=AssertionError("unexpected RPC"))
    assert reseed.status(environment.plugin)["status"] == "completed"


@pytest.mark.parametrize("text", ["站点A:secret:0", "站点A:secret:no", "missing:secret", "站点A:one\n站点A:two"])
def test_bad_site_configuration_is_rejected_without_credentials(environment, text):
    """错误提示不能包含输入的凭据正文。"""
    with pytest.raises(ValueError) as result:
        pieces.parse_site_keys(text, environment.sites)
    assert "secret" not in str(result.value)


def test_duplicate_names_and_changed_domains_are_not_guessed(environment, monkeypatch):
    """站名重名和站点绑定变更都不能把凭据发给推测的目标。"""
    with pytest.raises(ValueError):
        pieces.parse_site_keys("站点A:secret", environment.sites + [dict(environment.sites[0], id=3)])
    resolved = pieces.parse_site_keys("站点A:secret:3", environment.sites)
    assert resolved[0]["id"] == 1 and resolved[0]["interval"] == 3


def test_info_hash_uses_original_dictionary_bytes():
    """非排序 info 字典仍按原始编码计算 hash，避免重编码产生错误身份。"""
    raw = b"d6:pieces20:aaaaaaaaaaaaaaaaaaaa4:name9:movie.mkv6:lengthi5e12:piece lengthi16ee"
    assert pieces.torrent_metadata(b"d4:info" + raw + b"e")["hash"] == hashlib.sha1(raw).hexdigest()


@pytest.mark.parametrize("name", [b"../movie", b"/movie", b"..", b"a\\b"])
def test_unsafe_torrent_paths_rejected(name):
    """路径穿越和绝对路径不会进入添加流程。"""
    with pytest.raises(ValueError):
        pieces.torrent_metadata(torrent(name=name))


@pytest.mark.parametrize("http_status,payload,message", [
    (200, {"data": {}}, ""), (401, {}, "认证"), (429, {}, "限流"),
    (200, {"data": []}, "格式"), (200, {"data": {"unknown": 1}}, "格式"),
    (200, {"ret": 0, "data": {}}, ""), (200, {"ret": "0", "data": {}}, ""),
    (200, {"ret": -1, "data": {}}, "业务"), (200, {"ret": "-1", "data": {}}, "业务"),
    (200, {"ret": False, "data": {}}, "业务"), (404, {}, "HTTP 404"),
])
def test_query_distinguishes_failure_and_empty_match(monkeypatch, http_status, payload, message):
    """协议错误、鉴权失败、限流和正常空结果分别返回。"""
    response = SimpleNamespace(status_code=http_status, headers={"Retry-After": "120"}, json=lambda: payload)
    monkeypatch.setattr(pieces, "request_pieces_res", lambda *args: response)
    matches, cooldown, error = pieces.query_site({}, ["a" * 40])
    assert matches == {}
    assert message in error
    assert bool(cooldown) == bool(message)


def test_pieces_cannot_bypass_iyuu_activation(environment):
    """配置 Passkey 不会绕过 IYUU 开关、Token 或下载器门禁。"""
    assert is_iyuu_active(environment.plugin)
    for name, value in [("_iyuu_token", ""), ("_iyuu_downloaders", []), ("_iyuu_enabled", False)]:
        original = getattr(environment.plugin, name)
        setattr(environment.plugin, name, value)
        assert not is_iyuu_active(environment.plugin)
        setattr(environment.plugin, name, original)
    environment.plugin._iyuu_token = ""
    with pytest.raises(ValueError, match="IYUU Token"):
        reseed.start(environment.plugin)


def test_failed_registration_is_visible_and_allows_another_request(environment, monkeypatch):
    """调度器异常不会把任务永久卡在排队状态。"""
    monkeypatch.setattr(scheduler, "add_plugin_once_job", Mock(side_effect=RuntimeError("offline")))
    result = reseed.start(environment.plugin, "failed-request")
    assert result["status"] == "failed"
    assert reseed.start(environment.plugin, "next-request")["task_id"] != result["task_id"]


def test_recheck_never_starts_incomplete_pieces_and_returns_final_status(environment):
    """即便下载器状态误报可做种，Pieces 仍要求进度达到 100%。"""
    task, _ = execute(environment)
    target_hash = pieces.torrent_metadata(torrent(b"target"))["hash"]
    row = environment.rows[target_hash]
    row.update(state="stoppedUP", progress=0.9)
    environment.service.instance.start_torrents = Mock(return_value=True)
    queue = recheck.load_seed_recheck_queue(environment.plugin)
    recheck.process_seed_recheck_once(environment.plugin, queue)
    environment.service.instance.start_torrents.assert_not_called()
    row["progress"] = 1
    recheck.process_seed_recheck_once(environment.plugin, queue)
    environment.service.instance.start_torrents.assert_called_once()
    result = reseed.results(environment.plugin, task["task_id"])
    assert result["items"][0]["state"] == "seeding"


def test_result_pages_cover_all_rows_without_duplicates(environment):
    """分页结果完整覆盖边界，不把状态回包扩展成大结果。"""
    task = reseed.start(environment.plugin, "pages", True)
    execution = reseed.ReseedRun(environment.plugin, task)
    for index in range(215):
        execution.record("skipped", str(index))
    execution.flush()
    messages = []
    for offset in range(0, 215, 50):
        messages.extend(item["message"] for item in reseed.results(environment.plugin, task["task_id"], offset, 50)["items"])
    assert messages == [str(index) for index in range(215)]
    assert "items" not in reseed.status(environment.plugin)


def test_query_cooldown_survives_new_task(environment, monkeypatch):
    """站点限流持久化后，下一轮手动运行仍遵守冷却。"""
    query = Mock(return_value=({}, 900, "站点限流"))
    monkeypatch.setattr(pieces, "query_site", query)
    execute(environment, preview=True)
    assert len(environment.stored[reseed.LIMITS_KEY]) == 2
    current = reseed.start(environment.plugin, "next", True)
    execution = reseed.ReseedRun(environment.plugin, current)
    assert all(expiry > current["created_at"] for expiry in environment.stored[reseed.LIMITS_KEY].values())
    assert execution.cancel.is_set() is False


def test_add_timeout_reads_back_real_target_without_resubmitting(environment):
    """下载器已接收而回执超时时按真实 hash 完成后处理。"""
    original_add = environment.service.instance.add_torrent
    def add_then_timeout(**kwargs):
        """模拟服务端提交成功后连接超时。"""
        original_add(**kwargs)
        raise TimeoutError("reply lost")
    environment.service.instance.add_torrent = add_then_timeout
    task, _ = execute(environment)
    assert task["added"] == 1
    assert len(environment.additions) == 1
    assert environment.stored["iyuu_pending_postprocess"] == {}


@pytest.mark.parametrize("legacy_mode", ["iyuu", "pieces", "auto"])
def test_passkeys_alone_control_supplement_regardless_of_legacy_mode(environment, legacy_mode):
    """旧模式设置不再影响 IYUU 主、Pieces 辅的固定顺序。"""
    environment.plugin._reseed_mode = legacy_mode
    task = reseed.start(environment.plugin, "configured-pieces", True)
    assert task["mode"] == "auto"
    reseed.recover(environment.plugin)
    environment.plugin._pieces_site_keys = ""
    task = reseed.start(environment.plugin, "without-pieces", True)
    assert task["mode"] == "iyuu"


def test_run_uses_configured_supplement_and_smaller_limits(environment):
    """后台任务沿用配置补查，并可缩小本轮数量。"""
    environment.plugin._reseed_mode = "iyuu"
    task = reseed.start(environment.plugin, "one-pieces", False,
                        addition_limit=1, source_limit=100)
    assert task["mode"] == "auto"
    assert task["addition_limit"] == 1
    assert task["source_limit"] == 100
    args, kwargs = environment.jobs[-1]
    args[2](**kwargs["func_kwargs"])
    current = reseed.status(environment.plugin)
    assert current["submission_count"] == current["added"] == 1
    assert environment.plugin._reseed_mode == "iyuu"
    assert environment.plugin.update_config.call_args.kwargs["config"].get("reseed_mode") is None


def test_pending_postprocess_consumes_submission_limit(environment, monkeypatch):
    """添加成功但校验登记失败仍占名额，后续候选不会绕过数量限制。"""
    monkeypatch.setattr(reseed, "request_pieces_torrent", lambda site, identity: torrent(str(site["id"]).encode()))
    environment.service.instance.recheck_torrents = Mock(return_value=False)
    environment.plugin._reseed_max_additions = 1
    task, _ = execute(environment)
    assert task["submission_count"] == 1
    assert len(environment.additions) == 1
    assert environment.stored["iyuu_pending_postprocess"]


def test_source_limit_bounds_preview_and_registration_fingerprint(environment, monkeypatch):
    """小范围预览自动截取来源，重复请求不能更换上限。"""
    template = dict(environment.rows[environment.source_hash])
    content = torrent(b"second")
    identity = pieces.torrent_metadata(content)["hash"]
    environment.contents[identity] = content
    environment.rows[identity] = dict(template, hash=identity)
    task = reseed.start(environment.plugin, "limited-preview", True, source_limit=1)
    with pytest.raises(ValueError):
        reseed.start(environment.plugin, "limited-preview", True, source_limit=2)
    reseed.run(environment.plugin, task["task_id"])
    assert reseed.status(environment.plugin)["scanned"] == 1


def add_sources(environment, count=250):
    """构造排序可预测的来源，模拟两批之后仍有数据等待扫描。"""
    template = dict(environment.rows[environment.source_hash])
    environment.rows.clear()
    for index in range(count):
        identity = f"{index + 1:040x}"
        environment.rows[identity] = dict(template, hash=identity)
    environment.plugin._pieces_site_keys = ""


def test_transient_query_retries_then_continues(environment, monkeypatch):
    """第二批短暂断网后重试同一批，并继续覆盖剩余来源。"""
    add_sources(environment)
    calls = []

    def query(plugin, sources, *_args, **_kwargs):
        """第二次调用模拟网络失败，其余批次成功返回空结果。"""
        calls.append([source["hash"] for source in sources])
        return "请求IYUU失败，未获取到返回信息" if len(calls) == 2 else None

    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", query)
    task, _ = execute(environment)
    assert task["status"] == "completed"
    assert task["scanned"] == 250 and task["query_retries"] == 1
    assert calls[1] == calls[2] and len(calls[-1]) == 50
    assert environment.stored[reseed.PROGRESS_KEY] == {}


def test_exhausted_query_resumes_failed_batch_after_reload(environment, monkeypatch):
    """失败三次只保留上一完整批次；新实例从失败批续扫且完整轮次重置。"""
    add_sources(environment)
    calls = []

    def query(plugin, sources, *_args, **_kwargs):
        """记录输入；第一批成功，其余请求暂时失败。"""
        calls.append([source["hash"] for source in sources])
        return None if len(calls) == 1 else "HTTP 503"

    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", query)
    task, _ = execute(environment)
    assert task["status"] == "partial" and task["query_retries"] == 2
    assert len(calls) == 4 and task["scanned"] == 200
    assert environment.stored[reseed.PROGRESS_KEY]["services"]["QB"]["after"] == f"{100:040x}"
    # 下一轮只复用持久状态，不依赖旧 worker 或事件；冷却已经经过。
    environment.stored[reseed.LIMITS_KEY] = {}
    environment.plugin = SimpleNamespace(**vars(environment.plugin))
    environment.plugin._run_reseed_task = lambda task_id: reseed.run(environment.plugin, task_id)
    seen = []
    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", lambda p, sources, *a, **kw: seen.extend(sources))
    task, _ = execute(environment)
    assert task["resumed"] is True and task["scanned"] == 150
    assert seen[0]["hash"] == f"{101:040x}" and len(seen) == 150
    assert environment.stored[reseed.PROGRESS_KEY] == {}
    seen.clear()
    task, _ = execute(environment)
    assert task["scanned"] == 250 and seen[0]["hash"] == f"{1:040x}"


@pytest.mark.parametrize("error", ["HTTP 429", "IYUU 请求限流，等待冷却", "请求缺少token", "HTTP 401", "HTTP 404"])
def test_non_retryable_query_keeps_supplement_blocked(environment, monkeypatch, error):
    """认证、限流及永久 HTTP 错误只尝试一次，也不扇出 Pieces 请求。"""
    query = Mock(return_value=error)
    supplement = Mock()
    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", query)
    monkeypatch.setattr(pieces, "query_site", supplement)
    task, _ = execute(environment)
    assert task["status"] == "partial"
    assert query.call_count == 1 and not task.get("query_retries")
    supplement.assert_not_called()


def test_stop_during_retry_does_not_advance_checkpoint(environment, monkeypatch):
    """重试等待期间取消，不发出第二次查询且保持来源可重查。"""
    query = Mock(return_value="请求IYUU失败，未获取到返回信息")
    waits = []

    def wait(run, *_args):
        """在第一次重试等待时模拟用户停止。"""
        waits.append(True)
        if len(waits) == 2:
            reseed.stop(run.plugin)
        return not run.stopped()

    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", query)
    monkeypatch.setattr(reseed.ReseedRun, "wait_budget", wait)
    task, _ = execute(environment)
    assert task["status"] == "cancelled" and query.call_count == 1
    assert environment.stored[reseed.PROGRESS_KEY]["services"]["QB"]["after"] == ""


@pytest.mark.parametrize("change", ["preview", "small_run", "config", "binding", "removed_source"])
def test_checkpoint_scope_and_source_changes(environment, monkeypatch, change):
    """预览不消费断点；配置与连接变更重扫；源列表变化不依赖旧数组下标。"""
    add_sources(environment)
    query = Mock(side_effect=[None, "HTTP 401"])
    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", query)
    execute(environment)
    saved = deepcopy(environment.stored[reseed.PROGRESS_KEY])
    environment.stored[reseed.LIMITS_KEY] = {}
    seen = []
    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", lambda p, sources, *a, **kw: seen.extend(sources))
    if change == "config":
        environment.plugin._iyuu_sites = [1]
    elif change == "binding":
        environment.service.type = "new-binding"
        monkeypatch.setattr(reseed, "_completed_sources", lambda s: list(environment.rows.values()))
        monkeypatch.setattr(iyuu, "_iyuu_candidates", lambda *a, **kw: [{"hash": h} for h in environment.rows])
    elif change == "removed_source":
        environment.rows.pop(f"{100:040x}")
    if change == "small_run":
        task = reseed.start(environment.plugin, "small", source_limit=1)
        reseed.run(environment.plugin, task["task_id"])
    else:
        execute(environment, preview=change == "preview")
    if change in ("preview", "small_run"):
        assert environment.stored[reseed.PROGRESS_KEY] == saved
    expected_first = 101 if change == "removed_source" else 1
    assert seen[0]["hash"] == f"{expected_first:040x}"


def test_cap_keeps_unfinished_batch_for_next_run(environment, monkeypatch):
    """新增限额命中时不越过该批剩余候选，下轮仍能重新查询。"""
    add_sources(environment, 150)
    environment.plugin._reseed_max_additions = 1

    def query(plugin, sources, *_args, **_kwargs):
        """模拟本批已经消耗一次实际提交名额。"""
        plugin._reseed_execution.task["submission_count"] = 1

    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", query)
    task, _ = execute(environment)
    assert task["submission_count"] == 1 and task["scanned"] == 100
    assert environment.stored[reseed.PROGRESS_KEY]["services"]["QB"]["after"] == ""


@pytest.mark.parametrize("payload", [None, [], "bad-json"])
def test_malformed_iyuu_response_is_retryable(monkeypatch, payload):
    """错误页和无效 JSON 不抛出未分类异常，也不伪装成没有候选。"""
    from app.plugins.downloadmanagerlocal import iyuu_helper

    response = SimpleNamespace(status_code=200, json=Mock(return_value=payload))
    if payload == "bad-json":
        response.json.side_effect = ValueError("invalid json")
    monkeypatch.setattr(iyuu_helper, "request_post_res", lambda *a, **kw: response)
    helper = iyuu_helper.IyuuHelper("test")
    value, error = helper._IyuuHelper__request_iyuu("/query", "post")
    assert value is None and error == "IYUU 响应格式无效"


@pytest.mark.parametrize("status_code,attempts", [(401, 1), (403, 1), (404, 1), (408, 3), (429, 1), (503, 3)])
@pytest.mark.parametrize("body", [b"<html>error</html>", b'{"code": 0, "data": {}}'])
def test_http_errors_keep_their_retry_classification(environment, monkeypatch, status_code, attempts, body):
    """实际 HTTP 错误状态优先于 HTML 或伪成功正文，不误重试认证错误。"""
    import httpx
    from app.plugins.downloadmanagerlocal import iyuu_helper

    response = httpx.Response(status_code, content=body, headers={"Retry-After": "60"})
    monkeypatch.setattr(iyuu_helper, "request_post_res", lambda *a, **kw: response)
    helper = iyuu_helper.IyuuHelper("test")
    value, error = helper._IyuuHelper__request_iyuu("/query", "post")
    assert value is None and error
    query = Mock(return_value=error)
    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", query)
    task, _ = execute(environment)
    assert task["status"] == "partial" and query.call_count == attempts


def test_known_target_skips_download_and_reports_duplicate(environment, monkeypatch):
    """已完成目标在本轮快照中存在时，不再下载 torrent 或逐候选调用下载器。"""
    environment.plugin._pieces_site_keys = ""
    download = Mock()

    def query(plugin, sources, service, *_args, **kwargs):
        """模拟 IYUU 返回已在本机的跨站候选。"""
        kwargs["candidate_handler"]({"info_hash": environment.source_hash, "torrent_id": 1},
                                    sources[0], service, environment.sites[0])

    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", query)
    monkeypatch.setattr(iyuu, "iyuu_download_torrent", download)
    task, result = execute(environment)
    assert task["skipped"] == 1 and result["items"][0]["message"] == "目标任务已存在"
    download.assert_not_called()


def test_completed_downloader_is_not_repeated_when_next_fails(environment, monkeypatch):
    """第二下载器查询失败后，下轮跳过已完成的第一个下载器。"""
    environment.plugin._pieces_site_keys = ""
    second = SimpleNamespace(name="QB2", type="qbittorrent", instance=environment.service.instance)
    monkeypatch.setattr(reseed, "get_downloader_services", lambda **kw: {"QB": environment.service, "QB2": second})
    calls = []

    def query(plugin, sources, service, *_args, **_kwargs):
        """仅第二下载器的请求返回配置错误。"""
        calls.append(service.name)
        return "HTTP 401" if service.name == "QB2" else None

    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", query)
    execute(environment)
    assert calls == ["QB", "QB2"]
    assert environment.stored[reseed.PROGRESS_KEY]["services"]["QB"]["done"] is True
    environment.stored[reseed.LIMITS_KEY] = {}
    calls.clear()
    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", lambda p, sources, service, *a, **kw: calls.append(service.name))
    # append 的返回值为 None，代表查询正常完成。
    task, _ = execute(environment)
    assert calls == ["QB2"] and task["status"] == "completed"
    assert environment.stored[reseed.PROGRESS_KEY] == {}


def test_offline_downloader_does_not_starve_other_source(environment, monkeypatch):
    """一个下载器不可达不饿死其他来源，也不清掉尚未完成的断点。"""
    environment.plugin._pieces_site_keys = ""
    offline = SimpleNamespace(name="A", type="qbittorrent", instance=SimpleNamespace(is_inactive=lambda: True))
    monkeypatch.setattr(reseed, "get_downloader_services", lambda **kw: {"A": offline, "QB": environment.service})
    query = Mock(return_value=None)
    monkeypatch.setattr(iyuu, "iyuu_seed_torrents", query)
    task, _ = execute(environment)
    assert task["failed"] == 1 and query.call_count == 1
    assert environment.stored[reseed.PROGRESS_KEY]["services"]["QB"]["done"] is True
    assert "A" not in environment.stored[reseed.PROGRESS_KEY]["services"]


def test_retry_wait_respects_persisted_cooldown_and_cancel(environment, monkeypatch):
    """实际等待入口尊重冷却时长；取消后不能预约下一次请求。"""
    monkeypatch.undo()
    task = {"task_id": "wait", "preview": False}
    environment.stored[reseed.TASK_KEY] = task
    environment.plugin._reseed_cancel = Mock()
    environment.plugin._reseed_cancel.is_set.return_value = False
    environment.plugin._reseed_cancel.wait.return_value = False
    monkeypatch.setattr(reseed.time, "time", lambda: 100)
    execution = reseed.ReseedRun(environment.plugin, task)
    environment.stored[reseed.LIMITS_KEY] = {"iyuu": 115}
    assert execution.wait_budget("iyuu", 15) is True
    execution.cancel.wait.assert_called_once_with(15)
    assert environment.stored[reseed.LIMITS_KEY]["iyuu"] == 115
    execution.cancel.wait.return_value = True
    assert execution.wait_budget("iyuu", 15) is False
    environment.stored[reseed.LIMITS_KEY]["iyuu"] = 1000
    execution.cancel.wait.reset_mock()
    assert execution.wait_budget("iyuu", 15) is False
    execution.cancel.wait.assert_not_called()
