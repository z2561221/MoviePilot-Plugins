"""AgentRank V3 持久化身份迁移测试。"""

from copy import deepcopy

from agentrank.storage.repository import AgentRankRepository


class MemoryPlugin:
    """提供 MoviePilot 插件数据接口的内存替身。"""

    def __init__(self, values):
        self.values = deepcopy(values)

    def get_data(self, key=None):
        if key is None:
            return deepcopy(self.values)
        return deepcopy(self.values.get(key))

    def save_data(self, key, value):
        self.values[key] = deepcopy(value)

    def del_data(self, key):
        self.values.pop(key, None)


def _legacy_candidate(candidate_id="tmdb:movie:42"):
    """返回没有 V3 主身份字段的旧候选载荷。"""
    return {
        "candidate_id": candidate_id,
        "title": "Movie",
        "media_type": "movie",
        "source_ids": {"tmdb": "42"},
    }


def test_repository_migrates_board_history_and_snapshot_without_data_loss():
    """三类旧数据原子补全身份，无法解析的榜单项保持原值。"""
    profile_id = "emby-user"
    run_id = "run-1"
    board_key = f"recommendation_board:profile:{profile_id}"
    history_key = f"board_history:profile:{profile_id}"
    index_key = f"candidate_snapshot_index:profile:{profile_id}"
    snapshot_key = f"candidate_snapshot:profile:{profile_id}:run:{run_id}"
    unresolved = {
        "candidate_id": "legacy:unknown",
        "rank": 2,
        "title": "Unknown",
        "source_ids": {},
    }
    board = {
        "profile_id": profile_id,
        "run_id": run_id,
        "recommendations": [
            {**_legacy_candidate(), "rank": 1},
            deepcopy(unresolved),
        ],
    }
    plugin = MemoryPlugin(
        {
            board_key: board,
            history_key: [deepcopy(board)],
            index_key: {
                "profile_id": profile_id,
                "snapshots": [{"run_id": run_id, "generated_at": "2026-08-14T00:00:00+00:00"}],
                "schema_version": 1,
            },
            snapshot_key: {
                "profile_id": profile_id,
                "run_id": run_id,
                "profile_version": {"run_id": run_id, "schema_version": 1},
                "retrieval_plan": {},
                "candidates": [_legacy_candidate()],
                "source_stats": {},
                "exclusion_counts": {},
                "generated_at": "2026-08-14T00:00:00+00:00",
                "content_hash": "legacy",
                "schema_version": 3,
            },
        }
    )

    result = AgentRankRepository(plugin).migrate_media_identities(profile_id)

    assert result == {
        "identity_updated_count": 3,
        "identity_unresolved_count": 2,
        "identity_storage_count": 3,
    }
    assert plugin.values[board_key]["recommendations"][0]["media_source"] == "themoviedb"
    assert plugin.values[history_key][0]["recommendations"][0]["media_id"] == "42"
    assert plugin.values[board_key]["recommendations"][1] == unresolved
    snapshot = plugin.values[snapshot_key]
    assert snapshot["schema_version"] == 4
    assert snapshot["candidates"][0]["media_source"] == "themoviedb"
    assert snapshot["content_hash"] != "legacy"

    second = AgentRankRepository(plugin).migrate_media_identities(profile_id)
    assert second["identity_updated_count"] == 0
    assert plugin.values[board_key]["recommendations"][1] == unresolved
