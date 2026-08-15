"""确定性支持度、证据验证与反证自动计入测试。"""

import copy
import importlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"
PACKAGE_NAME = "agentrank_support_scoring_test"
PROFILE_ID = "emby:home:user-1"
FIXED_NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

archive_module = importlib.import_module(f"{PACKAGE_NAME}.service.archive")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
config_module = importlib.import_module(f"{PACKAGE_NAME}.model.config")
feedback_module = importlib.import_module(f"{PACKAGE_NAME}.model.feedback")
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
ShortTermSignal = feedback_module.ShortTermSignal
ProfilePreferences = preferences_module.ProfilePreferences
AgentRankRepository = repository_module.AgentRankRepository
DeterministicSupportScorer = scoring_module.DeterministicSupportScorer
PolicyLearningService = scoring_module.PolicyLearningService
ShortTermPreferenceRanker = scoring_module.ShortTermPreferenceRanker
StableRecommendationRanker = scoring_module.StableRecommendationRanker
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


def _rank_item(candidate_id, units, *, policy_version="policy-v1-rank"):
    """构造具有指定确定性净分的榜单条目。"""
    support = SupportScore.from_contributions(
        policy_version,
        [_contribution("positive", units, suffix=candidate_id)],
    )
    return RecommendationItem(
        candidate_id=candidate_id,
        rank=99,
        support=support,
        selection_source="agent",
    )


def test_stable_ranker_replays_score_and_all_tie_breakers_one_hundred_times():
    """净分优先，随后按 Agent、冻结候选和身份顺序稳定破同分。"""
    ranker = StableRecommendationRanker()
    candidates = [
        _candidate("tmdb:movie:a"),
        _candidate("tmdb:movie:b"),
        _candidate("tmdb:movie:c"),
        _candidate("tmdb:movie:d"),
    ]

    def replay():
        """每次创建新对象，排除原地 rank 赋值对重放的影响。"""
        items = [
            _rank_item("tmdb:movie:a", 4_000),
            _rank_item("tmdb:movie:b", 8_000),
            _rank_item("tmdb:movie:c", 4_000),
            _rank_item("tmdb:movie:e", 4_000),
            _rank_item("tmdb:movie:d", 4_000),
        ]
        ranked = ranker.rank(
            items,
            candidates,
            agent_order={"tmdb:movie:c": 0, "tmdb:movie:a": 1},
        )
        return [
            (item.candidate_id, item.rank, item.support.to_dict())
            for item in ranked
        ]

    expected = replay()
    assert [item[0] for item in expected] == [
        "tmdb:movie:b",
        "tmdb:movie:c",
        "tmdb:movie:a",
        "tmdb:movie:d",
        "tmdb:movie:e",
    ]
    assert all(replay() == expected for _ in range(100))


