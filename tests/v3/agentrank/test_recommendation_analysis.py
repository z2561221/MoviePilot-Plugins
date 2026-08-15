"""结构化推荐分析的来源、隐私、持久化与原子性测试。"""

import copy
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType


PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "agentrank"
PACKAGE_NAME = "agentrank_recommendation_analysis_test"
PROFILE_ID = "emby:home:user-1"
NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

analysis_module = importlib.import_module(f"{PACKAGE_NAME}.model.analysis")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
config_module = importlib.import_module(f"{PACKAGE_NAME}.model.config")
memory_module = importlib.import_module(f"{PACKAGE_NAME}.model.memory")
playback_module = importlib.import_module(f"{PACKAGE_NAME}.model.playback")
support_module = importlib.import_module(f"{PACKAGE_NAME}.model.support")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
builder_module = importlib.import_module(f"{PACKAGE_NAME}.service.analysis")
data_lifecycle_module = importlib.import_module(
    f"{PACKAGE_NAME}.service.data_lifecycle"
)
scoring_module = importlib.import_module(f"{PACKAGE_NAME}.service.scoring")

RecommendationAnalysis = analysis_module.RecommendationAnalysis
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
WEIGHT_DEFAULTS = config_module.WEIGHT_DEFAULTS
PreferenceMemory = memory_module.PreferenceMemory
PlaybackSnapshot = playback_module.PlaybackSnapshot
SupportContribution = support_module.SupportContribution
SupportScore = support_module.SupportScore
AgentRankRepository = repository_module.AgentRankRepository
RecommendationAnalysisBuilder = builder_module.RecommendationAnalysisBuilder
DataLifecycleService = data_lifecycle_module.DataLifecycleService
PolicyLearningService = scoring_module.PolicyLearningService


