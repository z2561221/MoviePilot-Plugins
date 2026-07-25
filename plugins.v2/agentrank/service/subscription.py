"""AgentRank 单项手动订阅安全服务。"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..model.candidate import Candidate, typed_tmdb_candidate_id
from ..storage.repository import AgentRankRepository


SUBSCRIPTION_USERNAME = "Agent榜单中心"


@dataclass
class ManualSubscriptionResult:
    """表示手动订阅安全链结果。"""

    success: bool
    changed: bool
    code: str
    message: str
    subscription_id: Optional[int] = None


@dataclass
class BatchSubscriptionResult:
    """表示自动 Top-N 逐项订阅的汇总结果。"""

    status: str
    items: List[ManualSubscriptionResult]
    success_count: int = 0
    failure_count: int = 0


class SubscriptionService:
    """执行榜单、快照、归档、置信度、识别与重复安全闸。"""

    def __init__(
        self,
        repository: AgentRankRepository,
        subscribe_chain: Any = None,
        media_factory: Callable[..., Any] = None,
        media_type_factory: Callable[[str], Any] = None,
        subscription_adapter: Any = None,
    ):
        """允许测试注入宿主订阅链和媒体类型工厂。"""
        use_default_chain = subscribe_chain is None
        self._repository = repository
        self._subscribe_chain = subscribe_chain or self._default_subscribe_chain()
        self._media_factory = media_factory or self._default_media_factory()
        self._media_type_factory = media_type_factory or self._default_media_type
        self._subscription_adapter = subscription_adapter
        if self._subscription_adapter is None and use_default_chain:
            self._subscription_adapter = self._default_subscription_adapter()

    @staticmethod
    def _default_subscribe_chain() -> Any:
        """创建当前 MoviePilot SubscribeChain。"""
        from app.chain.subscribe import SubscribeChain

        return SubscribeChain()

    @staticmethod
    def _default_media_factory() -> Callable[..., Any]:
        """返回当前 MoviePilot MediaInfo 类。"""
        from app.core.context import MediaInfo

        return MediaInfo

    @staticmethod
    def _default_subscription_adapter() -> Any:
        """创建跨全部用户名的订阅读取适配器。"""
        from ..adapter.subscription import SubscriptionAdapter

        return SubscriptionAdapter()

    @staticmethod
    def _default_media_type(value: str) -> Any:
        """把规范化类型映射为 MoviePilot MediaType。"""
        from app.schemas.types import MediaType

        if value == "movie":
            return MediaType.MOVIE
        return MediaType.TV

    @staticmethod
    def _candidate_media_type(candidate: Candidate) -> str:
        """优先使用识别阶段保存的 MoviePilot 基础类型。"""
        media_type = str(candidate.metadata.get("mp_media_type") or "").strip()
        if media_type in {"电影", "movie"}:
            return "movie"
        if media_type in {"电视剧", "tv"}:
            return "tv"
        return "movie" if candidate.media_type == "movie" else "tv"

    @staticmethod
    def _integer(value: Any) -> Optional[int]:
        """安全转换可选整数媒体标识。"""
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _identifier_kwargs(cls, candidate: Candidate) -> Dict[str, Any]:
        """把候选来源 ID 映射为 SubscribeChain.add 参数。"""
        ids = dict(candidate.source_ids or {})
        kwargs: Dict[str, Any] = {
            "tmdbid": cls._integer(ids.get("tmdb")),
            "doubanid": str(ids.get("douban")) if ids.get("douban") else None,
            "bangumiid": cls._integer(ids.get("bangumi")),
        }
        if not any(kwargs.values()):
            for prefix, media_id in ids.items():
                if prefix not in {"tmdb", "douban", "bangumi", "tvdb", "imdb"} and media_id:
                    kwargs["mediaid"] = f"{prefix}:{media_id}"
                    break
        return {key: value for key, value in kwargs.items() if value not in (None, "")}

    @staticmethod
    def _candidate_identity(candidate: Candidate) -> Optional[str]:
        """返回候选可证明的类型化 TMDB 身份，旧快照也可安全兼容。"""
        try:
            return typed_tmdb_candidate_id(
                candidate.candidate_id,
                candidate.media_type,
                candidate.metadata.get("mp_media_type"),
            )
        except ValueError:
            try:
                return typed_tmdb_candidate_id(
                    candidate.source_ids.get("tmdb"),
                    candidate.media_type,
                    candidate.metadata.get("mp_media_type"),
                )
            except ValueError:
                return None

    def _globally_subscribed(self, candidate: Candidate) -> Optional[bool]:
        """按媒体身份检查所有用户名下的订阅；无法检查时闭锁。"""
        if self._subscription_adapter is None:
            return False
        candidate_id = self._candidate_identity(candidate)
        if candidate_id is None:
            return False
        try:
            return candidate_id in self._subscription_adapter.candidate_ids()
        except Exception as error:
            raise RuntimeError("global subscription duplicate check unavailable") from error

    @staticmethod
    def _failure(code: str, message: str) -> ManualSubscriptionResult:
        """构造未改变状态的失败结果。"""
        return ManualSubscriptionResult(False, False, code, message)

    def subscribe(
        self, profile_id: str, candidate_id: str, confidence_threshold: float
    ) -> ManualSubscriptionResult:
        """按稳定画像身份执行单项订阅的完整安全链。"""
        board = self._repository.load_board(profile_id)
        if board is None or board.profile_id != profile_id:
            return self._failure("board_unavailable", "当前用户没有可用榜单")
        item = next(
            (
                recommendation
                for recommendation in board.recommendations
                if recommendation.candidate_id == candidate_id
            ),
            None,
        )
        if item is None:
            return self._failure("candidate_not_in_board", "候选不在当前榜单中")
        candidates = self._repository.load_candidate_snapshot(board.run_id, profile_id)
        candidate = next(
            (value for value in candidates if value.candidate_id == candidate_id), None
        )
        if candidate is None:
            return self._failure(
                "candidate_not_in_snapshot", "候选不属于当前榜单绑定的发现快照"
            )
        archive = self._repository.load_archive(profile_id)
        if any(entry.candidate_id == candidate_id for entry in archive.entries):
            return self._failure("candidate_archived", "候选已被当前用户归档")
        threshold = float(confidence_threshold or 0.0)
        threshold = threshold * 100 if threshold <= 1 else threshold
        if float(item.confidence) < threshold:
            return self._failure(
                "confidence_below_threshold", "候选置信度低于当前安全阈值"
            )
        identifiers = self._identifier_kwargs(candidate)
        if not identifiers:
            return self._failure("candidate_unrecognizable", "候选缺少可识别媒体 ID")
        try:
            if self._globally_subscribed(candidate):
                return ManualSubscriptionResult(
                    True, False, "already_subscribed", "订阅已存在"
                )
        except Exception:
            return self._failure(
                "subscription_duplicate_check_failed",
                "全局订阅查重不可用，未创建订阅",
            )
        media_type = self._media_type_factory(self._candidate_media_type(candidate))
        media = self._media_factory(
            title=candidate.title,
            year=str(candidate.year or ""),
            type=media_type,
            tmdb_id=identifiers.get("tmdbid"),
            douban_id=identifiers.get("doubanid"),
            bangumi_id=identifiers.get("bangumiid"),
        )
        if self._subscribe_chain.exists(media):
            return ManualSubscriptionResult(
                True, False, "already_subscribed", "订阅已存在"
            )
        subscription_id, message = self._subscribe_chain.add(
            title=candidate.title,
            year=str(candidate.year or ""),
            mtype=media_type,
            username=SUBSCRIPTION_USERNAME,
            message=False,
            exist_ok=False,
            **identifiers,
        )
        if not subscription_id:
            return ManualSubscriptionResult(
                False,
                False,
                "subscription_failed",
                str(message or "订阅创建失败"),
            )
        return ManualSubscriptionResult(
            True,
            True,
            "subscription_created",
            str(message or "订阅创建成功"),
            int(subscription_id),
        )

    def subscribe_top_n(
        self,
        profile_id: str,
        top_n: int,
        configured_limit: int,
        confidence_threshold: float,
    ) -> BatchSubscriptionResult:
        """按榜单排名逐项执行同一套安全链，单项失败不中断后续项。"""
        requested = int(top_n or 0)
        limit = max(0, min(int(configured_limit or 0), 10))
        if requested <= 0:
            return BatchSubscriptionResult("disabled", [])
        if requested > limit or requested > 10:
            return BatchSubscriptionResult("invalid_limit", [], 0, requested)
        board = self._repository.load_board(profile_id)
        if board is None:
            return BatchSubscriptionResult("subscription_partial_failed", [], 0, requested)
        ranked_items = sorted(
            board.recommendations, key=lambda item: (item.rank, item.candidate_id)
        )[:requested]
        results: List[ManualSubscriptionResult] = []
        for item in ranked_items:
            try:
                result = self.subscribe(
                    profile_id, item.candidate_id, confidence_threshold
                )
            except Exception as error:
                result = ManualSubscriptionResult(
                    False,
                    False,
                    "subscription_failed",
                    str(error),
                )
            results.append(result)
        success_count = sum(1 for item in results if item.success)
        failure_count = len(results) - success_count + max(0, requested - len(results))
        status = "success" if failure_count == 0 else "subscription_partial_failed"
        return BatchSubscriptionResult(
            status=status,
            items=results,
            success_count=success_count,
            failure_count=failure_count,
        )
