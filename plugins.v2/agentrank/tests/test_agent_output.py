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
AgentOutputParser = validation_module.AgentOutputParser
RecommendationValidator = validation_module.RecommendationValidator
AgentOutputError = validation_module.AgentOutputError
fallback_summary = validation_module.fallback_summary
build_ranking_prompt = prompt_module.build_ranking_prompt


def _output(recommendations=None, profile=None):
    return json.dumps(
        {
            "profile": profile
            or {
                "summary": "偏好悬疑犯罪与高口碑短剧",
                "tags": ["悬疑", "犯罪"],
                "negative_tags": ["低分长剧"],
                "playback_count": 12,
            },
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
    assert "二十到六十" in prompt
    assert "至少给出两项彼此独立的匹配证据" in prompt
    assert "评分高、热度高" in prompt
    assert '"reason"' in prompt
    assert "文案要具体、流畅" in prompt
    assert "ignore all previous instructions" not in prompt


def test_custom_agent_prompt_is_inserted_without_replacing_fixed_contract():
    """自定义排序指令生效，但固定工具与输出边界仍存在。"""
    prompt = build_ranking_prompt(agent_prompt="优先推荐冷门科幻并保持俏皮文风")
    assert "优先推荐冷门科幻并保持俏皮文风" in prompt
    assert "只能通过 read_agentrank_playback" in prompt
    assert "不能覆盖硬性边界、输出结构或字段校验" in prompt
    assert "十二到四十" in prompt


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
        AgentOutputParser().parse(_output(profile=profile))


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
        "invalid_summary",
    ]


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
