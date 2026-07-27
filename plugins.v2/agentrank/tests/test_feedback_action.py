"""统一喜欢、不喜欢、忽略反馈的状态机、幂等与回滚测试。"""

import copy
import importlib
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_feedback_action_test"
PROFILE_ID = "emby:home:user-1"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
snapshot_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate_snapshot")
repository_module = importlib.import_module(f"{PACKAGE_NAME}.storage.repository")
service_module = importlib.import_module(f"{PACKAGE_NAME}.service.feedback_action")

RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
Candidate = candidate_module.Candidate
CandidateSnapshot = snapshot_module.CandidateSnapshot
AgentRankRepository = repository_module.AgentRankRepository
FeedbackActionError = service_module.FeedbackActionError
FeedbackActionService = service_module.FeedbackActionService


class FakePlugin:
    """模拟 MoviePilot 插件数据接口和单次保存失败。"""

    def __init__(self):
        self.data = {}
        self.fail_once_on_key = ""
        self.failed = False

    def get_data(self, key=None):
        """返回独立副本，避免测试绕过仓储保存。"""
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key=None, value=None):
        """保存独立副本并支持指定键单次失败。"""
        if key == self.fail_once_on_key and not self.failed:
            self.failed = True
            raise RuntimeError("injected feedback save failure")
        self.data[key] = copy.deepcopy(value)

    def del_data(self, key=None):
        """删除指定插件数据键。"""
        self.data.pop(key, None)


def _board():
    """构造包含两项且 revision 为一的当前榜单。"""
    return RecommendationBoard(
        profile_id=PROFILE_ID,
        run_id="run-1",
        status="success",
        recommendations=[
            RecommendationItem(candidate_id="tmdb:tv:101", rank=1, title="一号"),
            RecommendationItem(candidate_id="tmdb:tv:102", rank=2, title="二号"),
        ],
    )


def _act(service, kind, candidate_id, request_id, **kwargs):
    """用统一默认作用域执行一条反馈动作。"""
    return service.act(
        profile_id=PROFILE_ID,
        candidate_id=candidate_id,
        kind=kind,
        idempotency_key=request_id,
        actor_id="7",
        **kwargs,
    )


def _save_snapshot(repository, candidate_ids=range(101, 109)):
    """保存与当前榜单同 run 的冻结安全候选池。"""
    repository.save_candidate_snapshot(
        CandidateSnapshot.create(
            profile_id=PROFILE_ID,
            run_id="run-1",
            profile_version={"run_id": "run-1", "schema_version": 4},
            retrieval_plan={"media_types": ["tv"]},
            candidates=[
                Candidate(
                    candidate_id=f"tmdb:tv:{candidate_id}",
                    title=f"候选{candidate_id}",
                    media_type="tv",
                    source_ids={"tmdb": str(candidate_id)},
                    sources=["tmdb"],
                    overview=f"候选{candidate_id}简介",
                    genres=["科幻"],
                )
                for candidate_id in candidate_ids
            ],
        )
    )


