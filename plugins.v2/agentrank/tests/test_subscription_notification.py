"""AgentRank notification confirmation and safe manual subscription tests."""

import importlib
import asyncio
import sys
from enum import Enum
from pathlib import Path
from types import ModuleType, SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_subscription_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

app_module = sys.modules.setdefault("app", ModuleType("app"))
schemas_module = sys.modules.setdefault("app.schemas", ModuleType("app.schemas"))
types_module = sys.modules.setdefault("app.schemas.types", ModuleType("app.schemas.types"))


class NotificationType(Enum):
    """测试使用的最小 MoviePilot 通知类型枚举。"""

    Subscribe = "订阅"


app_module.schemas = schemas_module
schemas_module.types = types_module
types_module.NotificationType = NotificationType

candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
snapshot_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate_snapshot")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
archive_module = importlib.import_module(f"{PACKAGE_NAME}.model.archive")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
service_module = importlib.import_module(f"{PACKAGE_NAME}.service.subscription")
notification_module = importlib.import_module(f"{PACKAGE_NAME}.service.notification")
runtime_module = importlib.import_module(f"{PACKAGE_NAME}.service.runtime")
controller_module = importlib.import_module(f"{PACKAGE_NAME}.controller.api")

Candidate = candidate_module.Candidate
CandidateSnapshot = snapshot_module.CandidateSnapshot
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
ArchiveFeedback = archive_module.ArchiveFeedback
ArchiveEntry = archive_module.ArchiveEntry
AgentRankRepository = repository_module.AgentRankRepository
SubscriptionService = service_module.SubscriptionService
NotificationService = notification_module.NotificationService
AgentRankRuntime = runtime_module.AgentRankRuntime
AgentRankApiController = controller_module.AgentRankApiController

PROFILE_ID = "emby:home:user-1"
IDENTITY_CONFIG = {
    "emby_identities": [
        {
            "server_name": "home",
            "user_id": "user-1",
            "username": "Alice",
            "profile_id": PROFILE_ID,
            "schema_version": 1,
        }
    ],
    "default_profile_id": PROFILE_ID,
}


class FakePlugin:
    """In-memory plugindata and notification recorder."""

    def __init__(self):
        self.data = {}
        self.messages = []

    def get_state(self):
        """模拟已通过硬依赖门禁的运行中插件。"""
        return True

    def get_data(self, key=None):
        return self.data.get(key)

    def save_data(self, key=None, value=None):
        self.data[key] = value

    def del_data(self, key=None):
        self.data.pop(key, None)

    def post_message(self, **kwargs):
        self.messages.append(kwargs)


class FakeSubscribeChain:
    """Record exists/add calls and expose configurable results."""

    def __init__(self, exists=False, add_result=(123, "ok")):
        self.exists_result = exists
        self.add_result = add_result
        self.exists_calls = []
        self.add_calls = []

    def exists(self, mediainfo, meta=None):
        self.exists_calls.append((mediainfo, meta))
        return self.exists_result

    def add(self, **kwargs):
        self.add_calls.append(kwargs)
        return self.add_result


