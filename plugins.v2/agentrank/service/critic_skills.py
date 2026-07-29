"""CinePilot Agent 使用的版本化无副作用分析 skills。"""

from typing import Any, Dict, Iterable, List, Mapping, Sequence


CRITIC_PERSONA_VERSION = "1.0.0"
CRITIC_SKILLS_VERSION = "1.1.0"
CRITIC_SKILL_NAMES = (
    "summarize_evidence",
    "understand_feedback",
    "compare_conflicts",
    "propose_memory_change",
    "explain_recommendation",
    "ask_clarification",
)


def _text(value: Any, limit: int = 240) -> str:
    """把不可信标量规范为有界文本。"""
    return str(value or "").strip()[: max(1, int(limit))]


def _unique_texts(values: Iterable[Any], limit: int = 24) -> List[str]:
    """返回保持顺序的有界唯一文本列表。"""
    result: List[str] = []
    for value in values or ():
        text = _text(value)
        if text and text not in result:
            result.append(text)
        if len(result) >= max(1, int(limit)):
            break
    return result


def critic_skill_manifest() -> Dict[str, Any]:
    """返回固定人设和六个只读 skill 的版本清单。"""
    return {
        "persona_version": CRITIC_PERSONA_VERSION,
        "skills_version": CRITIC_SKILLS_VERSION,
        "skills": list(CRITIC_SKILL_NAMES),
        "side_effects": False,
        "writes_memory": False,
        "writes_configuration": False,
        "calls_external_tools": False,
    }


def summarize_evidence(
    feedback_event: Mapping[str, Any],
    candidate: Mapping[str, Any],
    confirmed_memory: Mapping[str, Any],
) -> Dict[str, Any]:
    """把事件、作品事实和已确认记忆投影为最小证据摘要。"""
    event = dict(feedback_event or {})
    media = dict(candidate or {})
    memory = dict(confirmed_memory or {})
    active_memory = []
    for item in memory.get("items") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("status") or "") != "active" or bool(
            item.get("tombstone")
        ):
            continue
        active_memory.append(
            {
                "item_id": _text(item.get("item_id"), 128),
                "category": _text(item.get("category"), 64),
                "value": _text(item.get("value"), 120),
                "polarity": _text(item.get("polarity"), 16),
                "certainty": float(item.get("certainty") or 0.0),
            }
        )
    return {
        "event": {
            "event_id": _text(event.get("event_id"), 128),
            "sequence": max(0, int(event.get("sequence") or 0)),
            "kind": _text(event.get("kind"), 24),
            "candidate_id": _text(event.get("candidate_id"), 128),
            "comment": _text(event.get("comment"), 1000),
        },
        "candidate": {
            "candidate_id": _text(media.get("candidate_id"), 128),
            "title": _text(media.get("title"), 160),
            "media_type": _text(media.get("media_type"), 24),
            "year": media.get("year"),
            "overview": _text(media.get("overview"), 1000),
            "genres": _unique_texts(media.get("genres") or ()),
            "regions": _unique_texts(media.get("regions") or ()),
            "actors": _unique_texts(media.get("actors") or (), 12),
            "directors": _unique_texts(media.get("directors") or (), 8),
        },
        "confirmed_memory": {
            "memory_revision": max(0, int(memory.get("memory_revision") or 0)),
            "items": active_memory,
        },
    }


def understand_feedback(evidence: Mapping[str, Any]) -> Dict[str, Any]:
    """为反馈理解声明不可被 LLM 覆盖的动作语义边界。"""
    event = dict((evidence or {}).get("event") or {})
    kind = _text(event.get("kind"), 24).casefold()
    comment = _text(event.get("comment"), 1000)
    if kind == "ignore" and not comment:
        outcome = "exclusion_only"
    elif not comment:
        outcome = "ambiguous"
    else:
        outcome = "understood_or_ambiguous"
    return {
        "action": kind,
        "required_outcome": outcome,
        "may_propose_memory": bool(comment and kind in {"like", "dislike"}),
        "may_revise_analysis": bool(comment and kind == "analysis_comment"),
        "ignore_is_taste_signal": False,
        "uncommented_action_is_stable_preference": False,
    }


