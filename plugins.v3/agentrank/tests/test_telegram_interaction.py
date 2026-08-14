"""AgentRank Telegram 单页榜单与自选订阅交互测试。"""

import importlib
import sys
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from types import ModuleType, SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_telegram_interaction_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

app_module = sys.modules.setdefault("app", ModuleType("app"))
schemas_module = sys.modules.setdefault("app.schemas", ModuleType("app.schemas"))
types_module = sys.modules.setdefault("app.schemas.types", ModuleType("app.schemas.types"))
message_module = sys.modules.setdefault("app.schemas.message", ModuleType("app.schemas.message"))


class NotificationType(Enum):
    """测试使用的通知类型。"""

    Subscribe = "订阅"
    Plugin = "插件"


class MessageChannel(Enum):
    """测试使用的消息渠道。"""

    Telegram = "Telegram"


app_module.schemas = schemas_module
schemas_module.types = types_module
types_module.NotificationType = NotificationType
types_module.MessageChannel = MessageChannel

sdk_module = sys.modules.setdefault("app.sdk", ModuleType("app.sdk"))
services_module = sys.modules.setdefault(
    "app.sdk.services", ModuleType("app.sdk.services")
)
NOTIFICATION_CONFIGS = [
    SimpleNamespace(
        name="Telegram",
        type="telegram",
        enabled=True,
        switchs=["插件"],
    )
]


class ServiceConfigHelper:
    """提供可变通知配置的宿主服务替身。"""

    @staticmethod
    def get_notification_configs():
        """返回当前测试通知配置。"""
        return list(NOTIFICATION_CONFIGS)


app_module.sdk = sdk_module
sdk_module.services = services_module
services_module.ServiceConfigHelper = ServiceConfigHelper


class Notification:
    """接收宿主 Notification 载荷的测试替身。"""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


message_module.Notification = Notification

board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
pending_model_module = importlib.import_module(
    f"{PACKAGE_NAME}.model.pending_center"
)
telegram_pending_module = importlib.import_module(
    f"{PACKAGE_NAME}.model.telegram_pending"
)
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
interaction_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.telegram_interaction"
)

RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
AgentRankRepository = repository_module.AgentRankRepository
TelegramSelectionService = interaction_module.TelegramSelectionService
TelegramTargetAdapter = interaction_module.TelegramTargetAdapter
PendingCenterItem = pending_model_module.PendingCenterItem
PendingNotice = pending_model_module.PendingNotice
TelegramPendingSession = telegram_pending_module.TelegramPendingSession


class FakeMessageChain:
    """记录直发、删除和编辑调用并允许配置结果。"""

    def __init__(
        self,
        delete_result=True,
        direct_result=None,
        edit_result=True,
        use_run_module=False,
    ):
        self.delete_result = delete_result
        self.direct_result = direct_result or SimpleNamespace(success=False)
        self.edit_result = edit_result
        self.run_module_calls = []
        self.direct_calls = []
        self.delete_calls = []
        self.edit_calls = []
        self.run_module = self._run_module if use_run_module else None

    def send_direct_message(self, message):
        """记录需要返回消息身份的直发调用。"""
        self.direct_calls.append(message)
        return self.direct_result

    def delete_message(self, **kwargs):
        """记录 MoviePilot 消息删除参数。"""
        self.delete_calls.append(kwargs)
        return self.delete_result

    def edit_message(self, **kwargs):
        """记录删除失败后的原地收束。"""
        self.edit_calls.append(kwargs)
        return self.edit_result

    def _run_module(self, method, **kwargs):
        """记录通过宿主模块分发的编辑调用。"""
        self.run_module_calls.append((method, kwargs))
        if method == "edit_message":
            self.edit_calls.append(kwargs)
            return self.edit_result
        return None


class FakePlugin:
    """记录插件数据与发送消息的测试替身。"""

    def __init__(
        self,
        delete_result=True,
        direct_result=None,
        edit_result=True,
        use_run_module=False,
    ):
        self.data = {}
        self.duplicate_data_rows = []
        self.messages = []
        self._poster_service = None
        self.enabled = True
        self.chain = FakeMessageChain(
            delete_result,
            direct_result,
            edit_result,
            use_run_module=use_run_module,
        )

    def get_data(self, key=None):
        """读取内存插件数据。"""
        if key is None:
            return [
                *(
                    SimpleNamespace(key=item_key, value=value)
                    for item_key, value in self.data.items()
                ),
                *self.duplicate_data_rows,
            ]
        return self.data.get(key)

    def save_data(self, key=None, value=None):
        """保存内存插件数据。"""
        self.data[key] = value

    def del_data(self, key=None):
        """删除内存插件数据。"""
        self.data.pop(key, None)
        self.duplicate_data_rows = [
            item
            for item in self.duplicate_data_rows
            if str(getattr(item, "key", "")) != str(key or "")
        ]

    def post_message(self, **kwargs):
        """记录一次通知发送或编辑。"""
        self.messages.append(kwargs)

    def get_state(self):
        """返回测试插件启用状态。"""
        return self.enabled


class FakeTargetAdapter:
    """返回固定 Telegram 用户映射。"""

    def __init__(self, userid="1001"):
        self.userid = userid

    def resolve_userid(self, username):
        """返回目标用户 ID。"""
        return self.userid


class FakeUserOper:
    """按用户名返回通知设置并记录查询顺序。"""

    def __init__(self, settings_by_name):
        self.settings_by_name = settings_by_name
        self.calls = []

    def get_settings(self, username):
        """模拟 MoviePilot 用户设置读取。"""
        self.calls.append(username)
        return self.settings_by_name.get(username)


