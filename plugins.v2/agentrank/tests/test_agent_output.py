"""AgentRank prompt, strict JSON parser, and deterministic validator tests."""

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_output_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
prompt_module = importlib.import_module(f"{PACKAGE_NAME}.service.prompt")
validation_module = importlib.import_module(f"{PACKAGE_NAME}.service.validation")

Candidate = candidate_module.Candidate
ProfileOutputParser = validation_module.ProfileOutputParser
RankingOutputParser = validation_module.RankingOutputParser
AgentOutputParser = RankingOutputParser
RecommendationValidator = validation_module.RecommendationValidator
AgentOutputError = validation_module.AgentOutputError
fallback_summary = validation_module.fallback_summary
build_ranking_prompt = prompt_module.build_ranking_prompt
build_profile_prompt = prompt_module.build_profile_prompt


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
            "filters": filters
            or {
                "media_types": ["movie"],
                "genre_ids": [80],
                "keyword_ids": [],
                "original_languages": ["zh"],
                "year_min": 2000,
                "year_max": 2026,
                "rating_min": 7.0,
                "vote_count_min": 100,
                "sort_by": "popularity.desc",
            },
            "ranking_tags": ranking_tags or ["高质量悬疑"],
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
    assert "最多四十" in prompt
    assert "两个 match_tags" in prompt
    assert "评分高、热度高" in prompt
    assert '"reason"' in prompt
    assert "文案要具体、流畅" in prompt
    assert "最多 8 条" in prompt
    assert "最终仍只保存五条" in prompt
    assert "ignore all previous instructions" not in prompt


def test_profile_prompt_declares_retrieval_plan_schema_and_id_boundary():
    """画像提示明确区分结构化过滤与自由排序语义。"""
    prompt = build_profile_prompt()

    assert "只能调用 read_agentrank_playback" in prompt
    assert '"filters"' in prompt
    assert '"ranking_tags"' in prompt
    assert '"genre_ids"' in prompt
    assert '"keyword_ids"' in prompt
    assert "不得猜测" in prompt
    assert "overview" in prompt
    assert "genres" in prompt
    assert "不要仅凭片名猜测题材" in prompt


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


def test_custom_agent_prompt_is_inserted_without_replacing_fixed_contract():
    """自定义排序指令生效，但固定工具与输出边界仍存在。"""
    prompt = build_ranking_prompt(agent_prompt="优先推荐冷门科幻并保持俏皮文风")
    assert "优先推荐冷门科幻并保持俏皮文风" in prompt
    assert "只能通过 read_agentrank_playback" in prompt
    assert "不能覆盖硬性边界、输出结构或字段校验" in prompt
    assert "最多二十" in prompt
    assert "每个 match_tags 标签最多五个字符" in prompt


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
    assert len(result.accepted[0].summary) <= 20


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


def test_profile_and_ranking_parsers_reject_each_others_schema():
    """两个 Agent parser 不接受对方的根字段。"""
    with pytest.raises(AgentOutputError):
        ProfileOutputParser().parse(_output())
    with pytest.raises(AgentOutputError):
        RankingOutputParser().parse(_profile_output())


def test_profile_parser_accepts_only_trusted_keyword_ids_and_typed_ranges():
    """结构化过滤允许可信 ID，但不接受 Agent 自造关键词。"""
    parsed = ProfileOutputParser(allowed_keyword_ids={123}).parse(
        _profile_output(
            filters={
                "media_types": ["movie", "tv"],
                "genre_ids": [18, 9648],
                "keyword_ids": [123],
                "original_languages": ["en", "zh"],
                "year_min": 1990,
                "year_max": 2026,
                "rating_min": 7.5,
                "vote_count_min": 50,
                "sort_by": "vote_average.desc",
            },
            ranking_tags=["冷峻悬疑"],
        )
    )

    assert parsed.profile.playback_count == 12
    assert parsed.filters.keyword_ids == (123,)
    assert parsed.filters.sort_by == "vote_average.desc"
    assert parsed.ranking_tags == ["冷峻悬疑"]


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


