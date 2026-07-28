"""根据确定性支持度生成用户可读的结构化推荐分析。"""

import hashlib
from datetime import datetime, timezone
from typing import Any, Iterable, List

from ..model.analysis import AnalysisEvidence, RecommendationAnalysis
from ..model.board import RecommendationItem
from ..model.policy import PolicySnapshot
from .critic_skills import CRITIC_PERSONA_VERSION, CRITIC_SKILLS_VERSION


class RecommendationAnalysisBuilder:
    """把已验证贡献投影为不含原始思维链的可纠正分析。"""

    def __init__(self, now_factory: Any = None) -> None:
        """注入可测试时钟。"""
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def prompt_fingerprint(ranking_prompt: str, copy_prompt: str) -> str:
        """返回不保存提示词正文的内容指纹。"""
        payload = f"{str(ranking_prompt or '')}\0{str(copy_prompt or '')}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _data_sources(evidence: Iterable[AnalysisEvidence]) -> List[str]:
        """把不透明证据引用映射为固定用户可读来源。"""
        sources: List[str] = ["policy_snapshot", "frozen_candidate"]
        refs = [ref for item in evidence for ref in item.user_refs]
        if any(ref.startswith("memory:") for ref in refs):
            sources.append("confirmed_memory")
        if any(ref.startswith("profile_preference:") for ref in refs):
            sources.append("manual_preference")
        if any(ref.startswith("playback:") for ref in refs):
            sources.append("playback_history")
        return sources

    def build(
        self,
        profile_id: str,
        run_id: str,
        item: RecommendationItem,
        policy: PolicySnapshot,
        prompt_fingerprint: str,
    ) -> RecommendationAnalysis:
        """为一条同策略推荐生成稳定身份和完整结构化分析。"""
        if item.support is None:
            raise ValueError("recommendation analysis requires deterministic support")
        if item.support.policy_version != policy.policy_version:
            raise ValueError("recommendation analysis policy version mismatch")
        if item.selection_source not in {"agent", "safe_fallback"}:
            raise ValueError("recommendation analysis selection source is invalid")
        evidence = [
            AnalysisEvidence.from_dict(contribution.to_dict())
            for contribution in item.support.contributions
        ]
        positive = [item for item in evidence if item.direction == "positive"]
        counter = [item for item in evidence if item.direction == "counter"]
        uncertainties = []
        if item.selection_source == "safe_fallback":
            uncertainties.append("该条目由同策略安全补位生成，并非排序Agent直接选择")
        if not positive:
            uncertainties.append("当前没有可验证的正向匹配贡献")
        identity = "\0".join(
            (
                str(profile_id),
                str(run_id),
                item.candidate_id,
                policy.policy_version,
                str(policy.memory_revision),
                item.selection_source,
            )
        )
        analysis_id = "analysis-" + hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:32]
        return RecommendationAnalysis(
            analysis_id=analysis_id,
            profile_id=profile_id,
            candidate_id=item.candidate_id,
            run_id=run_id,
            selection_source=item.selection_source,
            summary=item.summary,
            reason=item.reason,
            positive_evidence=positive,
            counter_evidence=counter,
            uncertainties=uncertainties,
            data_sources=self._data_sources(evidence),
            support_percentage=item.support.percentage,
            policy_version=policy.policy_version,
            memory_revision=policy.memory_revision,
            persona_version=CRITIC_PERSONA_VERSION,
            skills_version=CRITIC_SKILLS_VERSION,
            prompt_fingerprint=prompt_fingerprint,
            created_at=self._now_factory().astimezone(timezone.utc).isoformat(),
        )
