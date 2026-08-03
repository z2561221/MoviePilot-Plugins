"""下载速度异常通知与 Telegram 回调的轻量协议。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


SPEED_MONITOR_CALLBACK_PREFIX = "dmsm"
TELEGRAM_CALLBACK_LIMIT_BYTES = 64
MESSAGE_ACTION_FIELDS = (
    "plugin_id",
    "channel",
    "userid",
    "text",
    "source",
    "original_message_id",
    "original_chat_id",
)


@dataclass(frozen=True)
class CallbackValidation:
    """Telegram 回调契约校验结果。"""

    accepted: bool
    reason: str
    token: str = ""
    action: str = ""


def build_speed_monitor_callback(plugin_id: str, token: str, action: str) -> str:
    """生成符合 MoviePilot 插件格式且不超过 64 字节的回调数据。"""
    clean_plugin_id = str(plugin_id or "").strip()
    clean_token = str(token or "").strip()
    clean_action = str(action or "").strip()
    if not clean_plugin_id or not clean_token or not clean_action:
        raise ValueError("plugin_id、token 和 action 不能为空")
    if ":" in clean_token or ":" in clean_action or "|" in clean_plugin_id:
        raise ValueError("callback 字段包含保留分隔符")
    callback_data = (
        f"[PLUGIN]{clean_plugin_id}|"
        f"{SPEED_MONITOR_CALLBACK_PREFIX}:{clean_token}:{clean_action}"
    )
    if len(callback_data.encode("utf-8")) > TELEGRAM_CALLBACK_LIMIT_BYTES:
        raise ValueError("telegram callback_data exceeds 64 bytes")
    return callback_data


def parse_speed_monitor_callback(text: Any) -> Optional[tuple[str, str]]:
    """解析 MoviePilot MessageAction 已拆出的速度监控回调正文。"""
    parts = str(text or "").split(":", 2)
    if len(parts) != 3 or parts[0] != SPEED_MONITOR_CALLBACK_PREFIX:
        return None
    token = parts[1].strip()
    action = parts[2].strip()
    if not token or not action:
        return None
    return token, action


def is_telegram_channel(channel: Any) -> bool:
    """兼容 MessageChannel 枚举和值字符串判断 Telegram 渠道。"""
    value = getattr(channel, "value", channel)
    return str(value or "").strip().lower() == "telegram"


def validate_speed_monitor_callback(
    event_data: dict,
    *,
    plugin_id: str,
    telegram_userid: str,
    token: str,
    expires_at: float,
    now: float,
) -> CallbackValidation:
    """按 MP 目标用户、短 token 和过期时间校验 Telegram 回调。"""
    data = event_data if isinstance(event_data, dict) else {}
    if data.get("plugin_id") != plugin_id:
        return CallbackValidation(False, "foreign_plugin")
    if not is_telegram_channel(data.get("channel")):
        return CallbackValidation(False, "non_telegram")
    parsed = parse_speed_monitor_callback(data.get("text"))
    if not parsed:
        return CallbackValidation(False, "foreign_callback")
    callback_token, action = parsed
    if callback_token != str(token or ""):
        return CallbackValidation(False, "token_mismatch")
    if str(data.get("userid") or "") != str(telegram_userid or ""):
        return CallbackValidation(False, "unauthorized_user")
    if float(now) >= float(expires_at):
        return CallbackValidation(False, "expired")
    return CallbackValidation(True, "accepted", callback_token, action)


def original_message_kwargs(event_data: dict) -> dict:
    """返回通过 post_message 原地编辑 Telegram 卡片所需字段。"""
    data = event_data if isinstance(event_data, dict) else {}
    return {
        "source": data.get("source"),
        "original_message_id": data.get("original_message_id"),
        "original_chat_id": data.get("original_chat_id"),
    }


def handle_speed_message_action_event(plugin: Any, event: Any) -> bool:
    """识别当前插件 Telegram 回调并转交后续速度监控处理器。"""
    event_data = getattr(event, "event_data", None) or {}
    if event_data.get("plugin_id") != plugin.__class__.__name__:
        return False
    if not is_telegram_channel(event_data.get("channel")):
        return False
    if not parse_speed_monitor_callback(event_data.get("text")):
        return False
    handler = getattr(plugin, "_speed_monitor_callback_handler", None)
    if callable(handler):
        return bool(handler(event_data))
    return True