@pytest.mark.parametrize(
    "filters",
    [
        {"media_types": ["documentary"]},
        {"genre_ids": [999999]},
        {"keyword_ids": [123]},
        {"original_languages": ["xx"]},
        {"year_min": 1869},
        {"year_min": 2027, "year_max": 2026},
        {"rating_min": 10.1},
        {"vote_count_min": -1},
        {"sort_by": "unknown.desc"},
        {"free_text": "悬疑"},
    ],
)
def test_profile_parser_rejects_unknown_enums_ids_ranges_and_extra_filter_fields(filters):
    """越界、未知枚举、未知 ID 和自由语义不得进入 filters。"""
    base = {
        "media_types": [],
        "genre_ids": [],
        "keyword_ids": [],
        "original_languages": [],
        "year_min": None,
        "year_max": None,
        "rating_min": None,
        "vote_count_min": None,
        "sort_by": "popularity.desc",
    }
    base.update(filters)
    with pytest.raises(AgentOutputError):
        ProfileOutputParser().parse(_profile_output(filters=base))


def test_profile_parser_rejects_extra_root_fields_and_duplicate_free_tags():
    """根对象额外字段与重复自由标签均被拒绝。"""
    payload = json.loads(_profile_output())
    payload["unexpected"] = True
    with pytest.raises(AgentOutputError):
        ProfileOutputParser().parse(json.dumps(payload, ensure_ascii=False))

    with pytest.raises(AgentOutputError):
        ProfileOutputParser().parse(
            _profile_output(ranking_tags=["悬疑", "悬疑"])
        )


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


def test_validator_builds_five_unique_grounded_fallback_items_in_frozen_order():
    """安全保底按冻结顺序补齐五条，并只引用画像与候选事实。"""
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

    fallback = RecommendationValidator().build_fallback_items(
        candidates,
        accepted=[],
        blocked_candidate_ids={"tmdb:2"},
        preference_evidence=["偏好悬疑犯罪作品"],
        limit=5,
    )

    assert [item.candidate_id for item in fallback] == [
        "tmdb:1",
        "tmdb:3",
        "tmdb:4",
        "tmdb:5",
        "tmdb:6",
    ]
    assert [item.rank for item in fallback] == [1, 2, 3, 4, 5]
    assert all(item.confidence == 60 for item in fallback)
    assert all("安全" in item.reason or "保底" in item.reason for item in fallback)
    assert all(item.summary for item in fallback)


def test_validator_trims_overlong_copy_and_tags_without_dropping_candidate():
    """展示字数超限会被安全裁剪，不得触发补榜或丢弃作品。"""
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
                "reason": "你有悬疑片偏好，这部旧案调查故事围绕小镇秘密展开，人物关系也会逐步揭开。",
                "summary": "一名侦探追查多年未解旧案，并在封闭小镇逐步发现一个家族隐藏已久的秘密。",
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

    assert result.dropped == []
    assert len(result.accepted) == 1
    assert len(result.accepted[0].reason) <= 40
    assert not result.accepted[0].reason.endswith(("，", "、", "；", "："))
    assert len(result.accepted[0].summary) <= 20
    assert result.accepted[0].match_tags == ["悬疑片", "旧案调查故"]
    assert all(len(tag) <= 5 for tag in result.accepted[0].match_tags)


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
                    "reason": "你偏爱人物剧情与长期成长线，这部用群像关系和连续冲突提供相近体验。",
                    "summary": "连环剧情逐步揭开人物命运新篇章",
                    "match_tags": ["人物剧情", "群像关系"],
                    "confidence": 70,
                },
                {
                    "candidate_id": "tmdb:1",
                    "reason": "你常订阅悬疑犯罪题材，这部用密室追凶与双线叙事延续该口味。",
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


def test_subscribed_candidate_is_rejected_even_when_other_fields_are_valid():
    """Current subscription membership is a hard validation gate."""
    parsed = AgentOutputParser().parse(_output())
    result = RecommendationValidator().validate(
        parsed, _candidates(), set(), {"tmdb:1"}
    )
    assert result.accepted == []
    assert result.dropped[0].reason == "subscribed_candidate"


def test_fallback_summary_is_deterministic_readable_and_exactly_fifteen_chinese_chars():
    """Every media type gets a stable fifteen-Han-character description fallback."""
    expected = {
        "movie": "光影故事缓缓铺展人物命运新篇章",
        "tv": "连环剧情逐步揭开人物命运新篇章",
        "anime": "动画世界热烈展开青春奇幻冒险路",
        "unknown": "精彩故事生动呈现人物命运新篇章",
    }
    for media_type, summary in expected.items():
        candidate = Candidate(candidate_id=f"x:{media_type}", title="Title", media_type=media_type)
        assert fallback_summary(candidate) == summary
        assert len(summary) == 15
        assert all("\u4e00" <= char <= "\u9fff" for char in summary)
