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


class NotificationType(Enum):
    """测试使用的通知类型。"""

    Subscribe = "订阅"


class MessageChannel(Enum):
    """测试使用的消息渠道。"""

    Telegram = "Telegram"


app_module.schemas = schemas_module
schemas_module.types = types_module
types_module.NotificationType = NotificationType
types_module.MessageChannel = MessageChannel

board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
interaction_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.telegram_interaction"
)

RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
AgentRankRepository = repository_module.AgentRankRepository
TelegramSelectionService = interaction_module.TelegramSelectionService


class FakePlugin:
    """记录插件数据与发送消息的测试替身。"""

    def __init__(self):
        self.data = {}
        self.messages = []
        self._poster_service = None
        self.enabled = True

    def get_data(self, key=None):
        """读取内存插件数据。"""
        return self.data.get(key)

    def save_data(self, key=None, value=None):
        """保存内存插件数据。"""
        self.data[key] = value

    def del_data(self, key=None):
        """删除内存插件数据。"""
        self.data.pop(key, None)

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
            reason="较长推荐理由不会进入紧凑单页通知正文",
            summary="较长剧情简介也不会挤占移动端通知空间",
            poster_path=f"https://image.tmdb.org/t/p/w200/{index}.jpg",
            backdrop_path=f"https://image.tmdb.org/t/p/w1280/backdrop-{index}.jpg",
            source_ids={"tmdb": str(index)},
            match_tags=["日本动画偏好", "古装历史题材"],
        )
        for index in range(1, 11)
    ]
    return board


def _service(now=None, target="1001"):
    """创建固定令牌和时钟的交互服务。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    subscription = FakeSubscriptionService()
    clock = [now or datetime(2026, 7, 18, tzinfo=timezone.utc)]
    service = TelegramSelectionService(
        plugin=plugin,
        repository=repository,
        subscription_service=subscription,
        config={"confidence_threshold": 0.6},
        target_adapter=FakeTargetAdapter(target),
        token_factory=lambda: "token123",
        now_factory=lambda: clock[0],
    )
    return plugin, repository, subscription, service, clock


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


def _callbacks(message):
    """提取消息内全部回调按钮。"""
    return [
        button["callback_data"]
        for row in message.get("buttons") or []
        for button in row
        if button.get("callback_data")
    ]


def test_start_sends_linked_single_line_top_list_with_horizontal_cover():
    """初始通知用榜首横版封面和紧凑单行榜单展示 TMDB 标题链接。"""
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
        '第一部电影</a> · 2025 · 92%'
    ) in message["text"]
    assert (
        '<code>02</code> <a href="https://www.themoviedb.org/tv/2">'
        '第二部剧集</a> · 2026 · 88%'
    ) in message["text"]
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
    assert message["mtype"] is NotificationType.Subscribe
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
        message["mtype"] is NotificationType.Subscribe for message in plugin.messages
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

    service.handle_callback(_event("c"))
    assert len(subscription.calls) == 2
    assert "不会重复提交" in plugin.messages[-1]["text"]


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
