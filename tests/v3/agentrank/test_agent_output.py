"""AgentRank prompt, strict JSON parser, and deterministic validator tests."""

import ast
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"
PACKAGE_NAME = "agentrank_output_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
config_module = importlib.import_module(f"{PACKAGE_NAME}.model.config")
memory_module = importlib.import_module(f"{PACKAGE_NAME}.model.memory")
playback_module = importlib.import_module(f"{PACKAGE_NAME}.model.playback")
preferences_module = importlib.import_module(
    f"{PACKAGE_NAME}.model.profile_preferences"
)
prompt_module = importlib.import_module(f"{PACKAGE_NAME}.service.prompt")
scoring_module = importlib.import_module(f"{PACKAGE_NAME}.service.scoring")
validation_module = importlib.import_module(f"{PACKAGE_NAME}.service.validation")

Candidate = candidate_module.Candidate
WEIGHT_DEFAULTS = config_module.WEIGHT_DEFAULTS
PreferenceMemory = memory_module.PreferenceMemory
PlaybackSample = playback_module.PlaybackSample
PlaybackSnapshot = playback_module.PlaybackSnapshot
ProfilePreferences = preferences_module.ProfilePreferences
PolicyLearningService = scoring_module.PolicyLearningService
ProfileOutputParser = validation_module.ProfileOutputParser
RankingOutputParser = validation_module.RankingOutputParser
AgentOutputParser = RankingOutputParser
RecommendationValidator = validation_module.RecommendationValidator
AgentOutputError = validation_module.AgentOutputError
fallback_summary = validation_module.fallback_summary
fallback_reason = validation_module.fallback_reason
is_complete_recommendation_copy = validation_module.is_complete_recommendation_copy
build_ranking_prompt = prompt_module.build_ranking_prompt
build_profile_prompt = prompt_module.build_profile_prompt
build_preliminary_prompt = prompt_module.build_preliminary_prompt
build_retrieval_prompt = prompt_module.build_retrieval_prompt
build_final_prompt = prompt_module.build_final_prompt
build_refill_prompt = prompt_module.build_refill_prompt
build_feedback_understanding_prompt = prompt_module.build_feedback_understanding_prompt
build_analysis_comment_prompt = prompt_module.build_analysis_comment_prompt
build_conversation_prompt = prompt_module.build_conversation_prompt


def _support_context():
    """构造可重放的同策略补位上下文。"""
    profile_id = "emby:home:user-1"
    now = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
    playback = PlaybackSnapshot(
        profile_id=profile_id,
        source="playback_reporting",
        confidence="high",
        status="ready",
        samples=[
            PlaybackSample(
                stable_id=f"tmdb:movie:{index}",
                title=f"已看悬疑片{index}",
                media_type="movie",
                genres=["悬疑"],
                completed=True,
                play_count=1,
                watch_minutes=90,
            )
            for index in range(1, 3)
        ],
        synced_at=now.isoformat(),
    )
    memory = PreferenceMemory.empty(profile_id)
    preferences = ProfilePreferences(profile_id=profile_id)
    policy = PolicyLearningService(
        repository=None,
        now_factory=lambda: now,
    ).build_snapshot(profile_id, WEIGHT_DEFAULTS, memory, playback)
    return policy, memory, preferences, playback


def _profile_output(profile=None, filters=None, ranking_tags=None):
    return json.dumps(
        {
            "profile": profile
            or {
                "summary": "偏好悬疑犯罪与高口碑短剧",
                "tags": ["悬疑", "犯罪"],
                "negative_tags": ["低分长剧"],
                "playback_count": 12,
            },
        },
        ensure_ascii=False,
    )


def _output(recommendations=None):
    return json.dumps(
        {
            "recommendations": recommendations
            or [
                {
                    "candidate_id": "tmdb:1",
                    "reason": "你常订阅悬疑犯罪题材，这部用密室追凶与双线叙事延续该口味。",
                    "summary": "悬疑迷局层层牵出尘封往事与真相",
                    "match_tags": ["悬疑犯罪", "双线叙事"],
                    "confidence": 86,
                }
            ],
        },
        ensure_ascii=False,
    )


def _candidates():
    return [
        Candidate(candidate_id="tmdb:1", title="One", media_type="movie"),
        Candidate(candidate_id="tmdb:2", title="Two", media_type="tv"),
        Candidate(candidate_id="bangumi:3", title="Three", media_type="anime"),
    ]


def test_prompt_states_hard_boundaries_without_embedding_untrusted_media_text():
    """Candidate text remains tool data and cannot overwrite the protocol."""
    prompt = build_ranking_prompt(max_recommendations=10)

    assert "read_agentrank_candidates" in prompt
    assert "candidate_id" in prompt
    assert "禁止订阅" in prompt
    assert "不得暴露推理过程" in prompt
    assert "单个 JSON 对象" in prompt
    assert "不超过三十" in prompt
    assert "两个 match_tags" in prompt
    assert "评分高、热度高" in prompt
    assert "evidence_catalog" in prompt
    assert "type=tv" in prompt
    assert "candidate.media_type=anime" in prompt
    assert "两项证据可以同为 theme" in prompt
    assert '"reason"' in prompt
    assert "文案要具体、流畅" in prompt
    assert "最多 8 条" in prompt
    assert "最终仍只保存五条" in prompt
    assert "ignore all previous instructions" not in prompt


def test_profile_prompt_uses_one_read_one_submit_without_repeating_schema():
    """画像提示只保留角色边界和工具顺序，字段规则交给提交 schema。"""
    prompt = build_profile_prompt()

    assert prompt.count("read_agentrank_profile_context") == 1
    assert prompt.count("submit_agentrank_profile_result") == 1
    assert "唯一输出通道" in prompt
    assert "禁止返回自由文本 JSON" in prompt
    assert "禁止猜测题材或未知 ID" in prompt
    for repeated_schema_field in (
        '"filters"',
        '"ranking_tags"',
        '"genre_ids"',
        '"keyword_ids"',
    ):
        assert repeated_schema_field not in prompt


