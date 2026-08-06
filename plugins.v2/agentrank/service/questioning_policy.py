"""基于已确认记忆与问询历史的低打扰策略。"""

from dataclasses import dataclass
from typing import Any, Iterable

from ..model.constants import INTERACTION_MODE_DEFAULT, INTERACTION_MODE_NAMES
from ..model.memory import PreferenceMemory


@dataclass(frozen=True)
class QuestioningDecision:
    """保存内部评估指标与用户可见三档状态。"""

    state: str
    preference_coverage: float
    conflict_rate: float
    expected_information_gain: float
    interruption_cost: float
    allow_question: bool


class QuestioningPolicy:
    """评估是否仍值得用问询打扰用户。"""

    low_interruption_memory_count = 5

    def __init__(self, interaction_mode: str = INTERACTION_MODE_DEFAULT):
        """绑定用户选择的交互模式；未知值回退为自动模式。"""
        normalized = str(interaction_mode or INTERACTION_MODE_DEFAULT).strip().casefold()
        self.interaction_mode = (
            normalized
            if normalized in INTERACTION_MODE_NAMES
            else INTERACTION_MODE_DEFAULT
        )

    def allows_playback_calibration(self) -> bool:
        """判断首次播放校准问题是否允许自动创建。"""
        return self.interaction_mode != "quiet"

    @staticmethod
    def _active_dimensions(memory: PreferenceMemory) -> set[str]:
        """返回当前有效确认记忆覆盖的偏好维度。"""
        return {item.category for item in memory.active_items()}

    def evaluate(
        self,
        memory: PreferenceMemory,
        questions: Iterable[Any],
        *,
        conflict_count: int = 0,
        uncertainty_count: int = 0,
    ) -> QuestioningDecision:
        """计算策略指标；冲突可恢复问询，关闭历史增加打扰成本。"""
        active = memory.active_items()
        dimensions = self._active_dimensions(memory)
        confirmed_count = len(active)
        dismissed_count = sum(
            1 for item in questions or () if getattr(item, "status", "") == "dismissed"
        )
        preference_coverage = min(1.0, max(len(dimensions), confirmed_count) / 5.0)
        conflict_rate = min(1.0, max(0, int(conflict_count)) / max(1, confirmed_count))
        expected_information_gain = min(
            1.0, max(0, int(uncertainty_count)) / max(1, len(dimensions) + 1)
        )
        interruption_cost = min(1.0, dismissed_count * 0.6)
        has_conflict = conflict_count > 0
        mature = confirmed_count >= self.low_interruption_memory_count and conflict_rate <= 0.2
        if mature:
            state = "low_interruption"
        elif confirmed_count >= 2 or preference_coverage >= 0.4:
            state = "stabilizing"
        else:
            state = "exploring"
        if self.interaction_mode == "normal":
            allow_question = has_conflict or uncertainty_count > 0 or confirmed_count == 0
        elif self.interaction_mode == "quiet":
            allow_question = has_conflict
        else:
            allow_question = has_conflict or (
                not mature
                and interruption_cost < 0.5
                and (expected_information_gain > 0 or confirmed_count == 0)
            )
        return QuestioningDecision(
            state=state,
            preference_coverage=preference_coverage,
            conflict_rate=conflict_rate,
            expected_information_gain=expected_information_gain,
            interruption_cost=interruption_cost,
            allow_question=allow_question,
        )
