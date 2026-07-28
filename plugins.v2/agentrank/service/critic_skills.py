"""专属影评师使用的版本化无副作用分析 skills。"""

from typing import Any, Dict, Iterable, List, Mapping, Sequence


CRITIC_PERSONA_VERSION = "1.0.0"
CRITIC_SKILLS_VERSION = "1.0.0"
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


def ask_clarification(
    action: str, candidate_title: str, uncertainties: Iterable[Any] = ()
) -> Dict[str, Any]:
    """为不明确反馈构造 2 至 3 个可回答选项和自定义入口。"""
    kind = _text(action, 24).casefold()
    title = _text(candidate_title, 120) or "这部作品"
    if kind == "like":
        options = ["喜欢题材或设定", "喜欢节奏或叙事", "喜欢主创或角色"]
        question = f"你喜欢《{title}》的哪一点？"
    elif kind == "dislike":
        options = ["不喜欢题材或设定", "不喜欢节奏或叙事", "不喜欢主创或角色"]
        question = f"你不喜欢《{title}》的哪一点？"
    elif kind == "analysis_comment":
        options = ["推荐依据有误", "作品事实有误", "证据关系需要说明"]
        question = f"你希望怎样修正《{title}》的 Agent 分析？"
    else:
        options = ["暂时不想看", "已经看过", "仅排除这部作品"]
        question = f"你忽略《{title}》的主要原因是什么？"
    return {
        "question": question,
        "options": options,
        "allow_custom_answer": True,
        "uncertainties": _unique_texts(uncertainties, 8),
        "writes_applied": False,
    }