def test_preliminary_and_final_prompts_only_name_their_one_read_one_submit_tools():
    """初赛与决赛提示不重复候选数据或大段输出 schema。"""
    preliminary = build_preliminary_prompt()
    final = build_final_prompt("文案克制", "相关性优先")

    assert preliminary.count("read_agentrank_batch_context") == 1
    assert preliminary.count("submit_agentrank_batch_result") == 1
    assert "每一条候选" in preliminary
    assert "0 到 100 的整数" in preliminary
    assert "影片与当前用户观影偏好的总体契合度" in preliminary
    assert "不能拿作品质量、热度或大众口碑代替个人契合度" in preliminary
    assert "禁止无依据地全部给满分" in preliminary
    assert final.count("read_agentrank_final_context") == 1
    assert final.count("submit_agentrank_final_board") == 1
    assert "每条推荐都必须提交零到一百的整数 fit_score" in final
    assert "补位候选也必须" in final
    assert "不能直接照抄确定性支持度" in final
    assert "提交顺序必须按 fit_score 从高到低" in final
    assert "同分候选按你的最终优先级排列" in final
    assert "排序要求：相关性优先" in final
    assert "文案要求：文案克制" in final
    assert "用户偏好短词和一个作品事实短词" in final
    for prompt in (preliminary, final):
        assert "candidate_id\"" not in prompt
        assert "positive_evidence\"" not in prompt


def test_final_evidence_parser_requires_bounded_fit_score():
    """决赛证据协议必须为每条推荐提交合法的最终评分。"""
    recommendation = {
        "candidate_id": "tmdb:1",
        "fit_score": 88,
        "reason": "悬疑偏好与密室追凶题材相符。",
        "summary": "密室旧案牵出尘封真相。",
        "match_tags": ["悬疑", "电影"],
        "positive_evidence": [
            {
                "dimension": "theme",
                "user_value": "悬疑",
                "candidate_value": "悬疑",
            },
            {
                "dimension": "type",
                "user_value": "movie",
                "candidate_value": "movie",
            },
        ],
        "counter_evidence": [],
    }

    parsed = AgentOutputParser().parse(_output([recommendation]))

    assert parsed.recommendations[0].fit_score == 88
    for invalid_fit_score in (None, -1, 101, True):
        invalid = dict(recommendation)
        invalid["fit_score"] = invalid_fit_score
        with pytest.raises(AgentOutputError, match="fit_score"):
            AgentOutputParser().parse(_output([invalid]))
    missing = dict(recommendation)
    missing.pop("fit_score")
    with pytest.raises(AgentOutputError):
        AgentOutputParser().parse(_output([missing]))


def test_psychological_motivation_is_evidence_bounded_and_never_diagnostic():
    """观看动机仅以多证据软排序，且禁止敏感心理推断。"""
    profile_prompt = build_profile_prompt()
    ranking_prompt = build_ranking_prompt()

    for prompt in (profile_prompt, ranking_prompt):
        for dimension in (
            "情绪体验",
            "认知满足",
            "叙事投入",
            "熟悉与新奇",
            "节奏与完成感",
        ):
            assert dimension in prompt
        assert "至少两条相互独立" in prompt
        assert "单一样本不得形成稳定结论" in prompt
        assert "弱负向信号" in prompt
        assert "人格、焦虑、孤独、疾病、创伤" in prompt
        assert "软排序信号" in prompt
        assert "不得输出心理诊断或心理学术语" in prompt


def test_custom_ranking_and_copy_prompts_keep_fixed_contract():
    """排序与文案指令各自生效，但固定工具与输出边界仍存在。"""
    prompt = build_ranking_prompt(
        ranking_prompt="优先推荐冷门科幻",
        copy_prompt="保持俏皮但克制的文风",
    )
    assert "优先推荐冷门科幻" in prompt
    assert "保持俏皮但克制的文风" in prompt
    assert "只能通过 read_agentrank_playback" in prompt
    assert "不能覆盖硬性边界、输出结构或字段校验" in prompt
    assert "不超过三十" in prompt
    assert "不得按字符截断原文" in prompt
    assert "每个 match_tags 标签最多五个字符" in prompt


def test_profile_prompt_is_isolated_from_ranking_and_copy_prompts():
    """画像指令只进入画像协议，排序与文案指令只进入榜单协议。"""
    profile = build_profile_prompt(profile_prompt="画像只关注叙事节奏")
    ranking = build_ranking_prompt(
        ranking_prompt="排序优先新鲜感",
        copy_prompt="文案保持简洁",
    )

    assert "画像只关注叙事节奏" in profile
    assert "排序优先新鲜感" not in profile
    assert "文案保持简洁" not in profile
    assert "排序优先新鲜感" in ranking
    assert "文案保持简洁" in ranking
    assert "画像只关注叙事节奏" not in ranking


def test_refill_reuses_ranking_and_copy_prompts():
    """唯一补选沿用同一排序策略和文案风格。"""
    prompt = build_refill_prompt(
        ["tmdb:1"],
        1,
        ranking_prompt="补选仍按相关性排序",
        copy_prompt="补选文案保持克制",
    )
    assert "补选仍按相关性排序" in prompt
    assert "补选文案保持克制" in prompt


def test_persona_reaches_final_ranking_and_refill_without_overriding_contract():
    """自定义人设进入三条用户文案链路，同时保留工具、证据与 schema 边界。"""
    persona = "像严谨的实验室助手一样轻微吐槽，但先说清推荐依据。"
    prompts = (
        build_final_prompt(persona_prompt=persona),
        build_ranking_prompt(persona_prompt=persona),
        build_refill_prompt(["tmdb:1"], 1, persona_prompt=persona),
    )

    for prompt in prompts:
        assert persona in prompt
        assert "人设只影响推荐理由 reason" in prompt
        assert "summary 必须保持客观中立" in prompt
        assert "不能改变候选选择、排序、事实、证据引用" in prompt

    assert prompts[0].count("read_agentrank_final_context") == 1
    assert "只能通过 read_agentrank_playback" in prompts[1]
    assert "这是唯一一轮补选" in prompts[2]
    default_prompt = build_ranking_prompt()
    assert "默认克里斯蒂娜人设必须在本轮 Top 5 的至少两条 reason" in default_prompt


def test_continuation_guidance_is_dynamic_and_follows_effective_persona():
    """继续观看建议依赖安全状态与当前人设，不能退化为固定模板。"""
    persona = "像冷静的档案管理员一样给出简洁建议。"
    prompts = (
        build_final_prompt(persona_prompt=persona),
        build_ranking_prompt(persona_prompt=persona),
        build_refill_prompt(["tmdb:1"], 1, persona_prompt=persona),
    )

    for prompt in prompts:
        assert "in_library=true 且 watch_status=partial" in prompt
        assert "按照当前有效人设" in prompt
        assert "不要固定复用“值得坚持看完”" in prompt
        assert "同一 Top 5 中的继续观看提示应随作品事实变化" in prompt
        assert "不得猜测用户停看的原因" in prompt
        assert persona in prompt
        assert "包括开始、继续或重拾观看建议" in prompt