class FakeSubscriptionService:
    """记录最终确认调用并返回可配置结果。"""

    def __init__(self):
        self.calls = []

    def subscribe(self, username, candidate_id, threshold):
        """模拟已有订阅安全链。"""
        self.calls.append((username, candidate_id, threshold))
        return SimpleNamespace(
            success=True,
            changed=candidate_id != "tmdb:2",
            message="ok",
        )


def _board(run_id="run-1"):
    """构造两条带 TMDB 标识与匹配标签的推荐榜单。"""
    return RecommendationBoard(
        profile_id="alice",
        username="alice",
        run_id=run_id,
        status="success",
        recommendations=[
            RecommendationItem(
                candidate_id="tmdb:1",
                rank=1,
                title="第一部电影",
                media_type="movie",
                year=2025,
                confidence=92,
                reason="第一部推荐理由",
                summary="第一部简介",
                poster_path="https://image.tmdb.org/t/p/w200/a.jpg",
                backdrop_path="https://image.tmdb.org/t/p/w1280/backdrop-a.jpg",
                source_ids={"tmdb": "1", "douban": "11"},
                match_tags=["悬疑", "成长"],
            ),
            RecommendationItem(
                candidate_id="tmdb:2",
                rank=2,
                title="第二部剧集",
                media_type="tv",
                year=2026,
                confidence=0.88,
                reason="第二部推荐理由",
                summary="第二部简介",
                poster_path="https://image.tmdb.org/t/p/w200/b.jpg",
                backdrop_path="https://image.tmdb.org/t/p/w1280/backdrop-b.jpg",
                source_ids={"tmdb": "2", "bangumi": "22"},
                match_tags=["科幻", "群像"],
            ),
        ],
    )


def _oversized_board():
    """构造十条输入以验证交互榜单固定截取前五条。"""
    board = _board()
    board.recommendations = [
        RecommendationItem(
            candidate_id=f"tmdb:{index}",
            rank=index,
            title=f"第{index:02d}部具有较长中文标题的推荐作品",
            media_type="anime" if index % 2 else "tv",
            year=2020 + index,
            confidence=90 - index,
            reason="较长推荐理由会在标签后按客户端宽度自然换行",
            summary="较长剧情简介会在标签后按客户端宽度自然换行",
            poster_path=f"https://image.tmdb.org/t/p/w200/{index}.jpg",
            backdrop_path=f"https://image.tmdb.org/t/p/w1280/backdrop-{index}.jpg",
            source_ids={"tmdb": str(index)},
            match_tags=["日本动画偏好", "古装历史题材"],
        )
        for index in range(1, 11)
    ]
    return board


def _service(
    now=None,
    target="1001",
    pending_center=None,
    delete_result=True,
    direct_result=None,
    edit_result=True,
    use_run_module=False,
):
    """创建固定令牌和时钟的交互服务。"""
    plugin = FakePlugin(
        delete_result=delete_result,
        direct_result=direct_result,
        edit_result=edit_result,
        use_run_module=use_run_module,
    )
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    subscription = FakeSubscriptionService()
    clock = [now or datetime(2026, 7, 18, tzinfo=timezone.utc)]
    service = TelegramSelectionService(
        plugin=plugin,
        repository=repository,
        subscription_service=subscription,
        config={"confidence_threshold": 0.6, "notification_type": "Plugin"},
        pending_center=pending_center,
        target_adapter=FakeTargetAdapter(target),
        token_factory=lambda: "token123",
        now_factory=lambda: clock[0],
    )
    return plugin, repository, subscription, service, clock


class FakePendingCenter:
    """记录 Telegram 直接待确认响应。"""

    def __init__(self):
        """创建空调用列表。"""
        self.calls = []

    def respond(self, **kwargs):
        """记录安全响应并返回终态。"""
        self.calls.append(kwargs)
        return {
            "action": kwargs["action"],
            "changed": True,
            "item": {"status": "answered"},
        }


class FakePendingLookup:
    """返回指定终态的待办中心查询替身。"""

    def __init__(self, status="answered"):
        self.status = status

    def item(self, profile_id, item_type, item_id):
        return SimpleNamespace(
            profile_id=profile_id,
            item_type=item_type,
            item_id=item_id,
            status=self.status,
        )


def _event(action, userid="1001"):
    """构造 MoviePilot MessageAction 事件数据。"""
    return {
        "text": f"ar:token123:{action}",
        "channel": MessageChannel.Telegram,
        "source": "Telegram",
        "userid": userid,
        "original_message_id": 77,
        "original_chat_id": "1001",
    }


def _pending_event(action, argument="", userid="1001"):
    """构造 Telegram 待确认按钮事件。"""
    suffix = f":{argument}" if argument else ""
    return {
        "text": f"arp:token123:{action}{suffix}",
        "channel": MessageChannel.Telegram,
        "source": "Telegram",
        "userid": userid,
        "original_message_id": 88,
        "original_chat_id": "1001",
    }


def _callbacks(message):
    """提取消息内全部回调按钮。"""
    return [
        button["callback_data"]
        for row in message.get("buttons") or []
        for button in row
        if button.get("callback_data")
    ]


def _question_notice(profile_id="alice"):
    """构造可在两个终端处理的问询通知。"""
    return PendingNotice(
        item=PendingCenterItem(
            item_type="question",
            item_id="question-cross-device",
            profile_id=profile_id,
            title="CinePilot Agent 需要你确认",
            summary="未来推荐更应该延续熟悉体验，还是主动带来变化？",
            created_at="2026-07-18T00:00:00+00:00",
            status="pending",
            options=(
                {
                    "option_id": "continue_patterns",
                    "label": "延续已看作品的共同点",
                },
                {"option_id": "either", "label": "都可以"},
                {"option_id": "uncertain", "label": "不确定"},
                {"option_id": "not_me", "label": "不是我看的"},
            ),
            allow_custom_answer=True,
        ),
        actor_id="mp-user-1",
    )


