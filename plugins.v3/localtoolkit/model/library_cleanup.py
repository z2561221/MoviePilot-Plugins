"""清理库存条件模型与候选结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional


FAVORITE_LABELS = {
    "all": "收藏不限",
    "fav": "已收藏",
    "unfav": "未收藏",
}
PLAYED_LABELS = {
    "all": "观看不限",
    "played": "已看过",
    "unplayed": "未看过",
}


@dataclass(frozen=True)
class CleanupCondition:
    """清理库存的单组筛选条件。"""

    index: int
    favorite: str = "all"
    played: str = "all"
    days_threshold: int = 30

    @property
    def title(self) -> str:
        """返回条件组显示标题。"""
        names = ["条件一", "条件二", "条件三"]
        if 1 <= self.index <= len(names):
            return names[self.index - 1]
        return f"条件{self.index}"

    @property
    def label(self) -> str:
        """返回用于通知和结果的条件说明。"""
        favorite_label = FAVORITE_LABELS.get(self.favorite, FAVORITE_LABELS["all"])
        played_label = PLAYED_LABELS.get(self.played, PLAYED_LABELS["all"])
        return f"{self.title}（{favorite_label} + {played_label} + 超过{self.days_threshold}天）"


@dataclass
class CleanupCandidate:
    """清理库存待检查的媒体候选项。"""

    movie_id: str
    code: str = ""
    title: str = ""
    date_created: str = ""
    date_created_obj: Optional[datetime] = None
    played: Optional[bool] = None
    favorite: Optional[bool] = None
    server: str = ""
    library_id: str = ""
    library_name: str = ""
    raw: Any = None

    @property
    def identity(self) -> str:
        """返回用于去重的稳定身份。"""
        return str(self.movie_id or self.code or self.title or id(self.raw))

    def age_days(self, now: Optional[datetime] = None) -> Optional[int]:
        """返回候选项创建时间距今的天数。"""
        created = self.date_created_obj or parse_datetime(self.date_created)
        if not created:
            return None
        current = normalize_datetime(now or datetime.now(timezone.utc))
        return (current - normalize_datetime(created)).days

    def to_dict(self, now: Optional[datetime] = None) -> dict:
        """转换为可持久化的结果字典。"""
        return {
            "movie_id": self.movie_id,
            "code": self.code,
            "title": self.title,
            "server": self.server,
            "library_id": self.library_id,
            "library_name": self.library_name,
            "date_created": self.date_created,
            "age_days": self.age_days(now),
            "played": self.played,
            "favorite": self.favorite,
        }


@dataclass
class CleanupResult:
    """清理库存筛选结果。"""

    conditions: List[CleanupCondition] = field(default_factory=list)
    qualified_movies: List[CleanupCandidate] = field(default_factory=list)

    @property
    def qualified_count(self) -> int:
        """返回符合条件的媒体数量。"""
        return len(self.qualified_movies)

    @property
    def condition_label(self) -> str:
        """返回本次筛选使用的条件说明。"""
        return format_conditions_label(self.conditions)

    def to_dict(self, now: Optional[datetime] = None) -> dict:
        """转换为可保存到插件数据区的结果。"""
        return {
            "qualified_count": self.qualified_count,
            "condition_label": self.condition_label,
            "conditions": [condition.label for condition in self.conditions],
            "qualified_movies": [movie.to_dict(now) for movie in self.qualified_movies],
        }


def normalize_datetime(value: datetime) -> datetime:
    """将时间统一为带时区的 UTC 时间。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_datetime(value: Any) -> Optional[datetime]:
    """解析媒体服务器返回的常见时间字符串。"""
    if isinstance(value, datetime):
        return normalize_datetime(value)
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    if "." in text:
        prefix, suffix = text.split(".", 1)
        timezone_part = ""
        for marker in ("+", "-"):
            if marker in suffix:
                fraction, timezone_part = suffix.split(marker, 1)
                timezone_part = marker + timezone_part
                break
        else:
            fraction = suffix
        text = f"{prefix}.{fraction[:6]}{timezone_part}"
    try:
        return normalize_datetime(datetime.fromisoformat(text))
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return normalize_datetime(datetime.strptime(str(value), fmt))
            except ValueError:
                continue
    return None


