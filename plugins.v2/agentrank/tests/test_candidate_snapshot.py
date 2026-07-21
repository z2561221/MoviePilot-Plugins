"""AgentRank 最终候选不可变快照测试。"""

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_candidate_snapshot_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
snapshot_module = importlib.import_module(
    f"{PACKAGE_NAME}.model.candidate_snapshot"
)
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")

Candidate = candidate_module.Candidate
CandidateSnapshot = snapshot_module.CandidateSnapshot
AgentRankRepository = repository_module.AgentRankRepository

PROFILE_ID = "emby:home:user-1"


class FakePlugin:
    """内存插件数据接口，可模拟写入后抛错。"""

    def __init__(self, fail_snapshot_save=False):
        """初始化内存数据与一次性快照写入故障开关。"""
        self.data = {}
        self.fail_snapshot_save = fail_snapshot_save

    def get_data(self, key=None):
        """读取内存插件数据。"""
        return self.data.get(key)

    def save_data(self, key=None, value=None):
        """保存数据，并可在半写后模拟宿主失败。"""
        self.data[key] = value
        if self.fail_snapshot_save and str(key).startswith("candidate_snapshot:"):
            self.fail_snapshot_save = False
            raise RuntimeError("snapshot write failed")

    def del_data(self, key=None):
        """删除内存插件数据。"""
        self.data.pop(key, None)


def _snapshot(run_id="run-1", candidate_id="tmdb:movie:1"):
    """创建包含完整 4.4 元数据的测试快照。"""
    return CandidateSnapshot.create(
        profile_id=PROFILE_ID,
        run_id=run_id,
        profile_version={
            "run_id": "profile-run",
            "schema_version": 4,
            "retrieval_resolution_version": 1,
        },
        retrieval_plan={
            "filters": {"media_types": ["movie"]},
            "ranking_tags": ["悬疑"],
        },
        candidates=[
            Candidate(
                candidate_id=candidate_id,
                title="Candidate",
                media_type="movie",
                source_ids={"tmdb": candidate_id.rsplit(":", 1)[-1]},
            )
        ],
        source_stats={
            "fetched_source_counts": {"tmdb_movies": 2},
            "accepted_source_counts": {"tmdb_movies": 1},
            "layer_counts": {"exact": 2},
            "source_error_count": 0,
        },
        exclusion_counts={"library": 1},
    )


def test_snapshot_roundtrip_preserves_metadata_and_content_hash():
    """完整快照回读必须保留画像版本、检索计划、统计和内容 hash。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    snapshot = _snapshot()

    repository.save_candidate_snapshot(snapshot)
    loaded = repository.load_candidate_snapshot_record("run-1", PROFILE_ID)

    assert loaded is not None
    assert loaded.profile_version == snapshot.profile_version
    assert loaded.retrieval_plan == snapshot.retrieval_plan
    assert loaded.source_stats == snapshot.source_stats
    assert loaded.exclusion_counts == {"library": 1}
    assert loaded.content_hash == snapshot.content_hash
    assert len(loaded.content_hash) == 64
    assert loaded.calculate_content_hash() == loaded.content_hash


def test_snapshot_same_run_is_write_once_and_never_appended():
    """同 profile_id/run_id 的第二次写入必须拒绝且不改变首次内容。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    first = _snapshot()
    repository.save_candidate_snapshot(first)

    with pytest.raises(ValueError, match="already exists"):
        repository.save_candidate_snapshot(
            _snapshot(candidate_id="tmdb:movie:2")
        )

    loaded = repository.load_candidate_snapshot_record("run-1", PROFILE_ID)
    assert loaded.content_hash == first.content_hash
    assert [item.candidate_id for item in loaded.candidates] == ["tmdb:movie:1"]


def test_snapshot_hash_tampering_is_rejected_with_recovery_evidence():
    """持久化内容被篡改后不得交给 Agent，并记录恢复证据。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_candidate_snapshot(_snapshot())
    key = "candidate_snapshot:profile:emby%3Ahome%3Auser-1:run:run-1"
    plugin.data[key]["candidates"][0]["title"] = "Tampered"

    assert repository.load_candidate_snapshot_record("run-1", PROFILE_ID) is None
    assert plugin.data["agentrank_recovery_log"][-1]["detail"] == (
        "candidate snapshot content_hash mismatch"
    )


def test_snapshot_save_failure_removes_partial_value():
    """宿主在半写后抛错时仓库必须删除风险快照。"""
    plugin = FakePlugin(fail_snapshot_save=True)
    repository = AgentRankRepository(plugin)
    key = "candidate_snapshot:profile:emby%3Ahome%3Auser-1:run:run-1"

    with pytest.raises(RuntimeError, match="snapshot write failed"):
        repository.save_candidate_snapshot(_snapshot())

    assert key not in plugin.data