def compare_conflicts(
    signals: Sequence[Mapping[str, Any]],
    confirmed_memory: Mapping[str, Any],
) -> List[Dict[str, str]]:
    """确定性比较候选信号与已确认记忆，不修改任一输入。"""
    current = []
    for item in dict(confirmed_memory or {}).get("items") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("status") or "") != "active" or bool(
            item.get("tombstone")
        ):
            continue
        current.append(dict(item))
    result: List[Dict[str, str]] = []
    for signal in signals or ():
        if not isinstance(signal, Mapping):
            continue
        category = _text(signal.get("category"), 64).casefold()
        value = _text(signal.get("value"), 120).casefold()
        polarity = _text(signal.get("polarity"), 16).casefold()
        for item in current:
            if _text(item.get("category"), 64).casefold() != category:
                continue
            if _text(item.get("value"), 120).casefold() != value:
                continue
            if _text(item.get("polarity"), 16).casefold() == polarity:
                continue
            result.append(
                {
                    "memory_item_id": _text(item.get("item_id"), 128),
                    "category": category,
                    "value": value,
                    "reason": "与已确认偏好方向相反",
                }
            )
    return result


def propose_memory_change(understanding: Mapping[str, Any]) -> Dict[str, Any]:
    """把明确理解转换为待确认预览，不执行任何记忆写入。"""
    value = dict(understanding or {})
    outcome = _text(value.get("outcome"), 32)
    signals = [
        dict(item) for item in value.get("signals") or [] if isinstance(item, Mapping)
    ]
    return {
        "status": "pending_confirmation" if outcome == "understood" and signals else "not_proposed",
        "restatement": _text(value.get("restatement"), 240),
        "changes": signals if outcome == "understood" else [],
        "writes_applied": False,
    }


def explain_recommendation(
    candidate: Mapping[str, Any], evidence_refs: Iterable[Any]
) -> Dict[str, Any]:
    """构造可纠正的作品依据摘要，不生成隐藏推理过程。"""
    media = dict(candidate or {})
    return {
        "candidate_id": _text(media.get("candidate_id"), 128),
        "title": _text(media.get("title"), 160),
        "genres": _unique_texts(media.get("genres") or ()),
        "evidence_refs": _unique_texts(evidence_refs, 16),
        "contains_chain_of_thought": False,
    }


_PREFERENCE_QUESTION_CATALOG = (
    {
        "dimension": "selection_basis",
        "level": 0,
        "question": "平时挑选影视内容时，你通常最先看重什么？",
        "options": ("题材与设定", "叙事节奏", "人物关系", "情绪体验", "主创风格"),
        "keywords": (),
    },
    {
        "dimension": "viewing_goal",
        "level": 0,
        "question": "你最常希望一次观看带来什么体验？",
        "options": ("放松陪伴", "情绪冲击", "思考启发", "沉浸冒险", "轻松消遣"),
        "keywords": (),
    },
    {
        "dimension": "story_focus",
        "level": 1,
        "question": "在题材与设定之外，什么最容易让你继续看下去？",
        "options": ("世界观展开", "悬念推进", "现实议题", "创意概念"),
        "keywords": ("题材", "设定", "故事", "世界观"),
    },
    {
        "dimension": "pacing",
        "level": 1,
        "question": "你通常更偏好哪种整体叙事节奏？",
        "options": ("紧凑直接", "张弛有度", "舒缓细腻", "节奏不限但要连贯"),
        "keywords": ("节奏", "叙事"),
    },
    {
        "dimension": "character_focus",
        "level": 1,
        "question": "人物塑造中，哪种侧重点更吸引你？",
        "options": ("个人成长", "群像互动", "复杂关系", "鲜明角色魅力"),
        "keywords": ("人物", "角色", "关系"),
    },
    {
        "dimension": "emotion_tone",
        "level": 1,
        "question": "你通常更享受哪种观看情绪？",
        "options": ("温暖治愈", "轻松幽默", "紧张刺激", "克制深沉", "热血振奋"),
        "keywords": ("情绪", "体验", "氛围"),
    },
    {
        "dimension": "creator_style",
        "level": 1,
        "question": "主创因素会怎样影响你的选择？",
        "options": ("导演风格优先", "演员阵容优先", "编剧口碑优先", "通常不看主创"),
        "keywords": ("主创", "导演", "演员", "编剧"),
    },
    {
        "dimension": "novelty_balance",
        "level": 2,
        "question": "面对熟悉题材时，你更希望作品怎样变化？",
        "options": ("保留经典套路", "熟悉框架中有新意", "大胆颠覆类型", "取决于完成度"),
        "keywords": ("世界观", "悬念", "题材", "设定", "创意"),
    },
    {
        "dimension": "structure_preference",
        "level": 2,
        "question": "同样的故事，你更容易接受哪种讲述结构？",
        "options": ("线性清晰", "多线并行", "慢热铺陈", "非线性拼图"),
        "keywords": ("紧凑", "舒缓", "节奏", "叙事"),
    },
    {
        "dimension": "relationship_density",
        "level": 2,
        "question": "角色关系复杂时，你更看重哪一点？",
        "options": ("关系变化可信", "冲突足够强", "群像分配均衡", "主角线集中"),
        "keywords": ("人物", "角色", "群像", "关系"),
    },
    {
        "dimension": "emotional_intensity",
        "level": 2,
        "question": "作品情绪较强时，你更适应哪种表达方式？",
        "options": ("直接浓烈", "克制留白", "幽默缓冲", "强弱交替"),
        "keywords": ("温暖", "紧张", "深沉", "热血", "情绪"),
    },
)