class FakePlugin:
    """提供隔离副本的内存插件数据区。"""

    def __init__(self) -> None:
        """创建空数据区。"""
        self.data = {}
        self.fail_once_on_key = ""
        self.failed = False

    def get_data(self, key=None):
        """返回指定键的独立副本。"""
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """保存指定键的独立副本。"""
        if key == self.fail_once_on_key and not self.failed:
            self.failed = True
            raise RuntimeError("injected analysis save failure")
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除指定插件数据键。"""
        self.data.pop(key, None)


class JsonRoundTripPlugin(FakePlugin):
    """模拟 MoviePilot 插件数据层的 JSON 序列化往返。"""

    def save_data(self, key=None, value=None):
        """通过 JSON 往返后保存，暴露 tuple 与 list 的宿主差异。"""
        if key == self.fail_once_on_key and not self.failed:
            self.failed = True
            raise RuntimeError("injected analysis save failure")
        self.data[key] = json.loads(json.dumps(value, ensure_ascii=False))


def _policy():
    """构造固定时钟下的空证据策略。"""
    playback = PlaybackSnapshot(
        profile_id=PROFILE_ID,
        source="playback_reporting",
        status="ready",
        synced_at=NOW.isoformat(),
    )
    return PolicyLearningService(
        repository=None,
        now_factory=lambda: NOW,
    ).build_snapshot(
        PROFILE_ID,
        WEIGHT_DEFAULTS,
        PreferenceMemory.empty(PROFILE_ID),
        playback,
    )


def _item(policy_version):
    """构造同时含正向记忆和反向播放证据的推荐条目。"""
    contributions = [
        SupportContribution(
            dimension="theme_weight",
            direction="positive",
            user_value="悬疑",
            candidate_value="悬疑",
            user_refs=("memory:item-1",),
            candidate_ref="candidate:1:genres:0",
            weight_units=8_000,
            certainty_units=10_000,
            contribution_units=8_000,
        ),
        SupportContribution(
            dimension="freshness_weight",
            direction="counter",
            user_value="慢节奏",
            candidate_value="慢节奏",
            user_refs=("playback:abandoned:tmdb:movie:2",),
            candidate_ref="candidate:1:pacing:0",
            weight_units=2_000,
            certainty_units=5_000,
            contribution_units=1_000,
        ),
    ]
    return RecommendationItem(
        candidate_id="tmdb:movie:1",
        rank=1,
        summary="旧案重启牵出层层隐秘",
        reason="悬疑题材契合，但慢节奏存在反向证据。",
        support=SupportScore.from_contributions(policy_version, contributions),
        selection_source="agent",
    )


def test_builder_exposes_verified_sources_without_prompt_or_chain_of_thought():
    """分析只保存结构化贡献和提示指纹，不保存提示正文或推理过程。"""
    policy = _policy()
    item = _item(policy.policy_version)
    builder = RecommendationAnalysisBuilder(now_factory=lambda: NOW)
    fingerprint = builder.prompt_fingerprint("private ranking prompt", "private copy prompt")

    analysis = builder.build(PROFILE_ID, "run-1", item, policy, fingerprint)
    payload = analysis.to_dict()
    serialized = json.dumps(payload, ensure_ascii=False)

    assert len(analysis.positive_evidence) == 1
    assert len(analysis.counter_evidence) == 1
    assert analysis.data_sources == [
        "policy_snapshot",
        "frozen_candidate",
        "confirmed_memory",
        "playback_history",
    ]
    assert analysis.support_percentage == item.support.percentage
    assert analysis.policy_version == policy.policy_version
    assert analysis.memory_revision == policy.memory_revision
    for forbidden in (
        "private ranking prompt",
        "private copy prompt",
        "chain_of_thought",
        "raw_output",
        "tool_process",
        "token",
        "思维链",
    ):
        assert forbidden not in serialized


def test_board_and_recommendation_analysis_round_trip_atomically():
    """榜单只在同轮同候选分析完整时与分析记录一并保存。"""
    repository = AgentRankRepository(FakePlugin())
    policy = _policy()
    item = _item(policy.policy_version)
    analysis = RecommendationAnalysisBuilder(now_factory=lambda: NOW).build(
        PROFILE_ID,
        "run-1",
        item,
        policy,
        "a" * 64,
    )
    item.analysis_id = analysis.analysis_id
    board = RecommendationBoard(
        profile_id=PROFILE_ID,
        run_id="run-1",
        recommendations=[item],
    )

    repository.save_board_with_recommendation_analyses(board, [analysis])

    restored_board = repository.load_board(PROFILE_ID)
    restored = repository.load_recommendation_analyses(PROFILE_ID, "run-1")
    assert restored_board.recommendations[0].analysis_id == analysis.analysis_id
    assert restored == [RecommendationAnalysis.from_dict(analysis.to_dict())]

    analysis_key = repository._learning_key("agent_analysis", PROFILE_ID)
    plugin_data = repository._plugin.data
    plugin_data[analysis_key][0]["positive_evidence"][0]["user_value"] = (
        "api_key=supersecret"
    )
    exported = DataLifecycleService(repository).export_profile(PROFILE_ID)
    assert exported["board"]["recommendations"][0]["analysis_id"] == (
        analysis.analysis_id
    )
    assert exported["recommendation_analyses"][0]["policy_version"] == (
        policy.policy_version
    )
    serialized = json.dumps(exported["recommendation_analyses"], ensure_ascii=False)
    for forbidden in (
        "chain_of_thought",
        "raw_output",
        "tool_process",
        "supersecret",
        "思维链",
    ):
        assert forbidden not in serialized


def test_board_atomic_readback_matches_moviepilot_json_storage():
    """支持度证据必须在 MoviePilot JSON 往返后保持原始字典完全相等。"""
    plugin = JsonRoundTripPlugin()
    repository = AgentRankRepository(plugin)
    policy = _policy()
    item = _item(policy.policy_version)
    analysis = RecommendationAnalysisBuilder(now_factory=lambda: NOW).build(
        PROFILE_ID,
        "run-json",
        item,
        policy,
        "e" * 64,
    )
    item.analysis_id = analysis.analysis_id
    board = RecommendationBoard(
        profile_id=PROFILE_ID,
        run_id="run-json",
        recommendations=[item],
    )

    repository.save_board_with_recommendation_analyses(board, [analysis])

    board_key = repository._profile_key("recommendation_board", PROFILE_ID)
    assert plugin.data[board_key] == board.to_dict()
    assert repository.load_board(PROFILE_ID) == board


def test_analysis_save_failure_restores_previous_board_and_records():
    """分析保存失败时原子恢复旧榜单和旧分析，绝不留下半更新状态。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    policy = _policy()
    builder = RecommendationAnalysisBuilder(now_factory=lambda: NOW)

    old_item = _item(policy.policy_version)
    old_analysis = builder.build(PROFILE_ID, "run-old", old_item, policy, "b" * 64)
    old_item.analysis_id = old_analysis.analysis_id
    old_board = RecommendationBoard(
        profile_id=PROFILE_ID,
        run_id="run-old",
        recommendations=[old_item],
    )
    repository.save_board_with_recommendation_analyses(old_board, [old_analysis])
    before = copy.deepcopy(plugin.data)

    new_item = _item(policy.policy_version)
    new_analysis = builder.build(PROFILE_ID, "run-new", new_item, policy, "c" * 64)
    new_item.analysis_id = new_analysis.analysis_id
    new_board = RecommendationBoard(
        profile_id=PROFILE_ID,
        run_id="run-new",
        recommendations=[new_item],
    )
    plugin.fail_once_on_key = repository._learning_key("agent_analysis", PROFILE_ID)

    try:
        repository.save_board_with_recommendation_analyses(
            new_board, [new_analysis]
        )
    except RuntimeError as error:
        assert "injected analysis save failure" in str(error)
    else:
        raise AssertionError("analysis save failure was not raised")

    comparable = {
        key: value
        for key, value in plugin.data.items()
        if key != repository.recovery_log_key
    }
    assert comparable == before


def test_historical_analysis_survives_current_board_replacement_for_feedback_audit():
    """同轮作品移出榜单后仍保留其分析，供反馈事实和归档恢复引用。"""
    repository = AgentRankRepository(FakePlugin())
    policy = _policy()
    builder = RecommendationAnalysisBuilder(now_factory=lambda: NOW)
    first_item = _item(policy.policy_version)
    first_analysis = builder.build(
        PROFILE_ID, "run-1", first_item, policy, "d" * 64
    )
    first_item.analysis_id = first_analysis.analysis_id
    repository.save_board_with_recommendation_analyses(
        RecommendationBoard(
            profile_id=PROFILE_ID,
            run_id="run-1",
            recommendations=[first_item],
        ),
        [first_analysis],
    )

    second_item = _item(policy.policy_version)
    second_item.candidate_id = "tmdb:movie:2"
    second_item.selection_source = "safe_fallback"
    second_analysis = builder.build(
        PROFILE_ID, "run-1", second_item, policy, "d" * 64
    )
    second_item.analysis_id = second_analysis.analysis_id
    repository.save_board_with_recommendation_analyses(
        RecommendationBoard(
            profile_id=PROFILE_ID,
            run_id="run-1",
            recommendations=[second_item],
        ),
        [second_analysis],
    )

    assert {
        item.analysis_id
        for item in repository.load_recommendation_analyses(PROFILE_ID, "run-1")
    } == {first_analysis.analysis_id, second_analysis.analysis_id}