class FakeMedia:
    """Simple MediaInfo stand-in receiving normalized keyword fields."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeSubscriptionAdapter:
    """返回跨全部用户名聚合后的类型化订阅身份。"""

    def __init__(self, candidate_ids=None, error=None):
        """配置已有订阅集合或模拟查重故障。"""
        self.values = set(candidate_ids or set())
        self.error = error
        self.calls = 0

    def candidate_ids(self):
        """返回全局订阅身份，或抛出配置的数据库异常。"""
        self.calls += 1
        if self.error is not None:
            raise self.error
        return set(self.values)


def _legacy_snapshot(run_id, candidates):
    """构造供旧榜单订阅兼容测试使用的 schema 2 快照。"""
    return CandidateSnapshot(
        profile_id=PROFILE_ID,
        run_id=run_id,
        profile_version={},
        retrieval_plan={},
        candidates=candidates,
        schema_version=2,
    ).seal()


def _seed(repository, confidence=80, source_ids=None, run_id="run-1"):
    source_ids = source_ids if source_ids is not None else {"tmdb": "1"}
    repository.save_board(
        RecommendationBoard(
            profile_id=PROFILE_ID,
            username="Alice",
            run_id=run_id,
            status="success",
            recommendations=[
                RecommendationItem(
                    candidate_id="tmdb:1",
                    rank=1,
                    title="One",
                    media_type="movie",
                    confidence=confidence,
                    source_ids=source_ids,
                )
            ],
        )
    )
    repository.save_candidate_snapshot(
        _legacy_snapshot(
            run_id,
        [
            Candidate(
                candidate_id="tmdb:1",
                title="One",
                media_type="movie",
                year=2025,
                source_ids=source_ids,
            )
        ],
        )
    )


def test_notification_confirmation_sends_summary_without_subscription_dependency():
    """Notify mode posts a UI-directed summary and cannot create subscriptions."""
    plugin = FakePlugin()
    board = RecommendationBoard(
        profile_id=PROFILE_ID,
        username="Alice",
        run_id="run-1",
        status="success",
        recommendations=[
            RecommendationItem(
                candidate_id="tmdb:1",
                rank=1,
                title="One",
                summary="悬疑迷局层层牵出尘封往事与真相",
            )
        ],
    )

    NotificationService(plugin).send_confirmation("Alice", board)

    assert len(plugin.messages) == 1
    assert plugin.messages[0]["username"] == "Alice"
    assert plugin.messages[0]["mtype"] is NotificationType.Subscribe
    assert plugin.messages[0]["parse_mode"] == "MarkdownV2"
    assert plugin.messages[0]["disable_web_page_preview"] is True
    assert plugin.messages[0]["text"].startswith("本轮 Agent 推荐已生成，共 1 条：\n\n```")
    assert "01 │ One\n   │ 推荐：悬疑迷局层层牵出尘封往事与真相" in plugin.messages[0]["text"]
    assert "   │ 简介：悬疑迷局层层牵出尘封往事与真相" in plugin.messages[0]["text"]
    assert "请前往 **Agent榜单中心** 手动订阅" in plugin.messages[0]["text"]
    assert "One" in plugin.messages[0]["text"]


def test_notification_confirmation_compacts_long_or_multiline_fields():
    """MarkdownV2 榜单压缩多行文本并保持两位排名和等宽列结构。"""
    plugin = FakePlugin()
    board = RecommendationBoard(
        profile_id=PROFILE_ID,
        username="Alice",
        run_id="run-mdv2",
        status="success",
        recommendations=[
            RecommendationItem(
                candidate_id="tmdb:10",
                rank=10,
                title="A_B [Test] (2025)! " * 5,
                summary="第一行\n第二行   间隔",
            )
        ],
    )

    NotificationService(plugin).send_confirmation("Alice", board)

    text = plugin.messages[0]["text"]
    assert text.count("```") == 2
    assert "10 │ A_B [Test] (2025)!" in text
    assert "   │ 推荐：第一行 第二行 间隔" in text
    assert "   │ 简介：第一行 第二行 间隔" in text
    assert "…" in text


def test_notification_confirmation_prefers_interactive_card_when_available():
    """Telegram 自选卡片发送成功后不再重复发送摘要。"""
    plugin = FakePlugin()
    board = RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="run-1", status="success")

    class InteractionService:
        """记录自选卡片启动参数。"""

        def __init__(self):
            self.calls = []

        def start(self, profile_id, username, current_board):
            """模拟已发送交互卡片。"""
            self.calls.append((profile_id, username, current_board.run_id))
            return True

    interaction = InteractionService()
    NotificationService(plugin, interaction).send_confirmation("Alice", board)

    assert interaction.calls == [(PROFILE_ID, "Alice", "run-1")]
    assert plugin.messages == []


def test_failure_notification_hides_addresses_credentials_and_emby_identity():
    """运行失败通知只展示安全原因，不泄露 Emby 连接或身份细节。"""
    plugin = FakePlugin()

    NotificationService(plugin).send_failure(
        username="Alice",
        status="playback_unavailable",
        run_id="run-1",
        message=(
            "emby:home:user-1 http://192.168.50.5:8096 "
            "10.0.0.8:8096 host=emby.local:8096 "
            "token=secret-value userid=user-1"
        ),
        old_board_preserved=True,
    )

    text = plugin.messages[-1]["text"]
    assert "Alice" not in text
    assert "emby:home:user-1" not in text
    assert "192.168.50.5" not in text
    assert "10.0.0.8" not in text
    assert "emby.local" not in text
    assert "secret-value" not in text
    assert "user-1" not in text
    assert "已隐藏" in text


def test_manual_subscription_passes_username_and_identifiers_after_all_gates():
    """A valid board item calls exists then add with the target username."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed(repository)
    chain = FakeSubscribeChain()
    service = SubscriptionService(
        repository,
        subscribe_chain=chain,
        media_factory=FakeMedia,
        media_type_factory=lambda value: value,
    )

    result = service.subscribe(PROFILE_ID, "tmdb:1", confidence_threshold=0.6)

    assert result.success is True
    assert result.changed is True
    assert len(chain.exists_calls) == 1
    assert chain.add_calls[0]["username"] == "AgentRank"
    assert chain.add_calls[0]["tmdbid"] == 1
    assert chain.add_calls[0]["message"] is False
    assert chain.add_calls[0]["exist_ok"] is False


