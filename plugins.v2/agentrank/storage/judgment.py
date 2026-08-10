"""AgentRank 初赛批次检查点的隔离持久化存储。"""

import re
import threading
from typing import Any, Optional
from urllib.parse import quote

from ..model.judgment import JudgmentBatchCheckpoint


_SAFE_FINGERPRINT = re.compile(r"^[a-f0-9]{64}$")


class JudgmentCheckpointStore:
    """通过插件数据后端保存成功批次，不改动主仓储的用户工作树。"""

    _lock = threading.RLock()

    def __init__(self, repository: Any):
        """复用仓储持有的插件数据后端并保持存储边界独立。"""
        plugin = getattr(repository, "_plugin", None)
        if plugin is None:
            raise ValueError("judgment checkpoint store requires repository backend")
        self._plugin = plugin

    @staticmethod
    def _key(profile_id: str, idempotency_key: str) -> str:
        """构造画像与完整输入指纹隔离的插件数据键。"""
        profile = quote(str(profile_id or "").strip(), safe="@._-")
        key = str(idempotency_key or "").strip().casefold()
        if not profile or not _SAFE_FINGERPRINT.fullmatch(key):
            raise ValueError("judgment checkpoint scope is invalid")
        return f"judgment_batch:profile:{profile}:key:{key}"

    def load(
        self, profile_id: str, idempotency_key: str
    ) -> Optional[JudgmentBatchCheckpoint]:
        """读取同画像和完整指纹绑定的成功批次。"""
        key = self._key(profile_id, idempotency_key)
        value = self._plugin.get_data(key=key)
        if value is None:
            return None
        try:
            checkpoint = JudgmentBatchCheckpoint.from_dict(value)
        except (TypeError, ValueError, KeyError):
            return None
        if (
            checkpoint.profile_id != str(profile_id)
            or checkpoint.idempotency_key != str(idempotency_key)
        ):
            return None
        return checkpoint

    def save(self, checkpoint: JudgmentBatchCheckpoint) -> JudgmentBatchCheckpoint:
        """幂等保存并回读；同 key 不允许覆盖不同判断。"""
        key = self._key(checkpoint.profile_id, checkpoint.idempotency_key)
        with self._lock:
            existing = self.load(
                checkpoint.profile_id, checkpoint.idempotency_key
            )
            if existing is not None:
                if not existing.same_content(checkpoint):
                    raise RuntimeError("judgment checkpoint idempotency conflict")
                return existing
            self._plugin.save_data(key=key, value=checkpoint.to_dict())
            saved = self.load(checkpoint.profile_id, checkpoint.idempotency_key)
            if saved is None or not saved.same_content(checkpoint):
                raise RuntimeError("judgment checkpoint readback failed")
            return saved