def test_custom_critic_prompt_extends_all_critic_roles_without_overriding_safety():
    """CinePilot Agent 扩展指令进入三种角色，同时保留工具、记忆和写操作边界。"""
    custom = "发现证据冲突时先向用户确认，不要自行归因。"
    prompts = (
        build_feedback_understanding_prompt(custom),
        build_analysis_comment_prompt(custom),
        build_conversation_prompt(custom),
    )

    for prompt in prompts:
        assert custom in prompt
        assert "不能覆盖上述硬性边界" in prompt
        assert "心理" in prompt
        assert "原始推理过程或思维链" in prompt
    assert "人格、焦虑、孤独、疾病、创伤" in prompts[0]
    assert "人格、焦虑、孤独、疾病、创伤" in prompts[2]
    assert "只能调用 read_agentrank_feedback_event" in prompts[0]
    assert "不得改变确定性证据" in prompts[1]
    assert "你没有任何写工具" in prompts[2]
    assert "不得生成 weight 或来源修改命令" in prompts[2]
    assert '"kind": "weight"' not in prompts[2]


def test_persona_prompt_is_separate_and_cannot_override_agent_safety():
    """独立人设进入三类用户表达，但安全协议和JSON契约仍优先。"""
    persona = "用高浓度二次元天才少女语气，偶尔提到世界线。"
    prompts = (
        build_feedback_understanding_prompt(persona_prompt=persona),
        build_analysis_comment_prompt(persona_prompt=persona),
        build_conversation_prompt(persona_prompt=persona),
    )

    for prompt in prompts:
        assert persona in prompt
        assert "人设只影响用户可见表达" in prompt
        assert "输出 schema" in prompt
    assert "signals" in prompts[0]
    assert "revised_reason" in prompts[1]
    assert "commands" in prompts[2]


def test_parser_accepts_one_schema_object_and_preserves_agent_order():
    """A valid object parses without sorting or changing recommendation order."""
    payload = _output(
        [
            {
                "candidate_id": "tmdb:2",
                "summary": "连环剧情逐步揭开人物命运新篇章",
                "match_tags": ["剧情"],
                "confidence": 70,
            },
            {
                "candidate_id": "tmdb:1",
                "summary": "悬疑迷局层层牵出尘封往事与真相",
                "match_tags": ["悬疑"],
                "confidence": 90,
            },
        ]
    )
    parsed = AgentOutputParser().parse(payload)

    assert [item.candidate_id for item in parsed.recommendations] == ["tmdb:2", "tmdb:1"]


def test_validator_recovers_missing_summary_from_frozen_candidate_overview():
    """Agent 漏写简介时使用冻结候选剧情，不得让整份排序输出失败。"""
    candidate = Candidate(
        candidate_id="tmdb:missing-summary",
        title="缺简介",
        media_type="movie",
        overview="一名侦探追查旧案并发现家族秘密。",
        genres=["悬疑"],
    )
    payload = json.dumps(
        {
            "recommendations": [{
                "candidate_id": candidate.candidate_id,
                "reason": "你偏爱悬疑题材，这部作品围绕旧案调查展开。",
                "match_tags": ["悬疑", "旧案"],
                "confidence": 80,
            }]
        },
        ensure_ascii=False,
    )

    parsed = AgentOutputParser().parse(payload)
    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["悬疑"],
    )

    assert result.dropped == []
    assert result.accepted[0].summary == "一名侦探追查旧案并发现家族秘密。"
    assert len(result.accepted[0].summary) <= 30


@pytest.mark.parametrize(
    "payload",
    [
        "```json\n" + _output() + "\n```",
        "结果如下：" + _output(),
        _output() + "\n" + _output(),
        "[]",
        json.dumps({"profile": {}, "recommendations": [], "username": "bob"}),
    ],
)
def test_parser_rejects_markdown_prefix_multiple_values_non_object_and_extra_scope(payload):
    """Only one exact top-level schema object is accepted."""
    with pytest.raises(AgentOutputError):
        AgentOutputParser().parse(payload)


def test_parser_enforces_byte_count_tag_count_and_string_limits():
    """Oversized output and nested strings are rejected before domain validation."""
    with pytest.raises(AgentOutputError, match="bytes"):
        AgentOutputParser(max_bytes=50).parse(_output())

    profile = {
        "summary": "摘要",
        "tags": [f"标签{index}" for index in range(21)],
        "negative_tags": [],
        "playback_count": 1,
    }
    with pytest.raises(AgentOutputError, match="tags"):
        ProfileOutputParser().parse(_profile_output(profile=profile))


def test_ranking_parser_rejects_more_than_five_recommendations():
    """固定榜单协议不接受超过五条的排序输出。"""
    recommendations = [
        {
            "candidate_id": f"tmdb:{index}",
            "reason": "你偏爱悬疑题材，这部作品围绕旧案调查展开。",
            "summary": "侦探追查旧案真相",
            "match_tags": ["悬疑", "旧案"],
            "confidence": 80,
        }
        for index in range(1, 7)
    ]

    with pytest.raises(AgentOutputError, match="exceeds 5 items"):
        RankingOutputParser().parse(_output(recommendations))


def test_ranking_parser_can_accept_three_bounded_reserve_items():
    """运行编排器可显式接收五条正式候选和三条校验备用候选。"""
    recommendations = [
        {
            "candidate_id": f"tmdb:{index}",
            "reason": "你偏爱悬疑题材，这部作品围绕旧案调查展开。",
            "summary": "侦探追查旧案真相",
            "match_tags": ["悬疑", "旧案"],
            "confidence": 80,
        }
        for index in range(1, 9)
    ]

    parsed = RankingOutputParser(max_recommendations=8).parse(
        _output(recommendations)
    )

    assert len(parsed.recommendations) == 8


