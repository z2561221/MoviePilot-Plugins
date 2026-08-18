"""AgentRank notification confirmation and safe manual subscription tests."""

import importlib
import asyncio
import sys
from enum import Enum
from pathlib import Path
from types import ModuleType, SimpleNamespace

from fastapi import Depends, HTTPException


PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"
PACKAGE_NAME = "agentrank_subscription_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

app_module = sys.modules.setdefault("app", ModuleType("app"))
schemas_module = sys.modules.setdefault("app.schemas", ModuleType("app.schemas"))
types_module = sys.modules.setdefault("app.schemas.types", ModuleType("app.schemas.types"))
sdk_module = sys.modules.setdefault("app.sdk", ModuleType("app.sdk"))
security_module = sys.modules.setdefault(
    "app.sdk.security", ModuleType("app.sdk.security")
)


class TokenPayload:
    """测试使用的最小 MoviePilot 登录载荷。"""

    def __init__(self, sub=None, username=None, super_user=False):
        self.sub = sub
        self.username = username
        self.super_user = super_user


class MediaSource(str):
    """测试使用的可扩展 V3 媒体来源值。"""

    def __new__(cls, value):
        instance = str.__new__(cls, value)
        instance.value = value
        return instance


MediaSource.TMDB = MediaSource("themoviedb")
MediaSource.Douban = MediaSource("douban")


def verify_token():
    """为控制器 FastAPI 签名提供测试鉴权依赖。"""
    return TokenPayload(sub=1, username="admin", super_user=True)


class NotificationType(Enum):
    """测试使用的最小 MoviePilot 通知类型枚举。"""

    Subscribe = "订阅"
    Manual = "手动处理"
    Plugin = "插件"
    Agent = "智能体"


app_module.schemas = schemas_module
app_module.sdk = sdk_module
sdk_module.security = security_module
schemas_module.types = types_module
schemas_module.TokenPayload = TokenPayload
types_module.NotificationType = NotificationType
types_module.MediaSource = MediaSource
security_module.verify_token = verify_token

candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
snapshot_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate_snapshot")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
pending_model_module = importlib.import_module(
    f"{PACKAGE_NAME}.model.pending_center"
)
support_module = importlib.import_module(f"{PACKAGE_NAME}.model.support")
archive_module = importlib.import_module(f"{PACKAGE_NAME}.model.archive")
feedback_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback")
run_module = importlib.import_module(f"{PACKAGE_NAME}.model.run")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
service_module = importlib.import_module(f"{PACKAGE_NAME}.service.subscription")
notification_module = importlib.import_module(f"{PACKAGE_NAME}.service.notification")
notification_type_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.notification_type"
)
runtime_module = importlib.import_module(f"{PACKAGE_NAME}.service.runtime")
controller_module = importlib.import_module(f"{PACKAGE_NAME}.controller.api")

Candidate = candidate_module.Candidate
CandidateSnapshot = snapshot_module.CandidateSnapshot
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
SupportContribution = support_module.SupportContribution
SupportScore = support_module.SupportScore
ArchiveFeedback = archive_module.ArchiveFeedback
ArchiveEntry = archive_module.ArchiveEntry
FeedbackEvent = feedback_module.FeedbackEvent
RecommendationRun = run_module.RecommendationRun
AgentRankRepository = repository_module.AgentRankRepository
SubscriptionService = service_module.SubscriptionService
NotificationService = notification_module.NotificationService
AgentRankRuntime = runtime_module.AgentRankRuntime
AgentRankApiController = controller_module.AgentRankApiController
PendingCenterItem = pending_model_module.PendingCenterItem
PendingNotice = pending_model_module.PendingNotice


def test_notification_type_options_follow_current_host_enum():
    """配置选项动态复用当前 MoviePilot 宿主通知类型。"""
    options = notification_type_module.notification_type_options(NotificationType)

    assert options == [
        {"title": item.value, "value": item.name} for item in NotificationType
    ]

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


