"""媒体库部分失败必须保留未知状态，不能污染候选、Agent 或榜单。"""

import pytest

from app.plugins.agentrank.adapter.discovery import DiscoveryAdapter
from app.plugins.agentrank.adapter.library import LibraryAdapter
from app.plugins.agentrank.agent_tools.tools import _minimal_candidate
from app.plugins.agentrank.model.board import RecommendationItem
from app.plugins.agentrank.model.candidate import Candidate
from app.plugins.agentrank.service.candidate import CandidateCollectionService
from app.plugins.agentrank.storage.repository import AgentRankRepository


class MixedLookup:
    """让三个有效身份分别命中、未命中和查询失败。"""

    def exists(self, **kwargs):
        """按查询身份返回独立结果。"""
        if kwargs["media_id"] == "3":
            raise RuntimeError("database unavailable")
        return kwargs["media_id"] == "1"


class MemoryPlugin:
    """提供测试私有的插件存储。"""

    def __init__(self):
        """初始化空存储。"""
        self.data = {}

    def get_data(self, key=None):
        """读取隔离数据。"""
        return self.data.get(key)

    def save_data(self, key=None, value=None):
        """写入隔离数据。"""
        self.data[key] = value


def _candidates():
    """生成三个具有规范主身份的候选。"""
    return [Candidate(candidate_id=f"tmdb:movie:{i}", title=f"候选{i}", media_type="movie") for i in range(1, 4)]


def test_adapter_preserves_independent_lookup_states():
    """一项失败不能抹掉其它候选已经取得的事实。"""
    adapter = LibraryAdapter(MixedLookup())
    assert adapter.candidate_states(_candidates()) == {
        "tmdb:movie:1": True, "tmdb:movie:2": False, "tmdb:movie:3": None,
    }
    with pytest.raises(RuntimeError, match="未知"):
        adapter.candidate_ids(_candidates())
    with pytest.raises(RuntimeError, match="查询失败"):
        adapter.exists(_candidates()[2])


@pytest.mark.parametrize("exclude_library", [False, True])
def test_collection_preserves_unknown_or_excludes_it_for_a_hard_filter(exclude_library):
    """普通召回保留未知；明确要求排除已有媒体时，未知不能当作未入库放行。"""
    discovery = DiscoveryAdapter(source_fetchers={
        "tmdb_movies": lambda count: [
            {"title": f"候选{i}", "media_type": "movie", "tmdb_id": i} for i in range(1, 4)
        ],
    })
    service = CandidateCollectionService(
        discovery, AgentRankRepository(MemoryPlugin()), library_adapter=LibraryAdapter(MixedLookup()),
    )
    result = service.collect_and_freeze(
        "alice", "library-unknown", {"tmdb_movies": True}, 10,
        exclude_library_candidates=exclude_library,
    )
    states = {item.candidate_id: item.metadata["in_library"] for item in result.candidates}
    if exclude_library:
        assert states == {"tmdb:movie:2": False}
        assert result.exclusion_counts["library_unknown"] == 1
    else:
        assert states == {"tmdb:movie:1": True, "tmdb:movie:2": False, "tmdb:movie:3": None}
    assert result.source_errors["library"]


@pytest.mark.parametrize("state", [True, False, None])
def test_board_roundtrip_keeps_library_state(state):
    """持久化往返不能把 null 转成 false。"""
    item = RecommendationItem.from_dict({"candidate_id": "tmdb:movie:3", "in_library": state})
    assert item.in_library is state
    assert RecommendationItem.from_dict(item.to_dict()).in_library is state


def test_agent_context_preserves_explicit_unknown_over_old_metadata():
    """顶层明确未知的状态不能被旧 metadata 覆盖。"""
    value = _minimal_candidate({
        "candidate_id": "tmdb:movie:3", "in_library": None, "metadata": {"in_library": True},
    })
    assert value["in_library"] is None


def test_optional_library_adapter_does_not_disable_candidate_collection():
    """未接入库适配器时仍可召回候选，但不能假造已确认的库存状态。"""
    discovery = DiscoveryAdapter(source_fetchers={
        "tmdb_movies": lambda count: [{"title": "候选", "media_type": "movie", "tmdb_id": 3}],
    })
    result = CandidateCollectionService(
        discovery, AgentRankRepository(MemoryPlugin()),
    ).collect_and_freeze("alice", "no-library-adapter", {"tmdb_movies": True}, 10)
    assert len(result.candidates) == 1
    assert result.candidates[0].metadata["in_library"] is None
