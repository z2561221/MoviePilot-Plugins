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
from ..model.telegram_selection import TelegramSelectionSession


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
    session_ttl_hours = 24
    caption_limit = 3500

    def __init__(
        self,
        plugin: Any,
        repository: Any,
        subscription_service: Any,
        config: Dict[str, Any],
        target_adapter: Any = None,
        token_factory: Callable[[], str] = None,
        now_factory: Callable[[], datetime] = None,
    ):
        """绑定插件、仓库、订阅安全链与可替换测试依赖。"""
        self._plugin = plugin
        self._repository = repository
        self._subscription_service = subscription_service
        self._config = config
        self._target_adapter = target_adapter or TelegramTargetAdapter()
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(7))
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()

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
    def _confidence(value: Any) -> int:
        """把 0-1 或 0-100 置信度统一为整数百分比。"""
        try:
            number = float(value or 0)
        except (TypeError, ValueError):
            return 0
        number = number * 100 if number <= 1 else number
        return max(0, min(int(round(number)), 100))

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

    def _single_page_payload(
        self,
        session: TelegramSelectionSession,
        board: RecommendationBoard,
        notice: str = "",
    ) -> Tuple[str, List[List[Dict[str, str]]], Optional[str]]:
        """生成横版封面与紧凑单行榜单正文及编号按钮。"""
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
            meta = " · ".join(
                value
                for value in (
                    str(item.year or "").strip(),
                    f"{self._confidence(item.confidence)}%",
                )
                if value
            )
            lines.append(
                f"<code>{index + 1:02d}</code> {title} · {html.escape(meta)}"
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
            mtype=NotificationType.Subscribe,
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
        """编辑为无按钮终态并保留榜首横版封面。"""
        board = (
            self._repository.load_board(session.profile_id)
            if session.profile_id
            else None
        )
        items = self._ranked_items(board) if board is not None else []
        image = self._image_url(items[0]) if items else None
        self._plugin.post_message(
            channel=MessageChannel.Telegram,
            source=event_data.get("source"),
            mtype=NotificationType.Subscribe,
            title=title,
            text=text,
            image=image,
            username=session.username,
            targets={"telegram_userid": session.telegram_userid},
            buttons=None,
            original_message_id=event_data.get("original_message_id"),
            original_chat_id=event_data.get("original_chat_id"),
            parse_mode="HTML",
            disable_web_page_preview=True,
            save_history=False,
        )

    def _post_rejection(self, event_data: Dict[str, Any], text: str) -> None:
        """向越权点击者单独发送拒绝提示，不修改原卡片。"""
        self._plugin.post_message(
            channel=MessageChannel.Telegram,
            source=event_data.get("source"),
            mtype=NotificationType.Subscribe,
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
