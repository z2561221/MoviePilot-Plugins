"""Telegram 异常通知的受控重试入口。"""

import html
import logging
import re
import secrets
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from app.schemas.types import MessageType, NotificationChannel

from ..adapter.telegram import TelegramTargetAdapter
from ..model.telegram_retry import TelegramRetrySession
from .notification import _compact_text, _safe_notice_text, failure_notice_text
from .notification_type import resolve_notification_type
from .prompt import configured_agent_display_name
from .telegram_interaction import TelegramSelectionService

logger = logging.getLogger(__name__)


class TelegramRunRetryService:
    """管理一次性运行重试按钮，复用宿主消息渠道与后台运行入口。"""

    session_ttl_hours = 24

    def __init__(
        self,
        plugin: Any,
        repository: Any,
        config: dict[str, Any],
        retry_handler: Callable[[str], dict[str, Any]],
        target_adapter: Any = None,
        token_factory: Callable[[], str] | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ):
        """绑定通知归属、会话存储及可替换的后台任务入口。"""
        self._plugin = plugin
        self._repository = repository
        self._config = config
        self._retry_handler = retry_handler
        self._target_adapter = target_adapter or TelegramTargetAdapter()
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(7))
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._active: dict[str, tuple[str, int]] = {}
        self._last_rendered: dict[str, tuple] = {}

    def _buttons(self, session: TelegramRetrySession) -> list[list[dict]]:
        """生成不携带画像信息且符合 Telegram 长度限制的按钮。"""
        callback = (
            f"[PLUGIN]{self._plugin.__class__.__name__}|"
            f"arr:{session.token}:r:{session.attempt}"
        )
        if len(callback.encode("utf-8")) > 64:
            raise ValueError("telegram retry callback exceeds 64 bytes")
        return [[{"text": "🔄 重试", "callback_data": callback}]]

    def create_buttons(
        self,
        profile_id: str,
        username: str,
        run_id: str,
        message: str,
    ) -> list[list[dict]] | None:
        """为可接收 Telegram 的目标用户保存重试会话。"""
        mtype = resolve_notification_type(self._config, MessageType)
        if not TelegramSelectionService._notification_sources(mtype):
            return None
        userid = self._target_adapter.resolve_userid(username)
        if not profile_id or not userid:
            return None
        now = self._now_factory()
        session = TelegramRetrySession(
            token=self._token_factory(),
            profile_id=profile_id,
            username=username,
            telegram_userid=str(userid),
            run_id=str(run_id or ""),
            message=message,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=self.session_ttl_hours)).isoformat(),
        )
        buttons = self._buttons(session)
        with self._lock:
            self._repository.save_telegram_retry_session(session)
            self._active.pop(profile_id, None)
            self._last_rendered.pop(profile_id, None)
        return buttons

    @staticmethod
    def _bind_message(
        session: TelegramRetrySession, event_data: dict[str, Any]
    ) -> bool:
        """仅从本人回调绑定原消息，拒绝缺失或冲突的来源与消息身份。"""
        incoming = tuple(
            str(event_data.get(key) or "")
            for key in (
                "source",
                "original_message_id",
                "original_chat_id",
            )
        )
        if not all(incoming):
            return False
        existing = (session.source, session.message_id, session.chat_id)
        if any(existing) and existing != incoming:
            return False
        session.source, session.message_id, session.chat_id = incoming
        return True

    def _result_buttons(self) -> list[list[dict]]:
        """成功后提供榜单页面入口，不再另发结果卡片。"""
        try:
            from app.sdk.config import settings

            link = settings.MP_DOMAIN(
                f"#/plugin-app/{self._plugin.__class__.__name__}/main"
            )
        except Exception:
            logger.debug("AgentRank 榜单详情入口不可用", exc_info=True)
            return []
        return [[{"text": "查看榜单", "url": link}]] if link else []

    def _edit_card(self, session: TelegramRetrySession, text: str = "") -> bool:
        """只调用宿主编辑操作；编辑失败保留原卡片，绝不降级为新消息。"""
        if not all((session.source, session.message_id, session.chat_id)):
            return False
        buttons = self._buttons(session) if session.status == "open" else []
        if session.status == "completed":
            buttons = self._result_buttons()
        body = text or session.message
        fingerprint = (
            session.token,
            session.attempt,
            session.status,
            body,
            repr(buttons),
        )
        if self._last_rendered.get(session.profile_id) == fingerprint:
            return True
        chain = getattr(self._plugin, "chain", None)
        dispatcher = getattr(chain, "run_module", None)
        if not callable(dispatcher):
            logger.warning(
                "AgentRank 消息编辑入口不可用 profile_id=%s", session.profile_id
            )
            return False
        try:
            # Chain.edit_message 不透传 parse_mode，使用同一公开模块分发入口明确选择 HTML。
            edited = dispatcher(
                "edit_message",
                channel=NotificationChannel.Telegram,
                source=session.source,
                message_id=session.message_id,
                chat_id=session.chat_id,
                title=f"{configured_agent_display_name(self._config.get('agent_display_name'))} · 榜单运行",
                text=html.escape(body),
                buttons=buttons,
                parse_mode="HTML",
            )
        except Exception:
            logger.warning(
                "AgentRank 原通知编辑异常 profile_id=%s",
                session.profile_id,
                exc_info=True,
            )
            return False
        if edited is not True:
            logger.warning("AgentRank 原通知尚未更新 profile_id=%s", session.profile_id)
            return False
        self._last_rendered[session.profile_id] = fingerprint
        if len(self._last_rendered) > 200:
            self._last_rendered.pop(next(iter(self._last_rendered)))
        return True

    def active_key(self, profile_id: str) -> tuple[str, int] | None:
        """返回当前重试代次，供进度与终态拒绝迟到的旧更新。"""
        with self._lock:
            return self._active.get(profile_id)

    def _active_session(
        self,
        profile_id: str,
        key: tuple[str, int] | None,
    ) -> TelegramRetrySession | None:
        """恢复仍归属于本轮重试的消息，已重置或已换轮次时失效。"""
        if key is None or self._active.get(profile_id) != key:
            return None
        session = self._repository.load_telegram_retry_session(key[0])
        if (
            session is None
            or session.status != "submitted"
            or session.attempt != key[1]
        ):
            return None
        return session

    def update_progress(
        self,
        profile_id: str,
        key: tuple[str, int],
        progress: dict[str, Any],
    ) -> bool:
        """将真实阶段快照更新到原通知，不因时间戳变化重复编辑。"""
        with self._lock:
            session = self._active_session(profile_id, key)
            if session is None or not progress.get("active"):
                return False
            stage = _compact_text(_safe_notice_text(progress.get("message")), 120)
            run_id = str(progress.get("run_id") or "")
            lines = ["状态：重试中", f"阶段：{stage or '正在准备生成榜单'}"]
            if run_id:
                lines.append(f"运行 ID：{_compact_text(run_id, 64)}")
            text = "\n".join(lines)
            if text != session.message:
                session.message = text
                if run_id:
                    session.run_id = run_id
                if not self._repository.save_telegram_retry_session(
                    session,
                    expected_status="submitted",
                    expected_attempt=key[1],
                ):
                    return False
            return self._edit_card(session)

    def finish(
        self,
        profile_id: str,
        key: tuple[str, int],
        result: Any,
    ) -> bool:
        """成功在原卡片显示结果；失败换重试代次并原地恢复按钮。"""
        with self._lock:
            session = self._active_session(profile_id, key)
            if session is None:
                return False
            status = str(getattr(result, "status", "failed") or "failed")
            run_id = str(getattr(result, "run_id", "") or "")
            board = getattr(result, "board", None)
            session.run_id = run_id
            if status in {"success", "recommendation_incomplete"}:
                items = list(getattr(board, "recommendations", []) or [])[:5]
                count = int(getattr(result, "final_count", 0) or len(items))
                lines = [
                    "状态：已完成"
                    if status == "success"
                    else "状态：已完成（推荐不足）"
                ]
                if run_id:
                    lines.append(f"运行 ID：{_compact_text(run_id, 64)}")
                lines.append(f"推荐：{max(0, count)} 条")
                lines.extend(
                    f"{index}. {_compact_text(_safe_notice_text(getattr(item, 'title', '')), 80)}"
                    for index, item in enumerate(items, 1)
                )
                session.message = "\n".join(lines)
                session.status = "completed"
            else:
                message = str(getattr(result, "message", "") or "运行失败")
                preserved = getattr(result, "old_board_preserved", board is not None)
                session.message = failure_notice_text(
                    status, run_id, message, bool(preserved)
                )
                if status == "stopped":
                    session.message = "状态：已停止\n本次重试已中断，可再次重试。"
                elif status == "running":
                    session.message = (
                        "状态：已有任务运行中\n请等待当前任务结束后再重试。"
                    )
                session.status = "open"
                session.attempt += 1
                now = self._now_factory()
                session.created_at = now.isoformat()
                session.expires_at = (
                    now + timedelta(hours=self.session_ttl_hours)
                ).isoformat()
            saved = self._repository.save_telegram_retry_session(
                session,
                expected_status="submitted",
                expected_attempt=key[1],
            )
            self._active.pop(profile_id, None)
            if saved:
                return self._edit_card(session)
            return False

    def refresh_result(self, profile_id: str, key: tuple[str, int]) -> bool:
        """对暂未送达的最终状态重试原消息编辑，不覆盖下一轮任务。"""
        with self._lock:
            if profile_id in self._active:
                return True
            session = self._repository.load_telegram_retry_session(key[0])
            if (
                session is None
                or session.profile_id != profile_id
                or session.status == "submitted"
                or session.attempt not in {key[1], key[1] + 1}
            ):
                return True
            return self._edit_card(session)

    def _superseded(self, session: TelegramRetrySession) -> bool:
        """有较新运行结果时拒绝旧通知，避免重跑已经恢复的任务。"""
        history = self._repository.load_run_history(session.profile_id)
        if not history:
            return False
        latest = history[0]
        if session.run_id:
            return latest.run_id != session.run_id or latest.status in {
                "success",
                "recommendation_incomplete",
            }
        try:
            finished = datetime.fromisoformat(latest.finished_at)
            created = datetime.fromisoformat(session.created_at)
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return finished > created
        except (TypeError, ValueError):
            return False

    def _recover_finished_submission(self, session: TelegramRetrySession) -> bool:
        """重载后无任务的旧会话只恢复状态与按钮，本次旧点击不再次执行。"""
        runtime = getattr(self._retry_handler, "__self__", None)
        in_progress = getattr(runtime, "retry_in_progress", None)
        if (
            session.profile_id in self._active
            or not callable(in_progress)
            or in_progress(session.profile_id)
            or session.is_expired(self._now_factory())
        ):
            return False
        previous_attempt = session.attempt
        session.status = "open"
        session.attempt += 1
        session.message = (
            "状态：上次重试已结束或中断\n当前没有运行中的任务，可再次点击重试。"
        )
        history = self._repository.load_run_history(session.profile_id)
        latest = history[0] if history else None
        if latest is not None and latest.run_id != session.run_id:
            session.run_id = latest.run_id
            if latest.status in {"success", "recommendation_incomplete"}:
                session.status = "completed"
                session.message = f"状态：已完成\n运行 ID：{_compact_text(latest.run_id, 64)}\n最新结果请查看榜单。"
            else:
                session.message = failure_notice_text(
                    latest.status,
                    latest.run_id,
                    latest.message,
                    self._repository.load_board(session.profile_id) is not None,
                )
        if self._repository.save_telegram_retry_session(
            session,
            expected_status="submitted",
            expected_attempt=previous_attempt,
        ):
            self._edit_card(session)
        return True

    def handle_callback(self, event_data: dict[str, Any]) -> bool:
        """校验原接收人并原子领取一次重试，重复回调不再运行。"""
        event_data = event_data or {}
        match = re.fullmatch(
            r"arr:([A-Za-z0-9_-]{6,32}):r(?::(\d{1,9}))?",
            str(event_data.get("text") or ""),
        )
        channel = event_data.get("channel")
        if (
            not match
            or event_data.get("plugin_id") != self._plugin.__class__.__name__
            or getattr(channel, "value", channel) != NotificationChannel.Telegram.value
        ):
            return False
        with self._lock:
            session = self._repository.load_telegram_retry_session(match.group(1))
            if session is None:
                logger.info("AgentRank 忽略已失效的重试回调")
                return True
            if str(event_data.get("userid") or "") != session.telegram_userid:
                logger.warning("AgentRank 拒绝非接收人的重试回调")
                return True
            if not self._bind_message(session, event_data):
                logger.warning("AgentRank 拒绝消息身份缺失或冲突的重试回调")
                return True
            attempt = int(match.group(2) or 0)
            if session.status == "submitted" and self._recover_finished_submission(
                session
            ):
                return True
            if attempt != session.attempt or session.status in {
                "submitted",
                "completed",
            }:
                self._edit_card(session)
                return True
            previous_status = session.status
            if session.is_expired(self._now_factory()):
                session.status = "expired"
            elif session.status == "open" and self._superseded(session):
                session.status = "stale"
            if session.status != "open":
                self._repository.save_telegram_retry_session(
                    session,
                    expected_status=previous_status,
                    expected_attempt=attempt,
                )
                self._edit_card(
                    session, "状态：通知已失效\n请使用最新通知或在插件页面刷新。"
                )
                return True
            previous_message = session.message
            session.status = "submitted"
            session.message = "状态：重试中\n阶段：正在准备生成榜单"
            if not self._repository.save_telegram_retry_session(
                session,
                expected_status="open",
                expected_attempt=attempt,
            ):
                return True
            self._active[session.profile_id] = (session.token, attempt)
            try:
                result = self._retry_handler(session.profile_id)
            except Exception:
                logger.warning(
                    "AgentRank Telegram 重试受理失败 profile_id=%s",
                    session.profile_id,
                    exc_info=True,
                )
                result = {"accepted": False}
            if not result.get("accepted"):
                self._active.pop(session.profile_id, None)
                session.status = "open"
                session.message = previous_message
                self._repository.save_telegram_retry_session(
                    session,
                    expected_status="submitted",
                    expected_attempt=attempt,
                )
                text = (
                    "该画像正在运行，请结束后再重试。"
                    if result.get("status") == "running"
                    else "暂未受理，请确认插件已启用后重试。"
                )
                self._edit_card(session, f"{previous_message}\n重试：{text}")
                return True
            self._edit_card(session)
            return True