def test_existing_subscription_is_idempotent_and_never_calls_add():
    """SubscribeChain.exists is a final duplicate gate."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed(repository)
    chain = FakeSubscribeChain(exists=True)
    service = SubscriptionService(repository, chain, FakeMedia, lambda value: value)

    result = service.subscribe(PROFILE_ID, "tmdb:1", 0.6)

    assert result.success is True
    assert result.changed is False
    assert result.code == "already_subscribed"
    assert chain.add_calls == []


def test_other_username_subscription_blocks_creation_before_chain_calls():
    """其他用户名下的同类型 TMDB 订阅必须阻止 AgentRank 重复创建。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed(repository)
    chain = FakeSubscribeChain()
    adapter = FakeSubscriptionAdapter({"tmdb:movie:1"})
    service = SubscriptionService(
        repository,
        chain,
        FakeMedia,
        lambda value: value,
        subscription_adapter=adapter,
    )

    result = service.subscribe(PROFILE_ID, "tmdb:1", 0.6)

    assert result.success is True
    assert result.changed is False
    assert result.code == "already_subscribed"
    assert adapter.calls == 1
    assert chain.exists_calls == []
    assert chain.add_calls == []


def test_global_duplicate_check_failure_stops_closed_without_creation():
    """全局订阅读取失败时不得绕过查重继续创建订阅。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed(repository)
    chain = FakeSubscribeChain()
    adapter = FakeSubscriptionAdapter(error=RuntimeError("database unavailable"))
    service = SubscriptionService(
        repository,
        chain,
        FakeMedia,
        lambda value: value,
        subscription_adapter=adapter,
    )

    result = service.subscribe(PROFILE_ID, "tmdb:1", 0.6)

    assert result.success is False
    assert result.changed is False
    assert result.code == "subscription_duplicate_check_failed"
    assert adapter.calls == 1
    assert chain.exists_calls == []
    assert chain.add_calls == []


def test_manual_subscription_rejects_missing_snapshot_archive_and_low_confidence():
    """Snapshot membership, active archive, and confidence are hard gates."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed(repository, confidence=50)
    chain = FakeSubscribeChain()
    service = SubscriptionService(repository, chain, FakeMedia, lambda value: value)

    low = service.subscribe(PROFILE_ID, "tmdb:1", 0.6)
    assert low.code == "confidence_below_threshold"

    board = repository.load_board(PROFILE_ID)
    board.recommendations[0].confidence = 80
    repository.save_board(board)
    repository.save_archive(
        ArchiveFeedback(
            profile_id=PROFILE_ID,
            username="Alice",
            entries=[ArchiveEntry(candidate_id="tmdb:1", original_rank=1)],
        )
    )
    archived = service.subscribe(PROFILE_ID, "tmdb:1", 0.6)
    assert archived.code == "candidate_archived"

    repository.save_archive(ArchiveFeedback(profile_id=PROFILE_ID, username="Alice"))
    plugin.del_data(key=repository._candidate_key("run-1", PROFILE_ID))
    missing = service.subscribe(PROFILE_ID, "tmdb:1", 0.6)
    assert missing.code == "candidate_not_in_snapshot"
    assert chain.add_calls == []


