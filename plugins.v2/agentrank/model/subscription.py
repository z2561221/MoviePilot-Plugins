"""订阅画像输入领域对象。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SubscriptionSample:
    """表示一条已规范化的用户订阅画像样本。"""

    stable_id: str
    title: str
    media_type: str
    year: Optional[int] = None
    ids: Dict[str, str] = field(default_factory=dict)
    genres: List[str] = field(default_factory=list)
    actors: List[str] = field(default_factory=list)
    directors: List[str] = field(default_factory=list)
    regions: List[str] = field(default_factory=list)
    rating: Optional[float] = None
    subscribed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """返回 Agent 工具可读取的纯字典。"""
        return asdict(self)


@dataclass
class ProfileInputResult:
    """表示画像输入收集结果及显式不足状态。"""

    username: str
    status: str
    samples: List[SubscriptionSample] = field(default_factory=list)
    minimum_samples: int = 0
    rejected_count: int = 0

    @property
    def sample_count(self) -> int:
        """返回当前有效样本数量。"""
        return len(self.samples)

    def to_dict(self) -> Dict[str, Any]:
        """返回服务与 Agent 工具之间的稳定字典契约。"""
        return {
            "username": self.username,
            "status": self.status,
            "samples": [sample.to_dict() for sample in self.samples],
            "sample_count": self.sample_count,
            "minimum_samples": self.minimum_samples,
            "rejected_count": self.rejected_count,
        }
