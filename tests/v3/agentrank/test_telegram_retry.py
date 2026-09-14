"""异常通知重试的归属、幂等和后台生命周期回归。"""

import asyncio
import copy
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from app.plugins.agentrank import AgentRank
from app.plugins.agentrank.model.run import RecommendationRun
from app.plugins.agentrank.service.notification import NotificationService
from app.plugins.agentrank.service.runtime import AgentRankRuntime
from app.plugins.agentrank.service.telegram_interaction import TelegramSelectionService
from app.plugins.agentrank.service.telegram_retry import TelegramRunRetryService
from app.plugins.agentrank.storage.repository import AgentRankRepository

PROFILE = "emby:home:user-1"
OTHER_PROFILE = "emby:remote:user-1"


class FakeMessageChain:
    """区分真正编辑与普通发送，允许模拟 Telegram 编辑失败。"""

    def __init__(self):
        """记录编辑调用及可控制的结果。"""
        self.edits = []
        self.edit_result = True
        self.edit_error = None
        self.progress_edited = threading.Event()

    def run_module(self, method, **kwargs):
        """只允许编辑接口，禁止用普通发送冒充消息更新。"""
        assert method == "edit_message"
        self.edits.append(copy.deepcopy(kwargs))
        if self.edit_error is not None:
            raise self.edit_error
        if "正在更新画像" in kwargs.get("text", ""):
            self.progress_edited.set()
        return self.edit_result


class FakePlugin:
    """以独立内存数据和消息记录代替宿主副作用。"""

    def __init__(self):
        """准备两个同名但身份不同的画像。"""
        self.data = {}
        self.messages = []
        self.chain = FakeMessageChain()
        self.enabled = True
        self._config = {
            "enabled": True,
            "notify": True,
            "emby_identities": [
                {"server_name": server, "user_id": "user-1", "username": "Alice"}
                for server in ("home", "remote")
            ],
            "default_profile_id": PROFILE,
        }

    def get_state(self):
        """返回可由测试切换的插件启用状态。"""
        return self.enabled

    def get_data(self, key=None):
        """模拟宿主按键读取和数据枚举。"""
        if key is None:
            return [
                {"key": name, "value": copy.deepcopy(value)}
                for name, value in self.data.items()
            ]
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key, value):
        """保存独立副本，避免对象别名掩盖持久化错误。"""
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key):
        """删除本测试实例的指定数据。"""
        self.data.pop(key, None)

    def post_message(self, **kwargs):
        """记录消息参数而不连接 Telegram。"""
        self.messages.append(kwargs)


@pytest.fixture
def setup_retry(monkeypatch):
    """构造真实插件服务与仓库，仅替换宿主通知和运行任务。"""
    monkeypatch.setattr(
        TelegramSelectionService,
        "_notification_sources",
        staticmethod(lambda mtype: ["Telegram"]),
    )
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    plugin._repository = repository
    calls = []

    def accept(profile_id):
        """记录被受理的画像。"""
        calls.append(profile_id)
        return {"accepted": True}

    service = TelegramRunRetryService(
        plugin,
        repository,
        plugin._config,
        accept,
        target_adapter=SimpleNamespace(resolve_userid=lambda username: "1001"),
    )
    return plugin, repository, service, calls


def _notice(service, profile_id=PROFILE, run_id="failed-run"):
    """建立一次通知并返回宿主回调事件。"""
    NotificationService(service._plugin, retry_service=service).send_failure(
        "Alice",
        "profile_agent_failed",
        run_id,
        "Agent 调用失败",
        True,
        profile_id=profile_id,
    )
    buttons = service._plugin.messages[-1]["buttons"]
    callback = buttons[0][0]["callback_data"]
    assert len(callback.encode("utf-8")) <= 64
    assert profile_id not in callback
    return {
        "plugin_id": service._plugin.__class__.__name__,
        "channel": "Telegram",
        "text": callback.split("|", 1)[1],
        "userid": "1001",
        "source": "Telegram",
        "original_message_id": 41 + len(service._plugin.messages),
        "original_chat_id": "1001",
    }