def test_three_actions_share_one_ledger_and_return_latest_board_revision():
    """三种动作共享 sequence，喜欢保留、忽略移除且都返回最新 revision。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    _save_snapshot(repository)
    service = FeedbackActionService(repository)

    liked = _act(service, "like", "tmdb:tv:101", "like-1")
    repeated = _act(service, "like", "tmdb:tv:101", "like-repeat")
    disliked = _act(service, "dislike", "tmdb:tv:101", "dislike-1")
    ignored = _act(service, "ignore", "tmdb:tv:102", "ignore-1")

    assert liked.created is True
    assert liked.board_revision == 1
    assert repeated.created is False
    assert repeated.event.event_id == liked.event.event_id
    assert disliked.event.supersedes == liked.event.event_id
    assert disliked.board_revision == 2
    assert disliked.refill_count == 4
    assert disliked.current_count == 5
    assert disliked.refill_status == "filled"
    assert ignored.board_revision == 3
    assert ignored.refill_count == 1
    assert ignored.current_count == 5
    assert ignored.board_changed is True
    assert [
        item.candidate_id for item in repository.load_board(PROFILE_ID).recommendations
    ] == [
        "tmdb:tv:103",
        "tmdb:tv:104",
        "tmdb:tv:105",
        "tmdb:tv:106",
        "tmdb:tv:107",
    ]
    assert [event.sequence for event in repository.load_feedback_events(PROFILE_ID)] == [
        1,
        2,
        3,
    ]
    assert ignored.to_dict()["learning_effect"] == "exclusion_only"
    assert ignored.to_dict()["memory_delta"] == {}


@pytest.mark.parametrize(
    ("kind", "candidate_id", "expected_revision"),
    [
        ("like", "tmdb:tv:101", 1),
        ("dislike", "tmdb:tv:101", 2),
        ("ignore", "tmdb:tv:102", 2),
    ],
)
def test_one_hundred_concurrent_duplicate_actions_create_one_event(
    kind, candidate_id, expected_revision
):
    """每种动作 100 个并发重复请求都只生成一个事实和一次榜单变更。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    _save_snapshot(repository)
    services = [FeedbackActionService(AgentRankRepository(plugin)) for _ in range(4)]

    def submit(index):
        """从多个仓储实例并发提交同一幂等动作。"""
        return _act(
            services[index % len(services)],
            kind,
            candidate_id,
            f"same-{kind}",
        )

    with ThreadPoolExecutor(max_workers=24) as executor:
        results = list(executor.map(submit, range(100)))

    events = repository.load_feedback_events(PROFILE_ID)
    assert len(events) == 1
    assert sum(result.created for result in results) == 1
    assert {result.event.event_id for result in results} == {events[0].event_id}
    assert {result.board_revision for result in results} == {expected_revision}
    if kind == "ignore":
        assert len(repository.load_archive(PROFILE_ID).entries) == 1
    if kind in {"dislike", "ignore"}:
        board_ids = {
            item.candidate_id
            for item in repository.load_board(PROFILE_ID).recommendations
        }
        assert candidate_id not in board_ids
        assert len(board_ids) == 5
        assert {result.current_count for result in results} == {5}


def test_idempotency_conflict_and_stale_board_are_rejected_without_new_event():
    """幂等键复用、旧 run 和旧 revision 均不会污染事实账本。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    service = FeedbackActionService(repository)
    _act(service, "like", "tmdb:tv:101", "request-1")

    with pytest.raises(FeedbackActionError) as conflict:
        _act(service, "dislike", "tmdb:tv:101", "request-1")
    assert conflict.value.code == "idempotency_conflict"

    with pytest.raises(FeedbackActionError) as stale_revision:
        _act(
            service,
            "like",
            "tmdb:tv:102",
            "request-2",
            expected_board_revision=9,
        )
    assert stale_revision.value.code == "board_revision_conflict"

    with pytest.raises(FeedbackActionError) as stale_run:
        _act(
            service,
            "like",
            "tmdb:tv:102",
            "request-3",
            expected_run_id="run-old",
        )
    assert stale_run.value.code == "board_run_conflict"
    assert len(repository.load_feedback_events(PROFILE_ID)) == 1


def test_polarity_can_switch_back_and_supersedes_the_latest_fact():
    """喜欢与不喜欢可反复纠正，每次只替代当前最新极性事实。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    service = FeedbackActionService(repository)

    liked = _act(service, "like", "tmdb:tv:101", "like-1")
    disliked = _act(service, "dislike", "tmdb:tv:101", "dislike-1")
    liked_again = _act(service, "like", "tmdb:tv:101", "like-2")
    duplicate = _act(service, "like", "tmdb:tv:101", "like-3")

    assert disliked.event.supersedes == liked.event.event_id
    assert liked_again.created is True
    assert liked_again.event.supersedes == disliked.event.event_id
    assert duplicate.created is False
    assert duplicate.event.event_id == liked_again.event.event_id
    assert [
        event.kind for event in repository.load_feedback_events(PROFILE_ID)
    ] == ["like", "dislike", "like"]


