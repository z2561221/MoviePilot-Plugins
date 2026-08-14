"""十项策略快照、独立证据、弃看边界与确定性重放测试。"""

import copy
import importlib
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_policy_learning_test"
PROFILE_ID = "emby:home:user-1"
FIXED_NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

config_module = importlib.import_module(f"{PACKAGE_NAME}.model.config")
feedback_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback")
memory_module = importlib.import_module(f"{PACKAGE_NAME}.model.memory")
playback_module = importlib.import_module(f"{PACKAGE_NAME}.model.playback")
policy_module = importlib.import_module(f"{PACKAGE_NAME}.model.policy")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
scoring_module = importlib.import_module(f"{PACKAGE_NAME}.service.scoring")

WEIGHT_DEFAULTS = config_module.WEIGHT_DEFAULTS
FeedbackEvent = feedback_module.FeedbackEvent
PreferenceMemory = memory_module.PreferenceMemory
PreferenceMemoryItem = memory_module.PreferenceMemoryItem
PlaybackSample = playback_module.PlaybackSample
PlaybackSnapshot = playback_module.PlaybackSnapshot
POLICY_WEIGHT_NAMES = policy_module.POLICY_WEIGHT_NAMES
PolicySnapshot = policy_module.PolicySnapshot
AgentRankRepository = repository_module.AgentRankRepository
PolicyLearningService = scoring_module.PolicyLearningService