def test_recoverable_ranking_parser_keeps_valid_items_and_records_bad_siblings():
    """补选解析器忽略额外字段并按条丢弃真正无效的推荐。"""
    recommendations = json.loads(
        _output(
            [
                {
                    "candidate_id": "tmdb:1",
                    "reason": "你偏爱悬疑题材，这部围绕旧案调查展开。",
                    "summary": "侦探追查旧案真相",
                    "match_tags": ["悬疑", "旧案"],
                    "confidence": 80,
                    "completed_episode_count": 2,
                },
                {
                    "candidate_id": "tmdb:2",
                    "reason": "你偏爱悬疑题材，这部围绕密室案件展开。",
                    "summary": "密室案件牵出隐藏真相",
                    "match_tags": ["悬疑", "密室"],
                    "confidence": "80",
                },
                {
                    "candidate_id": "bangumi:3",
                    "reason": "你偏爱悬疑题材，这部围绕连环谜案展开。",
                    "summary": "连环谜案逐步揭开真相",
                    "match_tags": ["悬疑", "谜案"],
                    "confidence": 78,
                },
            ]
        )
    )
    payload = json.dumps(recommendations, ensure_ascii=False)

    with pytest.raises(AgentOutputError, match="completed_episode_count"):
        RankingOutputParser().parse(payload)

    parsed, warnings = RankingOutputParser().parse_recoverable(payload)

    assert [item.candidate_id for item in parsed.recommendations] == [
        "tmdb:1",
        "bangumi:3",
    ]
    assert any("completed_episode_count" in warning for warning in warnings)
    assert any("confidence must be an integer" in warning for warning in warnings)


def test_profile_and_ranking_parsers_reject_each_others_schema():
    """两个 Agent parser 不接受对方的根字段。"""
    with pytest.raises(AgentOutputError):
        ProfileOutputParser().parse(_output())
    with pytest.raises(AgentOutputError):
        RankingOutputParser().parse(_profile_output())


def test_profile_parser_accepts_only_stable_profile_fields():
    """画像 parser 不再接受检索筛选或自由排序字段。"""
    parsed = ProfileOutputParser().parse(_profile_output())
    assert parsed.profile.playback_count == 12
    assert not hasattr(parsed, "retrieval_plan")


def test_profile_parser_trims_overlong_summary_without_rejecting_profile():
    """画像摘要偶发超长时裁剪文本，不能让整轮推荐提前失败。"""
    parsed = ProfileOutputParser().parse(
        _profile_output(
            profile={
                "summary": "偏好悬疑与人物成长，" * 30,
                "tags": ["悬疑"],
                "negative_tags": [],
                "playback_count": 12,
            }
        )
    )

    assert 0 < len(parsed.profile.summary) <= 200


def test_profile_parser_rejects_retrieval_fields():
    """画像输出携带检索字段时必须被拒绝，检索计划由独立角色提交。"""
    payload = json.loads(_profile_output())
    payload["filters"] = {}
    with pytest.raises(AgentOutputError):
        ProfileOutputParser().parse(json.dumps(payload, ensure_ascii=False))


def test_profile_parser_rejects_extra_root_fields_and_duplicate_free_tags():
    """根对象额外字段与重复自由标签均被拒绝。"""
    payload = json.loads(_profile_output())
    payload["unexpected"] = True
    with pytest.raises(AgentOutputError):
        ProfileOutputParser().parse(json.dumps(payload, ensure_ascii=False))

    payload["ranking_tags"] = ["悬疑"]
    with pytest.raises(AgentOutputError):
        ProfileOutputParser().parse(json.dumps(payload, ensure_ascii=False))


def test_validator_rejects_every_unsafe_item_with_specific_reason():
    """Unknown, duplicate, archived, subscribed, confidence, and summary failures drop."""
    parsed = AgentOutputParser().parse(
        _output(
            [
                {"candidate_id": "unknown", "summary": "精彩故事生动呈现人物命运新篇章", "match_tags": [], "confidence": 50},
                {"candidate_id": "tmdb:1", "summary": "悬疑迷局层层牵出尘封往事与真相", "match_tags": [], "confidence": 80},
                {"candidate_id": "tmdb:1", "summary": "悬疑迷局层层牵出尘封往事与真相", "match_tags": [], "confidence": 70},
                {"candidate_id": "tmdb:2", "summary": "连环剧情逐步揭开人物命运新篇章", "match_tags": [], "confidence": 101},
                {"candidate_id": "bangumi:3", "summary": "not chinese", "match_tags": [], "confidence": 60},
            ]
        )
    )
    result = RecommendationValidator().validate(
        parsed,
        _candidates(),
        archived_candidate_ids={"tmdb:1"},
        subscribed_candidate_ids=set(),
    )

    assert result.accepted == []
    assert [drop.reason for drop in result.dropped] == [
        "unknown_candidate",
        "archived_candidate",
        "duplicate_candidate",
        "invalid_confidence",
        "invalid_reason",
    ]


def test_validator_scores_five_unique_grounded_fallback_items_with_same_policy():
    """安全补位使用同一策略评分，并按净分和冻结顺序稳定破局。"""
    candidates = [
        Candidate(
            candidate_id=f"tmdb:{index}",
            title=f"作品{index}",
            media_type="movie",
            overview=f"第{index}部作品围绕旧案调查展开。",
            genres=["悬疑" if index % 2 else "剧情"],
            source_ids={"tmdb": str(index)},
        )
        for index in range(1, 8)
    ]

    policy, memory, preferences, playback = _support_context()
    fallback = RecommendationValidator().build_fallback_items(
        candidates,
        accepted=[],
        blocked_candidate_ids={"tmdb:2"},
        preference_evidence=["偏好悬疑犯罪作品"],
        limit=5,
        policy_snapshot=policy,
        confirmed_memory=memory,
        profile_preferences=preferences,
        playback_snapshot=playback,
    )

    assert [item.candidate_id for item in fallback] == [
        "tmdb:1",
        "tmdb:3",
        "tmdb:5",
        "tmdb:7",
        "tmdb:4",
    ]
    assert [item.rank for item in fallback] == [1, 2, 3, 4, 5]
    assert all(item.support is not None for item in fallback)
    assert all(item.selection_source == "safe_fallback" for item in fallback)
    assert all(item.confidence == item.support.percentage for item in fallback)
    assert all("安全" in item.reason or "保底" in item.reason for item in fallback)
    assert all(item.summary for item in fallback)
    assert all(len(item.reason) <= 30 for item in fallback)
    assert all(len(item.summary) <= 30 for item in fallback)
    assert all(item.reason.endswith("。") for item in fallback)


