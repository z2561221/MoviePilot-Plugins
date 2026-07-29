"""Telegram 单页榜单与待订阅选择交互服务。"""

import html
import logging
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.schemas.types import MessageChannel, NotificationType

from ..adapter.telegram import TelegramTargetAdapter
from ..model.board import RecommendationBoard, RecommendationItem
from ..model.constants import RECOMMENDATION_LIMIT
from ..model.pending_center import PendingNotice
from ..model.telegram_pending import TelegramPendingSession
from ..model.telegram_selection import TelegramSelectionSession
from .notification_type import resolve_notification_type


logger = logging.getLogger(__name__)

def _compact_text(value: Any, limit: int) -> str:
    """压缩连续空白并限制 Telegram 卡片字段长度。"""
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


class TelegramSelectionService:
    """管理 Telegram 单页榜单、待订阅选择与最终确认。"""

    callback_prefix = "ar"
    pending_callback_prefix = "arp"
    session_ttl_hours = 24
    caption_limit = 3500

    def __init__(
        self,
        plugin: Any,
        repository: Any,
        subscription_service: Any,
        config: Dict[str, Any],
        pending_center: Any = None,
        target_adapter: Any = None,
        token_factory: Callable[[], str] = None,
        now_factory: Callable[[], datetime] = None,
    ):
        """绑定插件、仓库、订阅安全链与可替换测试依赖。"""
        self._plugin = plugin
        self._repository = repository
        self._subscription_service = subscription_service
        self._config = config
        self._pending_center = pending_center
        self._target_adapter = target_adapter or TelegramTargetAdapter()
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(7))
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()

    def set_pending_center(self, service: Any) -> None:
        """绑定统一待处理中心，供运行时完成依赖组装。"""
        self._pending_center = service

    @staticmethod
    def _ranked_items(board: RecommendationBoard) -> List[RecommendationItem]:
        """返回稳定排序且不超过固定榜单数量的项目。"""
        return sorted(
            list(board.recommendations or []),
            key=lambda item: (int(item.rank), str(item.candidate_id)),
        )[:RECOMMENDATION_LIMIT]

    @staticmethod
    def _item_map(board: RecommendationBoard) -> Dict[str, RecommendationItem]:
        """按候选标识建立当前榜单项目索引。"""
        return {
            str(item.candidate_id): item
            for item in TelegramSelectionService._ranked_items(board)
        }

    @staticmethod
    def _linked_title(item: RecommendationItem) -> str:
        """返回带 TMDB 详情链接的安全标题，缺少有效 ID 时使用纯文本。"""
        title = html.escape(_compact_text(item.title, 14) or "未命名条目")
        tmdb_id = str((item.source_ids or {}).get("tmdb") or "").strip()
        if not tmdb_id.isdigit():
            return title
        media_path = "movie" if item.media_type == "movie" else "tv"
        url = f"https://www.themoviedb.org/{media_path}/{tmdb_id}"
        return f'<a href="{html.escape(url, quote=True)}">{title}</a>'

    def _image_url(self, item: RecommendationItem) -> Optional[str]:
        """返回榜首横版封面，缺失时回退到可抓取的海报地址。"""
        backdrop = str(getattr(item, "backdrop_path", "") or "").strip()
        if backdrop.lower().startswith(("http://", "https://")):
            return backdrop
        service = getattr(self._plugin, "_poster_service", None)
        poster = str(item.poster_path or "").strip()
        if service is not None and hasattr(service, "thumbnail_url"):
            poster = str(service.thumbnail_url(poster) or "").strip()
        if poster.lower().startswith(("http://", "https://")):
            return poster
        return None

    def _callback(self, token: str, action: str, argument: str = "") -> str:
        """生成符合 MoviePilot 插件格式且不超过 64 字节的回调。"""
        suffix = f":{argument}" if argument else ""
        value = (
            f"[PLUGIN]{self._plugin.__class__.__name__}|"
            f"{self.callback_prefix}:{token}:{action}{suffix}"
        )
        if len(value.encode("utf-8")) > 64:
            raise ValueError("telegram callback_data exceeds 64 bytes")
        return value

    def _pending_callback(
        self, token: str, action: str, argument: str = ""
    ) -> str:
        """生成紧凑的待处理回调数据。"""
        suffix = f":{argument}" if argument else ""
        value = (
            f"[PLUGIN]{self._plugin.__class__.__name__}|"
            f"{self.pending_callback_prefix}:{token}:{action}{suffix}"
        )
        if len(value.encode("utf-8")) > 64:
            raise ValueError("telegram pending callback_data exceeds 64 bytes")
        return value

    @staticmethod
    def _pending_type_label(item_type: str) -> str:
        """返回 Telegram 待处理卡片的类型标签。"""
        return {
            "proposal": "偏好理解",
            "question": "需要补充",
            "command": "操作确认",
        }.get(str(item_type or ""), "待处理")

    def _pending_buttons(
        self,
        session: TelegramPendingSession,
        notice: PendingNotice,
    ) -> List[List[Dict[str, str]]]:
        """生成直接答复、确认、拒绝、关闭与详情按钮。"""
        item = notice.item
        buttons: List[List[Dict[str, str]]] = []
        direct_allowed = bool(session.actor_id) and not item.requires_superuser
        if item.item_type == "question" and direct_allowed:
            for index, option in enumerate(item.options):
                buttons.append(
                    [
                        {
                            "text": _compact_text(option.get("label"), 24),
                            "callback_data": self._pending_callback(
                                session.token, "o", str(index)
                            ),
                        }
                    ]
                )
        elif item.item_type in {"proposal", "command"} and direct_allowed:
            confirm_text = "确认采纳" if item.item_type == "proposal" else "确认执行"
            reject_text = "拒绝采纳" if item.item_type == "proposal" else "拒绝执行"
            buttons.append(
                [
                    {
                        "text": confirm_text,
                        "callback_data": self._pending_callback(session.token, "y"),
                    },
                    {
                        "text": reject_text,
                        "callback_data": self._pending_callback(session.token, "x"),
                    },
                ]
            )
        if item.item_type == "question":
            buttons.append(
                [
                    {
                        "text": "关闭问询",
                        "callback_data": self._pending_callback(session.token, "x"),
                    }
                ]
            )
        final_row: List[Dict[str, str]] = []
        if session.detail_link:
            final_row.append({"text": "打开详情", "url": session.detail_link})
        if final_row:
            buttons.append(final_row)
        return buttons

    def start_pending(
        self,
        *,
        username: str,
        notice: PendingNotice,
        detail_link: str = "",
    ) -> bool:
        """向已绑定 Telegram 的用户发送安全待处理交互卡片。"""
        if not isinstance(notice, PendingNotice):
            raise TypeError("notice must be PendingNotice")
        try:
            telegram_userid = self._target_adapter.resolve_userid(username)
        except Exception as error:
            logger.warning(
                "AgentRank Telegram 待处理目标解析失败 user=%s reason=%s",
                username,
                error,
            )
            return False
        if not telegram_userid:
            return False
        now = self._now_factory()
        token = str(self._token_factory() or "").strip()
        if not token or ":" in token:
            raise ValueError("invalid telegram pending token")
        item = notice.item
        session = TelegramPendingSession(
            token=token,
            profile_id=item.profile_id,
            username=username,
            telegram_userid=str(telegram_userid),
            item_type=item.item_type,
            item_id=item.item_id,
            actor_id=notice.actor_id,
            title=item.title,
            summary=item.summary,
            option_ids=[str(value.get("option_id") or "") for value in item.options],
            requires_superuser=item.requires_superuser,
            detail_link=detail_link,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=self.session_ttl_hours)).isoformat(),
        )
        lines = [
            f"<b>{html.escape(self._pending_type_label(item.item_type))}</b>",
            html.escape(_compact_text(item.summary, 240)),
            "",
            "<i>尚未写入长期画像，也不会自动执行操作。</i>",
        ]
        if item.requires_superuser:
            lines.extend(["", "此操作需要管理员在插件详情页确认。"])
        elif item.allow_custom_answer:
            lines.extend(["", "自定义回答请在插件详情页填写。"])
        with self._lock:
            self._repository.save_telegram_pending_session(session)
        self._plugin.post_message(
            channel=MessageChannel.Telegram,
            mtype=resolve_notification_type(self._config, NotificationType),
            title="Agent榜单中心 · 待处理",
            text="\n".join(lines),
            username=username,
            targets={"telegram_userid": session.telegram_userid},
            buttons=self._pending_buttons(session, notice),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return True

    @staticmethod
    def _parse_pending_callback(
        text: str,
    ) -> Optional[Tuple[str, str, str]]:
        """解析 Telegram 待处理回调。"""
        parts = str(text or "").split(":", 3)
        if len(parts) < 3 or parts[0] != TelegramSelectionService.pending_callback_prefix:
            return None
        token = parts[1].strip()
        action = parts[2].strip()
        argument = parts[3].strip() if len(parts) == 4 else ""
        if not token or not action:
            return None
        return token, action, argument

    def _post_pending_terminal(
        self,
        session: TelegramPendingSession,
        event_data: Dict[str, Any],
        text: str,
    ) -> None:
        """删除待处理卡片并另发结果；失败时原地收束为无按钮状态。"""
        deleted = self._delete_original_message(event_data)
        self._plugin.post_message(
            channel=MessageChannel.Telegram,
            source=event_data.get("source"),
            mtype=resolve_notification_type(self._config, NotificationType),
            title="Agent榜单中心 · 待处理",
            text=html.escape(_compact_text(text, 300)),
            username=session.username,
            targets={"telegram_userid": session.telegram_userid},
            buttons=None,
            original_message_id=(
                None if deleted else event_data.get("original_message_id")
            ),
            original_chat_id=(
                None if deleted else event_data.get("original_chat_id")
            ),
            parse_mode="HTML",
            save_history=False,
        )

    def _handle_pending_callback(
        self, event_data: Dict[str, Any]
    ) -> Optional[bool]:
        """处理待处理回调；不是本协议时返回 None。"""
        parsed = self._parse_pending_callback((event_data or {}).get("text"))
        if not parsed:
            return None
        channel = (event_data or {}).get("channel")
        if getattr(channel, "value", channel) != MessageChannel.Telegram.value:
            return False
        token, action, argument = parsed
        with self._lock:
            session = self._repository.load_telegram_pending_session(token)
            if session is None:
                self._post_rejection(event_data, "待处理会话不存在或已清理。")
                return True
            if str(event_data.get("userid") or "") != session.telegram_userid:
                self._post_rejection(event_data, "这不是发送给你的待处理消息。")
                return True
            if session.is_expired(self._now_factory()):
                session.status = "expired"
                self._repository.save_telegram_pending_session(session)
                self._post_pending_terminal(
                    session, event_data, "这条待处理通知已过期，请前往详情页查看。"
                )
                return True
            if session.status != "open":
                self._post_pending_terminal(
                    session, event_data, "这条待处理通知已经处理，不会重复提交。"
                )
                return True
            get_state = getattr(self._plugin, "get_state", None)
            if callable(get_state) and not get_state():
                session.status = "disabled"
                self._repository.save_telegram_pending_session(session)
                self._post_pending_terminal(
                    session, event_data, "插件当前已停用，待处理操作不会执行。"
                )
                return True
            if self._pending_center is None:
                self._post_pending_terminal(
                    session, event_data, "待处理服务暂不可用，请前往详情页处理。"
                )
                return True
            if not session.actor_id:
                self._post_pending_terminal(
                    session, event_data, "缺少可审计用户身份，请前往详情页处理。"
                )
                return True
            kwargs: Dict[str, Any] = {
                "profile_id": session.profile_id,
                "item_type": session.item_type,
                "item_id": session.item_id,
                "actor_id": session.actor_id,
                "is_superuser": False,
            }
            message = "待处理项已处理。"
            if action == "o" and session.item_type == "question":
                try:
                    option_index = int(argument)
                except (TypeError, ValueError):
                    option_index = -1
                if not 0 <= option_index < len(session.option_ids):
                    return False
                kwargs.update(
                    action="answer",
                    option_id=session.option_ids[option_index],
                    idempotency_key=(
                        f"telegram-pending:{session.token}:{session.option_ids[option_index]}"
                    ),
                )
                message = "回答已提交，CinePilot Agent 会异步重新理解。"
            elif action == "y" and not session.requires_superuser:
                kwargs["action"] = "confirm"
                message = "已确认并完成受控处理。"
            elif action == "y" and session.requires_superuser:
                self._post_pending_terminal(
                    session, event_data, "该操作需要管理员在插件详情页确认。"
                )
                return True
            elif action == "x":
                kwargs["action"] = (
                    "close" if session.item_type == "question" else "reject"
                )
                message = (
                    "问询已关闭，不会形成负向偏好。"
                    if session.item_type == "question"
                    else "已拒绝，本次内容不会生效。"
                )
            else:
                return False
            try:
                self._pending_center.respond(**kwargs)
            except Exception as error:
                safe = getattr(error, "message", "待处理失败，请前往详情页重试")
                self._post_pending_terminal(session, event_data, str(safe))
                return True
            session.status = "resolved"
            self._repository.save_telegram_pending_session(session)
            self._post_pending_terminal(session, event_data, message)
            return True

    def _single_page_payload(
        self,
        session: TelegramSelectionSession,
        board: RecommendationBoard,
        notice: str = "",
    ) -> Tuple[str, List[List[Dict[str, str]]], Optional[str]]:
        """生成横版封面、三行式五条榜单正文及编号按钮。"""
        item_map = self._item_map(board)
        items = [
            item_map[candidate_id]
            for candidate_id in session.candidate_ids
            if candidate_id in item_map
        ]
        total = len(items)
        lines = [
            f"已选 <b>{len(session.selected_ids)}</b> / {total}",
            "",
        ]
        buttons: List[List[Dict[str, str]]] = []
        choice_buttons: List[Dict[str, str]] = []
        for index, item in enumerate(items):
            candidate_id = str(item.candidate_id)
            selected = candidate_id in session.selected_ids
            title = self._linked_title(item)
            year = html.escape(str(item.year or "").strip())
            reason = html.escape(
                _compact_text(item.reason, 120) or "暂无推荐理由"
            )
            summary = html.escape(_compact_text(item.summary, 180) or "暂无简介")
            if index:
                lines.append("")
            title_line = f"<code>{index + 1:02d}</code> {title}"
            if year:
                title_line = f"{title_line} · {year}"
            lines.extend(
                [
                    title_line,
                    f"<b>推荐：</b>{reason}",
                    f"<b>简介：</b>{summary}",
                ]
            )
            choice_buttons.append(
                {
                    "text": f"✓{index + 1:02d}" if selected else f"{index + 1:02d}",
                    "callback_data": self._callback(session.token, "t", str(index)),
                }
            )
        if notice:
            lines.extend(["", f"<i>{html.escape(_compact_text(notice, 120))}</i>"])
        lines.extend(["", "点击编号选择，确认后创建订阅。"])
        buttons.extend(
            choice_buttons[index : index + 5]
            for index in range(0, len(choice_buttons), 5)
        )
        buttons.append(
            [
                {
                    "text": "清空",
                    "callback_data": self._callback(session.token, "e"),
                },
                {
                    "text": f"确认 {len(session.selected_ids)}",
                    "callback_data": self._callback(session.token, "c"),
                },
                {
                    "text": "关闭",
                    "callback_data": self._callback(session.token, "x"),
                },
            ]
        )
        text = "\n".join(lines)
        if len(text) > self.caption_limit:
            raise ValueError("telegram single-page caption exceeds safe character limit")
        return text, buttons, self._image_url(items[0]) if items else None

    def _post(
        self,
        session: TelegramSelectionSession,
        board: RecommendationBoard,
        event_data: Dict[str, Any] = None,
        notice: str = "",
    ) -> None:
        """发送单页榜单卡片或原地更新选择状态。"""
        event_data = event_data or {}
        text, buttons, image = self._single_page_payload(session, board, notice)
        original_message_id = event_data.get("original_message_id")
        self._plugin.post_message(
            channel=MessageChannel.Telegram,
            source=event_data.get("source"),
            mtype=resolve_notification_type(self._config, NotificationType),
            title=f"Agent榜单中心 · Top {len(session.candidate_ids):02d}",
            text=text,
            image=image,
            username=session.username,
            targets={"telegram_userid": session.telegram_userid},
            buttons=buttons,
            original_message_id=original_message_id,
            original_chat_id=event_data.get("original_chat_id"),
            parse_mode="HTML",
            disable_web_page_preview=True,
            save_history=not bool(original_message_id),
        )

    def _post_terminal(
        self,
        session: TelegramSelectionSession,
        event_data: Dict[str, Any],
        title: str,
        text: str,
    ) -> None:
        """删除原榜单卡片并另发结果；失败时编辑为无按钮终态。"""
        board = (
            self._repository.load_board(session.profile_id)
            if session.profile_id
            else None
        )
        items = self._ranked_items(board) if board is not None else []
        image = self._image_url(items[0]) if items else None
        deleted = self._delete_original_message(event_data)
        self._plugin.post_message(
            channel=MessageChannel.Telegram,
            source=event_data.get("source"),
            mtype=resolve_notification_type(self._config, NotificationType),
            title=title,
            text=text,
            image=image,
            username=session.username,
            targets={"telegram_userid": session.telegram_userid},
            buttons=None,
            original_message_id=(
                None if deleted else event_data.get("original_message_id")
            ),
            original_chat_id=(
                None if deleted else event_data.get("original_chat_id")
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
            save_history=False,
        )

    def _delete_original_message(self, event_data: Dict[str, Any]) -> bool:
        """通过 MoviePilot 消息链删除原 Telegram 交互卡片。"""
        message_id = (event_data or {}).get("original_message_id")
        chain = getattr(self._plugin, "chain", None)
        delete_message = getattr(chain, "delete_message", None)
        if message_id in (None, "") or not callable(delete_message):
            return False
        try:
            return bool(
                delete_message(
                    channel=MessageChannel.Telegram,
                    source=(event_data or {}).get("source"),
                    message_id=message_id,
                    chat_id=(event_data or {}).get("original_chat_id"),
                )
            )
        except Exception:
            logger.exception("AgentRank Telegram 原交互消息删除失败，回退原地编辑")
            return False

    def _post_rejection(self, event_data: Dict[str, Any], text: str) -> None:
        """向越权点击者单独发送拒绝提示，不修改原卡片。"""
        self._plugin.post_message(
            channel=MessageChannel.Telegram,
            source=event_data.get("source"),
            mtype=resolve_notification_type(self._config, NotificationType),
            title="Agent榜单中心",
            text=html.escape(text),
            targets={"telegram_userid": str(event_data.get("userid") or "")},
            parse_mode="HTML",
            save_history=False,
        )

    @staticmethod
    def _parse_callback(text: str) -> Optional[Tuple[str, str, str]]:
        """解析插件消息事件中的紧凑选择回调。"""
        parts = str(text or "").split(":", 3)
        if len(parts) < 3 or parts[0] != TelegramSelectionService.callback_prefix:
            return None
        token = parts[1].strip()
        action = parts[2].strip()
        argument = parts[3].strip() if len(parts) == 4 else ""
        if not token or not action:
            return None
        return token, action, argument

    def start(self, profile_id: str, username: str, board: RecommendationBoard) -> bool:
        """为指定画像创建 Telegram 卡片，显示名只用于发送目标。"""
        target = str(profile_id or "").strip()
        if not target or board.profile_id != target:
            raise ValueError("telegram selection profile_id does not match board")
        items = self._ranked_items(board)
        if not items:
            return False
        try:
            telegram_userid = self._target_adapter.resolve_userid(username)
        except Exception as error:
            logger.warning("AgentRank Telegram 用户目标解析失败 user=%s reason=%s", username, error)
            return False
        if not telegram_userid:
            logger.info("AgentRank 用户未绑定 Telegram，回退摘要通知 user=%s", username)
            return False
        now = self._now_factory()
        token = str(self._token_factory() or "").strip()
        if not token or ":" in token:
            raise ValueError("invalid telegram selection token")
        session = TelegramSelectionSession(
            token=token,
            username=username,
            profile_id=target,
            telegram_userid=str(telegram_userid),
            run_id=board.run_id,
            candidate_ids=[str(item.candidate_id) for item in items],
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=self.session_ttl_hours)).isoformat(),
        )
        with self._lock:
            self._repository.save_telegram_session(session)
        self._post(session, board)
        return True

    def _confirm(
        self,
        session: TelegramSelectionSession,
        event_data: Dict[str, Any],
    ) -> None:
        """逐项执行既有订阅安全链并把原消息编辑为结果摘要。"""
        if not session.selected_ids:
            self._repository.save_telegram_session(session)
            board = self._repository.load_board(session.profile_id)
            if board is not None:
                self._post(session, board, event_data, "请至少选择一部作品后再确认。")
            return
        session.status = "processing"
        self._repository.save_telegram_session(session)
        results = []
        threshold = float(self._config.get("confidence_threshold") or 0.0)
        board = self._repository.load_board(session.profile_id)
        item_map = self._item_map(board) if board is not None else {}
        for candidate_id in session.candidate_ids:
            if candidate_id not in session.selected_ids:
                continue
            item = item_map.get(candidate_id)
            try:
                result = self._subscription_service.subscribe(
                    session.profile_id, candidate_id, threshold
                )
                if result.success and result.changed:
                    label = "✅ 已创建"
                elif result.success:
                    label = "☑️ 已存在"
                else:
                    label = f"❌ {_compact_text(result.message, 36) or '订阅失败'}"
            except Exception as error:
                logger.exception(
                    "AgentRank Telegram 订阅异常 user=%s candidate=%s",
                    session.profile_id,
                    candidate_id,
                )
                label = f"❌ {_compact_text(error, 36) or '订阅异常'}"
            results.append(
                f"{html.escape(_compact_text(getattr(item, 'title', ''), 28) or candidate_id)}　{html.escape(label)}"
            )
        session.status = "completed"
        self._repository.save_telegram_session(session)
        text = "<b>本轮订阅处理完成</b>\n\n" + "\n".join(results)
        self._post_terminal(
            session,
            event_data,
            "Agent榜单中心 · 订阅结果",
            text,
        )

    def handle_callback(self, event_data: Dict[str, Any]) -> bool:
        """处理 MoviePilot MessageAction 传入的 Telegram 轮播回调。"""
        pending_result = self._handle_pending_callback(event_data)
        if pending_result is not None:
            return pending_result
        parsed = self._parse_callback((event_data or {}).get("text"))
        if not parsed:
            return False
        channel = (event_data or {}).get("channel")
        if getattr(channel, "value", channel) != MessageChannel.Telegram.value:
            return False
        token, action, argument = parsed
        with self._lock:
            session = self._repository.load_telegram_session(token)
            if session is None:
                self._post_rejection(event_data, "本轮选择会话不存在或已清理。")
                return True
            if str(event_data.get("userid") or "") != session.telegram_userid:
                self._post_rejection(event_data, "这不是发送给你的榜单，无法操作。")
                return True
            if not session.profile_id:
                session.status = "stale"
                self._repository.save_telegram_session(session)
                self._post_terminal(
                    session,
                    event_data,
                    "Agent榜单中心 · 会话已失效",
                    "旧版选择会话缺少稳定画像身份，无法继续创建订阅。",
                )
                return True
            if session.is_expired(self._now_factory()):
                session.status = "expired"
                self._repository.save_telegram_session(session)
                self._post_terminal(
                    session,
                    event_data,
                    "Agent榜单中心 · 会话已过期",
                    "本轮选择已超过 24 小时，请等待或生成新榜单。",
                )
                return True
            if session.status == "completed":
                self._post_terminal(
                    session,
                    event_data,
                    "Agent榜单中心 · 已处理",
                    "本轮订阅已经处理完成，不会重复提交。",
                )
                return True
            terminal_messages = {
                "cancelled": (
                    "Agent榜单中心 · 已关闭",
                    "本轮选择已经关闭，没有创建任何新订阅。",
                ),
                "stale": (
                    "Agent榜单中心 · 榜单已更新",
                    "这条通知对应的榜单已经失效，请使用最新榜单通知。",
                ),
                "disabled": (
                    "Agent榜单中心 · 插件已停用",
                    "插件当前已停用，旧榜单不会继续创建订阅。",
                ),
            }
            if session.status in terminal_messages:
                title, text = terminal_messages[session.status]
                self._post_terminal(session, event_data, title, text)
                return True
            if session.status != "open":
                self._post_terminal(
                    session,
                    event_data,
                    "Agent榜单中心 · 正在处理",
                    "本轮订阅正在处理，请勿重复提交。",
                )
                return True
            get_state = getattr(self._plugin, "get_state", None)
            if callable(get_state) and not get_state():
                session.status = "disabled"
                self._repository.save_telegram_session(session)
                self._post_terminal(
                    session,
                    event_data,
                    "Agent榜单中心 · 插件已停用",
                    "插件当前已停用，旧榜单不会继续创建订阅。",
                )
                return True
            board = self._repository.load_board(session.profile_id)
            if board is None or board.run_id != session.run_id:
                session.status = "stale"
                self._repository.save_telegram_session(session)
                self._post_terminal(
                    session,
                    event_data,
                    "Agent榜单中心 · 榜单已更新",
                    "这条通知对应的榜单已失效，请使用最新榜单通知。",
                )
                return True
            item_map = self._item_map(board)
            if any(candidate_id not in item_map for candidate_id in session.candidate_ids):
                session.status = "stale"
                self._repository.save_telegram_session(session)
                self._post_terminal(
                    session,
                    event_data,
                    "Agent榜单中心 · 榜单已变化",
                    "候选内容已经变化，请使用最新榜单通知。",
                )
                return True
            total = len(session.candidate_ids)
            notice = ""
            if action == "t":
                try:
                    index = int(argument) if argument else session.current_index
                except (TypeError, ValueError):
                    index = -1
                if not 0 <= index < total:
                    return False
                candidate_id = session.candidate_ids[index]
                if candidate_id in session.selected_ids:
                    session.selected_ids.remove(candidate_id)
                    notice = f"已取消 {index + 1:02d}。"
                else:
                    session.selected_ids.append(candidate_id)
                    session.selected_ids = [
                        value
                        for value in session.candidate_ids
                        if value in session.selected_ids
                    ]
                    notice = f"已选择 {index + 1:02d}。"
            elif action == "e":
                session.selected_ids = []
                notice = "已清空本轮选择。"
            elif action == "d":
                try:
                    index = int(argument)
                except (TypeError, ValueError):
                    index = -1
                if 0 <= index < total:
                    candidate_id = session.candidate_ids[index]
                    if candidate_id in session.selected_ids:
                        session.selected_ids.remove(candidate_id)
                        notice = f"已取消 {index + 1:02d}。"
            elif action in {"p", "n", "s", "b"}:
                notice = "通知已升级为单页，请直接点击编号选择。"
            elif action == "c":
                self._confirm(session, event_data)
                return True
            elif action == "x":
                session.status = "cancelled"
                self._repository.save_telegram_session(session)
                self._post_terminal(
                    session,
                    event_data,
                    "Agent榜单中心 · 已关闭",
                    "本轮选择已关闭，没有创建任何新订阅。",
                )
                return True
            else:
                return False
            self._repository.save_telegram_session(session)
            self._post(session, board, event_data, notice)
            return True