def _session(repository, event):
    """读取事件指向的持久化重试状态。"""
    return repository.load_telegram_retry_session(event["text"].split(":")[1])


def test_failure_notice_adds_button_without_changing_original_reason(setup_retry):
    """画像失败通知同时保留错误摘要和原榜单状态。"""
    plugin, repository, service, _ = setup_retry
    NotificationService(plugin, retry_service=service).send_failure(
        "Alice",
        "profile_agent_failed",
        "failed-run",
        "画像 Agent 调用失败",
        True,
        profile_id=PROFILE,
    )
    assert len(plugin.messages) == 1
    message = plugin.messages[0]
    assert "画像 Agent 调用失败" in message["text"]
    assert "旧榜单：已保留" in message["text"]
    assert message["buttons"][0][0]["text"] == "🔄 重试"
    token = message["buttons"][0][0]["callback_data"].split(":")[1]
    assert repository.load_telegram_retry_session(token).profile_id == PROFILE


def test_retry_is_bound_to_recipient_and_survives_service_recreation(setup_retry):
    """越权点击不改原卡片，重建服务后重复点击仍只运行一次。"""
    plugin, repository, service, calls = setup_retry
    event = _notice(service)
    assert service.handle_callback({**event, "userid": "9999"}) is True
    assert calls == []
    assert plugin.chain.edits == []
    assert len(plugin.messages) == 1
    assert _session(repository, event).status == "open"

    assert service.handle_callback(event) is True
    assert calls == [PROFILE]
    assert _session(repository, event).status == "submitted"
    assert plugin.chain.edits[-1]["message_id"] == "42"
    assert plugin.chain.edits[-1]["buttons"] == []
    assert "状态：重试中" in plugin.chain.edits[-1]["text"]
    assert len(plugin.messages) == 1

    recreated = TelegramRunRetryService(
        plugin,
        AgentRankRepository(plugin),
        plugin._config,
        service._retry_handler,
        target_adapter=service._target_adapter,
    )
    recreated.handle_callback(event)
    assert calls == [PROFILE]
    assert len(plugin.messages) == 1


@pytest.mark.parametrize("change", ["expired", "new_run", "new_notice", "cleared"])
def test_expired_or_superseded_notice_cannot_start_run(setup_retry, change):
    """过期、较新结果、较新通知和已清理会话都不能触发重试。"""
    _, repository, service, calls = setup_retry
    event = _notice(service)
    if change == "expired":
        service._now_factory = lambda: datetime.now(timezone.utc) + timedelta(days=2)
    elif change == "new_run":
        repository.append_run(
            RecommendationRun(
                profile_id=PROFILE, run_id="new-success", status="success"
            )
        )
    elif change == "new_notice":
        _notice(service, run_id="new-failure")
    else:
        repository.reset_all_profile_data(PROFILE)
    service.handle_callback(event)
    assert calls == []


@pytest.mark.parametrize("first_result", ["busy", "exception"])
def test_unaccepted_retry_keeps_button_and_can_be_submitted_later(
    setup_retry, first_result
):
    """忙碌和受理前异常不消耗按钮，恢复后允许再次提交。"""
    plugin, repository, service, calls = setup_retry
    event = _notice(service)
    accepted_handler = service._retry_handler

    def refuse(profile_id):
        """模拟已在运行或后台队列暂时不可用。"""
        if first_result == "exception":
            raise RuntimeError("queue unavailable")
        return {"accepted": False, "status": "running"}

    service._retry_handler = refuse
    service.handle_callback(event)
    assert _session(repository, event).status == "open"
    assert plugin.chain.edits[-1]["buttons"]
    assert len(plugin.messages) == 1
    assert calls == []
    service._retry_handler = accepted_handler
    service.handle_callback(event)
    assert calls == [PROFILE]


