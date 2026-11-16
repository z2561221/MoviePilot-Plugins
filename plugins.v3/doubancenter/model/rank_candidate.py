"""榜单候选的内存视图；持久化快照继续使用原字典格式。"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RankCandidate:
    raw: dict = field(default_factory=dict)
    entry: dict = field(default_factory=dict)
    mediainfo: Any = None
    meta: Any = None
    media_type: str = ""
    resolver: Callable[[], tuple[Any, Any, str]] | None = None

    @classmethod
    def from_snapshot(cls, snapshot):
        if isinstance(snapshot, cls):
            return snapshot
        if not isinstance(snapshot, dict):
            return None
        return cls(
            raw=snapshot.get("raw") if isinstance(snapshot.get("raw"), dict) else {},
            entry=snapshot.get("entry") if isinstance(snapshot.get("entry"), dict) else {},
            mediainfo=snapshot.get("mediainfo"),
        )

    def resolve(self):
        """传统入口延迟识别，保持历史/黑名单筛选先于外部识别。"""
        if self.resolver is not None:
            self.meta, self.mediainfo, self.media_type = self.resolver()
            self.resolver = None
        return self.mediainfo
