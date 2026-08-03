"""下载速度异常通知与 Telegram 回调的轻量协议。"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, Callable, Optional


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
SPEED_ALERT_TTL_SECONDS = 24 * 60 * 60


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


def resolve_notification_type(value: Any, notification_type: Any = None) -> Any:
    """按 MoviePilot 枚举名或显示值解析通知分类，非法值回退 Plugin。"""
    if notification_type is None:
        from app.schemas.types import NotificationType

        notification_type = NotificationType
    clean_value = str(value or "").strip()
    members = getattr(notification_type, "__members__", {})
    if clean_value in members:
        return members[clean_value]
    for member in members.values():
        if str(getattr(member, "value", "")) == clean_value:
            return member
    return members["Plugin"]


def _human_bytes(value: Any) -> str:
    """把字节或字节每秒数转换为紧凑可读文本。"""
    try:
        number = max(0.0, float(value or 0.0))
    except (TypeError, ValueError):
        number = 0.0
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    unit = units[0]
    for candidate in units:
        unit = candidate
        if number < 1024 or candidate == units[-1]:
            break
        number /= 1024
    return f"{number:.1f} {unit}"


def _human_duration(value: Any) -> str:
    """把秒数转换为稳定的时分秒文本。"""
    try:
        seconds = max(0, int(float(value or 0.0)))
    except (TypeError, ValueError):
        seconds = 0
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}小时{minutes}分{seconds}秒"
    if minutes:
        return f"{minutes}分{seconds}秒"
    return f"{seconds}秒"


def format_speed_alert_text(session: Any, decision: dict) -> str:
    """构造包含判断依据与删除风险的速度异常通知正文。"""
    details = decision if isinstance(decision, dict) else {}
    progress = max(0.0, min(1.0, float(details.get("progress") or 0.0)))
    return "\n".join([
        f"下载器：{getattr(session, 'downloader_id', '')}",
        f"任务：{getattr(session, 'name', '')}",
        f"Hash：{getattr(session, 'torrent_hash', '')}",
        f"体积：{_human_bytes(getattr(session, 'total_bytes', 0))}",
        f"进度：{progress * 100:.1f}%",
        f"当前速度：{_human_bytes(details.get('current_speed_bps'))}/s",
        f"参考速度：{_human_bytes(details.get('reference_speed_bps'))}/s",
        f"有效时长：{_human_duration(details.get('effective_seconds'))}",
        f"允许时限：{_human_duration(details.get('allowed_seconds'))}",
        "风险：删除会同时清理该种子的全部数据且不可恢复。",
    ])


def _resolve_telegram_userid(plugin: Any) -> str:
    """按 MP 超级管理员通知设置解析 Telegram 用户 ID。"""
    injected = str(
        getattr(plugin, "_speed_monitor_telegram_userid", "") or ""
    ).strip()
    if injected:
        return injected
    try:
        from ..adapter.telegram_target import resolve_admin_telegram_userid

        return resolve_admin_telegram_userid()
    except Exception:
        return ""


def _speed_alert_buttons(plugin_id: str, token: str) -> list[list[dict]]:
    """生成关闭和进入删除确认流程的 Telegram 按钮。"""
    return [[
        {
            "text": "关闭",
            "callback_data": build_speed_monitor_callback(
                plugin_id, token, "close"
            ),
        },
        {
            "text": "删除种子及全部数据",
            "callback_data": build_speed_monitor_callback(
                plugin_id, token, "delete"
            ),
        },
    ]]


def send_speed_alert(
    plugin: Any,
    alert: dict,
    session: Any,
    *,
    now: float,
    token_factory: Callable[[], str] | None = None,
    notification_type: Any = None,
) -> bool:
    """发送一条分类异常通知并把交互身份写入告警状态。"""
    token_factory = token_factory or (lambda: secrets.token_urlsafe(6))
    telegram_userid = _resolve_telegram_userid(plugin)
    kwargs = {
        "mtype": resolve_notification_type(
            getattr(plugin, "_speed_monitor_notification_type", "Plugin"),
            notification_type,
        ),
        "title": "下载速度异常",
        "text": format_speed_alert_text(session, alert.get("decision") or {}),
    }
    if telegram_userid:
        token = str(alert.get("token") or token_factory() or "").strip()
        if not token or ":" in token:
            raise ValueError("invalid speed alert callback token")
        alert["token"] = token
        alert["telegram_userid"] = telegram_userid
        alert["expires_at"] = float(now) + SPEED_ALERT_TTL_SECONDS
        kwargs["targets"] = {"telegram_userid": telegram_userid}
        kwargs["buttons"] = _speed_alert_buttons(
            plugin.__class__.__name__, token
        )
    plugin.post_message(**kwargs)
    alert["status"] = "notified"
    alert["notified_at"] = float(now)
    alert["updated_at"] = float(now)
    alert.pop("notification_error", None)
    return True


def dispatch_pending_speed_alerts(
    plugin: Any,
    runtime: Any,
    now: float,
    *,
    token_factory: Callable[[], str] | None = None,
    notification_type: Any = None,
) -> int:
    """派发全部 pending 告警，失败项保留以便下轮重试。"""
    sent = 0
    for alert in runtime.alerts.values():
        if not isinstance(alert, dict) or alert.get("status") != "pending":
            continue
        session_key = (
            f"{alert.get('downloader_id')}:{alert.get('torrent_hash')}"
        )
        session = runtime.sessions.get(session_key)
        if session is None or getattr(session, "status", "") != "active":
            continue
        try:
            if send_speed_alert(
                plugin,
                alert,
                session,
                now=now,
                token_factory=token_factory,
                notification_type=notification_type,
            ):
                sent += 1
        except Exception as error:
            alert["notification_error"] = str(error)
            alert["updated_at"] = float(now)
    return sent


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
    from .speed_actions import process_speed_message_action

    return process_speed_message_action(plugin, event_data)