def test_pending_notification_persists_message_identity_and_preserves_buttons():
    """待办同步发送后保存消息身份，并补挂完整 Telegram 选项按钮。"""
    response = SimpleNamespace(
        success=True,
        message_id=901,
        chat_id="1001",
        source="Telegram",
    )
    plugin, repository, _, service, _ = _service(direct_result=response)
    notice = _question_notice()

    assert service.start_pending(username="alice", notice=notice) is True
    session = repository.load_telegram_pending_session("token123")
    assert session.message_id == "901"
    assert session.chat_id == "1001"
    assert session.source == "Telegram"
    assert session.option_ids == [
        "continue_patterns",
        "either",
        "uncertain",
        "not_me",
    ]
    assert repository.telegram_pending_sessions_key not in plugin.data
    assert repository._telegram_pending_session_key("token123") in plugin.data
    assert len(plugin.chain.direct_calls) == 1
    assert len(plugin.chain.edit_calls) == 1
    assert plugin.chain.edit_calls[0]["message_id"] == "901"
    message = plugin.chain.direct_calls[0].__dict__
    assert message["userid"] == "1001"
    assert message["targets"] == {"telegram_userid": "1001"}
    buttons = plugin.chain.edit_calls[0]["buttons"]
    assert [row[0]["text"] for row in buttons[:4]] == [
        "延续已看作品的共同点",
        "都可以",
        "不确定",
        "不是我看的",
    ]
    assert all(
        row[0].get("callback_data")
        for row in buttons[:4]
    )


def test_pending_legacy_duplicate_rows_recover_hidden_message_identity():
    """旧共享键出现重复数据库行时仍恢复消息身份并完成跨端删除。"""
    response = SimpleNamespace(
        success=True,
        message_id=911,
        chat_id="1001",
        source="Telegram",
    )
    plugin, repository, _, service, _ = _service(direct_result=response)
    notice = _question_notice()
    assert service.start_pending(username="alice", notice=notice) is True
    payload = repository.load_telegram_pending_session("token123").to_dict()

    plugin.data.clear()
    plugin.data[repository.telegram_pending_sessions_key] = {}
    plugin.duplicate_data_rows = [
        SimpleNamespace(
            key=repository.telegram_pending_sessions_key,
            value={"token123": payload},
        )
    ]

    recovered = repository.load_telegram_pending_session("token123")
    assert recovered is not None
    assert recovered.message_id == "911"
    assert repository.telegram_pending_sessions_key not in plugin.data
    assert plugin.duplicate_data_rows == []
    assert repository._telegram_pending_session_key("token123") in plugin.data
    assert service.resolve_pending_item(notice.item) == 1
    assert plugin.chain.delete_calls[-1]["message_id"] == "911"


def test_pending_independent_keys_follow_profile_reset_boundaries():
    """学习与完整重置只删除目标画像的独立 Telegram 会话键。"""
    response = SimpleNamespace(
        success=True,
        message_id=912,
        chat_id="1001",
        source="Telegram",
    )
    _, repository, _, service, _ = _service(direct_result=response)
    notice = _question_notice()
    assert service.start_pending(username="alice", notice=notice) is True
    alice = repository.load_telegram_pending_session("token123")
    bob_payload = alice.to_dict()
    bob_payload.update(
        token="token-bob",
        profile_id="bob",
        item_id="question-bob",
        message_id="913",
        chat_id="1002",
    )
    repository.save_telegram_pending_session(
        TelegramPendingSession.from_dict(bob_payload)
    )

    repository.reset_learning_data("alice")
    assert repository.load_telegram_pending_session("token123") is None
    assert repository.load_telegram_pending_session("token-bob") is not None

    repository.reset_all_profile_data("bob")
    assert repository.load_telegram_pending_session("token-bob") is None


def test_pending_direct_message_pins_plugin_source_when_agent_config_is_first():
    """定向消息不能因智能体配置排在前面而绕过插件来源。"""
    previous = list(NOTIFICATION_CONFIGS)
    NOTIFICATION_CONFIGS[:] = [
        SimpleNamespace(
            name="小管家",
            type="telegram",
            enabled=True,
            switchs=["智能体"],
        ),
        SimpleNamespace(
            name="系统插件",
            type="telegram",
            enabled=True,
            switchs=["插件"],
        ),
    ]
    try:
        response = SimpleNamespace(
            success=True,
            message_id=902,
            chat_id="1001",
            source="系统插件",
        )
        plugin, _, _, service, _ = _service(direct_result=response)

        assert service.start_pending(username="alice", notice=_question_notice()) is True
        assert plugin.chain.direct_calls[-1].source == "系统插件"
    finally:
        NOTIFICATION_CONFIGS[:] = previous


def test_pending_direct_message_skips_agent_only_source_and_returns_fallback_signal():
    """没有插件通知配置时，不直发智能体来源并交给上层普通通知。"""
    previous = list(NOTIFICATION_CONFIGS)
    NOTIFICATION_CONFIGS[:] = [
        SimpleNamespace(
            name="小管家",
            type="telegram",
            enabled=True,
            switchs=["智能体"],
        ),
        SimpleNamespace(
            name="未分类",
            type="telegram",
            enabled=True,
            switchs=[],
        ),
    ]
    try:
        plugin, repository, _, service, _ = _service()

        assert service.start_pending(username="alice", notice=_question_notice()) is False
        assert plugin.chain.direct_calls == []
        assert plugin.messages == []
        assert repository.load_telegram_pending_session("token123") is None
    finally:
        NOTIFICATION_CONFIGS[:] = previous


