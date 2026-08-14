"""榜单生成实时进度的运行期存储。"""

import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from .prompt import AGENT_DISPLAY_NAME_DEFAULT


RUN_STAGE_ORDER = (
    "probe",
    "playback_snapshot",
    "policy",
    "profile",
    "candidate",
    "ranking",
    "save",
)

RUN_STAGE_MESSAGES = {
    "queued": "正在准备生成榜单",
    "probe": "正在检查播放数据",
    "playback_snapshot": "正在同步播放记录",
    "policy": "正在整理偏好策略",
    "profile": f"{AGENT_DISPLAY_NAME_DEFAULT} 正在更新用户画像",
    "candidate": "正在收集并筛选候选",
    "ranking": f"{AGENT_DISPLAY_NAME_DEFAULT} 正在分析候选",
    "save": "正在校验并保存榜单",
}

ACTIVE_PROGRESS_STATUSES = {"queued", "running"}


def _now() -> str:
    """返回稳定 UTC 时间文本。"""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunProgressSnapshot:
    """表示一个画像身份当前可公开的榜单生成进度。"""

    profile_id: str
    run_id: str = ""
    status: str = "idle"
    stage: str = ""
    stage_index: int = 0
    stage_total: int = len(RUN_STAGE_ORDER)
    message: str = "尚未生成榜单"
    started_at: str = ""
    updated_at: str = ""
    finished_at: str = ""
    final_count: int = 0
    revision: int = 0

    def to_public_dict(self, username: str = "") -> Dict[str, Any]:
        """返回不含内部载荷的前端进度字典。"""
        value = asdict(self)
        value["username"] = str(username or "")
        value["active"] = self.status in ACTIVE_PROGRESS_STATUSES
        value["agent_active"] = self.stage in {"profile", "ranking"}
        return value


class RunProgressStore:
    """按画像隔离保存页面刷新后仍可读取的运行期进度。"""

    def __init__(self, agent_name: str = AGENT_DISPLAY_NAME_DEFAULT) -> None:
        """创建空进度表并初始化并发保护。"""
        self._values: Dict[str, RunProgressSnapshot] = {}
        self._lock = threading.RLock()
        self._agent_name = (
            " ".join(str(agent_name or "").split()).strip()[:64]
            or AGENT_DISPLAY_NAME_DEFAULT
        )

    def _stage_message(self, stage: str) -> str:
        """返回带用户配置名称的进度文案；默认文案保持兼容。"""
        if self._agent_name == AGENT_DISPLAY_NAME_DEFAULT:
            return RUN_STAGE_MESSAGES.get(stage, "正在生成榜单")
        if stage == "profile":
            return f"{self._agent_name} 正在更新用户画像"
        if stage == "ranking":
            return f"{self._agent_name} 正在分析候选"
        return RUN_STAGE_MESSAGES.get(stage, "正在生成榜单")

    @staticmethod
    def _profile_id(profile_id: Any) -> str:
        """规范化并校验画像身份。"""
        target = str(profile_id or "").strip()
        if not target:
            raise ValueError("run progress profile_id is required")
        return target

    @staticmethod
    def _stage_index(stage: str) -> int:
        """返回当前阶段的一基序号。"""
        try:
            return RUN_STAGE_ORDER.index(stage) + 1
        except ValueError:
            return 0

    def begin(self, profile_id: Any) -> Dict[str, Any]:
        """登记一次后台运行；已有活动运行时保持原进度。"""
        target = self._profile_id(profile_id)
        with self._lock:
            current = self._values.get(target)
            if current is not None and current.status in ACTIVE_PROGRESS_STATUSES:
                return current.to_public_dict()
            revision = int(getattr(current, "revision", 0) or 0) + 1
            now = _now()
            current = RunProgressSnapshot(
                profile_id=target,
                status="queued",
                message=self._stage_message("queued"),
                started_at=now,
                updated_at=now,
                revision=revision,
            )
            self._values[target] = current
            return current.to_public_dict()

    def update(self, profile_id: Any, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """用编排器提供的安全阶段信息更新活动进度。"""
        target = self._profile_id(profile_id)
        data = dict(payload or {})
        stage = str(data.get("stage") or "").strip()
        with self._lock:
            current = self._values.get(target)
            if current is None or current.status not in ACTIVE_PROGRESS_STATUSES:
                self.begin(target)
                current = self._values[target]
            current.status = "running"
            current.run_id = str(data.get("run_id") or current.run_id or "")
            current.stage = stage
            current.stage_index = self._stage_index(stage)
            current.message = str(
                data.get("message")
                or self._stage_message(stage)
            )[:120]
            current.updated_at = _now()
            return current.to_public_dict()

    def finish(
        self,
        profile_id: Any,
        *,
        status: str,
        run_id: str = "",
        message: str = "",
        final_count: int = 0,
    ) -> Dict[str, Any]:
        """完成当前运行并保留一个可重连读取的最终快照。"""
        target = self._profile_id(profile_id)
        with self._lock:
            current = self._values.get(target)
            if current is None:
                self.begin(target)
                current = self._values[target]
            now = _now()
            current.status = str(status or "failed")
            current.run_id = str(run_id or current.run_id or "")
            current.message = str(message or "榜单生成已结束")[:120]
            current.final_count = max(0, int(final_count or 0))
            current.updated_at = now
            current.finished_at = now
            return current.to_public_dict()

    def snapshot(self, profile_id: Any, username: str = "") -> Dict[str, Any]:
        """返回指定画像当前进度或显式空状态。"""
        target = self._profile_id(profile_id)
        with self._lock:
            current = self._values.get(target)
            if current is None:
                current = RunProgressSnapshot(profile_id=target)
            return current.to_public_dict(username)

    def stop_all(self) -> None:
        """把停止时仍活动的任务收束为已停止状态。"""
        with self._lock:
            targets = [
                profile_id
                for profile_id, value in self._values.items()
                if value.status in ACTIVE_PROGRESS_STATUSES
            ]
        for profile_id in targets:
            self.finish(profile_id, status="stopped", message="榜单生成已停止")
