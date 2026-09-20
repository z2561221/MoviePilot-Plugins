"""使用宿主消息回执更新同一份 Telegram 清理报告。"""

from __future__ import annotations

import time
from html import unescape
from typing import Any

from app.db.oper.user import UserOper
from app.schemas.message import Message
from app.schemas.types import MessageType, NotificationChannel
from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.services import NotificationHelper, ServiceConfigHelper

from ..model.library_cleanup import read_value
from ..security import redact_sensitive_text


class NotificationOutcome:
    """区分业务发送结果与可确认的外部投递。"""

    def __init__(self, success: bool, confirmed: bool, state: str):
        self.success = success
        self.confirmed = confirmed
        self.state = state

    def __bool__(self):
        return self.success


def plain_report(text: str) -> str:
    """将受控 HTML 报告转换为其他通知渠道可读的纯文本。"""
    return unescape(text.replace("<b>", "").replace("</b>", ""))


class CleanupReportNotifier:
    """每轮独立持有各通知源的回执，避免并行任务互相编辑报告。"""

    def __init__(self, plugin, helper: Any = None):
        """记录本轮通知路由，不改变宿主通知配置。"""
        self.plugin = plugin
        self.receipts: list[dict] = []
        self.attempted: set[str] = set()
        self.failures: set[str] = set()
        try:
            configs = (helper or NotificationHelper()).get_configs().values()
            self.configs = [
                conf for conf in configs
                if conf.enabled and MessageType.Plugin.value in (conf.switchs or [])
            ]
        except Exception as err:
            self.configs = []
            self.failures.add("通知配置")
            logger.warning(f"工具中心：读取报告通知配置失败：{redact_sensitive_text(err)}")

    def _targets(self) -> dict | None:
        # 本报告没有发起用户名，按宿主后台通知的 admin/all 分流处理。
        action = ServiceConfigHelper.get_notification_switch(MessageType.Plugin) or "all"
        if action.split(",")[0] != "admin":
            return None
        return UserOper().get_settings(settings.SUPERUSER) or {}

    def start(self, title: str, text: str) -> None:
        """仅向支持回执和编辑的 Telegram 路由发送处理中报告。"""
        chain = getattr(self.plugin, "chain", None)
        send = getattr(chain, "send_direct_message", None)
        if not callable(send) or not callable(getattr(chain, "run_module", None)):
            return
        for conf in self.configs:
            if conf.type != "telegram":
                continue
            self.attempted.add(conf.name)
            try:
                targets = self._targets()
                if targets is not None and not targets.get("telegram_userid"):
                    continue
                response = send(Message(
                    channel=NotificationChannel.Telegram,
                    source=conf.name,
                    mtype=MessageType.Plugin,
                    title=title,
                    text=text,
                    parse_mode="HTML",
                    targets=targets,
                ))
                message_id = read_value(response, "message_id")
                chat_id = read_value(response, "chat_id")
                source = read_value(response, "source")
                if (
                    read_value(response, "success") is True
                    and message_id not in (None, "")
                    and chat_id not in (None, "")
                    and source == conf.name
                ):
                    self.receipts.append({
                        "source": source, "message_id": message_id, "chat_id": chat_id,
                    })
                    continue
            except Exception as err:
                logger.warning(f"工具中心：发送清理报告失败：{redact_sensitive_text(err)}")
            # 发送超时可能已经送达，缺少回执时不能再发一条冒充原消息。
            self.failures.add(conf.name)

    def update(self, title: str, text: str, *, final: bool = False) -> None:
        """按原回执编辑报告；终态编辑可重试一次，不发送替代消息。"""
        for receipt in self.receipts:
            edited = False
            for attempt in range(2 if final else 1):
                if attempt:
                    time.sleep(1)
                try:
                    # Chain.edit_message 不透传 parse_mode；沿用宿主模块分发入口。
                    edited = bool(self.plugin.chain.run_module(
                        "edit_message",
                        channel=NotificationChannel.Telegram,
                        **receipt,
                        title=title,
                        text=text,
                        buttons=None,
                        parse_mode="HTML",
                    ))
                except Exception as err:
                    logger.warning(f"工具中心：更新清理报告失败：{redact_sensitive_text(err)}")
                if edited:
                    break
            if edited:
                self.failures.discard(receipt["source"])
            else:
                self.failures.add(receipt["source"])
                logger.warning("工具中心：原清理报告未能更新，本轮结果仍保存在插件运行记录中")

    def finish(self, title: str, text: str) -> bool:
        """更新已有 Telegram 报告，并为其他渠道发送一次最终结果。"""
        self.update(title, text, final=True)
        plain_text = plain_report(text)
        for conf in self.configs:
            if conf.name in self.attempted:
                continue
            try:
                self.plugin.post_message(
                    source=conf.name,
                    mtype=MessageType.Plugin,
                    title=title,
                    text=text if conf.type == "telegram" else plain_text,
                    parse_mode="HTML" if conf.type == "telegram" else "plain",
                    save_history=False,
                )
            except Exception as err:
                self.failures.add(conf.name)
                logger.warning(f"工具中心：发送最终清理报告失败：{redact_sensitive_text(err)}")
        try:
            # 直发不自动保存宿主历史，最终文本仅在消息中心记录一次。
            self.plugin.post_message(
                channel=NotificationChannel.Web,
                mtype=MessageType.Plugin,
                title=title,
                text=plain_text,
                parse_mode="plain",
            )
        except Exception as err:
            self.failures.add("消息中心")
            logger.warning(f"工具中心：保存最终报告通知失败：{redact_sensitive_text(err)}")
        return not self.failures

    def to_dict(self) -> dict:
        """保存回执和更新状态，不保存通知源凭据。"""
        return {
            "receipts": self.receipts,
            "updated": not self.failures,
            "delivery_state": self.delivery_state,
        }

    @property
    def delivery_state(self) -> str:
        """返回 confirmed、queued 或 failed，不把入队当作确认投递。"""
        if self.failures:
            return "failed"
        if self.receipts:
            return "confirmed"
        return "queued"

    @property
    def delivery_confirmed(self) -> bool:
        return self.delivery_state == "confirmed"