def test_pending_direct_send_uses_run_module_for_html_edit():
    """宿主链存在 run_module 时，编辑按钮使用支持 parse_mode 的分发入口。"""
    response = SimpleNamespace(
        success=True,
        message_id=904,
        chat_id="1001",
        source="Telegram",
    )
    plugin, _, _, service, _ = _service(
        direct_result=response,
        use_run_module=True,
    )

    assert service.start_pending(username="alice", notice=_question_notice()) is True
    assert plugin.chain.run_module_calls[0][0] == "edit_message"
    assert plugin.chain.run_module_calls[0][1]["parse_mode"] == "HTML"


def test_pending_without_message_identity_does_not_leave_interactive_session():
    """直发未返回消息身份时降级普通通知，且不遗留无法收束的会话。"""
    plugin, repository, _, service, _ = _service()
    notice = _question_notice()

    assert service.start_pending(username="alice", notice=notice) is False
    assert len(plugin.chain.direct_calls) == 1
    assert plugin.messages == []
    assert repository.load_telegram_pending_session("token123") is None
    assert repository.load_telegram_pending_sessions(
        notice.item.profile_id,
        notice.item.item_type,
        notice.item.item_id,
    ) == []


def test_pending_cross_device_delete_uses_persisted_message_identity():
    """待办中心处理后按发送时保存的消息身份删除 Telegram 原卡片。"""
    response = SimpleNamespace(
        success=True,
        message_id=903,
        chat_id="1001",
        source="Telegram",
    )
    plugin, _, _, service, _ = _service(direct_result=response)
    notice = _question_notice()

    assert service.start_pending(username="alice", notice=notice) is True
    assert service.resolve_pending_item(notice.item) == 1

    assert plugin.chain.delete_calls[-1] == {
        "channel": MessageChannel.Telegram,
        "source": "Telegram",
        "message_id": "903",
        "chat_id": "1001",
    }


def test_pending_cross_device_cleanup_retries_resolved_session():
    """历史终态会话也要重新尝试删除 Telegram 原卡片。"""
    response = SimpleNamespace(
        success=True,
        message_id=904,
        chat_id="1001",
        source="Telegram",
    )
    plugin, repository, _, service, _ = _service(direct_result=response)
    notice = _question_notice()

    assert service.start_pending(username="alice", notice=notice) is True
    session = repository.load_telegram_pending_session("token123")
    assert session is not None
    session.status = "resolved"
    repository.save_telegram_pending_session(session)

    assert service.resolve_pending_item(notice.item) == 1
    assert plugin.chain.delete_calls[-1]["message_id"] == "904"


def test_pending_delete_retries_current_plugin_source_after_stored_source_fails():
    """历史来源失效时，删除会回退到当前允许插件通知的来源。"""
    response = SimpleNamespace(
        success=True,
        message_id=908,
        chat_id="1001",
        source="旧插件来源",
    )
    plugin, repository, _, service, _ = _service(
        delete_result=False,
        direct_result=response,
    )
    notice = _question_notice()
    assert service.start_pending(username="alice", notice=notice) is True

    def delete_by_source(**kwargs):
        plugin.chain.delete_calls.append(kwargs)
        return kwargs["source"] == "Telegram"

    plugin.chain.delete_message = delete_by_source
    assert service.resolve_pending_item(notice.item) == 1
    assert [item["source"] for item in plugin.chain.delete_calls[-2:]] == [
        "旧插件来源",
        "Telegram",
    ]
    assert repository.load_telegram_pending_session("token123").source == "Telegram"


def test_pending_startup_reconciles_open_session_for_answered_item():
    """重载时追补删除已经回答但仍开放的 Telegram 卡片。"""
    response = SimpleNamespace(
        success=True,
        message_id=907,
        chat_id="1001",
        source="Telegram",
    )
    plugin, repository, _, service, _ = _service(
        pending_center=FakePendingLookup(),
        direct_result=response,
    )
    notice = _question_notice()
    assert service.start_pending(username="alice", notice=notice) is True

    assert service.reconcile_pending_sessions() == 1
    assert plugin.chain.delete_calls[-1]["message_id"] == "907"
    assert repository.load_telegram_pending_session("token123").status == "resolved"


def test_pending_startup_reconciles_profile_id_with_colons():
    """真实 Emby 画像 ID 含冒号时仍能匹配 Telegram 会话。"""
    response = SimpleNamespace(
        success=True,
        message_id=911,
        chat_id="1001",
        source="Telegram",
    )
    plugin, repository, _, service, _ = _service(
        pending_center=FakePendingLookup(),
        direct_result=response,
    )
    notice = _question_notice(
        profile_id="emby:Embyserver:415a522ba91b45c5abd960b1eda3d06a"
    )
    assert service.start_pending(username="alice", notice=notice) is True

    assert service.reconcile_pending_sessions() == 1
    assert plugin.chain.delete_calls[-1]["message_id"] == "911"
    assert repository.load_telegram_pending_session("token123").status == "resolved"


def test_pending_startup_retries_resolved_session_for_answered_item():
    """旧逻辑误标终态的会话仍要在重载时再次尝试删除。"""
    response = SimpleNamespace(
        success=True,
        message_id=909,
        chat_id="1001",
        source="Telegram",
    )
    plugin, repository, _, service, _ = _service(
        pending_center=FakePendingLookup(),
        direct_result=response,
    )
    notice = _question_notice()
    assert service.start_pending(username="alice", notice=notice) is True
    session = repository.load_telegram_pending_session("token123")
    session.status = "resolved"
    repository.save_telegram_pending_session(session)

    assert service.reconcile_pending_sessions() == 1
    assert plugin.chain.delete_calls[-1]["message_id"] == "909"


