"""AgentRank 榜单生成实时进度存储测试。"""

import importlib
import sys
from pathlib import Path
from types import ModuleType


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_run_progress_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

progress_module = importlib.import_module(f"{PACKAGE_NAME}.service.run_progress")
RunProgressStore = progress_module.RunProgressStore


def test_progress_is_isolated_by_profile_and_tracks_real_stage_order():
    """不同画像互不污染，并按七段编排返回稳定序号。"""
    store = RunProgressStore()

    first = store.begin("emby:home:one")
    running = store.update(
        "emby:home:one",
        {"run_id": "run-1", "stage": "ranking"},
    )
    other = store.snapshot("emby:home:two", username="Bob")

    assert first["status"] == "queued"
    assert first["active"] is True
    assert running["stage_index"] == 6
    assert running["stage_total"] == 7
    assert running["message"] == "克里斯蒂娜 正在分析候选"
    assert running["agent_active"] is True
    assert other["status"] == "idle"
    assert other["username"] == "Bob"


def test_progress_finish_and_stop_all_leave_reconnectable_terminal_snapshot():
    """完成和停止后保留最终快照，但不再被前端视为活动任务。"""
    store = RunProgressStore()
    store.begin("emby:home:one")
    store.update("emby:home:one", {"run_id": "run-1", "stage": "save"})
    finished = store.finish(
        "emby:home:one",
        status="success",
        message="榜单生成成功",
        final_count=5,
    )
    store.begin("emby:home:two")
    store.stop_all()
    stopped = store.snapshot("emby:home:two")

    assert finished["active"] is False
    assert finished["stage_index"] == 7
    assert finished["final_count"] == 5
    assert finished["finished_at"]
    assert stopped["status"] == "stopped"
    assert stopped["active"] is False