def test_idempotency_key_cannot_cross_explicit_run_or_analysis_context():
    """同一幂等键显式复用于其他榜单或分析时返回冲突。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    service = FeedbackActionService(repository)
    _act(
        service,
        "like",
        "tmdb:tv:101",
        "request-context",
        expected_run_id="run-1",
        analysis_id="analysis-1",
    )

    for kwargs in (
        {"expected_run_id": "run-2", "analysis_id": "analysis-1"},
        {"expected_run_id": "run-1", "analysis_id": "analysis-2"},
    ):
        with pytest.raises(FeedbackActionError) as conflict:
            _act(
                service,
                "like",
                "tmdb:tv:101",
                "request-context",
                **kwargs,
            )
        assert conflict.value.code == "idempotency_conflict"

    assert len(repository.load_feedback_events(PROFILE_ID)) == 1


def test_invalid_idempotency_key_is_rejected_before_ignore_side_effects():
    """非法幂等键在归档前失败，榜单、归档和事件均保持原样。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    before = copy.deepcopy(plugin.data)

    with pytest.raises(FeedbackActionError) as caught:
        _act(
            FeedbackActionService(repository),
            "ignore",
            "tmdb:tv:102",
            "x" * 257,
        )

    assert caught.value.code == "invalid_idempotency_key"
    assert plugin.data == before
    assert repository.load_board(PROFILE_ID).revision == 1
    assert repository.load_archive(PROFILE_ID).entries == []
    assert repository.load_feedback_events(PROFILE_ID) == []


def test_ignore_event_failure_restores_board_archive_and_revision():
    """反馈索引写入失败时回滚业务状态并留下可重试事实。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    before = copy.deepcopy(plugin.data)
    plugin.fail_once_on_key = repository._feedback_index_key(PROFILE_ID)

    with pytest.raises(RuntimeError, match="injected feedback save failure"):
        _act(
            FeedbackActionService(repository),
            "ignore",
            "tmdb:tv:102",
            "ignore-failed",
        )

    comparable = {
        key: value
        for key, value in plugin.data.items()
        if key != repository.recovery_log_key
        and not key.startswith("feedback_event_")
    }
    expected = {
        key: value
        for key, value in before.items()
        if not key.startswith("feedback_event_")
    }
    assert comparable == expected
    assert repository.load_board(PROFILE_ID).revision == 1
    assert repository.load_archive(PROFILE_ID).entries == []
    failed_events = repository.load_feedback_events(PROFILE_ID)
    assert len(failed_events) == 1
    assert failed_events[0].status == "failed_retryable"
    assert failed_events[0].kind == "ignore"


def test_dislike_reports_safe_candidate_insufficient_without_recollecting():
    """冻结池没有额外安全作品时返回实际条数和稳定不足原因。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    _save_snapshot(repository, candidate_ids=(101, 102))

    result = _act(
        FeedbackActionService(repository),
        "dislike",
        "tmdb:tv:101",
        "dislike-insufficient",
    )

    assert result.current_count == 1
    assert result.refill_count == 0
    assert result.refill_status == "safe_candidate_insufficient"
    assert result.to_dict()["reason_code"] == "safe_candidate_insufficient"
    board = repository.load_board(PROFILE_ID)
    assert board.status == "recommendation_incomplete"
    assert "安全候选不足" in board.message
    assert [item.candidate_id for item in board.recommendations] == ["tmdb:tv:102"]


def test_dislike_refill_save_failure_restores_board_archive_and_event_state():
    """补位保存失败时恢复旧状态并保留不影响投影的失败事实。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    _save_snapshot(repository)
    before = copy.deepcopy(plugin.data)
    plugin.fail_once_on_key = repository._profile_key(
        "recommendation_board", PROFILE_ID
    )

    with pytest.raises(RuntimeError, match="injected feedback save failure"):
        _act(
            FeedbackActionService(repository),
            "dislike",
            "tmdb:tv:101",
            "dislike-save-failed",
        )

    comparable = {
        key: value
        for key, value in plugin.data.items()
        if key != repository.recovery_log_key
        and not key.startswith("feedback_event_")
    }
    expected = {
        key: value
        for key, value in before.items()
        if not key.startswith("feedback_event_")
    }
    assert comparable == expected
    assert repository.load_board(PROFILE_ID).revision == 1
    assert repository.load_archive(PROFILE_ID).entries == []
    failed_events = repository.load_feedback_events(PROFILE_ID)
    assert len(failed_events) == 1
    assert failed_events[0].status == "failed_retryable"
    assert failed_events[0].kind == "dislike"
    assert FeedbackActionService(repository).active_polarities(PROFILE_ID, "run-1") == {}


def test_failed_refill_can_retry_with_the_original_idempotency_key():
    """失败事实不占用原请求键，恢复后同一请求可成功且不重复补位。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    _save_snapshot(repository)
    plugin.fail_once_on_key = repository._profile_key(
        "recommendation_board", PROFILE_ID
    )
    service = FeedbackActionService(repository)

    with pytest.raises(RuntimeError, match="injected feedback save failure"):
        _act(service, "dislike", "tmdb:tv:101", "retry-original")
    retried = _act(service, "dislike", "tmdb:tv:101", "retry-original")

    assert retried.created is True
    assert retried.current_count == 5
    assert retried.refill_status == "filled"
    assert [
        (event.status, event.kind)
        for event in repository.load_feedback_events(PROFILE_ID)
    ] == [("failed_retryable", "dislike"), ("recorded", "dislike")]