def test_fallback_blocks_counter_evidence_and_never_projects_profile_tags():
    """安全补位排除反向命中项，标签只描述候选自身事实。"""
    candidates = [
        Candidate(
            candidate_id="tmdb:reality",
            title="真人节目",
            media_type="movie",
            genres=["悬疑", "真人秀"],
        ),
        Candidate(
            candidate_id="tmdb:safe",
            title="旧案追踪",
            media_type="movie",
            genres=["悬疑", "剧情"],
        ),
    ]
    policy, memory, _, playback = _support_context()
    preferences = ProfilePreferences(
        profile_id=playback.profile_id,
        custom_negative_tags=["真人秀"],
    )

    fallback = RecommendationValidator().build_fallback_items(
        candidates,
        accepted=[],
        preference_evidence=["国产修仙动画"],
        limit=2,
        policy_snapshot=policy,
        confirmed_memory=memory,
        profile_preferences=preferences,
        playback_snapshot=playback,
    )

    assert [item.candidate_id for item in fallback] == ["tmdb:safe"]
    assert fallback[0].match_tags == ["悬疑", "剧情"]
    assert "国产修仙" not in fallback[0].match_tags


@pytest.mark.parametrize(
    ("reason", "summary", "drop_reason"),
    [
        (
            "你有悬疑片偏好，这部旧案调查故事围绕小镇秘密展开，人物关系也会逐步揭开。",
            "侦探追查旧案并发现家族秘密。",
            "reason_too_long",
        ),
        (
            "悬疑偏好契合这部作品的旧案调查。",
            "一名侦探追查多年未解旧案，并在封闭小镇逐步发现一个家族隐藏已久的秘密。",
            "summary_too_long",
        ),
    ],
)
def test_validator_rejects_overlong_copy_for_semantic_rewrite(
    reason, summary, drop_reason
):
    """推荐与简介超长时进入补写链路，不得机械截取原文。"""
    candidate = Candidate(
        candidate_id="tmdb:9",
        title="九号",
        media_type="movie",
        overview="一段旧案调查故事，并在封闭小镇发现家族秘密。",
        genres=["悬疑"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [{
                "candidate_id": "tmdb:9",
                "reason": reason,
                "summary": summary,
                "match_tags": ["悬疑片偏好者", "旧案调查故事"],
                "confidence": 88,
            }]
        )
    )

    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["悬疑片偏好"],
    )

    assert result.accepted == []
    assert [item.reason for item in result.dropped] == [drop_reason]


def test_fallback_summary_uses_complete_semantic_copy_instead_of_truncation():
    """长剧情兜底应生成完整概括，不得保留原文开头残句。"""
    candidate = Candidate(
        candidate_id="tmdb:summary-fallback",
        title="长剧情",
        media_type="movie",
        overview="一名侦探追查多年未解旧案，并在封闭小镇逐步发现一个家族隐藏已久的秘密。",
        genres=["悬疑"],
    )

    summary = fallback_summary(candidate)

    assert summary == "围绕悬疑题材展开的完整故事。"
    assert len(summary) <= 30
    assert summary.endswith("。")


def test_validator_rejects_copy_with_unclosed_title_marks():
    """三十字内仍带未闭合书名号的残句不得进入榜单。"""
    candidate = Candidate(
        candidate_id="tmdb:broken-copy",
        title="残句",
        media_type="tv",
        overview="演员争取机会并走出事业困境。",
        genres=["剧情"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [{
                "candidate_id": candidate.candidate_id,
                "reason": "你偏爱人物成长，这部剧情聚焦事业突围。",
                "summary": "需要机会告别事业困境的演员去试戏电影《入",
                "match_tags": ["人物成长", "剧情"],
                "confidence": 80,
            }]
        )
    )

    result = RecommendationValidator().validate(
        parsed, [candidate], set(), set(), preference_evidence=["人物成长"]
    )

    assert result.accepted == []
    assert [item.reason for item in result.dropped] == ["invalid_summary"]


def test_validator_repairs_unsupported_agent_tags_from_trusted_evidence():
    """Agent 标签措辞不准时改用画像与候选事实，不因此丢弃作品。"""
    candidate = Candidate(
        candidate_id="tmdb:8",
        title="八号",
        media_type="tv",
        overview="一宗旧案牵出多年前的秘密。",
        genres=["剧情"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [{
                "candidate_id": "tmdb:8",
                "reason": "你偏爱悬疑追查，这部剧情围绕旧案秘密展开。",
                "summary": "旧案牵出多年前的秘密",
                "match_tags": ["烧脑神作", "群像反转线"],
                "confidence": 82,
            }]
        )
    )

    result = RecommendationValidator().validate(
        parsed, [candidate], set(), set(), preference_evidence=["悬疑"]
    )

    assert result.dropped == []
    assert result.accepted[0].match_tags == ["悬疑", "剧情"]


def test_validator_localizes_region_code_when_repairing_tags():
    """地区码作为候选事实回退时应转换为中文短标签。"""
    candidate = Candidate(
        candidate_id="tmdb:10",
        title="十号",
        media_type="tv",
        overview="校园中的阶层冲突逐步升级。",
        regions=["KR"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [{
                "candidate_id": "tmdb:10",
                "reason": "你偏爱复仇题材，这部韩国校园剧延续阶层冲突。",
                "summary": "校园阶层冲突逐步升级",
                "match_tags": ["复仇", "KR"],
                "confidence": 80,
            }]
        )
    )

    result = RecommendationValidator().validate(
        parsed, [candidate], set(), set(), preference_evidence=["复仇"]
    )

    assert result.dropped == []
    assert result.accepted[0].match_tags == ["复仇", "韩国"]


def test_validator_does_not_turn_playback_title_prefix_into_tag():
    """播放片名可作为理由证据，但不能被硬截成总结标签。"""
    candidate = Candidate(
        candidate_id="tmdb:11",
        title="十一号",
        media_type="tv",
        overview="日式动画中的时代冒险故事。",
        genres=["动画"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [{
                "candidate_id": "tmdb:11",
                "reason": "你看过尖帽子的魔法工房，这部同为日式动画时代冒险。",
                "summary": "日式动画时代冒险故事",
                "match_tags": ["尖帽子的魔法工房", "时代"],
                "confidence": 78,
            }]
        )
    )

    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["日本奇幻动画", "尖帽子的魔法工房"],
    )

    assert result.dropped == []
    assert "尖帽子的魔" not in result.accepted[0].match_tags
    assert all(len(tag) <= 5 for tag in result.accepted[0].match_tags)