def test_stable_ranker_rejects_mixed_policy_versions():
    """不同策略版本的条目不能被静默混排。"""
    with pytest.raises(RuntimeError, match="one policy version"):
        StableRecommendationRanker.rank(
            [
                _rank_item("tmdb:movie:a", 4_000, policy_version="policy-a"),
                _rank_item("tmdb:movie:b", 4_000, policy_version="policy-b"),
            ],
            [_candidate("tmdb:movie:a"), _candidate("tmdb:movie:b")],
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
                            "fit_score": 80,
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


def test_verified_claims_drive_match_tags_instead_of_unrelated_profile_tags():
    """决赛展示标签必须与已验证证据同源，不能被旧画像标签误杀。"""
    playback = _playback()
    memory = PreferenceMemory.empty(PROFILE_ID)
    policy = _policy(memory, playback)
    parsed = RankingOutputParser().parse(
        json.dumps(
            {
                "recommendations": [
                        {
                            "candidate_id": "tmdb:movie:99",
                            "fit_score": 80,
                            "reason": "偏爱悬疑电影，这部悬疑电影围绕追凶展开。",
                        "summary": "密室谜案牵出多年前的隐秘真相。",
                        "match_tags": ["无关旧标签"],
                        "positive_evidence": _claims(),
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
        preference_evidence=["修仙玄幻"],
        playback_samples=playback.samples,
        policy_snapshot=policy,
        confirmed_memory=memory,
        profile_preferences=ProfilePreferences(profile_id=PROFILE_ID),
        playback_snapshot=playback,
    )

    assert validated.dropped == []
    assert validated.accepted[0].match_tags == ["电影", "悬疑"]


def test_verified_claims_survive_semantic_copy_without_literal_labels():
    """合法证据不因 Agent 对理由作自然同义改写而被误判为不足。"""
    playback = _playback()
    memory = PreferenceMemory.empty(PROFILE_ID)
    policy = _policy(memory, playback)
    parsed = RankingOutputParser().parse(
        json.dumps(
            {
                "recommendations": [
                        {
                            "candidate_id": "tmdb:movie:99",
                            "fit_score": 80,
                            "reason": "偏爱推理故事，这部作品围绕追凶展开。",
                        "summary": "密室谜案牵出多年前的隐秘真相。",
                        "match_tags": ["推理", "追凶"],
                        "positive_evidence": _claims(),
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

    assert validated.dropped == []
    assert validated.accepted[0].match_tags == ["电影", "悬疑"]


def test_verified_claims_project_role_labels_for_long_values():
    """长演员名无法直接作短标签时仍从证据维度生成稳定展示标签。"""
    tags = RecommendationValidator._verified_evidence_tags(
        [
            {
                "dimension": "actor",
                "user_value": "克里斯托弗诺兰",
                "candidate_value": "克里斯托弗诺兰",
            },
            {
                "dimension": "director",
                "user_value": "亚历杭德罗冈萨雷斯伊纳里图",
                "candidate_value": "亚历杭德罗冈萨雷斯伊纳里图",
            },
        ]
    )

    assert tags == ["演员偏好", "演员契合"]


def test_anime_candidate_uses_two_verified_themes_instead_of_tv_type():
    """动画候选可用两项稳定题材证据，不得把播放 tv 类型冒充 anime。"""
    playback = PlaybackSnapshot(
        profile_id=PROFILE_ID,
        source="playback_reporting",
        confidence="high",
        status="ready",
        samples=[
            PlaybackSample(
                stable_id=f"tmdb:tv:{index}",
                title=f"已看动画 {index}",
                media_type="tv",
                genres=["动画", "科幻奇幻"],
                completed=True,
            )
            for index in range(1, 3)
        ],
        synced_at=FIXED_NOW.isoformat(),
    )
    memory = PreferenceMemory.empty(PROFILE_ID)
    preferences = ProfilePreferences(profile_id=PROFILE_ID)
    policy = _policy(memory, playback)
    candidate = Candidate(
        candidate_id="tmdb:tv:99",
        title="新科幻动画",
        media_type="anime",
        genres=["动画", "科幻"],
    )

    result = DeterministicSupportScorer().score_candidate(
        candidate,
        policy,
        [
            {"dimension": "theme", "user_value": "动画", "candidate_value": "动画"},
            {
                "dimension": "theme",
                "user_value": "科幻奇幻",
                "candidate_value": "科幻",
            },
        ],
        [],
        memory,
        preferences,
        playback,
    )
    catalog = DeterministicSupportScorer.trusted_signal_catalog(
        memory, preferences, playback
    )

    assert result.verified_positive_count == 2
    assert result.unsupported_claims == ()
    assert {(
        item["dimension"], item["value"], item["evidence_count"]
    ) for item in catalog} >= {
        ("type", "tv", 2),
        ("theme", "动画", 2),
        ("theme", "科幻奇幻", 2),
    }


def test_verified_evidence_options_are_directly_accepted_by_support_scorer():
    """候选证据选项必须逐项来自同一校验规则且无需 Agent 改写。"""
    playback = _playback()
    memory = PreferenceMemory.empty(PROFILE_ID)
    preferences = ProfilePreferences(
        profile_id=PROFILE_ID,
        custom_negative_tags=["中国"],
    )
    policy = _policy(memory, playback)
    candidate = _candidate()
    scorer = DeterministicSupportScorer()

    options = scorer.verified_evidence_options(
        candidate,
        policy,
        memory,
        preferences,
        playback,
    )
    result = scorer.score_candidate(
        candidate,
        policy,
        options["positive_evidence_options"],
        options["counter_evidence_options"],
        memory,
        preferences,
        playback,
    )

    assert len(options["positive_evidence_options"]) >= 2
    assert options["counter_evidence_options"] == [
        {
            "dimension": "region",
            "user_value": "中国",
            "candidate_value": "中国",
        }
    ]
    assert result.verified_positive_count == len(
        options["positive_evidence_options"]
    )
    assert result.verified_counter_claim_count == len(
        options["counter_evidence_options"]
    )
    assert result.unsupported_claims == ()


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


def test_short_term_ranker_applies_decay_neutral_cancellation_and_ignores_rotation():
    """近期信号按半衰期衰减，中立状态取消旧赞踩，轮换不参与口味排序。"""
    signals = [
        ShortTermSignal(
            profile_id=PROFILE_ID,
            kind="like",
            idempotency_key="like:a",
            candidate_id="tmdb:movie:a",
            strength=1.0,
            decay_days=10,
            observed_at=FIXED_NOW.isoformat(),
        ),
        ShortTermSignal(
            profile_id=PROFILE_ID,
            kind="like",
            idempotency_key="like:b",
            candidate_id="tmdb:movie:b",
            strength=1.0,
            decay_days=10,
            observed_at=(FIXED_NOW - timedelta(days=10)).isoformat(),
        ),
        ShortTermSignal(
            profile_id=PROFILE_ID,
            kind="dislike",
            idempotency_key="dislike:c",
            candidate_id="tmdb:movie:c",
            strength=-1.0,
            decay_days=10,
            observed_at=FIXED_NOW.isoformat(),
        ),
        ShortTermSignal(
            profile_id=PROFILE_ID,
            kind="rotation",
            idempotency_key="rotation:run:1",
            candidate_id="tmdb:movie:d",
            strength=1.0,
            observed_at=FIXED_NOW.isoformat(),
        ),
    ]

    summary = ShortTermPreferenceRanker.summarize(
        signals,
        active_feedback_polarities={
            "tmdb:movie:a": "neutral",
            "tmdb:movie:c": "dislike",
        },
        candidate_ids=[
            "tmdb:movie:a",
            "tmdb:movie:b",
            "tmdb:movie:c",
            "tmdb:movie:d",
        ],
        at=FIXED_NOW,
    )

    assert {item["candidate_id"] for item in summary} == {
        "tmdb:movie:b",
        "tmdb:movie:c",
    }
    values = {item["candidate_id"]: item for item in summary}
    assert values["tmdb:movie:b"]["strength"] == pytest.approx(0.5)
    assert values["tmdb:movie:c"]["strength"] == pytest.approx(-1.0)
    assert values["tmdb:movie:c"]["polarity"] == "negative"


def test_short_term_positive_signal_reorders_near_candidates_without_mutating_support_score():
    """近期正向信号可微调近邻顺序，但不得改写确定性支持度。"""
    ranker = StableRecommendationRanker()
    candidates = [
        _candidate("tmdb:movie:a"),
        _candidate("tmdb:movie:b"),
    ]
    items = [
        _rank_item("tmdb:movie:a", 9_000),
        _rank_item("tmdb:movie:b", 9_500),
    ]
    support_before = {
        item.candidate_id: item.support.to_dict() for item in items
    }

    baseline = ranker.rank(items, candidates)
    adjusted = ranker.rank(
        items,
        candidates,
        short_term_scores={"tmdb:movie:a": 1.0},
    )

    assert [item.candidate_id for item in baseline] == [
        "tmdb:movie:b",
        "tmdb:movie:a",
    ]
    assert [item.candidate_id for item in adjusted] == [
        "tmdb:movie:a",
        "tmdb:movie:b",
    ]
    assert {
        item.candidate_id: item.support.to_dict() for item in adjusted
    } == support_before


def test_short_term_ranker_clamps_only_after_aggregation_and_honors_empty_scope():
    """短期信号先求和后限幅，显式空候选范围不会泄露其它作品。"""
    signals = [
        ShortTermSignal(
            profile_id=PROFILE_ID,
            kind="playback_completed",
            idempotency_key=f"aggregate:{index}",
            candidate_id="tmdb:movie:aggregate",
            strength=strength,
            observed_at=FIXED_NOW.isoformat(),
        )
        for index, strength in enumerate((1.0, 1.0, -1.0), start=1)
    ]

    forward = ShortTermPreferenceRanker.score_map(
        signals,
        candidate_ids=["tmdb:movie:aggregate"],
        at=FIXED_NOW,
    )
    reverse = ShortTermPreferenceRanker.score_map(
        list(reversed(signals)),
        candidate_ids=["tmdb:movie:aggregate"],
        at=FIXED_NOW,
    )

    assert forward == reverse == {"tmdb:movie:aggregate": 1.0}
    assert ShortTermPreferenceRanker.score_map(
        signals,
        candidate_ids=[],
        at=FIXED_NOW,
    ) == {}
