"""用户订阅画像输入规范化服务。"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from ..adapter.subscription import SubscriptionAdapter
from ..model.subscription import ProfileInputResult, SubscriptionSample


class ProfileInputService:
    """按用户读取、规范化并稳定去重订阅样本。"""

    def __init__(self, adapter: SubscriptionAdapter):
        """绑定只读订阅适配器。"""
        self._adapter = adapter

    @staticmethod
    def _get(record: Any, name: str, default: Any = None) -> Any:
        """兼容 ORM 对象和字典读取字段。"""
        if isinstance(record, Mapping):
            return record.get(name, default)
        return getattr(record, name, default)

    @classmethod
    def _metadata(cls, record: Any) -> Dict[str, Any]:
        """合并记录中可用的结构化媒体描述字段。"""
        metadata: Dict[str, Any] = {}
        for field_name in ("metadata", "media", "note"):
            value = cls._get(record, field_name)
            if isinstance(value, Mapping):
                metadata.update(value)
        return metadata

    @staticmethod
    def _string_list(value: Any) -> List[str]:
        """把字符串或序列规范化为保持顺序的非空字符串列表。"""
        if value is None:
            return []
        if isinstance(value, str):
            items: Iterable[Any] = value.replace("/", ",").replace("，", ",").split(",")
        elif isinstance(value, (list, tuple, set)):
            items = value
        else:
            items = [value]
        result: List[str] = []
        for item in items:
            text = str(item or "").strip()
            if text and text not in result:
                result.append(text)
        return result

    @classmethod
    def _metadata_list(cls, metadata: Mapping[str, Any], *names: str) -> List[str]:
        """按别名顺序提取第一个可用的列表字段。"""
        for name in names:
            if metadata.get(name) not in (None, "", []):
                return cls._string_list(metadata.get(name))
        return []

    @classmethod
    def _media_type(cls, record: Any, metadata: Mapping[str, Any]) -> str:
        """将 MoviePilot 类型与类别规范化为 movie、tv 或 anime。"""
        raw = " ".join(
            str(value or "")
            for value in (
                cls._get(record, "type"),
                cls._get(record, "media_category"),
                metadata.get("media_type"),
                metadata.get("category"),
            )
        ).lower()
        if any(token in raw for token in ("anime", "animation", "动漫", "动画", "番剧")):
            return "anime"
        if any(token in raw for token in ("movie", "电影")):
            return "movie"
        if any(token in raw for token in ("tv", "电视剧", "剧集", "电视")):
            return "tv"
        if cls._get(record, "bangumiid"):
            return "anime"
        return "unknown"

    @classmethod
    def _ids(cls, record: Any) -> Dict[str, str]:
        """收集所有可用的 MoviePilot 媒体标识。"""
        aliases = (
            ("tmdb", "tmdbid"),
            ("douban", "doubanid"),
            ("bangumi", "bangumiid"),
            ("tvdb", "tvdbid"),
            ("imdb", "imdbid"),
            ("media", "mediaid"),
        )
        return {
            target: str(value)
            for target, source in aliases
            if (value := cls._get(record, source)) not in (None, "")
        }

    @staticmethod
    def _stable_id(
        ids: Mapping[str, str], media_type: str, title: str, year: Optional[int]
    ) -> str:
        """优先使用平台 ID，否则生成确定性的媒体回退标识。"""
        for name in ("tmdb", "douban", "bangumi", "tvdb", "imdb", "media"):
            if ids.get(name):
                return f"{name}:{ids[name]}"
        return f"fallback:{media_type}:{title}:{year or ''}"

    @staticmethod
    def _parse_date(value: Any) -> Optional[datetime]:
        """解析 MoviePilot 常见订阅时间格式为 UTC 时间。"""
        text = str(value or "").strip()
        if not text:
            return None
        candidates = (text.replace("Z", "+00:00"), text)
        for candidate in candidates:
            try:
                parsed = datetime.fromisoformat(candidate)
                return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
            except ValueError:
                continue
        return None

    @classmethod
    def _normalize(cls, record: Any) -> Tuple[SubscriptionSample, Optional[datetime]]:
        """规范化单条订阅；缺少标题时拒绝。"""
        title = str(cls._get(record, "name") or cls._get(record, "title") or "").strip()
        if not title:
            raise ValueError("subscription title is required")
        metadata = cls._metadata(record)
        media_type = cls._media_type(record, metadata)
        raw_year = cls._get(record, "year") or metadata.get("year")
        try:
            year = int(raw_year) if raw_year not in (None, "") else None
        except (TypeError, ValueError):
            year = None
        ids = cls._ids(record)
        raw_rating = cls._get(record, "vote")
        if raw_rating in (None, ""):
            raw_rating = metadata.get("rating", metadata.get("vote", metadata.get("score")))
        try:
            rating = float(raw_rating) if raw_rating not in (None, "") else None
        except (TypeError, ValueError):
            rating = None
        raw_date = cls._get(record, "date") or cls._get(record, "created_at")
        parsed_date = cls._parse_date(raw_date)
        return (
            SubscriptionSample(
                stable_id=cls._stable_id(ids, media_type, title, year),
                title=title,
                media_type=media_type,
                year=year,
                ids=ids,
                genres=cls._metadata_list(metadata, "genres", "genre", "themes", "theme"),
                actors=cls._metadata_list(metadata, "actors", "actor", "cast"),
                directors=cls._metadata_list(metadata, "directors", "director"),
                regions=cls._metadata_list(metadata, "regions", "region", "countries", "country"),
                rating=rating,
                subscribed_at=str(raw_date or ""),
            ),
            parsed_date,
        )

    def collect(
        self,
        username: str,
        profile_scope: str = "all",
        recent_days: int = 365,
        sample_limit: int = 200,
        minimum_samples: int = 5,
        now: datetime = None,
    ) -> ProfileInputResult:
        """收集当前用户画像样本并返回 ready 或 sample_insufficient。"""
        target = str(username or "").strip()
        if not target:
            raise ValueError("username is required")
        current_time = now or datetime.now(timezone.utc)
        current_time = current_time.replace(tzinfo=current_time.tzinfo or timezone.utc)
        cutoff = current_time.astimezone(timezone.utc) - timedelta(days=max(1, int(recent_days)))
        normalized: List[Tuple[SubscriptionSample, Optional[datetime], int]] = []
        rejected_count = 0
        for index, record in enumerate(self._adapter.list_by_username(target)):
            try:
                sample, subscribed_at = self._normalize(record)
            except (TypeError, ValueError):
                rejected_count += 1
                continue
            if profile_scope == "recent" and (subscribed_at is None or subscribed_at < cutoff):
                continue
            normalized.append((sample, subscribed_at, index))
        normalized.sort(
            key=lambda item: (
                item[1] is not None,
                item[1] or datetime.min.replace(tzinfo=timezone.utc),
                -item[2],
            ),
            reverse=True,
        )
        samples: List[SubscriptionSample] = []
        seen = set()
        for sample, _, _ in normalized:
            if sample.stable_id in seen:
                continue
            seen.add(sample.stable_id)
            samples.append(sample)
            if len(samples) >= max(1, int(sample_limit)):
                break
        minimum = max(1, int(minimum_samples))
        status = "ready" if len(samples) >= minimum else "sample_insufficient"
        return ProfileInputResult(
            username=target,
            status=status,
            samples=samples,
            minimum_samples=minimum,
            rejected_count=rejected_count,
        )
