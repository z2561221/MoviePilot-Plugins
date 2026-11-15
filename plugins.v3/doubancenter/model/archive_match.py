"""归档匹配规则和单次操作的候选索引，不持有插件或持久化句柄。"""

from bisect import bisect_left, insort
from dataclasses import dataclass
from heapq import merge

from .identity import identity_from_media

COMPAT_FIELDS = ("unique", "tmdbid", "tmdb_id", "reason", "detail", "link")


def _record_key(source, record, identity):
    if not isinstance(record, dict):
        return (source, "")
    media_source, media_id = identity
    return (
        source,
        str(record.get("unique") or ""),
        str(getattr(media_source, "value", media_source) or ""),
        str(media_id or ""),
        str(record.get("title") or ""),
        str(record.get("reason") or ""),
        str(record.get("detail") or ""),
        str(record.get("time") or ""),
        str(record.get("link") or ""),
    )


def archive_record_key(source: str, record: dict) -> tuple:
    identity = identity_from_media(record) if isinstance(record, dict) else (None, None)
    return _record_key(source, record, identity)


def archive_record_score(record: dict) -> int:
    if not isinstance(record, dict):
        return 0
    score = sum(1 for value in record.values() if value not in (None, "", [], {}))
    for field in ("unique", "poster", "tmdbid", "rank_key", "rank_name", "first_seen", "subscribed_at"):
        if record.get(field):
            score += 5
    return score


@dataclass(frozen=True, slots=True)
class ArchiveMatchRecord:
    key: tuple
    identity: tuple | None
    fields: tuple[str, ...]
    valid: bool

    @classmethod
    def from_record(cls, source: str, record):
        valid = isinstance(record, dict)
        media_source, media_id = identity_from_media(record) if valid else (None, None)
        identity = (media_source, str(media_id)) if media_source and media_id else None
        return cls(
            key=_record_key(source, record, (media_source, media_id)),
            identity=identity,
            fields=tuple(str(record.get(name) or "") for name in COMPAT_FIELDS) if valid else ("",) * len(COMPAT_FIELDS),
            valid=valid,
        )

    @property
    def bucket(self):
        return self.key[0], self.key[4] if self.valid else ""

    def matches(self, other: "ArchiveMatchRecord") -> bool:
        # 精确键优先，包括原实现中不参与精确键的辅助tmdb字段冲突。
        if self.key == other.key:
            return True
        if not self.valid or not other.valid or self.bucket != other.bucket or not self.key[4]:
            return False
        if self.identity is not None and other.identity is not None and self.identity != other.identity:
            return False
        return not any(left and right and left != right for left, right in zip(self.fields, other.fields))


def same_archive_record(source: str, left: dict, right: dict) -> bool:
    return ArchiveMatchRecord.from_record(source, left).matches(ArchiveMatchRecord.from_record(source, right))


def _add(postings, key, position):
    current = postings.get(key)
    if current is None:
        postings[key] = position
    elif isinstance(current, int):
        postings[key] = sorted((current, position))
    elif position > current[-1]:
        current.append(position)
    else:
        insort(current, position)


def _remove(postings, key, position):
    current = postings[key]
    if isinstance(current, int):
        del postings[key]
        return
    current.pop(bisect_left(current, position))
    if len(current) == 1:
        postings[key] = current[0]
    elif not current:
        del postings[key]


def _positions(posting):
    if posting is None:
        return ()
    return (posting,) if isinstance(posting, int) else posting


class _FieldIndex:
    """维护某个候选集合的计数，需要筛选时才建立字段位置列。"""

    def __init__(self):
        self.members = []
        self.counts = [{} for _ in COMPAT_FIELDS]
        self.filled = [0] * len(COMPAT_FIELDS)
        self.columns = {}

    def add(self, position, record):
        if not self.members or position > self.members[-1]:
            self.members.append(position)
        else:
            insort(self.members, position)
        for column, value in enumerate(record.fields):
            if value:
                counts = self.counts[column]
                counts[value] = counts.get(value, 0) + 1
                self.filled[column] += 1
            if column in self.columns:
                _add(self.columns[column], value, position)

    def remove(self, position, record):
        self.members.pop(bisect_left(self.members, position))
        for column, value in enumerate(record.fields):
            if value:
                counts = self.counts[column]
                counts[value] -= 1
                if not counts[value]:
                    del counts[value]
                self.filled[column] -= 1
            if column in self.columns:
                _remove(self.columns[column], value, position)

    def allowed(self, column, value):
        return len(self.members) - self.filled[column] + self.counts[column].get(value, 0)

    def filtered(self, column, value, features):
        if column not in self.columns:
            postings = {}
            for position in self.members:
                _add(postings, features[position].fields[column], position)
            self.columns[column] = postings
        postings = self.columns[column]
        return [_positions(postings.get(value)), _positions(postings.get(""))]