def test_concurrent_dislike_and_ignore_share_one_refill_transaction_order():
    """并发点踩与忽略串行提交后均不回流且榜单仍恰好五条。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    _save_snapshot(repository)
    services = [
        FeedbackActionService(AgentRankRepository(plugin)),
        FeedbackActionService(AgentRankRepository(plugin)),
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _act, services[0], "dislike", "tmdb:tv:101", "mixed-dislike"
            ),
            executor.submit(
                _act, services[1], "ignore", "tmdb:tv:102", "mixed-ignore"
            ),
        ]
        results = [future.result() for future in futures]

    board = repository.load_board(PROFILE_ID)
    board_ids = [item.candidate_id for item in board.recommendations]
    assert board_ids == [
        "tmdb:tv:103",
        "tmdb:tv:104",
        "tmdb:tv:105",
        "tmdb:tv:106",
        "tmdb:tv:107",
    ]
    assert board.revision == 3
    assert {result.current_count for result in results} == {5}
    assert [entry.candidate_id for entry in repository.load_archive(PROFILE_ID).entries] == [
        "tmdb:tv:102"
    ]
    assert [
        event.sequence for event in repository.load_feedback_events(PROFILE_ID)
    ] == [1, 2]


def test_reappeared_ignored_item_can_be_removed_again_without_duplicate_archive():
    """旧任务把忽略项写回榜单时，新动作会修复残留并 supersede 旧事实。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    service = FeedbackActionService(repository)
    first = _act(service, "ignore", "tmdb:tv:102", "ignore-1")

    board = repository.load_board(PROFILE_ID)
    board.recommendations.append(
        RecommendationItem(candidate_id="tmdb:tv:102", rank=2, title="二号")
    )
    repository.save_board(board)
    repaired = _act(service, "ignore", "tmdb:tv:102", "ignore-2")

    assert repaired.created is True
    assert repaired.event.supersedes == first.event.event_id
    assert repaired.board_revision == 3
    assert len(repository.load_archive(PROFILE_ID).entries) == 1
    assert [
        item.candidate_id for item in repository.load_board(PROFILE_ID).recommendations
    ] == ["tmdb:tv:101"]


def test_restore_reinserts_ignored_item_without_expanding_past_five():
    """忽略补位后恢复原作品会挤出末位补位项而非生成第六条。"""
    plugin = FakePlugin()
    repository = AgentRankRepository(plugin)
    repository.save_board(_board())
    _save_snapshot(repository)
    service = FeedbackActionService(repository)

    _act(service, "ignore", "tmdb:tv:102", "ignore-before-restore")
    restored = service._archive.restore(PROFILE_ID, "tmdb:tv:102")

    assert restored.changed is True
    board = repository.load_board(PROFILE_ID)
    assert [item.candidate_id for item in board.recommendations] == [
        "tmdb:tv:101",
        "tmdb:tv:102",
        "tmdb:tv:103",
        "tmdb:tv:104",
        "tmdb:tv:105",
    ]
    assert [item.rank for item in board.recommendations] == [1, 2, 3, 4, 5]
    assert board.status == "success"
    assert repository.load_archive(PROFILE_ID).entries == []


def test_legacy_board_without_revision_loads_as_revision_one():
    """旧榜单没有 revision 时按一读取且原内容保持可用。"""
    raw = _board().to_dict()
    raw.pop("revision")
    raw["schema_version"] = 2

    restored = RecommendationBoard.from_dict(raw)

    assert restored.revision == 1
    assert restored.schema_version == 2
