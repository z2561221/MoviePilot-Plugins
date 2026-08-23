"""Agent 榜单通知确认服务。"""

import hashlib
import json
import logging
import re
from typing import Any, Optional

from app.schemas.types import MessageType

from ..model.board import RecommendationBoard
from ..model.constants import RECOMMENDATION_LIMIT
from ..model.pending_center import PendingNotice
from .notification_type import resolve_notification_type
from .prompt import AGENT_DISPLAY_NAME_DEFAULT, configured_agent_display_name


logger = logging.getLogger(__name__)


STATUS_LABELS = {
    "playback_unavailable": "播放数据不可用",
    "emby_unavailable": "Emby 不可用",
    "permission_error": "权限不足",
    "transient_error": "临时错误",
    "configuration_error": "配置错误",
    "sample_insufficient": "播放样本不足",
    "candidate_insufficient": "候选数量不足",
    "recommendation_incomplete": "推荐榜单不足",
    "recommendation_degraded": "推荐榜单已降级",
    "profile_agent_failed": "画像 Agent 调用失败",
    "profile_validation_failed": "画像输出校验失败",
    "profile_save_failed": "画像保存失败",
    "policy_superseded": "偏好已更新，策略已过期",
    "candidate_failed": "候选采集失败",
    "candidate_filter_failed": "候选过滤失败",
    "candidate_snapshot_failed": "候选快照失败",
    "ranking_agent_failed": "排序 Agent 调用失败",
    "ranking_validation_failed": "排序输出校验失败",
    "ranking_save_failed": "榜单保存失败",
    "subscription_partial_failed": "部分订阅失败",
    "runtime_exception": "运行异常",
    "playback_reporting": "播放记录服务",
    "validation_failed": "输出校验失败",
    "agent_failed": "Agent 调用失败",
    "failed": "运行失败",
}

PENDING_TYPE_LABELS = {
    "proposal": "偏好理解",
    "question": "需要补充",
    "command": "操作确认",
}

_EXPLICIT_FEEDBACK_KINDS = frozenset(
    {"like", "dislike", "neutral", "ignore", "analysis_comment", "correction"}
)
_NOTIFICATION_SENT = "sent"
_NOTIFICATION_SUPPRESSED = "suppressed_unacted_duplicate"


