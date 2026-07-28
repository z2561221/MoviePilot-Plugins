"""确定性支持度、证据验证与反证自动计入测试。"""

import copy
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_support_scoring_test"
PROFILE_ID = "emby:home:user-1"
FIXED_NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

archive_module = importlib.import_module(f"{PACKAGE_NAME}.service.archive")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
config_module = importlib.import_module(f"{PACKAGE_NAME}.model.config")
memory_module = importlib.import_module(f"{PACKAGE_NAME}.model.memory")
playback_module = importlib.import_module(f"{PACKAGE_NAME}.model.playback")
preferences_module = importlib.import_module(
    f"{PACKAGE_NAME}.model.profile_preferences"
)
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
scoring_module = importlib.import_module(f"{PACKAGE_NAME}.service.scoring")
support_module = importlib.import_module(f"{PACKAGE_NAME}.model.support")
validation_module = importlib.import_module(f"{PACKAGE_NAME}.service.validation")

ArchiveService = archive_module.ArchiveService
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
Candidate = candidate_module.Candidate
WEIGHT_DEFAULTS = config_module.WEIGHT_DEFAULTS
PreferenceMemory = memory_module.PreferenceMemory
PlaybackSample = playback_module.PlaybackSample
PlaybackSnapshot = playback_module.PlaybackSnapshot
ProfilePreferences = preferences_module.ProfilePreferences
AgentRankRepository = repository_module.AgentRankRepository
DeterministicSupportScorer = scoring_module.DeterministicSupportScorer
PolicyLearningService = scoring_module.PolicyLearningService
SupportContribution = support_module.SupportContribution
SupportScore = support_module.SupportScore
AgentOutputError = validation_module.AgentOutputError
RankingOutputParser = validation_module.RankingOutputParser
RecommendationValidator = validation_module.RecommendationValidator


class FakePlugin:
    """提供隔离副本的内存插件数据区。"""

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


def _playback(count=3, *, abandoned=False):
    """构造具有独立电影与悬疑证据的播放快照。"""
    return PlaybackSnapshot(
        profile_id=PROFILE_ID,
        source="playback_reporting",
        confidence="high",
        status="ready",
        samples=[
            PlaybackSample(
                stable_id=f"tmdb:movie:{index}",
                title=f"已看作品 {index}",
                media_type="movie",
                genres=["悬疑"],
                completed=not abandoned,
                play_count=1,
                watch_minutes=10 if abandoned else 90,
                abandoned=abandoned,
            )
            for index in range(1, count + 1)
        ],
        synced_at=FIXED_NOW.isoformat(),
    )


def _candidate(candidate_id="tmdb:movie:99"):
    """构造带结构化类型、题材和地区事实的候选。"""
    return Candidate(
        candidate_id=candidate_id,
        title="候选作品",
        media_type="movie",
        genres=["悬疑"],
        regions=["中国"],
        source_ids={"tmdb": "99"},
    )


def _policy(memory, playback):
    """使用固定时钟生成可复现策略快照。"""
    return PolicyLearningService(
        repository=None,
        now_factory=lambda: FIXED_NOW,
    ).build_snapshot(PROFILE_ID, WEIGHT_DEFAULTS, memory, playback)


def _claims():
    """返回两项可由播放与候选字段共同验证的正向声明。"""
    return [
        {
            "dimension": "type",
            "user_value": "movie",
            "candidate_value": "movie",
        },
        {
            "dimension": "theme",
            "user_value": "悬疑",
            "candidate_value": "悬疑",
        },
    ]


def _score(*, playback=None, preferences=None, positive_claims=None):
    """按空确认记忆和可选人工偏好计算候选支持度。"""
    playback = playback or _playback()
    memory = PreferenceMemory.empty(PROFILE_ID)
    preferences = preferences or ProfilePreferences(profile_id=PROFILE_ID)
    policy = _policy(memory, playback)
    return DeterministicSupportScorer().score_candidate(
        _candidate(),
        policy,
        _claims() if positive_claims is None else positive_claims,
        [],
        memory,
        preferences,
        playback,
    )


def _contribution(direction, weight_units, *, suffix):
    """构造可精确重算且身份唯一的测试贡献。"""
    return SupportContribution(
        dimension="theme_weight",
        direction=direction,
        user_value=f"悬疑{suffix}",
        candidate_value="悬疑",
        user_refs=(f"memory:{suffix}",),
        candidate_ref=f"candidate:99:genres:{suffix}",
        weight_units=weight_units,
        certainty_units=10_000,
        contribution_units=weight_units,
    )


def test_support_score_round_trips_with_zero_recalculation_error():
    """保存的贡献项必须能零误差重算全部汇总字段。"""
    score = SupportScore.from_contributions(
        "policy-v1-test",
        [
            _contribution("positive", 7_000, suffix="positive"),
            _contribution("counter", 2_000, suffix="counter"),
        ],
    )

    restored = SupportScore.from_dict(score.to_dict())

    assert restored == score
    assert restored.positive_units == 7_000
    assert restored.counter_units == 2_000
    assert restored.net_units == 5_000
    assert restored.available_units == 9_000
    assert restored.percentage == 56


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("percentage",), 99),
        (("positive_units",), 1),
        (("contributions", 0, "contribution_units"), 6_999),
    ],
)
def test_support_score_rejects_tampered_totals_and_contributions(path, value):
    """持久化百分比、汇总或贡献被篡改时必须拒绝恢复。"""
    payload = SupportScore.from_contributions(
        "policy-v1-test",
        [_contribution("positive", 7_000, suffix="positive")],
    ).to_dict()
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValueError, match="reproducible"):
        SupportScore.from_dict(payload)


