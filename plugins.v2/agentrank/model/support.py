"""AgentRank 可精确重算的确定性支持度领域对象。"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Tuple

from .policy import POLICY_WEIGHT_NAMES


SUPPORT_SCHEMA_VERSION = 1
SUPPORT_UNIT_SCALE = 10_000
SUPPORT_DIRECTIONS = frozenset({"positive", "counter"})


def _text(value: Any) -> str:
    """把可选标量规范为去除首尾空白的文本。"""
    return str(value or "").strip()


def _unique_texts(values: Iterable[Any]) -> Tuple[str, ...]:
    """返回保持顺序的唯一非空证据引用。"""
    result = []
    for value in values or ():
        text = _text(value)
        if text and text not in result:
            result.append(text)
    return tuple(result)


def _round_div(numerator: int, denominator: int) -> int:
    """用整数半入规则完成非负除法，避免浮点重放漂移。"""
    if numerator < 0 or denominator <= 0:
        raise ValueError("support integer division input is invalid")
    return (int(numerator) + int(denominator) // 2) // int(denominator)


@dataclass(frozen=True)
class SupportContribution:
    """保存一项已由受信数据验证的正向或反向加权贡献。"""

    dimension: str
    direction: str
    user_value: str
    candidate_value: str
    user_refs: Tuple[str, ...]
    candidate_ref: str
    weight_units: int
    certainty_units: int
    contribution_units: int
    schema_version: int = SUPPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范字段并验证贡献可由权重与证据确定性精确重算。"""
        for field_name in (
            "dimension",
            "direction",
            "user_value",
            "candidate_value",
            "candidate_ref",
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name)))
        object.__setattr__(self, "user_refs", _unique_texts(self.user_refs))
        for field_name in (
            "weight_units",
            "certainty_units",
            "contribution_units",
            "schema_version",
        ):
            object.__setattr__(self, field_name, int(getattr(self, field_name)))
        if self.dimension not in POLICY_WEIGHT_NAMES:
            raise ValueError("support contribution dimension is invalid")
        if self.direction not in SUPPORT_DIRECTIONS:
            raise ValueError("support contribution direction is invalid")
        if not self.user_value or not self.candidate_value:
            raise ValueError("support contribution values are incomplete")
        if not self.user_refs or not self.candidate_ref:
            raise ValueError("support contribution evidence is incomplete")
        if not 0 <= self.weight_units <= SUPPORT_UNIT_SCALE:
            raise ValueError("support contribution weight is out of range")
        if not 0 <= self.certainty_units <= SUPPORT_UNIT_SCALE:
            raise ValueError("support contribution certainty is out of range")
        expected = _round_div(
            self.weight_units * self.certainty_units,
            SUPPORT_UNIT_SCALE,
        )
        if self.contribution_units != expected or expected <= 0:
            raise ValueError("support contribution is not reproducible")
        if self.schema_version != SUPPORT_SCHEMA_VERSION:
            raise ValueError("support contribution schema is unsupported")

    @property
    def identity(self) -> Tuple[Any, ...]:
        """返回可用于确定性去重和排序的贡献身份。"""
        return (
            self.dimension,
            self.direction,
            self.user_refs,
            self.candidate_ref,
            self.user_value.casefold(),
            self.candidate_value.casefold(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化的整数贡献字典。"""
        return {
            "dimension": self.dimension,
            "direction": self.direction,
            "user_value": self.user_value,
            "candidate_value": self.candidate_value,
            "user_refs": list(self.user_refs),
            "candidate_ref": self.candidate_ref,
            "weight_units": self.weight_units,
            "certainty_units": self.certainty_units,
            "contribution_units": self.contribution_units,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SupportContribution":
        """从持久化字典恢复并严格校验一项支持度贡献。"""
        if not isinstance(value, Mapping):
            raise ValueError("support contribution must be a mapping")
        return cls(
            dimension=value.get("dimension"),
            direction=value.get("direction"),
            user_value=value.get("user_value"),
            candidate_value=value.get("candidate_value"),
            user_refs=tuple(value.get("user_refs") or ()),
            candidate_ref=value.get("candidate_ref"),
            weight_units=value.get("weight_units") or 0,
            certainty_units=value.get("certainty_units") or 0,
            contribution_units=value.get("contribution_units") or 0,
            schema_version=value.get("schema_version") or 0,
        )


@dataclass(frozen=True)
class SupportScore:
    """保存由贡献项零误差重算的策略支持度与净分。"""

    policy_version: str
    contributions: Tuple[SupportContribution, ...]
    positive_units: int
    counter_units: int
    available_units: int
    net_units: int
    percentage: int
    schema_version: int = SUPPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """排序贡献并验证汇总值和百分比均与明细完全一致。"""
        object.__setattr__(self, "policy_version", _text(self.policy_version))
        normalized = tuple(
            item
            if isinstance(item, SupportContribution)
            else SupportContribution.from_dict(item)
            for item in self.contributions or ()
        )
        normalized = tuple(sorted(normalized, key=lambda item: item.identity))
        if len({item.identity for item in normalized}) != len(normalized):
            raise ValueError("support score contains duplicate contributions")
        object.__setattr__(self, "contributions", normalized)
        for field_name in (
            "positive_units",
            "counter_units",
            "available_units",
            "net_units",
            "percentage",
            "schema_version",
        ):
            object.__setattr__(self, field_name, int(getattr(self, field_name)))
        if not self.policy_version:
            raise ValueError("support score policy_version is required")
        positive = sum(
            item.contribution_units
            for item in normalized
            if item.direction == "positive"
        )
        counter = sum(
            item.contribution_units
            for item in normalized
            if item.direction == "counter"
        )
        available = positive + counter
        net = positive - counter
        percentage = (
            min(100, _round_div(max(0, net) * 100, available))
            if available
            else 0
        )
        if (
            self.positive_units != positive
            or self.counter_units != counter
            or self.available_units != available
            or self.net_units != net
            or self.percentage != percentage
        ):
            raise ValueError("support score totals are not reproducible")
        if self.schema_version != SUPPORT_SCHEMA_VERSION:
            raise ValueError("support score schema is unsupported")

    @classmethod
    def from_contributions(
        cls,
        policy_version: str,
        contributions: Iterable[SupportContribution],
    ) -> "SupportScore":
        """根据唯一贡献项生成全部整数汇总字段。"""
        unique = {}
        for item in contributions or ():
            if not isinstance(item, SupportContribution):
                raise TypeError("contributions must contain SupportContribution")
            unique[item.identity] = item
        values = tuple(sorted(unique.values(), key=lambda item: item.identity))
        positive = sum(
            item.contribution_units
            for item in values
            if item.direction == "positive"
        )
        counter = sum(
            item.contribution_units
            for item in values
            if item.direction == "counter"
        )
        available = positive + counter
        net = positive - counter
        percentage = (
            min(100, _round_div(max(0, net) * 100, available))
            if available
            else 0
        )
        return cls(
            policy_version=policy_version,
            contributions=values,
            positive_units=positive,
            counter_units=counter,
            available_units=available,
            net_units=net,
            percentage=percentage,
        )

    @property
    def evidence_count(self) -> int:
        """返回正反贡献引用的唯一受信证据数量。"""
        return len(
            {
                ref
                for item in self.contributions
                for ref in (*item.user_refs, item.candidate_ref)
            }
        )

    @property
    def positive_dimensions(self) -> Tuple[str, ...]:
        """返回支持度中独立正向证据维度。"""
        return tuple(
            sorted(
                {
                    item.dimension
                    for item in self.contributions
                    if item.direction == "positive"
                }
            )
        )

    @property
    def counter_dimensions(self) -> Tuple[str, ...]:
        """返回支持度中独立反向证据维度。"""
        return tuple(
            sorted(
                {
                    item.dimension
                    for item in self.contributions
                    if item.direction == "counter"
                }
            )
        )

    @property
    def evidence_dimension_count(self) -> int:
        """返回正反证据涉及的独立维度数。"""
        return len(set(self.positive_dimensions) | set(self.counter_dimensions))

    @property
    def counter_evidence_count(self) -> int:
        """返回反向贡献数量，用于解释主要反证。"""
        return sum(item.direction == "counter" for item in self.contributions)

    @property
    def confidence_level(self) -> str:
        """按证据维度而非百分比投影高/中/探索置信度。"""
        if len(self.positive_dimensions) >= 2 and not self.counter_dimensions:
            return "high"
        if self.positive_dimensions:
            return "medium"
        return "exploration"

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化且可独立重算的支持度字典。"""
        return {
            "policy_version": self.policy_version,
            "contributions": [item.to_dict() for item in self.contributions],
            "positive_units": self.positive_units,
            "counter_units": self.counter_units,
            "available_units": self.available_units,
            "net_units": self.net_units,
            "percentage": self.percentage,
            "evidence_count": self.evidence_count,
            "positive_dimensions": list(self.positive_dimensions),
            "counter_dimensions": list(self.counter_dimensions),
            "evidence_dimension_count": self.evidence_dimension_count,
            "counter_evidence_count": self.counter_evidence_count,
            "confidence_level": self.confidence_level,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SupportScore":
        """从持久化字典恢复并重算验证确定性支持度。"""
        if not isinstance(value, Mapping):
            raise ValueError("support score must be a mapping")
        return cls(
            policy_version=value.get("policy_version"),
            contributions=tuple(
                SupportContribution.from_dict(item)
                for item in value.get("contributions") or ()
            ),
            positive_units=value.get("positive_units") or 0,
            counter_units=value.get("counter_units") or 0,
            available_units=value.get("available_units") or 0,
            net_units=(
                value.get("net_units")
                if value.get("net_units") is not None
                else 0
            ),
            percentage=value.get("percentage") or 0,
            schema_version=value.get("schema_version") or 0,
        )