def test_validator_uses_reason_supported_region_theme_tag_instead_of_first_profile_tag():
    """理由只提到日本奇幻时不能回退成画像列表首个中国标签。"""
    candidate = Candidate(
        candidate_id="tmdb:12",
        title="十二号",
        media_type="tv",
        overview="日本动画中的奇幻探案故事。",
        genres=["动画"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [{
                "candidate_id": "tmdb:12",
                "reason": "你喜欢日本奇幻动画，这部作品延续动画探案设定。",
                "summary": "日本动画奇幻探案故事",
                "match_tags": ["中国动画", "动画"],
                "confidence": 78,
            }]
        )
    )

    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["中国动画", "日本奇幻动画"],
    )

    assert result.dropped == []
    assert result.accepted[0].match_tags == ["日本奇幻", "动画"]


def test_validator_summarizes_playback_title_reference_as_profile_theme():
    """理由可引用播放片名，但标签必须归纳画像主题而不是显示片名。"""
    candidate = Candidate(
        candidate_id="tmdb:13",
        title="十三号",
        media_type="tv",
        overview="未来都市中的网络犯罪调查。",
        genres=["动画"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [{
                "candidate_id": "tmdb:13",
                "reason": "你看完挽救计划，这部同为科幻动画。",
                "summary": "未来都市网络犯罪调查",
                "match_tags": ["挽救计划", "动画"],
                "confidence": 80,
            }]
        )
    )

    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["科幻动作"],
    )

    assert result.dropped == []
    assert result.accepted[0].match_tags == ["科幻", "动画"]


def test_validator_keeps_valid_agent_order_and_enriches_from_candidate_pool():
    """Validation preserves Agent order and only enriches display fields."""
    parsed = AgentOutputParser().parse(
        _output(
            [
                {
                    "candidate_id": "tmdb:2",
                    "reason": "你偏爱人物剧情，这部群像冲突延续成长体验。",
                    "summary": "连环剧情逐步揭开人物命运新篇章",
                    "match_tags": ["人物剧情", "群像关系"],
                    "confidence": 70,
                },
                {
                    "candidate_id": "tmdb:1",
                    "reason": "你常订阅悬疑犯罪，这部密室追凶延续该口味。",
                    "summary": "悬疑迷局层层牵出尘封往事与真相",
                    "match_tags": ["悬疑犯罪", "双线叙事"],
                    "confidence": 90,
                },
            ]
        )
    )
    result = RecommendationValidator().validate(parsed, _candidates(), set(), set())

    assert [(item.candidate_id, item.rank, item.title) for item in result.accepted] == [
        ("tmdb:2", 1, "Two"),
        ("tmdb:1", 2, "One"),
    ]
    assert all(item.reason for item in result.accepted)


def test_validator_rejects_vague_reason_and_insufficient_match_evidence():
    """空泛断言和单一匹配标签不能进入榜单。"""
    parsed = AgentOutputParser().parse(
        _output(
            [
                {
                    "candidate_id": "tmdb:1",
                    "reason": "这是一部评分很高的悬疑神作，你看完之后肯定喜欢。",
                    "summary": "悬疑迷局层层牵出尘封往事与真相",
                    "match_tags": ["悬疑", "高评分"],
                    "confidence": 90,
                },
                {
                    "candidate_id": "tmdb:2",
                    "reason": "你偏爱人物剧情，这部连续冲突正好延续这一观看口味。",
                    "summary": "连环剧情逐步揭开人物命运新篇章",
                    "match_tags": ["人物剧情"],
                    "confidence": 80,
                },
            ]
        )
    )

    result = RecommendationValidator().validate(parsed, _candidates(), set(), set())

    assert [drop.reason for drop in result.dropped] == [
        "invalid_reason",
        "insufficient_match_evidence",
    ]


@pytest.mark.parametrize(
    "phrase",
    ("不容错过", "不可错过", "值得一看", "强烈推荐", "一定要看", "不看可惜"),
)
def test_validator_rejects_vague_recommendation_synonyms(phrase):
    """明确同义的空泛推荐结论不能绕过理由安全门。"""
    parsed = AgentOutputParser().parse(
        _output(
            [{
                "candidate_id": "tmdb:1",
                "reason": f"你偏爱悬疑犯罪，这部经典作品{phrase}。",
                "summary": "密室追凶牵出旧案真相",
                "match_tags": ["悬疑犯罪", "密室追凶"],
                "confidence": 88,
            }]
        )
    )

    result = RecommendationValidator().validate(
        parsed,
        _candidates(),
        set(),
        set(),
        preference_evidence=["悬疑犯罪"],
    )

    assert result.accepted == []
    assert result.dropped[0].reason == "invalid_reason"


def test_validator_rejects_numeric_watch_events_as_completion_count():
    """播放事件数不得进入“看完 X 次”这类歧义推荐理由。"""
    for reason in (
        "你看完了100次悬疑剧，这部密室追凶延续悬疑体验。",
        "你100次看完悬疑剧，这部密室追凶延续悬疑体验。",
    ):
        parsed = AgentOutputParser().parse(
            _output(
                [{
                    "candidate_id": "tmdb:1",
                    "reason": reason,
                    "summary": "密室追凶牵出旧案真相",
                    "match_tags": ["悬疑", "密室追凶"],
                    "confidence": 88,
                }]
            )
        )

        result = RecommendationValidator().validate(
            parsed,
            _candidates(),
            set(),
            set(),
            preference_evidence=["悬疑"],
        )

        assert result.accepted == []
        assert result.dropped[0].reason == "ambiguous_playback_count"


def test_validator_rejects_unproven_playback_title_and_actor_claims():
    """推荐理由不能凭画像标签虚构看过的片名或演员经历。"""
    candidate = Candidate(
        candidate_id="tmdb:1",
        title="新动作片",
        media_type="movie",
        overview="追查旧案的动作冒险故事。",
        genres=["动作", "犯罪"],
        actors=["演员甲"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [
                {
                    "candidate_id": "tmdb:1",
                    "reason": "你爱看华语动作片如英雄精武门，这部动作犯罪延续追查线。",
                    "summary": "动作冒险追查旧案",
                    "match_tags": ["动作", "犯罪"],
                    "confidence": 82,
                }
            ]
        )
    )
    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["华语动作"],
        playback_samples=[
            {
                "title": "未提及的作品",
                "overview": "一部悬疑故事。",
                "genres": ["悬疑"],
            }
        ],
    )
    assert result.accepted == []
    assert result.dropped[0].reason == "unsupported_playback_claim"


