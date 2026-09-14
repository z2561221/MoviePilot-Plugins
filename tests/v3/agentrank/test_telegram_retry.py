"""异常通知重试的归属、幂等和后台生命周期回归。"""

import asyncio
import copy
import threading
from concurrent.futures import ThreadPoolExecutor
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


class FakePlugin:
    """以独立内存数据和消息记录代替宿主副作用。"""

    def __init__(self):
        """准备两个同名但身份不同的画像。"""
        self.data = {}
        self.messages = []
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
    buttons = service.create_buttons(
        profile_id, "Alice", run_id, "原因：Agent 调用失败\n旧榜单：已保留"
    )
    callback = buttons[0][0]["callback_data"]
    assert len(callback.encode("utf-8")) <= 64
    assert profile_id not in callback
    return {
        "plugin_id": service._plugin.__class__.__name__,
        "channel": "Telegram",
        "text": callback.split("|", 1)[1],
        "userid": "1001",
        "source": "Telegram",
        "original_message_id": 42,
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
    assert "original_message_id" not in plugin.messages[-1]
    assert _session(repository, event).status == "open"

    assert service.handle_callback(event) is True
    assert calls == [PROFILE]
    assert _session(repository, event).status == "submitted"
    assert plugin.messages[-1]["original_message_id"] == 42
    assert plugin.messages[-1]["buttons"] == []
    assert "已提交" in plugin.messages[-1]["text"]

    recreated = TelegramRunRetryService(
        plugin,
        AgentRankRepository(plugin),
        plugin._config,
        service._retry_handler,
        target_adapter=service._target_adapter,
    )
    recreated.handle_callback(event)
    assert calls == [PROFILE]
    assert "不会重复执行" in plugin.messages[-1]["text"]


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
    assert plugin.messages[-1]["buttons"]
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
    assert plugin.messages == []


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
def test_sync_callback_queues_run_and_notifies_retry_failure(setup_retry, unhandled):
    """同步 Telegram 回调立即返回，失败后仍发带按钮的新通知。"""
    plugin, _, service, _ = setup_retry
    entered, release = threading.Event(), threading.Event()
    sources = []

    class Orchestrator:
        """阻塞在可取消等待中的推荐编排替身。"""

        async def run(self, profile_id, config, *, trigger_reason=""):
            """记录真实触发来源，随后返回失败或抛出异常。"""
            sources.append((profile_id, trigger_reason))
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
    try:
        assert service.handle_callback(_notice(service))
        assert entered.wait(3)
        future = runtime._retry_jobs[PROFILE]
        assert runtime.start_retry(PROFILE) == {"accepted": False, "status": "running"}
        assert runtime.start_refresh(PROFILE)["active"] is True
        release.set()
        future.result(timeout=3)
        assert sources == [(PROFILE, "telegram_retry")]
        failures = [
            message
            for message in plugin.messages
            if message.get("title", "").endswith("运行异常")
        ]
        assert len(failures) == 1
        assert failures[0]["buttons"][0][0]["text"] == "🔄 重试"
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
        assert runtime.start_retry(PROFILE)["accepted"]
        assert entered.wait(3)
        running = runtime._retry_jobs[PROFILE]
        assert runtime.start_retry(OTHER_PROFILE)["accepted"]
        queued = runtime._retry_jobs[OTHER_PROFILE]
        runtime.stop()
        runtime.stop()
        assert cancelled.wait(3)
        with pytest.raises(asyncio.CancelledError):
            running.result(timeout=3)
        assert queued.cancelled()
        assert calls == [PROFILE]
        assert runtime.run_progress(PROFILE)["active"] is False
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
