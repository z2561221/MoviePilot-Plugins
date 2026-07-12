"""旧榜单失效海报修复服务。"""

import base64
import logging
from typing import Any, Callable, Dict, Iterable

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
        """判断海报是否为空或来自会触发防盗链的豆瓣域名。"""
        value = str(poster_path or "").lower()
        return not value or "doubanio.com" in value

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
    """通过 MoviePilot 图片缓存生成浏览器可直接显示的内联海报。"""

    def __init__(self, fetcher: Callable[[str], bytes] = None):
        """允许测试注入图片读取器，运行时使用 MoviePilot ImageHelper。"""
        self._fetcher = fetcher or self._fetch_image
        self._cache: Dict[str, str] = {}

    @staticmethod
    def _fetch_image(url: str) -> bytes:
        """通过 MoviePilot 图片助手下载并缓存海报。"""
        from app.helper.image import ImageHelper

        return ImageHelper().fetch_image(url=url, use_cache=True) or b""

    @staticmethod
    def _content_type(content: bytes, url: str) -> str:
        """按图片魔数和 URL 后缀推断内联媒体类型。"""
        if content.startswith(b"\x89PNG"):
            return "image/png"
        if content.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if content.startswith(b"RIFF") and b"WEBP" in content[:16]:
            return "image/webp"
        if str(url).lower().endswith(".webp"):
            return "image/webp"
        return "image/jpeg"

    def data_url(self, url: str) -> str:
        """返回缓存的 data URL，读取失败时返回空字符串。"""
        source = str(url or "").strip()
        if not source:
            return ""
        if source.startswith("data:image/"):
            return source
        if source in self._cache:
            return self._cache[source]
        try:
            content = self._fetcher(source)
        except Exception as error:
            logger.warning("AgentRank 海报缓存失败 url=%s reason=%s", source, error)
            content = b""
        if not content:
            self._cache[source] = ""
            return ""
        encoded = base64.b64encode(content).decode("ascii")
        result = f"data:{self._content_type(content, source)};base64,{encoded}"
        self._cache[source] = result
        return result

    def enrich_board(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """把榜单响应中的外部海报替换为内联缓存图片。"""
        for item in value.get("recommendations") or []:
            item["poster_path"] = self.data_url(item.get("poster_path"))
        return value