def test_pending_startup_normalizes_open_session_without_message_identity():
    """并发清理留下的无身份 open 会话要稳定收束为 resolved。"""
    response = SimpleNamespace(
        success=True,
        message_id=914,
        chat_id="1001",
        source="Telegram",
    )
    plugin, repository, _, service, _ = _service(
        pending_center=FakePendingLookup(),
        direct_result=response,
    )
    notice = _question_notice()
    assert service.start_pending(username="alice", notice=notice) is True
    session = repository.load_telegram_pending_session("token123")
    session.status = "open"
    session.message_id = ""
    session.chat_id = ""
    repository.save_telegram_pending_session(session)

    assert service.reconcile_pending_sessions() == 0
    normalized = repository.load_telegram_pending_session("token123")
    assert normalized.status == "resolved"
    assert normalized.message_id == ""
    assert plugin.chain.delete_calls == []


def test_pending_cross_device_delete_failure_edits_message_without_buttons():
    """已有消息身份时，渠道删除失败仍原地移除交互按钮。"""
    response = SimpleNamespace(
        success=True,
        message_id=902,
        chat_id="1001",
        source="Telegram",
    )
    plugin, _, _, service, _ = _service(
        delete_result=False,
        direct_result=response,
    )
    notice = _question_notice()
    assert service.start_pending(username="alice", notice=notice) is True

    assert service.resolve_pending_item(notice.item) == 1
    assert plugin.chain.edit_calls[-1]["title"] == "克里斯蒂娜 · 已处理"
    assert plugin.chain.edit_calls[-1]["buttons"] is None


def test_pending_none_edit_result_stays_open_for_retry():
    """删除失败且编辑返回 None 时不得误报已收束。"""
    response = SimpleNamespace(
        success=True,
        message_id=910,
        chat_id="1001",
        source="Telegram",
    )
    plugin, repository, _, service, _ = _service(
        delete_result=False,
        direct_result=response,
        edit_result=None,
    )
    notice = _question_notice()
    assert service.start_pending(username="alice", notice=notice) is True

    assert service.resolve_pending_item(notice.item) == 0
    assert repository.load_telegram_pending_session("token123").status == "open"
    assert len(plugin.chain.delete_calls) == service.pending_message_retry_attempts
    assert len(plugin.chain.edit_calls) == (
        1 + service.pending_message_retry_attempts
    )


def test_pending_cross_device_delete_retries_with_bounded_attempts():
    """跨端删除短暂失败时只重试一次并最终收束。"""
    response = SimpleNamespace(
        success=True,
        message_id=905,
        chat_id="1001",
        source="Telegram",
    )
    plugin, _, _, service, _ = _service(direct_result=response)
    notice = _question_notice()
    assert service.start_pending(username="alice", notice=notice) is True
    attempts = {"count": 0}

    def flaky_delete(**kwargs):
        attempts["count"] += 1
        plugin.chain.delete_calls.append(kwargs)
        return attempts["count"] >= 2

    plugin.chain.delete_message = flaky_delete
    assert service.resolve_pending_item(notice.item) == 1
    assert attempts["count"] == 2
    assert plugin.chain.edit_calls[-1]["buttons"] is not None


def test_resolved_pending_session_is_not_resent_after_service_recreation():
    """服务重建后已处理会话仍抑制同一事项再次投递。"""
    response = SimpleNamespace(
        success=True,
        message_id=906,
        chat_id="1001",
        source="Telegram",
    )
    plugin, repository, subscription, service, _ = _service(
        direct_result=response
    )
    notice = _question_notice()
    assert service.start_pending(username="alice", notice=notice) is True
    assert service.resolve_pending_item(notice.item) == 1
    sent_count = len(plugin.chain.direct_calls)

    recreated = TelegramSelectionService(
        plugin=plugin,
        repository=repository,
        subscription_service=subscription,
        config={},
        target_adapter=FakeTargetAdapter(),
        token_factory=lambda: "token-new",
    )
    assert recreated.start_pending(username="alice", notice=notice) is True
    assert len(plugin.chain.direct_calls) == sent_count


def test_target_adapter_resolves_direct_moviepilot_user_mapping():
    """MP 用户已绑定 Telegram 时直接使用该用户 ID。"""
    user_oper = FakeUserOper({"alice": {"telegram_userid": 1001}})
    adapter = TelegramTargetAdapter(lambda: user_oper, superuser="admin")

    assert adapter.resolve_userid("alice") == "1001"
    assert user_oper.calls == ["alice"]


def test_target_adapter_falls_back_to_superuser_for_emby_display_name():
    """Emby 显示名不是 MP 用户时沿用宿主规则回退管理员。"""
    user_oper = FakeUserOper(
        {"admin": {"telegram_userid": "9001", "nickname": ""}}
    )
    adapter = TelegramTargetAdapter(lambda: user_oper, superuser="admin")

    assert adapter.resolve_userid("Home") == "9001"
    assert user_oper.calls == ["Home", "admin"]


def test_target_adapter_does_not_bypass_existing_user_without_binding():
    """MP 用户存在但未绑定 Telegram 时不得越权改发管理员。"""
    user_oper = FakeUserOper(
        {
            "alice": {},
            "admin": {"telegram_userid": "9001"},
        }
    )
    adapter = TelegramTargetAdapter(lambda: user_oper, superuser="admin")

    assert adapter.resolve_userid("alice") is None
    assert user_oper.calls == ["alice"]


