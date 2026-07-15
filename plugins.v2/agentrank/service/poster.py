"""旧榜单失效海报修复服务。"""

import logging
import re
from functools import lru_cache
from typing import Any, Dict, Iterable

from ..model.candidate import Candidate


logger = logging.getLogger(__name__)


class BoardPosterRepairService:
    """使用 MoviePilot 识别结果替换旧榜单中的失效来源海报。"""

    def __init__(self, repository: Any, media_adapter: Any):
        """绑定榜单仓库与媒体识别适配器。"""
        self._repository = repository
        self._media_adapter = media_adapter

    @staticmethod
    def _needs_repair(poster_path: str) -> bool:
        """判断海报是否为空、内联或来自会触发防盗链的豆瓣域名。"""
        value = str(poster_path or "").lower()
        return (
            not value
            or value.startswith("data:image/")
            or "doubanio.com" in value
        )

    def repair_users(self, usernames: Iterable[str]) -> Dict[str, int]:
        """按用户修复旧榜单海报并返回每个用户的更新数量。"""
        results: Dict[str, int] = {}
        for raw_username in usernames:
            username = str(raw_username or "").strip()
            if not username:
                continue
            board = self._repository.load_board(username)
            if board is None:
                continue
            repaired = 0
            for item in board.recommendations:
                if not self._needs_repair(item.poster_path):
                    continue
                candidate = Candidate(
                    candidate_id=item.candidate_id,
                    title=item.title,
                    media_type=item.media_type,
                    year=item.year,
                    source_ids=dict(item.source_ids),
                    sources=list(item.sources),
                    poster_path=item.poster_path,
                )
                try:
                    recognized = self._media_adapter.recognize(candidate)
                except Exception as error:
                    logger.warning(
                        "AgentRank 海报修复失败 user=%s candidate=%s reason=%s",
                        username,
                        item.candidate_id,
                        error,
                    )
                    continue
                if not recognized or not recognized.poster_path:
                    continue
                if self._needs_repair(recognized.poster_path):
                    continue
                item.poster_path = recognized.poster_path
                repaired += 1
            if repaired:
                self._repository.save_board(board)
                logger.info(
                    "AgentRank 旧榜单海报修复 user=%s repaired=%s",
                    username,
                    repaired,
                )
            results[username] = repaired
        return results


class PosterImageService:
    """把榜单海报收敛为浏览器可直接加载的轻量图片地址。"""

    _TMDB_POSTER_PATTERN = re.compile(
        r"^(https://image\.tmdb\.org/t/p/)(?:original|w\d+)(/.*)$",
        re.IGNORECASE,
    )

    @staticmethod
    @lru_cache(maxsize=512)
    def thumbnail_url(url: str) -> str:
        """返回至多 w200 的海报地址并拒绝高内存内联图片。"""
        source = str(url or "").strip()
        if not source:
            return ""
        lowered = source.lower()
        if lowered.startswith("data:image/") or "doubanio.com" in lowered:
            return ""
        return PosterImageService._TMDB_POSTER_PATTERN.sub(
            r"\1w200\2", source
        )

    def enrich_board(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """把榜单响应中的海报替换为轻量 URL，避免 JSON 内嵌原图。"""
        for item in value.get("recommendations") or []:
            item["poster_path"] = self.thumbnail_url(item.get("poster_path"))
        return value
