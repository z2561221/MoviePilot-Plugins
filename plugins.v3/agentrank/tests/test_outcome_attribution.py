"""原生抽屉、订阅、入库、播放与复查失败的结果归因测试。"""

import copy
import importlib
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_outcome_attribution_test"
PROFILE_ID = "emby:home:user-1"
RUN_ID = "run-1"
CANDIDATE_ID = "tmdb:movie:101"
NOW = datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
snapshot_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate_snapshot")
playback_module = importlib.import_module(f"{PACKAGE_NAME}.model.playback")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
attribution_module = importlib.import_module(f"{PACKAGE_NAME}.service.attribution")
subscription_module = importlib.import_module(f"{PACKAGE_NAME}.service.subscription")
support_module = importlib.import_module(f"{PACKAGE_NAME}.model.support")
lifecycle_module = importlib.import_module(f"{PACKAGE_NAME}.service.data_lifecycle")

RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
Candidate = candidate_module.Candidate
CandidateSnapshot = snapshot_module.CandidateSnapshot
PlaybackSample = playback_module.PlaybackSample
PlaybackSnapshot = playback_module.PlaybackSnapshot
AgentRankRepository = repository_module.AgentRankRepository
OutcomeAttributionService = attribution_module.OutcomeAttributionService
SubscriptionService = subscription_module.SubscriptionService
SupportScore = support_module.SupportScore
DataLifecycleService = lifecycle_module.DataLifecycleService


class FakePlugin:
    """提供线程安全的深复制插件数据接口。"""

    def __init__(self):
        """创建空数据空间。"""
        self.data = {}
        self.lock = threading.RLock()

    def get_data(self, key=None):
        """读取指定键的独立副本。"""
        with self.lock:
            return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """保存指定键的独立副本。"""
        with self.lock:
            self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除指定键。"""
        with self.lock:
            self.data.pop(key, None)


class Clock:
    """提供可推进的 UTC 测试时钟。"""

    def __init__(self):
        """从固定时间开始。"""
        self.value = NOW

    def __call__(self):
        """返回当前时间。"""
        return self.value

    def advance(self, **kwargs):
        """推进测试时间。"""
        self.value += timedelta(**kwargs)


class SubscriptionState:
    """模拟 MoviePilot 全局订阅读取状态。"""

    def __init__(self):
        """创建空订阅集合和可控失败开关。"""
        self.ids = set()
        self.fail = False

    def candidate_ids(self):
        """返回订阅身份或模拟读取失败。"""
        if self.fail:
            raise RuntimeError("database unavailable")
        return set(self.ids)


class LibraryState:
    """模拟 MoviePilot 媒体库存在性读取。"""

    def __init__(self):
        """创建空媒体库集合和可控失败开关。"""
        self.ids = set()
        self.fail = False

    def exists(self, candidate):
        """返回候选是否入库或模拟读取失败。"""
        if self.fail:
            raise RuntimeError("library unavailable")
        return candidate.candidate_id in self.ids


def _ready_playback(*samples):
    """构造一次可读取的 Playback Reporting 快照。"""
    return PlaybackSnapshot(
        profile_id=PROFILE_ID,
        source="playback_reporting",
        confidence="high",
        status="ready",
        samples=list(samples),
        synced_at=(NOW + timedelta(hours=2)).isoformat(),
    )


def _setup():
    """创建当前榜单、冻结快照、仓储和归因服务。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    candidate = Candidate(
        candidate_id=CANDIDATE_ID,
        title="归因测试电影",
        media_type="movie",
        source_ids={"tmdb": "101"},
        metadata={"mp_media_type": "电影"},
    )
    repository.save_candidate_snapshot(
        CandidateSnapshot.create(
            profile_id=PROFILE_ID,
            run_id=RUN_ID,
            profile_version={"run_id": RUN_ID, "schema_version": 1},
            retrieval_plan={},
            candidates=[candidate],
            generated_at=NOW.isoformat(),
        )
    )
    repository.save_board(
        RecommendationBoard(
            profile_id=PROFILE_ID,
            run_id=RUN_ID,
            username="Alice",
            status="success",
            generated_at=NOW.isoformat(),
            recommendations=[
                RecommendationItem(
                    candidate_id=CANDIDATE_ID,
                    rank=1,
                    title=candidate.title,
                    media_type="movie",
                    source_ids={"tmdb": "101"},
                )
            ],
        )
    )
    clock = Clock()
    subscriptions = SubscriptionState()
    library = LibraryState()
    service = OutcomeAttributionService(
        repository,
        subscription_adapter=subscriptions,
        library_adapter=library,
        now_factory=clock,
    )
    return repository, clock, subscriptions, library, service