def test_start_sends_linked_three_line_top_list_with_horizontal_cover():
    """初始通知用榜首横版封面和三行榜单展示链接、推荐与简介。"""
    plugin, repository, _, service, _ = _service()

    assert service.start("alice", "alice", _board()) is True

    message = plugin.messages[-1]
    assert message["channel"] is MessageChannel.Telegram
    assert message.get("userid") is None
    assert message["username"] == "alice"
    assert message["targets"] == {"telegram_userid": "1001"}
    assert message["image"].endswith("/backdrop-a.jpg")
    assert (
        '<code>01</code> <a href="https://www.themoviedb.org/movie/1">'
        '第一部电影</a> · 2025\n'
        '<b>推荐：</b>第一部推荐理由\n'
        '<b>简介：</b>第一部简介'
    ) in message["text"]
    assert (
        '<code>02</code> <a href="https://www.themoviedb.org/tv/2">'
        '第二部剧集</a> · 2026\n'
        '<b>推荐：</b>第二部推荐理由\n'
        '<b>简介：</b>第二部简介'
    ) in message["text"]
    assert (
        '<b>简介：</b>第一部简介\n\n'
        '<code>02</code> <a href="https://www.themoviedb.org/tv/2">'
    ) in message["text"]
    assert "\n\n\n" not in message["text"]
    assert "92%" not in message["text"]
    assert "88%" not in message["text"]
    assert "置信度" not in message["text"]
    assert "<code>01</code> 第一部电影｜" not in message["text"]
    assert "第一部电影" in message["text"]
    assert "第二部剧集" in message["text"]
    assert "悬疑/成长" not in message["text"]
    assert " · 影 · " not in message["text"]
    assert " · 剧 · " not in message["text"]
    assert "科幻/群像" not in message["text"]
    assert "确认 0" in str(message["buttons"])
    assert ":t:0" in str(message["buttons"])
    assert ":t:1" in str(message["buttons"])
    assert ":p" not in str(message["buttons"])
    assert ":n" not in str(message["buttons"])
    assert "TMDB" not in str(message["buttons"])
    assert "豆瓣" not in str(message["buttons"])
    assert "Bangumi" not in str(message["buttons"])
    assert all("url" not in button for row in message["buttons"] for button in row)
    assert len(message["buttons"]) == 2
    assert max(len(row) for row in message["buttons"]) == 3
    assert len(message["text"]) <= service.caption_limit
    assert message["mtype"] is NotificationType.Plugin
    assert all(len(value.encode("utf-8")) <= 64 for value in _callbacks(message))
    session = repository.load_telegram_session("token123")
    assert session.candidate_ids == ["tmdb:1", "tmdb:2"]
    assert session.selected_ids == []


def test_oversized_board_is_limited_to_five_items():
    """超量榜单在 Telegram 中只保留前五条和一行编号按钮。"""
    plugin, repository, _, service, _ = _service()
    board = _oversized_board()
    repository.save_board(board)

    service.start("alice", "alice", board)

    message = plugin.messages[-1]
    assert len(message["text"]) <= service.caption_limit
    assert len(message["buttons"]) == 2
    assert [len(row) for row in message["buttons"]] == [5, 3]
    assert all(f"{index:02d}" in message["text"] for index in range(1, 6))
    assert "06" not in message["text"]
    assert message["image"].endswith("/backdrop-1.jpg")
    assert message["text"].count("<code>") == 5
    assert "\n　　" not in message["text"]
    assert "日本动画" not in message["text"]
    assert message["text"].count("<b>推荐：</b>") == 5
    assert message["text"].count("<b>简介：</b>") == 5
    assert "较长推荐理由会在标签后按客户端宽度自然换行" in message["text"]
    assert "较长剧情简介会在标签后按客户端宽度自然换行" in message["text"]
    assert "90%" not in message["text"]


def test_missing_tmdb_id_keeps_plain_title_and_cover():
    """缺少有效 TMDB ID 时标题保持纯文本但通知仍保留横版封面。"""
    plugin, _, _, service, _ = _service()
    board = _board()
    board.recommendations[0].source_ids.pop("tmdb")

    service.start("alice", "alice", board)

    assert plugin.messages[-1]["image"].endswith("/backdrop-a.jpg")
    assert "第一部电影" in plugin.messages[-1]["text"]
    assert "themoviedb.org/movie/1" not in plugin.messages[-1]["text"]


def test_missing_backdrop_falls_back_to_poster():
    """榜首缺少横版封面时回退到可抓取的海报地址。"""
    plugin, _, _, service, _ = _service()
    board = _board()
    board.recommendations[0].backdrop_path = ""

    service.start("alice", "alice", board)

    assert plugin.messages[-1]["image"].endswith("/a.jpg")


def test_number_toggle_and_clear_update_single_original_message():
    """编号选择与清空均在原单页消息中更新状态。"""
    plugin, repository, _, service, _ = _service()
    service.start("alice", "alice", _board())

    assert service.handle_callback(_event("t:1")) is True
    assert plugin.messages[-1]["image"].endswith("/backdrop-a.jpg")
    assert plugin.messages[-1]["original_message_id"] == 77
    session = repository.load_telegram_session("token123")
    assert session.selected_ids == ["tmdb:2"]
    assert "✓02" in str(plugin.messages[-1]["buttons"])
    assert "确认 1" in str(plugin.messages[-1]["buttons"])

    service.handle_callback(_event("t:0"))
    session = repository.load_telegram_session("token123")
    assert session.selected_ids == ["tmdb:1", "tmdb:2"]
    assert "✓01" in str(plugin.messages[-1]["buttons"])
    assert "✓02" in str(plugin.messages[-1]["buttons"])

    service.handle_callback(_event("e"))
    session = repository.load_telegram_session("token123")
    assert session.selected_ids == []
    assert "已清空本轮选择" in plugin.messages[-1]["text"]
    assert "确认 0" in str(plugin.messages[-1]["buttons"])
    assert all(
        message["mtype"] is NotificationType.Plugin for message in plugin.messages
    )
    assert all(message.get("userid") is None for message in plugin.messages)
    assert all(
        message["targets"] == {"telegram_userid": "1001"}
        for message in plugin.messages
    )