def _safe_notice_text(value: Any) -> str:
    """移除异常消息中的地址、凭据与稳定 Emby 身份细节。"""
    text = str(value or "")
    text = re.sub(r"https?://[^\s,;]+", "[地址已隐藏]", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b",
        "[地址已隐藏]",
        text,
    )
    text = re.sub(r"\bemby:[^\s,;]+", "[Emby身份已隐藏]", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b(?:api[_ -]?key|token|password|authorization|user[_ -]?id|userid|host|address|base[_ -]?url)\s*[:=]\s*[^\s,;]+",
        "[敏感信息已隐藏]",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _compact_text(value: Any, limit: int) -> str:
    """压缩通知字段中的空白并限制长度，避免榜单列被异常文本撑开。"""
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _format_ranking_block(board: RecommendationBoard) -> str:
    """将固定榜单数量内的推荐格式化为 Telegram 等宽 Markdown 代码块。"""
    lines = []
    for item in board.recommendations[:RECOMMENDATION_LIMIT]:
        title = _compact_text(item.title, 42) or "未命名条目"
        summary = _compact_text(item.summary, 64) or "暂无推荐摘要"
        reason = _compact_text(getattr(item, "reason", ""), 32) or summary
        lines.extend(
            [
                f"{int(item.rank):02d} │ {title}",
                f"   │ 推荐：{reason}",
                f"   │ 简介：{summary}",
            ]
        )
    return "```\n" + "\n".join(lines) + "\n```"


def _recommendation_fingerprint(board: RecommendationBoard) -> str:
    """按候选集合生成忽略排序变化的榜单指纹。"""
    candidate_ids = sorted(
        {
            str(item.candidate_id or "").strip()
            for item in (board.recommendations or [])[:RECOMMENDATION_LIMIT]
            if str(item.candidate_id or "").strip()
        }
    )
    payload = json.dumps(candidate_ids, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class NotificationService:
    """优先发送 Telegram 自选订阅卡片，并保留摘要降级。"""

    def __init__(self, plugin: Any, interaction_service: Any = None):
        """绑定插件通知扩展点与可选 Telegram 交互服务。"""
        self._plugin = plugin
        self._interaction_service = interaction_service

    def _agent_name(self) -> str:
        """读取当前配置的用户可见 Agent 名称。"""
        return configured_agent_display_name(
            getattr(self._plugin, "_config", {}).get(
                "agent_display_name", AGENT_DISPLAY_NAME_DEFAULT
            )
        )

    def _repository(self) -> Optional[Any]:
        """返回可选的 AgentRank 仓库；缺少仓库时跳过历史去重。"""
        repository = getattr(self._plugin, "_repository", None)
        if repository is None or not callable(
            getattr(repository, "load_run_history", None)
        ):
            return None
        return repository

    @staticmethod
    def _has_explicit_feedback(repository: Any, profile_id: str, run_id: str) -> bool:
        """判断指定榜单是否已有明确操作，不把无操作当成负向事实。"""
        load_events = getattr(repository, "load_feedback_events", None)
        if not callable(load_events):
            return False
        try:
            events = load_events(profile_id)
        except Exception:
            logger.exception(
                "AgentRank 读取榜单反馈失败，按未反馈处理 profile_id=%s run_id=%s",
                profile_id,
                run_id,
            )
            return False
        return any(
            str(getattr(event, "run_id", "") or "") == run_id
            and str(getattr(event, "status", "") or "") == "recorded"
            and str(getattr(event, "kind", "") or "") in _EXPLICIT_FEEDBACK_KINDS
            for event in events or ()
        )

    def _notification_state(
        self, board: RecommendationBoard, fingerprint: str
    ) -> str:
        """读取当前或上一份相同榜单的通知状态。"""
        repository = self._repository()
        if repository is None:
            return ""
        try:
            history = repository.load_run_history(board.profile_id)
        except Exception:
            logger.exception(
                "AgentRank 读取通知历史失败，跳过重复榜单抑制 profile_id=%s",
                board.profile_id,
            )
            return ""
        for run in history:
            run_id = str(getattr(run, "run_id", "") or "")
            metrics = dict(getattr(run, "metrics", {}) or {})
            if run_id == str(board.run_id or ""):
                if metrics.get("recommendation_notification_fingerprint") == fingerprint:
                    return str(metrics.get("recommendation_notification_status") or "")
                continue
            if (
                metrics.get("recommendation_notification_fingerprint") != fingerprint
                or metrics.get("recommendation_notification_status") != _NOTIFICATION_SENT
            ):
                continue
            if self._has_explicit_feedback(repository, board.profile_id, run_id):
                return ""
            return _NOTIFICATION_SUPPRESSED
        return ""

    def _record_notification_state(
        self, board: RecommendationBoard, fingerprint: str, status: str
    ) -> None:
        """把通知发送或抑制结果写入本轮运行指标。"""
        repository = self._repository()
        annotate_run = getattr(repository, "annotate_run", None) if repository else None
        if not callable(annotate_run) or not board.run_id:
            return
        try:
            annotate_run(
                profile_id=board.profile_id,
                run_id=board.run_id,
                status=str(board.status or "success"),
                metrics={
                    "recommendation_notification_fingerprint": fingerprint,
                    "recommendation_notification_status": status,
                },
            )
        except Exception:
            logger.exception(
                "AgentRank 写入通知状态失败 profile_id=%s run_id=%s",
                board.profile_id,
                board.run_id,
            )

    def send_confirmation(self, username: str, board: RecommendationBoard) -> bool:
        """发送榜单通知；无反馈的同榜单只发送一次。"""
        fingerprint = _recommendation_fingerprint(board)
        state = self._notification_state(board, fingerprint)
        if state in {_NOTIFICATION_SENT, _NOTIFICATION_SUPPRESSED}:
            if state == _NOTIFICATION_SUPPRESSED:
                self._record_notification_state(board, fingerprint, state)
            return state == _NOTIFICATION_SENT
        if self._interaction_service is not None:
            try:
                if self._interaction_service.start(board.profile_id, username, board):
                    self._record_notification_state(
                        board, fingerprint, _NOTIFICATION_SENT
                    )
                    return True
            except Exception:
                # Telegram 交互异常不得阻断榜单通知的摘要降级路径。
                logger.exception(
                    "AgentRank Telegram 交互通知失败，回退摘要 user=%s", username
                )
        ranking = _format_ranking_block(board)
        count = len(board.recommendations[:RECOMMENDATION_LIMIT])
        agent_name = self._agent_name()
        text = f"本轮 {agent_name} 推荐已生成，共 {count} 条：\n\n{ranking}"
        text += f"\n\n请前往 **{agent_name}** 手动订阅；此通知不会自动创建订阅。"
        self._plugin.post_message(
            mtype=resolve_notification_type(
                getattr(self._plugin, "_config", {}), MessageType
            ),
            title=f"{agent_name}推荐确认",
            text=text,
            username=username,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )
        self._record_notification_state(board, fingerprint, _NOTIFICATION_SENT)
        return True

    def send_failure(
        self,
        username: str,
        status: str,
        run_id: str,
        message: str,
        old_board_preserved: bool,
    ) -> None:
        """向目标用户发送一次简洁的 Agent 运行异常通知。"""
        reason = _compact_text(_safe_notice_text(message), 240) or "未知异常"
        lines = [
            f"状态：{STATUS_LABELS.get(str(status or ''), '运行异常')}",
            f"运行 ID：{_compact_text(run_id, 64) or '未生成'}",
            f"原因：{reason}",
            "旧榜单：已保留" if old_board_preserved else "旧榜单：无可用数据",
        ]
        self._plugin.post_message(
            mtype=resolve_notification_type(
                getattr(self._plugin, "_config", {}), MessageType
            ),
            title=f"{self._agent_name()}运行异常",
            text="\n".join(lines),
            username=username,
        )

    def _pending_detail_link(self) -> Any:
        """返回待处理中心深链；未配置外部域名时交给宿主默认详情链接。"""
        try:
            from app.sdk.config import settings

            plugin_id = self._plugin.__class__.__name__
            return settings.MP_DOMAIN(
                f"#/plugin-app/{plugin_id}/main?panel=pending"
            )
        except Exception:
            return None

    def send_pending(
        self,
        username: str,
        notice: PendingNotice,
    ) -> bool:
        """发送安全待处理摘要，Telegram 可用时提供直接交互。"""
        if not isinstance(notice, PendingNotice):
            raise TypeError("notice must be PendingNotice")
        detail_link = self._pending_detail_link()
        if self._interaction_service is not None:
            start_pending = getattr(self._interaction_service, "start_pending", None)
            if callable(start_pending):
                try:
                    if start_pending(
                        username=username,
                        notice=notice,
                        detail_link=detail_link or "",
                    ):
                        return True
                except Exception:
                    logger.exception(
                        "AgentRank Telegram 待处理通知失败，回退普通通知 type=%s",
                        notice.item.item_type,
                    )
        item = notice.item
        label = PENDING_TYPE_LABELS.get(item.item_type, "待处理")
        lines = [
            f"类型：{label}",
            f"内容：{_compact_text(_safe_notice_text(item.summary), 240)}",
            "状态：尚未生效",
            f"请前往 {self._agent_name()} 的待处理区域处理。",
        ]
        kwargs = {
            "mtype": resolve_notification_type(
                getattr(self._plugin, "_config", {}), MessageType
            ),
            "title": f"{self._agent_name()}待处理",
            "text": "\n".join(lines),
            "username": username,
        }
        if detail_link:
            kwargs["link"] = detail_link
        self._plugin.post_message(**kwargs)
        return False