def test_native_drawer_cancel_stays_opened_after_successful_empty_recheck():
    """原生抽屉打开后取消，复查无订阅时不得误报成功。"""
    repository, clock, _, _, service = _setup()
    opened = service.record_native_drawer_opened(PROFILE_ID, CANDIDATE_ID)
    first_evidence = opened.native_drawer_opened_at
    clock.advance(minutes=10)

    checked = service.verify_profile(
        PROFILE_ID, playback_snapshot=_ready_playback()
    )
    stored = repository.load_outcome_attributions(PROFILE_ID, strict=True)[0]

    assert opened.state == "native_drawer_opened"
    assert checked.advanced == 0 and checked.pending == 0
    assert stored.state == "native_drawer_opened"
    assert stored.native_drawer_opened_at == first_evidence
    assert stored.subscription_observed_at == ""
    assert stored.verification_status == "verified"


def test_real_subscription_library_and_new_playback_advance_monotonically():
    """真实订阅、入库和交互后的新播放依次推进且永不降级。"""
    repository, clock, subscriptions, library, service = _setup()
    service.record_native_drawer_opened(PROFILE_ID, CANDIDATE_ID)
    subscriptions.ids.add(CANDIDATE_ID)
    clock.advance(minutes=5)
    subscribed = service.verify_profile(
        PROFILE_ID, playback_snapshot=_ready_playback()
    ).records[0]
    library.ids.add(CANDIDATE_ID)
    clock.advance(minutes=5)
    in_library = service.verify_profile(
        PROFILE_ID, playback_snapshot=_ready_playback()
    ).records[0]
    clock.advance(minutes=5)
    playback = PlaybackSample(
        stable_id=CANDIDATE_ID,
        title="归因测试电影",
        media_type="movie",
        tmdb_id="101",
        play_count=1,
        watch_minutes=12,
        last_played_at=clock.value.isoformat(),
    )
    played = service.verify_profile(
        PROFILE_ID, playback_snapshot=_ready_playback(playback)
    ).records[0]
    subscriptions.ids.clear()
    library.ids.clear()

    assert subscribed.state == "subscription_observed"
    assert in_library.state == "library_observed"
    assert played.state == "playback_observed" and played.terminal is True
    assert service.verify_profile(PROFILE_ID).records[0].state == "playback_observed"
    assert repository.load_outcome_attributions(PROFILE_ID)[0].state == "playback_observed"


def test_higher_observed_fact_can_skip_missing_lower_fact_and_keeps_first_time():
    """入库事实可越过缺失订阅，重复复查不得改写第一证据时间。"""
    _, clock, _, library, service = _setup()
    opened = service.record_native_drawer_opened(PROFILE_ID, CANDIDATE_ID)
    library.ids.add(CANDIDATE_ID)
    clock.advance(minutes=5)

    first = service.verify_profile(
        PROFILE_ID, playback_snapshot=_ready_playback()
    ).records[0]
    clock.advance(minutes=5)
    repeated = service.verify_profile(
        PROFILE_ID, playback_snapshot=_ready_playback()
    ).records[0]

    assert first.state == "library_observed"
    assert first.subscription_observed_at == ""
    assert first.library_observed_at == repeated.library_observed_at
    assert repeated.native_drawer_opened_at == opened.native_drawer_opened_at