def ask_clarification(
    action: str,
    candidate_title: str,
    uncertainties: Iterable[Any] = (),
    *,
    question_history: Iterable[Mapping[str, Any]] = (),
    confirmed_memory: Mapping[str, Any] = None,
) -> Dict[str, Any]:
    """按信息缺口从宽到细选择一个面向整体偏好的动态问题。"""
    del action, candidate_title
    history = [dict(item) for item in question_history or () if isinstance(item, Mapping)]
    asked_counts: Dict[str, int] = {}
    recent_dimensions: List[str] = []
    latest_answer = ""
    for item in history:
        dimension = _text(item.get("preference_dimension"), 48)
        if dimension:
            asked_counts[dimension] = asked_counts.get(dimension, 0) + 1
            recent_dimensions.append(dimension)
        if str(item.get("status") or "") == "answered":
            latest_answer = _text(item.get("answer_text"), 1000) or latest_answer
    active_memory = [
        dict(item)
        for item in dict(confirmed_memory or {}).get("items") or ()
        if isinstance(item, Mapping)
        and str(item.get("status") or "") == "active"
        and not bool(item.get("tombstone"))
    ]
    memory_values = " ".join(_text(item.get("value"), 120) for item in active_memory)
    ranked = []
    for index, template in enumerate(_PREFERENCE_QUESTION_CATALOG):
        dimension = str(template["dimension"])
        count = asked_counts.get(dimension, 0)
        keyword_match = sum(
            1 for keyword in template["keywords"] if keyword and keyword in latest_answer
        )
        memory_match = sum(
            1 for keyword in template["keywords"] if keyword and keyword in memory_values
        )
        score = 100.0 if count == 0 else -60.0 * count
        score += keyword_match * 35.0
        score -= memory_match * 5.0
        score -= float(template["level"]) * (8.0 if not history else 1.0)
        if dimension in recent_dimensions[-3:]:
            score -= 80.0
        if not history and template["level"] == 0:
            score += 40.0
        ranked.append((score, -index, template))
    selected = max(ranked, key=lambda item: (item[0], item[1]))[2]
    confidence_gap = max(0.2, min(1.0, 1.0 - 0.12 * len(active_memory)))
    return {
        "question": selected["question"],
        "options": list(selected["options"]),
        "allow_custom_answer": True,
        "uncertainties": _unique_texts(uncertainties, 8),
        "preference_dimension": selected["dimension"],
        "exploration_level": selected["level"],
        "confidence_gap": confidence_gap,
        "writes_applied": False,
    }


def style_clarification_question(question: str, persona_prompt: str = "") -> str:
    """按可编辑人设对问询做有界表达修饰，不改变问题语义或选项。"""
    text = _text(question, 220)
    persona = str(persona_prompt or "").strip().casefold()
    if not text or not persona:
        return text
    if any(token in persona for token in ("克里斯蒂娜", "未来道具研究所", "世界线")):
        return _text(f"唔……根据实验数据，{text}", 240)
    if any(token in persona for token in ("温柔", "耐心", "亲切")):
        return _text(f"想和你确认一下：{text}", 240)
    if any(token in persona for token in ("简洁", "直接", "克制")):
        return text
    return _text(f"想确认一下：{text}", 240)


def style_agent_message(message: str, persona_prompt: str = "") -> str:
    """按人设修饰简短处理结果，同时保持原始结论完整可见。"""
    text = _text(message, 220)
    persona = str(persona_prompt or "").strip().casefold()
    if not text or not persona:
        return text
    if any(token in persona for token in ("克里斯蒂娜", "未来道具研究所", "世界线")):
        prefix = "唔……" if any(token in text for token in ("失败", "拒绝", "风险")) else "知道啦，"
        return _text(f"{prefix}{text}", 240)
    if any(token in persona for token in ("温柔", "耐心", "亲切")):
        return _text(f"已为你处理：{text}", 240)
    return text
