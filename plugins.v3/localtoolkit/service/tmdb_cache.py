"""TMDB Redis 缓存清理模块。"""

from __future__ import annotations

import time
from typing import Any, ClassVar

import redis

from app.sdk.config import settings
from app.sdk.logging import logger

from ..security import redact_sensitive_text, safe_error_text
from .base import BaseToolModule


class TmdbCacheModule(BaseToolModule):
    """按需查询和清理 Redis 中的 TMDB 缓存键。"""

    module_key = "tmdb_cache"
    module_name = "清理TMDB"
    _TMDB_CACHE_PATTERNS: ClassVar[tuple[str, ...]] = (
        "app.modules.themoviedb*",
        "__tmdb_cache__*",
        "curetmdbanime:tmdb*",
    )

    def get_default_config(self):
        """返回清理 TMDB 缓存默认配置。"""
        return {"notify": True, "auto_clear": False, "threshold_mb": 50}

    def _redis(self):
        try:
            client = redis.from_url(
                settings.CACHE_BACKEND_URL or "redis://localhost:6379",
                decode_responses=False,
                socket_timeout=5,
            )
            client.ping()
            return client
        except Exception as error:  # noqa: BLE001 - Redis client exposes vendor exceptions
            logger.warning(f"本地工具集：Redis连接失败：{redact_sensitive_text(error)}")
            return None

    def get_service(self):
        """清理 TMDB 缓存只支持手动运行，不注册后台服务。"""
        return []

    def _keys(self, client: Any) -> list[Any] | None:
        """使用传入客户端读取完整键集合；任一模式失败都返回未知。"""
        keys = []
        for pattern in self._TMDB_CACHE_PATTERNS:
            try:
                keys.extend(client.keys(f"region:{pattern}"))
            except Exception as error:  # noqa: BLE001 - Redis client exposes vendor exceptions
                logger.warning(
                    f"本地工具集：查询缓存键失败 pattern={pattern}: {redact_sensitive_text(error)}"
                )
                return None
        return list(set(keys))

    def _status(self, client: Any | None = None, keys: list[Any] | None = None) -> dict:
        """读取键数量和大小；不重新创建客户端，避免前后状态来自不同连接。"""
        client = client or self._redis()
        if not client:
            return {"keys": 0, "size_kb": 0.0, "error": "Redis 未连接"}
        keys = self._keys(client) if keys is None else keys
        if keys is None:
            return {"keys": 0, "size_kb": 0.0, "error": "Redis 缓存键查询失败"}
        total = 0
        for key in keys:
            try:
                dump = client.dump(key)
                total += len(key) + (len(dump) if dump else 0)
            except Exception as error:  # noqa: BLE001 - one key cannot invalidate deletion scope
                logger.warning(f"本地工具集：读取缓存大小失败：{redact_sensitive_text(error)}")
                return {"keys": len(keys), "size_kb": 0.0, "error": "Redis 缓存大小查询失败"}
        return {"keys": len(keys), "size_kb": round(total / 1024, 1), "error": None}

    def get_status(self):
        """返回 TMDB 缓存模块状态。"""
        status = self._status()
        status["run_mode"] = "manual"
        return status

    def run_once(self):
        """执行一次 TMDB 缓存清理。"""
        start = time.time()
        client = self._redis()
        if not client:
            self.add_history("failed", "Redis 未连接", time.time() - start)
            return {"success": False, "message": "Redis 未连接"}

        keys = self._keys(client)
        if keys is None:
            message = safe_error_text("读取 TMDB 缓存键")
            self.add_history("failed", message, time.time() - start)
            return {"success": False, "message": message}
        before = self._status(client, keys)
        if before["error"]:
            message = safe_error_text("读取 TMDB 缓存状态")
            self.add_history("failed", message, time.time() - start)
            return {"success": False, "message": message, "before": before}

        threshold = float(self.config.get("threshold_mb", 50) or 0) * 1024
        if self.config.get("auto_clear") and threshold > 0 and before["size_kb"] < threshold:
            message = f"缓存 {before['size_kb'] / 1024:.2f}MB 未超过阈值 {self.config.get('threshold_mb')}MB"
            self.add_history("success", message, time.time() - start)
            if self.config.get("notify", True):
                self.send_notification("本地工具集 - 清理TMDB", message)
            return {"success": True, "message": message, "deleted": 0}

        try:
            deleted = client.delete(*keys) if keys else 0
        except Exception as error:  # noqa: BLE001 - Redis client exposes vendor exceptions
            logger.error(f"本地工具集：清理TMDB缓存失败：{redact_sensitive_text(error)}")
            message = safe_error_text("清理 TMDB 缓存")
            self.add_history("failed", message, time.time() - start)
            if self.config.get("notify", True):
                self.send_notification("本地工具集 - 清理TMDB", message)
            return {"success": False, "message": message}

        after = self._status(client)
        payload = {"before": before, "after": after, "deleted": deleted}
        self.plugin.save_data(key="tmdb_cache_result", value=payload)
        if after["error"]:
            message = safe_error_text("核验 TMDB 缓存清理结果")
            self.add_history("failed", message, time.time() - start)
            return {"success": False, "message": message, **payload}

        summary = f"清理 TMDB 缓存 {deleted}/{len(keys)} 个，清理后 {after['keys']} 个键"
        logger.info("本地工具集：" + summary)
        self.add_history("success", summary, time.time() - start)
        if self.config.get("notify", True):
            self.send_notification("本地工具集 - 清理TMDB", summary)
        return {
            "success": True,
            "deleted": deleted,
            "total": len(keys),
            "before": before,
            "after": after,
            "message": summary,
        }