def test_unrecognizable_candidate_and_add_failure_are_visible():
    """Missing supported IDs and SubscribeChain.add failures return stable results."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed(repository, source_ids={})
    chain = FakeSubscribeChain(add_result=(None, "recognition failed"))
    service = SubscriptionService(repository, chain, FakeMedia, lambda value: value)

    unrecognizable = service.subscribe(PROFILE_ID, "tmdb:1", 0.6)
    assert unrecognizable.code == "candidate_unrecognizable"

    _seed(repository, source_ids={"douban": "db-1"}, run_id="run-2")
    failed = service.subscribe(PROFILE_ID, "tmdb:1", 0.6)
    assert failed.success is False
    assert failed.code == "subscription_failed"
    assert failed.message == "recognition failed"


def test_runtime_notify_mode_sends_summary_after_success_without_subscribing():
    """Runtime post-processing invokes only NotificationService in notify mode."""
    plugin = FakePlugin()
    board = RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="run-1", status="success")

    class Orchestrator:
        async def run(self, profile_id, config):
            return SimpleNamespace(status="success", board=board)

    runtime = AgentRankRuntime(
        plugin,
        {"enabled": True, "action_mode": "notify", **IDENTITY_CONFIG},
        Orchestrator(),
        lambda cron: cron,
        notification_service=NotificationService(plugin),
    )

    asyncio.run(runtime.refresh(PROFILE_ID))

    assert len(plugin.messages) == 1


def test_runtime_failure_sends_one_subscribe_notification_with_old_board_state():
    """A failed Agent result emits one concise Subscribe notification."""
    plugin = FakePlugin()
    board = RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success")

    class Orchestrator:
        async def run(self, profile_id, config):
            return SimpleNamespace(
                status="agent_failed",
                run_id="run-failed",
                message="Agent did not produce text output",
                board=board,
            )

    runtime = AgentRankRuntime(
        plugin,
        {"enabled": True, "notify": True, **IDENTITY_CONFIG},
        Orchestrator(),
        lambda cron: cron,
        notification_service=NotificationService(plugin),
    )

    asyncio.run(runtime.refresh(PROFILE_ID))

    assert len(plugin.messages) == 1
    assert plugin.messages[0]["mtype"] == NotificationType.Subscribe
    assert plugin.messages[0]["title"] == "Agent榜单中心运行异常"
    assert "run-failed" in plugin.messages[0]["text"]
    assert "状态：Agent 调用失败" in plugin.messages[0]["text"]
    assert "agent_failed" not in plugin.messages[0]["text"]
    assert "旧榜单：已保留" in plugin.messages[0]["text"]


def test_subscribe_api_returns_service_result_after_runtime_integration():
    """The bearer controller delegates to the same manual safety service."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed(repository)
    service = SubscriptionService(
        repository,
        FakeSubscribeChain(),
        FakeMedia,
        lambda value: value,
    )
    plugin._repository = repository
    plugin._runtime = SimpleNamespace(subscription_service=service)
    plugin._config = {
        **IDENTITY_CONFIG,
        "confidence_threshold": 0.6,
    }

    response = AgentRankApiController(plugin).subscribe(
        {"profile_id": PROFILE_ID, "candidate_id": "tmdb:1"}
    )

    assert response["success"] is True
    assert response["data"]["code"] == "subscription_created"