def _support(percentage=80):
    """构造百分之八十或五十的可重算订阅测试支持度。"""
    positive_units, counter_units = {
        80: (9_000, 1_000),
        50: (7_500, 2_500),
    }[int(percentage)]
    return SupportScore.from_contributions(
        "policy-v1-subscription-test",
        [
            SupportContribution(
                dimension="type_weight",
                direction="positive",
                user_value="movie",
                candidate_value="movie",
                user_refs=("playback:observed:1", "playback:observed:2"),
                candidate_ref="candidate:test:media_type:0",
                weight_units=positive_units,
                certainty_units=10_000,
                contribution_units=positive_units,
            ),
            SupportContribution(
                dimension="theme_weight",
                direction="counter",
                user_value="恐怖",
                candidate_value="恐怖",
                user_refs=("memory:negative",),
                candidate_ref="candidate:test:genres:0",
                weight_units=counter_units,
                certainty_units=10_000,
                contribution_units=counter_units,
            ),
        ],
    )


class FakePlugin:
    """In-memory plugindata and notification recorder."""

    def __init__(self):
        self.data = {}
        self.messages = []
        self._config = {"notification_type": "Plugin"}

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


def _seed(repository, support_percentage=80, source_ids=None, run_id="run-1"):
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
                    support=_support(support_percentage),
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


def _notification_board(run_id, candidate_ids):
    """构造只包含候选身份的通知测试榜单。"""
    return RecommendationBoard(
        profile_id=PROFILE_ID,
        username="Alice",
        run_id=run_id,
        status="success",
        recommendations=[
            RecommendationItem(
                candidate_id=candidate_id,
                rank=index,
                title=f"Title {candidate_id}",
            )
            for index, candidate_id in enumerate(candidate_ids, start=1)
        ],
    )