def build_cleanup_conditions(config: dict | None) -> List[CleanupCondition]:
    """根据配置构建清理库存条件组。"""
    config = config or {}
    conditions = [
        CleanupCondition(
            index=1,
            favorite=normalize_favorite(config.get("filter_favorite", "all")),
            played=normalize_played(config.get("filter_played", "all")),
            days_threshold=normalize_days(config.get("days_threshold", 30)),
        )
    ]
    if any(key in config for key in ("filter_favorite_2", "filter_played_2", "days_threshold_2")):
        conditions.append(
            CleanupCondition(
                index=2,
                favorite=normalize_favorite(config.get("filter_favorite_2", "all")),
                played=normalize_played(config.get("filter_played_2", "all")),
                days_threshold=normalize_days(config.get("days_threshold_2", 30)),
            )
        )
    return conditions


def normalize_favorite(value: Any) -> str:
    """归一化收藏状态筛选值。"""
    text = str(value or "all").strip().lower()
    return text if text in FAVORITE_LABELS else "all"


def normalize_played(value: Any) -> str:
    """归一化看过状态筛选值。"""
    text = str(value or "all").strip().lower()
    return text if text in PLAYED_LABELS else "all"


def normalize_days(value: Any) -> int:
    """归一化创建时间阈值天数。"""
    try:
        days = int(value)
    except (TypeError, ValueError):
        return 30
    return days if days > 0 else 1


def format_conditions_label(conditions: Iterable[CleanupCondition]) -> str:
    """格式化多组清理库存条件说明。"""
    labels = [condition.label for condition in conditions]
    return "或 ".join(labels)


def filter_cleanup_candidates(
    candidates: Iterable[CleanupCandidate],
    config: dict | None,
    now: Optional[datetime] = None,
) -> CleanupResult:
    """按多组条件 OR 语义筛选并去重候选项。"""
    conditions = build_cleanup_conditions(config)
    current = normalize_datetime(now or datetime.now(timezone.utc))
    qualified: List[CleanupCandidate] = []
    seen = set()
    for candidate in candidates or []:
        if not isinstance(candidate, CleanupCandidate):
            candidate = candidate_from_media_item(candidate)
        if not any(match_condition(candidate, condition, current) for condition in conditions):
            continue
        identity = candidate.identity
        if identity in seen:
            continue
        seen.add(identity)
        qualified.append(candidate)
    return CleanupResult(conditions=conditions, qualified_movies=qualified)


def match_condition(candidate: CleanupCandidate, condition: CleanupCondition, now: datetime) -> bool:
    """判断单个候选项是否命中一组清理条件。"""
    age = candidate.age_days(now)
    if age is None or age <= condition.days_threshold:
        return False
    if not match_favorite(candidate.favorite, condition.favorite):
        return False
    return match_played(candidate.played, condition.played)


def match_favorite(value: Optional[bool], expected: str) -> bool:
    """判断候选项收藏状态是否符合条件。"""
    if expected == "all":
        return True
    if value is None:
        return False
    return bool(value) if expected == "fav" else not bool(value)


def match_played(value: Optional[bool], expected: str) -> bool:
    """判断候选项看过状态是否符合条件。"""
    if expected == "all":
        return True
    if value is None:
        return False
    return bool(value) if expected == "played" else not bool(value)


def candidate_from_media_item(
    item: Any,
    server: str = "",
    library_id: str = "",
    library_name: str = "",
) -> CleanupCandidate:
    """将宿主媒体条目转换为清理库存候选项。"""
    raw = item
    movie_id = read_value(item, "movie_id", "item_id", "id", "Id") or ""
    title = read_value(item, "title", "Name", "name") or ""
    code = read_value(item, "code", "tmdbid", "imdbid", "item_id", "id", "Id") or movie_id
    date_created = read_value(item, "date_created", "DateCreated", "dateCreated", "created") or ""
    user_state = read_value(item, "user_state", "UserData") or {}
    played = read_bool(read_value(user_state, "played", "Played"))
    favorite = read_bool(
        read_value(item, "favorite", "is_favorite", "IsFavorite")
        if read_value(item, "favorite", "is_favorite", "IsFavorite") is not None
        else read_value(user_state, "favorite", "is_favorite", "IsFavorite")
    )
    return CleanupCandidate(
        movie_id=str(movie_id or ""),
        code=str(code or ""),
        title=str(title or ""),
        date_created=str(date_created or ""),
        date_created_obj=parse_datetime(date_created),
        played=played,
        favorite=favorite,
        server=str(server or read_value(item, "server") or ""),
        library_id=str(library_id or read_value(item, "library", "ParentId") or ""),
        library_name=str(library_name or ""),
        raw=raw,
    )


def read_value(obj: Any, *names: str) -> Any:
    """从对象或字典中读取第一个存在的字段。"""
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def read_bool(value: Any) -> Optional[bool]:
    """把媒体服务器返回值转换为布尔或未知。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None