def test_confirm_subscribes_only_selected_items_and_is_idempotent():
    """最终确认只处理已选作品，重复点击不会再次订阅。"""
    plugin, repository, subscription, service, _ = _service()
    service.start("alice", "alice", _board())
    service.handle_callback(_event("t:0"))
    service.handle_callback(_event("t:1"))

    service.handle_callback(_event("c"))

    assert subscription.calls == [
        ("alice", "tmdb:1", 0.6),
        ("alice", "tmdb:2", 0.6),
    ]
    assert "本轮订阅处理完成" in plugin.messages[-1]["text"]
    assert "已创建" in plugin.messages[-1]["text"]
    assert "已存在" in plugin.messages[-1]["text"]
    assert plugin.messages[-1]["buttons"] is None
    assert repository.load_telegram_session("token123").status == "completed"
    assert plugin.chain.delete_calls[-1]["message_id"] == 77
    assert plugin.chain.delete_calls[-1]["chat_id"] == "1001"
    assert plugin.messages[-1].get("original_message_id") is None

    service.handle_callback(_event("c"))
    assert len(subscription.calls) == 2
    assert "不会重复提交" in plugin.messages[-1]["text"]


def test_terminal_interaction_falls_back_to_edit_without_buttons_when_delete_fails():
    """删除原 Telegram 卡片失败时原地编辑为无按钮终态。"""
    plugin, repository, _, service, _ = _service(delete_result=False)
    service.start("alice", "alice", _board())
    service.handle_callback(_event("t:0"))

    service.handle_callback(_event("c"))

    assert repository.load_telegram_session("token123").status == "completed"
    assert plugin.chain.delete_calls[-1]["message_id"] == 77
    assert plugin.messages[-1]["original_message_id"] == 77
    assert plugin.messages[-1]["buttons"] is None