def test_validator_accepts_playback_title_only_when_snapshot_contains_it():
    """真实播放片名存在于快照时可以作为理由证据。"""
    candidate = Candidate(
        candidate_id="tmdb:1",
        title="新动作片",
        media_type="movie",
        overview="追查旧案的动作冒险故事。",
        genres=["动作", "犯罪"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [
                {
                    "candidate_id": "tmdb:1",
                    "reason": "你看过英雄，这部动作犯罪延续追查线。",
                    "summary": "动作冒险追查旧案",
                    "match_tags": ["动作", "犯罪"],
                    "confidence": 82,
                }
            ]
        )
    )
    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["动作"],
        playback_samples=[{"title": "英雄", "genres": ["动作"]}],
    )
    assert result.dropped == []
    assert result.accepted[0].title == "新动作片"


def test_validator_accepts_common_playback_aliases_and_split_titles():
    """真实播放片名的常见简称与并列写法不应被安全门误删。"""
    candidate = Candidate(
        candidate_id="tmdb:1",
        title="异世界校园番",
        media_type="tv",
        overview="少年转生异世界并进入校园生活。",
        genres=["动画", "奇幻"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [
                {
                    "candidate_id": "tmdb:1",
                    "reason": "你完整看完Re0和尖帽工房，这部转生异世界奇幻动画风格相近",
                    "summary": "少年转生异世界入学名校",
                    "match_tags": ["日本奇幻", "动画"],
                    "confidence": 86,
                }
            ]
        )
    )
    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["日本奇幻动画"],
        playback_samples=[
            {"title": "Re：从零开始的异世界生活", "genres": ["动画"]},
            {"title": "尖帽子的魔法工房", "genres": ["动画"]},
        ],
    )
    assert result.dropped == []


def test_validator_accepts_verified_titles_with_generic_tail():
    """连续列出的真实片名后接“等多部”泛类别时应逐项通过。"""
    candidate = Candidate(
        candidate_id="tmdb:1",
        title="新修仙动画",
        media_type="tv",
        overview="国漫修仙冒险故事。",
        genres=["动画", "奇幻"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [
                {
                    "candidate_id": "tmdb:1",
                    "reason": "你追完沧元图光阴之外等多部国漫修仙，这部动画奇幻风格相近",
                    "summary": "国漫修仙冒险故事",
                    "match_tags": ["动画", "奇幻"],
                    "confidence": 86,
                }
            ]
        )
    )
    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["国漫修仙"],
        playback_samples=[
            {"title": "沧元图", "genres": ["动画", "动作冒险"]},
            {"title": "光阴之外", "genres": ["动画", "科幻奇幻"]},
        ],
    )
    assert result.dropped == []


def test_validator_accepts_playback_title_with_category_prefix():
    """真实片名前的“韩剧”等受控类别修饰不能造成误删。"""
    candidate = Candidate(
        candidate_id="tmdb:1",
        title="韩国校园剧",
        media_type="tv",
        overview="校园阶层冲突带来持续剧情张力。",
        genres=["剧情"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [
                {
                    "candidate_id": "tmdb:1",
                    "reason": "你完整看完韩剧黑暗荣耀，这部韩国校园剧情张力十足",
                    "summary": "转学生打破校园秩序",
                    "match_tags": ["韩国剧情", "剧情"],
                    "confidence": 83,
                }
            ]
        )
    )
    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["韩国剧情"],
        playback_samples=[{"title": "黑暗荣耀", "genres": ["剧情"]}],
    )
    assert result.dropped == []


def test_validator_rejects_unverified_title_inside_verified_title_list():
    """连续片名中混入一个不存在的标题时不能被已知片名子串掩盖。"""
    candidate = Candidate(
        candidate_id="tmdb:1",
        title="新科幻片",
        media_type="movie",
        overview="未来城市冒险故事。",
        genres=["科幻", "冒险"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [
                {
                    "candidate_id": "tmdb:1",
                    "reason": "你看过挽救计划不存在等科幻片，这部科幻冒险延续未来设定",
                    "summary": "未来城市冒险故事",
                    "match_tags": ["科幻", "冒险"],
                    "confidence": 82,
                }
            ]
        )
    )
    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["科幻"],
        playback_samples=[{"title": "挽救计划", "genres": ["科幻"]}],
    )
    assert result.accepted == []
    assert result.dropped[0].reason == "unsupported_playback_claim"


def test_validator_rejects_unproven_repeated_playback_title():
    """多次播放的具体片名没有快照证据时仍必须被拒绝。"""
    candidate = Candidate(
        candidate_id="tmdb:1",
        title="新动作片",
        media_type="movie",
        overview="追查旧案的动作冒险故事。",
        genres=["动作", "犯罪"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [
                {
                    "candidate_id": "tmdb:1",
                    "reason": "你多次播放英雄，这部动作犯罪延续追查线。",
                    "summary": "动作冒险追查旧案",
                    "match_tags": ["动作", "犯罪"],
                    "confidence": 82,
                }
            ]
        )
    )
    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["动作"],
        playback_samples=[{"title": "未提及的作品", "genres": ["悬疑"]}],
    )
    assert result.accepted == []
    assert result.dropped[0].reason == "unsupported_playback_claim"


def test_validator_rejects_specific_title_disguised_as_generic_work():
    """“作品”等泛词不能替不存在的具体片名绕过播放证据校验。"""
    candidate = Candidate(
        candidate_id="tmdb:1",
        title="新动作片",
        media_type="movie",
        overview="追查旧案的动作冒险故事。",
        genres=["动作", "犯罪"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [
                {
                    "candidate_id": "tmdb:1",
                    "reason": "你多次播放不存在的作品，这部动作犯罪延续追查线。",
                    "summary": "动作冒险追查旧案",
                    "match_tags": ["动作", "犯罪"],
                    "confidence": 82,
                }
            ]
        )
    )
    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["动作"],
        playback_samples=[{"title": "真实悬疑片", "genres": ["悬疑"]}],
    )
    assert result.accepted == []
    assert result.dropped[0].reason == "unsupported_playback_claim"


def test_validator_accepts_generic_playback_category_with_snapshot_evidence():
    """泛题材观看经历可由播放样本的类型字段回溯时应保留。"""
    candidate = Candidate(
        candidate_id="tmdb:1",
        title="新科幻片",
        media_type="movie",
        overview="未来城市中的犯罪追查故事。",
        genres=["科幻", "犯罪"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [
                {
                    "candidate_id": "tmdb:1",
                    "reason": "你看过多部科幻片，这部科幻犯罪延续未来设定。",
                    "summary": "未来城市犯罪追查",
                    "match_tags": ["科幻", "犯罪"],
                    "confidence": 82,
                }
            ]
        )
    )
    result = RecommendationValidator().validate(
        parsed,
        [candidate],
        set(),
        set(),
        preference_evidence=["科幻"],
        playback_samples=[{"title": "真实科幻片", "genres": ["科幻"]}],
    )
    assert result.dropped == []