def _append_notification_run(repository, board):
    """保存通知去重所需的最小运行历史记录。"""
    repository.append_run(
        RecommendationRun(
            profile_id=board.profile_id,
            run_id=board.run_id,
            username=board.username,
            status=board.status,
            metrics={
                "recommendation_candidate_ids": [
                    item.candidate_id for item in board.recommendations
                ]
            },
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
    assert plugin.messages[0]["mtype"] is NotificationType.Plugin
    assert plugin.messages[0]["parse_mode"] == "MarkdownV2"
    assert plugin.messages[0]["disable_web_page_preview"] is True
    assert plugin.messages[0]["text"].startswith("本轮 克里斯蒂娜 推荐已生成，共 1 条：\n\n```")
    assert "01 │ One\n   │ 推荐：悬疑迷局层层牵出尘封往事与真相" in plugin.messages[0]["text"]
    assert "   │ 简介：悬疑迷局层层牵出尘封往事与真相" in plugin.messages[0]["text"]
    assert "请前往 **克里斯蒂娜** 手动订阅" in plugin.messages[0]["text"]
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


def test_unacted_duplicate_board_is_suppressed_without_negative_feedback():
    """无操作的同一榜单只抑制通知，不写入任何负向反馈事实。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    plugin._repository = repository
    first = _notification_board("run-notify-1", ["tmdb:1", "tmdb:2"])
    second = _notification_board("run-notify-2", ["tmdb:2", "tmdb:1"])
    _append_notification_run(repository, first)
    service = NotificationService(plugin)

    assert service.send_confirmation("Alice", first) is True
    _append_notification_run(repository, second)

    assert service.send_confirmation("Alice", second) is False
    assert len(plugin.messages) == 1
    assert repository.load_feedback_events(PROFILE_ID) == []
    latest = repository.load_run_history(PROFILE_ID)[0]
    assert latest.metrics["recommendation_notification_status"] == (
        "suppressed_unacted_duplicate"
    )


def test_explicit_feedback_allows_same_board_to_be_notified_again():
    """明确反馈后相同候选集合可以再次发送，排序变化不绕过去重指纹。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    plugin._repository = repository
    first = _notification_board("run-notify-feedback-1", ["tmdb:1", "tmdb:2"])
    second = _notification_board("run-notify-feedback-2", ["tmdb:2", "tmdb:1"])
    _append_notification_run(repository, first)
    service = NotificationService(plugin)
    assert service.send_confirmation("Alice", first) is True

    repository.append_feedback_event(
        FeedbackEvent(
            profile_id=PROFILE_ID,
            kind="like",
            candidate_id="tmdb:1",
            run_id=first.run_id,
            idempotency_key="notify-feedback-1",
        )
    )
    _append_notification_run(repository, second)

    assert service.send_confirmation("Alice", second) is True
    assert len(plugin.messages) == 2
    assert repository.load_run_history(PROFILE_ID)[0].metrics[
        "recommendation_notification_status"
    ] == "sent"


def test_failure_notification_hides_addresses_credentials_and_emby_identity():
    """运行失败通知只展示安全原因，不泄露 Emby 连接或身份细节。"""
    plugin = FakePlugin()

    NotificationService(plugin).send_failure(
        username="Alice",
        status="playback_unavailable",
        run_id="run-1",
        message=(
            "emby:home:user-1 http://192.0.2.12:8096 "
            "198.51.100.8:8096 host=emby.local:8096 "
            "token=secret-value userid=user-1"
        ),
        old_board_preserved=True,
    )

    text = plugin.messages[-1]["text"]
    assert plugin.messages[-1]["mtype"] is NotificationType.Plugin
    assert "Alice" not in text
    assert "emby:home:user-1" not in text
    assert "192.0.2.12" not in text
    assert "198.51.100.8" not in text
    assert "emby.local" not in text
    assert "secret-value" not in text
    assert "user-1" not in text
    assert "已隐藏" in text


def test_notification_type_is_shared_by_ranking_failure_and_pending_messages():
    """榜单、异常与待处理通知统一读取用户选择的 MoviePilot 通知类型。"""
    plugin = FakePlugin()
    plugin._config["notification_type"] = "Manual"
    board = RecommendationBoard(
        profile_id=PROFILE_ID,
        username="Alice",
        run_id="run-notice-type",
        status="success",
        recommendations=[RecommendationItem(candidate_id="tmdb:1", rank=1, title="One")],
    )
    service = NotificationService(plugin)

    service.send_confirmation("Alice", board)
    service.send_failure("Alice", "failed", "run-notice-type", "失败", True)
    service.send_pending(
        "Alice",
        PendingNotice(
            item=PendingCenterItem(
                item_type="question",
                item_id="question-notice-type",
                profile_id=PROFILE_ID,
                title="需要补充",
                summary="请补充整体偏好",
                created_at="2026-07-29T00:00:00+00:00",
                status="pending",
            )
        ),
    )

    assert len(plugin.messages) == 3
    assert all(message["mtype"] is NotificationType.Manual for message in plugin.messages)


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
    assert chain.add_calls[0]["username"] == "Agent榜单中心"
    assert chain.add_calls[0]["media_source"] == MediaSource.TMDB
    assert chain.add_calls[0]["media_id"] == "1"
    assert "tmdbid" not in chain.add_calls[0]
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


def test_manual_subscription_rejects_missing_snapshot_archive_and_low_support():
    """快照成员、有效归档和确定性支持度均为订阅硬门。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed(repository, support_percentage=50)
    chain = FakeSubscribeChain()
    service = SubscriptionService(repository, chain, FakeMedia, lambda value: value)

    low = service.subscribe(PROFILE_ID, "tmdb:1", 0.6)
    assert low.code == "support_below_threshold"

    board = repository.load_board(PROFILE_ID)
    board.recommendations[0].support = _support(80)
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


def test_legacy_confidence_only_board_is_closed_until_regenerated():
    """旧榜单即使 confidence 很高也不得绕过确定性支持度。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    _seed(repository)
    board = repository.load_board(PROFILE_ID)
    board.recommendations[0].support = None
    board.recommendations[0].confidence = 100
    repository.save_board(board)
    chain = FakeSubscribeChain()
    service = SubscriptionService(
        repository,
        chain,
        FakeMedia,
        lambda value: value,
    )

    result = service.subscribe(PROFILE_ID, "tmdb:1", 0.6)

    assert result.success is False
    assert result.code == "support_unavailable"
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


def test_runtime_notify_mode_sends_board_for_manual_and_background_runs():
    """通知内选择模式下，页面手动与后台周期运行都发送交互榜单。"""
    plugin = FakePlugin()
    board = RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="run-1", status="success")

    class Orchestrator:
        async def run(self, profile_id, config, *, trigger_reason=""):
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
    asyncio.run(runtime.run_scheduled())

    assert len(plugin.messages) == 2


def test_runtime_failure_only_notifies_for_background_run_with_old_board_state():
    """页面手动失败留在界面，后台失败才发送一次配置通知。"""
    plugin = FakePlugin()
    board = RecommendationBoard(profile_id=PROFILE_ID, username="Alice", run_id="old", status="success")

    class Orchestrator:
        async def run(self, profile_id, config, *, trigger_reason=""):
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
    assert plugin.messages == []
    asyncio.run(runtime.run_scheduled())

    assert len(plugin.messages) == 1
    assert plugin.messages[0]["mtype"] == NotificationType.Plugin
    assert plugin.messages[0]["title"] == "克里斯蒂娜运行异常"
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


def test_pending_fallback_notification_is_safe_and_keeps_detail_entry():
    """非交互渠道只收到安全摘要，宿主仍可附加插件详情链接。"""
    plugin = FakePlugin()
    notice = PendingNotice(
        item=PendingCenterItem(
            item_type="question",
            item_id="question-1",
            profile_id=PROFILE_ID,
            title="CinePilot Agent 需要你确认",
            summary=(
                "请确认这个理解 token=secret-value "
                "http://192.0.2.13:3000/internal"
            ),
            created_at="2026-07-28T00:00:00+00:00",
            status="pending",
            options=({"option_id": "one", "label": "选项一"},),
        ),
        actor_id="mp-user-1",
    )

    interactive = NotificationService(plugin).send_pending("Alice", notice)

    assert interactive is False
    assert len(plugin.messages) == 1
    rendered = str(plugin.messages[0])
    assert plugin.messages[0]["title"] == "克里斯蒂娜待处理"
    assert "尚未生效" in rendered and "待处理区域" in rendered
    assert "192.0.2.13" not in rendered
    assert "secret-value" not in rendered
    assert PROFILE_ID not in rendered
    assert "mp-user-1" not in rendered


def test_runtime_registers_no_pending_reminder_scheduler_or_sender():
    """运行时不再注册待处理提醒任务或暴露提醒发送方法。"""
    plugin = FakePlugin()
    runtime = AgentRankRuntime(
        plugin,
        {"enabled": True, "notify": True, **IDENTITY_CONFIG},
        orchestrator=SimpleNamespace(),
        notification_service=SimpleNamespace(),
        pending_center_service=SimpleNamespace(),
    )

    service_ids = {item["id"] for item in runtime.get_services()}
    assert "AgentRank.PendingReminders" not in service_ids
    assert not hasattr(runtime, "send_pending_reminders")


def test_runtime_registers_periodic_outcome_recheck_for_each_profile():
    """运行时每十分钟为全部配置画像执行一次可信结果复查。"""
    plugin = FakePlugin()

    class Attribution:
        """记录归因复查画像。"""

        def __init__(self):
            """创建空调用列表。"""
            self.calls = []

        def verify_profile(self, profile_id):
            """返回可序列化复查摘要。"""
            self.calls.append(profile_id)
            return SimpleNamespace(
                to_dict=lambda: {
                    "profile_id": profile_id,
                    "checked": 1,
                    "advanced": 0,
                    "pending": 0,
                }
            )

    attribution = Attribution()
    runtime = AgentRankRuntime(
        plugin,
        {"enabled": True, **IDENTITY_CONFIG},
        orchestrator=SimpleNamespace(),
        attribution_service=attribution,
        attribution_trigger_factory=lambda: "every-ten-minutes",
    )

    service = next(
        item
        for item in runtime.get_services()
        if item["id"] == "AgentRank.OutcomeAttribution"
    )
    results = service["func"]()

    assert service["trigger"] == "every-ten-minutes"
    assert attribution.calls == [PROFILE_ID]
    assert results[0]["profile_id"] == PROFILE_ID