def test_old_playback_cannot_be_attributed_to_new_native_interaction():
    """发生在打开抽屉之前的播放事实不得升级新归因。"""
    _, _, _, _, service = _setup()
    service.record_native_drawer_opened(PROFILE_ID, CANDIDATE_ID)
    old = PlaybackSample(
        stable_id=CANDIDATE_ID,
        title="归因测试电影",
        media_type="movie",
        tmdb_id="101",
        play_count=1,
        last_played_at=(NOW - timedelta(days=1)).isoformat(),
    )

    record = service.verify_profile(
        PROFILE_ID, playback_snapshot=_ready_playback(old)
    ).records[0]

    assert record.state == "native_drawer_opened"
    assert record.playback_observed_at == ""


def test_read_failures_mark_pending_and_recovery_preserves_trusted_state():
    """宿主读取失败只标记待复查，恢复后可继续从旧可信状态升级。"""
    repository, clock, subscriptions, library, service = _setup()
    service.record_native_drawer_opened(PROFILE_ID, CANDIDATE_ID)
    subscriptions.fail = True
    library.fail = True
    failed_snapshot = PlaybackSnapshot(
        profile_id=PROFILE_ID,
        source="playback_reporting",
        status="transient_error",
    )

    pending = service.verify_profile(
        PROFILE_ID, playback_snapshot=failed_snapshot
    ).records[0]
    subscriptions.fail = False
    library.fail = False
    subscriptions.ids.add(CANDIDATE_ID)
    clock.advance(minutes=10)
    recovered = service.verify_profile(
        PROFILE_ID, playback_snapshot=_ready_playback()
    ).records[0]

    assert pending.state == "native_drawer_opened"
    assert pending.verification_status == "verification_pending"
    assert pending.verification_code == "subscription_read_failed"
    assert recovered.state == "subscription_observed"
    assert recovered.verification_status == "verified"
    assert repository.load_outcome_attributions(PROFILE_ID)[0].state == "subscription_observed"


def test_controlled_subscription_can_start_at_observed_without_native_drawer():
    """插件静默安全链可用直接证据起始为已订阅，不伪造抽屉记录。"""
    _, _, _, _, service = _setup()

    record = service.record_subscription_observed(PROFILE_ID, CANDIDATE_ID)

    assert record.state == "subscription_observed"
    assert record.subscription_source == "plugin_controlled_subscription"
    assert record.native_drawer_opened_at == ""


def test_cross_profile_playback_snapshot_is_never_used_as_evidence():
    """其他 profile 的播放快照只能使复查待定，不能跨用户归因。"""
    _, _, _, _, service = _setup()
    service.record_native_drawer_opened(PROFILE_ID, CANDIDATE_ID)
    foreign = PlaybackSnapshot(
        profile_id="emby:home:user-2",
        source="playback_reporting",
        status="ready",
        samples=[
            PlaybackSample(
                stable_id=CANDIDATE_ID,
                title="归因测试电影",
                media_type="movie",
                last_played_at=(NOW + timedelta(hours=1)).isoformat(),
            )
        ],
    )

    record = service.verify_profile(
        PROFILE_ID, playback_snapshot=foreign
    ).records[0]

    assert record.state == "native_drawer_opened"
    assert record.verification_status == "verification_pending"
    assert record.verification_code == "playback_read_failed"


def test_subscription_service_records_controlled_evidence_after_host_success():
    """插件安全订阅创建成功后直接把受控证据交给归因服务。"""
    repository, _, _, _, attribution = _setup()
    board = repository.load_board(PROFILE_ID)
    board.recommendations[0].support = SupportScore.from_contributions(
        "policy-1", []
    )
    repository.save_board(board)

    class SubscribeChain:
        """模拟不存在旧订阅且创建成功的宿主订阅链。"""

        @staticmethod
        def exists(media):
            """返回未订阅。"""
            del media
            return False

        @staticmethod
        def add(**kwargs):
            """返回受控订阅 ID。"""
            del kwargs
            return 42, "新增订阅成功"

    service = SubscriptionService(
        repository,
        subscribe_chain=SubscribeChain(),
        media_factory=lambda **kwargs: SimpleNamespace(**kwargs),
        media_type_factory=lambda value: value,
        subscription_adapter=SubscriptionState(),
        attribution_service=attribution,
    )

    result = service.subscribe(PROFILE_ID, CANDIDATE_ID, 0)

    assert result.success is True and result.code == "subscription_created"
    assert result.attribution_error == ""
    assert result.attribution["state"] == "subscription_observed"
    assert repository.load_outcome_attributions(PROFILE_ID)[0].state == "subscription_observed"