def test_two_service_instances_cannot_claim_same_retry(setup_retry):
    """跨服务并发回调通过仓库原子状态领取去重。"""
    plugin, repository, service, calls = setup_retry
    event = _notice(service)
    entered, release = threading.Event(), threading.Event()

    def blocked_accept(profile_id):
        """暂停受理返回，制造另一实例同时回调的窗口。"""
        calls.append(profile_id)
        entered.set()
        assert release.wait(3)
        return {"accepted": True}

    service._retry_handler = blocked_accept
    other = TelegramRunRetryService(
        plugin,
        repository,
        plugin._config,
        blocked_accept,
        target_adapter=service._target_adapter,
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(service.handle_callback, event)
        try:
            assert entered.wait(3)
            other.handle_callback(event)
            assert calls == [PROFILE]
        finally:
            release.set()
        assert future.result(timeout=3)


def test_profile_reset_preserves_other_profiles_retry(setup_retry):
    """同名用户的两个画像会话隔离，重置仅清理目标画像。"""
    _, repository, service, calls = setup_retry
    first = _notice(service)
    second = _notice(service, OTHER_PROFILE)
    repository.reset_all_profile_data(PROFILE)
    assert _session(repository, first) is None
    assert _session(repository, second).profile_id == OTHER_PROFILE
    service.handle_callback(second)
    assert calls == [OTHER_PROFILE]


@pytest.mark.parametrize(
    "reason", ["no_target", "no_telegram", "button_error", "feedback"]
)
def test_notification_falls_back_to_text_without_misrouting(
    setup_retry, monkeypatch, reason
):
    """无 Telegram 目标、按钮异常及反馈失败保留原文字通知。"""
    plugin, _, service, _ = setup_retry
    if reason == "no_target":
        service._target_adapter.resolve_userid = lambda username: None
    elif reason == "no_telegram":
        monkeypatch.setattr(
            TelegramSelectionService,
            "_notification_sources",
            staticmethod(lambda mtype: []),
        )
    elif reason == "button_error":
        service._token_factory = lambda: "bad:token"
    NotificationService(plugin, retry_service=service).send_failure(
        "Alice",
        "failed",
        "failed-run",
        "原始原因",
        True,
        profile_id="" if reason == "feedback" else PROFILE,
    )
    assert len(plugin.messages) == 1
    assert "原始原因" in plugin.messages[0]["text"]
    assert "buttons" not in plugin.messages[0]


@pytest.mark.parametrize(
    "field,value",
    [
        ("plugin_id", "AnotherPlugin"),
        ("channel", "WeChat"),
        ("text", "arr:token:delete"),
    ],
)
def test_foreign_callbacks_are_ignored(setup_retry, field, value):
    """拒绝其他实例、渠道和不受支持的回调动作。"""
    plugin, _, service, calls = setup_retry
    event = _notice(service)
    assert service.handle_callback({**event, field: value}) is False
    assert calls == []
    assert len(plugin.messages) == 1
    assert plugin.chain.edits == []


def _runtime(plugin, orchestrator, service):
    """跳过无关 Agent 依赖组装，使用真实运行时和通知服务。"""
    repository = plugin._repository
    plugin._repository = None
    runtime = AgentRankRuntime(plugin, plugin._config, orchestrator, lambda cron: cron)
    plugin._repository = repository
    plugin._runtime = runtime
    runtime.retry_service = service
    runtime.notification_service = NotificationService(plugin, retry_service=service)
    service._retry_handler = runtime.start_retry
    return runtime


@pytest.mark.parametrize("unhandled", [False, True])
def test_sync_callback_updates_progress_and_failure_on_original_notice(
    setup_retry, unhandled
):
    """同步回调启动任务，阶段和再次失败全部编辑初始消息。"""
    plugin, _, service, _ = setup_retry
    entered, release = threading.Event(), threading.Event()
    sources = []

    class Orchestrator:
        """阻塞在可取消等待中的推荐编排替身。"""

        async def run(self, profile_id, config, *, trigger_reason=""):
            """记录真实触发来源，随后返回失败或抛出异常。"""
            sources.append((profile_id, trigger_reason))
            runtime._update_run_progress(
                {
                    "profile_id": profile_id,
                    "run_id": "retry-failed",
                    "stage": "profile",
                    "message": "正在更新画像",
                }
            )
            entered.set()
            while not release.is_set():
                await asyncio.sleep(0.01)
            if unhandled:
                raise RuntimeError("agent unavailable")
            return SimpleNamespace(
                status="profile_agent_failed",
                run_id="retry-failed",
                message="画像失败",
                board=None,
            )

    runtime = _runtime(plugin, Orchestrator(), service)
    runtime.retry_progress_interval_seconds = 0.02
    try:
        event = _notice(service)
        assert service.handle_callback(event)
        assert entered.wait(3)
        future = runtime._retry_jobs[PROFILE]
        assert runtime.start_retry(PROFILE) == {"accepted": False, "status": "running"}
        assert runtime.start_refresh(PROFILE)["active"] is True
        assert plugin.chain.progress_edited.wait(3)
        release.set()
        future.result(timeout=3)
        assert sources == [(PROFILE, "telegram_retry")]
        assert len(plugin.messages) == 1
        assert len(plugin.chain.edits) >= 3
        assert {edit["message_id"] for edit in plugin.chain.edits} == {"42"}
        assert {edit["source"] for edit in plugin.chain.edits} == {"Telegram"}
        assert {edit["chat_id"] for edit in plugin.chain.edits} == {"1001"}
        final = plugin.chain.edits[-1]
        assert final["buttons"][0][0]["text"] == "🔄 重试"
        assert "状态：重试中" not in final["text"]
        assert "retry-failed" in final["text"]
        assert final["buttons"][0][0]["callback_data"].endswith(":1")
        assert runtime.run_progress(PROFILE)["active"] is False
    finally:
        release.set()
        runtime.stop()


def test_stop_cancels_running_retry_and_queued_profile(setup_retry):
    """停止插件跨线程取消当前重试，并丢弃还未启动的另一画像任务。"""
    plugin, _, service, _ = setup_retry
    entered, cancelled = threading.Event(), threading.Event()
    calls = []

    class Orchestrator:
        """只等待取消，不执行外部工作。"""

        async def run(self, profile_id, config, *, trigger_reason=""):
            """保持任务运行，验证运行时停止清理。"""
            calls.append(profile_id)
            entered.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

    runtime = _runtime(plugin, Orchestrator(), service)
    try:
        first_event = _notice(service)
        assert service.handle_callback(first_event)
        assert entered.wait(3)
        running = runtime._retry_jobs[PROFILE]
        second_event = _notice(service, OTHER_PROFILE)
        assert service.handle_callback(second_event)
        queued = runtime._retry_jobs[OTHER_PROFILE]
        runtime.stop()
        runtime.stop()
        assert cancelled.wait(3)
        with pytest.raises(asyncio.CancelledError):
            running.result(timeout=3)
        assert queued.cancelled()
        assert calls == [PROFILE]
        assert runtime.run_progress(PROFILE)["active"] is False
        assert len(plugin.messages) == 2
        latest = {edit["message_id"]: edit for edit in plugin.chain.edits}
        assert all(
            "状态：已停止" in latest[message_id]["text"] for message_id in ("42", "43")
        )
        with pytest.raises(RuntimeError):
            runtime.start_retry(PROFILE)
    finally:
        runtime.stop()


def test_disabled_or_removed_profile_never_creates_worker(setup_retry):
    """插件停用或画像移出配置时拒绝重试而不启动线程。"""
    plugin, _, service, _ = setup_retry
    runtime = _runtime(plugin, SimpleNamespace(), service)
    try:
        plugin.enabled = False
        with pytest.raises(RuntimeError):
            runtime.start_retry(PROFILE)
        plugin.enabled = True
        with pytest.raises(ValueError):
            runtime.start_retry("emby:removed:user-1")
        assert runtime._retry_executor is None
    finally:
        runtime.stop()


def test_entrypoint_dispatches_retry_without_also_selecting_board():
    """已处理的重试回调不再进入榜单订阅处理器。"""
    plugin = AgentRank.__new__(AgentRank)
    plugin._enabled = True
    calls = []
    plugin._runtime = SimpleNamespace(
        retry_service=SimpleNamespace(
            handle_callback=lambda event: calls.append("retry") or True
        ),
        interaction_service=SimpleNamespace(
            handle_callback=lambda event: calls.append("selection")
        ),
    )
    plugin.message_action(SimpleNamespace(event_data={"plugin_id": "AgentRank"}))
    assert calls == ["retry"]


def test_failed_retry_rearms_same_message_and_old_callback_cannot_repeat(setup_retry):
    """一条消息连续重试，上一代按钮重放只能刷新状态而不能再次执行。"""
    plugin, repository, service, calls = setup_retry
    event = _notice(service)
    service.handle_callback(event)
    first_key = service.active_key(PROFILE)
    result = SimpleNamespace(
        status="ranking_agent_failed",
        run_id="second-run",
        message="排序失败",
        board=None,
    )
    assert service.finish(PROFILE, first_key, result)
    assert _session(repository, event).attempt == 1
    service.handle_callback(event)
    assert calls == [PROFILE]
    next_event = {
        **event,
        "text": plugin.chain.edits[-1]["buttons"][0][0]["callback_data"].split("|", 1)[
            1
        ],
    }
    service.handle_callback(next_event)
    assert calls == [PROFILE, PROFILE]
    second_key = service.active_key(PROFILE)
    edits_before = len(plugin.chain.edits)
    assert not service.update_progress(
        PROFILE, first_key, {"active": True, "message": "迟到的旧进度"}
    )
    assert not service.finish(PROFILE, first_key, result)
    assert len(plugin.chain.edits) == edits_before
    assert service.finish(
        PROFILE,
        second_key,
        SimpleNamespace(
            status="success",
            run_id="third-run",
            final_count=1,
            board=SimpleNamespace(recommendations=[SimpleNamespace(title="测试作品")]),
        ),
    )
    service.handle_callback(next_event)
    assert calls == [PROFILE, PROFILE]
    assert _session(repository, event).status == "completed"
    assert len(plugin.messages) == 1
    assert {edit["message_id"] for edit in plugin.chain.edits} == {"42"}
    assert "状态：已完成" in plugin.chain.edits[-1]["text"]
    assert "测试作品" in plugin.chain.edits[-1]["text"]
    assert all(
        "callback_data" not in button
        for row in plugin.chain.edits[-1]["buttons"]
        for button in row
    )


def test_identical_stage_snapshots_do_not_reedit_card(setup_retry):
    """时间戳变化不触发刷屏式编辑，只展示最新的真实阶段。"""
    plugin, _, service, _ = setup_retry
    service.handle_callback(_notice(service))
    key = service.active_key(PROFILE)
    snapshot = {"active": True, "run_id": "second-run", "message": "正在筛选候选"}
    assert service.update_progress(PROFILE, key, snapshot)
    count = len(plugin.chain.edits)
    assert service.update_progress(PROFILE, key, {**snapshot, "updated_at": "later"})
    assert len(plugin.chain.edits) == count
    assert len(plugin.messages) == 1


@pytest.mark.parametrize("failure", [False, RuntimeError("edit unavailable")])
def test_edit_failure_never_falls_back_to_new_notification(setup_retry, failure):
    """编辑入口失败不会新增消息，恢复后继续编辑相同消息。"""
    plugin, repository, service, calls = setup_retry
    event = _notice(service)
    plugin.chain.edit_result = False
    plugin.chain.edit_error = failure if isinstance(failure, Exception) else None
    service.handle_callback(event)
    key = service.active_key(PROFILE)
    assert calls == [PROFILE]
    assert not service.finish(
        PROFILE,
        key,
        SimpleNamespace(
            status="profile_agent_failed",
            run_id="second-run",
            message="画像失败",
            board=None,
        ),
    )
    assert _session(repository, event).status == "open"
    assert len(plugin.messages) == 1
    plugin.chain.edit_result = True
    plugin.chain.edit_error = None
    assert service.refresh_result(PROFILE, key)
    assert plugin.chain.edits[-1]["message_id"] == "42"
    assert plugin.chain.edits[-1]["buttons"]
    assert len(plugin.messages) == 1


@pytest.mark.parametrize("field", ["source", "original_message_id", "original_chat_id"])
def test_missing_original_identity_does_not_run_or_send_another_message(
    setup_retry, field
):
    """无法定位原消息时拒绝启动，避免后台运行却只能另发通知。"""
    plugin, repository, service, calls = setup_retry
    event = _notice(service)
    service.handle_callback({**event, field: None})
    assert calls == []
    assert _session(repository, event).status == "open"
    assert plugin.chain.edits == []
    assert len(plugin.messages) == 1


def test_legacy_callback_binds_message_and_conflicting_identity_is_rejected(
    setup_retry,
):
    """兼容未带代次的旧按钮，但不能改写已经绑定的原消息身份。"""
    plugin, repository, service, calls = setup_retry
    event = _notice(service)
    legacy = {**event, "text": event["text"].rsplit(":", 1)[0]}
    service.handle_callback(legacy)
    session = _session(repository, event)
    assert (session.message_id, session.chat_id, session.source) == (
        "42",
        "1001",
        "Telegram",
    )
    count = len(plugin.chain.edits)
    service.handle_callback({**event, "original_message_id": 999})
    assert calls == [PROFILE]
    assert len(plugin.chain.edits) == count
    assert len(plugin.messages) == 1


@pytest.mark.parametrize("transient_edit_error", [False, True])
def test_successful_retry_edits_result_without_sending_board_again(
    setup_retry, transient_edit_error
):
    """通知模式下成功结果仍更新原卡片，不另外发送榜单通知。"""
    plugin, _, service, _ = setup_retry
    plugin._config["action_mode"] = "notify"
    completed = threading.Event()

    class Orchestrator:
        """返回一次成功的最小榜单。"""

        async def run(self, profile_id, config, *, trigger_reason=""):
            """提供可在状态卡展示的最终推荐。"""
            return SimpleNamespace(
                status="success",
                run_id="success-run",
                final_count=1,
                board=SimpleNamespace(
                    recommendations=[SimpleNamespace(title="完成作品")]
                ),
            )

    runtime = _runtime(plugin, Orchestrator(), service)
    if transient_edit_error:
        dispatch = plugin.chain.run_module
        failures = [1]

        def flaky_edit(method, **kwargs):
            """模拟最终结果第一次编辑未获确认。"""
            result = dispatch(method, **kwargs)
            if "状态：已完成" in kwargs.get("text", "") and failures[0]:
                failures[0] -= 1
                return False
            return result

        plugin.chain.run_module = flaky_edit
    separate_boards = []
    runtime.notification_service.send_confirmation = lambda *args: (
        separate_boards.append(args)
    )
    original_finish = service.finish

    def finish(*args):
        """记录终态编辑完成，避免依赖快速任务的内部引用寿命。"""
        result = original_finish(*args)
        completed.set()
        return result

    service.finish = finish
    try:
        service.handle_callback(_notice(service))
        assert completed.wait(3)
        assert separate_boards == []
        assert len(plugin.messages) == 1
        assert "已完成" in plugin.chain.edits[-1]["text"]
        assert "完成作品" in plugin.chain.edits[-1]["text"]
        future = runtime._retry_jobs.get(PROFILE)
        if future is not None:
            future.result(timeout=3)
        final_edits = [
            edit for edit in plugin.chain.edits if "状态：已完成" in edit["text"]
        ]
        assert len(final_edits) == (2 if transient_edit_error else 1)
        assert len(plugin.messages) == 1
    finally:
        runtime.stop()


def test_progress_worker_coalesces_snapshots_at_five_second_interval(
    setup_retry, monkeypatch
):
    """使用受控时钟证明密集阶段变化只发布每个五秒窗口的最新状态。"""
    plugin, _, service, _ = setup_retry
    service.handle_callback(_notice(service))
    key = service.active_key(PROFILE)
    runtime = _runtime(plugin, SimpleNamespace(), service)

    async def scenario():
        """在两个发布时点之间注入多条阶段快照。"""
        entered, tick = asyncio.Event(), asyncio.Event()
        delays = []
        original_sleep = asyncio.sleep

        async def controlled_sleep(delay):
            """把真实五秒等待替换为可控的时间推进。"""
            delays.append(delay)
            entered.set()
            await tick.wait()
            tick.clear()

        monkeypatch.setattr(asyncio, "sleep", controlled_sleep)
        task = asyncio.create_task(runtime._refresh_retry_card(PROFILE, key))
        try:
            await entered.wait()
            for stage in ("profile", "candidate", "ranking"):
                runtime._update_run_progress(
                    {"profile_id": PROFILE, "run_id": "new-run", "stage": stage}
                )
            before = len(plugin.chain.edits)
            tick.set()
            for _ in range(100):
                if len(plugin.chain.edits) > before:
                    break
                await original_sleep(0.005)
            assert len(plugin.chain.edits) == before + 1
            assert "正在分析候选" in plugin.chain.edits[-1]["text"]
            assert delays and set(delays) == {5.0}
            assert len(plugin.messages) == 1
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    try:
        asyncio.run(scenario())
    finally:
        runtime.stop()


@pytest.mark.parametrize("latest_status", [None, "profile_agent_failed", "success"])
def test_reloaded_submitted_notice_recovers_in_place_without_running(
    setup_retry, latest_status
):
    """重载遗留的已提交消息先恢复最新状态，不把旧点击当成新重试。"""
    plugin, repository, service, calls = setup_retry
    event = _notice(service)
    service.handle_callback(event)
    if latest_status is not None:
        repository.append_run(
            RecommendationRun(
                profile_id=PROFILE,
                run_id="latest-run",
                status=latest_status,
                message="最新结果",
            )
        )
    runtime = _runtime(plugin, SimpleNamespace(), service)
    recreated = TelegramRunRetryService(
        plugin,
        repository,
        plugin._config,
        runtime.start_retry,
        target_adapter=service._target_adapter,
    )
    runtime.retry_service = recreated
    try:
        recreated.handle_callback(event)
        session = _session(repository, event)
        assert calls == [PROFILE]
        assert runtime._retry_executor is None
        assert session.attempt == 1
        assert session.status == ("completed" if latest_status == "success" else "open")
        assert plugin.chain.edits[-1]["message_id"] == "42"
        assert len(plugin.messages) == 1
    finally:
        runtime.stop()


def test_stop_before_retry_coroutine_starts_still_updates_queued_card(setup_retry):
    """工作线程已接单但协程尚未启动时停止，也必须收束原通知。"""
    plugin, repository, service, _ = setup_retry
    runtime = _runtime(plugin, SimpleNamespace(), service)

    class DeferredExecutor:
        """保留已被线程领取的任务，制造停止与协程启动之间的窗口。"""

        def __init__(self):
            """准备不能再按排队任务取消的 Future。"""
            self.future = Future()
            self.future.set_running_or_notify_cancel()
            self.call = None
            self.stopped = False

        def submit(self, function, *args):
            """延迟执行实际协程入口。"""
            self.call = lambda: function(*args)
            return self.future

        def shutdown(self, **_kwargs):
            """模拟工作线程已经领取任务，因此关闭队列不能取消它。"""
            self.stopped = True

        def finish(self):
            """在停止后继续进入真实运行时，再触发完成回调。"""
            self.future.set_result(self.call())

    executor = DeferredExecutor()
    runtime._retry_executor = executor
    event = _notice(service)
    try:
        service.handle_callback(event)
        runtime.stop()
        executor.finish()
        assert executor.stopped
        assert "状态：已停止" in plugin.chain.edits[-1]["text"]
        assert _session(repository, event).status == "open"
        assert runtime._retry_jobs == {}
        assert len(plugin.messages) == 1
    finally:
        runtime.stop()