def _group_members(group):
    return group.members if isinstance(group, _FieldIndex) else _positions(group)


def _group_allowed(group, column, value, features):
    if isinstance(group, _FieldIndex):
        return group.allowed(column, value)
    if group is None:
        return 0
    existing = features[group].fields[column]
    return int(not existing or existing == value)


def _group_filtered(group, column, value, features):
    if isinstance(group, _FieldIndex):
        return group.filtered(column, value, features)
    return [_positions(group)] if _group_allowed(group, column, value, features) else []


class _Bucket:
    """弱输入查询全桶，强输入只查询同身份及缺身份组；精确键始终加入。"""

    def __init__(self):
        self.all_fields = _FieldIndex()
        self.exact = {}
        self.identities = {}

    def add(self, position, record, features):
        self.all_fields.add(position, record)
        _add(self.exact, record.key, position)
        group = self.identities.get(record.identity)
        if group is None:
            self.identities[record.identity] = position
            return
        if isinstance(group, int):
            first = group
            group = _FieldIndex()
            group.add(first, features[first])
            self.identities[record.identity] = group
        group.add(position, record)

    def remove(self, position, record):
        self.all_fields.remove(position, record)
        _remove(self.exact, record.key, position)
        group = self.identities[record.identity]
        if isinstance(group, int):
            del self.identities[record.identity]
            return
        group.remove(position, record)
        if len(group.members) == 1:
            self.identities[record.identity] = group.members[0]

    def candidates(self, record, features):
        exact = self.exact.get(record.key)
        if not record.valid or not record.key[4]:
            return _positions(exact)
        if record.identity is None:
            streams = [self.all_fields.members]
            count = len(self.all_fields.members)
        else:
            strong = self.identities.get(record.identity)
            weak = self.identities.get(None)
            streams = [_group_members(strong), _group_members(weak), _positions(exact)]
            count = len(streams[0]) + len(streams[1])
        best = None
        for column, value in enumerate(record.fields):
            if not value:
                continue
            if record.identity is None:
                allowed = self.all_fields.allowed(column, value)
            else:
                allowed = (_group_allowed(strong, column, value, features)
                           + _group_allowed(weak, column, value, features))
            if allowed < count:
                count, best = allowed, column
        if best is not None:
            if count == 0:
                return _positions(exact)
            # 缺字段候选及精确键候选必须保留，不能被强身份或字段列隔离。
            if record.identity is None:
                streams = self.all_fields.filtered(best, record.fields[best], features)
            else:
                streams = (_group_filtered(strong, best, record.fields[best], features)
                           + _group_filtered(weak, best, record.fields[best], features))
            streams.append(_positions(exact))
        return streams[0] if len(streams) == 1 else merge(*streams)


class ArchiveMatchIndex:
    """位置与原输出一致；不同标题先存单位置，发生碰撞才投影身份。"""

    def __init__(self):
        self.records = []
        self.features = {}
        self.buckets = {}
        self.comparisons = 0

    @staticmethod
    def bucket_key(source, record):
        return source, str(record.get("title") or "") if isinstance(record, dict) else ""

    def _activate(self, key, position):
        first = ArchiveMatchRecord.from_record(key[0], self.records[position])
        self.features[position] = first
        bucket = _Bucket()
        bucket.add(position, first, self.features)
        self.buckets[key] = bucket
        return bucket

    def find(self, source, record):
        key = self.bucket_key(source, record)
        bucket = self.buckets.get(key)
        if bucket is None:
            return None, None
        if isinstance(bucket, int):
            bucket = self._activate(key, bucket)
        feature = ArchiveMatchRecord.from_record(source, record)
        previous = None
        for position in bucket.candidates(feature, self.features):
            if position == previous:
                continue
            previous = position
            self.comparisons += 1
            if self.features[position].matches(feature):
                return position, feature
        return None, feature

    def add(self, source, record, feature=None):
        position = len(self.records)
        self.records.append(record)
        key = self.bucket_key(source, record)
        bucket = self.buckets.get(key)
        if bucket is None:
            self.buckets[key] = position
        else:
            if isinstance(bucket, int):
                bucket = self._activate(key, bucket)
            feature = feature or ArchiveMatchRecord.from_record(source, record)
            self.features[position] = feature
            bucket.add(position, feature, self.features)

    def replace(self, position, record, feature):
        old = self.features[position]
        bucket = self.buckets[old.bucket]
        bucket.remove(position, old)
        self.records[position] = record
        self.features[position] = feature
        bucket.add(position, feature, self.features)