def test_corrupt_attribution_store_is_not_silently_overwritten():
    """损坏的新 schema 必须闭锁写入并保留原始载荷。"""
    repository, _, _, _, service = _setup()
    key = repository._learning_key("attribution", PROFILE_ID)
    repository._plugin.data[key] = {"corrupt": True}

    try:
        service.record_native_drawer_opened(PROFILE_ID, CANDIDATE_ID)
    except ValueError:
        pass
    else:
        raise AssertionError("corrupt attribution must fail closed")

    assert repository._plugin.data[key] == {"corrupt": True}


def test_inconsistent_evidence_state_is_rejected_as_corrupt():
    """状态低于最高证据或缺少来源的载荷不得进入可信归因账本。"""
    repository, _, _, _, service = _setup()
    record = service.record_native_drawer_opened(PROFILE_ID, CANDIDATE_ID)
    key = repository._learning_key("attribution", PROFILE_ID)
    value = record.to_dict()
    value["library_observed_at"] = (NOW + timedelta(minutes=5)).isoformat()
    repository._plugin.data[key] = [value]

    try:
        repository.load_outcome_attributions(PROFILE_ID, strict=True)
    except ValueError:
        pass
    else:
        raise AssertionError("inconsistent attribution must fail closed")

    assert repository._plugin.data[key] == [value]


def test_attribution_write_failure_does_not_hide_completed_subscription():
    """宿主订阅已成功时，归因保存失败只能作为附加错误返回。"""
    repository, _, _, _, attribution = _setup()
    board = repository.load_board(PROFILE_ID)
    board.recommendations[0].support = SupportScore.from_contributions(
        "policy-1", []
    )
    repository.save_board(board)

    class SubscribeChain:
        """模拟成功创建订阅的宿主链。"""

        @staticmethod
        def exists(media):
            """返回未订阅。"""
            del media
            return False

        @staticmethod
        def add(**kwargs):
            """返回成功订阅 ID。"""
            del kwargs
            return 42, "新增订阅成功"

    def fail_attribution(*args, **kwargs):
        """模拟宿主副作用完成后的归因存储失败。"""
        del args, kwargs
        raise RuntimeError("storage unavailable")

    attribution.record_subscription_observed = fail_attribution
    service = SubscriptionService(
        repository,
        subscribe_chain=SubscribeChain(),
        media_factory=lambda **kwargs: SimpleNamespace(**kwargs),
        media_type_factory=lambda value: value,
        subscription_adapter=SubscriptionState(),
        attribution_service=attribution,
    )

    result = service.subscribe(PROFILE_ID, CANDIDATE_ID, 0)

    assert result.success is True and result.code == "subscription_created"
    assert result.subscription_id == 42
    assert result.attribution == {}
    assert result.attribution_error == "attribution_record_failed"


def test_sanitized_export_includes_state_but_not_host_lookup_fields():
    """脱敏导出保留归因审计状态且不暴露宿主查找细节。"""
    repository, _, _, _, service = _setup()
    service.record_native_drawer_opened(PROFILE_ID, CANDIDATE_ID)

    exported = DataLifecycleService(repository, {}).export_profile(PROFILE_ID)
    [record] = exported["outcome_attributions"]

    assert record["state"] == "native_drawer_opened"
    assert record["candidate_id"] == CANDIDATE_ID
    assert "tmdb_id" not in record
    assert "mp_media_type" not in record
    assert "native_drawer_source" not in record