def test_two_verified_positive_claims_are_required():
    """单项正向声明即使真实也不能形成可发布支持度。"""
    result = _score(positive_claims=_claims()[:1])

    assert result.verified_positive_count == 1
    assert result.score.percentage == 100

    playback = _playback()
    memory = PreferenceMemory.empty(PROFILE_ID)
    policy = _policy(memory, playback)
    parsed = RankingOutputParser().parse(
        json.dumps(
            {
                "recommendations": [
                    {
                        "candidate_id": "tmdb:movie:99",
                        "reason": "偏爱悬疑电影，这部中国追凶故事更贴合。",
                        "summary": "密室谜案牵出多年前的隐秘真相。",
                        "match_tags": ["悬疑", "中国"],
                        "positive_evidence": _claims()[:1],
                        "counter_evidence": [],
                    }
                ]
            },
            ensure_ascii=False,
        )
    )
    validated = RecommendationValidator().validate(
        parsed,
        [_candidate()],
        set(),
        set(),
        preference_evidence=["悬疑"],
        playback_samples=playback.samples,
        policy_snapshot=policy,
        confirmed_memory=memory,
        profile_preferences=ProfilePreferences(profile_id=PROFILE_ID),
        playback_snapshot=playback,
    )

    assert validated.accepted == []
    assert validated.dropped[0].reason == "insufficient_verified_evidence"


def test_counter_evidence_is_automatically_included_when_agent_omits_it():
    """人工负向标签匹配候选时，Agent 不声明反证也不能抬高百分比。"""
    positive_only = _score()
    with_negative = _score(
        preferences=ProfilePreferences(
            profile_id=PROFILE_ID,
            custom_negative_tags=["悬疑"],
        )
    )

    assert positive_only.verified_counter_count == 0
    assert positive_only.score.percentage == 100
    assert with_negative.verified_counter_count >= 1
    assert with_negative.score.counter_units > 0
    assert with_negative.score.percentage < positive_only.score.percentage


def test_single_playback_sample_cannot_create_stable_support():
    """单部播放样本不得形成类型或题材稳定动机。"""
    result = _score(playback=_playback(count=1))

    assert result.verified_positive_count == 0
    assert result.score.contributions == ()
    assert result.score.percentage == 0
    assert result.unsupported_claims == (
        "positive:0:type_weight",
        "positive:1:theme_weight",
    )


def test_llm_confidence_cannot_enter_evidence_schema_or_final_percentage():
    """排序 Agent 在新协议中加入 confidence 必须被严格解析器拒绝。"""
    recommendation = {
        "candidate_id": "tmdb:movie:99",
        "reason": "偏爱悬疑电影，这部中国追凶故事更贴合。",
        "summary": "密室谜案牵出多年前的隐秘真相。",
        "match_tags": ["悬疑", "中国"],
        "positive_evidence": _claims(),
        "counter_evidence": [],
        "confidence": 99,
    }

    with pytest.raises(AgentOutputError, match="keys must be exactly"):
        RankingOutputParser().parse(
            json.dumps({"recommendations": [recommendation]}, ensure_ascii=False)
        )

    result = _score()
    assert result.score.percentage == 100


def test_ignore_changes_archive_only_and_has_zero_support_effect():
    """忽略作品不得改写确认记忆、人工标签、策略或支持度。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    candidate = _candidate()
    repository.save_board(
        RecommendationBoard(
            profile_id=PROFILE_ID,
            username="Alice",
            run_id="run-ignore",
            status="success",
            recommendations=[
                RecommendationItem(
                    candidate_id=candidate.candidate_id,
                    rank=1,
                    title=candidate.title,
                    media_type=candidate.media_type,
                )
            ],
        )
    )
    playback = _playback()
    memory_before = repository.load_preference_memory(PROFILE_ID)
    preferences_before = repository.load_profile_preferences(PROFILE_ID)
    policy_before = _policy(memory_before, playback)
    score_before = DeterministicSupportScorer().score_candidate(
        candidate,
        policy_before,
        _claims(),
        [],
        memory_before,
        preferences_before,
        playback,
    ).score

    ignored = ArchiveService(repository).ignore(PROFILE_ID, candidate.candidate_id)
    memory_after = repository.load_preference_memory(PROFILE_ID)
    preferences_after = repository.load_profile_preferences(PROFILE_ID)
    policy_after = _policy(memory_after, playback)
    score_after = DeterministicSupportScorer().score_candidate(
        candidate,
        policy_after,
        _claims(),
        [],
        memory_after,
        preferences_after,
        playback,
    ).score

    assert ignored.changed is True
    assert memory_after == memory_before
    assert preferences_after == preferences_before
    assert policy_after.policy_version == policy_before.policy_version
    assert score_after == score_before