class FakePlugin:
    """提供可验证回滚和跨调用隔离的内存插件存储。"""

    def __init__(self) -> None:
        """创建空数据区。"""
        self.data = {}

    def get_data(self, key=None):
        """返回指定键的独立副本。"""
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """保存指定键的独立副本。"""
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除指定键。"""
        self.data.pop(key, None)


def _service(repository=None):
    """创建固定时钟的策略学习服务。"""
    return PolicyLearningService(
        repository or AgentRankRepository(FakePlugin()),
        now_factory=lambda: FIXED_NOW,
    )


def _sample(
    stable_id,
    *,
    media_type="movie",
    genres=("科幻",),
    abandoned=False,
):
    """构造一条已经发生观看行为的播放证据。"""
    return PlaybackSample(
        stable_id=stable_id,
        title=f"作品 {stable_id}",
        media_type=media_type,
        genres=list(genres),
        completed=not abandoned,
        play_count=1,
        watch_minutes=90 if not abandoned else 10,
        abandoned=abandoned,
    )


def _playback(samples):
    """构造稳定 profile 的可用播放快照。"""
    return PlaybackSnapshot(
        profile_id=PROFILE_ID,
        source="playback_reporting",
        confidence="high",
        status="ready",
        samples=list(samples),
        synced_at=FIXED_NOW.isoformat(),
    )


def _memory_item(
    item_id,
    sequence,
    *,
    category="genre",
    value="科幻",
    polarity="positive",
    strength=1.0,
    certainty=1.0,
    supersedes=(),
):
    """构造一条已确认偏好记忆。"""
    return PreferenceMemoryItem(
        item_id=item_id,
        category=category,
        value=value,
        polarity=polarity,
        strength=strength,
        certainty=certainty,
        evidence_refs=(f"feedback:{sequence}",),
        source_event_sequence=sequence,
        created_at=(FIXED_NOW + timedelta(minutes=sequence)).isoformat(),
        supersedes=tuple(supersedes),
    )


def _project(memory, items, sequence):
    """把同一确认事件的一批记忆项投影到下一 revision。"""
    result = memory.project(
        items,
        expected_revision=memory.memory_revision,
        source_event_sequence=sequence,
    )
    assert result.applied is True
    return result.memory


def test_policy_snapshot_requires_exact_ten_weights_and_reproducible_formula():
    """快照拒绝缺项、越界增量和无法重算的有效权重。"""
    snapshot = _service().build_snapshot(
        PROFILE_ID,
        WEIGHT_DEFAULTS,
        PreferenceMemory.empty(PROFILE_ID),
        _playback([]),
    )

    assert tuple(WEIGHT_DEFAULTS) == POLICY_WEIGHT_NAMES
    assert tuple(snapshot.base_weights) == POLICY_WEIGHT_NAMES
    assert PolicySnapshot.from_dict(snapshot.to_dict()) == snapshot

    missing = snapshot.to_dict()
    missing["base_weights"].pop("type_weight")
    with pytest.raises(ValueError, match="exact ten"):
        PolicySnapshot.from_dict(missing)

    out_of_range = snapshot.to_dict()
    out_of_range["learned_deltas"]["type_weight"] = 0.251
    with pytest.raises(ValueError, match="out of range"):
        PolicySnapshot.from_dict(out_of_range)

    inconsistent = snapshot.to_dict()
    inconsistent["effective_weights"]["type_weight"] = 0.1
    with pytest.raises(ValueError, match="not reproducible"):
        PolicySnapshot.from_dict(inconsistent)

    tampered = snapshot.to_dict()
    tampered["calibration"]["memory_delta_scale"] = 0.2
    with pytest.raises(ValueError, match="version does not match"):
        PolicySnapshot.from_dict(tampered)

    malformed_refs = snapshot.to_dict()
    malformed_refs["evidence_refs"]["theme_weight"] = "memory:item-1"
    with pytest.raises(ValueError, match="must be a sequence"):
        PolicySnapshot.from_dict(malformed_refs)

    non_finite = snapshot.to_dict()
    non_finite["calibration"]["memory_delta_scale"] = float("nan")
    with pytest.raises(ValueError, match="calibration is invalid"):
        PolicySnapshot.from_dict(non_finite)


def test_confirmed_preference_changes_delta_without_overwriting_base_config():
    """单项明确偏好可学习，但用户配置仍逐项保持为原始基准。"""
    base = dict(WEIGHT_DEFAULTS)
    base["theme_weight"] = 0.55
    original = copy.deepcopy(base)
    memory = _project(
        PreferenceMemory.empty(PROFILE_ID),
        [_memory_item("memory-1", 1, strength=0.8, certainty=0.75)],
        1,
    )

    snapshot = _service().build_snapshot(
        PROFILE_ID, base, memory, _playback([])
    )

    assert base == original
    assert snapshot.base_weights["theme_weight"] == 0.55
    assert snapshot.learned_deltas["theme_weight"] == 0.08
    assert snapshot.evidence_certainty["theme_weight"] == 0.75
    assert snapshot.effective_weights["theme_weight"] == 0.61
    assert snapshot.evidence_refs["theme_weight"] == ("memory:memory-1",)


def test_negative_confirmed_preference_increases_dimension_salience():
    """明确避雷提高对应维度重要性，偏好正负留给评分证据决定。"""
    memory = _project(
        PreferenceMemory.empty(PROFILE_ID),
        [
            _memory_item(
                "memory-negative",
                1,
                category="actor",
                value="某演员",
                polarity="negative",
                strength=0.9,
                certainty=0.8,
            )
        ],
        1,
    )

    snapshot = _service().build_snapshot(
        PROFILE_ID, WEIGHT_DEFAULTS, memory, _playback([])
    )

    assert snapshot.calibration["delta_semantics"] == "dimension_salience"
    assert snapshot.learned_deltas["actor_weight"] == 0.09
    assert snapshot.effective_weights["actor_weight"] > snapshot.base_weights[
        "actor_weight"
    ]


def test_one_playback_or_repeated_same_title_cannot_form_stable_signal():
    """单部作品及其重复事件都不能冒充两条独立播放证据。"""
    service = _service()
    single = service.build_snapshot(
        PROFILE_ID,
        WEIGHT_DEFAULTS,
        PreferenceMemory.empty(PROFILE_ID),
        _playback([_sample("tmdb:movie:1")]),
    )
    repeated = service.build_snapshot(
        PROFILE_ID,
        WEIGHT_DEFAULTS,
        PreferenceMemory.empty(PROFILE_ID),
        _playback(
            [
                _sample("tmdb:movie:1"),
                _sample("tmdb:movie:1"),
                _sample("tmdb:movie:1"),
            ]
        ),
    )

    assert all(value == 0 for value in single.learned_deltas.values())
    assert all(value == 0 for value in repeated.learned_deltas.values())
    assert all(not refs for refs in repeated.evidence_refs.values())


def test_two_independent_playbacks_form_bounded_type_and_theme_signals():
    """两部不同作品可支持共同媒体类型和题材的稳定软信号。"""
    snapshot = _service().build_snapshot(
        PROFILE_ID,
        WEIGHT_DEFAULTS,
        PreferenceMemory.empty(PROFILE_ID),
        _playback([_sample("tmdb:movie:1"), _sample("tmdb:movie:2")]),
    )

    assert snapshot.learned_deltas["type_weight"] == 0.04
    assert snapshot.learned_deltas["theme_weight"] == 0.04
    assert snapshot.evidence_certainty["theme_weight"] == 0.6
    assert snapshot.evidence_refs["theme_weight"] == (
        "playback:observed:tmdb:movie:1",
        "playback:observed:tmdb:movie:2",
    )


def test_abandonment_is_weak_negative_and_never_creates_a_stable_single_signal():
    """单次弃看不学习，两部独立弃看也只产生低强度软负向。"""
    service = _service()
    single = service.build_snapshot(
        PROFILE_ID,
        WEIGHT_DEFAULTS,
        PreferenceMemory.empty(PROFILE_ID),
        _playback([_sample("tmdb:movie:1", abandoned=True)]),
    )
    two_abandoned = service.build_snapshot(
        PROFILE_ID,
        WEIGHT_DEFAULTS,
        PreferenceMemory.empty(PROFILE_ID),
        _playback(
            [
                _sample("tmdb:movie:1", abandoned=True),
                _sample("tmdb:movie:2", abandoned=True),
            ]
        ),
    )
    two_observed = service.build_snapshot(
        PROFILE_ID,
        WEIGHT_DEFAULTS,
        PreferenceMemory.empty(PROFILE_ID),
        _playback([_sample("tmdb:movie:1"), _sample("tmdb:movie:2")]),
    )

    assert single.learned_deltas["theme_weight"] == 0
    assert two_abandoned.learned_deltas["theme_weight"] == -0.01
    assert two_abandoned.evidence_certainty["theme_weight"] == 0.2
    assert abs(two_abandoned.learned_deltas["theme_weight"]) < abs(
        two_observed.learned_deltas["theme_weight"]
    )
    assert set(two_abandoned.to_dict()).isdisjoint({"filters", "tags"})


def test_completed_replay_supersedes_same_title_abandonment():
    """同一作品后来完整看完时不再保留早期弃看负向。"""
    completed = _sample("tmdb:movie:1")
    previously_abandoned = _sample("tmdb:movie:1", abandoned=True)
    companion = _sample("tmdb:movie:2")

    snapshot = _service().build_snapshot(
        PROFILE_ID,
        WEIGHT_DEFAULTS,
        PreferenceMemory.empty(PROFILE_ID),
        _playback([previously_abandoned, completed, companion]),
    )

    assert snapshot.learned_deltas["theme_weight"] == 0.04
    assert snapshot.evidence_refs["theme_weight"] == (
        "playback:observed:tmdb:movie:1",
        "playback:observed:tmdb:movie:2",
    )


def test_learning_delta_is_clamped_at_quarter_without_mutating_base():
    """大量确认偏好只能把单项增量推到正负四分之一边界。"""
    items = [
        _memory_item(f"memory-{index}", 1, value=f"题材-{index}")
        for index in range(10)
    ]
    memory = _project(PreferenceMemory.empty(PROFILE_ID), items, 1)

    snapshot = _service().build_snapshot(
        PROFILE_ID, WEIGHT_DEFAULTS, memory, _playback([])
    )

    assert snapshot.learned_deltas["theme_weight"] == 0.25
    assert snapshot.base_weights == WEIGHT_DEFAULTS
    assert all(-0.25 <= value <= 0.25 for value in snapshot.learned_deltas.values())


def test_correction_lineage_uses_only_current_memory_item():
    """被纠正的旧记忆退出策略证据，只有谱系当前项继续生效。"""
    first = _memory_item("memory-old", 1, strength=1.0)
    memory = _project(PreferenceMemory.empty(PROFILE_ID), [first], 1)
    corrected = _memory_item(
        "memory-new",
        2,
        polarity="negative",
        strength=0.2,
        certainty=0.5,
        supersedes=(first.item_id,),
    )
    memory = _project(memory, [corrected], 2)

    snapshot = _service().build_snapshot(
        PROFILE_ID, WEIGHT_DEFAULTS, memory, _playback([])
    )

    assert snapshot.learned_deltas["theme_weight"] == 0.02
    assert snapshot.evidence_refs["theme_weight"] == ("memory:memory-new",)
    assert "memory:memory-old" not in {
        ref for refs in snapshot.evidence_refs.values() for ref in refs
    }


def test_ignore_event_has_zero_effect_on_policy_version_and_weights():
    """纯忽略只存在于反馈与归档域，不进入策略学习输入。"""
    repository = AgentRankRepository(FakePlugin())
    service = _service(repository)
    playback = _playback([_sample("tmdb:movie:1"), _sample("tmdb:movie:2")])
    before = service.build_snapshot(
        PROFILE_ID,
        WEIGHT_DEFAULTS,
        repository.load_preference_memory(PROFILE_ID),
        playback,
    )
    repository.append_feedback_event(
        FeedbackEvent(
            profile_id=PROFILE_ID,
            kind="ignore",
            candidate_id="tmdb:movie:9",
            idempotency_key="ignore-1",
        )
    )
    after = service.build_snapshot(
        PROFILE_ID,
        WEIGHT_DEFAULTS,
        repository.load_preference_memory(PROFILE_ID),
        playback,
    )

    assert after.policy_version == before.policy_version
    assert after.learned_deltas == before.learned_deltas
    assert after.effective_weights == before.effective_weights


def test_policy_replay_is_order_independent_and_byte_stable():
    """同一事实任意输入顺序重放一百次得到完全相同的策略载荷。"""
    memory = _project(
        PreferenceMemory.empty(PROFILE_ID),
        [_memory_item("memory-1", 1, category="pacing", value="紧凑")],
        1,
    )
    samples = [
        _sample("tmdb:movie:1", genres=("科幻", "冒险")),
        _sample("tmdb:movie:2", genres=("科幻",)),
        _sample("tmdb:tv:3", media_type="tv", genres=("悬疑",)),
        _sample("tmdb:tv:4", media_type="tv", genres=("悬疑",)),
    ]
    service = _service()
    expected = service.build_snapshot(
        PROFILE_ID, WEIGHT_DEFAULTS, memory, _playback(samples)
    ).to_dict()

    for seed in range(100):
        shuffled = list(samples)
        random.Random(seed).shuffle(shuffled)
        replayed = service.build_snapshot(
            PROFILE_ID, WEIGHT_DEFAULTS, memory, _playback(shuffled)
        ).to_dict()
        assert replayed == expected


def test_repository_rejects_stale_memory_revision_and_round_trips_snapshot():
    """策略保存使用记忆 revision 门禁，旧快照不能覆盖新记忆对应策略。"""
    repository = AgentRankRepository(FakePlugin())
    service = _service(repository)
    playback = _playback([])
    stale = service.build_snapshot(
        PROFILE_ID,
        WEIGHT_DEFAULTS,
        repository.load_preference_memory(PROFILE_ID),
        playback,
    )
    repository.project_preference_memory(
        PROFILE_ID,
        [_memory_item("memory-1", 1)],
        expected_revision=0,
        source_event_sequence=1,
    )

    assert repository.save_policy_snapshot(
        stale, expected_memory_revision=0
    ) is None
    assert repository.load_policy_snapshot(PROFILE_ID) is None

    current = service.refresh(PROFILE_ID, WEIGHT_DEFAULTS, playback)
    assert current.memory_revision == 1
    assert repository.load_policy_snapshot(PROFILE_ID) == current


def test_corrupt_policy_is_replaced_by_reproducible_snapshot():
    """损坏的派生策略会留恢复记录并被重算，不阻断后续榜单运行。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    key = repository._learning_key("policy_snapshot", PROFILE_ID)
    plugin.data[key] = {"profile_id": PROFILE_ID, "policy_version": "broken"}

    current = _service(repository).refresh(
        PROFILE_ID, WEIGHT_DEFAULTS, _playback([])
    )

    assert repository.load_policy_snapshot(PROFILE_ID) == current
    assert plugin.data[repository.recovery_log_key][-1]["action"] == (
        "replaced_corrupt_policy_snapshot"
    )


def test_refresh_reuses_unchanged_version_without_rewriting_generation_time():
    """输入未变时复用已有快照，避免同版本因时钟产生无意义写入。"""
    repository = AgentRankRepository(FakePlugin())
    clock = iter((FIXED_NOW, FIXED_NOW + timedelta(days=1)))
    service = PolicyLearningService(repository, now_factory=lambda: next(clock))
    playback = _playback([])

    first = service.refresh(PROFILE_ID, WEIGHT_DEFAULTS, playback)
    second = service.refresh(PROFILE_ID, WEIGHT_DEFAULTS, playback)

    assert second == first
    assert second.generated_at == FIXED_NOW.isoformat()
