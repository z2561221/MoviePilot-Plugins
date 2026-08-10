"""最终候选不可变快照领域对象。"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping

from .candidate import Candidate, typed_tmdb_candidate_id


CANDIDATE_SNAPSHOT_SCHEMA_VERSION = 3


def _json_mapping(value: Any, field_name: str) -> Dict[str, Any]:
    """复制 JSON 映射并拒绝不可持久化值。"""
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    try:
        return json.loads(json.dumps(dict(value), ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be JSON serializable") from error


@dataclass
class CandidateSnapshot:
    """表示一次运行最终过滤后只写一次的候选快照。"""

    profile_id: str
    run_id: str
    profile_version: Dict[str, Any]
    retrieval_plan: Dict[str, Any]
    candidates: List[Candidate] = field(default_factory=list)
    source_stats: Dict[str, Any] = field(default_factory=dict)
    exclusion_counts: Dict[str, int] = field(default_factory=dict)
    generated_at: str = ""
    content_hash: str = ""
    schema_version: int = CANDIDATE_SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """规范化快照内容并校验作用域、版本和候选身份。"""
        self.profile_id = str(self.profile_id or "").strip()
        self.run_id = str(self.run_id or "").strip()
        self.schema_version = int(self.schema_version)
        if not self.profile_id or not self.run_id:
            raise ValueError("candidate snapshot profile_id and run_id are required")
        if self.schema_version < 2:
            raise ValueError("candidate snapshot schema_version is invalid")
        self.profile_version = _json_mapping(
            self.profile_version, "candidate snapshot profile_version"
        )
        self.retrieval_plan = _json_mapping(
            self.retrieval_plan, "candidate snapshot retrieval_plan"
        )
        self.source_stats = _json_mapping(
            self.source_stats, "candidate snapshot source_stats"
        )
        raw_counts = _json_mapping(
            self.exclusion_counts, "candidate snapshot exclusion_counts"
        )
        self.exclusion_counts = {
            str(name): max(0, int(count)) for name, count in raw_counts.items()
        }
        self.candidates = [
            Candidate.from_dict(candidate.to_dict())
            if isinstance(candidate, Candidate)
            else Candidate.from_dict(candidate)
            for candidate in self.candidates
        ]
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate snapshot contains duplicate candidate_id")
        if self.schema_version >= CANDIDATE_SNAPSHOT_SCHEMA_VERSION:
            for candidate_id in candidate_ids:
                if typed_tmdb_candidate_id(candidate_id) != candidate_id:
                    raise ValueError("candidate snapshot contains non-canonical TMDB id")
            profile_run_id = str(self.profile_version.get("run_id") or "").strip()
            profile_schema = int(self.profile_version.get("schema_version") or 0)
            if not profile_run_id or profile_schema <= 0:
                raise ValueError("candidate snapshot profile_version is incomplete")
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat()

    def _hash_payload(self) -> Dict[str, Any]:
        """返回排除 hash 字段本身的完整确定性内容。"""
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "run_id": self.run_id,
            "profile_version": dict(self.profile_version),
            "retrieval_plan": dict(self.retrieval_plan),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "source_stats": dict(self.source_stats),
            "exclusion_counts": dict(self.exclusion_counts),
            "generated_at": self.generated_at,
        }

    def calculate_content_hash(self) -> str:
        """计算快照完整内容的 SHA256。"""
        payload = json.dumps(
            self._hash_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def seal(self) -> "CandidateSnapshot":
        """写入当前内容 hash 并返回自身。"""
        self.content_hash = self.calculate_content_hash()
        return self

    def to_dict(self) -> Dict[str, Any]:
        """返回包含内容 hash 的可持久化字典。"""
        if not self.content_hash:
            self.seal()
        return {**self._hash_payload(), "content_hash": self.content_hash}

    @classmethod
    def create(
        cls,
        profile_id: str,
        run_id: str,
        profile_version: Mapping[str, Any],
        retrieval_plan: Mapping[str, Any],
        candidates: Iterable[Candidate],
        source_stats: Mapping[str, Any] = None,
        exclusion_counts: Mapping[str, Any] = None,
        generated_at: str = "",
    ) -> "CandidateSnapshot":
        """从最终候选及运行元数据创建并封存新快照。"""
        return cls(
            profile_id=profile_id,
            run_id=run_id,
            profile_version=dict(profile_version or {}),
            retrieval_plan=dict(retrieval_plan or {}),
            candidates=list(candidates or []),
            source_stats=dict(source_stats or {}),
            exclusion_counts=dict(exclusion_counts or {}),
            generated_at=generated_at,
        ).seal()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CandidateSnapshot":
        """从持久化字典恢复快照并验证内容 hash。"""
        if not isinstance(value, Mapping):
            raise ValueError("candidate snapshot must be a mapping")
        schema_version = int(value.get("schema_version") or 0)
        snapshot = cls(
            profile_id=value.get("profile_id"),
            run_id=value.get("run_id"),
            profile_version=dict(value.get("profile_version") or {}),
            retrieval_plan=dict(value.get("retrieval_plan") or {}),
            candidates=list(value.get("candidates") or []),
            source_stats=dict(value.get("source_stats") or {}),
            exclusion_counts=dict(value.get("exclusion_counts") or {}),
            generated_at=str(value.get("generated_at") or ""),
            content_hash=str(value.get("content_hash") or ""),
            schema_version=schema_version,
        )
        expected_hash = snapshot.calculate_content_hash()
        if schema_version >= CANDIDATE_SNAPSHOT_SCHEMA_VERSION:
            if not snapshot.content_hash or snapshot.content_hash != expected_hash:
                raise ValueError("candidate snapshot content_hash mismatch")
        else:
            snapshot.content_hash = expected_hash
        return snapshot
