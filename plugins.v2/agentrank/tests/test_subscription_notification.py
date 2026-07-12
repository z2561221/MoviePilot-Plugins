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
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
archive_module = importlib.import_module(f"{PACKAGE_NAME}.model.archive")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
service_module = importlib.import_module(f"{PACKAGE_NAME}.service.subscription")
notification_module = importlib.import_module(f"{PACKAGE_NAME}.service.notification")
runtime_module = importlib.import_module(f"{PACKAGE_NAME}.service.runtime")
controller_module = importlib.import_module(f"{PACKAGE_NAME}.controller.api")

Candidate = candidate_module.Candidate
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
ArchiveFeedback = archive_module.ArchiveFeedback
ArchiveEntry = archive_module.ArchiveEntry
AgentRankRepository = repository_module.AgentRankRepository
SubscriptionService = service_module.SubscriptionService
NotificationService = notification_module.NotificationService
AgentRankRuntime = runtime_module.AgentRankRuntime
AgentRankApiController = controller_module.AgentRankApiController


class FakePlugin:
    """In-memory plugindata and notification recorder."""

    def __init__(self):
        self.data = {}
        self.messages = []

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


def _seed(repository, confidence=80, source_ids=None):
    source_ids = source_ids if source_ids is not None else {"tmdb": "1"}
    repository.save_board(
        RecommendationBoard(
            username="alice",
            run_id="run-1",
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
        "run-1",
        "alice",
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


def test_notification_confirmation_sends_summary_without_subscription_dependency():
    """Notify mode posts a UI-directed summary and cannot create subscriptions."""
    plugin = FakePlugin()
    board = RecommendationBoard(
        username="alice",
        run_id="run-1",
        status="success",
        recommendations=[
            RecommendationItem(
                candidate_id="tmdb:1",
                rank=1,
                title="One",
                summary="悬疑迷局牵出旧日真相",
            )
        ],
    )

    NotificationService(plugin).send_confirmation("alice", board)

    assert len(plugin.messages) == 1
    assert plugin.messages[0]["username"] == "alice"
    assert plugin.messages[0]["mtype"] is NotificationType.Subscribe
    assert plugin.messages[0]["parse_mode"] == "MarkdownV2"
    assert plugin.messages[0]["disable_web_page_preview"] is True
    assert plugin.messages[0]["text"].startswith("本轮 Agent 推荐已生成，共 1 条：\n\n```")
    assert "01 │ One\n   │ 悬疑迷局牵出旧日真相" in plugin.messages[0]["text"]
    assert "请前往 **Agent榜单中心** 手动订阅" in plugin.messages[0]["text"]
    assert "One" in plugin.messages[0]["text"]


def test_notification_confirmation_compacts_long_or_multiline_fields():
    """MarkdownV2 榜单压缩多行文本并保持两位排名和等宽列结构。"""
    plugin = FakePlugin()
    board = RecommendationBoard(
        username="alice",
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

    NotificationService(plugin).send_confirmation("alice", board)

    text = plugin.messages[0]["text"]
    assert text.count("```") == 2
    assert "10 │ A_B [Test] (2025)!" in text
    assert "   │ 第一行 第二行 间隔" in text
    assert "…" in text


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

    result = service.subscribe("alice", "tmdb:1", confidence_threshold=0.6)

    assert result.success is True
    assert result.changed is True
    assert len(chain.exists_calls) == 1
    assert chain.add_calls[0]["username"] == "alice"
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

    result = service.subscribe("alice", "tmdb:1", 0.6)

    assert result.success is True
    assert result.changed is False
    assert result.code == "already_subscribed"
    assert chain.add_calls == []


def test_manual_subscription_rejects_missing_snapshot_archive_and_low_confidence():
    """Snapshot membership, active archive, and confidence are hard gates."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed(repository, confidence=50)
    chain = FakeSubscribeChain()
    service = SubscriptionService(repository, chain, FakeMedia, lambda value: value)

    low = service.subscribe("alice", "tmdb:1", 0.6)
    assert low.code == "confidence_below_threshold"

    board = repository.load_board("alice")
    board.recommendations[0].confidence = 80
    repository.save_board(board)
    repository.save_archive(
        ArchiveFeedback(
            username="alice",
            entries=[ArchiveEntry(candidate_id="tmdb:1", original_rank=1)],
        )
    )
    archived = service.subscribe("alice", "tmdb:1", 0.6)
    assert archived.code == "candidate_archived"

    repository.save_archive(ArchiveFeedback(username="alice"))
    plugin.del_data(key="candidate_snapshot:run-1:alice")
    missing = service.subscribe("alice", "tmdb:1", 0.6)
    assert missing.code == "candidate_not_in_snapshot"
    assert chain.add_calls == []


def test_unrecognizable_candidate_and_add_failure_are_visible():
    """Missing supported IDs and SubscribeChain.add failures return stable results."""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed(repository, source_ids={})
    chain = FakeSubscribeChain(add_result=(None, "recognition failed"))
    service = SubscriptionService(repository, chain, FakeMedia, lambda value: value)

    unrecognizable = service.subscribe("alice", "tmdb:1", 0.6)
    assert unrecognizable.code == "candidate_unrecognizable"

    _seed(repository, source_ids={"douban": "db-1"})
    failed = service.subscribe("alice", "tmdb:1", 0.6)
    assert failed.success is False
    assert failed.code == "subscription_failed"
    assert failed.message == "recognition failed"


def test_runtime_notify_mode_sends_summary_after_success_without_subscribing():
    """Runtime post-processing invokes only NotificationService in notify mode."""
    plugin = FakePlugin()
    board = RecommendationBoard(username="alice", run_id="run-1", status="success")

    class Orchestrator:
        async def run(self, username, config):
            return SimpleNamespace(status="success", board=board)

    runtime = AgentRankRuntime(
        plugin,
        {"enabled": True, "action_mode": "notify", "users": ["alice"]},
        Orchestrator(),
        lambda cron: cron,
        notification_service=NotificationService(plugin),
    )

    asyncio.run(runtime.refresh("alice"))

    assert len(plugin.messages) == 1


def test_runtime_failure_sends_one_subscribe_notification_with_old_board_state():
    """A failed Agent result emits one concise Subscribe notification."""
    plugin = FakePlugin()
    board = RecommendationBoard(username="alice", run_id="old", status="success")

    class Orchestrator:
        async def run(self, username, config):
            return SimpleNamespace(
                status="agent_failed",
                run_id="run-failed",
                message="Agent did not produce text output",
                board=board,
            )

    runtime = AgentRankRuntime(
        plugin,
        {"enabled": True, "notify": True, "users": ["alice"]},
        Orchestrator(),
        lambda cron: cron,
        notification_service=NotificationService(plugin),
    )

    asyncio.run(runtime.refresh("alice"))

    assert len(plugin.messages) == 1
    assert plugin.messages[0]["mtype"] == NotificationType.Subscribe
    assert plugin.messages[0]["title"] == "Agent榜单中心运行异常"
    assert "run-failed" in plugin.messages[0]["text"]
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
        "users": ["alice"],
        "default_user": "alice",
        "confidence_threshold": 0.6,
    }

    response = AgentRankApiController(plugin).subscribe(
        {"username": "alice", "candidate_id": "tmdb:1"}
    )

    assert response["success"] is True
    assert response["data"]["code"] == "subscription_created"