def test_validator_requires_named_candidate_personnel_in_frozen_evidence():
    """理由中的演员与导演姓名必须存在于冻结候选字段。"""
    candidate = Candidate(
        candidate_id="tmdb:1",
        title="华语动作喜剧",
        media_type="movie",
        overview="动作与喜剧交织的城市故事。",
        genres=["动作", "喜剧"],
        actors=["成龙"],
        directors=["冯小刚"],
    )

    def validate_reason(reason):
        """用同一候选校验一条主创理由。"""
        parsed = AgentOutputParser().parse(
            _output(
                [
                    {
                        "candidate_id": "tmdb:1",
                        "reason": reason,
                        "summary": "动作喜剧交织的城市故事",
                        "match_tags": ["动作", "喜剧"],
                        "confidence": 82,
                    }
                ]
            )
        )
        return RecommendationValidator().validate(
            parsed,
            [candidate],
            set(),
            set(),
            preference_evidence=["动作喜剧"],
        )

    accepted = validate_reason("冯小刚执导成龙主演的动作喜剧故事很对味")
    assert accepted.dropped == []

    foreign_name = Candidate(
        candidate_id="tmdb:1",
        title="人物传记",
        media_type="movie",
        overview="围绕演员生涯展开的人物故事。",
        genres=["剧情", "传记"],
        actors=["爱德华诺顿"],
        directors=["冯小刚"],
    )
    parsed = AgentOutputParser().parse(
        _output(
            [
                {
                    "candidate_id": "tmdb:1",
                    "reason": "冯小刚执导爱德华诺顿主演的人物传记故事",
                    "summary": "演员生涯人物故事",
                    "match_tags": ["剧情", "传记"],
                    "confidence": 82,
                }
            ]
        )
    )
    foreign_result = RecommendationValidator().validate(
        parsed,
        [foreign_name],
        set(),
        set(),
        preference_evidence=["剧情", "传记"],
    )
    assert foreign_result.dropped == []

    rejected = validate_reason("张三执导成龙主演的动作喜剧故事很对味")
    assert rejected.accepted == []
    assert rejected.dropped[0].reason == "invalid_reason"


def test_subscribed_candidate_remains_eligible_when_other_fields_are_valid():
    """已订阅但未观看候选不再作为排序硬排除项。"""
    parsed = AgentOutputParser().parse(_output())
    result = RecommendationValidator().validate(
        parsed, _candidates(), set(), {"tmdb:1"}
    )
    assert [item.candidate_id for item in result.accepted] == ["tmdb:1"]
    assert result.dropped == []


def test_fallback_summary_is_deterministic_readable_and_complete():
    """每种媒体类型都应获得三十字内、语义完整的稳定简介。"""
    expected = {
        "movie": "光影故事铺展人物命运的新篇章。",
        "tv": "连环剧情逐步揭开人物命运的新篇章。",
        "anime": "动画世界展开一段青春奇幻冒险。",
        "unknown": "故事生动呈现人物命运的新篇章。",
    }
    for media_type, summary in expected.items():
        candidate = Candidate(candidate_id=f"x:{media_type}", title="Title", media_type=media_type)
        assert fallback_summary(candidate) == summary
        assert len(summary) <= 30
        assert summary.endswith("。")


@pytest.mark.parametrize(
    "copy",
    (
        "密室旧案牵出尘封真相。",
        "A detective reopens a case.",
        "失踪事件の真相を追う物語。",
        "실종 사건의 진실을 쫓는 이야기.",
        "悬疑迷局层层牵出尘封往事与真相",
    ),
)
def test_semantic_copy_accepts_complete_multilingual_short_sentences(copy):
    """中文与多语言完整短句在三十字内均应原样保留。"""
    assert len(copy) <= 30
    assert is_complete_recommendation_copy(copy) is True


@pytest.mark.parametrize(
    "copy",
    (
        "侦探追查旧案并",
        "A detective story with",
        "一名演员面对事业低谷并且",
        "甲" * 30,
        "尚未说完的故事……",
    ),
)
def test_semantic_copy_rejects_obvious_fragments_without_truncating(copy):
    """连接词、英文虚词、边界碰撞和省略残句必须整条拒绝。"""
    assert is_complete_recommendation_copy(copy) is False


def test_semantic_copy_handles_exact_limit_and_pair_order_boundaries():
    """恰好三十字须有终止标点，闭合标点还必须保持正确顺序。"""
    quoted = "“" + "甲" * 27 + "。”"
    assert len(quoted) == 30
    assert is_complete_recommendation_copy(quoted) is True
    assert is_complete_recommendation_copy("》顺序错误《") is False


def test_fallback_copy_templates_are_complete_and_never_include_long_titles():
    """长标题不会被截进保底文案，理由与简介均由完整模板重述。"""
    candidate = Candidate(
        candidate_id="tmdb:long-title",
        title="这是一个远远超过三十个字符且不应该被截断进模板的多语言Title",
        media_type="tv",
        overview="一名调查员追踪旧案并",
        genres=["悬疑"],
    )
    summary = fallback_summary(candidate)
    reason = fallback_reason(["悬疑", "剧集"])

    assert candidate.title not in summary
    assert candidate.title not in reason
    assert "画像检索" not in reason
    assert "剧集" in reason
    assert is_complete_recommendation_copy(summary) is True
    assert is_complete_recommendation_copy(reason) is True


def test_fallback_reason_never_projects_profile_tag_onto_candidate():
    """保底理由只描述候选事实，不把首个画像标签冒充作品属性。"""
    reason = fallback_reason(["中国动画", "真人剧情"])

    assert "中国动画" not in reason
    assert "真人剧情" in reason


def test_recommendation_copy_validation_and_templates_never_slice_text():
    """推荐文案校验与模板函数不得用字符串切片伪造三十字总结。"""
    tree = ast.parse((PLUGIN_DIR / "service" / "validation.py").read_text(encoding="utf-8"))
    targets = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in {
            "is_complete_recommendation_copy",
            "fallback_summary",
            "fallback_reason",
        }
    }
    assert set(targets) == {
        "is_complete_recommendation_copy",
        "fallback_summary",
        "fallback_reason",
    }
    for function in targets.values():
        assert not any(
            isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice)
            for node in ast.walk(function)
        )