def test_profile_id_scopes_telegram_confirmation_while_username_is_display_only():
    """显示名与稳定画像不同也必须读取并订阅同一 profile_id 榜单。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    board = _board()
    board.profile_id = "emby:home:user-1"
    board.username = "Alice"
    repository.save_board(board)
    subscription = FakeSubscriptionService()
    service = TelegramSelectionService(
        plugin=plugin,
        repository=repository,
        subscription_service=subscription,
        config={"confidence_threshold": 0.6},
        target_adapter=FakeTargetAdapter(),
        token_factory=lambda: "token123",
    )

    assert service.start("emby:home:user-1", "Alice", board) is True
    session = repository.load_telegram_session("token123")
    assert session.profile_id == "emby:home:user-1"
    assert session.username == "Alice"
    service.handle_callback(_event("t:0"))
    service.handle_callback(_event("c"))

    assert subscription.calls == [("emby:home:user-1", "tmdb:1", 0.6)]
    assert plugin.messages[-1]["username"] == "Alice"


def test_telegram_start_rejects_cross_profile_board():
    """通知请求身份与榜单归属不一致时不得创建可操作会话。"""
    plugin, repository, subscription, service, _ = _service()

    try:
        service.start("emby:home:user-2", "Alice", _board())
    except ValueError as error:
        assert "profile_id does not match board" in str(error)
    else:
        raise AssertionError("cross-profile board must be rejected")

    assert repository.load_telegram_session("token123") is None
    assert plugin.messages == []
    assert subscription.calls == []


def test_legacy_telegram_session_without_profile_id_is_stale_and_cannot_subscribe():
    """缺失稳定画像身份的旧会话不得借显示名继续订阅。"""
    plugin, repository, subscription, service, _ = _service()
    service.start("alice", "alice", _board())
    raw = plugin.data[repository.telegram_sessions_key]["token123"]
    raw.pop("profile_id")
    plugin.data[repository.telegram_sessions_key]["token123"] = raw

    service.handle_callback(_event("t:0"))

    assert repository.load_telegram_session("token123").status == "stale"
    assert subscription.calls == []
    assert "缺少稳定画像身份" in plugin.messages[-1]["text"]


def test_empty_confirmation_keeps_session_open_and_prompts_selection():
    """空选择不会触发订阅，并切换到清单提示。"""
    plugin, repository, subscription, service, _ = _service()
    service.start("alice", "alice", _board())

    service.handle_callback(_event("c"))

    assert subscription.calls == []
    assert repository.load_telegram_session("token123").status == "open"
    assert "请至少选择一部作品" in plugin.messages[-1]["text"]
    assert "第一部电影" in plugin.messages[-1]["text"]
    assert "第二部剧集" in plugin.messages[-1]["text"]


def test_wrong_user_stale_board_and_expired_session_are_rejected():
    """越权、旧榜单和过期会话都不能进入订阅安全链。"""
    plugin, repository, subscription, service, clock = _service()
    service.start("alice", "alice", _board())

    service.handle_callback(_event("t", userid="9999"))
    assert "这不是发送给你的榜单" in plugin.messages[-1]["text"]
    assert plugin.messages[-1]["targets"] == {"telegram_userid": "9999"}
    assert plugin.messages[-1].get("userid") is None
    assert repository.load_telegram_session("token123").selected_ids == []

    repository.save_board(_board(run_id="run-2"))
    service.handle_callback(_event("t"))
    assert repository.load_telegram_session("token123").status == "stale"
    assert "榜单已失效" in plugin.messages[-1]["text"]
    assert subscription.calls == []

    plugin2, repository2, subscription2, service2, clock2 = _service()
    service2.start("alice", "alice", _board())
    clock2[0] += timedelta(hours=25)
    service2.handle_callback(_event("t"))
    assert repository2.load_telegram_session("token123").status == "expired"
    assert "超过 24 小时" in plugin2.messages[-1]["text"]
    assert subscription2.calls == []


def test_missing_telegram_mapping_returns_summary_fallback_signal():
    """用户未绑定 Telegram 时不发送交互卡片并要求通知服务降级。"""
    plugin, _, subscription, service, _ = _service(target=None)

    assert service.start("alice", "alice", _board()) is False
    assert plugin.messages == []
    assert subscription.calls == []


def test_disabled_plugin_and_closed_session_cannot_subscribe():
    """插件停用或会话关闭后，旧按钮不再进入订阅安全链。"""
    plugin, repository, subscription, service, _ = _service()
    service.start("alice", "alice", _board())
    plugin.enabled = False

    service.handle_callback(_event("t"))

    assert repository.load_telegram_session("token123").status == "disabled"
    assert "插件当前已停用" in plugin.messages[-1]["text"]
    assert subscription.calls == []

    plugin2, repository2, subscription2, service2, _ = _service()
    service2.start("alice", "alice", _board())
    service2.handle_callback(_event("x"))
    service2.handle_callback(_event("t"))

    assert repository2.load_telegram_session("token123").status == "cancelled"
    assert "已经关闭" in plugin2.messages[-1]["text"]
    assert subscription2.calls == []


def test_pending_question_buttons_answer_directly_and_reject_wrong_user():
    """Telegram 问询按钮直接回答，越权点击不复用审计身份。"""
    center = FakePendingCenter()
    response = SimpleNamespace(
        success=True,
        message_id=88,
        chat_id="1001",
        source="Telegram",
    )
    plugin, repository, _, service, _ = _service(
        pending_center=center,
        direct_result=response,
    )
    item = PendingCenterItem(
        item_type="question",
        item_id="question-1",
        profile_id="alice",
        title="CinePilot Agent 需要你确认",
        summary="你更喜欢人物、节奏还是世界观？",
        created_at="2026-07-18T00:00:00+00:00",
        status="pending",
        options=(
            {"option_id": "character", "label": "人物"},
            {"option_id": "pace", "label": "节奏"},
            {"option_id": "world", "label": "世界观"},
        ),
        allow_custom_answer=True,
    )
    notice = PendingNotice(item=item, actor_id="mp-user-1")

    assert service.start_pending(
        username="alice",
        notice=notice,
        detail_link="https://mp.example/#/plugin-app/AgentRank/main?panel=pending",
    ) is True
    first = plugin.chain.edit_calls[-1]
    rendered = str(first)
    assert "人物" in rendered and "关闭问询" in rendered
    assert "1 天后" not in rendered and "不提醒" not in rendered
    assert "打开详情" in rendered
    assert "mp-user-1" not in rendered
    assert "profile_id" not in rendered

    service.handle_callback(_pending_event("o", "1", userid="9999"))
    assert center.calls == []
    assert repository.load_telegram_pending_session("token123").status == "open"

    service.handle_callback(_pending_event("o", "1"))

    assert len(center.calls) == 1
    assert center.calls[0]["action"] == "answer"
    assert center.calls[0]["option_id"] == "pace"
    assert center.calls[0]["actor_id"] == "mp-user-1"
    assert center.calls[0]["idempotency_key"].startswith("telegram-pending:")
    assert repository.load_telegram_pending_session("token123").status == "resolved"
    assert plugin.chain.delete_calls[-1]["message_id"] == "88"
    assert plugin.messages[-1].get("original_message_id") is None


def test_pending_superuser_command_never_offers_direct_confirmation():
    """需要管理员的全局权重命令不在 Telegram 提供直接确认。"""
    center = FakePendingCenter()
    response = SimpleNamespace(
        success=True,
        message_id=89,
        chat_id="1001",
        source="Telegram",
    )
    plugin, _, _, service, _ = _service(
        pending_center=center,
        direct_result=response,
    )
    notice = PendingNotice(
        item=PendingCenterItem(
            item_type="command",
            item_id="command-weight",
            profile_id="alice",
            title="调整全局基准权重",
            summary="将题材权重调整为 0.80",
            created_at="2026-07-18T00:00:00+00:00",
            status="pending_confirmation",
            requires_superuser=True,
        ),
        actor_id="mp-user-1",
    )

    service.start_pending(username="alice", notice=notice)
    message = plugin.chain.direct_calls[-1].__dict__
    callbacks = _callbacks(message)

    assert all(":y" not in value for value in callbacks)
    assert "需要管理员" in message["text"]


def test_legacy_pending_reminder_callback_is_ignored_without_state_change():
    """旧提醒回调不再映射任何动作，也不改变待处理会话状态。"""
    center = FakePendingCenter()
    response = SimpleNamespace(
        success=True,
        message_id=90,
        chat_id="1001",
        source="Telegram",
    )
    plugin, repository, _, service, _ = _service(
        pending_center=center,
        direct_result=response,
    )
    notice = PendingNotice(
        item=PendingCenterItem(
            item_type="proposal",
            item_id="proposal-1",
            profile_id="alice",
            title="确认新理解",
            summary="你可能偏好节奏紧凑的叙事",
            created_at="2026-07-18T00:00:00+00:00",
            status="pending_confirmation",
        ),
        actor_id="mp-user-1",
    )
    service.start_pending(username="alice", notice=notice)

    handled = service.handle_callback(_pending_event("3"))

    assert handled is False
    assert center.calls == []
    assert repository.load_telegram_pending_session("token123").status == "open"
    assert "天后" not in str(plugin.chain.edit_calls[-1])
